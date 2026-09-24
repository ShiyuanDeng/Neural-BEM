"""Qualified training-only readiness routing for the normal full inverse.

Promoted from SPD-004/SPD-006 without changing the gate, fitting fallback,
independent endpoint checks, or optimizer budgets.
"""
from collections import Counter
from dataclasses import asdict
import time
import traceback
import numpy as np

from sdf_inverse.readiness import training_readiness
from sdf_inverse.runtime import inverse_execution
from . import run as pipeline

p, m = pipeline.p, pipeline.m
write = pipeline.write
NODES = (256, 512)
SCREEN_SOLVE_CAP, SCREEN_SECONDS = 8, 300


def combine_work(parts, elapsed):
    fields = ('attempted','completed','failed','calls','derivative_assemblies_attempted',
              'derivative_assemblies_completed','derivative_assemblies_failed',
              'per_frequency_attempted','per_frequency_completed','per_frequency_failed',
              'reciprocal_batches_attempted','reciprocal_batches_completed','reciprocal_batches_failed',
              'compiled_batches_attempted','compiled_batches_completed','compiled_batches_failed',
              'compiled_per_frequency_attempted','compiled_per_frequency_completed','compiled_per_frequency_failed')
    result = {}
    for name in fields:
        total = Counter()
        for part in parts:
            total.update(part.get(name, {}))
        result[name] = dict(total)
    result.update(total_attempted=sum(r['total_attempted'] for r in parts),
                  budget_work_units=sum(r['budget_work_units'] for r in parts),
                  solve_cap=sum(r['solve_cap'] for r in parts),
                  within_solve_cap=all(r['within_solve_cap'] for r in parts),
                  active_wall_seconds=elapsed,
                  wall_ceiling_seconds=sum(r['wall_ceiling_seconds'] for r in parts),
                  budget_unit='one full system, operator direction, reciprocal RHS batch, or compiled frequency batch',
                  parts=parts)
    return result


def screen_training(state, observed, solve, floor, ledger):
    """All routing inputs are training or numerical configuration, never truth."""
    p.training_data(p.TRAIN, observed)
    if not p.feasible(state, NODES, solve, floor):
        return dict(ready=False, reason='geometry_inadmissible'), {}
    predictions = {n:p.prediction(state, p.TRAIN, n, solve, ledger, 'readiness') for n in NODES}
    return training_readiness(observed, predictions[256], predictions[512]), predictions


@inverse_execution
def readiness_continuation(folder, state, optimizer, observed, evaluation, scene, spec, control, solve):
    started = time.perf_counter()
    screen = m.Ledger(cap=SCREEN_SOLVE_CAP, seconds=SCREEN_SECONDS)
    parts = []
    result = dict(status='IN_PROGRESS', fresh_recovery_pass=False)
    try:
        with screen.instrument():
            decision, training_predictions = screen_training(state, observed, solve,
                control.minimum_component_radius_m, screen)
        parts.append(screen.snapshot())
        write(folder.parent/'readiness.json',dict(decision=decision, state_sha256=m.state_hash(state),
            predictions={str(n):pipeline.follow.complex_record(v) for n,v in training_predictions.items()},
            frequencies_hz=p.TRAIN, solve_config=asdict(solve), work=parts[-1]))
        if not decision['ready']:
            result = pipeline.run_scheduled_continuation(folder, state, optimizer, observed, evaluation, scene, spec, control, solve)
            parts.append(result['work'])
            result.update(readiness=decision, skipped_continuation=False, screening_work=parts[0])
        else:
            # Routing is finished before independent evaluation/truth is used.
            folder.mkdir(parents=True, exist_ok=False)
            endpoint = m.Ledger(cap=4, seconds=300)
            with endpoint.instrument():
                predictions = {n:np.column_stack((training_predictions[n],
                    p.prediction(state, p.EVALUATION, n, solve, endpoint, 'endpoint'))) for n in NODES}
            parts.append(endpoint.snapshot())
            score = pipeline.base.score_predictions(state, scene, spec, observed, evaluation, predictions)
            write(folder/'endpoint_predictions.json',dict(state=p.driver.serialize_state(state),
                state_sha256=m.state_hash(state), frequencies_hz=pipeline.follow.FREQUENCIES,
                solve_config=asdict(solve), training_predictions_reused_after_decision=True,
                predictions={str(n):pipeline.follow.complex_record(v) for n,v in predictions.items()},score=score))
            metrics = dict(status='READY_WITHOUT_CONTINUATION',final_state=p.driver.serialize_state(state),
                final_state_sha256=m.state_hash(state),final=score, stages=[], schedule_complete=False,
                complete_effective_exposure=False, convergence='STATIONARITY_NOT_MEASURED',
                training_readiness=decision, reconstruction_gates_pass=score['original_gates_pass'],
                numerically_qualified=score['numerically_qualified'])
            write(folder/'metrics.json',metrics)
            result.update(status='READY_WITHOUT_CONTINUATION',readiness=decision,
                skipped_continuation=True, fresh_recovery_pass=bool(score['original_gates_pass'] and score['numerically_qualified']),
                schedule=metrics, screening_work=parts[0])
    except Exception as exc:
        if not parts:
            parts.append(screen.snapshot())
        # Preserve any partially attempted endpoint work as well.
        if 'endpoint' in locals() and len(parts)==1:
            parts.append(endpoint.snapshot())
        result.update(status='HARD_STOP',reason=getattr(exc,'code',type(exc).__name__),
                      detail=str(exc),traceback=traceback.format_exc(),fresh_recovery_pass=False)
    folder.mkdir(parents=True, exist_ok=True)
    result['work'] = combine_work(parts, time.perf_counter()-started)
    write(folder/'result.json',result)
    return result


