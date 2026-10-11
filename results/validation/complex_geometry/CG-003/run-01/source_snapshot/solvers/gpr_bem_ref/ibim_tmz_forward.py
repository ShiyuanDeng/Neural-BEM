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
    "implicit_single_layer_normal_derivative_trace_from_band",
    "implicit_single_layer_trace_from_band",
    "implicit_single_layer_potential_from_band",
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


def implicit_single_layer_normal_derivative_trace_from_band(
    band: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    densities,
    wavenumbers,
    *,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryNormalDerivativeTraceResult:
    """Evaluate exterior/interior normal-derivative traces of the single-layer potential."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    step = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if step <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)
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
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitBoundaryNormalDerivativeTraceResult:
    """Evaluate exterior/interior normal-derivative traces of the double-layer potential."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    step = _default_trace_offset_distance(band) if offset_distance is None else float(offset_distance)
    if step <= 0.0:
        raise ValueError("offset_distance must be positive.")

    boundary_points, normals = _target_geometry_from_representation(band, resolved_backend)
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
        backend=resolved_backend,
        complex_precision=complex_precision,
    )
    hypersingular = build_implicit_hypersingular_boundary_matrix(
        band,
        wave_array,
        offset_distance=single.offset_distance,
        use_strict_quadrature=use_strict_quadrature,
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
