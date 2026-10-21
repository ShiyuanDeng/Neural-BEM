"""Frequency dispatch and work/failure recording around standalone forward solvers."""
import hashlib
import traceback
import numpy as np
from .continuation.forward import ordered_calls
from .continuation.geometry_runtime import geometry_validated
from .recording import observe


@geometry_validated
def solve_frequencies(curve, observations, contrast, nodes, category, *,
                      forward_solve, ledger, physics=None, failures=None, keep=True):
    """Run A1–A4 at each frequency; return predictions and retained forward states.

    No observations are subtracted here. The caller performs B5 separately.
    Scheduling, work charges and failure records are shared by ordinary and
    refined evaluations. Failed numerical solves return None.
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
            with ledger._lock:
                failures.append(failure)
            observe(physics, 'physics_failure', failure=failure, ledger=ledger)
            raise
        return state if keep else state.prediction  # release discarded systems early

    calls_for = ordered_calls if physics is None else physics.ordered_calls
    with ledger.calls(calls_for, predict, observations, "solve", category) as calls:
        for call in calls:
            try:
                value = call()
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                if not ledger.strict_dispatch:
                    ledger.fail(category)
                return None
            columns.append(np.asarray(value.prediction if keep else value).reshape(-1))
            if keep:
                forwards.append(value)
    return np.column_stack(columns), tuple(forwards)

