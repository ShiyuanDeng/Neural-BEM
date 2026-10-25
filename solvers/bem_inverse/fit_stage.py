"""One stage of the inverse: A1–A4 → B5–B8 → C9–C12.

The main function below retains the actual iteration, damping retry and
backtracking loops. It owns the accepted state and the responses to rejected
lengths and numerical failures. Two local steps carry the mathematics:
``evaluate`` (A1–A4 forward solves, then the B5 residual) and ``linearize``
(B6 update space, B7 derivatives, B8 J and g). checks.py evaluates numerical
conditions.

FitStage supplies active observations, M, K_geometry, the backend resolution
token and the iteration/quota limits. The selected update supplies
normal-coordinate geometry and its complete-trial tangent; the selected physics
supplies fields and reciprocal derivatives. A trial curve is accepted when its
loss is lower than the current loss; nothing is re-solved at a finer resolution.
"""
from dataclasses import replace
from copy import deepcopy
import traceback
from time import perf_counter

import numpy as np
from ordered_boundary.validation_cache import fit_geometry_validation

from .continuation.geometry_runtime import geometry_validated
from .c9_lm import damping_floor, hanke_damping
from .stage_types import StageResult, StageEntry, StageCheckpoint, checkpoint_signature
from .errors import Stop, StageQuota, NumericalFailure, UpdateRefused, NORMAL_RETURN, STAGE_QUOTA
from .forward_batch import solve_frequencies
from .forward_solvers import bind_forward_solve
from .recording import observe
from .geometry_update_methods import bind_geometry_update, control_step
from . import b5_residual, b8_gauss_newton, c9_lm, c12_iteration, checks



@fit_geometry_validation
@geometry_validated
def fit_stage(curve, stage, contrast, update, config, ledger, *, physics, on_accept=None,
              resume=None, pause_after=None, entry=None, retain_final=False):
    """Run one stage, optionally under a fit-local ``geometry_validation`` cache.

    Exact reuse and spatial intersection checks are enabled by default. Use
    ``SC_GEOMETRY_RUNTIME=reference`` for pre-integration execution, or
    ``geometry_validation('cache', on_fit=...)`` to collect cache diagnostics. The
    generic cache callback's ``num_nodes`` is unset for this stage interface;
    resolutions remain available in the caller's FitStage record.

    ``entry`` (a previous stage's ``StageEntry``) replaces the initial forward
    solves when it matches this stage exactly; their charges are replayed, so
    decisions and receipts are unchanged. ``retain_final`` returns this stage's
    endpoint as ``StageResult.final_entry`` for the next stage.
    """
    started = perf_counter()
    geometry_update = bind_geometry_update(update)
    forward_solve = bind_forward_solve(physics)  # modal_muller.forward_solve or nodal_kress.forward_solve
    if curve.band != stage.curve_modes:
        raise ValueError("Pass the curve at the stage storage band.")
    signature = checkpoint_signature(stage, contrast, config, update) if resume is not None or pause_after is not None else None
    if resume is not None:
        if resume.signature != signature or not np.array_equal(curve.coefficients, resume.current.curve.coefficients):
            raise ValueError('Resume state does not match the stage, objective, update or curve')
        for key in ('work_units', 'stage', 'stage_units', 'stage_quota', 'cap', 'solves', 'reciprocal_batches', 'failed'):
            if ledger.snapshot()[key] != resume.work[key]:
                raise ValueError('Resume ledger mismatch: '+key)
    observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
    m = len(stage.observations)
    failures = []
    history, trials = [], []
    accepted_steps, converged, stop_reason, outcome, detail = 0, False, "maximum_iterations", NORMAL_RETURN, None
    current = None
    initial_loss = float("nan")
    checkpoint = None
    reach_cache = {}
    resume_iteration = 0
    geometry_proposals = 0

    def evaluate(curve, category, reused=None):
        """A1–A4 at every active frequency, then B5: residual r and loss. None if a solve fails.

        ``reused`` is an exactly matching previous endpoint (prediction, forward states);
        its solves are charged as if they ran, but not repeated.
        """
        if reused is None:
            batch = solve_frequencies(curve, stage.observations, contrast, stage.nodes, category,
                                      forward_solve=forward_solve, ledger=ledger, physics=physics, failures=failures)
            if batch is None:
                return None
        else:
            ledger.reserve(m)
            ledger.replay('solve', category, m)
            batch = reused
        prediction, forwards = batch
        evaluation = b5_residual.evaluate(curve, prediction, forwards, observed, stage.weights, config.residual_floor)
        observe(physics, 'objective', stage=stage, config=config, ledger=ledger,
                evaluation=evaluation, observed=observed)
        return evaluation

    def linearize(evaluation):
        """B6–B8 at an evaluated curve: update space, residual Jacobian J and gradient g."""
        # B6. Complete-trial Cartesian coefficient velocities at this curve.
        space = update.prepare(evaluation.curve, stage.update_modes, stage.curve_modes)
        ledger.reserve(2 * m)  # the Jacobian, then one trial evaluation
        # B7. Reciprocal derivatives reuse each frequency's forward factors.
        blocks = []
        with ledger.calls(physics.ordered_calls, lambda forward: physics.derivative(forward, update, space),
                          evaluation.forwards, "reciprocal", "derivative") as calls:
            for call in calls:
                block = call()
                blocks.append(block.reshape(-1, block.shape[-1]))
        # B8. The B5 map applied to each data derivative column gives J; then g = J.T r.
        J = b8_gauss_newton.residual_jacobian(blocks, observed, stage.weights, config.residual_floor)
        g = b8_gauss_newton.gradient(J, evaluation.residual)
        checks.require_gradient(g, J.shape[1])
        observe(physics, 'linearization', evaluation=evaluation, space=space, J=J,
                gradient=g, stage=stage, config=config, ledger=ledger)
        return space, J, g

    def record(iteration, evaluation, g, a_used, damping, next_damping, trial=None):
        row = dict(iteration=iteration, loss=evaluation.loss, relative_l2=evaluation.relative_l2,
                   gradient_inf=None if g is None else float(np.linalg.norm(g, ord=np.inf)),
                   step_norm_m=float(np.linalg.norm(a_used)), damping=float(damping),
                   next_damping=float(next_damping), step_m=np.asarray(a_used, float).tolist(),
                   coefficients=dict(real=evaluation.curve.coefficients.real.tolist(),
                                     imag=evaluation.curve.coefficients.imag.tolist()),
                   work=ledger.snapshot())
        if trial is not None:
            row.update({k: trial[k] for k in ("maximum_normal_m", "rms_normal_m",
                                               "speed_ratio", "accepted_fraction", "gain_ratio",
                                               "damping_feedback", "damping_floor") if k in trial})
        if g is None:
            row['terminal_linearization_skipped'] = True
        history.append(row)
        observe(physics, 'accepted_history', row=row, evaluation=evaluation, ledger=ledger)

    def capture():
        nonlocal checkpoint
        if resume is None and pause_after is None:
            return
        checkpoint = StageCheckpoint(checkpoint_signature(stage, contrast, config, update), stage,
            replace(current, forwards=()), J.copy(), g.copy(), accepted_steps, damping,
            initial_loss, scale, deepcopy(ledger.snapshot()), deepcopy(history), deepcopy(trials))

    scale = max(float(np.linalg.norm(curve.coefficients) * update.length_unit_m), 1.0)
    smoothing = None
    if config.metric == "curvature":
        smoothing = update.length_unit_m / (config.detectability_factor *
                                            max(o.wavenumber for o in stage.observations))

    reusable = entry is not None and resume is None and entry.matches(curve, stage, contrast, physics)
    try:
        if not checks.inside_box(curve, config.domain_box):
            raise NumericalFailure("initial state leaves the geometry domain")
        if resume is None:
            current = evaluate(curve, "initial_objective",
                               (np.array(entry.prediction, copy=True), entry.forwards) if reusable else None)
            if current is None:
                raise NumericalFailure("initial state is not solver-ready")
            initial_loss = current.loss
            if on_accept is not None:
                on_accept(0, current)
            damping = config.initial_damping
            space, J, g = linearize(current)
            record(0, current, g, np.zeros(J.shape[1]), damping, damping)
        else:
            current, J, g = resume.current, resume.matrix.copy(), resume.gradient.copy()
            history, trials = deepcopy((resume.history, resume.trials))
            geometry_proposals = sum(t.get('geometry_constructed', True) for t in trials)
            accepted_steps, resume_iteration = resume.iteration, resume.iteration
            damping, initial_loss, scale = resume.damping, resume.initial_loss, resume.scale
            space = update.prepare(current.curve, stage.update_modes, stage.curve_modes)
        capture()
        if checks.loss_converged(current.loss, config.loss_tolerance):
            converged, stop_reason = True, "loss_tolerance"
        elif checks.gradient_converged(g, config.gradient_tolerance):
            converged, stop_reason = True, "gradient_tolerance"
        iteration = resume_iteration
        while iteration < stage.iterations:
            if converged:
                break
            if pause_after is not None and accepted_steps >= pause_after:
                outcome, stop_reason = 'PAUSED', 'accepted_state_pause'
                break
            iteration += 1
            # One iteration = one accepted step. J and g (B7–B8) were built at the
            # end of the previous iteration, or at stage entry for the first one.
            # B8. H_GN = J.T @ J, formed once per iteration from that J.
            H_GN = b8_gauss_newton.curvature(J)
            # C9. Damping metric D, then the starting damping lambda_trial. The
            # configured rule is 'agreement' (floor), 'hanke', or the carried value.
            D = c9_lm.damping_matrix(H_GN, space, update, config, smoothing)
            accepted = None
            lambda_trial = damping
            rule = None
            seen_steps = set()
            floor = damping_floor(H_GN, D, config.damping_floor_relative) if config.damping_rule == 'agreement' else 0.
            if floor:
                lambda_trial = max(lambda_trial, floor)
            if config.damping_rule == "hanke":
                lambda_trial, attainable = hanke_damping(J, current.residual, D, config.hanke_ratio)
                rule = dict(hanke_lambda=float(lambda_trial), hanke_attainable=bool(attainable))
            # Outer retry loop (C9): each pass solves (H_GN + lambda_trial D) a_raw = -g.
            # A singular system, or a pass whose backtracking finds no accepted step,
            # multiplies lambda_trial by damping_increase and tries again.
            for _ in range(config.max_damping_trials):
                try:
                    a_raw = c9_lm.solve_proposal(g, H_GN, D, lambda_trial)
                except np.linalg.LinAlgError:
                    lambda_trial *= config.damping_increase
                    continue
                raw_norm = float(np.linalg.norm(a_raw))
                observed_raw_proposal = a_raw.copy() if getattr(physics, 'observer', None) is not None else None
                a_bounded = control_step(a_raw, space, update, config)
                clipping = {}
                if config.reach_fraction:
                    from bem_inverse.reach import clip_direction
                    a_bounded, clipping = clip_direction(a_bounded, space.curve, update.length_unit_m,
                                                        config.reach_fraction, reach_cache)
                observe(physics, 'proposal', evaluation=current, space=space, J=J,
                    gradient=g, normal=H_GN, metric=D, damping=lambda_trial,
                    raw_proposed=observed_raw_proposal, bounded_proposed=a_bounded, controller_floor=floor,
                    stage=stage, config=config, ledger=ledger)
                # Backtracking: construct and evaluate a_used = 0.5**backtrack * a_bounded.
                # `continue` below means "this length failed, halve it". Each failure
                # records its reason in `trial` (refused, outside_domain, nondecreasing).
                for backtrack in range(config.max_backtracks + 1):
                    if config.damping_rule == 'agreement':
                        ledger.reserve(0)  # deadline/work check before geometry, even after pure refusals
                        checks.require_geometry_proposal_allowance(geometry_proposals, config.geometry_proposal_cap)
                    # Halve the step and skip it when it is below the relative tolerance.
                    a_used = 0.5 ** backtrack * a_bounded
                    if checks.step_too_small(a_used, scale, config.relative_step_tolerance):
                        continue
                    trial = dict(iteration=iteration, damping=float(lambda_trial), backtrack=backtrack,
                                 step_norm_m=float(np.linalg.norm(a_used)), **clipping)
                    feedback = config.damping_rule == 'agreement'
                    if feedback:
                        fraction = float(np.linalg.norm(a_used)/max(raw_norm, np.finfo(float).tiny))
                        trial.update(accepted_fraction=fraction, damping_floor=floor,
                                     clipping_fraction=float(np.linalg.norm(a_bounded)/max(raw_norm, np.finfo(float).tiny)))
                    if config.log_model or feedback:
                        trial["step_m"] = a_used.tolist()
                    if config.log_model or feedback:
                        trial.update(predicted_decrease=float(-(g @ a_used) - 0.5 * a_used @ H_GN @ a_used),
                                     **(rule or {}))
                    trials.append(trial)
                    if feedback:
                        key = np.ascontiguousarray(a_used).tobytes()
                        if key in seen_steps:
                            trial.update(status='refused', reason='repeated_clipped_proposal', geometry_constructed=False)
                            continue
                        seen_steps.add(key)
                    # C10. Build the trial curve. The selected method runs its own
                    # checks and raises UpdateRefused, which counts as a rejected length.
                    geometry_proposals += 1
                    trial['geometry_constructed'] = True
                    geometry_started = perf_counter()
                    try:
                        c_trial, geometry = geometry_update(a_used, prepared=space)
                        trial.update(geometry)
                        if 'a_used' in geometry:
                            a_used = np.asarray(geometry['a_used'], float)
                            trial['step_m'] = a_used.tolist()
                            trial['step_norm_m'] = float(np.linalg.norm(a_used))
                            if feedback:
                                trial['accepted_fraction'] = float(np.linalg.norm(a_used)/max(raw_norm, np.finfo(float).tiny))
                            if config.log_model or feedback:
                                trial['predicted_decrease'] = float(-g@a_used-.5*a_used@H_GN@a_used)
                    except UpdateRefused as exc:
                        trial.update(getattr(update, "last_trial", {}))
                        trial.update(status="refused", reason=exc.reason, detail=exc.detail)
                        if config.log_model:
                            trial["geometry_seconds"] = perf_counter()-geometry_started
                        observe(physics, 'geometry_trial', base=current.curve, candidate=None,
                            step=a_used, space=space, trial=trial, ledger=ledger,
                            certificates=deepcopy(getattr(update,'records',[])),traceback=traceback.format_exc())
                        continue
                    if config.log_model:
                        trial["geometry_seconds"] = perf_counter()-geometry_started
                    observe(physics, 'geometry_trial', base=current.curve, candidate=c_trial,
                        step=a_used, space=space, trial=trial, ledger=ledger,
                        certificates=deepcopy(getattr(update,'records',[])))
                    if not checks.inside_box(c_trial, config.domain_box):
                        trial.update(status="refused", reason="outside_domain")
                        continue
                    # A1–A4 → B5 at the trial curve.
                    evaluation = evaluate(c_trial, "candidate")
                    if evaluation is None:
                        trial.update(status='physics_failed', reason='production_evaluation_failed',
                                     physics_failures=deepcopy(failures))
                        raise NumericalFailure("production evaluation failed at candidate state")
                    checks.require_finite_trial(evaluation)
                    trial.update(loss=evaluation.loss)
                    # C11. The trial is accepted when its loss is lower than the current loss.
                    if checks.production_nondecreasing(evaluation.loss, current.loss):
                        trial["status"] = "nondecreasing"
                        continue
                    if config.log_model or feedback:
                        trial["actual_decrease"] = current.loss-evaluation.loss
                        pred = trial["predicted_decrease"]
                        trial["gain_ratio"] = trial["actual_decrease"]/pred if pred > 0 else None
                    trial["status"] = "accepted"
                    accepted = (evaluation, a_used, lambda_trial, trial)
                    break
                if accepted is not None:
                    break
                lambda_trial *= config.damping_increase
            if accepted is None:
                stop_reason = "no_decreasing_step"
                break
            # C12. Accepted step: commit it, set the next damping, call on_accept,
            # rebuild J and g at the new state, then test the stopping conditions.
            # Callback, rebuild and stop-test order is part of the preserved behaviour.
            current, a_used, used_damping, trial = accepted
            accepted_steps = iteration
            if config.damping_rule == 'agreement':
                damping, trial['damping_feedback'] = c12_iteration.accepted_damping(used_damping, floor,
                    trial['accepted_fraction'], trial['gain_ratio'], config)
            else:
                damping = c12_iteration.scheduled_damping(used_damping, config.damping_decrease)
            if on_accept is not None:
                on_accept(iteration, current)
            terminal = checks.loss_converged(current.loss, config.loss_tolerance) or iteration >= stage.iterations
            if config.avoid_terminal_linearization and terminal and pause_after is None and resume is None:
                # on_accept has already observed the current evaluation; no callback
                # receives a tangent. Checkpoint paths retain it.
                record(iteration, current, None, a_used, used_damping, damping, trial)
                if checks.loss_converged(current.loss, config.loss_tolerance):
                    converged, stop_reason = True, 'loss_tolerance'
                break
            space, J, g = linearize(current)
            record(iteration, current, g, a_used, used_damping, damping, trial)
            capture()
            if (config.damping_rule == 'agreement' and not checks.loss_converged(current.loss, config.loss_tolerance) and
                    config.plain_progress_exit and
                    checks.insufficient_progress(history, config.progress_window, config.minimum_relative_progress)):
                stop_reason = 'progress_exit'
                break
            if (config.damping_rule == 'agreement' and not config.plain_progress_exit and
                    not checks.loss_converged(current.loss, config.loss_tolerance) and
                    checks.shortened_stagnation(history, config.progress_window, config.minimum_relative_progress)):
                stop_reason = 'shortened_step_stagnation'
                break
            if checks.loss_converged(current.loss, config.loss_tolerance):
                converged, stop_reason = True, "loss_tolerance"
            elif checks.gradient_converged(g, config.gradient_tolerance):
                converged, stop_reason = True, "gradient_tolerance"
            elif checks.step_too_small(a_used, scale, config.relative_step_tolerance):
                converged, stop_reason = True, "relative_step_tolerance"
    except StageQuota as exc:
        outcome, stop_reason, detail = STAGE_QUOTA, None, str(exc)
    except Stop as exc:
        outcome, stop_reason, detail = exc.code, None, str(exc)
    final = curve if current is None else current.curve
    final_entry = None
    if retain_final and current is not None and len(current.forwards) == m:
        final_entry = StageEntry(current.curve.coefficients.tobytes(), current.curve.band, stage.nodes,
            tuple(stage.observations), float(contrast), physics, current.prediction, current.forwards)
    return StageResult(stage.label, final, outcome, stop_reason, converged, accepted_steps, initial_loss,
                       float("nan") if current is None else current.loss, history, trials,
                       detail, ledger.snapshot(), perf_counter() - started, checkpoint,
                       deepcopy(failures), geometry_proposals, final_entry, reusable)
