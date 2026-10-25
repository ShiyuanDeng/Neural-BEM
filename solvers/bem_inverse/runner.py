"""Truth-free policy interpreter. Every physics operation uses the chosen service.

``fit`` runs the policy's operations and returns the unscored endpoint and its
final stage. An independent endpoint audit belongs to the caller and runs after
``fit`` returns.
"""
from dataclasses import dataclass
from time import perf_counter
import traceback
import numpy as np

from bem_inverse.continuation.geometry_runtime import geometry_runtime
from .fit_stage import fit_stage
from .work import Ledger
from .errors import Stop, NORMAL_RETURN, STAGE_QUOTA
from .continuation.geometry import resize, cleanup
from .geometry_update_methods.spline import ProjectedUpdate
from .geometry_selection import make_update, describe_plan, operation_record
from .io import write, curve_record
from .localization import localize
from .physics import make_backend
from .policy import CumulativePolicy, readable_plan


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


def fit(problem, *, solver='nodal_kress', execution=None, policy=None, output=None, physics=None,
        on_event=None, geometry_adapter=None, localization_adapter=None, geometry_update=None, resume=None):
    """Run from the prescribed start. This function cannot read truth or scene IDs.

    ``physics`` is dependency injection for qualified registered services/tests;
    ordinary callers choose only ``solver`` plus independent execution settings.
    Optional geometry/localization adapters extend the input representation while
    retaining this interpreter, policy operations and optimizer. They must
    declare their adaptations in the returned settings/receipt.
    ``geometry_update`` explicitly selects a maintained update without a global
    substitution; it cannot be combined with a representation adapter.
    The result's ``final_stage`` names the last fitted stage's M, storage band and
    any stage-local geometry update, which an endpoint audit needs.
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
    physics.validate(problem)
    operations = list(policy.operations(problem, physics))
    plan = policy.plan(problem, physics)
    first = next(op for op in operations if op.kind == 'fit')
    curve = resize_curve(problem.initial, first.stage.curve_modes)
    last = first
    selected_update = (create_update(problem.length_unit_m) if geometry_adapter is not None else
                       make_update(geometry_update, problem.length_unit_m, physics.execution, default=create_update))
    update_settings = selected_update.settings()
    stage_updates = {}
    record_settings = update_settings if geometry_update is not None else {}
    plan = describe_plan(plan, update_settings, override_operations=geometry_update is not None)
    stages, decisions, accepted = [], [], []
    outcome, detail = 'COMPLETED_SCHEDULE', None
    localization = {}
    ledger = None
    fit_seconds = 0.
    started = perf_counter()
    historical_seconds = 0.
    resumed_stage = None
    # Exact stage-entry reuse: the previous endpoint replaces the next stage's initial
    # solves when curve, catalog and resolution are unchanged (charges are replayed).
    reuse_entries = bool(getattr(physics.execution, 'stage_entry_reuse', False) and geometry_adapter is None)
    carried = None
    if resume is not None:
        if not resume.operations or resume.operations[0].label != resume.stage.stage.label:
            raise ValueError('Resume queue must begin with the checkpoint stage')
        if resume.stage.work['cap'] != policy.fit_units:
            raise ValueError('Resume cannot change the global work cap')
        if geometry_adapter is not None:
            raise ValueError('Resume is not qualified with a geometry representation adapter')
        curve = resume.stage.current.curve
        last = resume.operations[0]
        stages, decisions, accepted = list(resume.stages), list(resume.decisions), list(resume.accepted)
        localization = resume.localization or {}
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
         solver=physics.name, execution=physics.receipt()['execution'], update=update_settings, plan=plan))
    with geometry_runtime(physics.execution.geometry):
        try:
            strict = getattr(physics.execution, 'nodal_resolution_profile', 'fixed') == 'band_matched'
            if resume is None:
                ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds, strict_dispatch=strict)
                queue = list(operations)
            else:
                ledger = Ledger.restore(resume.stage.work, seconds=policy.fit_seconds, strict_dispatch=strict)
                queue = list(resume.operations)
                save('resume.json', dict(work=resume.stage.work, iteration=resume.stage.iteration,
                    next_damping=resume.stage.damping, curve=record_curve(curve),
                    remaining_operations=[operation_record(op, record_settings) for op in queue]))
            fit_started = perf_counter()-historical_seconds
            # C12. Policy operations may insert stages; retain the live queue.
            while queue:
                op = queue.pop(0)
                # Optional initialization, then explicit cleanup and stage entry.
                if op.kind == 'localize':
                    ledger.begin_stage(op.label, None)
                    carried = None
                    curve, localization = initialize(problem, physics, policy.localization, ledger,
                        lambda rows: save('localization_progress.json', dict(candidates=rows)))
                    save('localization.json', localization)
                    event(op, localization.get('reason', 'refined best grid circle'), initialization=localization)
                elif op.kind == 'cleanup':
                    ledger.reserve(0)
                    carried = None
                    curve = cleanup_curve(curve, op.details['retained_band'], op.details['storage_band'])
                    event(op, 'policy cleanup entered', curve=record_curve(curve))
                elif op.kind == 'fit':
                    if op.fit_geometry_update is not None:
                        if geometry_adapter is not None:
                            raise ValueError('Stage-local updates cannot use a representation adapter')
                        if op.fit_geometry_update not in stage_updates:
                            stage_updates[op.fit_geometry_update] = make_update(
                                op.fit_geometry_update, problem.length_unit_m, physics.execution)
                        update = stage_updates[op.fit_geometry_update]
                    else:
                        update = selected_update
                    last = op
                    curve = resize_curve(curve, op.stage.curve_modes)
                    if resumed_stage is None:
                        ledger.begin_stage(op.label, op.stage.quota)
                    event(op, 'resolved stage entered', work=ledger.snapshot())
                    if op.fit_geometry_update is not None:
                        save(op.label+'_geometry.json', update.settings())
                    def accepted_state(iteration, evaluation):
                        nonlocal curve
                        curve=evaluation.curve
                        observed = np.column_stack([o.scattered.reshape(-1) for o in op.stage.observations])
                        maximum_stage_residual = float(max(np.linalg.norm(evaluation.prediction-observed, axis=0)
                                                          /np.linalg.norm(observed, axis=0)))
                        accepted.append(dict(maximum_stage_residual=maximum_stage_residual,
                            active_frequency_count=len(op.stage.observations), stage=op.label, iteration=iteration, M=op.stage.update_modes,
                            loss=evaluation.loss, units=ledger.units, curve=record_curve(evaluation.curve)))
                        save('accepted.json', dict(states=accepted))
                    entry, carried = carried, None
                    # A–B–C. Run one resolved stage and retain its accepted endpoint.
                    result = fit_stage(curve, op.stage, problem.contrast, update, op.optimizer, ledger,
                                       on_accept=accepted_state, physics=physics, resume=resumed_stage,
                                       entry=entry, retain_final=reuse_entries)
                    resumed_stage = None
                    curve = result.curve
                    carried = result.final_entry if reuse_entries else None
                    row = dict(stage=op.label, M=op.stage.update_modes, K_geometry=op.stage.curve_modes,
                        outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                        accepted_steps=result.accepted_steps, initial_loss=result.initial_loss,
                        final_loss=result.final_loss, seconds=result.seconds, work=ledger.snapshot(),
                        curve=record_curve(curve), nodes=op.stage.nodes)
                    if reuse_entries:
                        row['entry_reused'] = result.entry_reused
                    row.update(physics_failures=getattr(result, 'physics_failures', []),
                               geometry_proposals=getattr(result, 'geometry_proposals', len(result.trials)))
                    stages.append(row)
                    save(op.label+'.json', dict(row, history=result.history, trials=result.trials))
                    save('checkpoint.json', dict(stages=stages, curve=record_curve(curve), work=ledger.snapshot()))
                    event(op, 'stage returned', outcome=result.outcome, stop=result.stop_reason,
                          final_loss=result.final_loss)
                    # C12. Only normal return or a stage quota advances the queue.
                    if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                        outcome, detail = result.outcome, result.detail
                        event(op, 'hard or numerical stop; remaining stages skipped')
                        break
                    if policy.at_noise_discrepancy(op, result.final_loss, problem):
                        outcome = 'NOISE_DISCREPANCY_REACHED'
                        event(op, 'full real catalog reached declared-noise discrepancy; skip remaining releases/tail',
                              loss=result.final_loss, threshold=op.details['noise_threshold'])
                        break
                elif op.kind == 'skip':
                    event(op,'SKIPPED_IDENTICAL',work=ledger.snapshot())
                # C12. The measured frontier determines additional policy stages.
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
        except Exception:
            outcome, detail = 'EXCEPTION', traceback.format_exc()
        finally:
            if ledger is not None and not fit_seconds:
                fit_seconds = perf_counter()-ledger.started
            fitting_snapshot=None if ledger is None else ledger.snapshot()
            if fitting_snapshot is not None:fit_seconds=fitting_snapshot['seconds']
            save('unscored.json', dict(outcome=outcome, detail=detail, final_curve=record_curve(curve),
                 stages=stages, fit_work=fitting_snapshot))
            if hasattr(physics, 'close'):
                physics.close()
    row = dict(policy=policy.name, policy_version=policy.version, outcome=outcome, detail=detail,
        final_curve=record_curve(curve), stages=stages, decisions=decisions, localization=localization,
        final_stage=dict(label=last.label, M=last.stage.update_modes, K_geometry=last.stage.curve_modes,
                         nodes=last.stage.nodes, fit_geometry_update=last.fit_geometry_update),
        fit_work=fitting_snapshot, fit_and_localization_seconds=fit_seconds,
        fit_and_localization_units=0 if ledger is None else ledger.units,
        total_seconds=perf_counter()-started,
        physics=physics.receipt(), geometry_work=dict(selected_update.counts),
        geometry_update=geometry_update, geometry_settings=update_settings)
    if stage_updates:
        row['stage_geometry_updates'] = {name: dict(settings=item.settings(), work=dict(item.counts))
                                        for name, item in stage_updates.items()}
        for item in stage_updates.values():
            for key, value in item.counts.items():
                row['geometry_work'][key] = row['geometry_work'].get(key, 0)+value
    if resume is not None:
        row.update(resumed=True, historical_seconds=historical_seconds,
                   fresh_fit_seconds=max(0., fit_seconds-historical_seconds),
                   historical_units=resume.stage.work['work_units'],
                   fresh_fit_units=row['fit_and_localization_units']-resume.stage.work['work_units'])
    save('fit_result.json', row)
    return row
