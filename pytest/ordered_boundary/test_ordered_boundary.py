"""Geometry-contract tests only; no BIE/PDE operator or field errors."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from ordered_boundary import (
    BoundaryValidationConfig,
    OrderedBoundary2D,
    OrderedBoundaryParameterization2D,
    PeriodicCurve2D,
    PeriodicParameterization2D,
    circle,
    validate_ordered_parameterization,
    validate_periodic_parameterization,
)


def test_multicomponent_discretization_preserves_local_grids_and_stable_ids() -> None:
    first = circle((0.0, 0.0), 1.0, component_id="left")
    second = circle((3.0, 0.0), 0.5, component_id="right")
    parameterization = OrderedBoundaryParameterization2D((first, second))
    boundary = parameterization.discretize({"left": 63, "right": 80})
    assert isinstance(parameterization, OrderedBoundaryParameterization2D)
    assert isinstance(boundary, OrderedBoundary2D)
    assert all(isinstance(component, PeriodicCurve2D) for component in boundary.components)
    assert not hasattr(boundary, "evaluator")
    assert not hasattr(boundary, "evaluate")
    assert not hasattr(boundary, "sample")
    assert parameterization.component_ids == ("left", "right")
    assert boundary.component_ids == ("left", "right")
    assert boundary.num_components == 2
    assert boundary.num_nodes == 143
    assert boundary.component_slices == (slice(0, 63), slice(63, 143))
    np.testing.assert_array_equal(boundary.component_offsets, (0, 63, 143))
    np.testing.assert_array_equal(boundary.node_component_indices[:63], 0)
    np.testing.assert_array_equal(boundary.node_component_indices[63:], 1)
    np.testing.assert_array_equal(boundary.node_local_indices[:63], np.arange(63))
    np.testing.assert_array_equal(boundary.node_local_indices[63:], np.arange(80))
    np.testing.assert_allclose(boundary.points[:63], boundary.component("left").points)
    np.testing.assert_allclose(boundary.points[63:], boundary.component("right").points)
    assert boundary.perimeter == pytest.approx(3.0 * np.pi, rel=3.0e-14)
    assert boundary.component("left").parameters[0] == 0.0
    assert boundary.component("right").parameters[0] == 0.0
    assert boundary.third_derivatives is not None
    for values in (
        boundary.parameters,
        boundary.points,
        boundary.first_derivatives,
        boundary.second_derivatives,
        boundary.third_derivatives,
        boundary.speeds,
        boundary.tangents,
        boundary.normals,
        boundary.curvatures,
        boundary.arc_length_weights,
        boundary.node_component_indices,
        boundary.node_local_indices,
        boundary.component_offsets,
    ):
        assert values is not None
        assert not values.flags.writeable


def test_boundary_report_is_json_safe_and_clearance_is_geometric() -> None:
    parameterization = OrderedBoundaryParameterization2D(
        (
            circle((0.0, 0.0), 1.0, component_id="left"),
            circle((3.0, 0.0), 0.5, component_id="right"),
        )
    )
    report = validate_ordered_parameterization(parameterization)
    assert report.valid
    assert report.minimum_intercomponent_clearance == pytest.approx(1.5, abs=2.0e-14)
    assert report.intersecting_component_pairs == ()
    assert report.nested_component_pairs == ()
    assert report.components[0].phase_anchor == (1.0, 0.0)
    assert report.components[0].source_kind == "analytic"
    assert report.components[0].projection_residual is None
    assert report.components[0].fit_residual is None
    json.dumps(report.to_dict(), allow_nan=False, sort_keys=True)

    single_report = validate_ordered_parameterization(
        OrderedBoundaryParameterization2D((circle((0.0, 0.0), 1.0, component_id="one"),))
    )
    assert single_report.minimum_intercomponent_clearance is None
    json.dumps(single_report.to_dict(), allow_nan=False)


@pytest.mark.parametrize(
    "second_center",
    [(1.5, 0.0), (2.0, 0.0)],
    ids=["overlap", "tangent"],
)
def test_intersecting_or_touching_components_are_rejected(second_center) -> None:
    parameterization = OrderedBoundaryParameterization2D(
        (
            circle((0.0, 0.0), 1.0, component_id="a"),
            circle(second_center, 1.0, component_id="b"),
        )
    )
    report = validate_ordered_parameterization(parameterization)
    assert not report.valid
    assert report.intersecting_component_pairs == (("a", "b"),)


def test_nested_components_are_reported_and_policy_is_explicit() -> None:
    parameterization = OrderedBoundaryParameterization2D(
        (
            circle((0.0, 0.0), 2.0, component_id="outer"),
            circle((0.0, 0.0), 0.5, component_id="inner"),
        )
    )
    rejected = validate_ordered_parameterization(parameterization)
    assert not rejected.valid
    assert rejected.nested_component_pairs == (("inner", "outer"),)
    accepted = validate_ordered_parameterization(
        parameterization,
        BoundaryValidationConfig(allow_nested_components=True),
    )
    assert accepted.valid
    assert accepted.nested_component_pairs == (("inner", "outer"),)


def test_clearance_threshold_is_a_solver_policy_not_hidden_geometry() -> None:
    parameterization = OrderedBoundaryParameterization2D(
        (
            circle((0.0, 0.0), 1.0, component_id="a"),
            circle((2.1, 0.0), 1.0, component_id="b"),
        )
    )
    assert validate_ordered_parameterization(parameterization).valid
    report = validate_ordered_parameterization(
        parameterization,
        BoundaryValidationConfig(minimum_intercomponent_clearance=0.11),
    )
    assert not report.valid
    assert any("minimum intercomponent clearance" in issue for issue in report.issues)


def test_smooth_self_intersection_and_double_cover_are_rejected() -> None:
    def gerono(t: np.ndarray):
        points = np.stack((np.sin(t), np.sin(t) * np.cos(t)), axis=-1)
        first = np.stack((np.cos(t), np.cos(2.0 * t)), axis=-1)
        second = np.stack((-np.sin(t), -2.0 * np.sin(2.0 * t)), axis=-1)
        third = np.stack((-np.cos(t), -4.0 * np.cos(2.0 * t)), axis=-1)
        return points, first, second, third

    def double_circle(t: np.ndarray):
        radial = np.stack((np.cos(2.0 * t), np.sin(2.0 * t)), axis=-1)
        angular = np.stack((-np.sin(2.0 * t), np.cos(2.0 * t)), axis=-1)
        return radial, 2.0 * angular, -4.0 * radial, -8.0 * angular

    for parameterization in (
        PeriodicParameterization2D("gerono", gerono),
        PeriodicParameterization2D("double", double_circle),
    ):
        report = validate_periodic_parameterization(parameterization)
        assert not report.valid
        assert report.self_intersection_count > 0


def test_open_curve_and_zero_speed_cusp_are_rejected() -> None:
    def open_evaluator(t: np.ndarray):
        points = np.stack((np.cos(t), np.sin(t) + 0.01 * t), axis=-1)
        first = np.stack((-np.sin(t), np.cos(t) + 0.01), axis=-1)
        second = np.stack((-np.cos(t), -np.sin(t)), axis=-1)
        return points, first, second

    open_report = validate_periodic_parameterization(
        PeriodicParameterization2D("open", open_evaluator)
    )
    assert not open_report.valid
    assert any("not periodic" in issue for issue in open_report.issues)

    def astroid(t: np.ndarray):
        cosine, sine = np.cos(t), np.sin(t)
        points = np.stack((cosine**3, sine**3), axis=-1)
        first = np.stack((-3.0 * cosine**2 * sine, 3.0 * sine**2 * cosine), axis=-1)
        second = np.stack(
            (6.0 * cosine * sine**2 - 3.0 * cosine**3, 6.0 * sine * cosine**2 - 3.0 * sine**3),
            axis=-1,
        )
        return points, first, second

    cusp_report = validate_periodic_parameterization(
        PeriodicParameterization2D("cusp", astroid)
    )
    assert not cusp_report.valid
    assert cusp_report.minimum_speed == pytest.approx(0.0, abs=1.0e-14)
    assert any("speed is too small" in issue for issue in cusp_report.issues)


def test_boundary_identity_and_node_count_inputs_are_strict() -> None:
    with pytest.raises(TypeError, match="node-based PeriodicCurve2D"):
        OrderedBoundary2D((circle((0.0, 0.0), 1.0, component_id="not_nodes"),))
    with pytest.raises(ValueError, match="At least one"):
        OrderedBoundaryParameterization2D(())
    with pytest.raises(ValueError, match="unique"):
        OrderedBoundaryParameterization2D(
            (
                circle((0.0, 0.0), 1.0, component_id="same"),
                circle((3.0, 0.0), 1.0, component_id="same"),
            )
        )
    parameterization = OrderedBoundaryParameterization2D(
        (circle((0.0, 0.0), 1.0, component_id="a"),)
    )
    with pytest.raises(TypeError, match="integers"):
        parameterization.discretize([32.5])
    with pytest.raises(ValueError, match="mapping mismatch"):
        parameterization.discretize({"wrong": 32})


def test_ordered_boundary_package_has_no_solver_or_oracle_dependencies() -> None:
    package = Path(__file__).resolve().parents[2] / "solvers" / "ordered_boundary"
    forbidden = {"gpr_bem_mod", "gpr_bem_kdiff", "gpr_bem_qbx", "nystrom_ref", "torch"}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        assert not imported & forbidden, f"{path.name} imports forbidden dependencies: {imported & forbidden}"
