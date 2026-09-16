"""Fast contracts for neural-inverse geometry and stopping diagnostics."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from ordered_boundary import ellipse, fourier_curve

torch = pytest.importorskip("torch")

from sdf_inverse.neural import NeuralRedistanceConfig, NeuralRedistanceResult
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.curve_updates import (
    fit_radial_fourier_curve_state,
    radial_fourier_displacement_basis,
    radial_fourier_state_curve,
)
from sdf_inverse.neural_optimization import (
    AlternatingNeuralInverseConfig,
    SmoothNormalModeUpdate2D,
    _bounded_modal_step,
    _curve_distance,
    _failed_step_outcome,
    _maximum_modal_displacement,
    _radial_spectral_tail_rms,
    _redistance_config_for_iteration,
    _update_meets_convergence_tolerances,
    run_alternating_neural_inverse,
)
from sdf_inverse.optimization import ComplexScatteredData


def _inverse_config() -> AlternatingNeuralInverseConfig:
    return AlternatingNeuralInverseConfig(
        redistance=NeuralRedistanceConfig(
            bounds=((0.0, 0.0), (1.0, 1.0)),
            eikonal_rms_tolerance=0.1,
        ),
        relative_loss_change_tolerance=1.0e-4,
        geometry_change_tolerance_m=5.0e-5,
        eikonal_rms_tolerance=0.15,
    )


def test_curve_change_uses_segments_not_sampling_phase() -> None:
    count = 96
    radius = 0.05
    angles = 2.0 * np.pi * np.arange(count) / count
    first = radius * np.column_stack((np.cos(angles), np.sin(angles)))
    half_node_phase = np.pi / count
    second_angles = angles + half_node_phase
    second = radius * np.column_stack(
        (np.cos(second_angles), np.sin(second_angles))
    )

    # The old nearest-node metric sees half a node spacing as curve motion.
    nearest_node = float(
        np.max(
            np.min(
                np.linalg.norm(first[:, None, :] - second[None, :, :], axis=2),
                axis=1,
            )
        )
    )
    geometric = _curve_distance(first, second)

    assert nearest_node > 1.0e-3
    assert geometric < 5.0e-5
    assert geometric < nearest_node / 20.0
    assert _curve_distance(second, first) == pytest.approx(geometric)
    assert _curve_distance(first, np.roll(first[::-1], 17, axis=0)) < 1.0e-14


def test_redistance_seed_advances_once_per_outer_iteration() -> None:
    base = _inverse_config().redistance

    iteration_two_a = _redistance_config_for_iteration(base, 2)
    iteration_two_b = _redistance_config_for_iteration(base, 2)
    iteration_three = _redistance_config_for_iteration(base, 3)

    assert base.seed == 31415
    assert iteration_two_a == iteration_two_b
    assert iteration_two_a.seed == base.seed + 2
    assert iteration_three.seed == base.seed + 3
    assert iteration_three.seed != iteration_two_a.seed
    with pytest.raises(ValueError, match="iteration"):
        _redistance_config_for_iteration(base, 0)


def test_default_backtracking_reaches_completed_run_k3_sixth_halving() -> None:
    config = _inverse_config()

    # The completed full-band progressive-mode trace first found a valid K=3
    # candidate at this sixth halving.  ``range(max_backtracks + 1)`` must
    # therefore include the full step and every scale through 1/64.
    assert config.max_backtracks == 6
    assert tuple(0.5**index for index in range(config.max_backtracks + 1))[-1] == (
        pytest.approx(1.0 / 64.0)
    )
    # Seven consecutive accepts saturated the former 4 mm cap before the
    # canonical parameterization collapsed in the completed joint run.
    assert config.maximum_modal_field_update_m == pytest.approx(2.0e-3)


def test_optimizer_accepts_first_admissible_candidate_at_sixth_halving(
    monkeypatch,
) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    center = np.array([0.5, 0.5])

    def circle(radius: float):
        cosine = np.zeros((2, 2), dtype=np.float64)
        sine = np.zeros_like(cosine)
        cosine[0] = center
        cosine[1, 0] = radius
        sine[1, 1] = radius
        return fourier_curve(
            cosine,
            sine,
            component_id="sixth-backtrack-test",
        ).discretize(32, require_even=True)

    initial_curve = circle(0.05)
    accepted_curve = circle(0.049)
    raw_coefficient = 6.4e-4
    first_admissible = raw_coefficient / 64.0
    attempted_coefficients: list[float] = []

    def forward_result(curve, response: float):
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[response + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def predictor(model, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        if isinstance(model, SmoothNormalModeUpdate2D):
            coefficient = float(model.coefficients[0].detach().cpu())
            attempted_coefficients.append(coefficient)
            if coefficient > first_admissible * (1.0 + 1.0e-12):
                raise OrderedSDFGeometryError("synthetic candidate is too large")
            return forward_result(accepted_curve, 1.0)
        if getattr(model, "_sixth_backtrack_projection", False):
            return forward_result(accepted_curve, 1.0)
        return forward_result(initial_curve, 2.0)

    def fake_redistance(candidate, direct_curve, config):
        del config
        assert direct_curve is accepted_curve
        candidate._sixth_backtrack_projection = True
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_distillation",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    monkeypatch.setattr(
        optimization_module,
        "_modal_jacobian",
        lambda evaluator, base, config: (
            np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            np.full(3, config.finite_difference_step_m),
        ),
    )
    monkeypatch.setattr(
        optimization_module,
        "_mode_values_at_curve",
        lambda model, points, center, radius_scale, maximum_mode: np.ones(
            (points.shape[0], 3)
        ),
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([raw_coefficient, 0.0, 0.0]),
            damping,
        ),
    )
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", fake_redistance
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )

    redistance = NeuralRedistanceConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        max_steps=2,
        minimum_steps=1,
        warmup_steps=1,
        sample_count=8,
        heldout_sample_count=8,
        eikonal_rms_tolerance=0.1,
    )
    result = run_alternating_neural_inverse(
        torch.nn.Linear(2, 1, dtype=torch.float64),
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1),
            np.array([[0.5 + 0.0j]]),
        ),
        object(),
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=redistance,
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
        ),
        forward_predictor=predictor,
    )

    expected_attempts = raw_coefficient * 0.5 ** np.arange(7)
    np.testing.assert_allclose(attempted_coefficients, expected_attempts)
    assert result.infeasible_evaluation_count == 6
    assert result.redistance_attempt_count == 1
    assert len(result.iterations) == 2
    assert result.final_iteration.modal_step[0] == pytest.approx(first_admissible)
    assert result.initial_iteration.accepted_backtrack_count == 0
    assert result.initial_iteration.accepted_step_predicted_relative_change == 0.0
    assert result.final_iteration.accepted_backtrack_count == 6
    assert result.final_iteration.trust_region_predicted_relative_change == pytest.approx(
        64.0 * result.final_iteration.accepted_step_predicted_relative_change
    )
    assert result.final_iteration.arclength_refit_rms_m == 0.0
    assert result.final_iteration.arclength_refit_maximum_m == 0.0
    final_speed_ratio = float(
        np.max(result.final_curve.speeds) / np.min(result.final_curve.speeds)
    )
    assert result.final_iteration.arclength_speed_ratio_before == pytest.approx(
        final_speed_ratio
    )
    assert result.final_iteration.arclength_speed_ratio_after == pytest.approx(
        final_speed_ratio
    )
    with pytest.raises(ValueError, match="accepted_backtrack_count"):
        replace(result.final_iteration, accepted_backtrack_count=-1)
    with pytest.raises(
        ValueError, match="accepted_step_predicted_relative_change"
    ):
        replace(
            result.final_iteration,
            accepted_step_predicted_relative_change=float("inf"),
        )
    with pytest.raises(ValueError, match="arclength_speed_ratio_after"):
        replace(result.final_iteration, arclength_speed_ratio_after=0.999)


def test_radial_spectral_tail_is_translation_invariant_and_detects_k_plus_one() -> None:
    count = 512
    maximum_mode = 3
    amplitude = 2.0e-3
    angles = 2.0 * np.pi * np.arange(count) / count
    directions = np.column_stack((np.cos(angles), np.sin(angles)))
    translation = np.array([1.7, -0.4])
    circle = translation[None, :] + 0.05 * directions
    ripple = translation[None, :] + (
        0.05 + amplitude * np.cos((maximum_mode + 1) * angles)
    )[:, None] * directions

    assert _radial_spectral_tail_rms(circle, maximum_mode) < 1.0e-14
    assert _radial_spectral_tail_rms(ripple, maximum_mode) == pytest.approx(
        amplitude / np.sqrt(2.0), rel=1.0e-12, abs=1.0e-14
    )
    assert _radial_spectral_tail_rms(ripple, maximum_mode + 1) < 1.0e-14


def test_dense_radial_trust_basis_catches_a_between_node_harmonic_peak() -> None:
    maximum_mode = 5
    node_count = 64
    cap = 2.0e-3
    node_angles = 2.0 * np.pi * np.arange(node_count) / node_count
    dense_count = 64 * (maximum_mode + 1)
    dense_angles = 2.0 * np.pi * np.arange(dense_count) / dense_count
    node_basis = radial_fourier_displacement_basis(
        node_angles, maximum_mode=maximum_mode
    )
    dense_basis = radial_fourier_displacement_basis(
        dense_angles, maximum_mode=maximum_mode
    )

    # k=4 has only sixteen distinct phases on this 64-node solver grid. Put
    # every continuous maximum halfway between its nearest solver nodes.
    phase = np.pi / 16.0
    direction = np.zeros(11)
    direction[7] = np.cos(phase)
    direction[8] = np.sin(phase)
    node_limited = direction * (
        cap / _maximum_modal_displacement(node_basis, direction)
    )
    assert _maximum_modal_displacement(node_basis, node_limited) == pytest.approx(cap)
    assert _maximum_modal_displacement(dense_basis, node_limited) > 1.019 * cap

    config = AlternatingNeuralInverseConfig(
        redistance=NeuralRedistanceConfig(
            bounds=((0.0, 0.0), (1.0, 1.0)),
            eikonal_rms_tolerance=0.1,
        ),
        maximum_mode=maximum_mode,
        maximum_modal_field_update_m=cap,
        max_trust_region_solves=0,
        direct_curve_retraction="radial_fourier",
    )
    bounded, _ = _bounded_modal_step(
        np.eye(11),
        -direction,
        np.ones(11),
        np.zeros(11),
        dense_basis,
        config.initial_damping,
        config,
    )
    assert _maximum_modal_displacement(dense_basis, bounded) <= cap
    assert _maximum_modal_displacement(dense_basis, bounded) == pytest.approx(cap)


def test_radial_inverse_initializes_and_returns_one_authoritative_state(
    monkeypatch,
) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    geometry = OrderedSDFGeometryConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(33, 33),
        projected_samples=32,
        bandwidth=12,
        num_nodes=64,
        arclength_dense_resolution=128,
        validation_resolution=256,
    )
    initial_curve = ellipse(
        (0.5, 0.5), 0.075, 0.045, rotation=0.31
    ).discretize(geometry.num_nodes, require_even=True)

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("radial inverse entered the model predictor")

    def curve_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[0.0 + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
            forward_seconds=0.0,
        )

    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    result = run_alternating_neural_inverse(
        torch.nn.Linear(2, 1, dtype=torch.float64),
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1),
            np.array([[0.0 + 0.0j]]),
        ),
        geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=geometry.bounds,
                eikonal_rms_tolerance=0.1,
            ),
            maximum_mode=5,
            direct_curve_retraction="radial_fourier",
            geometry_change_tolerance_m=5.0e-3,
        ),
        initial_curve=initial_curve,
        initial_representation_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=curve_predictor,
    )

    assert result.converged
    assert result.final_radial_curve_state is not None
    assert result.final_radial_curve_state.maximum_mode == 5
    assert np.array_equal(result.final_curve.points, result.initial_iteration.geometry_points)
    assert _radial_spectral_tail_rms(result.final_curve.points, 5) < 3.0e-16


def test_accepted_radial_step_reuses_probe_forward_and_advances_exact_state(
    monkeypatch,
) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    geometry = OrderedSDFGeometryConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(33, 33),
        projected_samples=32,
        bandwidth=12,
        num_nodes=64,
        arclength_dense_resolution=128,
        validation_resolution=256,
    )
    original = ellipse((0.5, 0.5), 0.05, 0.05).discretize(
        geometry.num_nodes, require_even=True
    )
    initial_state = fit_radial_fourier_curve_state(original, maximum_mode=1)
    initial_curve = radial_fourier_state_curve(
        initial_state, geometry_config=geometry
    )
    curve_calls = []
    latest_direct_curve = None
    trust_bases = []

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("radial inverse entered the model predictor")

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        curve_calls.append(curve)
        center = np.mean(curve.points, axis=0)
        radius = float(np.mean(np.linalg.norm(curve.points - center, axis=1)))
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
            forward_seconds=0.0,
        )

    def accept_without_training(candidate, curve, config):
        nonlocal latest_direct_curve
        del candidate, config
        latest_direct_curve = curve
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_distillation",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    def representation_geometry(model, geometry_config):
        del model, geometry_config
        assert latest_direct_curve is not None
        return SimpleNamespace(curve=latest_direct_curve)

    def bounded_step(
        normal_matrix, gradient, scaling, curvature, basis, damping, config
    ):
        del normal_matrix, gradient, scaling, curvature, config
        trust_bases.append(np.asarray(basis))
        return np.array([-1.0e-3, 0.0, 0.0]), damping

    monkeypatch.setattr(optimization_module, "_bounded_modal_step", bounded_step)
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", accept_without_training
    )
    monkeypatch.setattr(
        optimization_module, "build_ordered_sdf_geometry", representation_geometry
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )

    result = run_alternating_neural_inverse(
        torch.nn.Linear(2, 1, dtype=torch.float64),
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1),
            np.array([[0.045 + 0.0j]]),
        ),
        geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(
                bounds=geometry.bounds,
                max_steps=2,
                minimum_steps=1,
                warmup_steps=1,
                sample_count=8,
                heldout_sample_count=8,
                eikonal_rms_tolerance=0.1,
            ),
            max_iterations=1,
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=0,
            direct_curve_retraction="radial_fourier",
            maximum_redistance_curve_drift_m=1.0e-2,
        ),
        initial_curve=initial_curve,
        initial_representation_curve=initial_curve,
        initial_radial_curve_state=initial_state,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    # Initial + six central finite-difference probes + one accepted line-search
    # probe. Full validation is geometry-only for this exact retraction.
    assert len(curve_calls) == result.total_evaluation_count == 8
    assert [basis.shape for basis in trust_bases] == [(256, 3, 2)]
    assert len(result.iterations) == 2
    assert result.final_radial_curve_state is not None
    assert result.final_radial_curve_state.mean_radius_m == pytest.approx(0.049)
    rebuilt = radial_fourier_state_curve(
        result.final_radial_curve_state, geometry_config=geometry
    )
    np.testing.assert_array_equal(rebuilt.points, result.final_curve.points)
    np.testing.assert_array_equal(
        result.final_curve.points, result.final_iteration.geometry_points
    )
    np.testing.assert_array_equal(result.final_curve.points, curve_calls[-1].points)


def test_spectral_tail_guard_rolls_back_and_reports_rejection(monkeypatch) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    count = 64
    angles = 2.0 * np.pi * np.arange(count) / count
    directions = np.column_stack((np.cos(angles), np.sin(angles)))
    center = np.array([0.5, 0.5])

    def curve(radius: float, ripple: float = 0.0):
        # Cartesian Fourier form of
        #   center + (radius + ripple*cos(2t)) * (cos(t), sin(t)).
        cosine = np.zeros((4, 2), dtype=np.float64)
        sine = np.zeros_like(cosine)
        cosine[0] = center
        cosine[1, 0] = radius + 0.5 * ripple
        cosine[3, 0] = 0.5 * ripple
        sine[1, 1] = radius - 0.5 * ripple
        sine[3, 1] = 0.5 * ripple
        return fourier_curve(
            cosine,
            sine,
            component_id="spectral-tail-test",
        ).discretize(count, require_even=True)

    initial_curve = curve(0.05)
    # The guard belongs to the canonical direct contour.  Projection-only
    # ripple is audited as MLP representation drift and must never replace
    # the inverse state.
    direct_curve = curve(0.051, ripple=1.0e-3)
    projected_curve = curve(0.051, ripple=1.0e-3)
    redistance_seeds: list[int] = []

    def predictor(model, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        if isinstance(model, SmoothNormalModeUpdate2D):
            selected_curve = direct_curve
            response = 1.0
        elif getattr(model, "_spectral_tail_test_projection", False):
            selected_curve = projected_curve
            response = 0.75
        else:
            selected_curve = initial_curve
            response = 2.0
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=selected_curve),
            scattered_response=np.array([[response + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def fake_redistance(candidate, accepted_curve, config):
        assert accepted_curve is direct_curve
        redistance_seeds.append(config.seed)
        candidate._spectral_tail_test_projection = True
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_projection",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    monkeypatch.setattr(optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0))
    monkeypatch.setattr(
        optimization_module,
        "_modal_jacobian",
        lambda evaluator, base, config: (
            np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            np.full(3, config.finite_difference_step_m),
        ),
    )
    monkeypatch.setattr(
        optimization_module,
        "_mode_values_at_curve",
        lambda model, points, center, radius_scale, maximum_mode: np.ones(
            (points.shape[0], 3)
        ),
    )
    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        lambda normal_matrix, gradient, scaling, curvature, basis, damping, config: (
            np.array([1.0e-3, 0.0, 0.0]),
            damping,
        ),
    )
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", fake_redistance
    )

    redistance = NeuralRedistanceConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        max_steps=2,
        minimum_steps=1,
        warmup_steps=1,
        sample_count=8,
        heldout_sample_count=8,
        eikonal_rms_tolerance=0.1,
        seed=40,
    )
    config = AlternatingNeuralInverseConfig(
        redistance=redistance,
        max_iterations=1,
        maximum_mode=1,
        max_damping_trials=1,
        max_backtracks=0,
        maximum_spectral_tail_growth_m=2.0e-4,
    )
    model = torch.nn.Linear(2, 1, dtype=torch.float64)
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    data = ComplexScatteredData(
        SimpleNamespace(num_pairs=1, num_frequencies=1),
        np.array([[0.5 + 0.0j]]),
    )

    result = run_alternating_neural_inverse(
        model,
        data,
        object(),
        solver="kress",
        config=config,
        forward_predictor=predictor,
    )

    assert not result.converged
    assert result.stop_reason == "spectral_tail_growth_limit"
    assert result.spectral_tail_rejection_count == 1
    assert len(result.iterations) == 1
    assert result.initial_iteration.radial_spectral_tail_rms_m < 1.0e-14
    assert result.initial_iteration.radial_spectral_tail_limit_m == pytest.approx(2.0e-4)
    # Reject before paying for a neural fit whose target curve is inadmissible.
    assert redistance_seeds == []
    assert not hasattr(model, "_spectral_tail_test_projection")
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0.0, atol=0.0)


def test_failed_step_diagnostics_distinguish_modal_and_projection_limits() -> None:
    config = _inverse_config()

    assert _failed_step_outcome(
        1.0,
        best_direct_loss=None,
        best_direct_curve_change_m=None,
        best_trial_loss=None,
        best_trial_curve_change_m=None,
        best_trial_predicted_change=None,
        eikonal_rms=0.1,
        config=config,
    ) == (
        False,
        "no_decreasing_modal_step",
    )
    # The best direct step changes both data and geometry by less than their
    # normal convergence gates, but neural projection could not retain it.
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=0.99995,
        best_direct_curve_change_m=4.0e-5,
        best_trial_loss=0.99995,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
    ) == (
        False,
        "representation_limited_stationary",
    )
    # The same micro-step is geometry-limited when larger candidates also hit
    # the dense topology/regularity audit; do not blame MLP projection alone.
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=0.99995,
        best_direct_curve_change_m=4.0e-5,
        best_trial_loss=0.99995,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
        full_validation_rejection_count=1,
    ) == (False, "geometry_limited_stationary")
    # A useful direct update that projection erases is a limitation, not a
    # convergence claim.
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=0.999,
        best_direct_curve_change_m=4.0e-5,
        best_trial_loss=0.999,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-1.0e-3,
        eikonal_rms=0.1,
        config=config,
    ) == (
        False,
        "no_acceptable_mlp_distillation",
    )
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=0.99995,
        best_direct_curve_change_m=8.0e-5,
        best_trial_loss=0.99995,
        best_trial_curve_change_m=8.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
    ) == (
        False,
        "no_acceptable_mlp_distillation",
    )
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=0.99995,
        best_direct_curve_change_m=4.0e-5,
        best_trial_loss=0.99995,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.2,
        config=config,
    ) == (
        False,
        "no_acceptable_mlp_distillation",
    )

    # If no direct descent survives Armijo, convergence is possible only from
    # a genuinely negligible model direction and negligible realised change.
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=None,
        best_direct_curve_change_m=None,
        best_trial_loss=1.00005,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
    ) == (True, "stationary_modal_step")
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=None,
        best_direct_curve_change_m=None,
        best_trial_loss=1.00005,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
        redistance_curve_drift_m=6.0e-5,
    ) == (False, "no_decreasing_modal_step")
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=None,
        best_direct_curve_change_m=None,
        best_trial_loss=1.00005,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-5.0e-5,
        eikonal_rms=0.1,
        config=config,
        maximum_curve_field_residual=6.0e-5,
    ) == (False, "no_decreasing_modal_step")
    assert _failed_step_outcome(
        1.0,
        best_direct_loss=None,
        best_direct_curve_change_m=None,
        best_trial_loss=1.00005,
        best_trial_curve_change_m=4.0e-5,
        best_trial_predicted_change=-1.0e-3,
        eikonal_rms=0.1,
        config=config,
    ) == (False, "no_decreasing_modal_step")


def test_stationarity_requires_small_model_direction_and_representation_drift() -> None:
    config = _inverse_config()
    common = dict(
        previous_loss=1.0,
        updated_loss=0.99995,
        curve_change_m=4.0e-5,
        eikonal_rms=0.1,
        config=config,
    )

    assert _update_meets_convergence_tolerances(
        **common,
        redistance_curve_drift_m=4.0e-5,
        trust_region_predicted_change=-5.0e-5,
    )
    assert not _update_meets_convergence_tolerances(
        **common,
        redistance_curve_drift_m=6.0e-5,
        trust_region_predicted_change=-5.0e-5,
    )
    assert not _update_meets_convergence_tolerances(
        **common,
        redistance_curve_drift_m=4.0e-5,
        trust_region_predicted_change=-1.0e-3,
    )
    assert not _update_meets_convergence_tolerances(
        **common,
        redistance_curve_drift_m=4.0e-5,
        trust_region_predicted_change=-5.0e-5,
        maximum_curve_field_residual=6.0e-5,
    )


@pytest.mark.parametrize(
    (
        "representation_shift_m",
        "modal_steps_m",
        "reject_full_step",
        "expected_converged",
        "expected_stop_reason",
        "expected_accepted_updates",
        "expected_dampings",
    ),
    (
        pytest.param(
            0.0,
            (-1.0e-5,) * 4,
            False,
            True,
            "stable_data_geometry_representation_and_eikonal",
            2,
            (1.0e-3, 3.0e-4),
            id="complete-convergence",
        ),
        pytest.param(
            1.0e-4,
            (-1.0e-5,) * 4,
            False,
            False,
            "representation_limited_stationary",
            2,
            (1.0e-3, 3.0e-4),
            id="consecutive-representation-limit",
        ),
        pytest.param(
            1.0e-4,
            (-1.0e-5, -1.0e-4, -1.0e-5, -1.0e-5, -1.0e-5),
            False,
            False,
            "representation_limited_stationary",
            4,
            (1.0e-3, 3.0e-4, 9.0e-5, 2.7e-5),
            id="nonstationary-update-resets-counter",
        ),
        pytest.param(
            1.0e-4,
            (-1.0e-5,) * 4,
            True,
            False,
            "geometry_limited_stationary",
            2,
            (1.0e-3, 1.0e-3),
            id="consecutive-geometry-limit-retains-damping",
        ),
    ),
)
def test_canonical_stationarity_preserves_convergence_or_reports_representation_limit(
    monkeypatch,
    representation_shift_m: float,
    modal_steps_m: tuple[float, ...],
    reject_full_step: bool,
    expected_converged: bool,
    expected_stop_reason: str,
    expected_accepted_updates: int,
    expected_dampings: tuple[float, ...],
) -> None:
    import sdf_inverse.neural_optimization as optimization_module

    count = 32
    center = np.array([0.5, 0.5])

    def circular_curve(curve_center: np.ndarray, radius: float):
        cosine = np.zeros((2, 2), dtype=np.float64)
        sine = np.zeros_like(cosine)
        cosine[0] = curve_center
        cosine[1, 0] = radius
        sine[1, 1] = radius
        return fourier_curve(
            cosine,
            sine,
            component_id="canonical-stationarity-test",
        ).discretize(count, require_even=True)

    initial_curve = circular_curve(center, 0.05)
    latest_direct_curve = initial_curve

    def radius_predictor(curve, forward_problem, geometry_config, *, solver):
        del forward_problem, geometry_config, solver
        radius = np.sqrt(curve.signed_area / np.pi)
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[radius + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    def forbidden_model_predictor(*args, **kwargs):
        del args, kwargs
        raise AssertionError("direct curve path must not call model predictor")

    def fake_redistance(candidate, direct_curve, config):
        nonlocal latest_direct_curve
        del candidate, config
        latest_direct_curve = direct_curve
        return NeuralRedistanceResult(
            converged=True,
            steps=1,
            stop_reason="test_distillation",
            initial_total_loss=1.0,
            final_total_loss=0.5,
            final_distance_rms_m=0.0,
            final_heldout_distance_rms_m=0.0,
            final_boundary_max_abs_m=0.0,
            final_eikonal_rms=0.0,
            final_eikonal_maximum_deviation=0.0,
            loss_history=np.array([0.5]),
            diagnostics={},
        )

    def representation_geometry(model, geometry_config):
        del model, geometry_config
        radius = np.sqrt(latest_direct_curve.signed_area / np.pi)
        direct_center = np.mean(latest_direct_curve.points, axis=0)
        shifted_center = direct_center + np.array([representation_shift_m, 0.0])
        return SimpleNamespace(curve=circular_curve(shifted_center, radius))

    monkeypatch.setattr(
        optimization_module,
        "_modal_jacobian",
        lambda evaluator, base, config: (
            np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            np.full(3, config.finite_difference_step_m),
        ),
    )
    modal_steps = iter(modal_steps_m)

    def bounded_modal_step(
        normal_matrix, gradient, scaling, curvature, basis, damping, config
    ):
        del normal_matrix, gradient, scaling, curvature, basis, config
        return np.array([next(modal_steps), 0.0, 0.0]), damping

    monkeypatch.setattr(
        optimization_module,
        "_bounded_modal_step",
        bounded_modal_step,
    )
    monkeypatch.setattr(
        optimization_module, "redistance_neural_sdf_to_curve", fake_redistance
    )
    monkeypatch.setattr(
        optimization_module, "build_ordered_sdf_geometry", representation_geometry
    )
    monkeypatch.setattr(
        optimization_module, "_field_audit", lambda *args: (0.0, 0.0, 0.0)
    )
    real_curve_update = optimization_module.apply_normal_mode_update
    validated_updates = []

    def reject_only_the_full_candidate(*args, **kwargs):
        coefficients = np.asarray(args[1], dtype=np.float64)
        if (
            reject_full_step
            and kwargs["full_validation"]
            and abs(coefficients[0]) > 7.5e-6
        ):
            raise OrderedSDFGeometryError("forced full-step geometry barrier")
        update = real_curve_update(*args, **kwargs)
        if kwargs["full_validation"]:
            validated_updates.append(update)
        return update

    monkeypatch.setattr(
        optimization_module,
        "apply_normal_mode_update",
        reject_only_the_full_candidate,
    )

    geometry = OrderedSDFGeometryConfig(
        bounds=((0.0, 0.0), (1.0, 1.0)),
        grid_shape=(33, 33),
        projected_samples=16,
        bandwidth=4,
        num_nodes=count,
        arclength_dense_resolution=64,
        validation_resolution=64,
    )
    redistance = NeuralRedistanceConfig(
        bounds=geometry.bounds,
        max_steps=2,
        minimum_steps=1,
        warmup_steps=1,
        sample_count=8,
        heldout_sample_count=8,
        eikonal_rms_tolerance=0.1,
    )
    model = torch.nn.Linear(2, 1, dtype=torch.float64)
    result = run_alternating_neural_inverse(
        model,
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1),
            np.array([[0.045 + 0.0j]]),
        ),
        geometry,
        solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=redistance,
            max_iterations=len(modal_steps_m),
            maximum_mode=1,
            max_damping_trials=1,
            max_backtracks=1 if reject_full_step else 0,
            relative_loss_change_tolerance=1.0e-2,
            geometry_change_tolerance_m=2.0e-5,
            maximum_redistance_curve_drift_m=1.0e-3,
            consecutive_convergence_iterations=2,
        ),
        initial_curve=initial_curve,
        initial_representation_curve=initial_curve,
        forward_predictor=forbidden_model_predictor,
        curve_forward_predictor=radius_predictor,
    )

    assert result.converged is expected_converged
    assert result.stop_reason == expected_stop_reason
    # In the reset case, a nonstationary middle update must clear both
    # consecutive-stationarity counters; only the following two stationary
    # updates may terminate.
    assert len(result.iterations) == expected_accepted_updates + 1
    assert result.redistance_attempt_count == expected_accepted_updates
    accepted_scale = 0.5 if reject_full_step else 1.0
    np.testing.assert_allclose(
        [record.modal_step[0] for record in result.iterations[1:]],
        np.asarray(modal_steps_m[:expected_accepted_updates]) * accepted_scale,
    )
    np.testing.assert_allclose(
        [record.applied_damping for record in result.iterations[1:]],
        expected_dampings,
    )
    assert [
        record.accepted_backtrack_count for record in result.iterations[1:]
    ] == [int(reject_full_step)] * expected_accepted_updates
    assert result.full_validation_rejection_count == (
        expected_accepted_updates if reject_full_step else 0
    )
    assert len(validated_updates) == expected_accepted_updates
    initial_speed_ratio = float(
        np.max(initial_curve.speeds) / np.min(initial_curve.speeds)
    )
    assert result.initial_iteration.arclength_refit_rms_m == 0.0
    assert result.initial_iteration.arclength_refit_maximum_m == 0.0
    assert result.initial_iteration.arclength_speed_ratio_before == pytest.approx(
        initial_speed_ratio
    )
    assert result.initial_iteration.arclength_speed_ratio_after == pytest.approx(
        initial_speed_ratio
    )
    for record, update in zip(result.iterations[1:], validated_updates):
        assert record.arclength_refit_rms_m == pytest.approx(
            update.arclength_refit_rms_m
        )
        assert record.arclength_refit_maximum_m == pytest.approx(
            update.arclength_refit_maximum_m
        )
        assert record.arclength_speed_ratio_before == pytest.approx(
            update.arclength_speed_ratio_before
        )
        assert record.arclength_speed_ratio_after == pytest.approx(
            update.arclength_speed_ratio_after
        )
