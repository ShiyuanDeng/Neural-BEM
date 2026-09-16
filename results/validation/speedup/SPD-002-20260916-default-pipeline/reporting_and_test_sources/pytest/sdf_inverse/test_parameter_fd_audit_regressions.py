"""Regression tests for incomplete geometry probes and false stationarity."""

from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse.geometry import OrderedSDFGeometryError
from sdf_inverse.models import TorchParameterController
from sdf_inverse.optimization import (
    ComplexScatteredData,
    ParameterFDConfig,
    run_parameter_fd_inverse,
)


def _run_scalar(monkeypatch, response, *, initial=0.0, lower=-1.0, upper=1.0,
                **config_overrides):
    import sdf_inverse.forward as forward

    model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
    with torch.no_grad():
        model.weight.fill_(initial)
    controller = TorchParameterController(
        model, lower_bounds=lower, upper_bounds=upper,
    )

    def predict(model, *args, **kwargs):
        value = float(model.weight.detach().item())
        predicted = response(value)
        return SimpleNamespace(
            scattered_response=np.array([[predicted]], dtype=np.complex128),
            linear_system_relative_residuals=np.array([0.0]),
            geometry_points=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        )

    monkeypatch.setattr(forward, "predict_paired_response", predict)
    settings = dict(
        max_iterations=1, finite_difference_steps=0.01, max_steps=0.01,
        infeasible_trial_policy="reject", loss_tolerance=1.0e-14,
    )
    settings.update(config_overrides)
    result = run_parameter_fd_inverse(
        model, controller,
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1), np.array([[1.0j]]),
        ),
        object(), solver="kress", config=ParameterFDConfig(**settings),
    )
    np.testing.assert_array_equal(
        controller.parameter_vector(), result.final_iteration.parameter_vector,
    )
    assert model.training
    return result


def test_missing_geometry_derivatives_do_not_certify_stationarity(monkeypatch):
    def response(value):
        if value != 0.0:
            raise OrderedSDFGeometryError("synthetic unavailable contour")
        return 1.0 + 1.0j

    result = _run_scalar(monkeypatch, response)
    assert result.maximum_frozen_jacobian_columns == 1
    assert result.final_iteration.loss == pytest.approx(0.5)
    assert not result.converged
    assert result.stop_reason == "infeasible_jacobian"


@pytest.mark.parametrize("bound", ("lower", "upper"))
@pytest.mark.parametrize("feasible_probe", (0.01, 0.02))
def test_bound_stencil_uses_surviving_probe(monkeypatch, bound, feasible_probe):
    direction = 1.0 if bound == "lower" else -1.0

    def response(value):
        inward = direction * value
        if inward != 0.0 and not np.isclose(inward, feasible_probe, atol=1.0e-14):
            raise OrderedSDFGeometryError("synthetic unavailable contour")
        return (1.0 - inward) + 1.0j

    result = _run_scalar(
        monkeypatch, response, lower=0.0 if bound == "lower" else -1.0,
        upper=1.0 if bound == "lower" else 0.0, max_steps=0.001,
    )
    assert result.maximum_frozen_jacobian_columns == 0
    np.testing.assert_allclose(result.initial_iteration.gradient, [-direction])
    assert not result.converged


def test_rejected_backtracks_cannot_manufacture_step_convergence(monkeypatch):
    import sdf_inverse.optimization as optimization

    # A noisy numerical derivative can point uphill. Damping and halving will
    # eventually make that rejected proposal tiny without finding a minimum.
    monkeypatch.setattr(
        optimization, "_finite_difference_jacobian",
        lambda *args: (np.array([[1.0], [0.0]]), 0.0, 0),
    )
    result = _run_scalar(
        monkeypatch, lambda value: (1.0 - value) + 1.0j,
        relative_step_tolerance=1.0e-3,
    )
    assert len(result.iterations) == 1
    assert not result.converged
    assert result.stop_reason == "no_decreasing_step"


@pytest.mark.parametrize("bound", ("lower", "upper"))
@pytest.mark.parametrize("start_on_bound", (False, True))
def test_declared_bound_optimum_uses_projected_gradient(
    monkeypatch, bound, start_on_bound
):
    direction = 1.0 if bound == "lower" else -1.0
    result = _run_scalar(
        monkeypatch,
        lambda value: (1.0 + direction * value) + 1.0j,
        initial=0.0 if start_on_bound else direction * 0.05,
        lower=0.0 if bound == "lower" else -1.0,
        upper=1.0 if bound == "lower" else 0.0,
        max_steps=0.2,
    )

    assert result.converged
    assert result.stop_reason == "projected_gradient_tolerance"
    assert len(result.iterations) == (1 if start_on_bound else 2)
    np.testing.assert_allclose(result.final_iteration.parameter_vector, [0.0])
    # Keep the measured gradient in the record; only its feasible projection
    # vanishes at this constrained optimum, whose data residual is nonzero.
    np.testing.assert_allclose(result.final_iteration.gradient, [direction])
    assert result.final_iteration.loss == pytest.approx(0.5)


@pytest.mark.parametrize("bound", ("lower", "upper"))
def test_bound_does_not_certify_stationarity_without_geometry_derivatives(
    monkeypatch, bound
):
    def response(value):
        if value != 0.0:
            raise OrderedSDFGeometryError("unavailable inward geometry probes")
        return 1.0 + 1.0j

    result = _run_scalar(
        monkeypatch,
        response,
        lower=0.0 if bound == "lower" else -1.0,
        upper=1.0 if bound == "lower" else 0.0,
    )
    assert result.maximum_frozen_jacobian_columns == 1
    assert not result.converged
    assert result.stop_reason == "infeasible_jacobian"


def test_unconstrained_stationarity_keeps_ordinary_gradient_stop_reason(monkeypatch):
    result = _run_scalar(monkeypatch, lambda value: 1.0 + 1.0j)
    assert result.converged
    assert result.stop_reason == "gradient_tolerance"


def test_projected_gradient_requires_every_derivative_to_be_available(monkeypatch):
    import sdf_inverse.forward as forward

    model = torch.nn.Linear(2, 1, bias=False, dtype=torch.float64)
    with torch.no_grad():
        model.weight.zero_()
    controller = TorchParameterController(model, lower_bounds=0.0, upper_bounds=1.0)

    def predict(model, *args, **kwargs):
        first, second = model.weight.detach().numpy().reshape(-1)
        if second != 0.0:
            raise OrderedSDFGeometryError("second parameter has no feasible probe")
        return SimpleNamespace(
            scattered_response=np.array([[1.0 + first + 1.0j]]),
            linear_system_relative_residuals=np.array([0.0]),
            geometry_points=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        )

    monkeypatch.setattr(forward, "predict_paired_response", predict)
    result = run_parameter_fd_inverse(
        model, controller,
        ComplexScatteredData(
            SimpleNamespace(num_pairs=1, num_frequencies=1), np.array([[1.0j]]),
        ),
        object(), solver="kress",
        config=ParameterFDConfig(
            max_iterations=1, finite_difference_steps=0.01,
            infeasible_trial_policy="reject",
        ),
    )
    # The known gradient points outward at its bound, but the frozen second
    # component may conceal an inward descent; projection cannot certify it.
    np.testing.assert_allclose(result.initial_iteration.gradient, [1.0, 0.0])
    assert result.maximum_frozen_jacobian_columns == 1
    assert not result.converged
    assert result.stop_reason == "infeasible_jacobian"
