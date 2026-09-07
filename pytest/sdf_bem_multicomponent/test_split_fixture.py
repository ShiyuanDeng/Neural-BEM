"""One-to-two topology-change validation for the analytic split fixture."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from gpr_bem_kress import Material
from gpr_bem_kress.multicomponent import (
    solve_multicomponent_kress_tmz_total_field_batch,
)
from multicylinder_ref import (
    CircularCylinder2D,
    solve_multicylinder_line_sources,
)
from sdf_bem_multicomponent.geometry import (
    MultiComponentOrderedSDFGeometryConfig,
    MultiComponentOrderedSDFGeometryError,
    build_multicomponent_ordered_sdf_geometry,
)
from sdf_bem_multicomponent.split_fixture import (
    CassiniSplitConfig,
    CassiniSplitStage,
    CassiniSplitTopology,
    CassiniSplitTrajectory2D,
    CassiniSplitTransitionError,
    build_cassini_split_geometry,
)


@pytest.fixture(scope="module")
def trajectory() -> CassiniSplitTrajectory2D:
    return CassiniSplitTrajectory2D()


@pytest.fixture(scope="module")
def automatic_geometry_config() -> MultiComponentOrderedSDFGeometryConfig:
    return MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        expected_num_components=None,
        grid_shape=(129, 129),
        projected_samples=48,
        bandwidth=6,
        num_nodes=48,
        arclength_dense_resolution=128,
        validation_resolution=128,
        minimum_intercomponent_clearance=0.02,
    )


def test_trajectory_exposes_the_analytic_split_parameter_and_stages(
    trajectory: CassiniSplitTrajectory2D,
) -> None:
    initial = trajectory.frame(0.0)
    pre_split = trajectory.frame(0.35)
    critical = trajectory.frame(trajectory.critical_progress)
    post_split = trajectory.frame(0.70)
    blended = trajectory.frame(0.90)
    endpoint = trajectory.frame(1.0)

    assert initial.stage is CassiniSplitStage.INITIAL_CIRCLE
    assert initial.topology is CassiniSplitTopology.ONE_COMPONENT
    assert initial.focal_half_distance == 0.0
    assert initial.normalized_split_parameter == pytest.approx(-1.0)
    assert initial.expected_num_components == 1

    assert pre_split.topology is CassiniSplitTopology.ONE_COMPONENT
    assert pre_split.normalized_split_parameter < 0.0
    assert critical.stage is CassiniSplitStage.CRITICAL_PINCH
    assert critical.topology is CassiniSplitTopology.CRITICAL_PINCH
    assert critical.normalized_split_parameter == 0.0
    assert critical.expected_num_components is None
    assert not critical.solver_ready
    assert post_split.stage is CassiniSplitStage.POST_SPLIT_CASSINI
    assert post_split.normalized_split_parameter > 0.0
    assert post_split.expected_num_components == 2
    assert blended.stage is CassiniSplitStage.POST_SPLIT_BLEND
    assert 0.0 < blended.exact_circle_blend_weight < 1.0
    assert endpoint.stage is CassiniSplitStage.EXACT_TWO_CIRCLES
    assert endpoint.exact_circle_blend_weight == 1.0
    assert endpoint.is_exact_circle_endpoint


def test_initial_zero_set_and_endpoint_are_exact_circles(
    trajectory: CassiniSplitTrajectory2D,
) -> None:
    config = trajectory.config
    angles = np.linspace(0.0, 2.0 * np.pi, 41, endpoint=False)
    initial_points = np.asarray(config.center)[None, :] + config.cassini_radius * (
        np.column_stack((np.cos(angles), np.sin(angles)))
    )
    initial_model = trajectory.model(0.0)
    initial_values = initial_model(
        torch.as_tensor(initial_points, dtype=torch.float64)
    ).detach().numpy()[:, 0]
    np.testing.assert_allclose(initial_values, 0.0, atol=1.0e-16)

    endpoint_model = trajectory.model(1.0)
    query = np.asarray(
        (
            config.center,
            config.exact_circle_centers[0],
            config.exact_circle_centers[1],
            (0.23, 0.71),
        ),
        dtype=np.float64,
    )
    observed = endpoint_model(
        torch.as_tensor(query, dtype=torch.float64)
    ).detach().numpy()[:, 0]
    centers = np.asarray(config.exact_circle_centers)
    expected = np.min(
        np.linalg.norm(query[:, None, :] - centers[None, :, :], axis=2)
        - config.final_circle_radius,
        axis=1,
    )
    np.testing.assert_allclose(observed, expected, rtol=0.0, atol=2.0e-16)
    assert config.exact_circle_clearance > 0.0


def test_critical_frame_remains_drawable_but_is_explicitly_not_solvable(
    trajectory: CassiniSplitTrajectory2D,
    automatic_geometry_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    model = trajectory.model(trajectory.critical_progress)
    raw_contours = trajectory.critical_raw_contours(num_points_per_lobe=129)
    center = np.asarray(trajectory.config.center)

    assert len(raw_contours) == 2
    for contour in raw_contours:
        assert contour.shape == (129, 2)
        np.testing.assert_array_equal(contour[0], center)
        np.testing.assert_array_equal(contour[-1], center)
        values = model(torch.as_tensor(contour.copy(), dtype=torch.float64))
        assert float(torch.max(torch.abs(values))) < 2.0e-16
        assert not contour.flags.writeable

    critical_point = torch.tensor(
        trajectory.config.center,
        dtype=torch.float64,
        requires_grad=True,
    )
    model(critical_point[None, :]).sum().backward()
    np.testing.assert_allclose(critical_point.grad.detach().numpy(), 0.0, atol=0.0)

    with pytest.raises(CassiniSplitTransitionError, match="zero gradient"):
        build_cassini_split_geometry(
            trajectory,
            trajectory.critical_progress,
            automatic_geometry_config,
        )


def test_generic_builder_also_rejects_the_unlabelled_critical_field(
    trajectory: CassiniSplitTrajectory2D,
    automatic_geometry_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    # This bypasses the fixture's exact analytic guard on purpose.  Marching
    # squares may visually separate the pinched contour by a grid cell, so the
    # normalized fitted-boundary residual remains the independent safeguard.
    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="maximum normalized curve residual",
    ):
        build_multicomponent_ordered_sdf_geometry(
            trajectory.model(trajectory.critical_progress),
            replace(
                automatic_geometry_config,
                minimum_intercomponent_clearance=0.0,
            ),
        )


def test_automatic_extraction_discovers_one_then_two_components(
    trajectory: CassiniSplitTrajectory2D,
    automatic_geometry_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    initial = build_cassini_split_geometry(
        trajectory,
        0.0,
        automatic_geometry_config,
    )
    post_split = build_cassini_split_geometry(
        trajectory,
        0.70,
        automatic_geometry_config,
    )
    blended = build_cassini_split_geometry(
        trajectory,
        0.90,
        automatic_geometry_config,
    )
    endpoint = build_cassini_split_geometry(
        trajectory,
        1.0,
        automatic_geometry_config,
    )

    assert initial.geometry.num_components == 1
    assert initial.geometry.boundary.component_offsets.tolist() == [0, 48]
    assert post_split.geometry.num_components == 2
    assert post_split.geometry.boundary.component_offsets.tolist() == [0, 48, 96]
    assert blended.geometry.num_components == 2
    assert blended.frame.stage is CassiniSplitStage.POST_SPLIT_BLEND
    assert blended.geometry.maximum_normalized_curve_residual < 1.0e-6
    assert endpoint.geometry.num_components == 2
    assert endpoint.geometry.boundary.component_offsets.tolist() == [0, 48, 96]
    assert endpoint.frame.is_exact_circle_endpoint

    observed_centers = np.asarray(
        [item.centroid for item in endpoint.geometry.component_diagnostics]
    )
    np.testing.assert_allclose(
        observed_centers,
        np.asarray(trajectory.config.exact_circle_centers),
        atol=2.0e-7,
    )
    assert (
        endpoint.geometry.topology_report.minimum_intercomponent_clearance
        == pytest.approx(trajectory.config.exact_circle_clearance, abs=2.0e-6)
    )


def test_extracted_exact_endpoint_matches_independent_two_cylinder_oracle(
    trajectory: CassiniSplitTrajectory2D,
    automatic_geometry_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    endpoint = build_cassini_split_geometry(
        trajectory,
        1.0,
        automatic_geometry_config,
    )
    center = np.asarray(trajectory.config.center)
    source_angles = np.asarray((0.1, 2.2, 4.3))
    receiver_angles = np.asarray((0.7, 2.8, 4.9))
    sources = center + 0.34 * np.column_stack(
        (np.cos(source_angles), np.sin(source_angles))
    )
    receivers = center + 0.31 * np.column_stack(
        (np.cos(receiver_angles), np.sin(receiver_angles))
    )
    eps0 = 8.8541878128e-12
    mu0 = 1.25663706212e-6
    angular_frequency = 2.0 * np.pi * 1.2e9
    exterior = Material(epsr=3.1)
    interior = Material(epsr=2.2)

    kress = solve_multicomponent_kress_tmz_total_field_batch(
        endpoint.geometry.boundary,
        sources,
        receivers,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
    )
    cylinders = tuple(
        CircularCylinder2D(component_center, component_radius)
        for component_center, component_radius in zip(
            trajectory.config.exact_circle_centers,
            trajectory.config.exact_circle_radii,
        )
    )
    oracle = solve_multicylinder_line_sources(
        cylinders,
        sources,
        k_exterior=exterior.wavenumber(angular_frequency, eps0, mu0),
        k_interior=interior.wavenumber(angular_frequency, eps0, mu0),
        mode_order=20,
    )

    np.testing.assert_allclose(
        kress.scattered_receiver,
        oracle.scattered_field(receivers).T,
        rtol=3.0e-9,
        atol=3.0e-12,
    )
    assert kress.linear_system_relative_residual < 1.0e-12


def test_split_config_rejects_an_invalid_endpoint() -> None:
    with pytest.raises(ValueError, match="must exceed cassini_radius"):
        CassiniSplitConfig(final_focal_half_distance=0.10)
    with pytest.raises(ValueError, match="endpoint circles are disjoint"):
        CassiniSplitConfig(final_circle_radius=0.17)
    with pytest.raises(ValueError, match="strictly between"):
        CassiniSplitConfig(critical_progress=0.8, blend_start_progress=0.8)
