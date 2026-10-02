"""Truth-free policy interpreter. Every physics operation uses the chosen service."""
from contextlib import contextmanager
from dataclasses import replace
import signal
from threading import current_thread, main_thread
from time import perf_counter
import traceback
import numpy as np

from experiments.shape_continuation.geometry_runtime import geometry_runtime, geometry_validated
from experiments.shape_continuation.lm_backend import (
    Ledger, Objective, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA)
from .geometry import ProjectedUpdate, resize, cleanup
from .io import write, curve_record
from .localization import localize
from .physics import make_backend
from .policy import CumulativePolicy, readable_plan


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
    ledger = Ledger(cap=6*count+16, seconds=seconds, endpoint_reserve=0)
    started = perf_counter()
    try:
        with deadline(seconds):
            coarse = Objective(stage, problem.contrast, config, ledger, physics=physics)
            fine = Objective(replace(stage, nodes=stage.refined_nodes,
                                     refined_nodes=physics.refine_resolution(stage.refined_nodes)),
                             problem.contrast, config, ledger, physics=physics)
            low, high = coarse.production(curve, 'audit_base'), fine.production(curve, 'audit_fine')
            if low is None or high is None:
                raise ValueError('Endpoint forward evaluation failed')
            space = update.prepare(curve, stage.update_modes, curve.band)
            ja, jb = coarse.jacobian(low, update, space), fine.jacobian(high, update, space)
            fields = np.linalg.norm(low.prediction-high.prediction, axis=0)/np.linalg.norm(high.prediction, axis=0)
            colnorm = np.linalg.norm(jb, axis=0)
            derivative = np.linalg.norm(ja-jb, axis=0)/np.maximum(colnorm, 1e-30)
            direction = np.random.default_rng(42001).normal(size=ja.shape[1])
            direction /= np.linalg.norm(direction)
            plus, minus = [fine.production(update.trial(space, sign*1e-7*direction)[0], 'audit_fd')
                           for sign in (1, -1)]
            if plus is None or minus is None:
                raise ValueError('Complete-trial finite difference refused')
            fd = (plus.residual-minus.residual)/2e-7
            error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
            row = dict(passed=bool(np.all(fields <= stage.discrepancy_tolerances) and
                max(derivative) <= 1e-3 and error <= 1e-3), field_relative=fields,
                jacobian_relative=derivative, jacobian_column_norm=colnorm, full_trial_fd_relative=error,
                fine_loss=high.loss, relative_residual=np.linalg.norm(high.prediction-fine.observed, axis=0)/
                                                      np.linalg.norm(fine.observed, axis=0))
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    return dict(row, work=ledger.snapshot(), seconds=perf_counter()-started, solver=physics.name,
                update_modes=stage.update_modes, storage_band=curve.band,
                production_resolution=stage.nodes, refined_resolution=stage.refined_nodes)


def fit(problem, *, solver='nodal_kress', execution=None, policy=None, output=None, physics=None,
        on_event=None, geometry_adapter=None, localization_adapter=None, audit_adapter=None):
    """Run from the prescribed start. This function cannot read truth or scene IDs.

    ``physics`` is dependency injection for qualified registered services/tests;
    ordinary callers choose only ``solver`` plus independent execution settings.
    Optional geometry/localization adapters extend the input representation while
    retaining this interpreter, policy operations, optimizer and audit. They must
    declare their adaptations in the returned settings/receipt.
    """
    physics = physics or make_backend(solver, execution)
    policy = policy or CumulativePolicy()
    resize_curve = resize if geometry_adapter is None else geometry_adapter.resize
    cleanup_curve = cleanup if geometry_adapter is None else geometry_adapter.cleanup
    record_curve = curve_record if geometry_adapter is None else geometry_adapter.record
    create_update = ProjectedUpdate if geometry_adapter is None else geometry_adapter.update
    initialize = localize if localization_adapter is None else localization_adapter
    numerical_audit = audit if audit_adapter is None else audit_adapter
    physics.validate(problem)
    operations = list(policy.operations(problem, physics))
    plan = policy.plan(problem, physics)
    first = next(op for op in operations if op.kind == 'fit')
    curve = resize_curve(problem.initial, first.stage.curve_modes)
    last_stage, last_config = first.stage, first.optimizer
    update = create_update(problem.length_unit_m)
    stages, decisions, accepted = [], [], []
    outcome, detail = 'COMPLETED_SCHEDULE', None
    initial_audit, final_audit, localization = {}, {}, {}
    ledger = None
    fit_seconds = 0.
    started = perf_counter()

    def save(name, value):
        if output is not None:
            from pathlib import Path
            write(Path(output)/name, value)

    def event(op, reason, **values):
        decisions.append(dict(index=len(decisions), operation=op.record(), reason=reason, **values))
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
            initial_audit = numerical_audit(curve, first.stage, first.optimizer, problem, physics, update, policy.audit_seconds)
            save('initial_audit.json', initial_audit)
            event(operations[0], 'original start '+('qualified' if initial_audit['passed'] else 'refused'),
                  passed=initial_audit['passed'])
            if not initial_audit['passed']:
                raise ValueError('Original-start numerical audit failed')
            ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds)
            fit_started = perf_counter()
            queue = list(operations[1:-1])
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
                    last_stage, last_config = op.stage, op.optimizer
                    curve = resize_curve(curve, op.stage.curve_modes)
                    ledger.begin_stage(op.label, op.stage.quota)
                    event(op, 'resolved stage entered', work=ledger.snapshot())
                    def checkpoint(iteration, evaluation):
                        accepted.append(dict(stage=op.label, iteration=iteration, M=op.stage.update_modes,
                            loss=evaluation.loss, units=ledger.units, curve=record_curve(evaluation.curve)))
                        save('accepted.json', dict(states=accepted))
                    result = fit_stage(curve, op.stage, problem.contrast, update, op.optimizer, ledger,
                                       on_accept=checkpoint, physics=physics)
                    curve = result.curve
                    row = dict(stage=op.label, M=op.stage.update_modes, K_geometry=op.stage.curve_modes,
                        outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                        accepted_steps=result.accepted_steps, initial_loss=result.initial_loss,
                        final_loss=result.final_loss, seconds=result.seconds, work=ledger.snapshot(),
                        curve=record_curve(curve))
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
                          measured=measured, resolved_operations=[item.record() for item in tail])
                    queue[:0] = tail
                else:
                    raise ValueError('Unknown policy operation: '+op.kind)
            fit_seconds = perf_counter()-fit_started
        except Stop as exc:
            outcome, detail = exc.code, str(exc)
        except Exception:
            outcome, detail = 'EXCEPTION', traceback.format_exc()
        finally:
            if ledger is not None and not fit_seconds:
                fit_seconds = perf_counter()-ledger.started
            # Preserve endpoint before audits or external scoring can fail.
            save('unscored.json', dict(outcome=outcome, detail=detail, final_curve=record_curve(curve),
                 stages=stages, fit_work=None if ledger is None else ledger.snapshot()))
            event(operations[-1], 'fit returned; audit endpoint', outcome=outcome)
            final_audit = numerical_audit(curve, last_stage, last_config, problem, physics, update, policy.audit_seconds)
            save('final_audit.json', final_audit)
            event(operations[-1], 'endpoint '+('qualified' if final_audit['passed'] else 'refused'),
                  passed=final_audit['passed'])
    row = dict(policy=policy.name, policy_version=policy.version, outcome=outcome, detail=detail,
        final_curve=record_curve(curve), stages=stages, decisions=decisions, localization=localization,
        fit_work=None if ledger is None else ledger.snapshot(), fit_and_localization_seconds=fit_seconds,
        fit_and_localization_units=0 if ledger is None else ledger.units,
        initial_audit_passed=initial_audit.get('passed', False), final_audit_passed=final_audit['passed'],
        relative_residual=final_audit.get('relative_residual'),
        audit_units=sum(a.get('work', {}).get('work_units', 0) for a in (initial_audit, final_audit)),
        total_seconds=perf_counter()-started, physics=physics.receipt(), geometry_work=update.counts)
    row['total_units'] = row['fit_and_localization_units']+row['audit_units']
    save('fit_result.json', row)
    return row
