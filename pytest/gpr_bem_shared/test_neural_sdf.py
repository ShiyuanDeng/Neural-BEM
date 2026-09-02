from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from gpr_bem.neural_sdf import (
    SirenSDF2D,
    closed_curve_node_weights,
    circle_signed_distance,
    circles_union_signed_distance,
    eikonal_loss,
    evaluate_sdf_grid,
    extract_zero_level_set_curves,
    extract_zero_level_set_curves_from_grid,
    extract_zero_level_set_mesh,
    extract_zero_level_set_polygon,
    extract_zero_level_set_polygon_from_grid,
    laplacian_loss,
    polygon_signed_area,
    resample_closed_curve,
    sample_uniform_points,
    shape_gradient_surrogate_loss,
)


def test_circle_signed_distance_matches_expected_values() -> None:
    points = torch.tensor(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
        ],
        dtype=torch.float32,
    )
    sdf = circle_signed_distance(points, radius=1.0)
    expected = torch.tensor([[-1.0], [0.0], [1.0]], dtype=torch.float32)
    torch.testing.assert_close(sdf, expected)


def test_circles_union_signed_distance_matches_expected_values() -> None:
    points = torch.tensor(
        [
            [-0.5, 0.0],
            [0.0, 0.0],
            [0.5, 0.0],
            [1.0, 0.0],
        ],
        dtype=torch.float32,
    )
    sdf = circles_union_signed_distance(
        points,
        centers=np.array([[-0.5, 0.0], [0.75, 0.0]], dtype=float),
        radii=np.array([0.2, 0.3], dtype=float),
    )
    expected = torch.tensor([[-0.2], [0.3], [-0.05], [-0.05]], dtype=torch.float32)
    torch.testing.assert_close(sdf, expected)


def test_sample_uniform_points_stays_inside_bounds() -> None:
    points = sample_uniform_points(((-1.0, -2.0), (3.0, 4.0)), 512)
    assert points.shape == (512, 2)
    assert torch.all(points[:, 0] >= -1.0)
    assert torch.all(points[:, 0] <= 3.0)
    assert torch.all(points[:, 1] >= -2.0)
    assert torch.all(points[:, 1] <= 4.0)


def test_siren_sdf_produces_finite_values_gradients_and_laplacian() -> None:
    model = SirenSDF2D(hidden_features=32, hidden_layers=1)
    points = sample_uniform_points(((-1.0, -1.0), (1.0, 1.0)), 64)

    sdf = model(points)
    gradients = model.spatial_gradient(points)
    laplacian = model.laplacian(points)

    assert sdf.shape == (64, 1)
    assert gradients.shape == (64, 2)
    assert laplacian.shape == (64, 1)
    assert torch.isfinite(sdf).all()
    assert torch.isfinite(gradients).all()
    assert torch.isfinite(laplacian).all()
    assert torch.isfinite(eikonal_loss(gradients))
    assert torch.isfinite(laplacian_loss(laplacian))


def test_closed_curve_node_weights_sum_to_polygon_perimeter() -> None:
    square = torch.tensor(
        [
            [-1.0, -1.0],
            [1.0, -1.0],
            [1.0, 1.0],
            [-1.0, 1.0],
        ],
        dtype=torch.float32,
    )
    weights = closed_curve_node_weights(square)

    assert weights.shape == (4,)
    torch.testing.assert_close(weights.sum(), torch.tensor(8.0, dtype=torch.float32))


def test_shape_gradient_surrogate_loss_matches_linear_model_gradient() -> None:
    model = torch.nn.Linear(2, 1, bias=True)
    with torch.no_grad():
        model.weight.copy_(torch.tensor([[2.0, -1.0]], dtype=torch.float32))
        model.bias.copy_(torch.tensor([0.3], dtype=torch.float32))

    boundary_points = torch.tensor(
        [
            [0.0, 0.0],
            [1.0, 2.0],
            [-2.0, 1.0],
        ],
        dtype=torch.float32,
    )
    shape_gradient = torch.tensor([0.7, -1.1, 0.4], dtype=torch.float32)
    quadrature_weights = torch.tensor([1.0, 0.5, 1.5], dtype=torch.float32)

    surrogate = shape_gradient_surrogate_loss(
        model,
        boundary_points,
        shape_gradient,
        quadrature_weights=quadrature_weights,
    )
    surrogate.backward()

    scale = -(quadrature_weights * shape_gradient) / torch.sqrt(torch.tensor(5.0, dtype=torch.float32))
    expected_weight_grad = torch.sum(scale[:, None] * boundary_points, dim=0, keepdim=True)
    expected_bias_grad = torch.sum(scale)

    torch.testing.assert_close(model.weight.grad, expected_weight_grad)
    torch.testing.assert_close(model.bias.grad, expected_bias_grad[None])


def test_resample_closed_curve_preserves_circle_radius() -> None:
    angles = np.linspace(0.0, 2.0 * np.pi, 17, endpoint=False)
    coarse_circle = np.column_stack((0.5 + 0.2 * np.cos(angles), -0.25 + 0.2 * np.sin(angles)))
    resampled = resample_closed_curve(coarse_circle, 64)
    radius = np.linalg.norm(resampled - np.array([[0.5, -0.25]]), axis=1)

    assert resampled.shape == (64, 2)
    assert polygon_signed_area(resampled) > 0.0
    np.testing.assert_allclose(np.mean(radius), 0.2, atol=3.0e-3)


def test_extract_zero_level_set_polygon_from_grid_recovers_circle() -> None:
    xs = np.linspace(-1.0, 1.0, 129)
    ys = np.linspace(-1.0, 1.0, 129)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    sdf_grid = np.sqrt((grid_x - 0.15) ** 2 + (grid_y + 0.1) ** 2) - 0.35
    polygon = extract_zero_level_set_polygon_from_grid(
        sdf_grid,
        bounds=((-1.0, -1.0), (1.0, 1.0)),
        num_points=96,
    )
    radius = np.linalg.norm(polygon - np.array([[0.15, -0.1]]), axis=1)

    assert polygon.shape == (96, 2)
    assert polygon_signed_area(polygon) > 0.0
    np.testing.assert_allclose(np.mean(radius), 0.35, atol=4.0e-3)


def test_extract_zero_level_set_curves_from_grid_recovers_two_circles() -> None:
    xs = np.linspace(-1.0, 1.0, 193)
    ys = np.linspace(-1.0, 1.0, 193)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    sdf_left = np.sqrt((grid_x + 0.35) ** 2 + (grid_y - 0.05) ** 2) - 0.28
    sdf_right = np.sqrt((grid_x - 0.3) ** 2 + (grid_y + 0.1) ** 2) - 0.18
    sdf_grid = np.minimum(sdf_left, sdf_right)

    curves = extract_zero_level_set_curves_from_grid(
        sdf_grid,
        bounds=((-1.0, -1.0), (1.0, 1.0)),
        num_points=72,
    )

    assert len(curves) == 2
    assert curves[0].shape == (72, 2)
    assert curves[1].shape == (72, 2)
    assert polygon_signed_area(curves[0]) > 0.0
    assert polygon_signed_area(curves[1]) > 0.0

    curve_centers = [np.mean(curve, axis=0) for curve in curves]
    curve_radii = [np.mean(np.linalg.norm(curve - center[None, :], axis=1)) for curve, center in zip(curves, curve_centers)]

    np.testing.assert_allclose(curve_centers[0], np.array([-0.35, 0.05]), atol=3.0e-2)
    np.testing.assert_allclose(curve_centers[1], np.array([0.3, -0.1]), atol=3.0e-2)
    np.testing.assert_allclose(curve_radii[0], 0.28, atol=1.5e-2)
    np.testing.assert_allclose(curve_radii[1], 0.18, atol=1.5e-2)


def test_extract_zero_level_set_polygon_from_grid_returns_dominant_curve() -> None:
    xs = np.linspace(-1.0, 1.0, 193)
    ys = np.linspace(-1.0, 1.0, 193)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    sdf_large = np.sqrt((grid_x + 0.35) ** 2 + (grid_y - 0.05) ** 2) - 0.28
    sdf_small = np.sqrt((grid_x - 0.3) ** 2 + (grid_y + 0.1) ** 2) - 0.18
    sdf_grid = np.minimum(sdf_large, sdf_small)

    polygon = extract_zero_level_set_polygon_from_grid(
        sdf_grid,
        bounds=((-1.0, -1.0), (1.0, 1.0)),
        num_points=72,
    )

    center = np.mean(polygon, axis=0)
    radius = np.mean(np.linalg.norm(polygon - center[None, :], axis=1))
    np.testing.assert_allclose(center, np.array([-0.35, 0.05]), atol=3.0e-2)
    np.testing.assert_allclose(radius, 0.28, atol=1.5e-2)


def test_extract_zero_level_set_polygon_from_model_recovers_circle() -> None:
    class AnalyticCircleModel(torch.nn.Module):
        def forward(self, points: torch.Tensor) -> torch.Tensor:
            return circle_signed_distance(points, center=(0.1, -0.2), radius=0.4)

    model = AnalyticCircleModel()
    _, _, sdf_grid = evaluate_sdf_grid(model, ((-1.0, -1.0), (1.0, 1.0)), grid_shape=(129, 129))
    polygon_grid = extract_zero_level_set_polygon_from_grid(
        sdf_grid,
        bounds=((-1.0, -1.0), (1.0, 1.0)),
        num_points=80,
    )
    polygon_model = extract_zero_level_set_polygon(
        model,
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(129, 129),
        num_points=80,
    )
    radius = np.linalg.norm(polygon_model - np.array([[0.1, -0.2]]), axis=1)

    np.testing.assert_allclose(polygon_model, polygon_grid, atol=1.0e-6)
    np.testing.assert_allclose(np.mean(radius), 0.4, atol=5.0e-3)


def test_extract_zero_level_set_curves_from_model_recovers_two_circles() -> None:
    class AnalyticTwoCircleModel(torch.nn.Module):
        def forward(self, points: torch.Tensor) -> torch.Tensor:
            left = circle_signed_distance(points, center=(-0.35, 0.05), radius=0.28)
            right = circle_signed_distance(points, center=(0.3, -0.1), radius=0.18)
            return torch.minimum(left, right)

    model = AnalyticTwoCircleModel()
    curves = extract_zero_level_set_curves(
        model,
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(193, 193),
        num_points=72,
    )

    assert len(curves) == 2
    centers = [np.mean(curve, axis=0) for curve in curves]
    np.testing.assert_allclose(centers[0], np.array([-0.35, 0.05]), atol=3.0e-2)
    np.testing.assert_allclose(centers[1], np.array([0.3, -0.1]), atol=3.0e-2)


def test_extract_zero_level_set_mesh_from_model_builds_two_surface_mesh() -> None:
    class AnalyticTwoCircleModel(torch.nn.Module):
        def forward(self, points: torch.Tensor) -> torch.Tensor:
            left = circle_signed_distance(points, center=(-0.35, 0.05), radius=0.28)
            right = circle_signed_distance(points, center=(0.3, -0.1), radius=0.18)
            return torch.minimum(left, right)

    model = AnalyticTwoCircleModel()
    mesh = extract_zero_level_set_mesh(
        model,
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(193, 193),
        num_points=48,
    )

    assert mesh.num_surfaces == 2
    assert mesh.nodes.shape[1] == 2
    assert mesh.panel_surfaces.shape[0] == mesh.num_panels
