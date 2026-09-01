"""Implicit-boundary geometry helpers for mesh-free 2D SDF/BEM experiments."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Callable

import torch

__all__ = [
    "ImplicitBoundaryBand2D",
    "ImplicitBoundarySamples2D",
    "build_implicit_boundary_band",
    "build_implicit_boundary_samples",
    "compress_implicit_boundary_band",
    "cartesian_grid_points",
    "leading_order_level_set_boundary_update",
    "perfect_circle_boundary_samples",
    "project_points_to_level_set",
    "regularized_cosine_delta",
]


@dataclass(frozen=True)
class ImplicitBoundaryBand2D:
    """Narrow-band samples and implicit-boundary quadrature weights."""

    points: torch.Tensor
    sdf_values: torch.Tensor
    sdf_gradients: torch.Tensor
    grad_norm: torch.Tensor
    signed_offset: torch.Tensor
    projected_points: torch.Tensor
    normals: torch.Tensor
    curvature: torch.Tensor
    jacobian: torch.Tensor
    delta_values: torch.Tensor
    quadrature_weights: torch.Tensor
    strict_quadrature_weights: torch.Tensor
    cell_area: float
    grid_shape: tuple[int, int]
    bounds: tuple[tuple[float, float], tuple[float, float]]
    level: float
    band_half_width: float
    delta_half_width: float

    @property
    def num_samples(self) -> int:
        return int(self.points.shape[0])

    def boundary_measure(self, *, strict: bool = False) -> torch.Tensor:
        weights = self.strict_quadrature_weights if strict else self.quadrature_weights
        return torch.sum(weights)


@dataclass(frozen=True)
class ImplicitBoundarySamples2D:
    """Compressed implicit-boundary samples after merging nearby projected points."""

    points: torch.Tensor
    normals: torch.Tensor
    quadrature_weights: torch.Tensor
    strict_quadrature_weights: torch.Tensor
    merge_distance: float
    source_num_samples: int
    bounds: tuple[tuple[float, float], tuple[float, float]]
    level: float

    @property
    def num_samples(self) -> int:
        return int(self.points.shape[0])

    def boundary_measure(self, *, strict: bool = False) -> torch.Tensor:
        weights = self.strict_quadrature_weights if strict else self.quadrature_weights
        return torch.sum(weights)


def cartesian_grid_points(
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[float, float], float]:
    """Construct a regular Cartesian grid and return flattened sample points."""

    ny, nx = int(grid_shape[0]), int(grid_shape[1])
    if ny < 2 or nx < 2:
        raise ValueError("grid_shape must contain at least 2 points along each axis.")
    (xmin, ymin), (xmax, ymax) = bounds
    if not (xmax > xmin and ymax > ymin):
        raise ValueError("bounds must define a non-empty axis-aligned box.")
    x = torch.linspace(float(xmin), float(xmax), nx, device=device, dtype=dtype)
    y = torch.linspace(float(ymin), float(ymax), ny, device=device, dtype=dtype)
    grid_y, grid_x = torch.meshgrid(y, x, indexing="ij")
    points = torch.stack((grid_x, grid_y), dim=-1).reshape(-1, 2)
    hx = float((xmax - xmin) / max(nx - 1, 1))
    hy = float((ymax - ymin) / max(ny - 1, 1))
    return grid_x, grid_y, points, (hx, hy), hx * hy


def regularized_cosine_delta(
    sdf_values: torch.Tensor,
    half_width: float,
    *,
    level: float = 0.0,
) -> torch.Tensor:
    """Cosine regularized Dirac delta with compact support ``|phi-level| <= half_width``."""

    support = float(half_width)
    if support <= 0.0:
        raise ValueError("half_width must be positive.")
    shifted = sdf_values - float(level)
    delta = torch.zeros_like(shifted)
    mask = torch.abs(shifted) <= support
    if torch.any(mask):
        delta[mask] = 0.5 * (1.0 + torch.cos(torch.pi * shifted[mask] / support)) / support
    return delta


def project_points_to_level_set(
    points: torch.Tensor,
    sdf_values: torch.Tensor,
    sdf_gradients: torch.Tensor,
    *,
    level: float = 0.0,
    epsilon: float = 1.0e-8,
) -> torch.Tensor:
    """Project narrow-band points to the target level set via first-order Newton update."""

    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points must have shape (num_points, 2).")
    if sdf_gradients.shape != points.shape:
        raise ValueError("sdf_gradients must have shape (num_points, 2).")
    sdf_column = _coerce_column_vector(sdf_values, name="sdf_values")
    grad_norm_sq = torch.sum(sdf_gradients * sdf_gradients, dim=1, keepdim=True).clamp_min(float(epsilon))
    signed_offset = (sdf_column - float(level)) / grad_norm_sq
    return points - signed_offset * sdf_gradients


def build_implicit_boundary_band(
    sdf_fn: Callable[[torch.Tensor], torch.Tensor],
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    level: float = 0.0,
    band_half_width: float | None = None,
    delta_half_width: float | None = None,
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
    create_graph: bool = False,
    gradient_epsilon: float = 1.0e-8,
) -> ImplicitBoundaryBand2D:
    """Sample an SDF on a Cartesian grid and keep only the implicit-boundary narrow band."""

    _, _, points, spacing, cell_area = cartesian_grid_points(
        bounds,
        grid_shape=grid_shape,
        device=device,
        dtype=dtype,
    )
    max_spacing = max(spacing)
    delta_support = float(delta_half_width) if delta_half_width is not None else 2.5 * max_spacing
    band_support = float(band_half_width) if band_half_width is not None else delta_support
    if band_support <= 0.0 or delta_support <= 0.0:
        raise ValueError("band_half_width and delta_half_width must be positive.")
    if band_support + 1.0e-15 < delta_support:
        raise ValueError("band_half_width must be greater than or equal to delta_half_width.")

    points_for_grad = points.detach().clone().requires_grad_(True)
    sdf_values = _coerce_column_vector(sdf_fn(points_for_grad), name="sdf_values")
    sdf_gradients = torch.autograd.grad(
        outputs=sdf_values,
        inputs=points_for_grad,
        grad_outputs=torch.ones_like(sdf_values),
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
    shifted = sdf_values[:, 0] - float(level)
    band_mask = torch.abs(shifted) <= band_support
    if not torch.any(band_mask):
        raise ValueError("No sample points fell inside the implicit-boundary narrow band.")

    band_points = points_for_grad[band_mask]
    band_sdf_values = sdf_values[band_mask]
    band_gradients = sdf_gradients[band_mask]
    grad_norm_all = torch.linalg.norm(sdf_gradients, dim=1, keepdim=True).clamp_min(float(gradient_epsilon))
    grad_norm = grad_norm_all[band_mask]
    signed_offset = (band_sdf_values - float(level)) / grad_norm
    projected_points = project_points_to_level_set(
        band_points,
        band_sdf_values,
        band_gradients,
        level=level,
        epsilon=gradient_epsilon,
    )
    normals = band_gradients / grad_norm
    normals_all = sdf_gradients / grad_norm_all
    curvature_all = _divergence_of_vector_field(
        normals_all,
        points_for_grad,
        create_graph=create_graph,
    )
    curvature = curvature_all[band_mask]
    jacobian = 1.0 - signed_offset * curvature
    delta_values = regularized_cosine_delta(
        band_sdf_values,
        delta_support,
        level=level,
    )
    quadrature_weights = delta_values * grad_norm * float(cell_area)
    strict_quadrature_weights = quadrature_weights * jacobian
    if not create_graph:
        band_points = band_points.detach()
        band_sdf_values = band_sdf_values.detach()
        band_gradients = band_gradients.detach()
        grad_norm = grad_norm.detach()
        signed_offset = signed_offset.detach()
        projected_points = projected_points.detach()
        normals = normals.detach()
        curvature = curvature.detach()
        jacobian = jacobian.detach()
        delta_values = delta_values.detach()
        quadrature_weights = quadrature_weights.detach()
        strict_quadrature_weights = strict_quadrature_weights.detach()
    return ImplicitBoundaryBand2D(
        points=band_points,
        sdf_values=band_sdf_values,
        sdf_gradients=band_gradients,
        grad_norm=grad_norm,
        signed_offset=signed_offset,
        projected_points=projected_points,
        normals=normals,
        curvature=curvature,
        jacobian=jacobian,
        delta_values=delta_values,
        quadrature_weights=quadrature_weights,
        strict_quadrature_weights=strict_quadrature_weights,
        cell_area=float(cell_area),
        grid_shape=(int(grid_shape[0]), int(grid_shape[1])),
        bounds=bounds,
        level=float(level),
        band_half_width=band_support,
        delta_half_width=delta_support,
    )


def compress_implicit_boundary_band(
    band: ImplicitBoundaryBand2D,
    *,
    merge_distance: float | None = None,
    min_weight: float = 0.0,
    normal_epsilon: float = 1.0e-12,
) -> ImplicitBoundarySamples2D:
    """Merge nearby projected boundary points into a compact quadrature set."""

    merge_scale = float(merge_distance) if merge_distance is not None else float(band.delta_half_width)
    if merge_scale <= 0.0:
        raise ValueError("merge_distance must be positive.")
    minimum_weight = float(min_weight)
    if minimum_weight < 0.0:
        raise ValueError("min_weight must be non-negative.")

    # Keep the compressed set from collapsing too aggressively on dense bands.
    # The heuristic scales sublinearly with the source band size so small smoke cases stay compact,
    # while denser bands automatically retain more samples.
    target_min_samples = max(16, int(math.ceil(4.0 * math.sqrt(max(int(band.num_samples), 1)))))
    current_merge_scale = merge_scale
    compressed = None
    for _ in range(6):
        compressed = _compress_implicit_boundary_band_once(
            band,
            merge_scale=current_merge_scale,
            min_weight=minimum_weight,
            normal_epsilon=normal_epsilon,
        )
        if compressed.num_samples >= target_min_samples:
            break
        current_merge_scale *= 0.5
    assert compressed is not None
    if current_merge_scale < merge_scale:
        # Callers that size other length scales (notably the layer-potential trace
        # offset) against the *requested* merge distance would otherwise be tuned
        # against a value this function silently discarded.
        warnings.warn(
            f"compress_implicit_boundary_band reduced merge_distance from {merge_scale:.6g} "
            f"to {current_merge_scale:.6g} to retain {target_min_samples} samples; "
            "size offset_distance against samples.merge_distance, not the requested value.",
            RuntimeWarning,
            stacklevel=2,
        )
    return compressed


def _compress_implicit_boundary_band_once(
    band: ImplicitBoundaryBand2D,
    *,
    merge_scale: float,
    min_weight: float,
    normal_epsilon: float,
) -> ImplicitBoundarySamples2D:
    device = band.projected_points.device
    dtype = band.projected_points.dtype
    origin = torch.tensor(band.bounds[0], device=device, dtype=dtype)
    bin_indices = torch.round((band.projected_points - origin[None, :]) / merge_scale).to(torch.int64)
    unique_bins, inverse = torch.unique(bin_indices, dim=0, return_inverse=True)
    num_unique = int(unique_bins.shape[0])
    if num_unique == 0:
        raise ValueError("No implicit-boundary samples are available for compression.")

    weight_column = band.quadrature_weights.reshape(-1, 1)
    aggregated_weight = torch.zeros((num_unique, 1), device=device, dtype=dtype)
    aggregated_weight.index_add_(0, inverse, weight_column)
    strict_weight_column = band.strict_quadrature_weights.reshape(-1, 1)
    aggregated_strict_weight = torch.zeros((num_unique, 1), device=device, dtype=dtype)
    aggregated_strict_weight.index_add_(0, inverse, strict_weight_column)

    aggregated_points = torch.zeros((num_unique, 2), device=device, dtype=dtype)
    aggregated_points.index_add_(0, inverse, band.projected_points * weight_column)
    aggregated_points = aggregated_points / aggregated_weight.clamp_min(float(normal_epsilon))

    aggregated_normals = torch.zeros((num_unique, 2), device=device, dtype=dtype)
    aggregated_normals.index_add_(0, inverse, band.normals * weight_column)
    aggregated_normals = aggregated_normals / torch.linalg.norm(
        aggregated_normals,
        dim=1,
        keepdim=True,
    ).clamp_min(float(normal_epsilon))

    keep_mask = aggregated_weight[:, 0] > min_weight
    if not torch.any(keep_mask):
        raise ValueError("Compression removed every implicit-boundary sample.")

    return ImplicitBoundarySamples2D(
        points=aggregated_points[keep_mask],
        normals=aggregated_normals[keep_mask],
        quadrature_weights=aggregated_weight[keep_mask],
        strict_quadrature_weights=aggregated_strict_weight[keep_mask],
        merge_distance=merge_scale,
        source_num_samples=band.num_samples,
        bounds=band.bounds,
        level=band.level,
    )


def build_implicit_boundary_samples(
    sdf_fn: Callable[[torch.Tensor], torch.Tensor],
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    level: float = 0.0,
    band_half_width: float | None = None,
    delta_half_width: float | None = None,
    merge_distance: float | None = None,
    min_weight: float = 0.0,
    normal_epsilon: float = 1.0e-12,
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
    create_graph: bool = False,
    gradient_epsilon: float = 1.0e-8,
) -> ImplicitBoundarySamples2D:
    """Build and compress IBIM boundary samples in one call."""

    band = build_implicit_boundary_band(
        sdf_fn,
        bounds,
        grid_shape=grid_shape,
        level=level,
        band_half_width=band_half_width,
        delta_half_width=delta_half_width,
        device=device,
        dtype=dtype,
        create_graph=create_graph,
        gradient_epsilon=gradient_epsilon,
    )
    return compress_implicit_boundary_band(
        band,
        merge_distance=merge_distance,
        min_weight=min_weight,
        normal_epsilon=normal_epsilon,
    )


def perfect_circle_boundary_samples(
    center: tuple[float, float],
    radius: float,
    *,
    num_samples: int,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> ImplicitBoundarySamples2D:
    """Exact uniform-arclength circle nodes, in the compressed-sample format.

    Bypasses the Cartesian-grid sample / Newton-project / bin-merge pipeline
    entirely: points sit exactly on the circle at evenly spaced angles, normals
    are exact, and the trapezoidal quadrature weight is exact for a smooth
    periodic integrand (no jacobian correction needed, since offset is exactly
    zero everywhere). Drop-in replacement for a real `ImplicitBoundarySamples2D`,
    meant for isolating how much of the IBIM error floor is node placement versus
    everything downstream of it (offset, kernels, formulation).
    """

    if num_samples < 3:
        raise ValueError("num_samples must be at least 3.")
    origin = torch.tensor(center, device=device, dtype=dtype)
    theta = torch.arange(int(num_samples), device=device, dtype=dtype) * (2.0 * math.pi / int(num_samples))
    unit_radial = torch.stack((torch.cos(theta), torch.sin(theta)), dim=-1)
    points = origin[None, :] + float(radius) * unit_radial
    arc_length = 2.0 * math.pi * float(radius) / int(num_samples)
    quadrature_weights = torch.full((int(num_samples), 1), arc_length, device=device, dtype=dtype)
    return ImplicitBoundarySamples2D(
        points=points,
        normals=unit_radial,
        quadrature_weights=quadrature_weights,
        strict_quadrature_weights=quadrature_weights,
        merge_distance=arc_length,
        source_num_samples=int(num_samples),
        bounds=bounds,
        level=0.0,
    )


def leading_order_level_set_boundary_update(
    band: ImplicitBoundaryBand2D,
    phi_parameter_derivative: torch.Tensor,
    *,
    epsilon: float = 1.0e-8,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the leading-order boundary normal velocity and projected-point update.

    For a parameter ``alpha``, this uses the standard leading-order level-set
    relation on the interface samples:

    ``p_dot = -(phi_dot / |grad phi|) * n``.
    """

    phi_dot = _coerce_column_vector(phi_parameter_derivative, name="phi_parameter_derivative")
    if phi_dot.shape != band.sdf_values.shape:
        raise ValueError("phi_parameter_derivative must have the same shape as band.sdf_values.")
    grad_norm = band.grad_norm.clamp_min(float(epsilon))
    normal_velocity = -phi_dot / grad_norm
    point_directional = normal_velocity * band.normals
    return normal_velocity, point_directional


def _coerce_column_vector(values: torch.Tensor, *, name: str) -> torch.Tensor:
    if values.ndim == 1:
        return values[:, None]
    if values.ndim == 2 and values.shape[1] == 1:
        return values
    raise ValueError(f"{name} must have shape (num_points,) or (num_points, 1).")


def _divergence_of_vector_field(
    vector_field: torch.Tensor,
    points: torch.Tensor,
    *,
    create_graph: bool,
) -> torch.Tensor:
    if vector_field.ndim != 2 or vector_field.shape[1] != 2:
        raise ValueError("vector_field must have shape (num_points, 2).")
    components: list[torch.Tensor] = []
    for axis in range(2):
        derivative = torch.autograd.grad(
            outputs=vector_field[:, axis],
            inputs=points,
            grad_outputs=torch.ones_like(vector_field[:, axis]),
            create_graph=create_graph,
            retain_graph=True,
            only_inputs=True,
        )[0][:, axis : axis + 1]
        components.append(derivative)
    return components[0] + components[1]
