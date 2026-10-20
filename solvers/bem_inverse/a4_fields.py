"""A4. Matrix + source RHS → boundary traces → predicted measurements.

A_f is (2*(2*K_trace+1), 2*(2*K_trace+1)); columns of the right-hand side
and traces are sources. Trace rows stack u_D and speed-weighted flux q.
The LU factors remain owned by the per-frequency forward state for B7.
"""
from typing import NamedTuple
import numpy as np
from scipy.linalg import lu_factor, lu_solve


class Fields(NamedTuple):
    rhs: np.ndarray
    traces: np.ndarray
    system_residual: float
    receiver: np.ndarray
    prediction: np.ndarray
    test_indices: np.ndarray


def factorize(A_f):
    """CPU LU, including the original SciPy finite-input check."""
    return lu_factor(A_f, check_finite=True)


def solve_and_predict(A_f, factors, sources, receivers, cutoff, window, strength):
    """Solve all source columns and evaluate the matched receiver diagonal."""
    test, trial = window+np.arange(-cutoff, cutoff+1), window-np.arange(-cutoff, cutoff+1)
    rhs = np.vstack((sources[0][test], sources[1][test]))*strength
    traces = lu_solve(factors, rhs)
    residual = float(np.linalg.norm(A_f@traces-rhs)/np.linalg.norm(rhs))
    receiver = 2*np.pi*np.hstack((receivers[1][trial].T, -receivers[0][trial].T))
    prediction = np.einsum('ri,ir->r', receiver, traces)
    return Fields(rhs, traces, residual, receiver, prediction, test)
