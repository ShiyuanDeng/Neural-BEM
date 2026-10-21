"""Truth-free policy interpreter. Every physics operation uses the chosen service."""
from . import checks
from contextlib import contextmanager
from dataclasses import dataclass, replace
import signal
from threading import current_thread, main_thread
from time import perf_counter
import traceback
import numpy as np

from bem_inverse.continuation.geometry_runtime import geometry_runtime, geometry_validated
from .fit_stage import (
    Ledger, Objective, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA)
from .continuation.geometry import resize, cleanup
from .geometry_update_methods.spline import ProjectedUpdate
from .geometry_selection import make_update, describe_plan, operation_record
from .io import write, curve_record
from .localization import localize
from .endpoint import audit, deadline
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
    audit_phase_seconds = dict(initial=0., early=0., terminal=0.)
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
        started_audit = perf_counter()
        previous_role=getattr(physics,'calculation_role','production')
        physics.calculation_role=phase+'_audit'
        try:row = selected_audit(curve, stage, config, problem, physics, update, seconds)
        finally:physics.calculation_role=previous_role
        audit_phase_seconds[phase] += perf_counter()-started_audit
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
    audit_update = update
    stage_updates = {}
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
    # Exact stage-entry reuse: the previous endpoint replaces the next stage's initial
    # solves when curve, catalog and resolution are unchanged (charges are replayed).
    reuse_entries = bool(getattr(physics.execution, 'stage_entry_reuse', False) and geometry_adapter is None)
    carried = None
    adaptive_state = None
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
            io_started=perf_counter()
            write(Path(output)/name, value)
            if ledger is not None and getattr(physics,'qualified_controller',False):
                ledger.started+=perf_counter()-io_started

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
                audit_stage = (replace(first.stage, update_modes=1)
                               if first.fit_geometry_update == 'similarity' else first.stage)
                initial_audit = numerical_audit(curve, audit_stage, first.optimizer, problem, physics, audit_update, policy.audit_seconds, phase='initial')
                save('initial_audit.json', initial_audit)
                event(operations[0], 'original start '+('qualified' if initial_audit['passed'] else 'refused'),
                      passed=initial_audit['passed'])
                if not initial_audit['passed']:
                    raise ValueError('Original-start numerical audit failed')
                ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds,
                                strict_dispatch=(resolution_response is not None or
                                    getattr(physics,'strict_dispatch',False) or
                                    getattr(physics.execution, 'nodal_resolution_profile', 'fixed') == 'band_matched'))
                queue = list(operations[1:-1])
            else:
                ledger = Ledger.restore(resume.stage.work, seconds=policy.fit_seconds,
                                        strict_dispatch=(resolution_response is not None or
                                    getattr(physics,'strict_dispatch',False) or
                                    getattr(physics.execution, 'nodal_resolution_profile', 'fixed') == 'band_matched'))
                queue = list(resume.operations)
                save('resume.json', dict(work=resume.stage.work, iteration=resume.stage.iteration,
                    next_damping=resume.stage.damping, curve=record_curve(curve),
                    remaining_operations=[operation_record(op, record_settings) for op in queue]))
            fit_started = perf_counter()-historical_seconds
            # C12. Policy operations may insert stages; retain the live queue.
            while queue:
                op = queue.pop(0)
                if op.kind in ('adaptive','adaptive_bridge'):
                    op,adaptive_state=policy.resolve_adaptive(op,problem,physics,adaptive_state)
                # Optional initialization, then explicit cleanup and stage entry.
                if op.kind == 'localize':
                    ledger.begin_stage(op.label, None)
                    carried = None
                    curve, localization = initialize(problem, physics, policy.localization, ledger,
                        lambda rows: save('localization_progress.json', dict(candidates=rows)))
                    save('localization.json', localization)
                    event(op, localization.get('reason', 'first refined candidate passing selected-backend qualification'),
                          initialization=localization)
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
                        update = audit_update
                    if resolution_response is not None:
                        # The stage's own (unpromoted) profile; constant for nodal recipes, while a
                        # modal profile follows each stage's storage band.
                        original_resolution = (op.stage.nodes, op.stage.refined_nodes)
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
                    if op.fit_geometry_update is not None:
                        save(op.label+'_geometry.json', update.settings())
                    def checkpoint(iteration, evaluation):
                        nonlocal early_endpoint, early_retry_residual, early_retry_resolution, fit_started, curve
                        curve=evaluation.curve
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
                                                  physics, audit_update, policy.audit_seconds, phase='early')
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
                    entry, carried = carried, None
                    if (op.details or {}).get('adaptive_decision'):
                        from .four_control_adaptive import decision_slot
                        result,op,adaptive_state=decision_slot(problem,curve,op,policy,physics,update,ledger,adaptive_state)
                        last_stage,last_config=op.stage,op.optimizer
                        event(op,'adaptive slot returned at saved endpoint',outcome=result.outcome,
                            stop=result.stop_reason,actual_controls=adaptive_state['controls'])
                        if result.outcome==NORMAL_RETURN and getattr(result,'committed_evaluation',None) is not None:
                            checkpoint(result.accepted_steps,result.committed_evaluation)
                    else:
                        # A–B–C. Run one resolved stage and retain its accepted endpoint.
                        result = fit_stage(curve, op.stage, problem.contrast, update, op.optimizer, ledger,
                                           on_accept=checkpoint, physics=physics, resume=resumed_stage,
                                           resolution_response=resolution_response, entry=entry,
                                           retain_final=reuse_entries, **objective_options)
                    resumed_stage = None
                    curve = result.curve
                    carried = result.final_entry if reuse_entries else None
                    row = dict(stage=op.label, M=op.stage.update_modes, K_geometry=op.stage.curve_modes,
                        outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                        accepted_steps=result.accepted_steps, initial_loss=result.initial_loss,
                        final_loss=result.final_loss, seconds=result.seconds, work=ledger.snapshot(),
                        curve=record_curve(curve), nodes=op.stage.nodes, refined_nodes=op.stage.refined_nodes,
                        resolution_selection=selection)
                    if reuse_entries:
                        row['entry_reused'] = result.entry_reused
                    row.update(physics_failures=getattr(result, 'physics_failures', []),
                               geometry_proposals=getattr(result, 'geometry_proposals', len(result.trials)))
                    overshoots = [check for check in result.acceptance_checks
                                  if check.get('accepted') and check.get('numerical_obstruction')]
                    row.update(resolution_gate=op.optimizer.resolution_gate,
                               accepted_resolution_overshoots=len(overshoots),
                               largest_accepted_resolution_overshoot=max(
                                   (max(check['prediction_discrepancy_ratios']) for check in overshoots), default=0.))
                    if resolution_response is not None:
                        row.update(nodes=result.final_nodes, refined_nodes=result.final_refined_nodes,
                                   resolution_events=result.resolution_events)
                        if result.final_nodes == resolution_response.production_nodes:
                            promoted = True
                            physics = resolution_response.physics or physics
                            last_stage = replace(last_stage, nodes=result.final_nodes,
                                                 refined_nodes=result.final_refined_nodes)
                    elif getattr(physics,'qualified_controller',False):
                        row.update(nodes=result.final_nodes,refined_nodes=result.final_refined_nodes,
                            resolution_events=result.resolution_events)
                        last_stage=replace(last_stage,nodes=result.final_nodes,refined_nodes=result.final_refined_nodes)
                    stages.append(row)
                    save(op.label+'.json', dict(row, history=result.history, trials=result.trials,
                                               acceptance_checks=result.acceptance_checks))
                    save('checkpoint.json', dict(stages=stages, curve=record_curve(curve), work=ledger.snapshot()))
                    event(op, 'stage returned', outcome=result.outcome, stop=result.stop_reason,
                          final_loss=result.final_loss)
                    # C12. Only normal return or a stage quota advances the queue.
                    if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                        outcome, detail = result.outcome, result.detail
                        event(op, 'hard or numerical stop; remaining stages skipped; final audit next')
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
            if hasattr(exc, 'resolution_selection'):
                save('resolution_selection_failure.json', exc.resolution_selection)
        except Exception:
            outcome, detail = 'EXCEPTION', traceback.format_exc()
        finally:
            if ledger is not None and not fit_seconds:
                fit_seconds = perf_counter()-ledger.started
            # Preserve endpoint before audits or external scoring can fail.
            fitting_snapshot=None if ledger is None else ledger.snapshot()
            if fitting_snapshot is not None:fit_seconds=fitting_snapshot['seconds']
            save('unscored.json', dict(outcome=outcome, detail=detail, final_curve=record_curve(curve),
                 stages=stages, fit_work=fitting_snapshot))
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
                audit_stage = (replace(last_stage, update_modes=1)
                               if update is not audit_update and last_stage.update_modes == 0 else last_stage)
                final_audit = numerical_audit(curve, audit_stage, last_config, problem, physics, audit_update, policy.audit_seconds)
                if (promoted and original_resolution is not None and
                        tuple(original_resolution) != (last_stage.nodes, last_stage.refined_nodes)):
                    original_stage = replace(last_stage, nodes=original_resolution[0],
                                             refined_nodes=original_resolution[1])
                    original_audit = numerical_audit(curve, original_stage, last_config, problem, physics,
                                                     audit_update, policy.audit_seconds)
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
        fit_work=fitting_snapshot, fit_and_localization_seconds=fit_seconds,
        fit_and_localization_units=0 if ledger is None else ledger.units,
        initial_audit_passed=initial_audit.get('passed', False), final_audit_passed=final_audit['passed'],
        relative_residual=final_audit.get('relative_residual'),
        audit_units=sum(a.get('work', {}).get('work_units', 0) for a in (initial_audit, final_audit, original_audit, *early_audits)),
        total_seconds=perf_counter()-started, audit_seconds=audit_spent, early_audits=early_audits,
        physics=physics.receipt(), geometry_work=dict(audit_update.counts),
        geometry_update=geometry_update, geometry_settings=update_settings)
    if stage_updates:
        row['stage_geometry_updates'] = {name: dict(settings=item.settings(), work=dict(item.counts))
                                        for name, item in stage_updates.items()}
        for item in stage_updates.values():
            for key, value in item.counts.items():
                row['geometry_work'][key] = row['geometry_work'].get(key, 0)+value
    row['exclusive_wall_seconds'] = dict(initial_audit=audit_phase_seconds['initial'],
        fit_and_localization=fit_seconds, early_audits=audit_phase_seconds['early'],
        terminal_audits=audit_phase_seconds['terminal'])
    row['total_units'] = row['fit_and_localization_units']+row['audit_units']
    row.update(resolution_gate=policy.resolution_gate,
               accepted_resolution_overshoots=sum(s['accepted_resolution_overshoots'] for s in stages),
               largest_accepted_resolution_overshoot=max(
                   (s['largest_accepted_resolution_overshoot'] for s in stages), default=0.))
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
