"""The Phase-A accounting must preserve the production optimization path."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse.models import TorchParameterController
from sdf_inverse.optimization import ComplexScatteredData, ParameterFDConfig
from sdf_inverse import forward, optimization


def test_trial_audit_excludes_fd_probes_and_preserves_actual_updates(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "matched_star_controls_under_test", root / "run_implicit_star_matched_controls.py",
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    def predict(model, *args, **kwargs):
        value = float(model.weight.detach().item())
        return SimpleNamespace(
            scattered_response=np.array([[value * value]], dtype=np.complex128),
            linear_system_relative_residuals=np.array([0.0]),
            geometry_points=np.array([[0., 0.], [1., 0.], [0., 1.]]),
        )

    monkeypatch.setattr(forward, "predict_paired_response", predict)
    data = ComplexScatteredData(
        SimpleNamespace(num_pairs=1, num_frequencies=1), np.array([[1.0 + 0.0j]]),
    )
    config = ParameterFDConfig(
        max_iterations=1, finite_difference_steps=1e-4, max_steps=2.0,
        initial_damping=1e-8,
    )

    def factory():
        model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
        with torch.no_grad():
            model.weight.fill_(0.1)
        return model, TorchParameterController(model, lower_bounds=-3., upper_bounds=3.)

    plain_model, plain_controller = factory()
    plain = optimization.run_parameter_fd_inverse(
        plain_model, plain_controller, data, object(), solver="kress", config=config,
    )
    model, controller = factory()
    audit = module.TrainingAudit()
    observed = audit.run(model, controller, data, object(), config)

    assert observed.stop_reason == plain.stop_reason
    assert observed.total_evaluation_count == plain.total_evaluation_count
    assert observed.cache_hit_count == plain.cache_hit_count
    assert len(plain.iterations) == len(observed.iterations)
    for expected, actual in zip(plain.iterations, observed.iterations):
        np.testing.assert_array_equal(expected.parameter_vector, actual.parameter_vector)
        assert expected.loss == actual.loss
    assert [trial["accepted"] for trial in audit.trials] == [False, True]
    assert audit.trials[0]["rejection_reason"] == "data_not_decreased"
    assert audit.progress[-1]["accepted_trials"] == 1
    assert audit.progress[-1]["rejected_trials"] == 1
    assert len(audit.trials) < observed.total_evaluation_count
