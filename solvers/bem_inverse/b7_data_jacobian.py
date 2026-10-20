"""B7. Geometry derivatives + forward/reciprocal traces → complex data Jacobian.

Velocities have axes (Cartesian coefficient, update coordinate). Traces have
axes (modal coefficient, source/receiver). One reciprocal batch serves every
coordinate, using the forward LU factors without a conjugate-transpose solve.
"""
import numpy as np
from scipy.linalg import lu_solve
from scipy.signal import fftconvolve
from .a1_geometry import real_product


def normal_velocity_weights(coefficients, velocities):
    """Return Re(V conj N) coefficients, with N the speed-weighted normal."""
    band = len(coefficients)//2
    speed_weighted_normal = np.arange(-band, band+1)*coefficients
    return real_product(velocities.T, speed_weighted_normal[None, :], 1).T


def reciprocal_jacobian(state, weights):
    """Return (complex data Jacobian, reciprocal traces), retaining LU reuse."""
    count = 2*state.cutoff+1
    reciprocal = lu_solve(state.factors, state.reciprocal_rhs)
    material_difference = state.interior_wavenumber**2-state.wavenumber**2
    J_data = hadamard(state.traces[:count], reciprocal[:count], weights,
                      state.cutoff, material_difference)
    return J_data, reciprocal


def hadamard(traces, reciprocal, weights, cutoff, factor):
    """2 pi (ki^2-ko^2) sum_m w_m (u_s u~_r)_(-m) for paired columns; w=Re(V conj N)."""
    moments = fftconvolve(traces, reciprocal, axes=0)
    centre = (len(weights)-1)//2
    n = min(centre, 2*cutoff)
    return 2*np.pi*factor*moments[2*cutoff-n:2*cutoff+n+1][::-1].T@weights[centre-n:centre+n+1]
