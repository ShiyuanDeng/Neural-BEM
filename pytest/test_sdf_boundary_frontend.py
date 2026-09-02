"""Focused tests for the isolated SDF-to-ordered-boundary shared front end."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from ordered_boundary import PeriodicParameterization2D
from sdf_to_ordered_boundary.fields import (
    CallableImplicitField2D,
    CircleSDF,
    CountedImplicitField2D,
    EllipseLevelSet,
    ImplicitField2D,
    RadialFourierLevelSet,
    TorchImplicitField2D,
)
from sdf_to_ordered_boundary.frontend import (
    BoundaryTouchingContourError,
    ComponentCountError,
    FrontendConfig,
    OpenContourError,
    PolygonValidationError,
    ProjectionConfig,
    ProjectionError,
    extract_frontend_components,
    polygon_diagnostics,
    polygon_self_intersection_count,
    prepare_single_component,
    project_to_zero_set,
    resample_closed_polygon,
)


def _central_gradient(field: ImplicitField2D, points: np.ndarray, step: float = 1.0e-6) -> np.ndarray:
    columns = []
    for axis in range(2):
        offset = np.zeros_like(points)
        offset[:, axis] = step
        columns.append((field.value(points + offset) - field.value(points - offset)) / (2.0 * step))
    return np.column_stack(columns)


def test_analytic_fields_match_reference_zero_sets_and_spatial_gradients() -> None:
    circle = CircleSDF((0.2, -0.1), 0.8)
    assert isinstance(circle, ImplicitField2D)
    np.testing.assert_allclose(circle.value(np.asarray([1.0, -0.1])), 0.0, atol=2.0e-16)
    np.testing.assert_allclose(circle.gradient(np.asarray([1.0, -0.1])), (1.0, 0.0))
    assert circle.is_signed_distance

    ellipse = EllipseLevelSet((0.1, -0.2), 1.3, 0.55, rotation=0.31)
    assert not ellipse.is_signed_distance
    ellipse_reference = ellipse.reference_parameterization(component_id="ellipse-reference")
    assert isinstance(ellipse_reference, PeriodicParameterization2D)
    ellipse_points = ellipse_reference.evaluate(np.linspace(0.1, 5.9, 17)).points
    np.testing.assert_allclose(ellipse.value(ellipse_points), 0.0, rtol=0.0, atol=5.0e-16)
    np.testing.assert_allclose(
        ellipse.gradient(ellipse_points),
        _central_gradient(ellipse, ellipse_points),
        rtol=2.0e-9,
        atol=2.0e-9,
    )

    radial = RadialFourierLevelSet.star(
        (0.05, -0.08), 0.9, 0.18, 5, rotation=0.27
    )
    radial_reference = radial.reference_parameterization(component_id="star-reference")
    parameters = 2.0 * np.pi * np.arange(41) / 41
    radial_points = radial_reference.evaluate(parameters).points
    np.testing.assert_allclose(radial.value(radial_points), 0.0, rtol=0.0, atol=2.0e-15)
    np.testing.assert_allclose(
        radial.gradient(radial_points),
        _central_gradient(radial, radial_points),
        rtol=2.0e-9,
        atol=2.0e-9,
    )
    assert radial_reference.discretize(128).orientation == "counterclockwise"


def test_callable_adapter_preserves_batch_shapes_and_counted_wrapper_is_explicit() -> None:
    field = CallableImplicitField2D(
        lambda xy: np.sum(xy**2, axis=-1, keepdims=True) - 1.0,
        lambda xy: 2.0 * xy,
        name="quadratic_circle",
    )
    counted = CountedImplicitField2D(field)
    points = np.arange(12, dtype=np.float64).reshape(2, 3, 2) / 10.0
    assert counted.value(points).shape == (2, 3)
    assert counted.gradient(points).shape == (2, 3, 2)
    assert counted.counts.value_calls == 1
    assert counted.counts.value_points == 6
    assert counted.counts.gradient_calls == 1
    assert counted.counts.gradient_points == 6
    counted.reset_counts()
    assert counted.counts.value_points == 0
    with pytest.raises(ValueError, match="shape"):
        field.value(np.ones((4, 3)))


def test_optional_torch_adapter_does_not_create_a_hard_import_dependency() -> None:
    if importlib.util.find_spec("torch") is None:
        adapter = TorchImplicitField2D(lambda points: points[:, 0])
        with pytest.raises(ImportError, match="optional 'torch'"):
            adapter.value(np.asarray([[0.0, 0.0]]))
        return

    import torch

    class QuadraticCircle(torch.nn.Module):
        def forward(self, points):
            return torch.sum(points**2, dim=1, keepdim=True) - 1.0

    adapter = TorchImplicitField2D(QuadraticCircle(), dtype=torch.float64)
    points = np.asarray(((1.0, 0.0), (0.3, -0.4)))
    np.testing.assert_allclose(adapter.value(points), (0.0, -0.75), atol=2.0e-15)
    np.testing.assert_allclose(adapter.gradient(points), 2.0 * points, atol=2.0e-15)


def test_circle_frontend_is_ccw_deterministic_projected_and_immutable() -> None:
    field = CountedImplicitField2D(CircleSDF((0.0, 0.0), 1.0))
    config = FrontendConfig(
        bounds=((-1.5, -1.5), (1.5, 1.5)),
        grid_shape=(65, 65),
        projected_samples=96,
        second_resample_and_project=True,
        projection=ProjectionConfig(residual_tolerance=1.0e-13),
    )
    result = prepare_single_component(field, config)
    component = result.single_component

    assert result.num_components == 1
    assert result.grid.values.shape == (65, 65)
    assert component.component_id == "component_000"
    assert component.raw_diagnostics.orientation == "counterclockwise"
    assert component.projected_diagnostics.orientation == "counterclockwise"
    assert component.projected_diagnostics.self_intersection_count == 0
    assert len(component.projection_passes) == 2
    assert all(projection.all_converged for projection in component.projection_passes)
    assert component.projection_passes[-1].maximum_residual < 2.0e-14
    np.testing.assert_allclose(field.value(result.projected_points), 0.0, atol=2.0e-14)
    np.testing.assert_allclose(result.projected_points[0], (1.0, 0.0), atol=2.0e-13)
    assert result.parameters[0] == 0.0
    assert np.all(np.diff(result.parameters) > 0.0)
    assert result.parameters[-1] < 2.0 * np.pi
    assert result.field_counts is not None
    assert result.field_counts.value_points >= 65 * 65
    for values in (
        result.grid.x_coordinates,
        result.grid.y_coordinates,
        result.grid.values,
        component.raw_contour,
        component.initial_points,
        component.projected_points,
        component.parameters,
        component.projection_passes[-1].converged,
    ):
        assert not values.flags.writeable


def test_generic_rotated_ellipse_level_set_projects_without_sdf_gradient_assumption() -> None:
    field = EllipseLevelSet((0.1, -0.15), 1.25, 0.52, rotation=0.37)
    config = FrontendConfig(
        bounds=((-1.7, -1.4), (1.9, 1.2)),
        grid_shape=(83, 101),
        projected_samples=112,
        projection=ProjectionConfig(residual_tolerance=2.0e-13),
    )
    result = prepare_single_component(field, config)
    residual = np.abs(field.value(result.projected_points))
    gradient_norm = np.linalg.norm(field.gradient(result.projected_points), axis=1)
    assert float(np.max(residual)) < 3.0e-13
    assert float(np.ptp(gradient_norm)) > 0.5
    assert result.single_component.projected_diagnostics.signed_area > 0.0


def _two_circle_field() -> CallableImplicitField2D:
    centers = np.asarray(((-1.2, 0.0), (1.2, 0.0)), dtype=np.float64)
    radius = 0.55

    def value(points: np.ndarray) -> np.ndarray:
        distances = np.linalg.norm(points[..., None, :] - centers, axis=-1) - radius
        return np.min(distances, axis=-1)

    def gradient(points: np.ndarray) -> np.ndarray:
        relative = points[..., None, :] - centers
        distances = np.linalg.norm(relative, axis=-1)
        selected = np.argmin(distances, axis=-1)
        flat_relative = relative.reshape(-1, 2, 2)
        flat_distances = distances.reshape(-1, 2)
        flat_selected = selected.reshape(-1)
        row = np.arange(flat_selected.size)
        result = flat_relative[row, flat_selected] / flat_distances[row, flat_selected, None]
        return result.reshape(points.shape)

    return CallableImplicitField2D(value, gradient, name="two_circles", is_signed_distance=True)


def test_component_detection_retains_all_loops_and_single_entrypoint_rejects_zero_or_many() -> None:
    config = FrontendConfig(
        bounds=((-2.2, -1.0), (2.2, 1.0)),
        grid_shape=(81, 161),
        projected_samples=64,
        second_resample_and_project=False,
    )
    all_components = extract_frontend_components(_two_circle_field(), config)
    assert all_components.num_components == 2
    assert tuple(component.component_id for component in all_components.components) == (
        "component_000",
        "component_001",
    )
    assert np.mean(all_components.components[0].projected_points[:, 0]) < 0.0
    assert np.mean(all_components.components[1].projected_points[:, 0]) > 0.0
    with pytest.raises(ComponentCountError) as multiple:
        prepare_single_component(_two_circle_field(), config)
    assert multiple.value.actual == 2

    empty_field = CallableImplicitField2D(
        lambda points: np.ones(points.shape[:-1]),
        lambda points: np.zeros_like(points),
        name="empty",
    )
    empty = extract_frontend_components(empty_field, config)
    assert empty.components == ()
    with pytest.raises(ComponentCountError) as zero:
        prepare_single_component(empty_field, config)
    assert zero.value.actual == 0


def test_open_and_bounding_box_touching_contours_fail_explicitly() -> None:
    line = CallableImplicitField2D(
        lambda points: points[..., 0],
        lambda points: np.broadcast_to((1.0, 0.0), points.shape),
        name="open_vertical_line",
    )
    with pytest.raises(OpenContourError, match="open"):
        extract_frontend_components(
            line,
            FrontendConfig(
                bounds=((-1.0, -1.0), (1.0, 1.0)),
                grid_shape=(33, 33),
                projected_samples=32,
            ),
        )

    near_box = CircleSDF((0.0, 0.0), 0.95)
    with pytest.raises(BoundaryTouchingContourError, match="bounding box"):
        extract_frontend_components(
            near_box,
            FrontendConfig(
                bounds=((-1.0, -1.0), (1.0, 1.0)),
                grid_shape=(65, 65),
                projected_samples=32,
                boundary_tolerance=0.1,
            ),
        )


def test_deliberately_underresolved_grid_reports_zero_components() -> None:
    # The small off-grid circle lies strictly between all 9x9 grid nodes, so
    # marching squares must not invent a boundary from an unresolved field.
    unresolved = CircleSDF((0.125, 0.125), 0.04)
    with pytest.raises(ComponentCountError) as captured:
        prepare_single_component(
            unresolved,
            FrontendConfig(
                bounds=((-1.0, -1.0), (1.0, 1.0)),
                grid_shape=(9, 9),
                projected_samples=32,
            ),
        )
    assert captured.value.actual == 0


def test_projection_caps_steps_and_reports_near_critical_gradient_failure() -> None:
    circle = CircleSDF((0.0, 0.0), 1.0)
    projected = project_to_zero_set(
        circle,
        np.asarray(((1.2, 0.0), (0.0, 1.2))),
        grid_spacing=0.05,
        config=ProjectionConfig(
            residual_tolerance=1.0e-13,
            max_iterations=40,
            max_step_grid_fraction=0.25,
        ),
    )
    assert projected.all_converged
    assert np.all(projected.clipped_step_counts > 0)
    np.testing.assert_allclose(np.linalg.norm(projected.points, axis=1), 1.0, atol=2.0e-14)

    def cubic_value(points: np.ndarray) -> np.ndarray:
        return (np.linalg.norm(points, axis=-1) - 1.0) ** 3

    def cubic_gradient(points: np.ndarray) -> np.ndarray:
        radii = np.linalg.norm(points, axis=-1)
        radial = points / radii[..., None]
        return 3.0 * (radii - 1.0)[..., None] ** 2 * radial

    near_critical = CallableImplicitField2D(cubic_value, cubic_gradient, name="flat_cubic")
    settings = ProjectionConfig(
        residual_tolerance=1.0e-14,
        max_iterations=4,
        gradient_tolerance=1.0e-3,
        raise_on_failure=False,
    )
    failed = project_to_zero_set(
        near_critical,
        np.asarray(((1.01, 0.0),)),
        grid_spacing=0.1,
        config=settings,
    )
    assert not failed.all_converged
    assert failed.gradient_failed[0]
    with pytest.raises(ProjectionError) as error:
        project_to_zero_set(
            near_critical,
            np.asarray(((1.01, 0.0),)),
            grid_spacing=0.1,
            config=ProjectionConfig(
                residual_tolerance=1.0e-14,
                max_iterations=4,
                gradient_tolerance=1.0e-3,
                raise_on_failure=True,
            ),
        )
    assert error.value.result is not None
    assert error.value.result.gradient_failed[0]


def test_polygon_validation_rejects_self_intersection_and_chord_resampling_is_cyclic() -> None:
    crossing = np.asarray(
        ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0), (2.5, -0.5), (-0.5, -0.5))
    )
    assert polygon_self_intersection_count(crossing) > 0
    with pytest.raises(PolygonValidationError, match="intersection"):
        polygon_diagnostics(crossing, require_counterclockwise=False)

    square = np.asarray(((1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)))
    samples = resample_closed_polygon(square, 16)
    assert samples.shape == (16, 2)
    assert not np.array_equal(samples[0], samples[-1])
    lengths = np.linalg.norm(np.roll(samples, -1, axis=0) - samples, axis=1)
    np.testing.assert_allclose(lengths, lengths[0], rtol=0.0, atol=2.0e-15)
