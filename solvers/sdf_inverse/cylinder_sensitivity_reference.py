"""Independent matched-material circle sensitivity from the Mie Wronskian.

This opt-in reference is not a Kress derivative or a general material inverse.
It assumes a fixed circular interface, fixed paired exterior acquisition,
positive equal permittivities, zero conductivity, and relative permeability one.
"""

from __future__ import annotations

import math
import operator

import numpy as np
from scipy.special import hankel1, jv


def _real_scalar(value, *, name: str, positive: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise TypeError(f"{name} must be a real scalar, not bool or complex.")
    if np.ndim(value) != 0:
        raise TypeError(f"{name} must be a real scalar.")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        suffix = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {suffix}.")
    return result


def _points(value, *, name: str) -> np.ndarray:
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued.")
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 2 or result.shape[1:] != (2,) or result.shape[0] == 0:
        raise ValueError(f"{name} must have non-empty shape (num_pairs, 2).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain finite coordinates.")
    return result


def matched_material_cylinder_epsr_jvp(
    receiver_points,
    source_points,
    *,
    angular_frequency: float,
    exterior_epsr: float,
    interior_epsr: float,
    eps0: float,
    mu0: float,
    radius: float,
    center,
    maximum_mode: int,
    exterior_epsr_direction: float = 0.0,
    interior_epsr_direction: float = 1.0,
    source_strength=1.0,
) -> np.ndarray:
    """Return a paired scattered-field derivative for a real epsr direction.

    The result has shape ``(num_pairs,)`` and uses the same ``(i/4) H_0^(1)``
    line-source convention as ``gpr_bem_ref``. Acquisition, circle geometry,
    and source strengths are fixed. Conductivity is zero and relative
    permeability is one by construction; these parameters are not variable.

    ``maximum_mode=M`` fixes the symmetric inclusive mode range ``[-M, M]``.
    It must be an integer at least ``ceil(3*k*radius + 40)``. This conservative
    lower bound matches the existing Mie reference, but is not an a posteriori
    convergence certificate: callers can compare a larger *fixed* cutoff.

    At equal exterior/interior ``k``, each scattering coefficient is zero.
    Its interior-wavenumber derivative follows from the Bessel Wronskian:

    ``d beta_n / d k_i = (i*pi*radius**2*k/2) * (J_n**2 - J_(n-1)*J_(n+1))``.

    All Bessel factors here are evaluated at ``k*radius``. The exterior
    derivative is its negative. Derivatives of the incident/receiver Hankel
    factors multiply a zero base scattering coefficient, so only the contrast
    direction ``k*(dot_eps_i-dot_eps_e)/(2*epsr)`` remains. This is an analytic
    physical derivative, independent of the production integral operator.
    """

    receivers = _points(receiver_points, name="receiver_points")
    sources = _points(source_points, name="source_points")
    if receivers.shape != sources.shape:
        raise ValueError("receiver_points and source_points must have the same paired shape.")
    omega = _real_scalar(angular_frequency, name="angular_frequency", positive=True)
    eps_e = _real_scalar(exterior_epsr, name="exterior_epsr", positive=True)
    eps_i = _real_scalar(interior_epsr, name="interior_epsr", positive=True)
    if eps_e != eps_i:
        raise ValueError("This oracle requires exactly equal exterior and interior epsr.")
    epsilon_zero = _real_scalar(eps0, name="eps0", positive=True)
    mu_zero = _real_scalar(mu0, name="mu0", positive=True)
    circle_radius = _real_scalar(radius, name="radius", positive=True)
    direction_e = _real_scalar(exterior_epsr_direction, name="exterior_epsr_direction")
    direction_i = _real_scalar(interior_epsr_direction, name="interior_epsr_direction")
    if np.iscomplexobj(center):
        raise ValueError("center must be real-valued.")
    origin = np.asarray(center, dtype=np.float64)
    if origin.shape != (2,) or not np.all(np.isfinite(origin)):
        raise ValueError("center must contain exactly two finite coordinates.")
    if isinstance(maximum_mode, (bool, np.bool_)):
        raise TypeError("maximum_mode must be an integer, not bool.")
    try:
        cutoff = operator.index(maximum_mode)
    except TypeError as exc:
        raise TypeError("maximum_mode must be an integer.") from exc

    wave = omega * math.sqrt(mu_zero * epsilon_zero * eps_e)
    argument = wave * circle_radius
    if not math.isfinite(wave) or wave <= 0.0 or not math.isfinite(argument) or argument <= 0.0:
        raise FloatingPointError("Material/frequency scales must give a finite positive k*radius.")
    minimum_cutoff = math.ceil(3.0 * argument + 40.0)
    if cutoff < minimum_cutoff:
        raise ValueError(f"maximum_mode must be at least {minimum_cutoff} at the base material.")

    strengths = np.asarray(source_strength, dtype=np.complex128)
    if strengths.ndim == 0:
        strengths = np.full(sources.shape[0], strengths.item(), dtype=np.complex128)
    if strengths.shape != (sources.shape[0],) or not np.all(np.isfinite(strengths)):
        raise ValueError("source_strength must be finite and scalar or one value per pair.")
    source_delta = sources - origin
    receiver_delta = receivers - origin
    source_radius = np.linalg.norm(source_delta, axis=1)
    receiver_radius = np.linalg.norm(receiver_delta, axis=1)
    if np.any(source_radius <= circle_radius) or np.any(receiver_radius <= circle_radius):
        raise ValueError("This oracle requires strictly exterior source and receiver points.")
    if np.any(np.all(sources == receivers, axis=1)):
        raise ValueError("Each paired source and receiver must be distinct.")

    # A common material change preserves zero contrast exactly. Validate all
    # inputs first, but do not create roundoff residuals in this null direction.
    if direction_i == direction_e or np.all(strengths == 0.0):
        result = np.zeros(sources.shape[0], dtype=np.complex128)
    else:
        modes = np.arange(-cutoff, cutoff + 1, dtype=np.int64)
        bessel = jv(modes, argument)
        coefficient_derivative = (
            0.5j * np.pi * circle_radius**2 * wave
            * (bessel**2 - jv(modes - 1, argument) * jv(modes + 1, argument))
            * (wave * (direction_i - direction_e) / (2.0 * eps_e))
        )
        phase_angle = (
            np.arctan2(receiver_delta[:, 1], receiver_delta[:, 0])
            - np.arctan2(source_delta[:, 1], source_delta[:, 0])
        )
        with np.errstate(over="ignore", invalid="ignore"):
            terms = (
                hankel1(modes[None, :], wave * source_radius[:, None])
                * coefficient_derivative[None, :]
                * hankel1(modes[None, :], wave * receiver_radius[:, None])
                * np.exp(1j * phase_angle[:, None] * modes[None, :])
            )
            result = strengths * 0.25j * np.sum(terms, axis=1)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("The fixed-mode Mie sensitivity evaluation became non-finite.")
    result.setflags(write=False)
    return result


__all__ = ["matched_material_cylinder_epsr_jvp"]
