"""Truth-free policy interpreter. Every physics operation uses the chosen service."""
from contextlib import contextmanager
from dataclasses import dataclass, replace
import signal
from threading import current_thread, main_thread
from time import perf_counter
import traceback
import numpy as np

from bem_inverse.continuation.geometry_runtime import geometry_runtime, geometry_validated
from bem_inverse.continuation.lm_backend import (
    Ledger, Objective, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA)
from .geometry import ProjectedUpdate, resize, cleanup
from .geometry_selection import make_update, describe_plan, operation_record
from .io import write, curve_record
from .localization import localize
from .physics import make_backend
from .policy import CumulativePolicy, readable_plan


class RequiredAccuracyReached(Stop):
    code = 'REQUIRED_ACCURACY_REACHED'


@dataclass(frozen=True)
class FitResume:
    """Resolved policy queue and exact accepted-state optimizer checkpoint.

    Queue entry zero is the interrupted stage. Earlier decisions (including
    an already measured frontier) are retained; a future frontier is measured
    normally. Historical costs reside in ``stage.work``.
    """
    stage: object
    operations: tuple
    stages: tuple = ()
    decisions: tuple = ()
    accepted: tuple = ()
    localization: object = None
    initial_audit: object = None


@contextmanager
def deadline(seconds):
    """Bound audits in campaign worker main threads; restore an outer timer."""
    if current_thread() is not main_thread():
        yield
        return
    def expired(signum, frame):
        raise TimeoutError('Independent numerical audit exceeded its wall budget')
    handler = signal.signal(signal.SIGALRM, expired)
    previous = signal.setitimer(signal.ITIMER_REAL, seconds)
    started = perf_counter()
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
        if previous[0]:
            signal.setitimer(signal.ITIMER_REAL, max(1e-6, previous[0]-(perf_counter()-started)), previous[1])


@geometry_validated
def audit(curve, stage, config, problem, physics, update, seconds):
    """SC-042 numerical gates, recomputed via the selected backend on all real data."""
    count = len(problem.real)
    stage = replace(stage, observations=problem.real, weights=tuple(np.ones(count)/count),
                    curve_modes=curve.band,
                    discrepancy_tolerances=tuple(1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in problem.real))
    reference_nodes = (physics.audit_reference_resolution(stage)
                       if hasattr(physics, 'audit_reference_resolution') else None)
    independent_reference = reference_nodes is not None
    ledger = Ledger(cap=(8 if independent_reference else 6)*count+16, seconds=seconds, endpoint_reserve=0)
    started = perf_counter()
    try:
        with deadline(seconds):
            # Each frequency is independent. Keep only one coarse/fine pair of
            # dense systems long enough to extract the reciprocal derivatives.
            # Normalization/stacking below is exactly Objective's common map.
            from bem_inverse.continuation.lm_backend import normalize
            observed = np.column_stack([o.scattered.reshape(-1) for o in problem.real])
            space = update.prepare(curve, stage.update_modes, curve.band)
            low_columns, high_columns, coarse_jac, fine_jac = [], [], [], []
            reference_columns, reference_jac = [], []
            def evaluate(shape, observation, nodes, category):
                ledger.reserve(1)
                ledger.charge('solve', category)
                try:
                    return physics.evaluate(shape, observation, problem.contrast, nodes)
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    ledger.fail(category)
                    raise
            for observation in problem.real:
                low = evaluate(curve, observation, stage.nodes, 'audit_base')
                high = evaluate(curve, observation, stage.refined_nodes, 'audit_fine')
                low_columns.append(np.array(low.prediction, copy=True).reshape(-1))
                high_columns.append(np.array(high.prediction, copy=True).reshape(-1))
                for state, destination in ((low, coarse_jac), (high, fine_jac)):
                    ledger.reserve(1)
                    ledger.charge('reciprocal', 'derivative')
                    block = physics.derivative(state, update, space)
                    destination.append(block.reshape(-1, block.shape[-1]))
                if independent_reference:
                    reference = evaluate(curve, observation, reference_nodes, 'audit_reference')
                    reference_columns.append(np.array(reference.prediction, copy=True).reshape(-1))
                    ledger.reserve(1)
                    ledger.charge('reciprocal', 'audit_reference')
                    block = physics.derivative(reference, update, space)
                    reference_jac.append(block.reshape(-1, block.shape[-1]))
                    del reference
                del state, low, high
            low_prediction, high_prediction = np.column_stack(low_columns), np.column_stack(high_columns)
            ja = normalize(np.stack(coarse_jac, axis=1), observed, stage.weights, config.residual_floor)
            jb = normalize(np.stack(fine_jac, axis=1), observed, stage.weights, config.residual_floor)
            fields = np.linalg.norm(low_prediction-high_prediction, axis=0)/np.linalg.norm(high_prediction, axis=0)
            colnorm = np.linalg.norm(jb, axis=0)
            derivative = np.linalg.norm(ja-jb, axis=0)/np.maximum(colnorm, 1e-30)
            direction = np.random.default_rng(42001).normal(size=ja.shape[1])
            direction /= np.linalg.norm(direction)
            residuals = []
            for sign in (1, -1):
                candidate = update.trial(space, sign*1e-7*direction)[0]
                predictions = []
                for observation in problem.real:
                    state = evaluate(candidate, observation, stage.refined_nodes, 'audit_fd')
                    predictions.append(np.array(state.prediction, copy=True).reshape(-1))
                    del state
                residuals.append(normalize(np.column_stack(predictions)-observed, observed,
                                           stage.weights, config.residual_floor))
            fd = (residuals[0]-residuals[1])/2e-7
            error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
            residual = normalize(high_prediction-observed, observed, stage.weights, config.residual_floor)
            row = dict(passed=bool(np.all(fields <= stage.discrepancy_tolerances) and
                max(derivative) <= 1e-3 and error <= 1e-3), field_relative=fields,
                jacobian_relative=derivative, jacobian_column_norm=colnorm, full_trial_fd_relative=error,
                fine_loss=.5*float(residual@residual),
                relative_residual=np.linalg.norm(high_prediction-observed, axis=0)/np.linalg.norm(observed, axis=0))
            if independent_reference:
                reference_prediction = np.column_stack(reference_columns)
                jr = normalize(np.stack(reference_jac, axis=1), observed, stage.weights, config.residual_floor)
                reference_fields = (np.linalg.norm(reference_prediction-high_prediction, axis=0)
                                    /np.linalg.norm(high_prediction, axis=0))
                reference_derivative = np.linalg.norm(jr-jb, axis=0)/np.maximum(colnorm, 1e-30)
                row.update(reference_nodes=reference_nodes, reference_refined_nodes=stage.refined_nodes,
                           reference_field_relative=reference_fields, reference_jacobian_relative=reference_derivative)
                row['passed'] = bool(row['passed'] and np.all(reference_fields <= stage.discrepancy_tolerances)
                                     and np.all(reference_derivative <= 1e-3))
            if all(o.scattered.ndim == 2 for o in problem.real):
                paired_prediction = np.column_stack([np.diag(high_prediction[:,i].reshape(o.scattered.shape))
                                                     for i,o in enumerate(problem.real)])
                paired_observed = np.column_stack([np.diag(o.scattered) for o in problem.real])
                row['paired_relative_residual'] = (np.linalg.norm(paired_prediction-paired_observed,axis=0)
                                                  /np.linalg.norm(paired_observed,axis=0))
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    return dict(row, work=ledger.snapshot(), seconds=perf_counter()-started, solver=physics.name,
                update_modes=stage.update_modes, storage_band=curve.band,
                production_resolution=stage.nodes, refined_resolution=stage.refined_nodes)


def fit(problem, *, solver='nodal_kress', execution=None, policy=None, output=None, physics=None,
        on_event=None, geometry_adapter=None, localization_adapter=None, audit_adapter=None, geometry_update=None,
        resume=None, resolution_response=None):
    """Run from the prescribed start. This function cannot read truth or scene IDs.

    ``physics`` is dependency injection for qualified registered services/tests;
    ordinary callers choose only ``solver`` plus independent execution settings.
    Optional geometry/localization adapters extend the input representation while
    retaining this interpreter, policy operations, optimizer and audit. They must
    declare their adaptations in the returned settings/receipt.
    ``geometry_update`` explicitly selects a maintained update without a global
    substitution; it cannot be combined with a representation adapter.
    """
    physics = physics or make_backend(solver, execution)
    if geometry_adapter is not None and geometry_update is not None:
        raise ValueError('Choose geometry_update or geometry_adapter, not both.')
    policy = policy or CumulativePolicy()
    resize_curve = resize if geometry_adapter is None else geometry_adapter.resize
    cleanup_curve = cleanup if geometry_adapter is None else geometry_adapter.cleanup
    record_curve = curve_record if geometry_adapter is None else geometry_adapter.record
    create_update = ProjectedUpdate if geometry_adapter is None else geometry_adapter.update
    initialize = localize if localization_adapter is None else localization_adapter
    selected_audit = audit if audit_adapter is None else audit_adapter
    audit_spent, early_audits = 0., []
    early_endpoint = None
    early_retry_residual = None
    early_retry_resolution = None
    def numerical_audit(curve, stage, config, problem, physics, update, seconds, *, phase='terminal'):
        nonlocal audit_spent
        aggregate = getattr(policy, 'audit_aggregate_seconds', None)
        if aggregate is not None:
            remaining = max(0., aggregate-audit_spent)
            seconds = min(seconds, max(0., remaining-(10. if phase != 'terminal' else 0.)))
        if seconds <= 0:
            return dict(passed=False, seconds=0., work=dict(work_units=0), reason='audit allowance exhausted')
        if hasattr(physics, 'audit_stage'):
            stage = physics.audit_stage(stage)
        row = selected_audit(curve, stage, config, problem, physics, update, seconds)
        audit_spent += row['seconds']
        return row
    physics.validate(problem)
    operations = list(policy.operations(problem, physics))
    plan = policy.plan(problem, physics)
    first = next(op for op in operations if op.kind == 'fit')
    curve = resize_curve(problem.initial, first.stage.curve_modes)
    last_stage, last_config = first.stage, first.optimizer
    update = (create_update(problem.length_unit_m) if geometry_adapter is not None else
              make_update(geometry_update, problem.length_unit_m, physics.execution, default=create_update))
    update_settings = update.settings()
    record_settings = update_settings if geometry_update is not None else {}
    plan = describe_plan(plan, update_settings, override_operations=geometry_update is not None)
    stages, decisions, accepted = [], [], []
    outcome, detail = 'COMPLETED_SCHEDULE', None
    initial_audit, final_audit, localization = {}, {}, {}
    original_audit = {}
    ledger = None
    fit_seconds = 0.
    started = perf_counter()
    historical_seconds = 0.
    original_resolution = (first.stage.nodes, first.stage.refined_nodes) if resolution_response is not None else None
    resumed_stage = None
    promoted = False
    if resume is not None:
        if not resume.operations or resume.operations[0].label != resume.stage.stage.label:
            raise ValueError('Resume queue must begin with the checkpoint stage')
        if resume.stage.work['cap'] != policy.fit_units:
            raise ValueError('Resume cannot change the global work cap')
        if geometry_adapter is not None:
            raise ValueError('Resume is not qualified with a geometry representation adapter')
        curve = resume.stage.current.curve
        last_stage, last_config = resume.operations[0].stage, resume.operations[0].optimizer
        original_resolution = (last_stage.nodes, last_stage.refined_nodes)
        stages, decisions, accepted = list(resume.stages), list(resume.decisions), list(resume.accepted)
        localization, initial_audit = resume.localization or {}, resume.initial_audit or {}
        historical_seconds = resume.stage.work['seconds']
        resumed_stage = resume.stage

    def save(name, value):
        if output is not None:
            from pathlib import Path
            write(Path(output)/name, value)

    def event(op, reason, **values):
        decisions.append(dict(index=len(decisions), operation=operation_record(op, record_settings), reason=reason, **values))
        save('decisions.json', dict(policy=policy.name, version=policy.version, decisions=decisions))
        if on_event is not None:
            on_event(decisions[-1])

    save('plan.json', plan)
    if output is not None:
        from pathlib import Path
        (Path(output)/'plan.md').write_text(readable_plan(plan))
    save('configuration.json', dict(initial=record_curve(curve), contrast=problem.contrast,
         solver=physics.name, execution=physics.receipt()['execution'], update=update.settings(), plan=plan))
    with geometry_runtime(physics.execution.geometry):
        try:
            if resume is None:
                initial_audit = numerical_audit(curve, first.stage, first.optimizer, problem, physics, update, policy.audit_seconds, phase='initial')
                save('initial_audit.json', initial_audit)
                event(operations[0], 'original start '+('qualified' if initial_audit['passed'] else 'refused'),
                      passed=initial_audit['passed'])
                if not initial_audit['passed']:
                    raise ValueError('Original-start numerical audit failed')
                ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds,
                                strict_dispatch=(resolution_response is not None or
                                    getattr(physics.execution, 'nodal_resolution_profile', 'fixed') == 'band_matched'))
                queue = list(operations[1:-1])
            else:
                ledger = Ledger.restore(resume.stage.work, seconds=policy.fit_seconds,
                                        strict_dispatch=(resolution_response is not None or
                                    getattr(physics.execution, 'nodal_resolution_profile', 'fixed') == 'band_matched'))
                queue = list(resume.operations)
                save('resume.json', dict(work=resume.stage.work, iteration=resume.stage.iteration,
                    next_damping=resume.stage.damping, curve=record_curve(curve),
                    remaining_operations=[operation_record(op, record_settings) for op in queue]))
            fit_started = perf_counter()-historical_seconds
            while queue:
                op = queue.pop(0)
                if op.kind == 'localize':
                    ledger.begin_stage(op.label, None)
                    curve, localization = initialize(problem, physics, policy.localization, ledger,
                        lambda rows: save('localization_progress.json', dict(candidates=rows)))
                    save('localization.json', localization)
                    event(op, localization.get('reason', 'first refined candidate passing selected-backend qualification'),
                          initialization=localization)
                elif op.kind == 'cleanup':
                    ledger.reserve(0)
                    curve = cleanup_curve(curve, op.details['retained_band'], op.details['storage_band'])
                    event(op, 'policy cleanup entered', curve=record_curve(curve))
                elif op.kind == 'fit':
                    if promoted:
                        op = replace(op, stage=replace(op.stage, nodes=resolution_response.production_nodes,
                                                       refined_nodes=resolution_response.refined_nodes))
                    last_stage, last_config = op.stage, op.optimizer
                    curve = resize_curve(curve, op.stage.curve_modes)
                    if resumed_stage is None:
                        ledger.begin_stage(op.label, op.stage.quota)
                    selection = None
                    if resumed_stage is None and hasattr(physics, 'select_stage'):
                        selected, selection = physics.select_stage(curve, op.stage, op.optimizer,
                                                                   problem.contrast, update, ledger)
                        op = replace(op, stage=selected)
                        last_stage = selected
                        if selection is not None:
                            save(op.label+'_resolution.json', selection)
                    event(op, 'resolved stage entered', work=ledger.snapshot(), resolution_selection=selection)
                    def checkpoint(iteration, evaluation):
                        nonlocal early_endpoint, early_retry_residual, early_retry_resolution, fit_started
                        observed = np.column_stack([o.scattered.reshape(-1) for o in op.stage.observations])
                        maximum_stage_residual = float(max(np.linalg.norm(evaluation.prediction-observed, axis=0)
                                                          /np.linalg.norm(observed, axis=0)))
                        accepted.append(dict(maximum_stage_residual=maximum_stage_residual,
                            active_frequency_count=len(op.stage.observations), stage=op.label, iteration=iteration, M=op.stage.update_modes,
                            loss=evaluation.loss, units=ledger.units, curve=record_curve(evaluation.curve)))
                        save('accepted.json', dict(states=accepted))
                        threshold = getattr(policy, 'required_accuracy', None)
                        full_real = (len(op.stage.observations) == len(problem.real) and
                                     all(a is b for a, b in zip(op.stage.observations, problem.real)))
                        if threshold is None or not full_real:
                            return
                        residuals = np.linalg.norm(evaluation.prediction-np.column_stack(
                            [o.scattered.reshape(-1) for o in problem.real]), axis=0)/np.linalg.norm(
                            np.column_stack([o.scattered.reshape(-1) for o in problem.real]), axis=0)
                        maximum = float(max(residuals))
                        resolution = (op.stage.nodes, op.stage.refined_nodes, evaluation.curve.band)
                        if maximum > threshold or (early_retry_residual is not None and
                                (maximum > early_retry_residual/2 or maximum == early_retry_residual) and resolution == early_retry_resolution):
                            return
                        aggregate = getattr(policy, 'audit_aggregate_seconds', None)
                        if aggregate is not None and aggregate-audit_spent <= 10.:
                            return
                        before = perf_counter()
                        checked = numerical_audit(evaluation.curve, op.stage, op.optimizer, problem,
                                                  physics, update, policy.audit_seconds, phase='early')
                        elapsed = perf_counter()-before
                        # Optional audit has its own aggregate budget, not the fit wall allowance.
                        ledger.started += elapsed
                        fit_started += elapsed
                        early_audits.append(dict(checked, stage=op.label, iteration=iteration,
                                                maximum_residual=maximum))
                        save('early_audits.json', dict(audits=early_audits))
                        early_retry_residual, early_retry_resolution = maximum, resolution
                        if checked['passed']:
                            early_endpoint = (evaluation.curve.coefficients.tobytes(), checked)
                            raise RequiredAccuracyReached('full real catalog meets required accuracy; audit passed')
                    objective_options = {}
                    anchors = getattr(policy, 'working_anchors', 0)
                    full_real = (len(op.stage.observations) == len(problem.real) and
                                 all(a is b for a, b in zip(op.stage.observations, problem.real)))
                    if anchors and full_real and len(problem.real) == 19:
                        from functools import partial
                        from .working_frequency import WorkingObjective
                        objective_options['objective_factory'] = partial(WorkingObjective, anchor_count=anchors)
                    if getattr(op.stage, 'relaxed_tau', None) is not None:
                        from .full_matrix import RelaxedObjective
                        objective_options['objective_factory'] = RelaxedObjective
                    result = fit_stage(curve, op.stage, problem.contrast, update, op.optimizer, ledger,
                                       on_accept=checkpoint, physics=physics, resume=resumed_stage,
                                       resolution_response=resolution_response, **objective_options)
                    resumed_stage = None
                    curve = result.curve
                    row = dict(stage=op.label, M=op.stage.update_modes, K_geometry=op.stage.curve_modes,
                        outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                        accepted_steps=result.accepted_steps, initial_loss=result.initial_loss,
                        final_loss=result.final_loss, seconds=result.seconds, work=ledger.snapshot(),
                        curve=record_curve(curve), nodes=op.stage.nodes, refined_nodes=op.stage.refined_nodes,
                        resolution_selection=selection)
                    if resolution_response is not None:
                        row.update(nodes=result.final_nodes, refined_nodes=result.final_refined_nodes,
                                   resolution_events=result.resolution_events)
                        if result.final_nodes == resolution_response.production_nodes:
                            promoted = True
                            physics = resolution_response.physics or physics
                            last_stage = replace(last_stage, nodes=result.final_nodes,
                                                 refined_nodes=result.final_refined_nodes)
                    stages.append(row)
                    save(op.label+'.json', dict(row, history=result.history, trials=result.trials,
                                               acceptance_checks=result.acceptance_checks))
                    save('checkpoint.json', dict(stages=stages, curve=record_curve(curve), work=ledger.snapshot()))
                    event(op, 'stage returned', outcome=result.outcome, stop=result.stop_reason,
                          final_loss=result.final_loss)
                    if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                        outcome, detail = result.outcome, result.detail
                        event(op, 'hard or numerical stop; remaining stages skipped; final audit next')
                        break
                    if policy.at_noise_discrepancy(op, result.final_loss, problem):
                        outcome = 'NOISE_DISCREPANCY_REACHED'
                        event(op, 'full real catalog reached declared-noise discrepancy; skip remaining releases/tail',
                              loss=result.final_loss, threshold=op.details['noise_threshold'])
                        break
                elif op.kind == 'frontier':
                    ledger.begin_stage(op.label, None)
                    ledger.reserve(2)
                    # Frontier is a complete solve+derivative diagnostic; never free work.
                    ledger.charge('solve', 'frontier')
                    ledger.charge('reciprocal', 'frontier')
                    measured = physics.observable_frontier(curve, problem.real[-1], problem.contrast,
                        policy.frontier_top, policy.frontier_threshold)
                    tail = policy.tail(problem, physics, measured['frontier'])
                    event(op, 'frontier measured; releases resolved' if tail else 'frontier at or below completed band',
                          measured=measured, resolved_operations=[operation_record(item, record_settings) for item in tail])
                    queue[:0] = tail
                else:
                    raise ValueError('Unknown policy operation: '+op.kind)
            fit_seconds = perf_counter()-fit_started
        except Stop as exc:
            outcome, detail = exc.code, str(exc)
            if hasattr(exc, 'resolution_selection'):
                save('resolution_selection_failure.json', exc.resolution_selection)
        except Exception:
            outcome, detail = 'EXCEPTION', traceback.format_exc()
        finally:
            if ledger is not None and not fit_seconds:
                fit_seconds = perf_counter()-ledger.started
            # Preserve endpoint before audits or external scoring can fail.
            save('unscored.json', dict(outcome=outcome, detail=detail, final_curve=record_curve(curve),
                 stages=stages, fit_work=None if ledger is None else ledger.snapshot()))
            event(operations[-1], 'fit returned; audit endpoint', outcome=outcome)
            if ledger is None and initial_audit and not initial_audit['passed']:
                # No localization or fitting occurred: this is the identical
                # already-audited endpoint. Do not repeat a failed dense audit.
                final_audit = dict(initial_audit, reused_identical_initial_audit=True,
                    original_audit_work=initial_audit.get('work'), seconds=0.,
                    work=dict(work_units=0, solves={}, reciprocal_batches={}, failed={}))
            elif early_endpoint is not None and curve.coefficients.tobytes() == early_endpoint[0]:
                final_audit = dict(early_endpoint[1], reused_identical_early_audit=True, seconds=0.,
                                   work=dict(work_units=0))
            else:
                final_audit = numerical_audit(curve, last_stage, last_config, problem, physics, update, policy.audit_seconds)
                if promoted and original_resolution is not None:
                    original_stage = replace(last_stage, nodes=original_resolution[0],
                                             refined_nodes=original_resolution[1])
                    original_audit = numerical_audit(curve, original_stage, last_config, problem, physics,
                                                     update, policy.audit_seconds)
                    save('original_resolution_audit.json', original_audit)
                    final_audit = dict(final_audit, resolution_changed=True,
                        original_resolution=list(original_resolution), original_resolution_passed=original_audit['passed'])
            if hasattr(physics, 'close'):
                physics.close()
            save('final_audit.json', final_audit)
            event(operations[-1], 'endpoint '+('qualified' if final_audit['passed'] else 'refused'),
                  passed=final_audit['passed'])
    row = dict(policy=policy.name, policy_version=policy.version, outcome=outcome, detail=detail,
        final_curve=record_curve(curve), stages=stages, decisions=decisions, localization=localization,
        fit_work=None if ledger is None else ledger.snapshot(), fit_and_localization_seconds=fit_seconds,
        fit_and_localization_units=0 if ledger is None else ledger.units,
        initial_audit_passed=initial_audit.get('passed', False), final_audit_passed=final_audit['passed'],
        relative_residual=final_audit.get('relative_residual'),
        audit_units=sum(a.get('work', {}).get('work_units', 0) for a in (initial_audit, final_audit, original_audit, *early_audits)),
        total_seconds=perf_counter()-started, audit_seconds=audit_spent, early_audits=early_audits,
        physics=physics.receipt(), geometry_work=update.counts,
        geometry_update=geometry_update, geometry_settings=update_settings)
    row['total_units'] = row['fit_and_localization_units']+row['audit_units']
    if resume is not None:
        row.update(resumed=True, historical_seconds=historical_seconds,
                   fresh_fit_seconds=max(0., fit_seconds-historical_seconds),
                   historical_units=resume.stage.work['work_units'],
                   fresh_fit_units=row['fit_and_localization_units']-resume.stage.work['work_units'],
                   resolution_promoted=promoted)
    if 'paired_relative_residual' in final_audit:
        row['paired_relative_residual'] = final_audit['paired_relative_residual']
    save('fit_result.json', row)
    return row
