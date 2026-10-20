"""One stage of the inverse: A1–A4 → B5–B8 → C9–C12.

The main function below retains the actual iteration, damping retry and
backtracking loops. It owns the accepted state and explicit responses to
rejections, numerical failures and optional resolution changes. Numbered
modules compute the mathematics; checks.py evaluates numerical conditions.

FitStage supplies active observations, M, K_geometry, backend resolution tokens
and the iteration/quota limits. The selected update supplies normal-coordinate
geometry and its complete-trial tangent; the selected physics supplies fields
and reciprocal derivatives. Work and callback ordering are preserved.
"""
from . import checks
from dataclasses import replace
from copy import deepcopy
import traceback
from time import perf_counter

import numpy as np
from ordered_boundary.validation_cache import fit_geometry_validation

from .continuation.forward import ordered_calls, solve, shape_jacobian
from .continuation.geometry import FourierCurve, grid_size, integer
from .continuation.geometry_runtime import geometry_validated
from .continuation.updates import UpdateRefused
from .continuation.globalization import damping_floor, accepted_damping, shortened_stagnation, insufficient_progress


from .stage_types import (FitStage, BackendConfig, Evaluation, StageResult, StageEntry,
                          StageCheckpoint, checkpoint_signature, ResolutionResponse,
                          ScheduleResult, stage_record)
from .stage_types import _PromoteBase
from .errors import (Stop, StageQuota, TrialSolveCap, TrialWallLimit, NumericalFailure,
                     GeometryProposalCap, NORMAL_RETURN, STAGE_QUOTA)
from .work import Ledger
from .objective import Objective
from .recording import observe
from .b5_residual import normalize
from .checks import acceptance, relative_columns, resolution_check, inside_box
from .c9_lm import hanke_damping
from .c10_geometry_trial import control_step
from . import b8_gauss_newton, c9_lm, c10_geometry_trial, c11_trial_evaluation, c12_iteration, checks



@fit_geometry_validation
@geometry_validated
def fit_stage(curve, stage, contrast, update, config, ledger, *, on_accept=None, physics=None,
              objective_factory=None, resume=None, pause_after=None, resolution_response=None,
              entry=None, retain_final=False):
    """Run one stage, optionally under a fit-local ``geometry_validation`` cache.

    Exact reuse and spatial intersection checks are enabled by default. Use
    ``SC_GEOMETRY_RUNTIME=reference`` for pre-integration execution, or
    ``geometry_validation('cache', on_fit=...)`` to collect cache diagnostics. The
    generic cache callback's ``num_nodes`` is unset for this stage interface;
    resolutions remain available in the caller's FitStage record.

    ``entry`` (a previous stage's ``StageEntry``) replaces the initial production
    solve and the base refined solve when it matches this stage exactly; charges
    are replayed, so decisions and receipts are unchanged. ``retain_final`` returns
    this stage's endpoint as ``StageResult.final_entry`` for the next stage.
    """
    started = perf_counter()
    if curve.band != stage.curve_modes:
        raise ValueError("Pass the curve at the stage storage band.")
    if resolution_response is not None:
        if objective_factory not in (None, Objective) or getattr(stage, 'relaxed_tau', None) is not None:
            raise ValueError('Resolution response is qualified only for the ordinary objective')
        if stage.nodes > resolution_response.production_nodes or stage.refined_nodes > resolution_response.refined_nodes:
            raise ValueError('Starting resolution exceeds the response ceiling')
        ledger.strict_dispatch = True
    signature = checkpoint_signature(stage, contrast, config, update) if resume is not None or pause_after is not None else None
    if resume is not None:
        if resume.signature != signature or not np.array_equal(curve.coefficients, resume.current.curve.coefficients):
            raise ValueError('Resume state does not match the stage, objective, update or curve')
        for key in ('work_units', 'stage', 'stage_units', 'stage_quota', 'cap', 'solves', 'reciprocal_batches', 'failed'):
            if ledger.snapshot()[key] != resume.work[key]:
                raise ValueError('Resume ledger mismatch: '+key)
    objective = (objective_factory or Objective)(stage, contrast, config, ledger, physics=physics)
    if hasattr(objective, "model_residual") and (resume is not None or pause_after is not None):
        raise ValueError("Working-frequency checkpointing requires separately qualified W2 state")
    m = objective.count
    history, trials, acceptance_checks = [], [], []
    accepted_steps, converged, stop_reason, outcome, detail = 0, False, "maximum_iterations", NORMAL_RETURN, None
    current = None
    initial_loss = float("nan")
    checkpoint = None
    resolution_events = []
    promotion_objective = None
    qualified_controller = bool(getattr(physics, 'qualified_controller', False))
    reach_cache = {}
    resume_iteration = 0
    geometry_proposals = 0

    def admissible(candidate_curve):
        return inside_box(candidate_curve, config.domain_box)


    def finer_objective():
        nonlocal promotion_objective
        if promotion_objective is None:
            finer = replace(stage, nodes=resolution_response.production_nodes,
                            refined_nodes=resolution_response.refined_nodes)
            promotion_objective = Objective(finer, contrast, config, ledger,
                                            physics=resolution_response.physics or physics)
        return promotion_objective

    def promote(fine):
        nonlocal stage, objective, physics
        stage, objective, physics = fine.stage, fine, fine.physics
        resolution_events.append(dict(action='promoted', nodes=stage.nodes, refined_nodes=stage.refined_nodes,
                                      work=ledger.snapshot()))

    def validate(base, candidate):
        """C11. Ordinary acceptance, optional refinement, and explicit restart responses."""
        rb, rc = c11_trial_evaluation.refined_pair(objective, base, candidate, ledger)
        row, base_ok, candidate_ok = c11_trial_evaluation.checked_pair(base, candidate, rb, rc, stage, config, acceptance_checks=acceptance_checks, physics=physics, ledger=ledger,
                                                  check_base=resolution_response is not None or qualified_controller)
        if qualified_controller:
            if not base_ok:
                raise NumericalFailure('retained base lost its modal qualification')
            if not candidate_ok:
                answer=physics.respond_resolution_failure(base,candidate,stage,config,contrast,
                    space,update,ledger,trials[-1])
                if answer is False:
                    return None
                adopt_qualification(answer)
                raise _PromoteBase()
            if not row['accepted']:
                return None
            answer=physics.qualify_candidate(base,candidate,stage,config,contrast,
                space,update,ledger,trials[-1])
            if answer is True:
                return candidate
            if answer is False:
                row.update(accepted=False,numerical_obstruction=True,reason='accepted_move_fidelity')
                return None
            adopt_qualification(answer)
            raise _PromoteBase()
        if resolution_response is None:
            if not candidate_ok and config.resolution_gate == 'absolute':
                raise NumericalFailure("candidate leaves the frozen numerical-resolution regime")
            return candidate if row['accepted'] else None
        if base_ok and candidate_ok:
            return candidate if row['accepted'] else None
        if stage.nodes == resolution_response.production_nodes:
            if not base_ok:
                raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
            resolution_events.append(dict(action='reject_inaccurate_candidate', check=deepcopy(row),
                                          work=ledger.snapshot()))
            return None
        fine = finer_objective()
        ledger.reserve(2*m)
        rrb, rrc = fine.refined(base.curve), fine.refined(candidate.curve)
        finer_row, fine_base_ok, fine_candidate_ok = c11_trial_evaluation.checked_pair(rb, rc, rrb, rrc, fine.stage, config, acceptance_checks=acceptance_checks, physics=physics, ledger=ledger, check_base=True)
        resolution_events.append(dict(action='refinement_attempt', check=deepcopy(finer_row),
                                      work=ledger.snapshot()))
        if not fine_base_ok:
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        if finer_row['accepted'] and fine_candidate_ok:
            # Rebuild the factorized production evaluation at the promoted N.
            # Its refined counterpart remains in the fine objective's cache.
            rebuilt = fine.production(candidate.curve, 'promotion_candidate')
            if rebuilt is None:
                raise NumericalFailure('promoted candidate factorization failed')
            repeat, _, _ = c11_trial_evaluation.checked_pair(rb, rebuilt, rrb, rrc, fine.stage, config, acceptance_checks=acceptance_checks, physics=physics, ledger=ledger, check_base=True)
            if not repeat['accepted']:
                raise NumericalFailure('promoted candidate changed during factorization rebuild')
            promote(fine)
            return rebuilt
        if not base_ok:
            promote(fine)
            raise _PromoteBase()
        return None

    def qualified_base(evaluation):
        """No retry may start from an unresolved retained state."""
        refined = objective.refined(evaluation.curve)
        if refined is None:
            raise NumericalFailure('retained base refinement failed')
        discrepancy = relative_columns(evaluation.prediction, refined.prediction)
        if checks.fields_agree(discrepancy, stage.discrepancy_tolerances):
            return evaluation, False
        if stage.nodes == resolution_response.production_nodes:
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        fine = finer_objective()
        finer = fine.refined(evaluation.curve)
        if finer is None:
            raise NumericalFailure('retained base finer solve failed')
        discrepancy = relative_columns(refined.prediction, finer.prediction)
        if checks.fields_unresolved(discrepancy, stage.discrepancy_tolerances):
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        rebuilt = fine.production(evaluation.curve, 'promotion_base')
        if rebuilt is None:
            raise NumericalFailure('promoted base factorization failed')
        promote(fine)
        return rebuilt, True

    def adopt_qualification(frame):
        nonlocal stage,objective,current
        stage,objective,current=frame['stage'],frame['objective'],frame['evaluation']
        resolution_events.append(dict(action='modal_qualification_promotion',nodes=stage.nodes,
            refined_nodes=stage.refined_nodes,work=ledger.snapshot()))

    def gradient_frame(evaluation):
        nonlocal current,stage,objective
        # B6. Complete-trial Cartesian coefficient velocities at this accepted curve.
        space = update.prepare(evaluation.curve, stage.update_modes, stage.curve_modes)
        ledger.reserve(4 * m)  # Jacobian plus one production/refined step opportunity
        # B7–B8. Reuse forward factors; normalize the complex data derivative to J.
        J = objective.jacobian(evaluation, update, space)
        model_residual = (objective.model_residual(evaluation) if hasattr(objective, 'model_residual')
                          else evaluation.residual)
        g = (objective.gradient(evaluation, update, space, J)
                    if hasattr(objective, 'gradient') else b8_gauss_newton.gradient(J, model_residual))
        checks.require_gradient(g, J.shape[1])
        if qualified_controller:
            while True:
                answer=physics.qualify_linearization(evaluation,stage,config,contrast,space,update,ledger,
                    J,g,damping)
                if answer is None:
                    break
                adopt_qualification(answer)
                evaluation=current
                J,g=answer['matrix'],answer['gradient']
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
        if hasattr(objective, "indices"):
            row.update(active_frequencies=objective.indices,
                       maximum_full_residual=float(objective.relative_residuals(evaluation).max()),
                       working_events=deepcopy(objective.events))
        if trial is not None:
            row.update({k: trial[k] for k in ("maximum_normal_m", "rms_normal_m", "projection_relative",
                                               "speed_ratio", "accepted_fraction", "gain_ratio",
                                               "damping_feedback", "damping_floor") if k in trial})
        if g is None:
            row['terminal_linearization_skipped'] = True
        if resolution_response is not None or qualified_controller:
            row.update(nodes=stage.nodes, refined_nodes=stage.refined_nodes)
        history.append(row)
        observe(physics, 'accepted_history', row=row, evaluation=evaluation, ledger=ledger)

    def capture():
        nonlocal checkpoint
        if resume is None and pause_after is None:
            return
        checkpoint = StageCheckpoint(checkpoint_signature(stage, contrast, config, update), stage,
            replace(current, forwards=()), J.copy(), g.copy(), accepted_steps, damping,
            initial_loss, scale, deepcopy(ledger.snapshot()), deepcopy(history), deepcopy(trials),
            deepcopy(acceptance_checks), dict(objective.refined_cache))

    scale = max(float(np.linalg.norm(curve.coefficients) * update.length_unit_m), 1.0)
    smoothing = None
    if config.metric == "curvature":
        smoothing = update.length_unit_m / (config.detectability_factor *
                                            max(o.wavenumber for o in stage.observations))

    reusable = (entry is not None and resume is None and type(objective) is Objective and
                entry.matches(curve, stage, contrast, physics))
    try:
        if not admissible(curve):
            raise NumericalFailure("initial state leaves the geometry domain")
        if resume is None:
            if reusable:
                current = objective.reused(curve, entry.prediction, entry.forwards, "initial_objective")
                if entry.refined_prediction is not None:
                    objective.reusable_refined[entry.curve_bytes] = entry.refined_prediction
            else:
                # A1–A4, B5. Predictions, retained factors/traces, normalized r and loss.
                current = objective.production(curve, "initial_objective")
            if current is None:
                raise NumericalFailure("initial state is not solver-ready")
            initial_loss = current.loss
            if on_accept is not None and not qualified_controller:
                on_accept(0, current)
            if resolution_response is not None:
                current, _ = qualified_base(current)
            damping = config.initial_damping
            space, J, g = gradient_frame(current)
            if qualified_controller:
                initial_loss=current.loss
                if on_accept is not None:
                    on_accept(0,current)
            record(0, current, g, np.zeros(J.shape[1]), damping, damping)
        else:
            current, J, g = resume.current, resume.matrix.copy(), resume.gradient.copy()
            history, trials, acceptance_checks = deepcopy((resume.history, resume.trials, resume.checks))
            geometry_proposals = sum(t.get('geometry_constructed', True) for t in trials)
            accepted_steps, resume_iteration = resume.iteration, resume.iteration
            damping, initial_loss, scale = resume.damping, resume.initial_loss, resume.scale
            objective.refined_cache = dict(resume.refined_cache)
            space = update.prepare(current.curve, stage.update_modes, stage.curve_modes)
            if resolution_response is not None:
                current, changed = qualified_base(current)
                if changed:
                    space, J, g = gradient_frame(current)
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
            # B8, C9. H_GN = J.T @ J; construct D and choose the retry damping.
            H_GN = b8_gauss_newton.curvature(J)
            D = c9_lm.damping_matrix(H_GN, space, update, config, smoothing)
            accepted = None
            lambda_trial = damping
            rule = None
            restart = False
            accuracy_limited = False
            seen_steps = set()
            floor = damping_floor(H_GN, D, config.damping_floor_relative) if config.damping_rule == 'agreement' else 0.
            if floor:
                lambda_trial = max(lambda_trial, floor)
            if config.damping_rule == "hanke":
                lambda_trial, attainable = hanke_damping(J, current.residual, D, config.hanke_ratio)
                rule = dict(hanke_lambda=float(lambda_trial), hanke_attainable=bool(attainable))
            # C9. Each damping retry solves for new optimizer coordinates.
            for _ in range(config.max_damping_trials):
                try:
                    a_raw = c9_lm.solve_proposal(g, H_GN, D, lambda_trial)
                except np.linalg.LinAlgError:
                    lambda_trial *= config.damping_increase
                    continue
                raw_norm = float(np.linalg.norm(a_raw))
                observed_raw_proposal = a_raw.copy() if getattr(physics, 'observer', None) is not None else None
                a_bounded = c10_geometry_trial.control_step(a_raw, space, update, config)
                clipping = {}
                if config.reach_fraction:
                    from bem_inverse.reach import clip_direction
                    a_bounded, clipping = clip_direction(a_bounded, space.curve, update.length_unit_m,
                                                        config.reach_fraction, reach_cache)
                observe(physics, 'proposal', evaluation=current, space=space, J=J,
                    gradient=g, normal=H_GN, metric=D, damping=lambda_trial,
                    raw_proposed=observed_raw_proposal, bounded_proposed=a_bounded, controller_floor=floor,
                    stage=stage, config=config, ledger=ledger)
                # C10. Bound once, then successively halve the coordinate proposal.
                for backtrack in range(config.max_backtracks + 1):
                    if config.damping_rule == 'agreement':
                        ledger.reserve(0)  # deadline/work check before geometry, even after pure refusals
                        checks.require_geometry_proposal_allowance(geometry_proposals, config.geometry_proposal_cap)
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
                    if resolution_response is not None or qualified_controller:
                        trial.update(proposal_nodes=stage.nodes, proposal_refined_nodes=stage.refined_nodes)
                    trials.append(trial)
                    if feedback:
                        key = np.ascontiguousarray(a_used).tobytes()
                        if key in seen_steps:
                            trial.update(status='refused', reason='repeated_clipped_proposal', geometry_constructed=False)
                            continue
                        seen_steps.add(key)
                    geometry_proposals += 1
                    trial['geometry_constructed'] = True
                    geometry_started = perf_counter()
                    try:
                        candidate_curve, geometry = update.trial(space, a_used)
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
                    observe(physics, 'geometry_trial', base=current.curve, candidate=candidate_curve,
                        step=a_used, space=space, trial=trial, ledger=ledger,
                        certificates=deepcopy(getattr(update,'records',[])))
                    if not admissible(candidate_curve):
                        trial.update(status="refused", reason="outside_domain")
                        continue
                    if hasattr(objective, 'candidate'):
                        from bem_inverse.working_frequency import WorkingSetChanged
                        try:
                            candidate = objective.candidate(current, candidate_curve)
                        except WorkingSetChanged:
                            trial.update(status='working_model_rebuild', **objective.last_trial)
                            space, J, g = gradient_frame(current)
                            restart = True
                            break
                        trial.update(objective.last_trial)
                    else:
                        # C11 reuses A1–A4 and B5, keeping this trial separate from current.
                        candidate = objective.production(candidate_curve, "candidate")
                    if candidate is None:
                        trial.update(status='physics_failed', reason='production_evaluation_failed',
                                     physics_failures=deepcopy(getattr(objective, 'failures', [])))
                        raise NumericalFailure("production evaluation failed at candidate state")
                    checks.require_finite_trial(candidate)
                    trial.update(loss=candidate.loss)
                    if checks.production_nondecreasing(candidate.loss, current.loss):
                        trial["status"] = "nondecreasing"
                        continue
                    before_checks = len(acceptance_checks)
                    try:
                        qualified = validate(current, candidate)
                    except _PromoteBase:
                        trial.update(status='base_promotion_retry', nodes=stage.nodes)
                        current = objective.production(current.curve, 'promotion_base')
                        if current is None:
                            raise NumericalFailure('promoted base factorization failed')
                        space, J, g = gradient_frame(current)
                        restart = True
                        break
                    if qualified is None:
                        inaccurate = any(c.get('numerical_obstruction', False) for c in acceptance_checks[before_checks:])
                        accuracy_limited |= inaccurate
                        trial["status"] = "numerical_rejection" if inaccurate else "acceptance_margin"
                        if hasattr(objective, 'reject'):
                            from bem_inverse.working_frequency import WorkingSetChanged
                            try:
                                objective.reject(current, candidate)
                            except WorkingSetChanged:
                                trial.update(status='working_model_rebuild', **objective.last_trial)
                                space, J, g = gradient_frame(current)
                                restart = True
                                break
                        continue
                    candidate = qualified
                    if resolution_response is not None:
                        trial.update(original_production_loss=trial['loss'], loss=candidate.loss,
                                     nodes=stage.nodes, refined_nodes=stage.refined_nodes)
                    if config.log_model or feedback:
                        trial["actual_decrease"] = current.loss-candidate.loss
                        pred = trial["predicted_decrease"]
                        trial["gain_ratio"] = trial["actual_decrease"]/pred if pred > 0 else None
                    trial["status"] = "accepted"
                    accepted = (candidate, a_used, lambda_trial, trial)
                    break
                if accepted is not None or restart:
                    break
                lambda_trial *= config.damping_increase
            if restart:
                iteration -= 1  # same iteration, original quota and damping
                continue
            if accepted is None:
                stop_reason = "accuracy_limited_trials_exhausted" if accuracy_limited else "no_decreasing_step"
                if accuracy_limited:
                    outcome = 'KU_CAP_UNRESOLVED' if qualified_controller else 'ACCURACY_LIMITED_TRIALS'
                break
            # C12. Commit only the accepted geometry; preserve callback/rebuild order.
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
            if (config.avoid_terminal_linearization and terminal and pause_after is None and
                    resume is None and resolution_response is None):
                # on_accept has already observed the current evaluation; no callback
                # receives a tangent. Checkpoint/resolution-response paths retain it.
                record(iteration, current, None, a_used, used_damping, damping, trial)
                if checks.loss_converged(current.loss, config.loss_tolerance):
                    converged, stop_reason = True, 'loss_tolerance'
                break
            space, J, g = gradient_frame(current)
            record(iteration, current, g, a_used, used_damping, damping, trial)
            capture()
            if (config.damping_rule == 'agreement' and not checks.loss_converged(current.loss, config.loss_tolerance) and
                    config.plain_progress_exit and
                    insufficient_progress(history, config.progress_window, config.minimum_relative_progress)):
                stop_reason = 'progress_exit'
                break
            if (config.damping_rule == 'agreement' and not config.plain_progress_exit and
                    not checks.loss_converged(current.loss, config.loss_tolerance) and
                    shortened_stagnation(history, config.progress_window, config.minimum_relative_progress)):
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
    if resolution_response is not None and trials and 'status' not in trials[-1]:
        trials[-1].update(status=outcome, reason=detail)
    final = curve if current is None else current.curve
    final_entry = None
    if retain_final and current is not None and type(objective) is Objective and len(current.forwards) == m:
        key = current.curve.coefficients.tobytes()
        refined = objective.refined_cache.get(key)
        final_entry = StageEntry(key, current.curve.band, stage.nodes, stage.refined_nodes, tuple(stage.observations),
            float(contrast), physics, current.prediction, current.forwards,
            refined.prediction if refined is not None else objective.reusable_refined.get(key))
    return StageResult(stage.label, final, outcome, stop_reason, converged, accepted_steps, initial_loss,
                       float("nan") if current is None else current.loss, history, trials, acceptance_checks,
                       detail, ledger.snapshot(), perf_counter() - started, checkpoint,
                       resolution_events, stage.nodes, stage.refined_nodes,
                       deepcopy(getattr(objective, 'failures', [])), geometry_proposals,
                       final_entry, reusable)


class FixedSchedule:
    """The simplest policy: a declared list of stages, ignoring history."""

    def __init__(self, stages, name="fixed schedule"):
        self.stages, self.name = tuple(stages), name

    def next_stage(self, history):
        return self.stages[len(history)] if len(history) < len(self.stages) else None


def run_policy(initial, policy, contrast, update, config, ledger, *, on_stage=None, on_accept=None):
    """Policy loop. `on_stage(stage, result)` is the external endpoint hook.

    The hook may raise `Stop` (for example a failed endpoint numerical check);
    its return value is ignored, so evaluation cannot steer the policy.
    """
    history = []
    stage = policy.next_stage(history)
    if stage is None:
        return ScheduleResult("NO_STAGE", initial, history, 0.0)
    curve, regauge_error = update.regauge(initial, stage.curve_modes)
    status, reason, detail = "COMPLETED_SCHEDULE", None, None
    try:
        while stage is not None:
            if curve.band < stage.curve_modes:
                pad = stage.curve_modes - curve.band
                curve = FourierCurve(np.pad(curve.coefficients, (pad, pad)))
            elif curve.band > stage.curve_modes:
                curve, _ = update.regauge(curve, stage.curve_modes)
            ledger.begin_stage(stage.label, stage.quota)
            result = fit_stage(curve, stage, contrast, update, config, ledger,
                               on_accept=None if on_accept is None else
                               (lambda i, e, s=stage: on_accept(s, i, e)))
            history.append(result)
            curve = result.curve
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                status, reason, detail = "HARD_STOP", result.outcome, result.detail
                break
            if on_stage is not None:
                on_stage(stage, result)
            stage = policy.next_stage(history)
    except Stop as exc:
        status, reason, detail = "HARD_STOP", exc.code, str(exc)
    return ScheduleResult(status, curve, history, regauge_error, reason, detail)
