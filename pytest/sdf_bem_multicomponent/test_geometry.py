"""Focused tests for the isolated multi-component geometry seam."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import OrderedBoundary2D, OrderedBoundaryParameterization2D
from sdf_bem_multicomponent import (
    CircleUnionSDF2D,
    MultiComponentOrderedSDFGeometryConfig,
    MultiComponentOrderedSDFGeometryError,
    build_multicomponent_ordered_sdf_geometry,
)


CENTERS = np.array(((0.365, 0.515), (0.635, 0.485)), dtype=np.float64)
RADII = np.array((0.057, 0.039), dtype=np.float64)
EXACT_CLEARANCE = float(np.linalg.norm(CENTERS[1] - CENTERS[0]) - np.sum(RADII))


AUTO_CONFIG = MultiComponentOrderedSDFGeometryConfig(
    bounds=((0.20, 0.25), (0.80, 0.75)),
    grid_shape=(81, 97),
    projected_samples=24,
    bandwidth=3,
    num_nodes=24,
    arclength_dense_resolution=64,
    validation_resolution=64,
    minimum_intercomponent_clearance=0.04,
)


@pytest.fixture(scope="module")
def two_circle_config() -> MultiComponentOrderedSDFGeometryConfig:
    return MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.20, 0.30), (0.80, 0.70)),
        expected_num_components=2,
        grid_shape=(81, 121),
        projected_samples=32,
        bandwidth=4,
        num_nodes=(32, 40),
        arclength_dense_resolution=64,
        validation_resolution=64,
        minimum_intercomponent_clearance=0.15,
    )


@pytest.fixture(scope="module")
def two_circle_build(two_circle_config: MultiComponentOrderedSDFGeometryConfig):
    # Primitive order is intentionally right-to-left.  Extracted component IDs
    # must still follow the frontend's canonical spatial order.
    model = CircleUnionSDF2D(centers=CENTERS[::-1], radii=RADII[::-1])
    return build_multicomponent_ordered_sdf_geometry(model, two_circle_config)


def test_circle_union_is_negative_inside_and_has_trainable_geometry() -> None:
    model = CircleUnionSDF2D(centers=CENTERS, radii=RADII)
    points = torch.as_tensor(
        np.array(
            [
                CENTERS[0],
                CENTERS[0] + (RADII[0], 0.0),
                (0.5, 0.7),
            ],
            dtype=np.float64,
        ),
        dtype=torch.float64,
    )
    values = model(points).detach().cpu().numpy().reshape(-1)

    assert values[0] == pytest.approx(-RADII[0], abs=2.0e-15)
    assert values[1] == pytest.approx(0.0, abs=2.0e-15)
    assert values[2] > 0.0
    assert model.num_components == 2
    assert tuple(model.parameters()) == (model.centers, model.log_radii)
    assert model.geometry_dict == pytest.approx(
        {
            "primitive_000.center_x": CENTERS[0, 0],
            "primitive_000.center_y": CENTERS[0, 1],
            "primitive_000.radius": RADII[0],
            "primitive_001.center_x": CENTERS[1, 0],
            "primitive_001.center_y": CENTERS[1, 1],
            "primitive_001.radius": RADII[1],
        }
    )
    with pytest.raises(ValueError, match="must be real-valued"):
        CircleUnionSDF2D(centers=((0.5 + 0.0j, 0.5),), radii=(0.05,))


def test_reversed_primitives_build_one_spatially_ordered_boundary(
    two_circle_build,
) -> None:
    build = two_circle_build

    assert isinstance(build.boundary, OrderedBoundary2D)
    assert isinstance(build.parameterization, OrderedBoundaryParameterization2D)
    assert build.num_components == 2
    assert build.boundary.component_ids == ("component_000", "component_001")
    assert tuple(component.num_nodes for component in build.boundary.components) == (
        32,
        40,
    )
    assert build.resolved_node_counts == (32, 40)
    np.testing.assert_array_equal(build.boundary.component_offsets, [0, 32, 72])
    np.testing.assert_array_equal(
        build.boundary.node_component_indices,
        np.concatenate((np.zeros(32, dtype=int), np.ones(40, dtype=int))),
    )
    assert build.topology_report.valid
    assert build.topology_report.minimum_intercomponent_clearance == pytest.approx(
        EXACT_CLEARANCE,
        abs=2.0e-4,
    )
    assert build.maximum_projected_sdf_residual < 1.0e-9
    assert build.maximum_curve_sdf_residual < 1.0e-8
    assert build.maximum_normalized_curve_residual < 1.0e-8
    assert build.minimum_field_gradient_norm == pytest.approx(1.0, abs=2.0e-12)
    assert tuple(
        item.readiness_sample_count for item in build.component_diagnostics
    ) == (64, 64)

    reconstructed_centers = np.array(
        [component.centroid for component in build.component_diagnostics]
    )
    np.testing.assert_allclose(reconstructed_centers, CENTERS, atol=2.0e-6)
    assert all(
        component.signed_area > 0.0
        for component in build.component_diagnostics
    )
    assert all(
        curve.orientation == "counterclockwise"
        for curve in build.boundary.components
    )
    with pytest.raises(MultiComponentOrderedSDFGeometryError, match="no unique curve"):
        _ = build.curve


def test_build_audit_rejects_inconsistent_report_and_node_config(
    two_circle_build,
) -> None:
    build = two_circle_build
    first_report = replace(
        build.topology_report.components[0],
        component_id="not-the-boundary-id",
    )
    inconsistent_report = replace(
        build.topology_report,
        components=(first_report, *build.topology_report.components[1:]),
    )
    with pytest.raises(ValueError, match="report and boundary component IDs"):
        replace(build, topology_report=inconsistent_report)

    inconsistent_config = replace(build.config, num_nodes=(40, 32))
    with pytest.raises(ValueError, match="node counts must match"):
        replace(build, config=inconsistent_config)


def test_component_count_mismatch_fails_before_fitting(
    two_circle_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    model = CircleUnionSDF2D(centers=CENTERS, radii=RADII)
    config = replace(
        two_circle_config,
        expected_num_components=1,
        num_nodes=32,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match=r"expected 1 closed component\(s\), found 2",
    ):
        build_multicomponent_ordered_sdf_geometry(model, config)


def test_minimum_clearance_is_an_explicit_topology_failure(
    two_circle_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    model = CircleUnionSDF2D(centers=CENTERS, radii=RADII)
    config = replace(
        two_circle_config,
        minimum_intercomponent_clearance=EXACT_CLEARANCE + 0.01,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="minimum intercomponent clearance",
    ):
        build_multicomponent_ordered_sdf_geometry(model, config)


def test_config_rejects_node_count_not_aligned_with_component_count() -> None:
    with pytest.raises(ValueError, match="one entry per expected component"):
        MultiComponentOrderedSDFGeometryConfig(
            bounds=((0.0, 0.0), (1.0, 1.0)),
            expected_num_components=2,
            num_nodes=(32,),
        )


def test_structurally_compatible_config_can_enter_isolated_builder() -> None:
    existing = SimpleNamespace(
        bounds=((0.2, 0.2), (0.8, 0.8)),
        grid_shape=(65, 65),
        projected_samples=32,
        bandwidth=4,
        num_nodes=32,
        arclength_dense_resolution=64,
        validation_resolution=64,
    )
    config = MultiComponentOrderedSDFGeometryConfig.from_compatible_config(
        existing,
    )
    build = build_multicomponent_ordered_sdf_geometry(
        CircleUnionSDF2D(centers=((0.5, 0.5),), radii=(0.08,)),
        config,
    )

    assert config.grid_shape == existing.grid_shape
    with pytest.raises(ValueError, match="cannot be resolved before automatic"):
        _ = config.resolved_node_counts
    assert config.resolve_node_counts(1) == (existing.num_nodes,)
    assert build.resolved_node_counts == (existing.num_nodes,)
    assert build.num_components == 1
    assert build.curve is build.boundary.components[0]


def test_builder_is_generic_beyond_the_two_object_acceptance_case() -> None:
    centers = ((0.34, 0.43), (0.50, 0.58), (0.66, 0.43))
    config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.20, 0.28), (0.80, 0.72)),
        expected_num_components=3,
        grid_shape=(81, 101),
        projected_samples=24,
        bandwidth=3,
        num_nodes=(16, 24, 32),
        arclength_dense_resolution=64,
        validation_resolution=64,
        minimum_intercomponent_clearance=0.10,
    )
    build = build_multicomponent_ordered_sdf_geometry(
        CircleUnionSDF2D(centers=centers, radii=(0.025, 0.025, 0.025)),
        config,
    )

    assert build.num_components == 3
    assert build.boundary.component_ids == (
        "component_000",
        "component_001",
        "component_002",
    )
    assert tuple(item.num_nodes for item in build.boundary.components) == (
        16,
        24,
        32,
    )
    np.testing.assert_array_equal(build.boundary.component_offsets, (0, 16, 40, 72))
    assert build.topology_report.minimum_intercomponent_clearance > 0.10


@pytest.mark.parametrize(
    ("centers", "radii"),
    (
        (((0.50, 0.50),), (0.055,)),
        (((0.40, 0.50), (0.60, 0.50)), (0.040, 0.040)),
        (
            ((0.35, 0.50), (0.50, 0.50), (0.65, 0.50)),
            (0.030, 0.030, 0.030),
        ),
    ),
)
def test_one_automatic_config_discovers_one_two_or_three_components(
    centers,
    radii,
) -> None:
    build = build_multicomponent_ordered_sdf_geometry(
        CircleUnionSDF2D(centers=centers, radii=radii),
        AUTO_CONFIG,
    )

    expected_count = len(centers)
    assert AUTO_CONFIG.expected_num_components is None
    assert build.num_components == expected_count
    assert build.resolved_node_counts == (24,) * expected_count
    assert tuple(curve.num_nodes for curve in build.boundary.components) == (
        (24,) * expected_count
    )


def test_automatic_mode_keeps_sequence_arity_and_resource_guards_explicit() -> None:
    three_circles = CircleUnionSDF2D(
        centers=((0.35, 0.50), (0.50, 0.50), (0.65, 0.50)),
        radii=(0.030, 0.030, 0.030),
    )
    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="Per-component num_nodes mismatch",
    ):
        build_multicomponent_ordered_sdf_geometry(
            three_circles,
            replace(AUTO_CONFIG, num_nodes=(24, 24)),
        )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="exceeds maximum_num_components",
    ):
        build_multicomponent_ordered_sdf_geometry(
            three_circles,
            replace(AUTO_CONFIG, maximum_num_components=2),
        )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="exceeds maximum_total_nodes",
    ):
        build_multicomponent_ordered_sdf_geometry(
            three_circles,
            replace(AUTO_CONFIG, maximum_total_nodes=64),
        )


def test_automatic_mode_explicitly_rejects_an_empty_zero_set() -> None:
    class PositiveField(torch.nn.Module):
        def forward(self, points):
            return torch.ones_like(points[..., :1])

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="no closed zero-set components",
    ):
        build_multicomponent_ordered_sdf_geometry(PositiveField(), AUTO_CONFIG)


@pytest.mark.parametrize(
    ("centers", "radii"),
    (
        (((0.50, 0.50),), (0.055,)),
        (((0.40, 0.50), (0.60, 0.50)), (0.040, 0.040)),
    ),
)
def test_sign_reversed_zero_sets_cannot_be_used_as_negative_inside_inclusions(
    centers,
    radii,
) -> None:
    class SignReversedCircleUnion(CircleUnionSDF2D):
        def forward(self, points):
            return -super().forward(points)

    # These fields have exactly the same zero sets and gradient magnitudes as
    # valid circle unions; only the material-side convention is reversed.
    model = SignReversedCircleUnion(centers=centers, radii=radii)
    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="negative_inside sign convention",
    ):
        build_multicomponent_ordered_sdf_geometry(model, AUTO_CONFIG)


def test_tiny_component_and_weak_gradient_are_not_solver_ready() -> None:
    circle_model = CircleUnionSDF2D(
        centers=((0.50, 0.50),),
        radii=(0.030,),
    )
    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="minimum_component_area",
    ):
        build_multicomponent_ordered_sdf_geometry(
            circle_model,
            replace(AUTO_CONFIG, minimum_component_area=0.01),
        )

    class WeakGradientCircle(torch.nn.Module):
        def forward(self, points):
            center = points.new_tensor((0.50, 0.50))
            return 1.0e-10 * (
                torch.linalg.norm(points - center, dim=-1, keepdim=True) - 0.055
            )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="minimum_boundary_gradient_norm",
    ):
        build_multicomponent_ordered_sdf_geometry(
            WeakGradientCircle(),
            AUTO_CONFIG,
        )
