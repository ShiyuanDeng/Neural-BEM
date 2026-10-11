"""Mesh-free implicit-boundary forward building blocks for 2D TMz experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from .backend import AssemblyBackend, get_assembly_backend
from .ibim_geometry import ImplicitBoundaryBand2D, ImplicitBoundarySamples2D

__all__ = [
    "ImplicitLayerPotentialResult",
    "ImplicitBoundaryTraceResult",
    "ImplicitBoundaryNormalDerivativeTraceResult",
    "ImplicitBoundaryOperatorMatrixResult",
    "ImplicitBoundaryOperatorFamilyResult",
    "apply_implicit_adjoint_double_layer_boundary_operator",
    "apply_implicit_double_layer_boundary_operator",
    "apply_implicit_hypersingular_boundary_operator",
    "apply_implicit_single_layer_boundary_operator",
    "build_implicit_adjoint_double_layer_boundary_matrix",
    "build_implicit_boundary_operator_family",
    "build_implicit_double_layer_boundary_matrix",
    "build_implicit_hypersingular_boundary_matrix",
    "build_implicit_single_layer_boundary_matrix",
    "implicit_double_layer_normal_derivative_trace_from_band",
    "implicit_double_layer_trace_from_band",
    "implicit_double_layer_potential_from_band",
    "default_trace_offset_distance",
    "implicit_double_layer_normal_derivative_potential_from_band",
    "implicit_single_layer_normal_derivative_potential_from_band",
    "implicit_single_layer_normal_derivative_trace_from_band",
    "implicit_single_layer_trace_from_band",
    "implicit_single_layer_potential_from_band",
    "implicit_single_layer_source_directional_derivative_potential_from_band",
    "implicit_greens_function_mixed_directional_hessian_potential_from_band",
    "implicit_greens_function_pure_target_hessian_potential_from_band",
    "implicit_greens_function_pure_source_hessian_potential_from_band",
    "implicit_greens_function_third_derivative_two_target_one_source_potential_from_band",
    "implicit_greens_function_third_derivative_one_target_two_source_potential_from_band",
]


@dataclass(frozen=True)
class ImplicitLayerPotentialResult:
    """Dense implicit-boundary layer-potential evaluation."""

    receiver_points: object
    source_points: object
    source_normals: object | None
    quadrature_weights: object
    densities: object
    wavenumbers: object
    kernel_matrix: object
    potentials: object
    backend_name: str


@dataclass(frozen=True)
class ImplicitBoundaryTraceResult:
    """Offset-based implicit-boundary trace evaluation."""

    outside_potentials: object
    inside_potentials: object
    average_potentials: object
    jump_potentials: object
    offset_distance: float
    backend_name: str


@dataclass(frozen=True)
class ImplicitBoundaryOperatorMatrixResult:
    """Dense implicit-boundary operator matrix assembled by batched trace evaluation."""

    matrix: object
    offset_distance: float
    backend_name: str


@dataclass(frozen=True)
class ImplicitBoundaryNormalDerivativeTraceResult:
    """Offset-based normal derivative trace evaluation."""

    outside_normal_derivative: object
    inside_normal_derivative: object
    average_normal_derivative: object
    jump_normal_derivative: object
    offset_distance: float
    backend_name: str


@dataclass(frozen=True)
class ImplicitBoundaryOperatorFamilyResult:
    """Single/double-layer operator family on an implicit boundary sample set."""

    single_layer_matrix: object
    double_layer_matrix: object
    adjoint_double_layer_matrix: object
    hypersingular_matrix: object
    wavenumbers: object
    offset_distance: float
    num_boundary_samples: int
    backend_name: str


def implicit_single_layer_potential_from_band(
    receiver_points,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitLayerPotentialResult:
    """Evaluate the 2D Helmholtz single-layer potential on implicit-boundary samples."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    source_points, source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = resolved_backend.xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)

    kernel_matrix = 0.25j * resolved_backend.hankel1(0, wave_array[:, None, None] * distance[None, :, :])
    weighted_density = density_values * weights[:, None]
    potentials = resolved_backend.xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return ImplicitLayerPotentialResult(
        receiver_points=receivers,
        source_points=source_points,
        source_normals=source_normals,
        quadrature_weights=weights,
        densities=density_values,
        wavenumbers=wave_array,
        kernel_matrix=kernel_matrix,
        potentials=potentials,
        backend_name=resolved_backend.name,
    )


def implicit_double_layer_potential_from_band(
    receiver_points,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitLayerPotentialResult:
    """Evaluate the 2D Helmholtz double-layer potential on implicit-boundary samples."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    source_points, normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = resolved_backend.xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    source_factor = resolved_backend.xp.einsum("mnd,nd->mn", displacement, normals, optimize=True) / distance
    kernel_matrix = (
        0.25j
        * wave_array[:, None, None]
        * resolved_backend.hankel1(1, wave_array[:, None, None] * distance[None, :, :])
        * source_factor[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = resolved_backend.xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return ImplicitLayerPotentialResult(
        receiver_points=receivers,
        source_points=source_points,
        source_normals=normals,
        quadrature_weights=weights,
        densities=density_values,
        wavenumbers=wave_array,
        kernel_matrix=kernel_matrix,
        potentials=potentials,
        backend_name=resolved_backend.name,
    )


def implicit_single_layer_trace_from_band(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryTraceResult:
    """Evaluate exterior/interior traces of the single-layer potential via normal offsets."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    offset = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if offset <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)
    outside_points = boundary_points + offset * normals
    inside_points = boundary_points - offset * normals

    outside = implicit_single_layer_potential_from_band(
        outside_points,
        band,
        densities,
        wavenumbers,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    inside = implicit_single_layer_potential_from_band(
        inside_points,
        band,
        densities,
        wavenumbers,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    average = 0.5 * (outside + inside)
    jump = outside - inside
    return ImplicitBoundaryTraceResult(
        outside_potentials=outside,
        inside_potentials=inside,
        average_potentials=average,
        jump_potentials=jump,
        offset_distance=offset,
        backend_name=resolved_backend.name,
    )


def implicit_double_layer_trace_from_band(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryTraceResult:
    """Evaluate exterior/interior traces of the double-layer potential via normal offsets."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    offset = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if offset <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)
    outside_points = boundary_points + offset * normals
    inside_points = boundary_points - offset * normals

    outside = implicit_double_layer_potential_from_band(
        outside_points,
        band,
        densities,
        wavenumbers,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    inside = implicit_double_layer_potential_from_band(
        inside_points,
        band,
        densities,
        wavenumbers,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials
    average = 0.5 * (outside + inside)
    jump = outside - inside
    return ImplicitBoundaryTraceResult(
        outside_potentials=outside,
        inside_potentials=inside,
        average_potentials=average,
        jump_potentials=jump,
        offset_distance=offset,
        backend_name=resolved_backend.name,
    )


def apply_implicit_single_layer_boundary_operator(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Return the continuous boundary trace ``V mu`` of the single-layer potential."""

    trace = implicit_single_layer_trace_from_band(
        band,
        densities,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=backend,
        complex_precision=complex_precision,
    )
    return trace.average_potentials


def apply_implicit_double_layer_boundary_operator(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Return the principal-value boundary trace ``K mu`` of the double-layer potential."""

    trace = implicit_double_layer_trace_from_band(
        band,
        densities,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=backend,
        complex_precision=complex_precision,
    )
    return trace.average_potentials


_NORMAL_DERIVATIVE_SCHEMES = ("analytic_extrapolated", "analytic", "finite_difference")
DEFAULT_NORMAL_DERIVATIVE_SCHEME = "analytic_extrapolated"


def _normalize_normal_derivative_scheme(scheme: str | None) -> str:
    if scheme is None:
        return DEFAULT_NORMAL_DERIVATIVE_SCHEME
    name = str(scheme).strip().lower()
    if name not in _NORMAL_DERIVATIVE_SCHEMES:
        raise ValueError(
            f"normal_derivative_scheme must be one of {_NORMAL_DERIVATIVE_SCHEMES}, got {scheme!r}."
        )
    return name


def _normal_derivative_stencil(scheme: str) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Offset multipliers and extrapolation weights for an analytic normal-derivative scheme."""

    if scheme == "analytic":
        return (1,), (1.0,)
    # Lagrange extrapolation to t = 0 from derivative values at t = d, 2d, 3d.
    # Unlike differencing the potentials there is no division by d, so quadrature
    # noise is amplified by |3| + |-3| + |1| = 7 rather than by 8 / d.
    return (1, 2, 3), (3.0, -3.0, 1.0)


def implicit_single_layer_normal_derivative_potential_from_band(
    receiver_points,
    receiver_normals,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``d/dn_x`` of the single-layer potential from its analytic kernel.

    The kernel is ``dG/dn_x = -(i k / 4) H_1^(1)(k r) ((x - y) . n_x) / r``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    target_normals = _as_backend_real_array(receiver_normals, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    target_factor = xp.einsum("mnd,md->mn", displacement, target_normals, optimize=True) / distance
    argument = wave_array[:, None, None] * distance[None, :, :]
    kernel_matrix = (
        -0.25j
        * wave_array[:, None, None]
        * resolved_backend.hankel1(1, argument)
        * target_factor[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_double_layer_normal_derivative_potential_from_band(
    receiver_points,
    receiver_normals,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``d^2/dn_x dn_y`` of the Green function against a density.

    The kernel is

        (i / 4) [ k H_1^(1)(k r) (n_x . n_y) / r
                  - k^2 H_2^(1)(k r) ((x - y) . n_x)((x - y) . n_y) / r^2 ].

    ``H_2`` is formed from the recurrence ``H_2(z) = (2 / z) H_1(z) - H_0(z)`` so the
    backend only ever needs orders 0 and 1.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    target_normals = _as_backend_real_array(receiver_normals, resolved_backend)
    source_points, source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    target_factor = xp.einsum("mnd,md->mn", displacement, target_normals, optimize=True) / distance
    source_factor = xp.einsum("mnd,nd->mn", displacement, source_normals, optimize=True) / distance
    normal_dot = xp.einsum("md,nd->mn", target_normals, source_normals, optimize=True)

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    hankel_2 = 2.0 * hankel_1 / argument - hankel_0
    kernel_matrix = 0.25j * (
        wave * hankel_1 * normal_dot[None, :, :] / distance[None, :, :]
        - wave * wave * hankel_2 * (target_factor * source_factor)[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_single_layer_source_directional_derivative_potential_from_band(
    receiver_points,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_direction,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``grad_y G . v`` where ``v`` varies per *source* (column) point.

    Shape-derivative building block from ``docs/ibim_shape_derivative.md``
    S4. Structurally identical to ``implicit_double_layer_potential_from_band``
    (same kernel, ``0.25j k H_1^(1)(kr) (x-y).v / r``), except the direction
    dotted at the source is an explicit, arbitrary per-boundary-sample field
    ``source_direction`` instead of the boundary's own geometric normals.

    This is needed because ``implicit_single_layer_normal_derivative_potential_from_band``
    only supports a *row*-indexed (per-receiver) direction -- which already
    covers ``grad_x G . v`` for a receiver-side velocity, and (via
    ``grad_y G = -grad_x G``, true for any function of ``x - y``) even
    ``grad_y G . v`` when the same ``v`` is meant to apply uniformly across
    every source column for a given receiver row. Neither covers a direction
    that varies *by source column* -- which is exactly what every
    source-point-velocity term in ``docs/ibim_shape_derivative.md`` S5 needs
    (``p_dot_j`` in every block; ``n_dot_j`` in D, since
    ``d/dn_y[dG/dn_y] . n_dot_j = grad_y G . n_dot_j`` is only a *first*
    derivative -- ``dG/dn_y`` is linear in ``n_y``, so no second-derivative
    kernel is needed for that particular term).

    Verified against central differences of the raw Green's function; see
    ``docs/ibim_shape_derivative.md`` S4 and
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction = _as_backend_real_array(source_direction, resolved_backend)
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    source_factor = xp.einsum("mnd,nd->mn", displacement, direction, optimize=True) / distance
    kernel_matrix = (
        0.25j
        * wave_array[:, None, None]
        * resolved_backend.hankel1(1, wave_array[:, None, None] * distance[None, :, :])
        * source_factor[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_greens_function_mixed_directional_hessian_potential_from_band(
    receiver_points,
    target_direction,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_direction,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``d^2G/dn_x dn_y`` for two *explicit* direction fields.

    Shape-derivative building block from ``docs/ibim_shape_derivative.md``
    S4-S5. Generalizes
    ``implicit_double_layer_normal_derivative_potential_from_band``, which
    hard-codes the source-side direction to the boundary's own normals via
    ``_source_geometry_from_representation``. ``target_direction`` is
    row-indexed (one vector per receiver point); ``source_direction`` is
    column-indexed (one vector per boundary sample). Passing ``band.normals``
    as ``source_direction`` reproduces the existing function's result
    exactly -- this function exists so callers can also pass an arbitrary
    field there (e.g. a source-point velocity ``p_dot``), which the
    non-generalized function cannot do.

    Verified against central differences of the raw Green's function; see
    ``docs/ibim_shape_derivative.md`` S4 and
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    row_direction = _as_backend_real_array(target_direction, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    col_direction = _as_backend_real_array(source_direction, resolved_backend)
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    row_factor = xp.einsum("mnd,md->mn", displacement, row_direction, optimize=True) / distance
    col_factor = xp.einsum("mnd,nd->mn", displacement, col_direction, optimize=True) / distance
    normal_dot = xp.einsum("md,nd->mn", row_direction, col_direction, optimize=True)

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    hankel_2 = 2.0 * hankel_1 / argument - hankel_0
    kernel_matrix = 0.25j * (
        wave * hankel_1 * normal_dot[None, :, :] / distance[None, :, :]
        - wave * wave * hankel_2 * (row_factor * col_factor)[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_greens_function_pure_target_hessian_potential_from_band(
    receiver_points,
    target_direction_a,
    target_direction_b,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``v_a^T Hess_x(G) v_b`` for two row-indexed (per-receiver)
    direction fields -- the *pure* target-side second derivative, as opposed
    to the mixed ``d^2G/dn_x dn_y`` above.

    Shape-derivative building block from ``docs/ibim_shape_derivative.md``
    S4-S5, needed for K'/T's own-point-motion term, e.g.
    ``target_direction_a = n_i`` (the boundary's own normal),
    ``target_direction_b = p_dot_i`` (its position velocity).

    Uses the identity ``Hess_xx(G) = Hess_yy(G) = -Hess_xy(G)``, true for any
    function of ``x - y`` alone (verified numerically -- see
    ``docs/ibim_shape_derivative.md`` S4 -- both symbolically by hand and
    against a from-scratch scipy Hankel-function implementation, since a
    sign slip here would be exactly the kind of silent, plausible-looking
    error this project's own history warns about). This is therefore *not*
    a new closed form -- it is
    ``implicit_greens_function_mixed_directional_hessian_potential_from_band``'s
    formula, negated, with *both* direction factors projected using the row
    (receiver) index instead of one row- and one column-indexed. That
    single-row-index broadcast is the reason this needs its own function
    rather than a call to the mixed one: the mixed function's ``source_direction``
    argument is inherently column-indexed and cannot represent "the second
    direction at receiver row i," only "a direction at boundary column j."

    Verified against central differences of the raw Green's function; see
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    direction_a = _as_backend_real_array(target_direction_a, resolved_backend)
    direction_b = _as_backend_real_array(target_direction_b, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    factor_a = xp.einsum("mnd,md->mn", displacement, direction_a, optimize=True) / distance
    factor_b = xp.einsum("mnd,md->mn", displacement, direction_b, optimize=True) / distance
    normal_dot = xp.einsum("md,md->m", direction_a, direction_b, optimize=True)[:, None]

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    hankel_2 = 2.0 * hankel_1 / argument - hankel_0
    kernel_matrix = -0.25j * (
        wave * hankel_1 * normal_dot[None, :, :] / distance[None, :, :]
        - wave * wave * hankel_2 * (factor_a * factor_b)[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_greens_function_pure_source_hessian_potential_from_band(
    receiver_points,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_direction_a,
    source_direction_b,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``v_a^T Hess_y(G) v_b`` for two column-indexed (per-boundary-
    sample) direction fields -- the *pure* source-side second derivative.

    Mirrors ``implicit_greens_function_pure_target_hessian_potential_from_band``
    with the projection built against the column (source) index instead of
    the row (receiver) index; same ``Hess_yy(G) = -Hess_xy(G)`` identity.
    Needed for D's own-point-motion term (``docs/ibim_shape_derivative.md``
    S5), e.g. ``source_direction_a = n_j``, ``source_direction_b = p_dot_j``.

    Verified against central differences of the raw Green's function; see
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_a = _as_backend_real_array(source_direction_a, resolved_backend)
    direction_b = _as_backend_real_array(source_direction_b, resolved_backend)
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)
    factor_a = xp.einsum("mnd,nd->mn", displacement, direction_a, optimize=True) / distance
    factor_b = xp.einsum("mnd,nd->mn", displacement, direction_b, optimize=True) / distance
    normal_dot = xp.einsum("nd,nd->n", direction_a, direction_b, optimize=True)[None, :]

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    hankel_2 = 2.0 * hankel_1 / argument - hankel_0
    kernel_matrix = -0.25j * (
        wave * hankel_1 * normal_dot[None, :, :] / distance[None, :, :]
        - wave * wave * hankel_2 * (factor_a * factor_b)[None, :, :]
    )
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def _third_derivative_radial_coefficients(distance, wave, hankel_0, hankel_1):
    """``A(r)``, ``B(r)`` for the third-derivative contraction of ``G(r)``.

    ``D_u^3 g(u)_klm = A(r) e_k e_l e_m + B(r)(delta_kl e_m + delta_km e_l +
    delta_lm e_k)``, where ``g(u) = G(|u|)``. Derived by hand (three
    successive product-rule differentiations of
    ``Hess_u(g) = f''(r) ee^T + (f'(r)/r)(I - ee^T)``) and verified against a
    from-scratch scipy Hankel implementation and a triple-nested central
    difference of ``G`` itself -- see ``docs/ibim_shape_derivative.md`` S11b.
    ``f' = -(ik/4)H1``, ``f'' = -(ik^2/4)H0 + (ik/4r)H1``,
    ``f''' = (ik^3/4)H1 + (ik^2/4r)H0 - (ik/2r^2)H1``.
    """

    f1 = -0.25j * wave * hankel_1
    f2 = -0.25j * wave * wave * hankel_0 + 0.25j * wave * hankel_1 / distance
    f3 = (
        0.25j * wave ** 3 * hankel_1
        + 0.25j * wave * wave * hankel_0 / distance
        - 0.5j * wave * hankel_1 / (distance * distance)
    )
    coeff_a = f3 - 3.0 * f2 / distance + 3.0 * f1 / (distance * distance)
    coeff_b = f2 / distance - f1 / (distance * distance)
    return coeff_a, coeff_b


def implicit_greens_function_third_derivative_two_target_one_source_potential_from_band(
    receiver_points,
    target_direction_a,
    target_direction_b,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_direction,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``D_x^2 D_y^1 G`` contracted with two row-indexed and one
    column-indexed direction: ``target_direction_a``, ``target_direction_b``
    row-indexed (receiver/target side, e.g. the boundary's own normal and a
    position-velocity field), ``source_direction`` column-indexed (source
    side, e.g. the boundary's own normal).

    Shape-derivative building block for T's own-point-motion term
    (``docs/ibim_shape_derivative.md`` S5, S11a/S11b) -- a genuine *third*
    derivative of ``G``, since T is already a mixed second derivative. Uses
    ``D_x^p D_y^q G = (-1)^q D_u^{p+q} g(u)`` at ``u = x - y`` (true for any
    function of a single displacement argument), so this is
    ``-1`` times the raw third-derivative contraction of ``G`` -- the sign is
    baked into this function; callers still need T's own separate overall
    negation (``build_implicit_hypersingular_boundary_matrix`` negates the
    whole trace).

    Verified against central differences of the raw Green's function; see
    ``docs/ibim_shape_derivative.md`` S11b and
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    direction_a = _as_backend_real_array(target_direction_a, resolved_backend)
    direction_b = _as_backend_real_array(target_direction_b, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    col_direction = _as_backend_real_array(source_direction, resolved_backend)
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)

    fa = xp.einsum("mnd,md->mn", displacement, direction_a, optimize=True) / distance
    fb = xp.einsum("mnd,md->mn", displacement, direction_b, optimize=True) / distance
    fc = xp.einsum("mnd,nd->mn", displacement, col_direction, optimize=True) / distance
    ab = xp.einsum("md,md->m", direction_a, direction_b, optimize=True)[:, None]
    ac = xp.einsum("md,nd->mn", direction_a, col_direction, optimize=True)
    bc = xp.einsum("md,nd->mn", direction_b, col_direction, optimize=True)

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    coeff_a, coeff_b = _third_derivative_radial_coefficients(distance[None, :, :], wave, hankel_0, hankel_1)
    contraction = coeff_a * (fa * fb * fc)[None, :, :] + coeff_b * (
        ab[None, :, :] * fc[None, :, :] + ac[None, :, :] * fb[None, :, :] + bc[None, :, :] * fa[None, :, :]
    )
    kernel_matrix = -contraction
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_greens_function_third_derivative_one_target_two_source_potential_from_band(
    receiver_points,
    target_direction,
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_direction_a,
    source_direction_b,
    densities,
    wavenumbers,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Evaluate ``D_x^1 D_y^2 G`` contracted with one row-indexed and two
    column-indexed directions -- T's source-point-motion term. Mirrors
    ``implicit_greens_function_third_derivative_two_target_one_source_potential_from_band``;
    ``D_x^1 D_y^2 G = (-1)^2 D_u^3 g = +D_u^3 g`` (no sign flip here, per the
    same ``(-1)^q`` rule -- q=2 source-side derivatives this time).

    Verified against central differences of the raw Green's function; see
    ``docs/ibim_shape_derivative.md`` S11b and
    ``pytest/gpr_bem_mod/test_ibim_shape_derivative_kernels.py``.
    """

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    xp = resolved_backend.xp
    receivers = _as_backend_real_array(receiver_points, resolved_backend)
    row_direction = _as_backend_real_array(target_direction, resolved_backend)
    source_points, _source_normals, weights = _source_geometry_from_representation(
        band,
        resolved_backend,
        use_strict_quadrature=use_strict_quadrature,
    )
    direction_a = _as_backend_real_array(source_direction_a, resolved_backend)
    direction_b = _as_backend_real_array(source_direction_b, resolved_backend)
    density_values, density_is_vector = _as_backend_complex_density_array(densities, resolved_backend)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)

    displacement = receivers[:, None, :] - source_points[None, :, :]
    distance = xp.linalg.norm(displacement, axis=2)
    _validate_non_singular_distance(distance, resolved_backend)

    fr = xp.einsum("mnd,md->mn", displacement, row_direction, optimize=True) / distance
    fa = xp.einsum("mnd,nd->mn", displacement, direction_a, optimize=True) / distance
    fb = xp.einsum("mnd,nd->mn", displacement, direction_b, optimize=True) / distance
    ra = xp.einsum("md,nd->mn", row_direction, direction_a, optimize=True)
    rb = xp.einsum("md,nd->mn", row_direction, direction_b, optimize=True)
    ab = xp.einsum("nd,nd->n", direction_a, direction_b, optimize=True)[None, :]

    wave = wave_array[:, None, None]
    argument = wave * distance[None, :, :]
    hankel_0 = resolved_backend.hankel1(0, argument)
    hankel_1 = resolved_backend.hankel1(1, argument)
    coeff_a, coeff_b = _third_derivative_radial_coefficients(distance[None, :, :], wave, hankel_0, hankel_1)
    contraction = coeff_a * (fr * fa * fb)[None, :, :] + coeff_b * (
        ra[None, :, :] * fb[None, :, :] + rb[None, :, :] * fa[None, :, :] + ab[None, :, :] * fr[None, :, :]
    )
    kernel_matrix = contraction
    weighted_density = density_values * weights[:, None]
    potentials = xp.einsum("fmn,nr->fmr", kernel_matrix, weighted_density, optimize=True)
    if density_is_vector:
        potentials = potentials[:, :, 0]
    return potentials


def implicit_single_layer_normal_derivative_trace_from_band(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryNormalDerivativeTraceResult:
    """Evaluate exterior/interior normal-derivative traces of the single-layer potential."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    scheme = _normalize_normal_derivative_scheme(normal_derivative_scheme)
    step = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if step <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)

    if scheme != "finite_difference":
        multipliers, coefficients = _normal_derivative_stencil(scheme)
        outside_derivative = None
        inside_derivative = None
        for multiplier, coefficient in zip(multipliers, coefficients):
            outside_term = coefficient * implicit_single_layer_normal_derivative_potential_from_band(
                boundary_points + (multiplier * step) * normals,
                normals,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            )
            inside_term = coefficient * implicit_single_layer_normal_derivative_potential_from_band(
                boundary_points - (multiplier * step) * normals,
                normals,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            )
            outside_derivative = outside_term if outside_derivative is None else outside_derivative + outside_term
            inside_derivative = inside_term if inside_derivative is None else inside_derivative + inside_term
        return ImplicitBoundaryNormalDerivativeTraceResult(
            outside_normal_derivative=outside_derivative,
            inside_normal_derivative=inside_derivative,
            average_normal_derivative=0.5 * (outside_derivative + inside_derivative),
            jump_normal_derivative=outside_derivative - inside_derivative,
            offset_distance=step,
            backend_name=resolved_backend.name,
        )

    outside_samples = []
    inside_samples = []
    for multiplier in (1, 2, 3):
        outside_points = boundary_points + (multiplier * step) * normals
        inside_points = boundary_points - (multiplier * step) * normals
        outside_samples.append(
            implicit_single_layer_potential_from_band(
                outside_points,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            ).potentials
        )
        inside_samples.append(
            implicit_single_layer_potential_from_band(
                inside_points,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            ).potentials
        )

    outside_derivative = _one_sided_normal_derivative(outside_samples, step, from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, step, from_inside=True)
    average_derivative = 0.5 * (outside_derivative + inside_derivative)
    jump_derivative = outside_derivative - inside_derivative
    return ImplicitBoundaryNormalDerivativeTraceResult(
        outside_normal_derivative=outside_derivative,
        inside_normal_derivative=inside_derivative,
        average_normal_derivative=average_derivative,
        jump_normal_derivative=jump_derivative,
        offset_distance=step,
        backend_name=resolved_backend.name,
    )


def implicit_double_layer_normal_derivative_trace_from_band(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryNormalDerivativeTraceResult:
    """Evaluate exterior/interior normal-derivative traces of the double-layer potential."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    scheme = _normalize_normal_derivative_scheme(normal_derivative_scheme)
    step = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if step <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)

    if scheme != "finite_difference":
        multipliers, coefficients = _normal_derivative_stencil(scheme)
        outside_derivative = None
        inside_derivative = None
        for multiplier, coefficient in zip(multipliers, coefficients):
            outside_term = coefficient * implicit_double_layer_normal_derivative_potential_from_band(
                boundary_points + (multiplier * step) * normals,
                normals,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            )
            inside_term = coefficient * implicit_double_layer_normal_derivative_potential_from_band(
                boundary_points - (multiplier * step) * normals,
                normals,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            )
            outside_derivative = outside_term if outside_derivative is None else outside_derivative + outside_term
            inside_derivative = inside_term if inside_derivative is None else inside_derivative + inside_term
        return ImplicitBoundaryNormalDerivativeTraceResult(
            outside_normal_derivative=outside_derivative,
            inside_normal_derivative=inside_derivative,
            average_normal_derivative=0.5 * (outside_derivative + inside_derivative),
            jump_normal_derivative=outside_derivative - inside_derivative,
            offset_distance=step,
            backend_name=resolved_backend.name,
        )

    outside_samples = []
    inside_samples = []
    for multiplier in (1, 2, 3):
        outside_points = boundary_points + (multiplier * step) * normals
        inside_points = boundary_points - (multiplier * step) * normals
        outside_samples.append(
            implicit_double_layer_potential_from_band(
                outside_points,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            ).potentials
        )
        inside_samples.append(
            implicit_double_layer_potential_from_band(
                inside_points,
                band,
                densities,
                wavenumbers,
                use_strict_quadrature=use_strict_quadrature,
                backend=resolved_backend,
                complex_precision=complex_precision,
            ).potentials
        )

    outside_derivative = _one_sided_normal_derivative(outside_samples, step, from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, step, from_inside=True)
    average_derivative = 0.5 * (outside_derivative + inside_derivative)
    jump_derivative = outside_derivative - inside_derivative
    return ImplicitBoundaryNormalDerivativeTraceResult(
        outside_normal_derivative=outside_derivative,
        inside_normal_derivative=inside_derivative,
        average_normal_derivative=average_derivative,
        jump_normal_derivative=jump_derivative,
        offset_distance=step,
        backend_name=resolved_backend.name,
    )


def apply_implicit_adjoint_double_layer_boundary_operator(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Return the principal-value boundary trace ``K' mu``."""

    trace = implicit_single_layer_normal_derivative_trace_from_band(
        band,
        densities,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=backend,
        complex_precision=complex_precision,
    )
    return trace.average_normal_derivative


def apply_implicit_hypersingular_boundary_operator(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
):
    """Return the hypersingular boundary operator ``W`` via offset normal differentiation."""

    trace = implicit_double_layer_normal_derivative_trace_from_band(
        band,
        densities,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=backend,
        complex_precision=complex_precision,
    )
    return -trace.average_normal_derivative


def build_implicit_single_layer_boundary_matrix(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryOperatorMatrixResult:
    """Assemble a dense implicit-boundary single-layer operator matrix ``V``."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    identity = _identity_density_matrix(_num_boundary_samples(band), resolved_backend)
    trace = implicit_single_layer_trace_from_band(
        band,
        identity,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    return ImplicitBoundaryOperatorMatrixResult(
        matrix=trace.average_potentials,
        offset_distance=trace.offset_distance,
        backend_name=trace.backend_name,
    )


def build_implicit_double_layer_boundary_matrix(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryOperatorMatrixResult:
    """Assemble a dense implicit-boundary double-layer operator matrix ``K``."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    identity = _identity_density_matrix(_num_boundary_samples(band), resolved_backend)
    trace = implicit_double_layer_trace_from_band(
        band,
        identity,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    return ImplicitBoundaryOperatorMatrixResult(
        matrix=trace.average_potentials,
        offset_distance=trace.offset_distance,
        backend_name=trace.backend_name,
    )


def build_implicit_adjoint_double_layer_boundary_matrix(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryOperatorMatrixResult:
    """Assemble a dense implicit-boundary adjoint double-layer matrix ``K'``."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    identity = _identity_density_matrix(_num_boundary_samples(band), resolved_backend)
    trace = implicit_single_layer_normal_derivative_trace_from_band(
        band,
        identity,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    return ImplicitBoundaryOperatorMatrixResult(
        matrix=trace.average_normal_derivative,
        offset_distance=trace.offset_distance,
        backend_name=trace.backend_name,
    )


def build_implicit_hypersingular_boundary_matrix(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryOperatorMatrixResult:
    """Assemble a dense implicit-boundary hypersingular matrix ``W``."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    identity = _identity_density_matrix(_num_boundary_samples(band), resolved_backend)
    trace = implicit_double_layer_normal_derivative_trace_from_band(
        band,
        identity,
        wavenumbers,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    return ImplicitBoundaryOperatorMatrixResult(
        matrix=-trace.average_normal_derivative,
        offset_distance=trace.offset_distance,
        backend_name=trace.backend_name,
    )


def build_implicit_boundary_operator_family(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    normal_derivative_scheme: str | None = None,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryOperatorFamilyResult:
    """Assemble the implicit-boundary single/double-layer operator family."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    wave_array = _as_backend_complex_wavenumbers(wavenumbers, resolved_backend)
    single = build_implicit_single_layer_boundary_matrix(
        band,
        wave_array,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    double = build_implicit_double_layer_boundary_matrix(
        band,
        wave_array,
        offset_distance=single.offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    adjoint_double = build_implicit_adjoint_double_layer_boundary_matrix(
        band,
        wave_array,
        offset_distance=single.offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    hypersingular = build_implicit_hypersingular_boundary_matrix(
        band,
        wave_array,
        offset_distance=single.offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    return ImplicitBoundaryOperatorFamilyResult(
        single_layer_matrix=single.matrix,
        double_layer_matrix=double.matrix,
        adjoint_double_layer_matrix=adjoint_double.matrix,
        hypersingular_matrix=hypersingular.matrix,
        wavenumbers=wave_array,
        offset_distance=single.offset_distance,
        num_boundary_samples=_num_boundary_samples(band),
        backend_name=single.backend_name,
    )


def _resolve_backend(backend: str | AssemblyBackend, *, complex_precision: str) -> AssemblyBackend:
    if isinstance(backend, AssemblyBackend):
        return backend
    return get_assembly_backend(str(backend), complex_precision=complex_precision)


def _as_backend_real_array(values, backend: AssemblyBackend):
    tensor = _as_torch_tensor(values)
    if tensor is not None:
        return _torch_to_backend_array(tensor, backend, complex_output=False)
    return backend.asreal(values)


def _as_backend_real_vector(values, backend: AssemblyBackend):
    array = _as_backend_real_array(values, backend)
    if array.ndim == 2 and array.shape[1] == 1:
        return array[:, 0]
    if array.ndim != 1:
        raise ValueError("Expected a one-dimensional real vector.")
    return array


def _as_backend_complex_density_array(values, backend: AssemblyBackend):
    tensor = _as_torch_tensor(values)
    if tensor is not None:
        array = _torch_to_backend_array(tensor, backend, complex_output=True)
    else:
        array = backend.ascomplex(values)
    if array.ndim == 1:
        return array[:, None], True
    if array.ndim == 2:
        return array, array.shape[1] == 1
    raise ValueError("Expected a complex density array of shape (n,) or (n, nrhs).")


def _as_backend_complex_wavenumbers(values, backend: AssemblyBackend):
    tensor = _as_torch_tensor(values)
    if tensor is not None:
        array = _torch_to_backend_array(tensor, backend, complex_output=True)
    else:
        array = backend.ascomplex(np.atleast_1d(values))
    if array.ndim == 0:
        return array.reshape(1)
    if array.ndim != 1:
        raise ValueError("wavenumbers must be scalar or one-dimensional.")
    return array


def _as_torch_tensor(values) -> torch.Tensor | None:
    if isinstance(values, torch.Tensor):
        return values.detach()
    return None


def _torch_to_backend_array(
    tensor: torch.Tensor,
    backend: AssemblyBackend,
    *,
    complex_output: bool,
):
    if backend.name == "cupy":
        import cupy as cp

        contiguous = tensor.detach().contiguous()
        if contiguous.is_cuda:
            array = cp.from_dlpack(contiguous)
        else:
            host = contiguous.cpu().numpy()
            array = cp.asarray(host)
        return array.astype(backend.complex_dtype if complex_output else backend.real_dtype, copy=False)

    host = tensor.detach().cpu().numpy()
    return np.asarray(host, dtype=backend.complex_dtype if complex_output else backend.real_dtype)


def _validate_non_singular_distance(distance, backend: AssemblyBackend) -> None:
    min_distance = float(backend.to_host(backend.xp.min(distance)))
    if min_distance <= 1.0e-10:
        raise ValueError("Receiver points must stay away from the implicit boundary samples for direct evaluation.")


def default_trace_offset_distance(band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D) -> float:
    """Public wrapper over the offset heuristic, for callers that rescale it."""

    return _default_trace_offset_distance(band)


def _default_trace_offset_distance(band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D) -> float:
    if isinstance(band, ImplicitBoundaryBand2D):
        return max(0.1 * float(band.delta_half_width), 0.25 * float(np.sqrt(band.cell_area)))
    # Validated against the exact Mie solution for a penetrable circle: the accuracy
    # valley sits at 1.5-2.5 x merge_distance. Below ~1x the one-sided traces are
    # evaluated too close to the layer and the error is systematic (it does not fall
    # under grid refinement); beyond ~4x the offset itself dominates.
    return 2.0 * float(band.merge_distance)


def _source_geometry_from_representation(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    backend: AssemblyBackend,
    *,
    use_strict_quadrature: bool = False,
):
    weight_attr = "strict_quadrature_weights" if use_strict_quadrature else "quadrature_weights"
    if isinstance(band, ImplicitBoundarySamples2D):
        return (
            _as_backend_real_array(band.points, backend),
            _as_backend_real_array(band.normals, backend),
            _as_backend_real_vector(getattr(band, weight_attr), backend),
        )
    return (
        _as_backend_real_array(band.projected_points, backend),
        _as_backend_real_array(band.normals, backend),
        _as_backend_real_vector(getattr(band, weight_attr), backend),
    )


def _target_geometry_from_representation(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    backend: AssemblyBackend,
):
    if isinstance(band, ImplicitBoundarySamples2D):
        return _as_backend_real_array(band.points, backend), _as_backend_real_array(band.normals, backend)
    return _as_backend_real_array(band.projected_points, backend), _as_backend_real_array(band.normals, backend)


def _num_boundary_samples(band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D) -> int:
    return int(band.num_samples)


def _identity_density_matrix(num_samples: int, backend: AssemblyBackend):
    if backend.name == "cupy":
        return backend.xp.eye(num_samples, dtype=backend.complex_dtype)
    return np.eye(num_samples, dtype=backend.complex_dtype)


def _one_sided_normal_derivative(sample_values: list[object], step: float, *, from_inside: bool):
    if len(sample_values) != 3:
        raise ValueError("sample_values must contain potentials at offsets h, 2h, and 3h.")
    sign = 1.0 if from_inside else -1.0
    return sign * (5.0 * sample_values[0] - 8.0 * sample_values[1] + 3.0 * sample_values[2]) / (2.0 * step)
