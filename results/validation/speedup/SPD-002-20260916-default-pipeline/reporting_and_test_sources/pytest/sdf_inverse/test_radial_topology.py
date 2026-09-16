"""Regression tests for the opt-in radial topology-birth path."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

import config.two_circle_config as cfg
from gpr_bem_kress import Material, solve_kress_tmz_total_field_batch
from gpr_bem_kress.multicomponent import adapt_multicomponent_boundary
from multicylinder_ref import CircularCylinder2D, solve_multicylinder_line_sources
from sdf_bem_multicomponent import MaterialSpec, PairedForwardProblem, predict_multicomponent_kress_paired_boundary_response
from sdf_inverse import (
    ComplexScatteredData,
    MultiRadialFourierState,
    OrderedSDFGeometryConfig,
    ParameterFDConfig,
    build_td_raster,
    circle_radial_fourier_state,
    evaluate_birth_ladder,
    evaluate_current_domain_topological_derivative,
    evaluate_multiradial_objective,
    iteration01_optimizer_config,
    iteration01_solve_config,
    run_multiradial_fd_inverse,
)


CENTERS = np.asarray(cfg.TARGET_CIRCLE_CENTERS, dtype=np.float64)
RADII = np.asarray(cfg.TARGET_CIRCLE_RADII, dtype=np.float64)
FREQUENCY_HZ = 0.5e9
SOURCE_STRENGTH = 1.0e-6


def _geometry(nodes: int) -> OrderedSDFGeometryConfig:
    return OrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        grid_shape=(16, 16),
        projected_samples=8,
        bandwidth=1,
        num_nodes=nodes,
        arclength_dense_resolution=128,
        validation_resolution=128,
    )


def _ring() -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, 24, endpoint=False)
    standoff = 0.30
    offset = cfg.TX_RX_OFFSET / standoff
    source = np.column_stack((0.5 + standoff * np.cos(angles), 0.5 + standoff * np.sin(angles)))
    receiver = np.column_stack((0.5 + standoff * np.cos(angles + offset), 0.5 + standoff * np.sin(angles + offset)))
    return source, receiver


def _problem(*, strength: float = SOURCE_STRENGTH) -> PairedForwardProblem:
    source, receiver = _ring()
    return PairedForwardProblem(
        source,
        receiver,
        np.asarray((2.0 * np.pi * FREQUENCY_HZ,)),
        strength,
        MaterialSpec(cfg.SAND_EPSR, 0.0, 1.0),
        MaterialSpec(cfg.PLASTIC_EPSR, 0.0, 1.0),
        cfg.EPS0,
        cfg.MU0,
    )


def _a_state() -> MultiRadialFourierState:
    return MultiRadialFourierState((circle_radial_fourier_state(CENTERS[0], RADII[0], "A"),))


def _truth_state() -> MultiRadialFourierState:
    return MultiRadialFourierState(
        (
            circle_radial_fourier_state(CENTERS[0], RADII[0], "A"),
            circle_radial_fourier_state(CENTERS[1], RADII[1], "B"),
        )
    )


def _oracle_observations(*, strength: float = SOURCE_STRENGTH) -> np.ndarray:
    source, receiver = _ring()
    omega = 2.0 * np.pi * FREQUENCY_HZ
    k_exterior = omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.SAND_EPSR)
    k_interior = omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.PLASTIC_EPSR)
    cylinders = (
        CircularCylinder2D(tuple(CENTERS[0]), RADII[0], "A"),
        CircularCylinder2D(tuple(CENTERS[1]), RADII[1], "B"),
    )
    solution = solve_multicylinder_line_sources(
        cylinders,
        source,
        k_exterior=k_exterior,
        k_interior=k_interior,
        source_strength=strength,
    )
    return np.diag(solution.scattered_field(receiver))[:, None]


def _data(*, strength: float = SOURCE_STRENGTH, weight: float = 1.0) -> ComplexScatteredData:
    return ComplexScatteredData(
        _problem(strength=strength),
        _oracle_observations(strength=strength),
        np.asarray((weight,)),
    )


@lru_cache(maxsize=2)
def _raster(count: int):
    nodes = 64 if count == 121 else 128
    return build_td_raster(
        _a_state(),
        _data(),
        num_points=count,
        geometry_config=_geometry(nodes),
        solve_config=iteration01_solve_config(),
    )[0]


@lru_cache(maxsize=1)
def _birth():
    raster = _raster(121)
    return evaluate_birth_ladder(
        _a_state(),
        _data(),
        seed_center=raster.selected_centroid,
        equivalent_radius_m=raster.equivalent_radius_m,
        production_geometry_config=_geometry(64),
        refined_geometry_config=_geometry(128),
        solve_config=iteration01_solve_config(),
    )


def test_multiradial_state_preserves_order_ids_slices_and_exact_rollback() -> None:
    state = _truth_state()
    assert state.component_ids == ("A", "B")
    assert state.parameter_names == (
        "A.radius_m", "A.center_x_m", "A.center_y_m",
        "B.radius_m", "B.center_x_m", "B.center_y_m",
    )
    assert state.parameter_slices == (slice(0, 3), slice(3, 6))
    np.testing.assert_allclose(
        state.parameter_vector(),
        (0.035, 0.43, 0.50, 0.035, 0.57, 0.50),
        rtol=0.0,
        atol=2.0e-16,
    )
    trial = state.incremented(np.asarray((0.001, 0.002, 0.0, -0.001, 0.0, 0.002)))
    restored = trial.from_parameter_vector(state.parameter_vector())
    np.testing.assert_array_equal(restored.parameter_vector(), state.parameter_vector())
    assert restored.component_ids == state.component_ids
    boundary = state.boundary(_geometry(64))
    assert boundary.component_ids == ("A", "B")
    np.testing.assert_array_equal(boundary.components[0].points, _a_state().boundary(_geometry(64)).components[0].points)


def test_multiradial_state_rejects_empty_and_duplicate_identifiers() -> None:
    with pytest.raises(ValueError, match="At least one"):
        MultiRadialFourierState(())
    component = circle_radial_fourier_state(CENTERS[0], RADII[0], "same")
    with pytest.raises(ValueError, match="unique"):
        MultiRadialFourierState((component, component))


def test_direct_forward_m1_matches_single_kress_and_m2_is_permutation_invariant() -> None:
    problem = _problem()
    one_boundary = _a_state().boundary(_geometry(64))
    multi_one = predict_multicomponent_kress_paired_boundary_response(one_boundary, problem, solve_config=iteration01_solve_config())
    curve = one_boundary.components[0]
    single = solve_kress_tmz_total_field_batch(
        curve,
        problem.source_points,
        problem.receiver_points,
        float(problem.angular_frequencies[0]),
        complex(problem.source_strengths[0]),
        exterior=Material(epsr=cfg.SAND_EPSR),
        interior=Material(epsr=cfg.PLASTIC_EPSR),
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
    )
    np.testing.assert_allclose(multi_one.scattered_response[:, 0], np.diag(single.scattered_receiver), rtol=2.0e-13, atol=1.0e-20)

    state = _truth_state()
    forward = predict_multicomponent_kress_paired_boundary_response(state.boundary(_geometry(64)), problem, solve_config=iteration01_solve_config())
    permuted = MultiRadialFourierState(tuple(reversed(state.components)))
    reverse = predict_multicomponent_kress_paired_boundary_response(permuted.boundary(_geometry(64)), problem, solve_config=iteration01_solve_config())
    np.testing.assert_allclose(forward.scattered_response, reverse.scattered_response, rtol=2.0e-12, atol=1.0e-20)


def test_physical_clearance_floor_is_identical_under_node_refinement() -> None:
    settings = iteration01_solve_config().assembly
    reports = []
    for nodes in (64, 128):
        report = adapt_multicomponent_boundary(_truth_state().boundary(_geometry(nodes)), config=settings).component_pair_reports[0]
        reports.append(report)
        assert report.required_clearance == pytest.approx(0.010, abs=1.0e-15)
        assert report.clearance == pytest.approx(0.070, abs=5.0e-5)
    assert reports[0].required_clearance == reports[1].required_clearance


def test_td_matches_saved_three_probe_oracle_and_preserves_pairing_scale_and_chunking() -> None:
    points = np.asarray(((0.57, 0.50), (0.50, 0.62), (0.66, 0.66)))
    expected = np.asarray((-159.268698, -53.3368618, 37.8091661))
    base = evaluate_current_domain_topological_derivative(
        _a_state(), _data(), points, geometry_config=_geometry(64), solve_config=iteration01_solve_config(), chunk_size=4096
    )
    np.testing.assert_allclose(base.values, expected, rtol=1.0e-7, atol=1.0e-7)
    chunked = evaluate_current_domain_topological_derivative(
        _a_state(), _data(), points, geometry_config=_geometry(64), solve_config=iteration01_solve_config(), chunk_size=1
    )
    np.testing.assert_allclose(chunked.values, base.values, rtol=0.0, atol=2.0e-13)
    weighted = evaluate_current_domain_topological_derivative(
        _a_state(), _data(weight=2.0), points, geometry_config=_geometry(64), solve_config=iteration01_solve_config()
    )
    np.testing.assert_allclose(weighted.values, 2.0 * base.values, rtol=2.0e-14, atol=2.0e-13)
    assert base.predicted_scattered_response.shape == (24, 1)
    assert base.linear_system_relative_residuals[0] < 1.0e-12


def test_td_source_strength_scaling_and_empty_background_branch() -> None:
    points = np.asarray(((0.57, 0.50), (0.50, 0.62)))
    base = evaluate_current_domain_topological_derivative(
        _a_state(), _data(), points, geometry_config=_geometry(64), solve_config=iteration01_solve_config()
    )
    scaled = evaluate_current_domain_topological_derivative(
        _a_state(), _data(strength=2.0e-6), points, geometry_config=_geometry(64), solve_config=iteration01_solve_config()
    )
    np.testing.assert_allclose(scaled.values, base.values, rtol=2.0e-13, atol=2.0e-11)

    one_truth = _oracle_observations().copy()
    source, receiver = _ring()
    omega = 2.0 * np.pi * FREQUENCY_HZ
    k_exterior = omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.SAND_EPSR)
    k_interior = omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.PLASTIC_EPSR)
    one = solve_multicylinder_line_sources(
        (CircularCylinder2D(tuple(CENTERS[0]), RADII[0], "A"),),
        source,
        k_exterior=k_exterior,
        k_interior=k_interior,
        source_strength=SOURCE_STRENGTH,
    )
    one_truth[:, 0] = np.diag(one.scattered_field(receiver))
    empty = evaluate_current_domain_topological_derivative(
        None,
        ComplexScatteredData(_problem(), one_truth),
        CENTERS[:1],
        solve_config=iteration01_solve_config(),
    )
    assert empty.empty_domain
    assert empty.predicted_scattered_response[0, 0] == 0.0
    assert empty.values[0] == pytest.approx(-407.673430, rel=1.0e-7)


def test_frozen_121_and_241_rasters_localize_one_deterministic_region() -> None:
    production = _raster(121)
    refined = _raster(241)
    for raster in (production, refined):
        assert raster.region_count == 1
        assert np.linalg.norm(raster.minimum_point - CENTERS[1]) <= 0.005
        assert np.linalg.norm(raster.selected_centroid - CENTERS[1]) <= 0.005
        assert raster.minimum_station_distance_m >= 0.10 - 1.0e-12
        assert not raster.selected_touches_inspection_boundary
        assert np.all(np.isnan(raster.values[~raster.valid_mask]))
        assert np.all(raster.labels[raster.selected_region] > 0)
    assert np.linalg.norm(production.selected_centroid - refined.selected_centroid) <= 0.005
    assert production.equivalent_radius_m == pytest.approx(0.0156217021930, rel=1.0e-10)


def test_birth_ladder_order_margin_and_existing_state_are_preserved() -> None:
    result = _birth()
    assert tuple(item.factor for item in result.trials) == (1.0, 0.75, 0.5, 0.35)
    assert result.stop_reason == "accepted"
    assert result.selected_state is not None
    np.testing.assert_array_equal(
        result.selected_state.parameter_vector()[:3], _a_state().parameter_vector()
    )
    np.testing.assert_array_equal(result.initial_state.parameter_vector(), _a_state().parameter_vector())
    assert all(item.accepted for item in result.trials)
    for item in result.trials:
        assert item.production_delta < 0.0
        assert item.refined_delta < 0.0
        assert min(-item.production_delta, -item.refined_delta) > 5.0 * abs(item.production_delta - item.refined_delta) + 1.0e-12
    assert result.selected_state.component_ids == ("A", "td_birth_001")


def test_birth_rejects_frozen_ladder_entries_below_five_mm() -> None:
    result = evaluate_birth_ladder(
        _a_state(),
        _data(),
        seed_center=CENTERS[1],
        equivalent_radius_m=0.010,
        production_geometry_config=_geometry(64),
        refined_geometry_config=_geometry(128),
        solve_config=iteration01_solve_config(),
    )
    assert result.trials[-1].radius_m == pytest.approx(0.0035)
    assert result.trials[-1].rejection_reason == "below_minimum_radius"
    with pytest.raises(ValueError, match="frozen"):
        evaluate_birth_ladder(
            _a_state(), _data(), seed_center=CENTERS[1], equivalent_radius_m=0.010,
            production_geometry_config=_geometry(64), refined_geometry_config=_geometry(128),
            solve_config=iteration01_solve_config(), radius_factors=(1.0, 0.5),
        )


def test_multiradial_fd_columns_and_accepted_objective_recover_two_circles() -> None:
    birth = _birth()
    assert birth.selected_state is not None
    result = run_multiradial_fd_inverse(
        birth.selected_state,
        _data(),
        _geometry(64),
        solve_config=iteration01_solve_config(),
        config=iteration01_optimizer_config(),
    )
    assert result.iterations[0].parameter_names == (
        "A.radius_m", "A.center_x_m", "A.center_y_m",
        "td_birth_001.radius_m", "td_birth_001.center_x_m", "td_birth_001.center_y_m",
    )
    assert all(later.loss < earlier.loss for earlier, later in zip(result.iterations, result.iterations[1:]))
    assert result.iterations[-1].relative_l2_error < 0.02
    np.testing.assert_allclose(
        result.final_state.parameter_vector(),
        (0.035, 0.43, 0.50, 0.035, 0.57, 0.50),
        rtol=0.0,
        atol=2.0e-6,
    )

    # Independently rebuild the full central-FD gradient at the stored initial
    # state.  This also checks that cross-component multiple scattering enters
    # every numerical column through the actual multi-Kress objective.
    initial = result.iterations[0].state
    base = evaluate_multiradial_objective(initial, _data(), _geometry(64), solve_config=iteration01_solve_config())
    columns = []
    for index in range(initial.parameter_count):
        step = np.zeros(initial.parameter_count)
        step[index] = 1.0e-4
        plus = evaluate_multiradial_objective(initial.incremented(step), _data(), _geometry(64), solve_config=iteration01_solve_config())
        minus = evaluate_multiradial_objective(initial.incremented(-step), _data(), _geometry(64), solve_config=iteration01_solve_config())
        columns.append((plus.residual - minus.residual) / 2.0e-4)
    independent_gradient = np.column_stack(columns).T @ base.residual
    np.testing.assert_allclose(result.iterations[0].gradient, independent_gradient, rtol=2.0e-12, atol=2.0e-12)


def test_infeasible_fd_trial_is_local_and_final_state_rolls_back_exactly() -> None:
    # The circles have only 10.05 mm clearance, so the +radius FD probe is
    # rejected by the physical 10-mm floor.  Zero residual makes the accepted
    # initial state the exact rollback target.
    close = MultiRadialFourierState(
        (
            circle_radial_fourier_state((0.445, 0.50), 0.035, "left"),
            circle_radial_fourier_state((0.52505, 0.50), 0.035, "right"),
        )
    )
    problem = _problem()
    observed = predict_multicomponent_kress_paired_boundary_response(
        close.boundary(_geometry(64)), problem, solve_config=iteration01_solve_config()
    ).scattered_response
    result = run_multiradial_fd_inverse(
        close,
        ComplexScatteredData(problem, observed),
        _geometry(64),
        solve_config=iteration01_solve_config(),
        config=ParameterFDConfig(
            max_iterations=1,
            finite_difference_steps=1.0e-4,
            max_steps=0.02,
            infeasible_trial_policy="reject",
        ),
    )
    assert result.infeasible_trial_count >= 1
    np.testing.assert_array_equal(result.final_state.parameter_vector(), close.parameter_vector())
    assert result.final_state.component_ids == close.component_ids
