"""Regression tests for neural SDF re-distancing optimizer semantics."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle
from sdf_inverse import (
    NeuralRedistanceConfig,
    SmoothMLPSDF2D,
    redistance_neural_sdf_to_curve,
)
import sdf_inverse.neural as neural_module


class _ScalarModel(torch.nn.Module):
    def __init__(self, value: float = 0.0) -> None:
        super().__init__()
        self.value = torch.nn.Parameter(torch.tensor(value, dtype=torch.float64))

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        return self.value.expand(points.shape[0], 1)


def _config(
    *,
    max_steps: int,
    warmup_steps: int,
    learning_rate: float = 1.0e-2,
    check_interval: int = 1,
):
    return NeuralRedistanceConfig(
        bounds=((-2.0, -2.0), (2.0, 2.0)),
        max_steps=max_steps,
        minimum_steps=1,
        warmup_steps=warmup_steps,
        sample_count=8,
        heldout_sample_count=8,
        learning_rate=learning_rate,
        distance_rms_tolerance_m=1.0,
        boundary_max_tolerance_m=1.0,
        eikonal_rms_tolerance=1.0,
        check_interval=check_interval,
        patience_checks=10,
        seed=7,
    )


def _scalar_objective(model, *args, **kwargs):
    del args, kwargs
    return (model.value - 1.0) ** 2


def test_tolerances_cannot_stop_during_eikonal_warmup(monkeypatch) -> None:
    monkeypatch.setattr(neural_module, "_redistance_objective", _scalar_objective)
    audit_calls = 0

    def initially_unsatisfactory_metrics(*args, **kwargs):
        nonlocal audit_calls
        del args, kwargs
        audit_calls += 1
        value = 10.0 if audit_calls <= 2 else 0.0
        return (value, value, value, value)

    monkeypatch.setattr(neural_module, "_quality_metrics", initially_unsatisfactory_metrics)
    model = _ScalarModel()
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=4, warmup_steps=2),
    )

    assert result.converged
    assert result.steps == 3
    assert result.stop_reason == "distance_boundary_and_eikonal_tolerances"


def test_satisfactory_input_is_audited_before_adam_and_is_a_zero_step_noop(
    monkeypatch,
) -> None:
    monkeypatch.setattr(neural_module, "_redistance_objective", _scalar_objective)
    monkeypatch.setattr(
        neural_module, "_quality_metrics", lambda *args, **kwargs: (0.0, 0.0, 0.0, 0.0)
    )

    def reject_adam(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Adam must not be constructed for an already-good input")

    monkeypatch.setattr(neural_module.torch.optim, "Adam", reject_adam)
    model = _ScalarModel()
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=4, warmup_steps=2),
    )

    assert result.converged
    assert result.steps == 0
    assert result.stop_reason.startswith("already_satisfies")
    assert result.loss_history.tolist() == [result.initial_total_loss]
    assert model.value.item() == pytest.approx(0.0)


def test_noop_boundary_gate_is_stricter_than_terminal_convergence(monkeypatch) -> None:
    monkeypatch.setattr(neural_module, "_redistance_objective", _scalar_objective)
    audit_calls = 0

    def submillimetre_initial_boundary_residual(*args, **kwargs):
        nonlocal audit_calls
        del args, kwargs
        audit_calls += 1
        boundary_max = 5.0e-4 if audit_calls == 1 else 0.0
        return (0.0, boundary_max, 0.0, 0.0)

    monkeypatch.setattr(
        neural_module, "_quality_metrics", submillimetre_initial_boundary_residual
    )
    model = _ScalarModel()
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=2, warmup_steps=1),
    )

    assert result.converged
    assert result.steps == 2
    assert result.stop_reason == "distance_boundary_and_eikonal_tolerances"


def test_noop_boundary_gate_cannot_exceed_terminal_gate() -> None:
    with pytest.raises(ValueError, match="no_op_boundary_max_tolerance_m"):
        NeuralRedistanceConfig(
            bounds=((-2.0, -2.0), (2.0, 2.0)),
            boundary_max_tolerance_m=1.0e-4,
            no_op_boundary_max_tolerance_m=1.0e-3,
        )


def test_redistance_restores_lowest_full_objective_parameters(monkeypatch) -> None:
    monkeypatch.setattr(neural_module, "_redistance_objective", _scalar_objective)
    monkeypatch.setattr(
        neural_module,
        "_quality_metrics",
        lambda *args, **kwargs: (10.0, 10.0, 10.0, 10.0),
    )
    model = _ScalarModel()
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=1, warmup_steps=0, learning_rate=10.0),
    )

    assert not result.converged
    assert model.value.item() == pytest.approx(0.0)
    assert result.final_total_loss == pytest.approx(result.initial_total_loss)
    assert result.diagnostics["best_full_objective_step"] == 0.0


def test_redistance_preserves_best_state_between_metric_checks(monkeypatch) -> None:
    class ScriptedOptimizer:
        def __init__(self, parameters, *, lr):
            del lr
            self.parameters = tuple(parameters)
            self.values = iter((0.5, 2.0, 3.0))

        def zero_grad(self, *, set_to_none):
            assert set_to_none
            for parameter in self.parameters:
                parameter.grad = None

        def step(self):
            with torch.no_grad():
                self.parameters[0].fill_(next(self.values))

    monkeypatch.setattr(neural_module, "_redistance_objective", _scalar_objective)
    monkeypatch.setattr(
        neural_module,
        "_quality_metrics",
        lambda *args, **kwargs: (10.0, 10.0, 10.0, 10.0),
    )
    monkeypatch.setattr(neural_module.torch.optim, "Adam", ScriptedOptimizer)
    model = _ScalarModel()
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=3, warmup_steps=0, check_interval=2),
    )

    assert not result.converged
    assert model.value.item() == pytest.approx(0.5)
    assert result.diagnostics["best_full_objective_step"] == 1.0


def test_failed_redistance_does_not_claim_signed_distance_training(monkeypatch) -> None:
    def first_parameter_objective(model, *args, **kwargs):
        del args, kwargs
        first_parameter = next(model.parameters()).reshape(-1)[0]
        return (first_parameter - 1.0) ** 2

    monkeypatch.setattr(
        neural_module, "_redistance_objective", first_parameter_objective
    )
    monkeypatch.setattr(
        neural_module,
        "_quality_metrics",
        lambda *args, **kwargs: (10.0, 10.0, 10.0, 10.0),
    )
    model = SmoothMLPSDF2D(
        bounds=((-2.0, -2.0), (2.0, 2.0)),
        hidden_features=4,
        hidden_layers=1,
        fourier_frequencies=(1.0,),
        seed=3,
        dtype=torch.float64,
    )
    model.trained_against_signed_distance = True
    result = redistance_neural_sdf_to_curve(
        model,
        circle((0.0, 0.0), 0.5).discretize(16),
        _config(max_steps=1, warmup_steps=0),
    )

    assert not result.converged
    assert model.trained_against_signed_distance is False
