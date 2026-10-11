"""Shape-derivative helpers for ``d/dalpha[A(theta) q]``.

This module started as the Phase 3-4 verification prototype described in
``docs/legacy/adjoint_inverse_rebuild_plan.md``. The verified Muller system-action
contraction is now reused by ``ibim_tmz_adjoint.py`` for frozen-geometry
point-directional gradients; the scalar-loss helper at the bottom remains a
diagnostic, not production inverse plumbing.

Implements the full action derivative of the Muller system:

    d/dalpha[Aq] = [ -D_dot @ u_D + S_dot @ u_N ]
                   [  T_dot @ u_D + K'_dot @ u_N ]

using the Phase 1 kernel primitives in ``ibim_tmz_forward.py`` (including the
two third-derivative functions added for T), combined per
``docs/ibim_shape_derivative.md`` S6.2 (differentiate each wavenumber's block
separately, then subtract exterior-minus-interior, mirroring how the forward
system itself is assembled) and, for K'/T, S3.3's extrapolation-commutes
result (apply the same (3,-3,1) stencil to the *derivative* terms that the
forward pass applies to the potential terms).

Still explicitly out of scope here, same as before: deriving the
point/normal/weight velocity fields from SDF parameters. The arbitrary
velocities accepted by these helpers check whether the *assembly* is
differentiated correctly for a smooth one-parameter family of boundaries; they
do not exercise ``docs/ibim_shape_derivative.md`` S2.3's SDF-specific
geometric chain (``m_dot``, ``n_dot`` via the tangential projector, etc.).
"""

from __future__ import annotations

import numpy as np
from scipy.special import hankel1

from .ibim_geometry import ImplicitBoundarySamples2D
from .ibim_tmz_forward import (
    _normal_derivative_stencil,
    default_trace_offset_distance,
    implicit_double_layer_normal_derivative_potential_from_band,
    implicit_double_layer_potential_from_band,
    implicit_greens_function_mixed_directional_hessian_potential_from_band,
    implicit_greens_function_pure_source_hessian_potential_from_band,
    implicit_greens_function_pure_target_hessian_potential_from_band,
    implicit_greens_function_third_derivative_one_target_two_source_potential_from_band,
    implicit_greens_function_third_derivative_two_target_one_source_potential_from_band,
    implicit_single_layer_normal_derivative_potential_from_band,
    implicit_single_layer_potential_from_band,
    implicit_single_layer_source_directional_derivative_potential_from_band,
)
from .ibim_tmz_system import (
    MULLER_OFFSET_SCALE,
    adjoint_system_matrix,
    build_ibim_tmz_frequency_system,
    ibim_incident_trace_on_boundary,
)
from .materials import Material

__all__ = [
    "full_system_action_directional_derivative",
    "full_system_action_directional_derivative_from_wavenumbers",
    "single_sample_system_action_directional_derivative_from_wavenumbers",
    "resolve_muller_offset",
    "incident_trace_directional_derivative",
    "receiver_row_matrices",
    "receiver_row_action_directional_derivative",
    "full_loss_gradient_directional_derivative",
]


def resolve_muller_offset(band: ImplicitBoundarySamples2D) -> float:
    """The exact offset the real Muller system would resolve to, for this
    band, so a perturbed rebuild and this module's derivative use the
    identical scalar (merge_distance is untouched by the point/normal/weight
    perturbations used in the verification check, so this is safe to
    precompute once)."""

    return MULLER_OFFSET_SCALE * default_trace_offset_distance(band)


def _weight_array(band: ImplicitBoundarySamples2D, *, use_strict_quadrature: bool) -> np.ndarray:
    attr = "strict_quadrature_weights" if use_strict_quadrature else "quadrature_weights"
    return getattr(band, attr).detach().cpu().numpy().reshape(-1)


def _slice_boundary_sample(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    *,
    use_strict_quadrature: bool,
) -> ImplicitBoundarySamples2D:
    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    one_weight = weights[sample_index : sample_index + 1]
    return ImplicitBoundarySamples2D(
        points=band.points[sample_index : sample_index + 1],
        normals=band.normals[sample_index : sample_index + 1],
        quadrature_weights=_np_to_torch_like(one_weight, band.points),
        strict_quadrature_weights=_np_to_torch_like(one_weight, band.points),
        merge_distance=band.merge_distance,
        source_num_samples=1,
        bounds=band.bounds,
        level=band.level,
    )


def _np_to_torch_like(values: np.ndarray, reference):
    import torch

    return torch.as_tensor(values, dtype=reference.dtype, device=reference.device)


def _first_frequency_potential_vector(values, *, num_receivers: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.complex128)
    if array.ndim == 1:
        return array.reshape(num_receivers)
    if array.ndim == 2:
        return array[0].reshape(num_receivers)
    if array.ndim == 3 and array.shape[2] == 1:
        return array[0, :, 0].reshape(num_receivers)
    raise ValueError("Expected a single-frequency, single-density potential result.")


def _single_layer_single_sample_action_derivative_one_wavenumber(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    direction: np.ndarray,
    u_neumann: np.ndarray,
    wavenumber: complex,
    offset: float,
    *,
    use_strict_quadrature: bool,
) -> np.ndarray:
    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    source_sample = _slice_boundary_sample(
        band,
        sample_index,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_row = np.asarray(direction, dtype=float).reshape(1, 2)
    density = np.asarray(u_neumann, dtype=np.complex128)
    source_density = density[sample_index : sample_index + 1]
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        receivers = points + sign * offset * normals
        row_term = np.zeros(band.num_samples, dtype=np.complex128)
        row_term[sample_index] = _first_frequency_potential_vector(
            implicit_single_layer_normal_derivative_potential_from_band(
                receivers[sample_index : sample_index + 1],
                direction_row,
                band,
                density,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            ),
            num_receivers=1,
        )[0]
        col_term = _first_frequency_potential_vector(
            implicit_single_layer_source_directional_derivative_potential_from_band(
                receivers,
                source_sample,
                direction_row,
                source_density,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            ),
            num_receivers=band.num_samples,
        )
        total += 0.5 * (row_term + col_term)
    return total


def _double_layer_single_sample_action_derivative_one_wavenumber(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    direction: np.ndarray,
    u_dirichlet: np.ndarray,
    wavenumber: complex,
    offset: float,
    *,
    use_strict_quadrature: bool,
) -> np.ndarray:
    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    source_sample = _slice_boundary_sample(
        band,
        sample_index,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_row = np.asarray(direction, dtype=float).reshape(1, 2)
    density = np.asarray(u_dirichlet, dtype=np.complex128)
    source_density = density[sample_index : sample_index + 1]
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        receivers = points + sign * offset * normals
        row_term = np.zeros(band.num_samples, dtype=np.complex128)
        row_term[sample_index] = _first_frequency_potential_vector(
            implicit_greens_function_mixed_directional_hessian_potential_from_band(
                receivers[sample_index : sample_index + 1],
                direction_row,
                band,
                normals,
                density,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            ),
            num_receivers=1,
        )[0]
        col_term = _first_frequency_potential_vector(
            implicit_greens_function_pure_source_hessian_potential_from_band(
                receivers,
                source_sample,
                source_sample.normals.detach().cpu().numpy(),
                direction_row,
                source_density,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            ),
            num_receivers=band.num_samples,
        )
        total += 0.5 * (row_term + col_term)
    return total


def _adjoint_double_layer_single_sample_action_derivative_one_wavenumber(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    direction: np.ndarray,
    u_neumann: np.ndarray,
    wavenumber: complex,
    offset: float,
    *,
    use_strict_quadrature: bool,
) -> np.ndarray:
    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    source_sample = _slice_boundary_sample(
        band,
        sample_index,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_row = np.asarray(direction, dtype=float).reshape(1, 2)
    density = np.asarray(u_neumann, dtype=np.complex128)
    source_density = density[sample_index : sample_index + 1]
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    multipliers, coefficients = _normal_derivative_stencil("analytic_extrapolated")
    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        for multiplier, coeff in zip(multipliers, coefficients):
            receivers = points + sign * multiplier * offset * normals
            row_term = np.zeros(band.num_samples, dtype=np.complex128)
            row_term[sample_index] = _first_frequency_potential_vector(
                implicit_greens_function_pure_target_hessian_potential_from_band(
                    receivers[sample_index : sample_index + 1],
                    normals[sample_index : sample_index + 1],
                    direction_row,
                    band,
                    density,
                    wavenumbers,
                    use_strict_quadrature=use_strict_quadrature,
                ),
                num_receivers=1,
            )[0]
            col_term = _first_frequency_potential_vector(
                implicit_greens_function_mixed_directional_hessian_potential_from_band(
                    receivers,
                    normals,
                    source_sample,
                    direction_row,
                    source_density,
                    wavenumbers,
                    use_strict_quadrature=use_strict_quadrature,
                ),
                num_receivers=band.num_samples,
            )
            total += 0.5 * coeff * (row_term + col_term)
    return total


def _hypersingular_single_sample_action_derivative_one_wavenumber(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    direction: np.ndarray,
    u_dirichlet: np.ndarray,
    wavenumber: complex,
    offset: float,
    *,
    use_strict_quadrature: bool,
) -> np.ndarray:
    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    source_sample = _slice_boundary_sample(
        band,
        sample_index,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_row = np.asarray(direction, dtype=float).reshape(1, 2)
    density = np.asarray(u_dirichlet, dtype=np.complex128)
    source_density = density[sample_index : sample_index + 1]
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    multipliers, coefficients = _normal_derivative_stencil("analytic_extrapolated")
    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        for multiplier, coeff in zip(multipliers, coefficients):
            receivers = points + sign * multiplier * offset * normals
            row_term = np.zeros(band.num_samples, dtype=np.complex128)
            row_term[sample_index] = _first_frequency_potential_vector(
                implicit_greens_function_third_derivative_two_target_one_source_potential_from_band(
                    receivers[sample_index : sample_index + 1],
                    normals[sample_index : sample_index + 1],
                    direction_row,
                    band,
                    normals,
                    density,
                    wavenumbers,
                    use_strict_quadrature=use_strict_quadrature,
                ),
                num_receivers=1,
            )[0]
            col_term = _first_frequency_potential_vector(
                implicit_greens_function_third_derivative_one_target_two_source_potential_from_band(
                    receivers,
                    normals,
                    source_sample,
                    source_sample.normals.detach().cpu().numpy(),
                    direction_row,
                    source_density,
                    wavenumbers,
                    use_strict_quadrature=use_strict_quadrature,
                ),
                num_receivers=band.num_samples,
            )
            total += 0.5 * coeff * (row_term + col_term)
    return -total


def single_sample_system_action_directional_derivative_from_wavenumbers(
    band: ImplicitBoundarySamples2D,
    sample_index: int,
    direction: np.ndarray,
    u_dirichlet: np.ndarray,
    u_neumann: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    offset_distance: float,
    *,
    use_strict_quadrature: bool = True,
) -> np.ndarray:
    """Sparse one-sample Muller ``d/dalpha[Aq]`` contraction.

    Normals and quadrature weights are frozen. This is the fast path used for
    normal-shape-gradient basis directions.
    """

    def _combine(fn, u):
        ext = fn(
            band,
            sample_index,
            direction,
            u,
            k_exterior,
            offset_distance,
            use_strict_quadrature=use_strict_quadrature,
        )
        interior_val = fn(
            band,
            sample_index,
            direction,
            u,
            k_interior,
            offset_distance,
            use_strict_quadrature=use_strict_quadrature,
        )
        return ext - interior_val

    s_dot = _combine(_single_layer_single_sample_action_derivative_one_wavenumber, u_neumann)
    d_dot = _combine(_double_layer_single_sample_action_derivative_one_wavenumber, u_dirichlet)
    k_adj_dot = _combine(_adjoint_double_layer_single_sample_action_derivative_one_wavenumber, u_neumann)
    t_dot = _combine(_hypersingular_single_sample_action_derivative_one_wavenumber, u_dirichlet)
    return np.concatenate([-d_dot + s_dot, t_dot + k_adj_dot])


def _single_layer_block_action_derivative_one_wavenumber(
    band, point_velocity, normal_velocity, weight_velocity, u_neumann, wavenumber, offset,
    *, use_strict_quadrature,
) -> np.ndarray:
    """``S_dot @ u_neumann`` -- plain +-offset average, no extrapolation."""

    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    density = np.asarray(u_neumann, dtype=np.complex128)
    density_weight_scaled = density * (weight_velocity / weights)

    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        receivers = points + sign * offset * normals
        row_direction = point_velocity + sign * offset * normal_velocity

        term_row = implicit_single_layer_normal_derivative_potential_from_band(
            receivers, row_direction, band, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        )
        term_col = implicit_single_layer_source_directional_derivative_potential_from_band(
            receivers, band, point_velocity, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        )
        term_weight = implicit_single_layer_potential_from_band(
            receivers, band, density_weight_scaled, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        ).potentials
        total = total + 0.5 * (term_row + term_col + term_weight).reshape(-1)
    return total


def _double_layer_block_action_derivative_one_wavenumber(
    band, point_velocity, normal_velocity, weight_velocity, u_dirichlet, wavenumber, offset,
    *, use_strict_quadrature,
) -> np.ndarray:
    """``D_dot @ u_dirichlet`` -- plain +-offset average, no extrapolation."""

    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    density = np.asarray(u_dirichlet, dtype=np.complex128)
    density_weight_scaled = density * (weight_velocity / weights)

    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        receivers = points + sign * offset * normals
        row_direction = point_velocity + sign * offset * normal_velocity

        term_mixed = implicit_greens_function_mixed_directional_hessian_potential_from_band(
            receivers, row_direction, band, normals, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        )
        term_pure_source = implicit_greens_function_pure_source_hessian_potential_from_band(
            receivers, band, normals, point_velocity, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        )
        term_normal_motion = implicit_single_layer_source_directional_derivative_potential_from_band(
            receivers, band, normal_velocity, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        )
        term_weight = implicit_double_layer_potential_from_band(
            receivers, band, density_weight_scaled, wavenumbers, use_strict_quadrature=use_strict_quadrature,
        ).potentials
        total = total + 0.5 * (term_mixed + term_pure_source + term_normal_motion + term_weight).reshape(-1)
    return total


def _adjoint_double_layer_block_action_derivative_one_wavenumber(
    band, point_velocity, normal_velocity, weight_velocity, u_neumann, wavenumber, offset,
    *, use_strict_quadrature,
) -> np.ndarray:
    """``K'_dot @ u_neumann`` -- 3-point (3,-3,1) extrapolation stencil,
    per side, per S3.3's "extrapolation commutes with the shape derivative"
    result."""

    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    density = np.asarray(u_neumann, dtype=np.complex128)
    density_weight_scaled = density * (weight_velocity / weights)
    multipliers, coefficients = _normal_derivative_stencil("analytic_extrapolated")

    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        for multiplier, coeff in zip(multipliers, coefficients):
            step = sign * multiplier * offset
            receivers = points + step * normals
            row_direction = point_velocity + step * normal_velocity

            term_row = implicit_greens_function_pure_target_hessian_potential_from_band(
                receivers, normals, row_direction, band, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
            )
            term_col = implicit_greens_function_mixed_directional_hessian_potential_from_band(
                receivers, normals, band, point_velocity, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
            )
            term_normal_motion = implicit_single_layer_normal_derivative_potential_from_band(
                receivers, normal_velocity, band, density, wavenumbers, use_strict_quadrature=use_strict_quadrature,
            )
            term_weight = implicit_single_layer_normal_derivative_potential_from_band(
                receivers, normals, band, density_weight_scaled, wavenumbers, use_strict_quadrature=use_strict_quadrature,
            )
            total = total + 0.5 * coeff * (term_row + term_col + term_normal_motion + term_weight).reshape(-1)
    return total


def _hypersingular_block_action_derivative_one_wavenumber(
    band, point_velocity, normal_velocity, weight_velocity, u_dirichlet, wavenumber, offset,
    *, use_strict_quadrature,
) -> np.ndarray:
    """``(-MixedKernel)_dot @ u_dirichlet`` -- 3-point extrapolation stencil,
    per side; the leading minus is T's own definition
    (``build_implicit_hypersingular_boundary_matrix`` negates the whole
    trace), applied once at the end."""

    points = band.points.detach().cpu().numpy()
    normals = band.normals.detach().cpu().numpy()
    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    density = np.asarray(u_dirichlet, dtype=np.complex128)
    density_weight_scaled = density * (weight_velocity / weights)
    multipliers, coefficients = _normal_derivative_stencil("analytic_extrapolated")

    total = np.zeros(band.num_samples, dtype=np.complex128)
    for sign in (+1.0, -1.0):
        for multiplier, coeff in zip(multipliers, coefficients):
            step = sign * multiplier * offset
            receivers = points + step * normals
            row_direction = point_velocity + step * normal_velocity

            term_row = implicit_greens_function_third_derivative_two_target_one_source_potential_from_band(
                receivers, normals, row_direction, band, normals, density, wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            )
            term_col = implicit_greens_function_third_derivative_one_target_two_source_potential_from_band(
                receivers, normals, band, normals, point_velocity, density, wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            )
            term_row_normal_motion = implicit_greens_function_mixed_directional_hessian_potential_from_band(
                receivers, normal_velocity, band, normals, density, wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            )
            term_col_normal_motion = implicit_greens_function_mixed_directional_hessian_potential_from_band(
                receivers, normals, band, normal_velocity, density, wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            )
            term_weight = implicit_double_layer_normal_derivative_potential_from_band(
                receivers, normals, band, density_weight_scaled, wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
            )
            total = total + 0.5 * coeff * (
                term_row + term_col + term_row_normal_motion + term_col_normal_motion + term_weight
            ).reshape(-1)
    return -total


def full_system_action_directional_derivative(
    band: ImplicitBoundarySamples2D,
    point_velocity: np.ndarray,
    normal_velocity: np.ndarray,
    weight_velocity: np.ndarray,
    u_dirichlet: np.ndarray,
    u_neumann: np.ndarray,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    use_strict_quadrature: bool = True,
) -> np.ndarray:
    """``d/dalpha[A(theta) q]``, both output rows, shape ``(2N,)`` complex,
    concatenated ``[top_row; bottom_row]`` matching the real system's
    ``[u_dirichlet; u_neumann]`` stacking convention.
    """

    offset = resolve_muller_offset(band)
    k_exterior = complex(exterior.wavenumber(float(angular_frequency), eps0, mu0))
    k_interior = complex(interior.wavenumber(float(angular_frequency), eps0, mu0))
    return full_system_action_directional_derivative_from_wavenumbers(
        band,
        point_velocity,
        normal_velocity,
        weight_velocity,
        u_dirichlet,
        u_neumann,
        k_exterior,
        k_interior,
        offset,
        use_strict_quadrature=use_strict_quadrature,
    )


def full_system_action_directional_derivative_from_wavenumbers(
    band: ImplicitBoundarySamples2D,
    point_velocity: np.ndarray,
    normal_velocity: np.ndarray,
    weight_velocity: np.ndarray,
    u_dirichlet: np.ndarray,
    u_neumann: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    offset_distance: float,
    *,
    use_strict_quadrature: bool = True,
) -> np.ndarray:
    """``d/dalpha[A(theta) q]`` for the Muller system with known wavenumbers.

    This variant is used by the production adjoint path, where the forward
    context already stores the resolved wavenumbers and trace offset but not
    the material objects that produced them.
    """

    def _combine(fn, u):
        ext = fn(band, point_velocity, normal_velocity, weight_velocity, u, k_exterior, offset_distance,
                  use_strict_quadrature=use_strict_quadrature)
        interior_val = fn(band, point_velocity, normal_velocity, weight_velocity, u, k_interior, offset_distance,
                           use_strict_quadrature=use_strict_quadrature)
        return ext - interior_val

    s_dot = _combine(_single_layer_block_action_derivative_one_wavenumber, u_neumann)
    d_dot = _combine(_double_layer_block_action_derivative_one_wavenumber, u_dirichlet)
    k_adj_dot = _combine(_adjoint_double_layer_block_action_derivative_one_wavenumber, u_neumann)
    t_dot = _combine(_hypersingular_block_action_derivative_one_wavenumber, u_dirichlet)

    top_row = -d_dot + s_dot
    bottom_row = t_dot + k_adj_dot
    return np.concatenate([top_row, bottom_row])


def _pure_target_hessian_scalar(disp, r, e, wavenumber, direction_a, direction_b):
    """Same closed form as
    ``implicit_greens_function_pure_target_hessian_potential_from_band``'s
    kernel, evaluated standalone (no band/quadrature) -- reused verbatim
    rather than re-derived, to avoid a second, independent chance to get the
    H0/H1/H2 bookkeeping wrong."""

    k = wavenumber
    z = k * r
    h0 = hankel1(0, z)
    h1 = hankel1(1, z)
    h2 = 2.0 * h1 / z - h0
    factor_a = np.einsum("...d,...d->...", disp, direction_a) / r
    factor_b = np.einsum("...d,...d->...", disp, direction_b) / r
    normal_dot = np.einsum("...d,...d->...", direction_a, direction_b)
    return -0.25j * (k * h1 * normal_dot / r - k * k * h2 * factor_a * factor_b)


def incident_trace_directional_derivative(
    boundary_points: np.ndarray,
    boundary_normals: np.ndarray,
    point_velocity: np.ndarray,
    normal_velocity: np.ndarray,
    source_points: np.ndarray,
    source_strength,
    wavenumber: complex,
):
    """``d/dalpha[dirichlet_incident, neumann_incident]``, standalone.

    The incident trace (``ibim_incident_trace_on_boundary``) is a direct
    point evaluation between fixed transmitter positions and boundary
    points -- no BEM quadrature weight, no offset averaging (the boundary is
    evaluated exactly at ``boundary_points``, not a probe point). So this
    needs only a first derivative for the Dirichlet trace and a first +
    (pure target) second derivative for the Neumann trace -- see
    ``docs/ibim_shape_derivative.md`` S8, re-derived here against the actual
    ``ibim_incident_trace_on_boundary`` formula rather than assumed
    unchanged from the pre-Muller version.
    """

    boundary_points = np.asarray(boundary_points, dtype=float)
    boundary_normals = np.asarray(boundary_normals, dtype=float)
    point_velocity = np.asarray(point_velocity, dtype=float)
    normal_velocity = np.asarray(normal_velocity, dtype=float)
    source_points = np.asarray(source_points, dtype=float)
    strengths = np.asarray(source_strength, dtype=complex).reshape(-1)
    if strengths.shape[0] == 1 and source_points.shape[0] > 1:
        strengths = np.full(source_points.shape[0], strengths[0])
    k = complex(wavenumber)

    disp = boundary_points[None, :, :] - source_points[:, None, :]  # (S, N, 2)
    r = np.linalg.norm(disp, axis=2)
    e = disp / r[:, :, None]
    z = k * r
    h1 = hankel1(1, z)
    fp = -0.25j * k * h1  # radial coefficient of grad_x G . v

    grad_dot_point_velocity = fp * np.einsum("snd,nd->sn", disp, point_velocity) / r
    dirichlet_dot = strengths[:, None] * grad_dot_point_velocity

    pure_target_term = _pure_target_hessian_scalar(
        disp, r, e, k, boundary_normals[None, :, :], point_velocity[None, :, :]
    )
    normal_motion_term = fp * np.einsum("snd,nd->sn", disp, normal_velocity) / r
    neumann_dot = strengths[:, None] * (pure_target_term + normal_motion_term)

    return dirichlet_dot, neumann_dot


def receiver_row_matrices(
    band: ImplicitBoundarySamples2D,
    receiver_points: np.ndarray,
    wavenumber: complex,
    *,
    use_strict_quadrature: bool,
):
    """Full ``S_r``, ``D_r`` receiver-row matrices (no offset averaging --
    receivers are fixed external points, not boundary probe points), via
    identity densities on the already-validated potential functions.
    """

    num_samples = band.num_samples
    identity = np.eye(num_samples, dtype=np.complex128)
    wavenumbers = np.array([wavenumber], dtype=np.complex128)
    s_r = implicit_single_layer_potential_from_band(
        receiver_points, band, identity, wavenumbers, use_strict_quadrature=use_strict_quadrature
    ).potentials[0]
    d_r = implicit_double_layer_potential_from_band(
        receiver_points, band, identity, wavenumbers, use_strict_quadrature=use_strict_quadrature
    ).potentials[0]
    return s_r, d_r


def receiver_row_action_directional_derivative(
    band: ImplicitBoundarySamples2D,
    receiver_points: np.ndarray,
    point_velocity: np.ndarray,
    normal_velocity: np.ndarray,
    weight_velocity: np.ndarray,
    u_dirichlet: np.ndarray,
    u_neumann: np.ndarray,
    wavenumber: complex,
    *,
    use_strict_quadrature: bool,
) -> np.ndarray:
    """``Ċq = Ḋ_r @ u_dirichlet - Ṡ_r @ u_neumann`` -- receivers are fixed,
    so only column (source/boundary-point) motion terms apply, no offset
    averaging, single wavenumber (``k_exterior`` -- receivers live in the
    exterior domain, matching ``solve_ibim_tmz_total_field_batch``).
    """

    weights = _weight_array(band, use_strict_quadrature=use_strict_quadrature)
    normals = band.normals.detach().cpu().numpy()
    wavenumbers = np.array([wavenumber], dtype=np.complex128)

    density_d = np.asarray(u_dirichlet, dtype=np.complex128)
    density_d_weight_scaled = density_d * (weight_velocity / weights)
    d_r_pure_source = implicit_greens_function_pure_source_hessian_potential_from_band(
        receiver_points, band, normals, point_velocity, density_d, wavenumbers,
        use_strict_quadrature=use_strict_quadrature,
    )
    d_r_normal_motion = implicit_single_layer_source_directional_derivative_potential_from_band(
        receiver_points, band, normal_velocity, density_d, wavenumbers, use_strict_quadrature=use_strict_quadrature,
    )
    d_r_weight = implicit_double_layer_potential_from_band(
        receiver_points, band, density_d_weight_scaled, wavenumbers, use_strict_quadrature=use_strict_quadrature,
    ).potentials
    d_dot_r_u_d = (d_r_pure_source + d_r_normal_motion + d_r_weight).reshape(-1)

    density_n = np.asarray(u_neumann, dtype=np.complex128)
    density_n_weight_scaled = density_n * (weight_velocity / weights)
    s_r_col = implicit_single_layer_source_directional_derivative_potential_from_band(
        receiver_points, band, point_velocity, density_n, wavenumbers, use_strict_quadrature=use_strict_quadrature,
    )
    s_r_weight = implicit_single_layer_potential_from_band(
        receiver_points, band, density_n_weight_scaled, wavenumbers, use_strict_quadrature=use_strict_quadrature,
    ).potentials
    s_dot_r_u_n = (s_r_col + s_r_weight).reshape(-1)

    return d_dot_r_u_d - s_dot_r_u_n


def full_loss_gradient_directional_derivative(
    band: ImplicitBoundarySamples2D,
    point_velocity: np.ndarray,
    normal_velocity: np.ndarray,
    weight_velocity: np.ndarray,
    source_points: np.ndarray,
    receiver_points: np.ndarray,
    source_strength,
    observed: np.ndarray,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    use_strict_quadrature: bool = True,
) -> tuple[float, float]:
    """``dJ/dalpha`` via the discrete adjoint identity, for
    ``J = 0.5 sum_r |total_receiver_r - observed_r|^2``.

    Returns ``(dJ_dalpha, J)``. Solves the real forward system once (to get
    ``q`` and the loss), assembles the real dual system once (``A^H``,
    reusing Phase 2's ``adjoint_system_matrix``, no re-derivation), solves
    for ``mu``, then combines with S3-S8's building blocks per
    ``docs/ibim_shape_derivative.md`` S9: ``Re[mu^H(bdot - Adot q) + psi^H
    (Cdot q)]``.
    """

    system = build_ibim_tmz_frequency_system(
        band, angular_frequency, exterior=exterior, interior=interior, eps0=eps0, mu0=mu0,
        use_strict_quadrature=use_strict_quadrature,
    )
    dirichlet_incident, neumann_incident = ibim_incident_trace_on_boundary(
        band, source_points, angular_frequency, source_strength, exterior=exterior, eps0=eps0, mu0=mu0,
    )
    rhs = np.concatenate([dirichlet_incident[0], neumann_incident[0]])
    A = system.system_matrix[0]
    q = np.linalg.solve(A, rhs)
    num_samples = band.num_samples
    u_dirichlet = q[:num_samples]
    u_neumann = q[num_samples:]

    s_r, d_r = receiver_row_matrices(
        band, receiver_points, system.k_exterior, use_strict_quadrature=use_strict_quadrature
    )
    strengths = np.asarray(source_strength, dtype=complex).reshape(-1)
    if strengths.shape[0] == 1 and source_points.shape[0] > 1:
        strengths = np.full(source_points.shape[0], strengths[0])
    source_receiver_distance = np.linalg.norm(np.asarray(receiver_points) - np.asarray(source_points), axis=1)
    incident_receiver = strengths * (0.25j * hankel1(0, system.k_exterior * source_receiver_distance))
    scattered_receiver = d_r @ u_dirichlet - s_r @ u_neumann
    total_receiver = incident_receiver + scattered_receiver

    residual = total_receiver - np.asarray(observed, dtype=complex)
    loss = 0.5 * float(np.sum(np.abs(residual) ** 2))
    psi = 0.5 * residual  # dJ/dconj(y) for J = 0.5 sum |y - obs|^2

    c_h_psi_top = d_r.conj().T @ psi
    c_h_psi_bottom = -(s_r.conj().T @ psi)
    rhs_dual = np.concatenate([c_h_psi_top, c_h_psi_bottom])
    a_h = adjoint_system_matrix(system)[0]
    mu = np.linalg.solve(a_h, rhs_dual)

    dirichlet_dot, neumann_dot = incident_trace_directional_derivative(
        band.points.detach().cpu().numpy(), band.normals.detach().cpu().numpy(),
        point_velocity, normal_velocity, source_points, source_strength, system.k_exterior,
    )
    b_dot = np.concatenate([dirichlet_dot[0], neumann_dot[0]])

    a_dot_q = full_system_action_directional_derivative(
        band, point_velocity, normal_velocity, weight_velocity, u_dirichlet, u_neumann,
        angular_frequency, exterior=exterior, interior=interior, eps0=eps0, mu0=mu0,
        use_strict_quadrature=use_strict_quadrature,
    )
    c_dot_q = receiver_row_action_directional_derivative(
        band, receiver_points, point_velocity, normal_velocity, weight_velocity,
        u_dirichlet, u_neumann, system.k_exterior, use_strict_quadrature=use_strict_quadrature,
    )

    d_j_d_alpha = np.real(mu.conj() @ (b_dot - a_dot_q) + psi.conj() @ c_dot_q)
    return float(d_j_d_alpha), loss
