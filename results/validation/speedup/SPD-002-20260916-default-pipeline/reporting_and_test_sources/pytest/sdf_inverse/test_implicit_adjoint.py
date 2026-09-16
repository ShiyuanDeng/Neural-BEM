"""Neural adjoints agree with the rebuilt Method-B objective and own updates."""

from dataclasses import replace

import numpy as np
import pytest
from types import SimpleNamespace

torch = pytest.importorskip("torch")

from run_sdf_inverse_comparison import _build_problem, _build_target, _ring_scan
from sdf_inverse.forward import predict_paired_response
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.implicit_adjoint import (
    ImplicitMLPAdjointConfig, implicit_mlp_data_gradient, run_implicit_mlp_adjoint_inverse,
)
from sdf_inverse.models import TorchParameterController
from sdf_inverse.neural import SmoothMLPSDF2D
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual


def _case(grid=57, nodes=32, width=8):
    bounds = ((0.3, 0.3), (0.7, 0.7))
    model = SmoothMLPSDF2D(
        bounds=bounds, hidden_features=width, hidden_layers=2,
        fourier_frequencies=(1.0, 2.0), geometric_center=(0.4853, 0.5117),
        geometric_radius=0.0581, seed=81,
    )
    # Nonzero final layer exercises gradients in earlier layers too.
    with torch.no_grad():
        model.network[-1].weight.add_(0.002)
    controller = TorchParameterController(model, lower_bounds=-10, upper_bounds=10,
                                          max_parameters=sum(p.numel() for p in model.parameters()))
    target = _build_target("circle")
    sources, receivers = _ring_scan(center=target.center, standoff=0.3, num_pairs=4)
    problem = _build_problem((0.25, 0.5), sources, receivers)
    data = ComplexScatteredData(problem, target.observations(problem), frequency_weights=np.array([0.3, 1.7]))
    geometry = OrderedSDFGeometryConfig(
        bounds=bounds, grid_shape=(grid, grid + 2), projected_samples=32, bandwidth=5,
        num_nodes=nodes, arclength_dense_resolution=128, validation_resolution=128,
    )
    return model, controller, data, geometry


def _loss(model, data, geometry):
    forward = predict_paired_response(model, data.forward_problem, geometry, solver="kress")
    residual, _ = normalized_complex_residual(forward.scattered_response,
                                             data.observed_scattered_response, data.frequency_weights)
    return 0.5 * float(residual @ residual)


@pytest.mark.parametrize("grid,nodes", ((57, 32), (85, 64)))
def test_full_neural_gradient_matches_actual_reextraction_objective(grid, nodes):
    model, controller, data, geometry = _case(grid=grid, nodes=nodes)
    initial = controller.parameter_vector()
    gradient, diagnostic = implicit_mlp_data_gradient(model, data, geometry)
    rng = np.random.default_rng(724)
    direction = rng.normal(size=gradient.size)
    direction /= np.linalg.norm(direction)
    analytic = float(gradient @ direction)
    assert abs(analytic) > 1e-5
    assert diagnostic["finite_difference_probes"] == 0
    assert diagnostic["adjoint_solve_count"] == 2
    try:
        for step in (2e-5, 1e-5, 5e-6):
            controller.assign(initial + step * direction)
            high = _loss(model, data, geometry)
            controller.assign(initial - step * direction)
            low = _loss(model, data, geometry)
            assert (high-low)/(2*step) == pytest.approx(analytic, rel=3e-4, abs=2e-6)
    finally:
        controller.assign(initial)


def test_adjoint_updates_mlp_and_accepts_its_actual_method_b_objective(monkeypatch):
    import sdf_inverse.optimization as fd
    import sdf_inverse.neural as neural
    model, controller, data, geometry = _case(width=16)
    initial = controller.parameter_vector()
    def forbidden(*args, **kwargs):
        raise AssertionError("Neural adjoint inversion must not invoke FD or curve distillation.")
    monkeypatch.setattr(fd, "_finite_difference_jacobian", forbidden)
    monkeypatch.setattr(neural, "redistance_neural_sdf_to_curve", forbidden)
    checked = []
    def check_accepted(record):
        np.testing.assert_array_equal(controller.parameter_vector(), record.parameter_vector)
        actual = predict_paired_response(model, data.forward_problem, geometry, solver="kress")
        np.testing.assert_array_equal(actual.geometry_build.curve.points, record.geometry_points)
        assert _loss(model, data, geometry) == pytest.approx(record.loss, rel=1e-12)
        checked.append(record.loss)
    result = run_implicit_mlp_adjoint_inverse(
        model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_iterations=3, regularization_samples=64),
        progress_callback=check_accepted,
    )
    assert len(checked) == 4
    assert np.all(np.diff(checked) < 0.0)
    assert result.final_iteration.loss < 0.95 * result.initial_iteration.loss
    assert not np.array_equal(initial, controller.parameter_vector())
    np.testing.assert_array_equal(controller.parameter_vector(), result.final_iteration.parameter_vector)
    assert result.diagnostics["curve_distillation_steps"] == 0
    assert result.diagnostics["finite_difference_probes"] == 0
    assert result.diagnostics["adjoint_solve_count"] == 6
    assert result.final_iteration.gradient is None
    assert not result.final_iteration.gradient_evaluated
    assert result.total_evaluation_count < controller.num_parameters


def test_rejected_neural_trials_restore_the_last_accepted_weights(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    initial = controller.parameter_vector()
    original = module.predict_paired_response
    calls = []
    def reject_trials(*args, **kwargs):
        calls.append(controller.parameter_vector())
        if len(calls) > 1:
            raise OrderedSDFGeometryError("Deliberate topology barrier")
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "predict_paired_response", reject_trials)
    result = run_implicit_mlp_adjoint_inverse(
        model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_iterations=2, max_backtracks=2, regularization_samples=32),
    )
    assert result.stop_reason == "no_decreasing_neural_step"
    assert not result.converged
    assert len(result.iterations) == 1
    assert result.infeasible_trial_count > 0
    assert result.diagnostics["rejection_reason_counts"]["extraction_topology"] == result.infeasible_trial_count
    assert len(result.diagnostics["trial_records"]) == result.infeasible_trial_count
    np.testing.assert_array_equal(controller.parameter_vector(), initial)


def test_solver_failure_propagates_and_restores_accepted_network(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    initial = controller.parameter_vector()
    original = module.predict_paired_response
    calls = []
    def fail_trial(*args, **kwargs):
        calls.append(None)
        if len(calls) > 1:
            raise RuntimeError("Deliberate solver failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "predict_paired_response", fail_trial)
    logged = []
    with pytest.raises(RuntimeError, match="Deliberate solver failure") as failure:
        run_implicit_mlp_adjoint_inverse(
            model, controller, data, geometry,
            config=ImplicitMLPAdjointConfig(max_iterations=2, regularization_samples=32),
            trial_callback=logged.append)
    assert logged[-1]["rejection_reasons"] == ["non_finite_or_solver_failure"]
    assert failure.value.implicit_mlp_trial_records[-1] == logged[-1]
    np.testing.assert_array_equal(controller.parameter_vector(), initial)


def test_deeper_search_records_an_accepted_step_beyond_eight(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    original = module.predict_paired_response
    calls = 0

    def temporary_refinement_barrier(*args, **kwargs):
        nonlocal calls
        calls += 1
        if 2 <= calls <= 10:
            failure = OrderedSDFGeometryError("Diagnostic refinement barrier")
            failure.rejection_reasons = ("conversion_refinement_change",)
            failure.conversion_error_m = .0001
            failure.conversion_refinement_change_m = .00002
            raise failure
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "predict_paired_response", temporary_refinement_barrier)
    result = run_implicit_mlp_adjoint_inverse(
        model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_iterations=1, max_backtracks=14, regularization_samples=32))
    assert len(result.iterations) == 2
    assert result.final_iteration.backtracks == 9
    counts = result.diagnostics["rejection_reason_counts"]
    assert counts["conversion_refinement_change"] == 9
    assert counts["conversion_distance"] == 0
    assert result.diagnostics["accepted_steps_beyond_historical_backtrack_8"][0]["backtracks"] == 9


def test_finished_initial_state_does_not_require_another_geometry_derivative(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    def forbidden(*args, **kwargs):
        raise AssertionError("An already finished state must not require an adjoint.")
    monkeypatch.setattr(module, "implicit_mlp_data_gradient", forbidden)
    result = run_implicit_mlp_adjoint_inverse(
        model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(loss_tolerance=1e4, regularization_samples=32))
    assert result.converged
    assert result.diagnostics["adjoint_solve_count"] == 0
    assert result.final_iteration.gradient is None
    assert result.final_iteration.data_gradient is None


def test_small_gradient_fallback_can_descend_after_adam_exhausts_backtracking(monkeypatch):
    """A narrow quadratic reproduces the false minimum-step stop near a fit."""
    import sdf_inverse.implicit_adjoint as module
    model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
    with torch.no_grad():
        model.weight.fill_(1e-6)
    controller = TorchParameterController(model, lower_bounds=-1, upper_bounds=1)
    points = np.array([[0., 0.], [1., 0.], [0., 1.]])
    def forward(*args, **kwargs):
        x = float(model.weight.detach().item())
        return SimpleNamespace(
            scattered_response=np.array([[1.0 + 100.0*x]], dtype=complex),
            geometry_build=SimpleNamespace(curve=SimpleNamespace(points=points)),
            linear_system_relative_residuals=np.array([0.]), total_seconds=0.,
        )
    def derivative(*args, **kwargs):
        return np.array([1e4 * model.weight.detach().item()]), {
            "adjoint_solve_count": 1, "gradient_seconds": 0., "method_b_replay_maximum_error": 0.,
        }
    monkeypatch.setattr(module, "predict_paired_response", forward)
    monkeypatch.setattr(module, "implicit_mlp_data_gradient", derivative)
    monkeypatch.setattr(module, "_eikonal", lambda *a, **kw: torch.tensor(0.))
    data = ComplexScatteredData(object(), np.ones((1, 1), dtype=complex))
    result = run_implicit_mlp_adjoint_inverse(
        model, controller, data, SimpleNamespace(bounds=((0., 0.), (1., 1.))),
        config=ImplicitMLPAdjointConfig(max_iterations=1, eikonal_weight=0., max_backtracks=8),
    )
    assert len(result.iterations) == 2
    assert result.final_iteration.step_method == "adjoint_steepest_descent"
    assert result.final_iteration.loss < .1 * result.initial_iteration.loss
    # The real accepted data decrease remains valid below the reporting-only
    # boundary movement floor; it must not be advertised as shape recovery.
    assert not result.final_iteration.meaningful_boundary_step
    assert result.diagnostics["rejection_reason_counts"]["data_armijo"] > 0
    assert result.diagnostics["rejection_reason_counts"]["regularized_armijo"] > 0


@pytest.mark.parametrize("kwargs", ({"learning_rate": 0}, {"eikonal_weight": -1},
                                   {"backtrack_factor": 1}, {"max_iterations": 1.5}))
def test_invalid_adjoint_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ImplicitMLPAdjointConfig(**kwargs)
