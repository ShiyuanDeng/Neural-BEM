"""Fast contracts for the post-iteration-01 topology challenge driver."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "radial_topology_challenges_under_test",
    ROOT / "run_radial_fourier_topology_challenges.py",
)
assert SPEC is not None and SPEC.loader is not None
driver = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = driver
SPEC.loader.exec_module(driver)


def test_far_circle_is_far_from_both_truth_components() -> None:
    case = driver._case_spec("far-circle")
    center = case.initial_state.components[0].center
    distances = np.linalg.norm(driver.TRUTH_CIRCLE_CENTERS - center[None, :], axis=1)

    assert case.proposal_policy == "background_td_replacement"
    assert np.all(distances > 0.17)


def test_large_circle_encloses_both_truth_circles() -> None:
    case = driver._case_spec("large-split")
    component = case.initial_state.components[0]
    required = (
        np.linalg.norm(driver.TRUTH_CIRCLE_CENTERS - component.center[None, :], axis=1)
        + driver.TRUTH_CIRCLE_RADII
    )

    assert case.proposal_policy == "background_td_replacement"
    assert np.all(required <= component.mean_radius_m + 1.0e-15)


def test_ellipse_and_star_are_on_opposite_diagonal_corners() -> None:
    case = driver._case_spec("ellipse-star")
    centers = np.asarray(
        [np.mean(curve.discretize(128).points, axis=0) for curve in case.truth_curves]
    )
    offsets = centers - np.asarray((0.50, 0.50))[None, :]

    assert np.all(offsets[0] < 0.0)
    assert np.all(offsets[1] > 0.0)
    assert case.training_indices == (0, 1)
    assert case.mode_schedule == (2, 5)


def test_mode_promotion_is_exactly_shape_preserving() -> None:
    state = driver._case_spec("ellipse-star").initial_state
    before = driver._sample_radial(state.components[0])
    promoted = driver._promote(state, 5)
    after = driver._sample_radial(promoted.components[0])

    assert promoted.components[0].maximum_mode == 5
    np.testing.assert_array_equal(after, before)


def test_mode_promotion_never_lowers_an_existing_component() -> None:
    state = driver._promote(driver._case_spec("ellipse-star").initial_state, 5)

    unchanged = driver._promote(state, 2)

    assert unchanged.components[0].maximum_mode == 5
    np.testing.assert_array_equal(
        driver._sample_radial(unchanged.components[0]),
        driver._sample_radial(state.components[0]),
    )


def test_optimizer_controls_cover_every_promoted_parameter() -> None:
    state = driver._promote(driver._case_spec("ellipse-star").initial_state, 5)
    config = driver._optimizer_config(state, 3)

    assert config.max_iterations == 3
    assert config.max_parameters >= state.parameter_count
    assert config.resolved_finite_difference_steps(state.parameter_count).shape == (
        state.parameter_count,
    )
    assert config.resolved_max_steps(state.parameter_count).shape == (
        state.parameter_count,
    )


def test_quick_profile_is_explicitly_non_qualifying() -> None:
    quick = driver._profile("quick")
    full = driver._profile("full")

    assert quick.production_nodes < full.production_nodes
    assert quick.production_raster < full.production_raster
    assert quick.mode_iterations < full.mode_iterations
    assert quick.frequency_iterations < full.frequency_iterations


def test_topology_data_uses_only_the_lowest_frequency() -> None:
    observations = np.ones((24, len(driver.FREQUENCIES_HZ)), dtype=np.complex128)

    data = driver._topology_data(observations)

    assert data.forward_problem.num_frequencies == 1
    assert data.observed_scattered_response.shape == (24, 1)
    assert data.forward_problem.angular_frequencies[0] == 2.0 * np.pi * 0.50e9
