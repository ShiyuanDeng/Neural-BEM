"""Independent endpoint audit, run on a returned fit before any truth is read.

The fit no longer checks itself at a finer resolution (D7); this audit does, once,
after ``fit`` returns. It recomputes every real-frequency field, the Jacobian
columns and a complete-trial finite difference with the selected physics and
geometry update, at the production and refined resolutions that
``physics.resolution_profile`` gives for the returned curve. Recovery still
requires a passed audit (the unchanged CI-001 rule).
"""
from contextlib import contextmanager
import signal
from threading import current_thread, main_thread
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.b5_residual import normalize
from bem_inverse.continuation.geometry_runtime import geometry_validated
from bem_inverse.geometry_update_methods import bind_geometry_update
from bem_inverse.stage_types import BackendConfig
from bem_inverse.work import Ledger

# Wall allowance of one audit: the CumulativePolicy default, and the TG-002 policy contract.
SECONDS, POLICY_SECONDS = 300., 30.
JACOBIAN_TOLERANCE = FULL_TRIAL_TOLERANCE = 1e-3
FD_STEP_M, FD_SEED = 1e-7, 42001


def field_tolerances(observations):
    """Relative production/refined field agreement required at each frequency."""
    return tuple(1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in observations)


def passed(fields, tolerances, derivative, full_trial_error):
    """All-frequency field, per-column Jacobian and directional finite-difference tests."""
    return bool(np.all(fields <= tolerances) and max(derivative) <= JACOBIAN_TOLERANCE and
                full_trial_error <= FULL_TRIAL_TOLERANCE)


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
def audit(curve, update_modes, problem, physics, update, seconds):
    """SC-042 numerical gates at ``curve`` with ``update_modes`` coordinates, on all real data."""
    geometry_update = bind_geometry_update(update)
    count = len(problem.real)
    weights = tuple(np.ones(count)/count)
    tolerances = field_tolerances(problem.real)
    profile = physics.resolution_profile(curve.band)
    nodes, refined_nodes = profile['production'], profile['refined']
    residual_floor = BackendConfig.residual_floor
    ledger = Ledger(cap=6*count+16, seconds=seconds, endpoint_reserve=0)
    execution = getattr(physics, 'execution', None)
    batch = min(getattr(execution, 'audit_frequency_batch', 1), getattr(execution, 'frequency_threads', 1))
    started = perf_counter()
    try:
        with deadline(seconds):
            # Each frequency is independent. Keep only one coarse/fine pair of
            # dense systems long enough to extract the reciprocal derivatives.
            # Normalization/stacking below is the fit's B5 map.
            observed = np.column_stack([o.scattered.reshape(-1) for o in problem.real])
            space = update.prepare(curve, update_modes, curve.band)
            low_columns, high_columns, coarse_jac, fine_jac = [], [], [], []
            def evaluate(shape, observation, resolution, category):
                with ledger._lock:
                    ledger.reserve(1)
                    ledger.charge('solve', category)
                try:
                    return physics.evaluate(shape, observation, problem.contrast, resolution)
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
                low = evaluate(curve, observation, nodes, 'audit_base')
                high = evaluate(curve, observation, refined_nodes, 'audit_fine')
                lp = np.array(low.prediction, copy=True).reshape(-1)
                hp = np.array(high.prediction, copy=True).reshape(-1)
                return lp, hp, derivative(low), derivative(high)
            for lp, hp, ja, jb in batches(field_pair):
                low_columns.append(lp); high_columns.append(hp)
                coarse_jac.append(ja); fine_jac.append(jb)
            low_prediction, high_prediction = np.column_stack(low_columns), np.column_stack(high_columns)
            ja = normalize(np.stack(coarse_jac, axis=1), observed, weights, residual_floor)
            jb = normalize(np.stack(fine_jac, axis=1), observed, weights, residual_floor)
            fields = np.linalg.norm(low_prediction-high_prediction, axis=0)/np.linalg.norm(high_prediction, axis=0)
            colnorm = np.linalg.norm(jb, axis=0)
            derivative_error = np.linalg.norm(ja-jb, axis=0)/np.maximum(colnorm, 1e-30)
            direction = np.random.default_rng(FD_SEED).normal(size=ja.shape[1])
            direction /= np.linalg.norm(direction)
            residuals = []
            for sign in (1, -1):
                candidate = geometry_update(sign*FD_STEP_M*direction, prepared=space)[0]
                predictions = []
                def finite_difference(observation):
                    state = evaluate(candidate, observation, refined_nodes, 'audit_fd')
                    return np.array(state.prediction, copy=True).reshape(-1)
                predictions.extend(batches(finite_difference))
                residuals.append(normalize(np.column_stack(predictions)-observed, observed,
                                           weights, residual_floor))
            fd = (residuals[0]-residuals[1])/(2*FD_STEP_M)
            error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
            residual = normalize(high_prediction-observed, observed, weights, residual_floor)
            row = dict(passed=passed(fields, tolerances, derivative_error, error), field_relative=fields,
                jacobian_relative=derivative_error, jacobian_column_norm=colnorm, full_trial_fd_relative=error,
                fine_loss=.5*float(residual@residual),
                relative_residual=np.linalg.norm(high_prediction-observed, axis=0)/np.linalg.norm(observed, axis=0))
            if all(o.scattered.ndim == 2 for o in problem.real):
                paired_prediction = np.column_stack([np.diag(high_prediction[:,i].reshape(o.scattered.shape))
                                                     for i,o in enumerate(problem.real)])
                paired_observed = np.column_stack([np.diag(o.scattered) for o in problem.real])
                row['paired_relative_residual'] = (np.linalg.norm(paired_prediction-paired_observed,axis=0)
                                                  /np.linalg.norm(paired_observed,axis=0))
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    return dict(row, work=ledger.snapshot(), seconds=perf_counter()-started, solver=physics.name,
                frequency_batch=batch, update_modes=update_modes, storage_band=curve.band,
                production_resolution=nodes, refined_resolution=refined_nodes)


def audited_modes(final_stage):
    """M of the returned stage; a stage-local zero-mode update is audited with one ordinary mode."""
    if final_stage['fit_geometry_update'] is not None and final_stage['M'] == 0:
        return 1
    return final_stage['M']
