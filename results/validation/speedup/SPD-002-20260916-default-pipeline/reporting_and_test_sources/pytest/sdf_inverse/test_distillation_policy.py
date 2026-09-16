"""Physics-state ownership and explicit neural export policy regressions."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle
from sdf_inverse import (
    AlternatingNeuralInverseConfig, ComplexScatteredData, MaterialSpec,
    NeuralRedistanceConfig, NeuralRedistanceResult, OrderedSDFGeometryConfig,
    OrderedSDFGeometryError, PairedForwardProblem, RadialFourierCurveState,
    radial_fourier_parameterization, radial_fourier_state_curve,
    run_alternating_neural_inverse,
)
from sdf_inverse.neural_optimization import export_neural_sdf_representation
import sdf_inverse.neural_optimization as inverse


class _ForbiddenField(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.value = torch.nn.Parameter(torch.tensor(0.0, dtype=torch.float64))

    def forward(self, points):
        raise AssertionError("the canonical reconstruction evaluated its neural field")


def _arguments(policy, *, observed_radius=0.045):
    geometry = OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)), grid_shape=(33, 33),
        projected_samples=32, bandwidth=6, num_nodes=32,
        arclength_dense_resolution=64, validation_resolution=64,
    )
    state = RadialFourierCurveState(
        center=np.array([0.5, 0.5]), radius_cosine_coefficients=np.array([0.05, 0.0]),
        radius_sine_coefficients=np.zeros(2), component_id="target",
    )
    problem = PairedForwardProblem(
        source_points=np.array([[0.1, 0.1]]), receiver_points=np.array([[0.2, 0.2]]),
        angular_frequencies=np.array([1.0e9]), source_strengths=1.0 + 0.0j,
        exterior=MaterialSpec(epsr=1.0), interior=MaterialSpec(epsr=2.0),
        eps0=8.8541878128e-12, mu0=1.25663706212e-6,
    )

    def radius_predictor(curve, *args, **kwargs):
        return SimpleNamespace(
            geometry_build=SimpleNamespace(curve=curve),
            scattered_response=np.array([[np.sqrt(curve.signed_area / np.pi) + 0.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
        )

    return dict(
        model=_ForbiddenField(), data=ComplexScatteredData(problem, np.array([[observed_radius + 0.0j]])),
        geometry_config=geometry, solver="kress",
        config=AlternatingNeuralInverseConfig(
            redistance=NeuralRedistanceConfig(bounds=geometry.bounds, eikonal_rms_tolerance=0.15),
            maximum_mode=1, max_iterations=2, max_backtracks=0, max_damping_trials=1,
            maximum_modal_field_update_m=0.001, direct_curve_retraction="radial_fourier",
            distillation_policy=policy, representation_audit_num_nodes=64,
            maximum_representation_audit_num_nodes=256,
        ),
        initial_curve=radial_fourier_state_curve(state, geometry_config=geometry),
        initial_radial_curve_state=state,
        curve_forward_predictor=radius_predictor,
    )


def _fit(*, converged=True):
    return NeuralRedistanceResult(
        converged=converged, steps=1, stop_reason="synthetic_fit",
        initial_total_loss=1.0, final_total_loss=0.5,
        final_distance_rms_m=0.0, final_heldout_distance_rms_m=0.0,
        final_boundary_max_abs_m=0.0, final_eikonal_rms=0.0,
        final_eikonal_maximum_deviation=0.0, loss_history=np.array([0.5]), diagnostics={},
    )


def _mock_export(monkeypatch, *, failure=None, events=None):
    events = [] if events is None else events
    continuous = []

    def train(model, curve, config, *, continuous_curve=None):
        assert config.distance_target == "smooth_curve"
        assert continuous_curve is not None
        events.append("train")
        continuous.append(continuous_curve)
        with torch.no_grad():
            model.value.fill_(7.0)
        if failure == "numerical":
            raise FloatingPointError("synthetic optimizer breakdown")
        if failure == "programming":
            raise RuntimeError("synthetic programming error")
        return _fit(converged=failure != "fit")

    def extract(model, geometry):
        events.append("extract")
        if failure == "topology":
            raise OrderedSDFGeometryError("synthetic multiple components")
        if failure == "drift":
            return SimpleNamespace(curve=circle((0.52, 0.5), 0.05).discretize(geometry.num_nodes))
        return SimpleNamespace(curve=continuous[-1].discretize(geometry.num_nodes))

    monkeypatch.setattr(inverse, "redistance_neural_sdf_to_curve", train)
    monkeypatch.setattr(inverse, "build_ordered_sdf_geometry", extract)
    monkeypatch.setattr(inverse, "_field_audit", lambda *args: (1.0, 1.0, 0.0) if failure == "eikonal" else (0.0, 0.0, 0.0))
    return events


def test_curve_only_never_evaluates_trains_or_audits_the_neural_field(monkeypatch):
    arguments = _arguments("curve_only")

    def forbidden(*args, **kwargs):
        raise AssertionError("curve-only mode entered neural work")

    for name in ("_field_audit", "_audit_points", "build_ordered_sdf_geometry", "redistance_neural_sdf_to_curve"):
        monkeypatch.setattr(inverse, name, forbidden)
    result = run_alternating_neural_inverse(**arguments)
    assert len(result.iterations) > 1
    assert result.final_iteration.loss < result.initial_iteration.loss
    assert result.final_representation_curve is None
    assert result.representation_status == result.representation_stop_reason == "not_requested"
    assert not result.representation_evaluated
    assert result.redistance_attempt_count == result.total_redistance_step_count == 0
    assert arguments["model"].value.item() == 0.0
    for iteration in result.iterations:
        assert not iteration.representation_evaluated
        assert iteration.redistance_curve_drift_m is None
        assert iteration.eikonal_rms is None
        assert iteration.eikonal_maximum_deviation is None
        assert iteration.maximum_curve_field_residual is None
    with pytest.raises(ValueError, match="must be None"):
        replace(result.final_iteration, eikonal_rms=0.0)


def test_curve_only_can_use_a_parameterless_placeholder_for_the_unused_network():
    arguments = _arguments("curve_only")
    arguments["model"] = torch.nn.Identity()
    result = run_alternating_neural_inverse(**arguments)
    assert len(result.iterations) > 1
    assert not result.representation_evaluated


def test_export_only_preserves_the_curve_only_trajectory_and_trains_once_at_end(monkeypatch):
    control = run_alternating_neural_inverse(**_arguments("curve_only"))
    arguments = _arguments("export_only")
    events = _mock_export(monkeypatch)
    result = run_alternating_neural_inverse(
        **arguments, progress_callback=lambda record: events.append(f"iteration_{record.iteration}")
    )
    assert [record.loss for record in result.iterations] == [record.loss for record in control.iterations]
    for first, second in zip(result.iterations, control.iterations):
        np.testing.assert_array_equal(first.geometry_points, second.geometry_points)
    assert events.count("train") == 1
    assert events.index("train") > events.index(f"iteration_{len(result.iterations) - 1}")
    assert result.representation_status == "passed"
    assert result.reconstruction_converged == control.converged
    assert result.reconstruction_stop_reason == control.stop_reason
    assert result.export_result.drift_m == 0.0
    assert result.export_result.audit_num_nodes == 128
    assert result.export_result.curve.num_nodes == arguments["geometry_config"].num_nodes
    assert result.export_seconds > 0.0
    assert result.total_seconds == result.reconstruction_seconds + result.export_seconds
    assert arguments["model"].value.item() == 7.0
    assert all(record.eikonal_rms is None for record in result.iterations)


@pytest.mark.parametrize("failure", ["fit", "topology", "drift", "eikonal", "numerical"])
def test_failed_export_preserves_converged_reconstruction_and_model(monkeypatch, failure):
    arguments = _arguments("export_only", observed_radius=0.05)
    _mock_export(monkeypatch, failure=failure)
    result = run_alternating_neural_inverse(**arguments)
    assert result.converged and result.reconstruction_converged
    assert result.representation_status == "failed"
    assert not result.requested_delivery_complete
    assert result.final_representation_curve is None
    assert result.export_result.curve is None
    assert arguments["model"].value.item() == 0.0
    np.testing.assert_array_equal(result.final_curve.points, arguments["initial_curve"].points)


def test_export_does_not_suppress_programming_errors(monkeypatch):
    arguments = _arguments("export_only", observed_radius=0.05)
    _mock_export(monkeypatch, failure="programming")
    with pytest.raises(RuntimeError, match="programming error"):
        run_alternating_neural_inverse(**arguments)
    assert arguments["model"].value.item() == 0.0


def test_explicit_export_requires_continuous_producer_before_training(monkeypatch):
    arguments = _arguments("curve_only")
    _mock_export(monkeypatch)
    result = export_neural_sdf_representation(
        arguments["model"], arguments["initial_curve"], arguments["geometry_config"],
        config=arguments["config"],
    )
    assert result.status == "failed"
    assert result.stop_reason == "continuous_curve_required"
    assert not result.representation_evaluated
    assert result.training_attempt_count == 0


def test_curve_only_initialization_from_an_sdf_still_extracts_it(monkeypatch):
    arguments = _arguments("curve_only", observed_radius=0.05)
    curve = arguments.pop("initial_curve")
    arguments.pop("initial_radial_curve_state")
    arguments["config"] = replace(arguments["config"], direct_curve_retraction="normal")
    import sdf_inverse.forward as forward
    calls = []

    def initial_predictor(model, *args, **kwargs):
        calls.append(model)
        return arguments["curve_forward_predictor"](curve)

    monkeypatch.setattr(forward, "predict_paired_response", initial_predictor)
    result = run_alternating_neural_inverse(**arguments)
    assert calls == [arguments["model"]]
    assert result.reconstruction_converged
    assert not result.representation_evaluated
    assert result.final_representation_curve is None


def test_default_policy_preserves_strict_initial_representation_audit(monkeypatch):
    arguments = _arguments("legacy_strict", observed_radius=0.05)
    assert AlternatingNeuralInverseConfig(
        redistance=arguments["config"].redistance
    ).distillation_policy == "legacy_strict"

    def reject(*args, **kwargs):
        raise OrderedSDFGeometryError("initial neural topology rejected")

    monkeypatch.setattr(inverse, "build_ordered_sdf_geometry", reject)
    with pytest.raises(OrderedSDFGeometryError, match="initial neural topology"):
        run_alternating_neural_inverse(**arguments)


def test_export_drift_quality_gate_is_independent_of_step_safety_cap(monkeypatch):
    arguments = _arguments("export_only", observed_radius=0.05)
    _mock_export(monkeypatch)
    shifted = circle((0.5003, 0.5), 0.05)
    monkeypatch.setattr(
        inverse, "build_ordered_sdf_geometry",
        lambda model, geometry: SimpleNamespace(curve=shifted.discretize(geometry.num_nodes)),
    )
    result = run_alternating_neural_inverse(**arguments)
    assert result.export_result.drift_m == pytest.approx(0.0003)
    assert result.export_result.drift_m < arguments["config"].maximum_redistance_curve_drift_m
    assert result.representation_status == "failed"
    assert result.representation_stop_reason == "representation_drift_tolerance"
    assert result.final_representation_curve is None


def test_continuous_distance_refinement_failure_is_an_export_failure(monkeypatch):
    from sdf_inverse.continuous_distance import ContinuousDistanceRefinementError
    arguments = _arguments("export_only", observed_radius=0.05)

    def unavailable_distance(*args, **kwargs):
        raise ContinuousDistanceRefinementError("target accuracy budget exhausted")

    monkeypatch.setattr(inverse, "redistance_neural_sdf_to_curve", unavailable_distance)
    result = run_alternating_neural_inverse(**arguments)
    assert result.reconstruction_converged
    assert result.representation_status == "failed"
    assert not result.representation_evaluated
    assert result.export_result.fit is None
    assert result.export_result.eikonal_rms is None
    assert "accuracy budget" in result.representation_stop_reason


def test_real_circle_export_uses_smooth_target_and_independent_drift_grid():
    from sdf_inverse import SmoothMLPSDF2D
    arguments = _arguments("curve_only", observed_radius=0.05)
    model = SmoothMLPSDF2D(
        bounds=arguments["geometry_config"].bounds,
        hidden_features=4, hidden_layers=1, fourier_frequencies=(1.0,),
        geometric_center=(0.5, 0.5), geometric_radius=0.05,
    )
    redistance = replace(
        arguments["config"].redistance, max_steps=1, minimum_steps=1, warmup_steps=0,
        sample_count=16, heldout_sample_count=16, smooth_boundary_sample_count=64,
        distance_initial_samples=32, distance_maximum_samples=128,
    )
    result = export_neural_sdf_representation(
        model, arguments["initial_curve"], arguments["geometry_config"],
        continuous_curve=radial_fourier_parameterization(arguments["initial_radial_curve_state"]),
        config=replace(
            arguments["config"], redistance=redistance,
            representation_audit_num_nodes=128, maximum_representation_audit_num_nodes=1024,
        ),
    )
    assert result.status == "passed", result.stop_reason
    assert result.fit.steps == 0
    assert result.fit.diagnostics["smooth_distance_target"] == 1.0
    assert result.audit_num_nodes > arguments["geometry_config"].num_nodes
    assert result.drift_refinement_difference_m <= 1.0e-6


def test_export_response_normalization_overflow_preserves_reconstruction(monkeypatch):
    arguments = _arguments("export_only", observed_radius=0.05)
    events = _mock_export(monkeypatch)
    ordinary_predictor = arguments["curve_forward_predictor"]

    def predictor(curve, *args, **kwargs):
        result = ordinary_predictor(curve)
        if "train" in events:
            # Finite amplitudes pass the forward-result finite-value contract,
            # but their norm can still overflow during residual normalization.
            result.scattered_response = np.array([[1.0e308 + 0.0j]])
        return result

    arguments["curve_forward_predictor"] = predictor
    with np.errstate(over="ignore", invalid="ignore"):
        result = run_alternating_neural_inverse(**arguments)
    assert result.reconstruction_converged
    assert result.representation_status == "failed"
    assert "representation_forward_failure" in result.representation_stop_reason
    assert result.export_result.relative_l2_error is None
    assert result.final_representation_curve is None
    assert arguments["model"].value.item() == 0.0


@pytest.mark.parametrize("distillation_succeeds", [False, True])
def test_strict_reconstruction_convergence_requires_verified_accepted_stationarity(
    monkeypatch, distillation_succeeds
):
    arguments = _arguments("legacy_strict")
    arguments["initial_representation_curve"] = arguments["initial_curve"]
    arguments["config"] = replace(
        arguments["config"], relative_loss_change_tolerance=0.01,
        geometry_change_tolerance_m=2.0e-5,
    )
    trained_curves = []

    def train(model, curve, config):
        trained_curves.append(curve)
        return _fit(converged=distillation_succeeds)

    def extract(model, geometry):
        radius = np.sqrt(trained_curves[-1].signed_area / np.pi)
        return SimpleNamespace(curve=circle((0.5001, 0.5), radius).discretize(geometry.num_nodes))

    monkeypatch.setattr(inverse, "redistance_neural_sdf_to_curve", train)
    monkeypatch.setattr(inverse, "build_ordered_sdf_geometry", extract)
    monkeypatch.setattr(inverse, "_field_audit", lambda *args: (0.0, 0.0, 0.0))
    monkeypatch.setattr(
        inverse, "_bounded_modal_step",
        lambda normal, gradient, scaling, curvature, basis, damping, config: (
            np.array([-1.0e-5, 0.0, 0.0]), damping,
        ),
    )
    result = run_alternating_neural_inverse(**arguments)
    # Both historical paths use this legacy label. Only the path with two
    # accepted stationary states verifies canonical reconstruction convergence.
    assert result.stop_reason == "representation_limited_stationary"
    assert not result.converged
    assert result.reconstruction_converged is distillation_succeeds
    assert len(result.iterations) == (3 if distillation_succeeds else 1)
