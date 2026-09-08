"""Iteration-local objectives, reproducible proposals and bounded work."""
from dataclasses import replace
import numpy as np
import pytest
import torch

from test_implicit_adjoint import _case
from sdf_inverse.eikonal_sampling import regularization_points, sample_set_hash
from sdf_inverse.implicit_adjoint import ImplicitMLPAdjointConfig, run_implicit_mlp_adjoint_inverse
from sdf_inverse.geometry import OrderedSDFGeometryError


def test_mixed_samples_are_deterministic_and_keep_exact_global_half():
    model, _, _, geometry = _case()
    base = ImplicitMLPAdjointConfig()
    uniform = regularization_points(model, geometry, base)
    mixed = regularization_points(model, geometry, replace(base, eikonal_sampling="contour_band"))
    assert mixed.shape == (512, 2)
    torch.testing.assert_close(uniform[:256], mixed[:256], rtol=0, atol=0)
    assert sample_set_hash(mixed) == sample_set_hash(regularization_points(model, geometry, replace(base, eikonal_sampling="contour_band")))
    with torch.no_grad():
        # The geometric circle is about 58 mm in radius; the mixed samples
        # must constrain the interface rather than filling the whole box.
        assert float(model(mixed[256:]).abs().max()) < .006


def test_candidate_cap_preserves_weights_and_adam_state_on_rejection(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    initial = controller.parameter_vector()
    real = module.predict_paired_response
    calls = 0
    def forward(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OrderedSDFGeometryError("test rejection")
        return real(*args, **kwargs)
    monkeypatch.setattr(module, "predict_paired_response", forward)
    proposals = []
    result = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_candidate_evaluations=2), optimizer_callback=proposals.append)
    assert result.stop_reason == "maximum_candidate_evaluations"
    assert calls == 3
    np.testing.assert_array_equal(controller.parameter_vector(), initial)
    assert not result.diagnostics["optimizer_state_dict"]["state"]
    assert not proposals[0]["accepted"]
    assert len(proposals[0]["trials"]) == 2
    assert proposals[0]["optimizer_after_proposal"]["state"]


def test_contour_samples_stay_fixed_within_search_and_refresh_after_acceptance():
    model, controller, data, geometry = _case()
    proposals = []
    result = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_iterations=2, eikonal_sampling="contour_band"),
        optimizer_callback=proposals.append)
    assert len(result.iterations) == 3
    for i, proposal in enumerate(proposals):
        assert all(t["sample_set_hash"] == result.iterations[i].sample_set_hash for t in proposal["trials"])
        assert proposal["sample_set_hash"] != result.iterations[i+1].sample_set_hash
        accepted = next(t for t in proposal["trials"] if t["accepted"])
        assert accepted["objective"] == result.iterations[i+1].acceptance_objective
        for state in proposal["optimizer_after_proposal"]["state"].values():
            assert {"step", "exp_avg", "exp_avg_sq"} <= state.keys()
        np.testing.assert_allclose(proposal["accepted_parameter_vector"] - proposal["parameter_vector"], proposal["accepted_step"])
    assert result.diagnostics["regularized_objective_scope"] == "iteration_local"


def test_fresh_optimizer_state_replays_identically():
    model, controller, data, geometry = _case()
    first = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_iterations=1))
    frozen = controller.parameter_vector()
    state = first.diagnostics["optimizer_state_dict"]
    cfg = ImplicitMLPAdjointConfig(max_iterations=1)
    a = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry, config=cfg, optimizer_state_dict=state)
    controller.assign(frozen)
    b = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry, config=cfg, optimizer_state_dict=state)
    np.testing.assert_array_equal(a.final_iteration.parameter_vector, b.final_iteration.parameter_vector)
    assert a.final_iteration.loss == b.final_iteration.loss


def test_wall_cap_stops_before_gradient_and_candidates(monkeypatch):
    import sdf_inverse.implicit_adjoint as module
    model, controller, data, geometry = _case()
    def forbidden(*args, **kwargs):
        raise AssertionError("No adjoint after cap")
    monkeypatch.setattr(module, "implicit_mlp_data_gradient", forbidden)
    result = run_implicit_mlp_adjoint_inverse(model, controller, data, geometry,
        config=ImplicitMLPAdjointConfig(max_wall_seconds=1e-12))
    assert result.stop_reason == "maximum_wall_seconds"
    assert result.total_evaluation_count == 1
    assert not result.final_iteration.gradient_evaluated
