"""Analytic references for 2D penetrable circular-cylinder TMz scattering."""

from __future__ import annotations

import math

import numpy as np
from scipy.special import h1vp, hankel1, jv, jvp

from .materials import Material

__all__ = [
    "cylinder_series_mode_numbers",
    "line_source_incident_field",
    "penetrable_cylinder_frequency_response",
    "penetrable_cylinder_scattered_field",
    "penetrable_cylinder_scattering_coefficient_ratio",
    "penetrable_cylinder_total_field",
]


def cylinder_series_mode_numbers(k_exterior: complex, k_interior: complex, radius: float) -> np.ndarray:
    """Return a conservative symmetric Fourier mode range for a circular cylinder."""

    scale = max(abs(complex(k_exterior)), abs(complex(k_interior))) * float(radius)
    nmax = int(math.ceil(3.0 * scale + 40.0))
    return np.arange(-nmax, nmax + 1, dtype=int)


def penetrable_cylinder_scattering_coefficient_ratio(
    mode_numbers: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    radius: float,
) -> np.ndarray:
    """Return the outgoing scattered coefficient per unit incident Bessel coefficient."""

    n = np.asarray(mode_numbers, dtype=int)
    ka_ext = complex(k_exterior) * float(radius)
    ka_int = complex(k_interior) * float(radius)
    numerator = (
        complex(k_interior) * jvp(n, ka_int) * jv(n, ka_ext)
        - complex(k_exterior) * jvp(n, ka_ext) * jv(n, ka_int)
    )
    denominator = (
        complex(k_exterior) * h1vp(n, ka_ext) * jv(n, ka_int)
        - complex(k_interior) * jvp(n, ka_int) * hankel1(n, ka_ext)
    )
    return numerator / denominator


def penetrable_cylinder_scattered_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    k_exterior: complex,
    k_interior: complex,
    radius: float,
    center: tuple[float, float],
    source_strength: complex | np.ndarray = 1.0,
) -> np.ndarray:
    """Return the exact exterior scattered field for paired line-source receivers."""

    receivers, sources = _coerce_paired_points(receiver_points, source_points)
    strengths = _coerce_pair_strengths(source_strength, sources.shape[0])
    center_array = np.asarray(center, dtype=float)
    n = cylinder_series_mode_numbers(k_exterior, k_interior, radius)
    coefficient_ratio = penetrable_cylinder_scattering_coefficient_ratio(
        n,
        k_exterior,
        k_interior,
        radius,
    )

    scattered = np.empty(sources.shape[0], dtype=np.complex128)
    for index, (receiver, source, strength) in enumerate(zip(receivers, sources, strengths)):
        receiver_delta = receiver - center_array
        source_delta = source - center_array
        receiver_radius = np.hypot(receiver_delta[0], receiver_delta[1])
        source_radius = np.hypot(source_delta[0], source_delta[1])
        if receiver_radius <= radius or source_radius <= radius:
            raise ValueError("This reference expects exterior source and receiver points.")
        receiver_angle = np.arctan2(receiver_delta[1], receiver_delta[0])
        source_angle = np.arctan2(source_delta[1], source_delta[0])
        coefficients = hankel1(n, complex(k_exterior) * source_radius) * coefficient_ratio
        scattered[index] = (
            strength
            * 0.25j
            * np.sum(
                coefficients
                * hankel1(n, complex(k_exterior) * receiver_radius)
                * np.exp(1j * n * (receiver_angle - source_angle))
            )
        )
    return scattered


def line_source_incident_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    k_exterior: complex,
    source_strength: complex | np.ndarray = 1.0,
) -> np.ndarray:
    """Return the paired 2D line-source incident field used by the IBIM solver."""

    receivers, sources = _coerce_paired_points(receiver_points, source_points)
    strengths = _coerce_pair_strengths(source_strength, sources.shape[0])
    distance = np.linalg.norm(receivers - sources, axis=1)
    if np.any(distance <= 0.0):
        raise ValueError("Source and receiver points must be distinct.")
    return strengths * (0.25j * hankel1(0, complex(k_exterior) * distance))


def penetrable_cylinder_total_field(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    k_exterior: complex,
    k_interior: complex,
    radius: float,
    center: tuple[float, float],
    source_strength: complex | np.ndarray = 1.0,
) -> np.ndarray:
    """Return incident plus exact scattered field for paired exterior receivers."""

    return line_source_incident_field(
        receiver_points,
        source_points,
        k_exterior=k_exterior,
        source_strength=source_strength,
    ) + penetrable_cylinder_scattered_field(
        receiver_points,
        source_points,
        k_exterior=k_exterior,
        k_interior=k_interior,
        radius=radius,
        center=center,
        source_strength=source_strength,
    )


def penetrable_cylinder_frequency_response(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    angular_frequencies: np.ndarray,
    source_strengths: complex | np.ndarray,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    radius: float,
    center: tuple[float, float],
    include_incident: bool = True,
) -> np.ndarray:
    """Return exact paired frequency response for a penetrable circular cylinder."""

    frequencies = np.atleast_1d(np.asarray(angular_frequencies, dtype=float))
    if frequencies.ndim != 1:
        raise ValueError("angular_frequencies must be scalar or one-dimensional.")
    strengths = np.atleast_1d(np.asarray(source_strengths, dtype=np.complex128))
    if strengths.size == 1:
        strengths = np.full(frequencies.shape, strengths[0], dtype=np.complex128)
    if strengths.shape != frequencies.shape:
        raise ValueError("source_strengths must be scalar or contain one value per frequency.")

    responses = []
    for angular_frequency, strength in zip(frequencies, strengths):
        k_exterior = exterior.wavenumber(float(angular_frequency), eps0, mu0)
        k_interior = interior.wavenumber(float(angular_frequency), eps0, mu0)
        scattered = penetrable_cylinder_scattered_field(
            receiver_points,
            source_points,
            k_exterior=k_exterior,
            k_interior=k_interior,
            radius=radius,
            center=center,
            source_strength=complex(strength),
        )
        if include_incident:
            response = scattered + line_source_incident_field(
                receiver_points,
                source_points,
                k_exterior=k_exterior,
                source_strength=complex(strength),
            )
        else:
            response = scattered
        responses.append(response)
    return np.stack(responses, axis=1).astype(np.complex128)


def _coerce_paired_points(receiver_points: np.ndarray, source_points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    receivers = np.atleast_2d(np.asarray(receiver_points, dtype=float))
    sources = np.atleast_2d(np.asarray(source_points, dtype=float))
    if receivers.shape != sources.shape or receivers.ndim != 2 or receivers.shape[1] != 2:
        raise ValueError("receiver_points and source_points must both have shape (num_pairs, 2).")
    return receivers, sources


def _coerce_pair_strengths(source_strength: complex | np.ndarray, num_pairs: int) -> np.ndarray:
    strengths = np.atleast_1d(np.asarray(source_strength, dtype=np.complex128))
    if strengths.size == 1:
        return np.full((num_pairs,), strengths[0], dtype=np.complex128)
    if strengths.shape != (num_pairs,):
        raise ValueError("source_strength must be scalar or one value per source point.")
    return strengths
