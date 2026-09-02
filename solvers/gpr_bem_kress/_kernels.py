"""Cancellation-safe Helmholtz Müller difference kernels.

The ordinary branch is the same kernel-level exterior-minus-interior algebra
used by the frozen kdiff comparison experiment.  The near branch evaluates the
difference Green function and its radial derivatives as one power-log series;
it therefore never subtracts two ``O(r**-2)`` hypersingular values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import hankel1, jv

EULER_GAMMA = 0.577215664901532860606512090082402431


def _readonly_complex(values: np.ndarray) -> np.ndarray:
    result = np.array(values, dtype=np.complex128, copy=True, order="C")
    result.setflags(write=False)
    return result


def validate_wavenumber(value: complex, *, name: str) -> complex:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a complex-valued number, not bool.")
    wave = complex(value)
    if not np.isfinite(wave.real) or not np.isfinite(wave.imag):
        raise ValueError(f"{name} must be finite.")
    if abs(wave) == 0.0:
        raise ValueError(f"{name} must be nonzero for the Helmholtz formulation.")
    return wave


@dataclass(frozen=True)
class PairGeometry:
    """Geometry invariants for target/source pairs with ``rvec = x-y``."""

    distance: np.ndarray
    displacement_dot_target_normal: np.ndarray
    displacement_dot_source_normal: np.ndarray
    normal_dot: np.ndarray


def pair_geometry(
    targets: np.ndarray,
    target_normals: np.ndarray,
    sources: np.ndarray,
    source_normals: np.ndarray,
) -> PairGeometry:
    """Return dense target/source displacement invariants."""

    if any(
        np.iscomplexobj(values)
        for values in (targets, target_normals, sources, source_normals)
    ):
        raise ValueError("pair geometry coordinates and normals must be real-valued.")
    target_values = np.asarray(targets, dtype=np.float64)
    source_values = np.asarray(sources, dtype=np.float64)
    target_normal_values = np.asarray(target_normals, dtype=np.float64)
    source_normal_values = np.asarray(source_normals, dtype=np.float64)
    if target_values.ndim != 2 or target_values.shape[1] != 2:
        raise ValueError("targets must have shape (num_targets, 2).")
    if source_values.ndim != 2 or source_values.shape[1] != 2:
        raise ValueError("sources must have shape (num_sources, 2).")
    if target_normal_values.shape != target_values.shape:
        raise ValueError("target_normals must have the same shape as targets.")
    if source_normal_values.shape != source_values.shape:
        raise ValueError("source_normals must have the same shape as sources.")
    if not all(
        np.all(np.isfinite(values))
        for values in (
            target_values,
            source_values,
            target_normal_values,
            source_normal_values,
        )
    ):
        raise ValueError("pair geometry must contain only finite values.")

    displacement = target_values[:, None, :] - source_values[None, :, :]
    return PairGeometry(
        distance=np.linalg.norm(displacement, axis=-1),
        displacement_dot_target_normal=np.einsum(
            "mnd,md->mn", displacement, target_normal_values
        ),
        displacement_dot_source_normal=np.einsum(
            "mnd,nd->mn", displacement, source_normal_values
        ),
        normal_dot=target_normal_values @ source_normal_values.T,
    )


@dataclass(frozen=True)
class MullerKernelEvaluation:
    """Bare physical difference kernels and coefficients of ``log(r)``."""

    delta_v: np.ndarray
    delta_k: np.ndarray
    delta_kp: np.ndarray
    delta_t: np.ndarray
    log_v: np.ndarray
    log_k: np.ndarray
    log_kp: np.ndarray
    log_t: np.ndarray
    near_pair_count: int
    direct_pair_count: int


def _series_radial_differences(
    distance: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    *,
    terms: int,
) -> tuple[np.ndarray, ...]:
    """Evaluate ``g``, radial Hessian factors, and their log coefficients.

    Here ``g(r)=(i/4)(H0(k_o r)-H0(k_i r))``.  Writing each term as
    ``r**p * (P log(r)+Q)`` makes the leading singular pieces cancel in the
    coefficients before floating-point evaluation.
    """

    radius = np.asarray(distance, dtype=np.float64)
    log_radius = np.log(radius)
    g = np.zeros(radius.shape, dtype=np.complex128)
    radial_first = np.zeros_like(g)
    radial_anisotropy = np.zeros_like(g)
    g_log = np.zeros_like(g)
    radial_first_log = np.zeros_like(g)
    radial_anisotropy_log = np.zeros_like(g)

    coefficient_exterior = 1.0 + 0.0j
    coefficient_interior = 1.0 + 0.0j
    harmonic = 0.0
    log_exterior = np.log(k_exterior)
    log_interior = np.log(k_interior)

    for mode in range(terms):
        if mode:
            harmonic += 1.0 / mode
        difference = coefficient_exterior - coefficient_interior
        p_coefficient = -difference / (2.0 * np.pi)
        q_coefficient = difference * (
            0.25j + (np.log(2.0) - EULER_GAMMA + harmonic) / (2.0 * np.pi)
        ) + (
            coefficient_interior * log_interior
            - coefficient_exterior * log_exterior
        ) / (2.0 * np.pi)

        power = 2 * mode
        radius_power = radius**power
        value = p_coefficient * log_radius + q_coefficient
        g += radius_power * value
        g_log += radius_power * p_coefficient
        if mode:
            derivative_power = radius ** (power - 2)
            radial_first += derivative_power * (
                power * value + p_coefficient
            )
            radial_anisotropy += derivative_power * (
                power * (power - 2) * value
                + (2 * power - 2) * p_coefficient
            )
            radial_first_log += (
                derivative_power * power * p_coefficient
            )
            radial_anisotropy_log += (
                derivative_power * power * (power - 2) * p_coefficient
            )

        next_mode = mode + 1
        coefficient_exterior *= (
            -0.25 * k_exterior**2 / next_mode**2
        )
        coefficient_interior *= (
            -0.25 * k_interior**2 / next_mode**2
        )

    return (
        g,
        radial_first,
        radial_anisotropy,
        g_log,
        radial_first_log,
        radial_anisotropy_log,
    )


def _direct_radial_differences(
    distance: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
) -> tuple[np.ndarray, ...]:
    radius = np.asarray(distance, dtype=np.float64)
    exterior_argument = k_exterior * radius
    interior_argument = k_interior * radius
    delta_h0 = hankel1(0, exterior_argument) - hankel1(0, interior_argument)
    delta_h1 = (
        k_exterior * hankel1(1, exterior_argument)
        - k_interior * hankel1(1, interior_argument)
    )
    delta_h2 = (
        k_exterior**2 * hankel1(2, exterior_argument)
        - k_interior**2 * hankel1(2, interior_argument)
    )

    g = 0.25j * delta_h0
    radial_first = -0.25j * delta_h1 / radius
    radial_anisotropy = 0.25j * delta_h2

    scale = -1.0 / (2.0 * np.pi)
    delta_j0 = jv(0, exterior_argument) - jv(0, interior_argument)
    delta_j1 = (
        k_exterior * jv(1, exterior_argument)
        - k_interior * jv(1, interior_argument)
    )
    delta_j2 = (
        k_exterior**2 * jv(2, exterior_argument)
        - k_interior**2 * jv(2, interior_argument)
    )
    g_log = scale * delta_j0
    radial_first_log = -scale * delta_j1 / radius
    radial_anisotropy_log = scale * delta_j2
    return (
        g,
        radial_first,
        radial_anisotropy,
        g_log,
        radial_first_log,
        radial_anisotropy_log,
    )


def _evaluate_radial_differences(
    distance: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    *,
    near_argument: float,
    series_terms: int,
) -> tuple[tuple[np.ndarray, ...], int, int]:
    """Evaluate the six shared radial factors on validated nonzero pairs.

    This private seam lets the matrix builder consume one target-row chunk at
    a time.  The public evaluator below still exposes named physical kernels;
    the production builder need not retain eight additional dense arrays just
    to assemble four final matrices.
    """

    radius = np.asarray(distance, dtype=np.float64)
    shape = radius.shape
    radial_values = tuple(
        np.empty(shape, dtype=np.complex128) for _ in range(6)
    )
    if k_exterior == k_interior:
        for values in radial_values:
            values.fill(0.0)
        return radial_values, 0, 0

    near_mask = max(abs(k_exterior), abs(k_interior)) * radius <= near_argument
    direct_mask = ~near_mask
    if np.any(near_mask):
        near_values = _series_radial_differences(
            radius[near_mask],
            k_exterior,
            k_interior,
            terms=series_terms,
        )
        for destination, source in zip(radial_values, near_values):
            destination[near_mask] = source
    if np.any(direct_mask):
        direct_values = _direct_radial_differences(
            radius[direct_mask],
            k_exterior,
            k_interior,
        )
        for destination, source in zip(radial_values, direct_values):
            destination[direct_mask] = source
    near_count = int(np.count_nonzero(near_mask))
    return radial_values, near_count, int(radius.size - near_count)


def evaluate_muller_kernel_differences(
    geometry: PairGeometry,
    k_exterior: complex,
    k_interior: complex,
    *,
    near_argument: float = 0.75,
    series_terms: int = 24,
) -> MullerKernelEvaluation:
    """Evaluate all four exterior-minus-interior kernels at nonzero pairs.

    ``near_argument`` applies to ``max(|k_o|, |k_i|) r``.  The two branches
    deliberately overlap in tests; it is a numerical switch, not a change in
    the represented operator.
    """

    if not isinstance(geometry, PairGeometry):
        raise TypeError("geometry must be a PairGeometry object.")
    exterior = validate_wavenumber(k_exterior, name="k_exterior")
    interior = validate_wavenumber(k_interior, name="k_interior")
    raw_arrays = (
        geometry.distance,
        geometry.displacement_dot_target_normal,
        geometry.displacement_dot_source_normal,
        geometry.normal_dot,
    )
    if any(np.iscomplexobj(values) for values in raw_arrays):
        raise ValueError("pair-geometry arrays must be real-valued.")
    radius = np.asarray(geometry.distance, dtype=np.float64)
    target_projection = np.asarray(
        geometry.displacement_dot_target_normal, dtype=np.float64
    )
    source_projection = np.asarray(
        geometry.displacement_dot_source_normal, dtype=np.float64
    )
    normal_dot = np.asarray(geometry.normal_dot, dtype=np.float64)
    if any(
        values.shape != radius.shape
        for values in (target_projection, source_projection, normal_dot)
    ):
        raise ValueError("pair-geometry arrays must have one common shape.")
    if not all(
        np.all(np.isfinite(values))
        for values in (radius, target_projection, source_projection, normal_dot)
    ):
        raise ValueError("pair-geometry arrays must contain only finite values.")
    if np.any(radius <= 0.0):
        raise ValueError("kernel evaluation requires finite, strictly positive distances.")
    if isinstance(near_argument, (bool, np.bool_)):
        raise TypeError("near_argument must be a real number, not bool.")
    threshold = float(near_argument)
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("near_argument must be finite and positive.")
    if isinstance(series_terms, bool) or int(series_terms) != series_terms:
        raise TypeError("series_terms must be an integer.")
    term_count = int(series_terms)
    if term_count < 6:
        raise ValueError("series_terms must be at least 6.")

    radial_values, near_count, direct_count = _evaluate_radial_differences(
        radius,
        exterior,
        interior,
        near_argument=threshold,
        series_terms=term_count,
    )

    (
        green,
        radial_first,
        radial_anisotropy,
        green_log,
        radial_first_log,
        radial_anisotropy_log,
    ) = radial_values
    projection_product = target_projection * source_projection / radius**2

    delta_v = green
    delta_k = -radial_first * source_projection
    delta_kp = radial_first * target_projection
    delta_t = (
        -radial_first * normal_dot
        - radial_anisotropy * projection_product
    )
    log_v = green_log
    log_k = -radial_first_log * source_projection
    log_kp = radial_first_log * target_projection
    log_t = (
        -radial_first_log * normal_dot
        - radial_anisotropy_log * projection_product
    )

    arrays = (
        delta_v,
        delta_k,
        delta_kp,
        delta_t,
        log_v,
        log_k,
        log_kp,
        log_t,
    )
    if not all(np.all(np.isfinite(values)) for values in arrays):
        raise FloatingPointError("Müller kernel evaluation produced non-finite values.")
    readonly = tuple(_readonly_complex(values) for values in arrays)
    return MullerKernelEvaluation(
        *readonly,
        near_pair_count=near_count,
        direct_pair_count=direct_count,
    )


__all__ = [
    "MullerKernelEvaluation",
    "PairGeometry",
    "evaluate_muller_kernel_differences",
    "pair_geometry",
    "validate_wavenumber",
]
