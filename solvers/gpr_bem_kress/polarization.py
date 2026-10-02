"""Opt-in TE/TM transmission and PDE shape derivatives on one smooth interface.

This module uses the established Kress difference kernels, and adds the
individual weakly singular operators needed when the normal derivative jumps.
The existing lossless TM API is unchanged. All calculations here use CPU SciPy.
See ``docs/reference/te_shape_derivative.md`` for conventions and derivation.
"""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1, jv

from periodic_kress import kress_log_weights
from .forward import (
    _points, _validate_exterior_points,
    build_exterior_receiver_operator, kress_incident_trace_on_boundary,
)
from .geometry import adapt_periodic_curve
from .operators import build_muller_difference_blocks

EPS0 = 8.8541878128e-12
MU0 = 1.25663706212e-6


def passive_permittivity(epsr, sigma, angular_frequency):
    """Absolute epsilon for exp(-i omega t): epsilon + i sigma / omega."""
    values = np.asarray([epsr, sigma, angular_frequency], dtype=float)
    if not np.all(np.isfinite(values)) or epsr <= 0 or sigma < 0 or angular_frequency <= 0:
        raise ValueError("Require epsr > 0, sigma >= 0 and angular_frequency > 0.")
    return EPS0 * epsr + 1j * sigma / angular_frequency


def passive_wavenumber(epsr, sigma, angular_frequency):
    """Nonmagnetic outgoing branch, Re(k)>0 and Im(k)>=0."""
    return angular_frequency * np.sqrt(MU0 * passive_permittivity(epsr, sigma, angular_frequency))


def arclength_derivative(curve):
    """Fourier collocation d/ds (the even-grid Nyquist derivative is zero)."""
    adapter = adapt_periodic_curve(curve)
    count = curve.num_nodes
    modes = np.fft.fftfreq(count, 1 / count)
    modes[count // 2] = 0
    derivative = np.fft.ifft(1j * modes[:, None] * np.fft.fft(np.eye(count), axis=0), axis=0).real
    return derivative / adapter.theta_speeds[:, None]


def _individual_operators(curve, wave):
    """Kress V,K,Kp; each includes source ds once, no trace jumps."""
    adapter = adapt_periodic_curve(curve)
    count = curve.num_nodes
    ids = np.arange(count)
    delta = curve.points[:, None, :] - curve.points[None, :, :]
    radius = np.linalg.norm(delta, axis=-1)
    np.fill_diagonal(radius, 1.0)  # diagonal overwritten by analytic limits
    target_dot = np.einsum("ijd,id->ij", delta, curve.normals)
    source_dot = np.einsum("ijd,jd->ij", delta, curve.normals)
    theta = adapter.theta[:, None] - adapter.theta[None, :]
    sine_squared = 4 * np.sin(theta / 2) ** 2
    np.fill_diagonal(sine_squared, 1.0)
    logarithm = np.log(sine_squared)
    speed = adapter.theta_speeds[None, :]
    weights = kress_log_weights(count)[(ids[:, None] - ids[None, :]) % count]
    z = wave * radius
    kernels = [0.25j * hankel1(0, z),
               0.25j * wave * hankel1(1, z) * source_dot / radius,
               -0.25j * wave * hankel1(1, z) * target_dot / radius]
    coefficients = [-jv(0, z) / (4 * np.pi),
                    -wave * jv(1, z) * source_dot / (4 * np.pi * radius),
                    wave * jv(1, z) * target_dot / (4 * np.pi * radius)]
    result = []
    for index, (kernel, coefficient) in enumerate(zip(kernels, coefficients)):
        smooth = (kernel - coefficient * logarithm) * speed
        coefficient = coefficient * speed
        if index == 0:
            np.fill_diagonal(coefficient, -adapter.theta_speeds / (4 * np.pi))
            np.fill_diagonal(smooth, adapter.theta_speeds * (
                0.25j - (np.log(wave * adapter.theta_speeds / 2) + np.euler_gamma) / (2 * np.pi)))
        else:
            np.fill_diagonal(coefficient, 0)
            np.fill_diagonal(smooth, -curve.curvatures * adapter.theta_speeds / (4 * np.pi))
        result.append(coefficient * weights + smooth * (2 * np.pi / count))
    return tuple(result)


@dataclass
class PolarizedSystem:
    curve: object
    k_exterior: complex
    k_interior: complex
    normal_ratio: complex
    matrix: np.ndarray
    factorization: tuple
    interior_v: np.ndarray
    interior_k: np.ndarray
    interior_kp: np.ndarray
    ds: np.ndarray

    def solve(self, rhs):
        return lu_solve(self.factorization, rhs)

    def interior_t_apply(self, values):
        """Maue identity T = d_s V d_s + k² n·V(n .), no f.p. subtraction."""
        result = self.ds @ (self.interior_v @ (self.ds @ values))
        for dimension in range(2):
            normal = self.curve.normals[:, dimension, None]
            result += self.k_interior ** 2 * normal * (self.interior_v @ (normal * values))
        return result


def build_polarized_system(curve, k_exterior, k_interior, *, normal_ratio=1):
    """Build weighted transmission with q_in = normal_ratio*q_out.

    For nonmagnetic TM use 1. For TE use epsilon_in/epsilon_out, including
    the complex passive permittivities for conductive media.
    """
    ratio = complex(normal_ratio)
    if not np.isfinite(ratio) or ratio.real <= 0:
        raise ValueError("normal_ratio must be finite with positive real part.")
    blocks = build_muller_difference_blocks(curve, k_exterior, k_interior)
    v, k, kp = _individual_operators(curve, blocks.k_interior)
    identity = np.eye(curve.num_nodes)
    matrix = np.block([
        [identity - blocks.delta_k, blocks.delta_v + (1 - ratio) * v],
        [-blocks.delta_t, (1 + ratio) * identity / 2 + blocks.delta_kp + (1 - ratio) * kp],
    ])
    return PolarizedSystem(curve, blocks.k_exterior, blocks.k_interior, ratio,
                           matrix, lu_factor(matrix), v, k, kp, arclength_derivative(curve))


@dataclass
class PolarizedForward:
    system: PolarizedSystem
    solution: np.ndarray
    receiver_operator: object
    scattered_receiver: np.ndarray
    relative_residual: float


def solve_polarized_transmission(curve, sources, receivers, k_exterior, k_interior,
                                *, normal_ratio=1, source_strength=1):
    """Line-source batch, result fields (source, receiver), exp(-i omega t)."""
    sources = _points(sources, name="sources")
    _validate_exterior_points(sources, curve, name="sources", minimum_clearance=0)
    system = build_polarized_system(curve, k_exterior, k_interior, normal_ratio=normal_ratio)
    incident, normal = kress_incident_trace_on_boundary(curve, sources, k_exterior, source_strength)
    rhs = np.concatenate([incident.T, normal.T])
    solution = system.solve(rhs)
    receiver = build_exterior_receiver_operator(curve, receivers, k_exterior)
    residual = np.linalg.norm(system.matrix @ solution - rhs) / max(np.linalg.norm(rhs), np.finfo(float).tiny)
    return PolarizedForward(system, solution, receiver, receiver.apply_state(solution), float(residual))


def polarized_shape_derivative(base, normal_velocity):
    """Eulerian exterior derivative from boundary jumps; reuse the primal LU.

    ``normal_velocity`` has shape (N,) or (N,directions). Return shape
    (directions,sources,receivers). Receiver locations are held fixed.
    """
    system = base.system
    count = system.curve.num_nodes
    if np.iscomplexobj(normal_velocity):
        raise ValueError("normal_velocity must be real-valued physical displacement.")
    h = np.asarray(normal_velocity, dtype=float)
    if h.ndim == 1:
        h = h[:, None]
    if h.ndim != 2 or h.shape[0] != count or not np.all(np.isfinite(h)):
        raise ValueError("normal_velocity must have finite shape (N,directions).")
    u, q = base.solution[:count], base.solution[count:]
    direction_count, source_count = h.shape[1], u.shape[1]
    h = h[:, :, None]
    # Jump f=[u']; b=[a*d_n u']/a_in, exterior minus interior.
    f = ((system.normal_ratio - 1) * h * q[:, None, :]).reshape(count, -1)
    tangential_product = (h * (system.ds @ u)[:, None, :]).reshape(count, -1)
    b = (system.normal_ratio - 1) * (system.ds @ tangential_product)
    b += (system.normal_ratio * system.k_exterior ** 2 - system.k_interior ** 2) * (
        h * u[:, None, :]).reshape(count, -1)
    rhs = np.concatenate([
        0.5 * f + system.interior_k @ f - system.interior_v @ b,
        system.interior_t_apply(f) + 0.5 * b - system.interior_kp @ b,
    ])
    derivative = base.receiver_operator.apply_state(system.solve(rhs))
    return derivative.reshape(direction_count, source_count, -1)
