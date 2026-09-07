"""Lightweight fixed-chart metric and bounded comparison regressions."""

from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pytest
import torch

from sdf_inverse.curve_updates import RadialFourierCurveState, radial_fourier_parameterization
from sdf_inverse.neural import SmoothMLPSDF2D
from sdf_inverse.neural_metric import (
    FrozenCurveMetric, build_frozen_curve_metric, radial_chart_directions,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import run_neural_metric_comparison as driver


def _curve(nodes=32):
    return radial_fourier_parameterization(driver._initial_state()).discretize(nodes, require_even=True)


def test_radial_coefficient_jets_match_the_actual_linear_retraction():
    state = driver._truth_state("star")
    parameters = np.arange(40)*2*np.pi/40
    directions = radial_chart_directions(parameters, 5)
    step = 1e-5
    for index, direction in enumerate(directions):
        increment = np.eye(11)[index]*step
        high = radial_fourier_parameterization(state.incremented(increment)).evaluate(parameters)
        low = radial_fourier_parameterization(state.incremented(-increment)).evaluate(parameters)
        for name in ("points", "first_derivatives", "second_derivatives", "third_derivatives"):
            np.testing.assert_allclose(getattr(direction, name),
                (getattr(high, name)-getattr(low, name))/(2*step), rtol=1e-10, atol=2e-10)


@pytest.mark.parametrize("kind", ["identity", "sobolev", "neural"])
def test_normalized_active_metrics_and_exact_initial_head_accounting(kind):
    curve = _curve()
    model = (SmoothMLPSDF2D(bounds=driver.BOUNDS, geometric_center=driver.INITIAL_CENTER,
                           geometric_radius=driver.INITIAL_RADIUS, seed=0) if kind == "neural" else None)
    before = [parameter.detach().clone() for parameter in model.parameters()] if model is not None else []
    metric = build_frozen_curve_metric(curve, kind=kind, model=model)
    expected_mass = np.diag(np.r_[2*np.pi*driver.INITIAL_RADIUS, np.full(10, np.pi*driver.INITIAL_RADIUS)])
    np.testing.assert_allclose(metric.mass_matrix, expected_mass, atol=2e-16)
    for mode in (1, 3, 5):
        coefficient, whitened, spectrum = metric.active_matrices(mode)
        assert np.isclose(np.trace(whitened), 1+2*mode)
        assert spectrum[0] >= 1e-3-1e-14
        gradient = np.arange(1., 2*mode+2)
        displacement = metric.descent_direction(gradient, maximum_mode=mode)
        assert np.dot(gradient, displacement) < 0
        np.testing.assert_allclose(displacement, -coefficient @ gradient)
        assert not coefficient.flags.writeable
    if model is not None:
        assert metric.diagnostics["parameter_count"] == 5441
        assert metric.diagnostics["active_parameter_columns"] == 65
        assert metric.diagnostics["maximum_initial_field_residual_m"] < 1e-15
        assert metric.diagnostics["model_training_steps"] == 0
        for old, current in zip(before, model.parameters()):
            assert torch.equal(old, current)
    else:
        assert metric.diagnostics["parameter_count"] is None
        assert metric.diagnostics["model_jacobian_seconds"] is None


def test_active_covariance_is_reprojected_with_its_own_nondiagonal_mass():
    rng = np.random.default_rng(4)
    q = rng.normal(size=(11, 11))
    mass = q @ q.T + np.eye(11)
    q = rng.normal(size=(11, 13))
    covariance = q @ q.T
    metric = FrozenCurveMetric("neural", 5, mass, covariance, .001, .35, {})
    coefficient, _, _ = metric.active_matrices(2)
    values, vectors = np.linalg.eigh(mass[:5, :5])
    inverse_sqrt = (vectors/np.sqrt(values)) @ vectors.T
    raw = inverse_sqrt @ covariance[:5, :5] @ inverse_sqrt
    expected = inverse_sqrt @ (.999*5*raw/np.trace(raw)+.001*np.eye(5)) @ inverse_sqrt
    np.testing.assert_allclose(coefficient, expected, rtol=1e-12, atol=1e-13)


def test_stationarity_norm_uses_current_geometry_but_not_chosen_update_metric():
    initial = _curve()
    current = radial_fourier_parameterization(driver._truth_state("star")).discretize(32, require_even=True)
    identity = build_frozen_curve_metric(initial, kind="identity")
    smoother = build_frozen_curve_metric(initial, kind="sobolev")
    gradient = np.arange(1., 12.)
    assert identity.covector_norm(gradient, curve=current) == smoother.covector_norm(gradient, curve=current)
    assert identity.covector_norm(gradient, curve=current) != identity.covector_norm(gradient)


def test_neural_zero_mismatch_and_explicit_model_queries_are_rejected():
    model = SmoothMLPSDF2D(bounds=driver.BOUNDS, geometric_center=driver.INITIAL_CENTER,
                         geometric_radius=driver.INITIAL_RADIUS+.001)
    with pytest.raises(ValueError, match="does not match"):
        build_frozen_curve_metric(_curve(), kind="neural", model=model)
    with pytest.raises(ValueError, match="must not receive"):
        build_frozen_curve_metric(_curve(), kind="identity", model=model)


def test_normal_step_cap_uses_current_non_circular_normals():
    state = driver._truth_state("star")
    config = driver.ComparisonConfig(normal_audit_nodes=1024)
    step = np.r_[.05, .02, -.01, np.zeros(6), .1, .04]
    capped, maximum = driver._normal_cap(state, step, 5, config)
    assert maximum <= config.maximum_normal_step_m*(1+1e-14)
    parameters = np.arange(config.normal_audit_nodes)*2*np.pi/config.normal_audit_nodes
    before = radial_fourier_parameterization(state).evaluate(parameters)
    after = radial_fourier_parameterization(state.incremented(capped)).evaluate(parameters)
    first = before.first_derivatives
    normal = np.column_stack((first[:, 1], -first[:, 0]))/np.linalg.norm(first, axis=1)[:, None]
    observed = np.max(np.abs(np.sum((after.points-before.points)*normal, axis=1)))
    np.testing.assert_allclose(observed, maximum, rtol=1e-11)


def _small_config(**changes):
    base = driver.ComparisonConfig(stages=(driver.Stage((.5,), 16, 1, 0),), metric_nodes=16,
                                   final_audit_nodes=(16, 32), forward_solve_cap=4)
    return replace(base, **changes)


@pytest.mark.parametrize("budget,perfect,reason,converged", [
    (4, False, "iteration_budget", False),
    (0, False, "forward_budget", False),
    (4, True, "loss_tolerance", True),
])
def test_budget_exits_are_not_convergence(budget, perfect, reason, converged):
    config = _small_config(forward_solve_cap=budget)
    acquisition = driver._acquisition()
    forwards = driver._forward(_curve(16), (.5,), acquisition, driver._work())
    observed = driver._prediction(forwards)
    if not perfect:
        observed = observed*1.5
    state, result, arrays = driver._run_arm("circle", "identity", None, observed, acquisition, config)
    assert result["stop_reason"] == reason
    assert result["converged"] is converged
    assert result["optimization_work"]["forward_solves"] <= budget
    np.testing.assert_array_equal(driver._state_vector(state), driver._state_vector(driver._initial_state()))
    assert "mass_matrix" in arrays
    assert result["metric"]["model_training_steps"] == 0


def test_one_accepted_true_objective_step_keeps_armijo_and_budget_labels():
    config = _small_config(stages=(driver.Stage((.5,), 16, 1, 1),), loss_tolerance=1e-14)
    acquisition = driver._acquisition()
    observed, reference = driver._independent_observations("circle", (.5,), acquisition, config)
    assert reference["maximum_mode"] == 64 and reference["audit_maximum_mode"] == 72
    state, result, _ = driver._run_arm("circle", "identity", None, observed, acquisition, config)
    assert result["accepted_steps"] == 1
    assert result["history"][-1]["loss"] < result["history"][0]["loss"]
    assert result["history"][-1]["maximum_normal_step_m"] <= config.maximum_normal_step_m*(1+1e-14)
    assert result["converged"] is False
    assert result["stop_reason"] == "iteration_budget"
    assert result["optimization_work"]["adjoint_solves"] == 1
    assert result["optimization_work"]["directional_operator_assemblies"] == 3


def test_frozen_metric_never_queries_model_in_reconstruction(monkeypatch):
    config = _small_config(stages=(driver.Stage((.5,), 16, 1, 1),), loss_tolerance=1e-14)
    observed, _ = driver._independent_observations("circle", (.5,), driver._acquisition(), config)
    original = driver.build_frozen_curve_metric
    def build_then_disable(*args, **kwargs):
        metric = original(*args, **kwargs)
        def unexpected_query(*args, **kwargs):
            raise AssertionError("Frozen reconstruction cannot query the neural model.")
        monkeypatch.setattr(SmoothMLPSDF2D, "forward", unexpected_query)
        return metric
    monkeypatch.setattr(driver, "build_frozen_curve_metric", build_then_disable)
    _, result, _ = driver._run_arm("circle", "neural", 0, observed, driver._acquisition(), config)
    assert result["accepted_steps"] == 1
    assert result["model_queries_after_initialization"] == 0


def test_physics_qualification_is_independent_of_optimization_stop(monkeypatch):
    config = _small_config(final_self_refinement_tolerance=1e-6)
    calls = []
    def fake_forward(curve, frequencies, acquisition, work, **kwargs):
        calls.append(curve.num_nodes)
        return np.ones((12, len(frequencies)), complex)*(1+1/curve.num_nodes)
    monkeypatch.setattr(driver, "_forward", fake_forward)
    monkeypatch.setattr(driver, "_prediction", lambda values: values)
    result = driver._qualify(driver._initial_state(), driver._truth_state("circle"),
        np.ones((12, 1)), np.ones((12, 1)), driver._acquisition(), driver._acquisition(heldout=True), config)
    assert result["physics_qualified"] is False
    assert result["training_physics_qualified"] is False
    assert result["heldout_physics_qualified"] is False


def test_failed_line_search_preserves_state_and_does_not_claim_convergence(monkeypatch):
    config = _small_config(stages=(driver.Stage((.5,), 16, 1, 1),), loss_tolerance=1e-14)
    observed, _ = driver._independent_observations("circle", (.5,), driver._acquisition(), config)
    def invalid_update(*args, **kwargs):
        raise driver.OrderedSDFGeometryError("controlled invalid trial")
    monkeypatch.setattr(driver, "apply_radial_fourier_update", invalid_update)
    state, result, _ = driver._run_arm("circle", "identity", None, observed, driver._acquisition(), config)
    assert result["stop_reason"] == "line_search_failed"
    assert result["converged"] is False
    assert result["optimization_work"]["invalid_geometry_trials"] == config.maximum_backtracks+1
    np.testing.assert_array_equal(driver._state_vector(state), driver._state_vector(driver._initial_state()))


def test_observation_checkpoint_survives_unexpected_reconstruction_error(monkeypatch, tmp_path):
    monkeypatch.setattr(driver, "_provenance", lambda: {"test": True})
    def observations(name, frequencies, acquisition, config):
        return np.ones((12, len(frequencies)), complex), {"kind": "controlled_test"}
    def fail(*args, **kwargs):
        raise RuntimeError("controlled coding error")
    monkeypatch.setattr(driver, "_independent_observations", observations)
    monkeypatch.setattr(driver, "_run_arm", fail)
    with pytest.raises(RuntimeError, match="controlled coding error"):
        driver.main(["--output-dir", str(tmp_path)])
    with np.load(tmp_path/"arrays.npz") as arrays:
        assert "circle_observed" in arrays
        assert "star_observed" in arrays
        assert "heldout_sources" in arrays
    import json
    manifest = json.loads((tmp_path/"metrics.json").read_text())
    assert manifest["status"] == "observations_frozen_before_optimization"
    assert manifest["completed"] is False
