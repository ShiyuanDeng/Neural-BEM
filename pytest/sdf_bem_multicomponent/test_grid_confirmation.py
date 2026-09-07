"""Independent-grid readiness checks for automatic component discovery."""

from __future__ import annotations

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")

from sdf_bem_multicomponent.geometry import (
    GridParityConfirmationDiagnostics,
    MultiComponentOrderedSDFGeometryConfig,
    MultiComponentOrderedSDFGeometryError,
    build_multicomponent_ordered_sdf_geometry,
)
from sdf_bem_multicomponent.circle_union import CircleUnionSDF2D
from sdf_bem_multicomponent.split_fixture import (
    CassiniSplitConfig,
    CassiniSplitTrajectory2D,
)


@pytest.fixture(scope="module")
def trajectory() -> CassiniSplitTrajectory2D:
    return CassiniSplitTrajectory2D()


@pytest.fixture(scope="module")
def high_resolution_config() -> MultiComponentOrderedSDFGeometryConfig:
    # This deliberately exercises the formerly ambiguous case: on the 257^2
    # grid, high-bandwidth fitting can smooth the exact Cassini pinch into two
    # apparently regular loops with normalized residual below 1e-3.  The
    # projected-gradient guard and independent 258^2 pass must prevent that
    # false acceptance.
    return MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.2, 0.2), (0.8, 0.8)),
        grid_shape=(257, 257),
        projected_samples=128,
        bandwidth=24,
        num_nodes=192,
        arclength_dense_resolution=512,
        validation_resolution=512,
        maximum_total_nodes=4096,
    )


def test_production_defaults_use_opposite_parity_and_grid_scale_clearance(
    high_resolution_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    config = high_resolution_config

    assert config.expected_num_components is None
    assert config.confirm_grid_parity
    assert config.resolved_confirmation_grid_shape == (258, 258)
    assert config.resolved_minimum_intercomponent_clearance == pytest.approx(
        2.0 * 0.6 / 256.0
    )
    assert config.resolved_minimum_component_area == pytest.approx(
        4.0 * (0.6 / 256.0) ** 2
    )
    assert config.resolved_minimum_component_perimeter == pytest.approx(
        8.0 * 0.6 / 256.0
    )
    assert config.resolved_minimum_component_spans == pytest.approx(
        (2.0 * 0.6 / 256.0, 2.0 * 0.6 / 256.0)
    )
    assert config.resolved_grid_confirmation_geometry_tolerance_cap == pytest.approx(
        2.0 * 0.6 / 256.0
    )

    with pytest.raises(ValueError, match="reverse the point-count parity"):
        replace(config, confirmation_grid_shape=(259, 259))
    with pytest.raises(ValueError, match="strictly finer"):
        replace(config, confirmation_grid_shape=(256, 256))
    with pytest.raises(ValueError, match="requires confirm_grid_parity=True"):
        replace(
            config,
            confirm_grid_parity=False,
            confirmation_grid_shape=(258, 258),
        )


def test_projected_gradient_rejects_grid_aligned_exact_pinch_before_fitting(
    trajectory: CassiniSplitTrajectory2D,
    high_resolution_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="minimum projected field-gradient norm",
    ):
        build_multicomponent_ordered_sdf_geometry(
            trajectory.model(trajectory.critical_progress),
            high_resolution_config,
        )


def test_opposite_parity_pass_independently_catches_exact_pinch(
    trajectory: CassiniSplitTrajectory2D,
    high_resolution_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    # Disable the other two safety gates only to isolate the confirmation
    # regression.  The 257^2 primary fit passes, while the independent 258^2
    # fit exposes the singular frame through its readiness residual.
    confirmation_only = replace(
        high_resolution_config,
        minimum_boundary_gradient_norm=0.0,
        minimum_grid_clearance_factor=0.0,
        minimum_quadrature_clearance_in_weights=0.0,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match=r"grid-parity confirmation on grid \(258, 258\).*normalized curve residual",
    ):
        build_multicomponent_ordered_sdf_geometry(
            trajectory.model(trajectory.critical_progress),
            confirmation_only,
        )


def test_grid_scale_clearance_checks_projected_contours_before_smoothing(
    trajectory: CassiniSplitTrajectory2D,
    high_resolution_config: MultiComponentOrderedSDFGeometryConfig,
) -> None:
    # Let the singular projected gradient through and disable the second grid;
    # the primary projected lobes are still separated by less than two cells.
    clearance_only = replace(
        high_resolution_config,
        minimum_boundary_gradient_norm=0.0,
        maximum_normalized_curve_residual=1.0,
        confirm_grid_parity=False,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="projected contours fail the minimum intercomponent clearance",
    ):
        build_multicomponent_ordered_sdf_geometry(
            trajectory.model(trajectory.critical_progress),
            clearance_only,
        )


def test_equal_counts_with_different_aliased_components_fail_geometry_match() -> None:
    # The 33^2 grid sees the tiny circle at (0.5, 0.5); the 34^2 grid sees the
    # equally tiny circle at (16/33, 16/33).  Both also see the large circle,
    # so count-only confirmation incorrectly reports M=2 on both passes even
    # though the underlying field has M=3 and the extracted component sets
    # differ.
    model = CircleUnionSDF2D(
        centers=((0.2, 0.2), (0.5, 0.5), (16.0 / 33.0, 16.0 / 33.0)),
        radii=(0.05, 0.006, 0.006),
    )
    config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(33, 33),
        projected_samples=24,
        bandwidth=3,
        num_nodes=24,
        arclength_dense_resolution=64,
        validation_resolution=64,
        minimum_grid_component_area_factor=0.0,
        minimum_grid_component_perimeter_factor=0.0,
        minimum_grid_component_span_factor=0.0,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="inconsistent component geometry despite an equal component count",
    ):
        build_multicomponent_ordered_sdf_geometry(model, config)


def test_pair_local_residual_tolerance_cannot_be_inflated_by_another_loop() -> None:
    big_component = CassiniSplitTrajectory2D(
        CassiniSplitConfig(
            center=(0.32, 0.32),
            cassini_radius=0.08,
            final_focal_half_distance=0.11,
        )
    ).model(0.5328125)

    class BigAndAliasedTinyCircles(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.big_component = big_component
            self.register_buffer(
                "tiny_centers",
                torch.tensor(
                    ((0.5, 0.5), (0.5011673151750973, 0.5035019455252918)),
                    dtype=torch.float64,
                ),
            )

        def forward(self, points):
            big_values = self.big_component(points).reshape(-1)
            centers = self.tiny_centers.to(dtype=points.dtype)
            tiny_values = torch.linalg.norm(
                points[:, None, :] - centers[None, :, :],
                dim=2,
            ) - 0.0005
            return torch.minimum(
                big_values,
                torch.amin(tiny_values, dim=1),
            )[:, None]

    config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.2, 0.2), (0.8, 0.8)),
        grid_shape=(257, 257),
        projected_samples=128,
        bandwidth=24,
        num_nodes=192,
        arclength_dense_resolution=512,
        validation_resolution=512,
        maximum_total_nodes=4096,
        minimum_grid_component_area_factor=0.0,
        minimum_grid_component_perimeter_factor=0.0,
        minimum_grid_component_span_factor=0.0,
        minimum_grid_clearance_factor=0.0,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="exceeding its pair-local grid/residual tolerance",
    ):
        build_multicomponent_ordered_sdf_geometry(
            BigAndAliasedTinyCircles(),
            config,
        )


def test_grid_relative_raw_size_floor_rejects_one_cell_component() -> None:
    model = CircleUnionSDF2D(
        centers=((0.2, 0.2), (0.5, 0.5)),
        radii=(0.05, 0.006),
    )
    config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(33, 33),
        projected_samples=24,
        bandwidth=3,
        num_nodes=24,
        arclength_dense_resolution=64,
        validation_resolution=64,
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match=r"raw .*resolved minimum_component_(?:perimeter|area)",
    ):
        build_multicomponent_ordered_sdf_geometry(model, config)


def test_post_discretization_clearance_matches_default_quadrature_scale() -> None:
    model = CircleUnionSDF2D(
        centers=((0.405, 0.5), (0.595, 0.5)),
        radii=(0.09, 0.09),
    )
    config = MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.2, 0.2), (0.8, 0.8)),
    )

    with pytest.raises(
        MultiComponentOrderedSDFGeometryError,
        match="not solver-ready for ordinary cross-component quadrature",
    ):
        build_multicomponent_ordered_sdf_geometry(model, config)

    permissive = replace(
        config,
        minimum_quadrature_clearance_in_weights=0.0,
    )
    build = build_multicomponent_ordered_sdf_geometry(model, permissive)
    assert build.num_components == 2
    assert build.resolved_required_intercomponent_clearance == pytest.approx(
        permissive.resolved_minimum_intercomponent_clearance
    )
    assert (
        build.topology_report.minimum_intercomponent_clearance
        > build.resolved_required_intercomponent_clearance
    )


@pytest.mark.parametrize(
    ("progress", "expected_components"),
    ((0.5328125, 1), (0.5666667, 2)),
)
def test_regular_near_split_frames_pass_both_grids_with_same_count_and_readiness(
    trajectory: CassiniSplitTrajectory2D,
    high_resolution_config: MultiComponentOrderedSDFGeometryConfig,
    progress: float,
    expected_components: int,
) -> None:
    build = build_multicomponent_ordered_sdf_geometry(
        trajectory.model(progress),
        high_resolution_config,
    )
    confirmation = build.grid_parity_confirmation

    assert isinstance(confirmation, GridParityConfirmationDiagnostics)
    assert build.num_components == expected_components
    assert confirmation.primary_grid_shape == (257, 257)
    assert confirmation.confirmation_grid_shape == (258, 258)
    assert confirmation.primary_num_components == expected_components
    assert confirmation.confirmation_num_components == expected_components
    assert (
        confirmation.primary_minimum_projected_field_gradient_norm
        == build.minimum_projected_field_gradient_norm
    )
    assert (
        confirmation.primary_minimum_field_gradient_norm
        == build.minimum_field_gradient_norm
    )
    assert (
        confirmation.primary_maximum_normalized_curve_residual
        == build.maximum_normalized_curve_residual
    )
    assert confirmation.confirmation_minimum_projected_field_gradient_norm > 0.0
    assert confirmation.confirmation_minimum_field_gradient_norm > 0.0
    assert (
        confirmation.confirmation_maximum_normalized_curve_residual
        <= high_resolution_config.maximum_normalized_curve_residual
    )
    assert confirmation.confirmation_seconds > 0.0
    assert build.total_seconds >= confirmation.confirmation_seconds
    assert len(confirmation.primary_to_confirmation_component_indices) == (
        expected_components
    )
    assert len(confirmation.matched_component_distances) == expected_components
    assert len(confirmation.matched_component_tolerances) == expected_components
    assert all(
        distance <= tolerance
        for distance, tolerance in zip(
            confirmation.matched_component_distances,
            confirmation.matched_component_tolerances,
        )
    )
    grid_tolerance = (
        high_resolution_config.resolved_grid_confirmation_geometry_tolerance
    )
    assert grid_tolerance is not None
    tolerance_cap = (
        high_resolution_config.resolved_grid_confirmation_geometry_tolerance_cap
    )
    assert tolerance_cap is not None
    assert confirmation.matched_component_tolerances == pytest.approx(
        tuple(
            max(
                grid_tolerance,
                min(
                    high_resolution_config.grid_confirmation_residual_tolerance_factor
                    * max(primary_residual, confirmation_residual),
                    tolerance_cap,
                ),
            )
            for primary_residual, confirmation_residual in zip(
                confirmation.primary_component_normalized_curve_residuals,
                confirmation.matched_confirmation_component_normalized_curve_residuals,
            )
        )
    )
    assert (
        confirmation.maximum_matched_component_distance
        <= confirmation.component_geometry_tolerance
    )
    if expected_components == 1:
        inconsistent_confirmation = replace(
            confirmation,
            matched_component_tolerances=tuple(
                2.0 * value
                for value in confirmation.matched_component_tolerances
            ),
        )
        with pytest.raises(
            ValueError,
            match="configured per-component geometry tolerances",
        ):
            replace(
                build,
                grid_parity_confirmation=inconsistent_confirmation,
            )
