"""Instrumentation must count work without affecting model execution."""

import copy
import json
from types import SimpleNamespace
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from run_sdf_representation_ablation import PipelineWork, _fresh_output, _trajectory_comparison
import run_sdf_representation_ablation as driver
from sdf_inverse import MaterialSpec, PairedForwardProblem, OrderedSDFGeometryConfig
from sdf_inverse.curve_updates import RadialFourierCurveState, radial_fourier_parameterization
from sdf_inverse.neural import NeuralRedistanceConfig


def test_instrumentation_tracks_candidate_copies_and_restores_after_failure():
    model = torch.nn.Linear(2, 1, dtype=torch.float64)
    original_grad = torch.autograd.grad
    points = torch.ones((4, 2), dtype=torch.float64, requires_grad=True)
    expected = model(points).detach().clone()
    with pytest.raises(RuntimeError, match="intentional"):
        with PipelineWork(model) as work:
            cloned = copy.deepcopy(model)
            output = cloned(points)
            torch.testing.assert_close(output.detach(), expected, rtol=0.0, atol=0.0)
            gradient = torch.autograd.grad(output.sum(), points)[0]
            assert gradient.shape == points.shape
            raise RuntimeError("intentional")
    assert torch.autograd.grad is original_grad
    assert not model._forward_pre_hooks
    assert work.counts["sdf_value_calls"] == 1
    assert work.counts["sdf_query_points"] == 4
    assert work.counts["spatial_gradient_calls"] == 1


def test_trajectory_gate_rejects_missing_steps_and_material_deviation():
    initial = np.zeros((3, 7))
    assert _trajectory_comparison(initial, initial.copy())["passed"]
    assert not _trajectory_comparison(initial, initial[:2])["passed"]
    changed = initial.copy()
    changed[1, 0] = 1.0e-6
    assert not _trajectory_comparison(initial, changed)["passed"]
    assert _trajectory_comparison(initial, None)["passed"] is None


def test_ablation_cannot_overwrite_historical_artifacts(tmp_path):
    output = _fresh_output(tmp_path / "evidence")
    sentinel = output / "metrics.json"
    sentinel.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="new or empty"):
        _fresh_output(output)
    assert sentinel.read_text(encoding="utf-8") == "existing"


@pytest.fixture
def small_policy_run(monkeypatch, tmp_path):
    """One deterministic accepted state; exercise driver I/O, not BEM again."""
    state = RadialFourierCurveState(
        center=np.array((.5, .5)), radius_cosine_coefficients=np.array((.065, 0)),
        radius_sine_coefficients=np.zeros(2), component_id="canonical",
    )
    curve = radial_fourier_parameterization(state).discretize(16)
    geometry_config = OrderedSDFGeometryConfig(
        bounds=((.3, .3), (.7, .7)), num_nodes=16, bandwidth=2,
        projected_samples=8, arclength_dense_resolution=64, validation_resolution=64,
    )
    config = NeuralRedistanceConfig(
        bounds=geometry_config.bounds, max_steps=2, minimum_steps=1, warmup_steps=0,
        sample_count=8, heldout_sample_count=8, eikonal_rms_tolerance=.1,
    )
    args = SimpleNamespace(
        hidden_features=4, hidden_layers=1, mlp_seed=1, outer_iterations=1,
        maximum_modal_update_mm=1., maximum_redistance_drift_mm=1.,
        geometry_convergence_tolerance_mm=.2, train_ghz=(.5,),
        continuation_strategy="frequency_then_modes",
    )
    problem = PairedForwardProblem(
        source_points=np.array(((.1, .4), (.9, .4))),
        receiver_points=np.array(((.1, .6), (.9, .6))),
        angular_frequencies=2*np.pi*np.array((.5e9, .7e9)), source_strengths=1.,
        exterior=MaterialSpec(epsr=6.), interior=MaterialSpec(epsr=3.),
        eps0=8.8541878128e-12, mu0=1.25663706212e-6,
    )
    truth = np.ones((2, 2), dtype=complex)
    target = SimpleNamespace(boundary_distances=lambda points: np.zeros(len(points)))
    stage = SimpleNamespace(stage=1, max_iterations=1, train_frequencies_ghz=(.5,))
    monkeypatch.setattr(driver.legacy, "_incremental_redistance_config", lambda value: value)
    monkeypatch.setattr(driver.legacy, "_effective_stage_budget", lambda **kwargs: 1)
    monkeypatch.setattr(driver.legacy, "_mode_budget", lambda *args, **kwargs: {"maximum_mode": 1})
    monkeypatch.setattr(driver.legacy, "_continuation_stage_maximum_mode", lambda *args, **kwargs: 1)
    monkeypatch.setattr(driver.legacy, "_stage_inverse_config", lambda config, **kwargs: config)
    monkeypatch.setattr(driver.neural, "redistance_neural_sdf_to_curve", lambda *args, **kwargs:
                        SimpleNamespace(converged=True, stop_reason="test_fit", steps=0))
    monkeypatch.setattr(driver.geometry, "build_ordered_sdf_geometry", lambda *args, **kwargs:
                        SimpleNamespace(curve=curve))
    monkeypatch.setattr(driver.forward, "predict_paired_curve_response", lambda *args, **kwargs:
                        SimpleNamespace(scattered_response=truth.copy()))

    def inverse_result(model, data, geom, **kwargs):
        strict = kwargs["config"].distillation_policy == "legacy_strict"
        record = SimpleNamespace(
            iteration=0, loss=0., relative_l2_error=0., representation_evaluated=strict,
            redistance_curve_drift_m=0. if strict else None, redistance_steps=0,
            redistance_stop_reason="test_fit" if strict else "not_requested",
            evaluation_count=1, geometry_points=curve.points, accepted_backtrack_count=0,
        )
        kwargs["progress_callback"](record)
        return SimpleNamespace(
            final_radial_curve_state=state, final_curve=curve,
            final_representation_curve=curve if strict else None,
            iterations=(record,), total_evaluation_count=1, infeasible_evaluation_count=0,
            total_bem_seconds=0., total_geometry_audit_seconds=0., full_validation_rejection_count=0,
            reconstruction_converged=True, reconstruction_stop_reason="test_reconstruction_converged",
            converged=True, stop_reason="test_converged",
            representation_status="passed" if strict else "not_requested",
            representation_stop_reason="test_passed" if strict else "not_requested",
            final_iteration=record, maximum_system_residual=0.,
        )
    monkeypatch.setattr(driver.inverse, "run_alternating_neural_inverse", inverse_result)

    def run(policy):
        return driver._policy_run(
            policy, args, target, state, curve, problem, truth,
            geometry_config, config, (stage,), tmp_path,
        )
    return SimpleNamespace(run=run, output=tmp_path, curve=curve, truth=truth)


@pytest.mark.parametrize("failure_kind", ("training", "extraction"))
def test_strict_initialization_failure_has_explicit_unavailable_results(
    monkeypatch, small_policy_run, failure_kind,
):
    if failure_kind == "training":
        monkeypatch.setattr(driver.neural, "redistance_neural_sdf_to_curve", lambda *args, **kwargs:
                            SimpleNamespace(converged=False, stop_reason="maximum_steps", steps=2))
    else:
        def invalid_contour(*args, **kwargs):
            raise driver.geometry.OrderedSDFGeometryError("two contours")
        monkeypatch.setattr(driver.geometry, "build_ordered_sdf_geometry", invalid_contour)
    summary, trajectory = small_policy_run.run("legacy_strict")
    assert trajectory is None
    assert not summary["requested_delivery_complete"]
    assert not summary["reconstruction_converged"]
    assert summary["representation_status"] == "failed"
    for key in ("canonical_fields", "representation_fields", "representation_drift_m",
                "reconstruction", "export", "final_audit"):
        assert summary[key] is None
    row = driver._policy_summary_row("legacy_strict", summary)
    assert "n/a | n/a | n/a" in row
    assert "nan" not in row
    directory = small_policy_run.output / "legacy_strict"
    assert json.loads((directory / "metrics.json").read_text())["requested_delivery_complete"] is False
    with np.load(directory / "canonical.npz", allow_pickle=False) as arrays:
        np.testing.assert_array_equal(arrays["points"], small_policy_run.curve.points)


@pytest.mark.parametrize("failure_kind", ("extraction", "forward"))
def test_final_representation_failure_preserves_canonical_artifacts_and_next_policy(
    monkeypatch, small_policy_run, failure_kind,
):
    directory = small_policy_run.output / "legacy_strict"
    def check_checkpoint():
        assert (directory / "canonical.npz").exists()
        assert (directory / "trajectory.csv").exists()
        summary = json.loads((directory / "metrics.json").read_text())
        assert summary["reconstruction_converged"]
        assert summary["canonical_fields"] is not None
        assert summary["requested_delivery_complete"] is False
    if failure_kind == "extraction":
        def extraction(model, config):
            if config.num_nodes > 16:
                check_checkpoint()
                raise driver.geometry.OrderedSDFGeometryError("refinement contour failed")
            return SimpleNamespace(curve=small_policy_run.curve)
        monkeypatch.setattr(driver.geometry, "build_ordered_sdf_geometry", extraction)
    else:
        calls = 0
        def forward(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                check_checkpoint()
                raise np.linalg.LinAlgError("representation solve failed")
            return SimpleNamespace(scattered_response=small_policy_run.truth.copy())
        monkeypatch.setattr(driver.forward, "predict_paired_curve_response", forward)
    summary, trajectory = small_policy_run.run("legacy_strict")
    assert summary["reconstruction_converged"]
    assert summary["representation_status"] == "failed"
    assert summary["final_audit_status"] == "failed"
    assert summary["canonical_fields"] is not None
    assert summary["representation_fields"] is None
    assert not summary["requested_delivery_complete"]
    assert trajectory.shape == (1, 3)
    with np.load(directory / "canonical.npz", allow_pickle=False) as arrays:
        np.testing.assert_array_equal(arrays["points"], small_policy_run.curve.points)
        assert "representation_points" not in arrays
    with np.load(directory / "responses.npz", allow_pickle=False) as arrays:
        np.testing.assert_array_equal(arrays["canonical"], small_policy_run.truth)
    following, _ = small_policy_run.run("curve_only")
    assert following["requested_delivery_complete"]


def test_failed_export_candidate_is_never_audited_as_the_unchanged_model(
    monkeypatch, small_policy_run,
):
    from sdf_inverse.neural_optimization import NeuralSDFExportResult
    monkeypatch.setattr(driver.inverse, "export_neural_sdf_representation", lambda *args, **kwargs:
                        NeuralSDFExportResult(status="failed", stop_reason="drift_failed",
                                              representation_evaluated=True, curve=small_policy_run.curve))
    def prohibit_extraction(*args, **kwargs):
        raise AssertionError("A failed copied candidate must not be refined through the original model")
    monkeypatch.setattr(driver.geometry, "build_ordered_sdf_geometry", prohibit_extraction)
    summary, _ = small_policy_run.run("export_only")
    assert summary["canonical_fields"] is not None
    assert summary["representation_fields"] is None
    assert summary["representation_status"] == "failed"
    assert not summary["requested_delivery_complete"]


def test_unexpected_final_audit_errors_propagate_after_canonical_checkpoint(
    monkeypatch, small_policy_run,
):
    def extraction(model, config):
        if config.num_nodes > 16:
            raise AttributeError("unexpected implementation error")
        return SimpleNamespace(curve=small_policy_run.curve)
    monkeypatch.setattr(driver.geometry, "build_ordered_sdf_geometry", extraction)
    with pytest.raises(AttributeError, match="unexpected implementation"):
        small_policy_run.run("legacy_strict")
    directory = small_policy_run.output / "legacy_strict"
    assert (directory / "canonical.npz").exists()
    assert (directory / "trajectory.csv").exists()
    saved = json.loads((directory / "metrics.json").read_text())
    assert saved["reconstruction_converged"]
    assert saved["canonical_fields"] is not None
    assert not saved["requested_delivery_complete"]
