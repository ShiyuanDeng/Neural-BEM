"""Neural signed-distance-function helpers for 2D inversion experiments."""

from __future__ import annotations

import math

import numpy as np
import torch
from skimage import measure
from torch import nn
from typing import Callable


class SineLayer(nn.Module):
    """SIREN sine layer with the initialization recommended by Sitzmann et al."""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        *,
        bias: bool = True,
        is_first: bool = False,
        omega_0: float = 30.0,
    ) -> None:
        super().__init__()
        self.in_features = int(in_features)
        self.is_first = bool(is_first)
        self.omega_0 = float(omega_0)
        self.linear = nn.Linear(in_features, out_features, bias=bias)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        with torch.no_grad():
            if self.is_first:
                bound = 1.0 / self.in_features
            else:
                bound = math.sqrt(6.0 / self.in_features) / self.omega_0
            self.linear.weight.uniform_(-bound, bound)
            if self.linear.bias is not None:
                self.linear.bias.uniform_(-bound, bound)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return torch.sin(self.omega_0 * self.linear(inputs))


class SirenSDF2D(nn.Module):
    """Minimal 2D SIREN network for signed-distance-function experiments."""

    def __init__(
        self,
        *,
        in_features: int = 2,
        hidden_features: int = 128,
        hidden_layers: int = 2,
        out_features: int = 1,
        first_omega_0: float = 30.0,
        hidden_omega_0: float = 30.0,
    ) -> None:
        super().__init__()
        if in_features != 2:
            raise ValueError("SirenSDF2D expects 2D input coordinates.")
        self.hidden_features = int(hidden_features)
        self.hidden_omega_0 = float(hidden_omega_0)
        layers: list[nn.Module] = [
            SineLayer(
                in_features,
                hidden_features,
                is_first=True,
                omega_0=first_omega_0,
            )
        ]
        for _ in range(hidden_layers):
            layers.append(
                SineLayer(
                    hidden_features,
                    hidden_features,
                    omega_0=hidden_omega_0,
                )
            )
        final_linear = nn.Linear(hidden_features, out_features)
        self._reset_final_linear(final_linear)
        layers.append(final_linear)
        self.network = nn.Sequential(*layers)

    def _reset_final_linear(self, final_linear: nn.Linear) -> None:
        with torch.no_grad():
            bound = math.sqrt(6.0 / self.hidden_features) / self.hidden_omega_0
            final_linear.weight.uniform_(-bound, bound)
            if final_linear.bias is not None:
                final_linear.bias.uniform_(-bound, bound)

    def reset_parameters(self) -> None:
        for module in self.network[:-1]:
            if hasattr(module, "reset_parameters"):
                module.reset_parameters()
        self._reset_final_linear(self.network[-1])

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        return self.network(points)

    def spatial_gradient(self, points: torch.Tensor, *, create_graph: bool = True) -> torch.Tensor:
        points_for_grad = points.clone().detach().requires_grad_(True)
        sdf = self(points_for_grad)
        grad = torch.autograd.grad(
            outputs=sdf,
            inputs=points_for_grad,
            grad_outputs=torch.ones_like(sdf),
            create_graph=create_graph,
            retain_graph=create_graph,
            only_inputs=True,
        )[0]
        return grad

    def laplacian(self, points: torch.Tensor) -> torch.Tensor:
        points_for_grad = points.clone().detach().requires_grad_(True)
        sdf = self(points_for_grad)
        grad = torch.autograd.grad(
            outputs=sdf,
            inputs=points_for_grad,
            grad_outputs=torch.ones_like(sdf),
            create_graph=True,
            retain_graph=True,
            only_inputs=True,
        )[0]
        laplace_terms = []
        for axis in range(points_for_grad.shape[1]):
            second = torch.autograd.grad(
                outputs=grad[:, axis],
                inputs=points_for_grad,
                grad_outputs=torch.ones_like(grad[:, axis]),
                create_graph=True,
                retain_graph=True,
                only_inputs=True,
            )[0][:, axis]
            laplace_terms.append(second)
        return torch.stack(laplace_terms, dim=1).sum(dim=1, keepdim=True)


def eikonal_loss(gradients: torch.Tensor) -> torch.Tensor:
    """Penalize deviation from unit gradient magnitude."""

    return ((gradients.norm(dim=1) - 1.0) ** 2).mean()


def laplacian_loss(laplacian_values: torch.Tensor) -> torch.Tensor:
    """Quadratic smoothness penalty used by the mesh-free reference paper."""

    return (laplacian_values**2).mean()


def closed_curve_node_weights(points: torch.Tensor) -> torch.Tensor:
    """Approximate arc-length quadrature weights on a closed polygonal curve."""

    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points must have shape (num_points, 2).")
    previous_points = torch.roll(points, shifts=1, dims=0)
    next_points = torch.roll(points, shifts=-1, dims=0)
    previous_length = torch.linalg.norm(points - previous_points, dim=1)
    next_length = torch.linalg.norm(next_points - points, dim=1)
    return 0.5 * (previous_length + next_length)


def polygon_signed_area(points: np.ndarray) -> float:
    """Return the signed area of a closed polygonal curve."""

    points_array = np.asarray(points, dtype=float)
    if points_array.ndim != 2 or points_array.shape[1] != 2:
        raise ValueError("points must have shape (num_points, 2).")
    x = points_array[:, 0]
    y = points_array[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def resample_closed_curve(points: np.ndarray, num_points: int) -> np.ndarray:
    """Resample a closed polygonal curve to equally spaced arc-length nodes."""

    points_array = np.asarray(points, dtype=float)
    if points_array.ndim != 2 or points_array.shape[1] != 2:
        raise ValueError("points must have shape (num_points, 2).")
    if int(num_points) < 3:
        raise ValueError("num_points must be at least 3.")
    if np.linalg.norm(points_array[0] - points_array[-1]) <= 1.0e-12:
        points_array = points_array[:-1]
    if points_array.shape[0] < 3:
        raise ValueError("At least three distinct points are required to resample a closed curve.")

    segment_vectors = np.roll(points_array, -1, axis=0) - points_array
    segment_lengths = np.linalg.norm(segment_vectors, axis=1)
    perimeter = float(np.sum(segment_lengths))
    if perimeter <= 0.0:
        raise ValueError("Closed curve perimeter must be strictly positive.")

    cumulative_length = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    extended_points = np.vstack((points_array, points_array[0]))
    sample_positions = np.linspace(0.0, perimeter, int(num_points), endpoint=False)
    x = np.interp(sample_positions, cumulative_length, extended_points[:, 0])
    y = np.interp(sample_positions, cumulative_length, extended_points[:, 1])
    return np.column_stack((x, y))


def _contour_to_polygon(
    contour: np.ndarray,
    *,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    grid_shape: tuple[int, int],
) -> np.ndarray:
    contour_array = np.asarray(contour, dtype=float)
    if contour_array.ndim != 2 or contour_array.shape[1] != 2:
        raise ValueError("contour must have shape (num_points, 2).")
    (xmin, ymin), (xmax, ymax) = bounds
    ny, nx = int(grid_shape[0]), int(grid_shape[1])
    x = xmin + (xmax - xmin) * contour_array[:, 1] / max(nx - 1, 1)
    y = ymin + (ymax - ymin) * contour_array[:, 0] / max(ny - 1, 1)
    polygon = np.column_stack((x, y))
    if np.linalg.norm(polygon[0] - polygon[-1]) <= 1.0e-12:
        polygon = polygon[:-1]
    if polygon.shape[0] < 3:
        raise ValueError("Extracted contour must contain at least three distinct points.")
    if polygon_signed_area(polygon) < 0.0:
        polygon = polygon[::-1]
    return polygon


def extract_zero_level_set_curves_from_grid(
    sdf_grid: np.ndarray,
    *,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    level: float = 0.0,
    num_points: int | None = None,
    min_abs_area: float = 0.0,
    sort_by: str = "perimeter",
) -> tuple[np.ndarray, ...]:
    """Extract all closed zero-level contours from sampled SDF values.

    The returned curves are sorted by decreasing perimeter or absolute area,
    oriented counterclockwise, and optionally resampled to a common number of
    points.
    """

    sdf_array = np.asarray(sdf_grid, dtype=float)
    if sdf_array.ndim != 2:
        raise ValueError("sdf_grid must have shape (ny, nx).")
    ny, nx = sdf_array.shape
    if ny < 2 or nx < 2:
        raise ValueError("sdf_grid must contain at least a 2x2 sample grid.")

    normalized_sort_key = sort_by.strip().lower()
    if normalized_sort_key not in {"perimeter", "area"}:
        raise ValueError("sort_by must be 'perimeter' or 'area'.")

    contours = measure.find_contours(sdf_array, float(level), positive_orientation="high")
    if not contours:
        raise ValueError("No zero-level contour was found in the sampled SDF grid.")

    polygons: list[np.ndarray] = []
    for contour in contours:
        polygon = _contour_to_polygon(
            contour,
            bounds=bounds,
            grid_shape=(ny, nx),
        )
        if abs(polygon_signed_area(polygon)) < float(min_abs_area):
            continue
        if num_points is not None:
            polygon = resample_closed_curve(polygon, int(num_points))
        polygons.append(polygon)

    if not polygons:
        raise ValueError("No zero-level contour remained after filtering.")

    if normalized_sort_key == "perimeter":
        polygons.sort(
            key=lambda polygon: float(
                np.sum(np.linalg.norm(np.roll(polygon, -1, axis=0) - polygon, axis=1))
            ),
            reverse=True,
        )
    else:
        polygons.sort(key=lambda polygon: abs(polygon_signed_area(polygon)), reverse=True)
    return tuple(polygons)


def extract_zero_level_set_polygon_from_grid(
    sdf_grid: np.ndarray,
    *,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    level: float = 0.0,
    num_points: int | None = None,
) -> np.ndarray:
    """Extract the dominant zero-level contour from sampled SDF values."""

    return extract_zero_level_set_curves_from_grid(
        sdf_grid,
        bounds=bounds,
        level=level,
        num_points=num_points,
        sort_by="perimeter",
    )[0]


def evaluate_sdf_grid(
    model: nn.Module,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample a 2D SDF model on a regular Cartesian grid."""

    ny, nx = int(grid_shape[0]), int(grid_shape[1])
    if ny < 2 or nx < 2:
        raise ValueError("grid_shape must contain at least 2 points in each direction.")
    (xmin, ymin), (xmax, ymax) = bounds
    x = torch.linspace(xmin, xmax, nx, device=device, dtype=dtype)
    y = torch.linspace(ymin, ymax, ny, device=device, dtype=dtype)
    grid_y, grid_x = torch.meshgrid(y, x, indexing="ij")
    points = torch.stack((grid_x, grid_y), dim=-1).reshape(-1, 2)
    with torch.no_grad():
        sdf = model(points).reshape(ny, nx)
    return (
        grid_x.detach().cpu().numpy(),
        grid_y.detach().cpu().numpy(),
        sdf.detach().cpu().numpy(),
    )


def extract_zero_level_set_polygon(
    model: nn.Module,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    level: float = 0.0,
    num_points: int | None = None,
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> np.ndarray:
    """Sample a 2D SDF model and extract its dominant zero-level contour."""

    _, _, sdf_grid = evaluate_sdf_grid(
        model,
        bounds,
        grid_shape=grid_shape,
        device=device,
        dtype=dtype,
    )
    return extract_zero_level_set_polygon_from_grid(
        sdf_grid,
        bounds=bounds,
        level=level,
        num_points=num_points,
    )


def extract_zero_level_set_curves(
    model: nn.Module,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    level: float = 0.0,
    num_points: int | None = None,
    min_abs_area: float = 0.0,
    sort_by: str = "perimeter",
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> tuple[np.ndarray, ...]:
    """Sample a 2D SDF model and extract all closed zero-level contours."""

    _, _, sdf_grid = evaluate_sdf_grid(
        model,
        bounds,
        grid_shape=grid_shape,
        device=device,
        dtype=dtype,
    )
    return extract_zero_level_set_curves_from_grid(
        sdf_grid,
        bounds=bounds,
        level=level,
        num_points=num_points,
        min_abs_area=min_abs_area,
        sort_by=sort_by,
    )


def extract_zero_level_set_mesh(
    model: nn.Module,
    bounds: tuple[tuple[float, float], tuple[float, float]],
    *,
    grid_shape: tuple[int, int] = (129, 129),
    level: float = 0.0,
    num_points: int | None = None,
    min_abs_area: float = 0.0,
    sort_by: str = "perimeter",
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
):
    """Sample a 2D SDF model and build a multi-surface BoundaryMesh2D."""

    from .geometry import BoundaryMesh2D

    curves = extract_zero_level_set_curves(
        model,
        bounds,
        grid_shape=grid_shape,
        level=level,
        num_points=num_points,
        min_abs_area=min_abs_area,
        sort_by=sort_by,
        device=device,
        dtype=dtype,
    )
    return BoundaryMesh2D.from_closed_curves(list(curves))


def shape_gradient_surrogate_loss(
    model: nn.Module | Callable[[torch.Tensor], torch.Tensor],
    boundary_points: torch.Tensor,
    shape_gradient: torch.Tensor,
    *,
    quadrature_weights: torch.Tensor | None = None,
    detach_normalizer: bool = True,
    epsilon: float = 1.0e-8,
) -> torch.Tensor:
    """Build the SDF surrogate whose parameter gradient matches shape calculus.

    For a boundary shape gradient ``g(x)`` on ``phi_theta(x) = 0``, the desired
    parameter gradient is

    dL/dtheta = -∫ g(x) (d phi_theta / d theta) / ||grad phi_theta|| ds.

    This function returns a scalar surrogate whose backward pass matches that
    expression when the boundary points are treated as fixed samples from the
    current interface. By default the normalizer is detached to avoid adding
    second-order terms that are outside the phase-1 coupling formula.
    """

    if boundary_points.ndim != 2 or boundary_points.shape[1] != 2:
        raise ValueError("boundary_points must have shape (num_points, 2).")
    num_points = int(boundary_points.shape[0])
    shape_gradient_values = shape_gradient.reshape(num_points, 1).to(
        device=boundary_points.device,
        dtype=boundary_points.dtype,
    )
    if quadrature_weights is None:
        quadrature = torch.ones((num_points, 1), device=boundary_points.device, dtype=boundary_points.dtype)
    else:
        quadrature = quadrature_weights.reshape(num_points, 1).to(
            device=boundary_points.device,
            dtype=boundary_points.dtype,
        )

    boundary_points_for_grad = boundary_points.detach().clone().requires_grad_(True)
    sdf_values = model(boundary_points_for_grad)
    if sdf_values.shape != (num_points, 1):
        raise ValueError("model(boundary_points) must return shape (num_points, 1).")
    spatial_gradients = torch.autograd.grad(
        outputs=sdf_values,
        inputs=boundary_points_for_grad,
        grad_outputs=torch.ones_like(sdf_values),
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
    normalizer = torch.linalg.norm(spatial_gradients, dim=1, keepdim=True).clamp_min(float(epsilon))
    if detach_normalizer:
        normalizer = normalizer.detach()
    density = -(quadrature * shape_gradient_values) / normalizer
    return torch.sum(density * sdf_values)


def sample_uniform_points(
    bounds: tuple[tuple[float, float], tuple[float, float]],
    num_points: int,
    *,
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Sample uniformly in an axis-aligned 2D box."""

    (xmin, ymin), (xmax, ymax) = bounds
    random = torch.rand((int(num_points), 2), device=device, dtype=dtype)
    scale = torch.tensor([xmax - xmin, ymax - ymin], device=device, dtype=dtype)
    shift = torch.tensor([xmin, ymin], device=device, dtype=dtype)
    return random * scale + shift


def circle_signed_distance(
    points: torch.Tensor,
    *,
    center: tuple[float, float] = (0.0, 0.0),
    radius: float = 1.0,
) -> torch.Tensor:
    """Analytic SDF of a circle, useful for phase-1 supervision and checks."""

    center_tensor = torch.tensor(center, device=points.device, dtype=points.dtype)
    return torch.linalg.norm(points - center_tensor[None, :], dim=1, keepdim=True) - float(radius)


def rectangle_signed_distance(
    points: torch.Tensor,
    *,
    center: tuple[float, float] = (0.0, 0.0),
    half_extents: tuple[float, float] = (1.0, 1.0),
) -> torch.Tensor:
    """Exact analytic SDF of an axis-aligned rectangle (a square when the two
    half-extents are equal). Unlike ``max(|x|-hw, |y|-hh)``, this is the true
    Euclidean distance in the corner regions too, not just along the edges."""

    center_tensor = torch.tensor(center, device=points.device, dtype=points.dtype)
    half_extents_tensor = torch.tensor(half_extents, device=points.device, dtype=points.dtype)
    offset = torch.abs(points - center_tensor[None, :]) - half_extents_tensor[None, :]
    outside_distance = torch.linalg.norm(torch.clamp(offset, min=0.0), dim=1, keepdim=True)
    inside_distance = torch.clamp(torch.amax(offset, dim=1, keepdim=True), max=0.0)
    return outside_distance + inside_distance


def circles_union_signed_distance(
    points: torch.Tensor,
    *,
    centers: np.ndarray | torch.Tensor,
    radii: np.ndarray | torch.Tensor,
) -> torch.Tensor:
    """Analytic SDF surrogate for the union of multiple circles."""

    centers_tensor = torch.as_tensor(centers, device=points.device, dtype=points.dtype)
    radii_tensor = torch.as_tensor(radii, device=points.device, dtype=points.dtype).reshape(-1)
    if centers_tensor.ndim != 2 or centers_tensor.shape[1] != 2:
        raise ValueError("centers must have shape (num_circles, 2).")
    if radii_tensor.shape != (centers_tensor.shape[0],):
        raise ValueError("radii must have shape (num_circles,).")
    distances = torch.linalg.norm(points[:, None, :] - centers_tensor[None, :, :], dim=2) - radii_tensor[None, :]
    return torch.min(distances, dim=1, keepdim=True).values
