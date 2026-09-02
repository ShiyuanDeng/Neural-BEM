from __future__ import annotations

import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from gpr_bem.ibim_geometry import (
    build_implicit_boundary_band,
    build_implicit_boundary_samples,
    compress_implicit_boundary_band,
    leading_order_level_set_boundary_update,
    project_points_to_level_set,
    regularized_cosine_delta,
)
from gpr_bem.neural_sdf import circle_signed_distance, circles_union_signed_distance


def test_regularized_cosine_delta_has_compact_support() -> None:
    sdf_values = torch.tensor([-0.25, -0.1, 0.0, 0.1, 0.25], dtype=torch.float64)
    delta = regularized_cosine_delta(sdf_values, half_width=0.1)

    expected = torch.tensor([0.0, 0.0, 10.0, 0.0, 0.0], dtype=torch.float64)
    torch.testing.assert_close(delta, expected)


def test_project_points_to_level_set_recovers_circle_boundary() -> None:
    center = (0.15, -0.2)
    radius = 0.35
    points = torch.tensor(
        [
            [0.15 + 0.47, -0.2],
            [0.15 - 0.52, -0.2],
            [0.15, -0.2 + 0.61],
            [0.15 + 0.31, -0.2 + 0.31],
        ],
        dtype=torch.float64,
    )
    points_for_grad = points.clone().detach().requires_grad_(True)
    sdf_values = circle_signed_distance(points_for_grad, center=center, radius=radius)
    sdf_gradients = torch.autograd.grad(
        outputs=sdf_values,
        inputs=points_for_grad,
        grad_outputs=torch.ones_like(sdf_values),
        create_graph=False,
        retain_graph=False,
        only_inputs=True,
    )[0]

    projected = project_points_to_level_set(points_for_grad, sdf_values, sdf_gradients)
    residual = circle_signed_distance(projected, center=center, radius=radius)

    assert projected.shape == points.shape
    torch.testing.assert_close(residual, torch.zeros_like(residual), atol=1.0e-10, rtol=0.0)


def test_build_implicit_boundary_band_circle_projection_normals_and_measure() -> None:
    center = (0.12, -0.08)
    radius = 0.31
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )

    projected_residual = circle_signed_distance(band.projected_points, center=center, radius=radius)
    radial_vectors = band.projected_points - torch.tensor(center, dtype=torch.float64)[None, :]
    radial_normals = radial_vectors / torch.linalg.norm(radial_vectors, dim=1, keepdim=True)
    alignment = torch.sum(radial_normals * band.normals, dim=1)
    expected_measure = 2.0 * math.pi * radius

    assert band.num_samples > 0
    assert torch.max(torch.abs(projected_residual)).item() < 5.0e-5
    assert torch.min(alignment).item() > 0.999
    assert math.isclose(band.boundary_measure().item(), expected_measure, rel_tol=0.025, abs_tol=2.5e-2)


def test_build_implicit_boundary_band_circle_curvature_and_jacobian_match_analytic_values() -> None:
    center = (0.12, -0.08)
    radius = 0.31
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )

    expected_curvature = torch.full_like(band.curvature, 1.0 / radius)
    expected_jacobian = 1.0 - band.signed_offset * expected_curvature

    curvature_relative_error = torch.mean(torch.abs(band.curvature - expected_curvature) / expected_curvature).item()
    jacobian_max_error = torch.max(torch.abs(band.jacobian - expected_jacobian)).item()

    assert curvature_relative_error < 4.0e-2
    assert jacobian_max_error < 6.0e-3
    assert math.isclose(band.boundary_measure(strict=True).item(), 2.0 * math.pi * radius, rel_tol=0.02, abs_tol=1.0e-2)


def test_build_implicit_boundary_band_three_circle_measure_matches_total_perimeter() -> None:
    centers = np.array([[0.3, 0.5], [0.5, 0.5], [0.7, 0.5]], dtype=float)
    radii = np.array([0.05, 0.05, 0.05], dtype=float)
    band = build_implicit_boundary_band(
        lambda points: circles_union_signed_distance(points, centers=centers, radii=radii),
        ((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(385, 385),
        dtype=torch.float64,
    )

    projected_residual = circles_union_signed_distance(band.projected_points, centers=centers, radii=radii)
    expected_measure = float(np.sum(2.0 * math.pi * radii))

    assert band.num_samples > 0
    assert torch.max(torch.abs(projected_residual)).item() < 2.0e-4
    assert math.isclose(band.boundary_measure().item(), expected_measure, rel_tol=0.05, abs_tol=3.0e-2)


def test_build_implicit_boundary_samples_three_circle_smoke_has_sufficient_density_and_stable_weights() -> None:
    centers = np.array([[0.3, 0.5], [0.5, 0.5], [0.7, 0.5]], dtype=float)
    radii = np.array([0.05, 0.05, 0.05], dtype=float)
    samples = build_implicit_boundary_samples(
        lambda points: circles_union_signed_distance(points, centers=centers, radii=radii),
        ((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(65, 65),
        band_half_width=0.03,
        delta_half_width=0.02,
        merge_distance=0.02,
        dtype=torch.float64,
    )

    expected_measure = float(np.sum(2.0 * math.pi * radii))
    assert samples.num_samples >= 80
    assert math.isclose(samples.boundary_measure().item(), expected_measure, rel_tol=0.05, abs_tol=3.0e-2)
    assert math.isclose(samples.boundary_measure(strict=True).item(), expected_measure, rel_tol=0.05, abs_tol=3.0e-2)


def test_build_implicit_boundary_samples_matches_build_then_compress() -> None:
    bounds = ((0.0, 0.0), (1.0, 1.0))
    kwargs = dict(
        grid_shape=(193, 193),
        dtype=torch.float64,
        band_half_width=0.02,
        delta_half_width=0.015,
        merge_distance=0.01,
    )
    direct = build_implicit_boundary_samples(
        lambda points: circle_signed_distance(points, center=(0.5, 0.5), radius=0.2),
        bounds,
        **kwargs,
    )
    staged = compress_implicit_boundary_band(
        build_implicit_boundary_band(
            lambda points: circle_signed_distance(points, center=(0.5, 0.5), radius=0.2),
            bounds,
            grid_shape=kwargs["grid_shape"],
            dtype=kwargs["dtype"],
            band_half_width=kwargs["band_half_width"],
            delta_half_width=kwargs["delta_half_width"],
        ),
        merge_distance=kwargs["merge_distance"],
    )
    assert direct.num_samples == staged.num_samples
    torch.testing.assert_close(direct.points, staged.points)
    torch.testing.assert_close(direct.normals, staged.normals)
    torch.testing.assert_close(direct.quadrature_weights, staged.quadrature_weights)
    torch.testing.assert_close(direct.strict_quadrature_weights, staged.strict_quadrature_weights)


def test_leading_order_level_set_boundary_update_matches_circle_radius_motion() -> None:
    radius = 0.31
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=(0.0, 0.0), radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    phi_radius = -torch.ones_like(band.sdf_values)
    normal_velocity, point_directional = leading_order_level_set_boundary_update(band, phi_radius)

    torch.testing.assert_close(normal_velocity, torch.ones_like(normal_velocity), rtol=0.0, atol=1.0e-12)
    torch.testing.assert_close(point_directional, band.normals, rtol=0.0, atol=1.0e-12)


def test_boundary_measure_retains_gradient_with_respect_to_circle_radius() -> None:
    radius = torch.tensor(0.27, dtype=torch.float64, requires_grad=True)
    center = torch.tensor([0.05, -0.1], dtype=torch.float64)

    def sdf_fn(points: torch.Tensor) -> torch.Tensor:
        return torch.linalg.norm(points - center[None, :], dim=1, keepdim=True) - radius

    band = build_implicit_boundary_band(
        sdf_fn,
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
        create_graph=True,
    )
    measure = band.boundary_measure()
    measure.backward()

    assert radius.grad is not None
    assert math.isclose(measure.item(), 2.0 * math.pi * radius.detach().item(), rel_tol=0.03, abs_tol=2.5e-2)
    assert math.isclose(radius.grad.item(), 2.0 * math.pi, rel_tol=0.08, abs_tol=2.5e-1)


def test_compress_implicit_boundary_band_preserves_measure_and_reduces_samples() -> None:
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=(0.1, -0.05), radius=0.3),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    compressed = compress_implicit_boundary_band(band)

    assert compressed.num_samples < band.num_samples
    assert compressed.num_samples > 0
    assert math.isclose(
        compressed.boundary_measure().item(),
        band.boundary_measure().item(),
        rel_tol=5.0e-4,
        abs_tol=5.0e-5,
    )
    assert math.isclose(
        compressed.boundary_measure(strict=True).item(),
        band.boundary_measure(strict=True).item(),
        rel_tol=5.0e-4,
        abs_tol=5.0e-5,
    )
