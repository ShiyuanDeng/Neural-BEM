"""Frequency dispatch and failure recording around a standalone forward solve."""
import hashlib
import traceback
import numpy as np
from .continuation.geometry_runtime import geometry_validated
from .recording import observe


@geometry_validated
def solve_frequencies(curve, observations, contrast, nodes, category, *,
                      forward_solve, ledger, threads, physics=None, failures=None):
    """Run A1–A4 at each frequency; return predictions and retained forward states.

    No observations are subtracted here. The caller performs B5 separately.
    ``ledger.calls`` schedules and charges the solves. Failed numerical solves
    are recorded in ``failures`` and return None.
    """
    if failures is None:
        failures = []
    ledger.reserve(len(observations))
    forwards, columns = [], []

    def predict(observation):
        try:
            state = forward_solve(curve, observation, contrast, nodes)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            failure = dict(exception_type=type(exc).__name__, message=str(exc),
                traceback=traceback.format_exc(),
                category=category, resolution=nodes,
                frequency_hz=getattr(observation, 'frequency_hz', None),
                wavenumber=dict(real=float(complex(observation.wavenumber).real),
                                imag=float(complex(observation.wavenumber).imag)),
                candidate_sha256=hashlib.sha256(curve.coefficients.tobytes()).hexdigest(),
                candidate_coefficients=dict(real=curve.coefficients.real.tolist(),
                                            imag=curve.coefficients.imag.tolist()))
            failures.append(failure)
            observe(physics, 'physics_failure', failure=failure, ledger=ledger)
            raise
        return state

    with ledger.calls(predict, observations, "solve", category, threads=threads) as calls:
        for call in calls:
            try:
                value = call()
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                return None
            columns.append(np.asarray(value.prediction).reshape(-1))
            forwards.append(value)
    return np.column_stack(columns), tuple(forwards)
