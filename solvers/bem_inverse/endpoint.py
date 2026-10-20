"""Independent endpoint calculations, separate from trial acceptance (C11).

The original all-real-frequency fields, Jacobian columns and complete-trial
finite difference are recomputed with the selected physics and geometry. Only
checks.py decides their numerical agreement; dispatch/budgets remain here.
"""
from contextlib import contextmanager
from dataclasses import replace
import signal
from threading import current_thread, main_thread
from time import perf_counter
import traceback
import numpy as np
from .continuation.geometry_runtime import geometry_validated
from .work import Ledger
from . import checks

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
    execution = getattr(physics, 'execution', None)
    batch = min(getattr(execution, 'audit_frequency_batch', 1), getattr(execution, 'frequency_threads', 1))
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
                with ledger._lock:
                    ledger.reserve(1)
                    ledger.charge('solve', category)
                try:
                    return physics.evaluate(shape, observation, problem.contrast, nodes)
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    with ledger._lock:
                        ledger.fail(category)
                    raise
            def derivative(state, category='derivative'):
                with ledger._lock:
                    ledger.reserve(1)
                    ledger.charge('reciprocal', category)
                block = physics.derivative(state, update, space)
                return block.reshape(-1, block.shape[-1])
            def batches(function):
                # Return arrays only; factorized systems die inside each worker.
                for begin in range(0, count, batch):
                    items = problem.real[begin:begin+batch]
                    if batch == 1:
                        yield function(items[0])
                    else:
                        with physics.ordered_calls(function, items) as calls:
                            for call in calls:
                                yield call()
            def field_pair(observation):
                low = evaluate(curve, observation, stage.nodes, 'audit_base')
                high = evaluate(curve, observation, stage.refined_nodes, 'audit_fine')
                lp = np.array(low.prediction, copy=True).reshape(-1)
                hp = np.array(high.prediction, copy=True).reshape(-1)
                ja, jb = derivative(low), derivative(high)
                rp = jr = None
                if independent_reference:
                    reference = evaluate(curve, observation, reference_nodes, 'audit_reference')
                    rp = np.array(reference.prediction, copy=True).reshape(-1)
                    jr = derivative(reference, 'audit_reference')
                return lp, hp, ja, jb, rp, jr
            for lp, hp, ja, jb, rp, jr in batches(field_pair):
                low_columns.append(lp); high_columns.append(hp)
                coarse_jac.append(ja); fine_jac.append(jb)
                if independent_reference:
                    reference_columns.append(rp); reference_jac.append(jr)
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
                def finite_difference(observation):
                    state = evaluate(candidate, observation, stage.refined_nodes, 'audit_fd')
                    return np.array(state.prediction, copy=True).reshape(-1)
                predictions.extend(batches(finite_difference))
                residuals.append(normalize(np.column_stack(predictions)-observed, observed,
                                           stage.weights, config.residual_floor))
            fd = (residuals[0]-residuals[1])/2e-7
            error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
            residual = normalize(high_prediction-observed, observed, stage.weights, config.residual_floor)
            row = dict(passed=checks.endpoint_passed(fields, stage.discrepancy_tolerances, derivative, error), field_relative=fields,
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
                row['passed'] = checks.endpoint_reference_passed(row['passed'], reference_fields,
                    stage.discrepancy_tolerances, reference_derivative)
            if all(o.scattered.ndim == 2 for o in problem.real):
                paired_prediction = np.column_stack([np.diag(high_prediction[:,i].reshape(o.scattered.shape))
                                                     for i,o in enumerate(problem.real)])
                paired_observed = np.column_stack([np.diag(o.scattered) for o in problem.real])
                row['paired_relative_residual'] = (np.linalg.norm(paired_prediction-paired_observed,axis=0)
                                                  /np.linalg.norm(paired_observed,axis=0))
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    return dict(row, work=ledger.snapshot(), seconds=perf_counter()-started, solver=physics.name,
                frequency_batch=batch,
                update_modes=stage.update_modes, storage_band=curve.band,
                production_resolution=stage.nodes, refined_resolution=stage.refined_nodes)
