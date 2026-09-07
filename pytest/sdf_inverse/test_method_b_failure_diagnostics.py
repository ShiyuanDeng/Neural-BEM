"""Causal-control contracts, small fitting checks, and diagnostic failure I/O."""

from copy import deepcopy
from dataclasses import replace
import json
from types import MappingProxyType

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle
from sdf_inverse import neural
from sdf_inverse.method_b_diagnostics import (
    checkpoint, conversion_settings, fit_loss, fit_metrics, fit_steps,
    fork_checkpoint, model_from_metadata, prepare_fit_data, transfer_comparison,
)
from sdf_inverse.neural import NeuralRedistanceConfig, SmoothMLPSDF2D
import run_method_b_failure_diagnostics as driver


def tiny_model():
    return SmoothMLPSDF2D(bounds=((-0.15, -0.15), (0.15, 0.15)),
                         hidden_features=8, hidden_layers=1, seed=19,
                         geometric_center=(0., 0.), geometric_radius=.055,
                         dtype=torch.float64)


def tiny_config():
    return NeuralRedistanceConfig(
        bounds=((-0.15, -0.15), (0.15, 0.15)), max_steps=4, minimum_steps=1,
        warmup_steps=1, sample_count=16, heldout_sample_count=8,
        distance_target="smooth_curve", smooth_boundary_sampling="legacy_polygon",
        distance_initial_samples=64, distance_maximum_samples=256,
    )


def assert_same_tree(left, right):
    if isinstance(left, torch.Tensor):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_same_tree(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_same_tree(a, b)
    else:
        assert left == right


def test_shared_samples_and_targets_match_production_preparation(monkeypatch):
    """Stop before production fitting; compare all arguments to the shared loss."""
    config = tiny_config()
    target = circle((0., 0.), .065)
    data = prepare_fit_data(target, config, polygon_nodes=16)
    captured = {}

    class Captured(RuntimeError):
        pass

    def capture(model, *values, **kwargs):
        captured.update(values=values, kwargs=kwargs)
        raise Captured

    monkeypatch.setattr(neural, "_redistance_objective", capture)
    with pytest.raises(Captured):
        neural.redistance_neural_sdf_to_curve(
            tiny_model(), target.discretize(16), config, continuous_curve=target,
        )
    keys = ("sample_points", "sample_targets", "boundary_points", "offset_points",
            "offset_targets", "box_points", "box_targets")
    for key, observed in zip(keys, captured["values"]):
        torch.testing.assert_close(data.tensors[key], observed, rtol=0, atol=0)
    torch.testing.assert_close(data.tensors["boundary_targets"], captured["kwargs"]["boundary_targets"], rtol=0, atol=0)
    assert captured["kwargs"]["length_scale"] == data.length_scale


def test_cloned_adam_resume_matches_uninterrupted_and_is_independent():
    model, config = tiny_model(), tiny_config()
    data = prepare_fit_data(circle((0., 0.), .065), config, polygon_nodes=16)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    fit_steps(model, optimizer, data, config, steps=2, weight=0.)
    shared = checkpoint(model, optimizer)
    saved = deepcopy(shared)
    branch, branch_optimizer = fork_checkpoint(model, shared, learning_rate=config.learning_rate)
    alternative, alternative_optimizer = fork_checkpoint(model, shared, learning_rate=config.learning_rate)
    assert shared["optimizer"]["state"]  # Adam moments must exist, not just weights.
    first = fit_steps(model, optimizer, data, config, steps=2, weight=.1)
    resumed = fit_steps(branch, branch_optimizer, data, config, steps=2, weight=.1)
    assert first == resumed
    assert_same_tree(checkpoint(model, optimizer), checkpoint(branch, branch_optimizer))
    assert_same_tree(shared, saved)
    assert_same_tree(checkpoint(alternative, alternative_optimizer), saved)
    fit_steps(alternative, alternative_optimizer, data, config, steps=2, weight=0.)
    assert any(not torch.equal(a, b) for a, b in zip(branch.parameters(), alternative.parameters()))
    assert_same_tree(shared, saved)


def test_reported_loss_components_reconstruct_shared_objective_and_keep_eikonal_gate():
    model, config = tiny_model(), tiny_config()
    data = prepare_fit_data(circle((0., 0.), .065), config, polygon_nodes=16)
    metrics = fit_metrics(model, data, config)
    c = metrics["unweighted_loss_components"]
    for weight in (0., .01, .1):
        expected = c["sample"] + config.boundary_weight*c["boundary"] + config.normal_offset_weight*c["offset"]
        expected += config.box_boundary_weight*c["box"] + weight*c["eikonal"]
        assert float(fit_loss(model, data, config, weight, create_graph=False).detach()) == pytest.approx(expected, rel=1e-13)
    zero_metrics = fit_metrics(model, data, replace(config, eikonal_weight=0.))
    assert zero_metrics["gates"]["training_eikonal"] == metrics["gates"]["training_eikonal"]


def test_frozen_model_replay_preserves_values_and_missing_keys_fail():
    model = tiny_model()
    state = {"saved_"+k: v.detach().numpy().copy() for k, v in model.state_dict().items()}
    restored = model_from_metadata(model.initialization_metadata(), state, prefix="saved_")
    points = torch.tensor([[.02, .03], [.1, -.02]], dtype=torch.float64)
    torch.testing.assert_close(model(points), restored(points), rtol=0, atol=0)
    with pytest.raises(KeyError):
        model_from_metadata(model.initialization_metadata(), {}, prefix="saved_")


def test_conversion_sweeps_change_only_one_factor():
    axes = ([129, 257, 513], [512, 1024], [24, 48, 96], [2048, 4096])
    anchor = tuple(max(values) for values in axes)
    settings = conversion_settings(*axes)
    assert len(settings) == len(set(settings)) == 1+sum(len(values)-1 for values in axes)
    assert anchor in settings
    for setting in settings:
        assert sum(a != b for a, b in zip(anchor, setting)) <= 1


@pytest.mark.parametrize("changes", [dict(references_resolved=False), dict(direct_objective=1.1), dict(actual_objective=1.1)])
def test_transfer_cannot_pass_without_resolved_direct_and_actual_descent(changes):
    values = dict(start_objective=1., direct_objective=.8, actual_objective=.9,
                  no_op_objective=1.05, intended_motion_m=1e-4, no_op_drift_m=2e-4,
                  references_resolved=True, predicted_change=-.25)
    assert transfer_comparison(**values)["transfer_descent_observed"]
    values.update(changes)
    result = transfer_comparison(**values)
    assert not result["transfer_descent_observed"]
    assert result["no_op_drift_over_intended_motion"] == 2.
    assert not result["strict_inverse_acceptance_evaluated"]
    values["intended_motion_m"] = 0.
    assert transfer_comparison(**values)["no_op_drift_over_intended_motion"] is None


def test_parser_rejects_coupled_resolution_and_artifact_collisions(tmp_path):
    prefix = ["--output-dir", str(tmp_path / "new")]
    args = driver.parse_args(prefix)
    assert args.bem_nodes == [256, 512]
    for bad in (["--bem-nodes", "64", "128"], ["--projected-samples", "64", "1024"],
                ["--shapes", "circle", "circle"], ["--step-scales-m", "0", ".001"],
                ["--experiments", "eikonal", "--frozen-policies", "legacy_polygon"]):
        with pytest.raises(SystemExit):
            driver.parse_args(prefix + bad)


def test_strict_json_rejects_nonfinite_and_preserves_previous_file(tmp_path):
    path = tmp_path / "result.json"
    driver.write_json(path, MappingProxyType(dict(status="running", value=np.float64(1.))))
    with pytest.raises(ValueError):
        driver.write_json(path, dict(value=float("nan")))
    assert json.loads(path.read_text()) == dict(status="running", value=1.)


def test_failed_conversion_does_not_discard_other_sweep_rows(tmp_path, monkeypatch):
    study = object.__new__(driver.Study)
    study.args = driver.parse_args(["--output-dir", str(tmp_path)])
    study.output = tmp_path
    monkeypatch.setattr(study, "raw_reference", lambda *a: (object(), np.ones(1), dict(resolved=True)))
    anchor = (513, 1024, 96, 4096)
    calls = []

    def converted(model, target, raw, raw_field, setting, name):
        calls.append(setting)
        if setting != anchor:
            raise ValueError("intentional invalid contour")
        distance = dict(resolved=True, symmetric_max_m=1e-6)
        return object(), np.ones(1), dict(status="completed", setting=dict(zip(
            ("grid", "projected_samples", "bandwidth", "arclength_dense"), setting)),
            stages=dict(arclength_refit=dict(forward=dict(resolved=True), to_raw_zero_set=distance,
                                             to_target=distance, regularity=dict(negative_inside_regular=True))))

    monkeypatch.setattr(study, "converted", converted)
    _, field, report = study.audit(None, None, "partial", sweep=True)
    assert field is not None
    assert len(calls) == len(driver.conversion_settings([257, 513], [512, 1024], [24, 48, 96], [2048, 4096]))
    assert any(r["status"] == "failed" for r in report["conversions"])
    assert json.loads((tmp_path / "partial_audit.json").read_text())["conversions"] == report["conversions"]


def test_missing_frozen_data_does_not_create_output(tmp_path):
    output = tmp_path / "new"
    with pytest.raises(FileNotFoundError, match="Restore it"):
        driver.main(["--output-dir", str(output), "--frozen", str(tmp_path / "missing")])
    assert not output.exists()


def test_existing_output_is_never_overwritten(tmp_path):
    frozen, output = tmp_path / "frozen", tmp_path / "existing"
    frozen.mkdir()
    (frozen / "summary.json").write_text("{}")
    (frozen / "arrays.npz").write_bytes(b"not read before overwrite check")
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep me")
    with pytest.raises(FileExistsError):
        driver.main(["--output-dir", str(output), "--frozen", str(frozen)])
    assert sentinel.read_text() == "keep me"


def test_eikonal_orchestration_keeps_shared_state_and_survives_warmup_extraction_failure(tmp_path, monkeypatch):
    """Small real fitting updates; stub geometry/BEM to test branch ownership."""
    study = object.__new__(driver.Study)
    study.output = tmp_path
    study.args = driver.parse_args(["--output-dir", str(tmp_path), "--warmup-steps", "2",
                                    "--branch-steps", "2", "--sample-count", "16"])
    target = circle((0., 0.), .065)
    audit_names = []

    def audit(model, target, name):
        audit_names.append(name)
        if name.endswith("_warmup"):
            return None, None, dict(resolved=False, error="intentional warmup topology failure")
        return target, np.ones(1), dict(resolved=True)

    monkeypatch.setattr(study, "audit", audit)
    monkeypatch.setattr(study, "target_forward", lambda target: (np.ones(1), dict(resolved=True)))
    before_fits = []
    original = driver.fit_steps

    def observe(model, optimizer, data, config, **kwargs):
        before_fits.append(checkpoint(model, optimizer))
        return original(model, optimizer, data, config, **kwargs)

    monkeypatch.setattr(driver, "fit_steps", observe)
    report = driver.run_eikonal(study, target, tiny_model().initialization_metadata(), "control")
    assert report["status"] == "completed"
    assert report["warmup"]["field_error"] is None
    assert len(before_fits) == 7  # shared warmup, then activation + remainder for each arm
    assert_same_tree(before_fits[1], before_fits[3])
    assert_same_tree(before_fits[1], before_fits[5])
    assert before_fits[1]["optimizer"]["state"]
    assert [arm["weight"] for arm in report["arms"]] == [0., .01, .1]
    assert all(arm["updates"] == 2 for arm in report["arms"])
    assert all(arm["initial_fit"] == report["warmup"]["fit"] for arm in report["arms"])
    assert sum(name.endswith("_activation") for name in audit_names) == 3
    restored = torch.load(tmp_path / report["warmup"]["checkpoint"]["path"], weights_only=True)
    assert_same_tree(restored, before_fits[1])
