"""Bounded orchestration and the complete indexed neural acceptance seam."""

from dataclasses import replace
import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import run_implicit_mlp_iteration2_matched as matched
from sdf_inverse.forward import IndexedForwardProblem, predict_indexed_response, predict_paired_response
from sdf_inverse.geometry import OrderedSDFGeometryConfig
from sdf_inverse.implicit_adjoint import implicit_mlp_data_gradient
from sdf_inverse.models import TorchParameterController
from sdf_inverse.neural import SmoothMLPSDF2D
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual


def neural_case():
    bounds = ((.3, .3), (.7, .7))
    model = SmoothMLPSDF2D(bounds=bounds, hidden_features=8, hidden_layers=2,
                           fourier_frequencies=(1., 2.), geometric_center=(.4853, .5117),
                           geometric_radius=.0581, seed=81)
    with torch.no_grad():
        model.network[-1].weight.add_(.002)
    controller = TorchParameterController(model, lower_bounds=-10., upper_bounds=10.,
                                          max_parameters=sum(p.numel() for p in model.parameters()))
    target = matched.driver._build_target("circle")
    sources, receivers = matched.driver._ring_scan(center=target.center, standoff=.3, num_pairs=2)
    paired = matched.driver._build_problem((.25, .5), sources, receivers)
    indexed = replace(IndexedForwardProblem.from_paired(paired, multistatic=True),
                      source_indices=np.array([1, 0, 1, 0, 1]),
                      receiver_indices=np.array([0, 1, 1, 0, 0]))
    observed = target.observations(matched.expanded_oracle_problem(indexed))
    data = ComplexScatteredData(indexed, observed, np.array([.3, 1.7]))
    geometry = OrderedSDFGeometryConfig(bounds=bounds, grid_shape=(57, 59), projected_samples=32,
                                         bandwidth=5, num_nodes=32, arclength_dense_resolution=128,
                                         validation_resolution=128)
    return model, controller, paired, data, geometry


def test_indexed_full_neural_normalization_derivative_and_diagonal_equivalence():
    model, controller, paired, data, geometry = neural_case()
    gradient, diagnostics = implicit_mlp_data_gradient(model, data, geometry)
    assert diagnostics["finite_difference_probes"] == 0
    assert diagnostics["adjoint_solve_count"] == 2
    actual = predict_indexed_response(model, data.forward_problem, geometry)
    observed = data.observed_scattered_response
    expected_loss = .5 * np.sum(data.frequency_weights * np.sum(abs(actual.scattered_response-observed)**2, axis=0)
                                  / np.linalg.norm(observed, axis=0)**2)
    assert matched.data_loss(model, data, geometry) == pytest.approx(expected_loss, rel=1e-14)
    diagonal = IndexedForwardProblem.from_paired(paired)
    np.testing.assert_array_equal(predict_indexed_response(model, diagonal, geometry).scattered_response,
                                  predict_paired_response(model, paired, geometry, solver="kress").scattered_response)
    original = controller.parameter_vector()
    direction = np.random.default_rng(724).normal(size=gradient.size)
    direction /= np.linalg.norm(direction)
    try:
        for step in (2e-5, 1e-5, 5e-6):
            controller.assign(original + step*direction)
            high = matched.data_loss(model, data, geometry)
            controller.assign(original - step*direction)
            low = matched.data_loss(model, data, geometry)
            assert (high-low)/(2*step) == pytest.approx(gradient@direction, rel=3e-4, abs=2e-6)
    finally:
        controller.assign(original)


def test_indexed_rollback_gate_restores_weights_and_fresh_optimizer():
    model, controller, _, data, geometry = neural_case()
    initial = controller.parameter_vector()
    optimizer = torch.optim.Adam(model.parameters(), lr=.001).state_dict()
    result = matched.rollback_gate(model, controller, data, geometry, optimizer)
    assert result["passed"]
    assert result["rejected_candidates"] == 2
    np.testing.assert_array_equal(controller.parameter_vector(), initial)


def test_default_prints_plan_without_loading_weights_or_running(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("default action must not load data or launch work")
    monkeypatch.setattr(matched, "load_initial", forbidden)
    monkeypatch.setattr(matched, "run", forbidden)
    monkeypatch.setattr(matched, "qualify", forbidden)
    assert matched.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["caps_per_arm"] == {"accepted_updates": 5, "attempted_candidates": 120, "wall_seconds": 600.}
    assert report["arms"][0][1] == "paired"
    assert report["arms"][1][1] == "multistatic"


def test_geometry_json_preserves_complex_spectra_and_marks_unresolved_values(tmp_path):
    path = tmp_path / "geometry.json"
    matched.write_json(path, {"coefficients": np.array([1 + 2j]), "unclipped_inverse_G": np.array([np.inf])})
    record = json.loads(path.read_text())
    assert record == {"coefficients": [{"real": 1., "imag": 2.}], "unclipped_inverse_G": [None]}


def test_real_posthoc_transition_does_not_shadow_correspondence_function(tmp_path):
    model, controller, _, _, geometry = neural_case()
    geometry = replace(geometry, num_nodes=64)
    initial = controller.parameter_vector()
    next_weights = initial.copy()
    next_weights[-1] += 1e-6
    records = []
    for i, vector in enumerate((initial, next_weights)):
        controller.assign(vector)
        built = matched.build_ordered_sdf_geometry(model, geometry)
        records.append(SimpleNamespace(iteration=i, parameter_vector=vector,
                                       geometry_points=built.curve.points))
    result = SimpleNamespace(iterations=records, final_iteration=records[-1],
                             diagnostics={"optimizer_records": []})
    matched.geometry_diagnostics(model, controller, geometry, result, tmp_path)
    report = json.loads((tmp_path / "geometry_trajectory.json").read_text())
    assert len(report) == 2
    assert report[1]["raw_correspondence"]["missing_normal_intersections"] == 0
    assert report[1]["converted_correspondence"]["missing_normal_intersections"] == 0
    assert "nearest-target squared-distance" in report[1]["signed_target_score_definition"]
    assert "signed_effect_by_mode" in report[1]["raw_motion_spectrum"]
    np.testing.assert_array_equal(controller.parameter_vector(), next_weights)


def test_posthoc_failure_restores_final_accepted_weights(tmp_path, monkeypatch):
    model, controller, _, _, geometry = neural_case()
    initial = controller.parameter_vector()
    def fail(*args):
        controller.assign(initial + 1e-5)
        raise RuntimeError("diagnostic failure")
    monkeypatch.setattr(matched, "_geometry_diagnostics_impl", fail)
    result = SimpleNamespace(final_iteration=SimpleNamespace(parameter_vector=initial))
    with pytest.raises(RuntimeError, match="diagnostic failure"):
        matched.geometry_diagnostics(model, controller, geometry, result, tmp_path)
    np.testing.assert_array_equal(controller.parameter_vector(), initial)


@pytest.mark.parametrize("arguments", [["--accepted-updates", "6"], ["--candidate-cap", "121"],
                                        ["--wall-seconds", "nan"], ["--state", "-1"]])
def test_bounded_comparison_rejects_uncapped_settings(arguments):
    with pytest.raises(SystemExit):
        matched.parse_args(arguments)


def test_conditional_arms_require_explicit_hash_bound_measured_evidence(tmp_path):
    evidence_path = tmp_path / "decisions.json"
    args = matched.parse_args(["--comparison", "high_band", "--sampling", "contour_band"])
    with pytest.raises(ValueError, match="evidence"):
        matched.validate_evidence(args)
    report = tmp_path / "measured.json"
    report.write_text('{"measured": true}')
    evidence = {key: {"supported": True, "reason": "Measured diagnosis supports this isolated comparison",
                      "report": report.name, "report_sha256": matched.sha256(report)}
                for key in matched.required_evidence(args)}
    evidence_path.write_text(json.dumps(evidence))
    args.evidence = evidence_path
    assert matched.validate_evidence(args)["decisions"] == evidence
    report.write_text('{"changed": true}')
    with pytest.raises(ValueError, match="SHA256"):
        matched.validate_evidence(args)


def test_sampling_and_frequency_comparisons_change_one_factor_and_keep_disjoint_evaluation():
    s0, s1 = matched.comparison_arms("sampling")
    assert s0[1:3] == s1[1:3]
    assert (s0[3], s1[3]) == ("uniform_box", "contour_band")
    for comparison in ("sampling", "acquisition", "high_band"):
        for _, acquisition, frequencies, _ in matched.comparison_arms(comparison):
            assert len(frequencies) == 2
            assert 3.0 not in frequencies
            problem = matched.build_problem(acquisition, frequencies)
            expected = 12 if acquisition == "paired12" else 64 if acquisition == "multistatic" else 8
            assert problem.num_measurements == expected


def test_matched_audit_repairs_sampling_without_changing_production_geometry_or_limits():
    _, _, _, _, source = neural_case()
    source = replace(source, conversion_tolerance_m=2e-4)
    settings = matched.matched_geometry_config(source)
    for key in ("grid_shape", "bandwidth", "num_nodes", "projected_samples",
                "arclength_dense_resolution", "validation_resolution", "bounds"):
        assert getattr(settings, key) == getattr(source, key)
    assert settings.conversion_audit_grid_shape == (513, 513)
    assert settings.conversion_audit_samples == 1024
    assert settings.conversion_tolerance_m == source.conversion_tolerance_m == 2e-4


def test_inverse_requires_existing_qualification_before_loading_initial(tmp_path, monkeypatch):
    args = matched.parse_args(["--action", "run", "--output-dir", str(tmp_path)])
    monkeypatch.setattr(matched, "load_initial", lambda *args: pytest.fail("must gate before weights"))
    with pytest.raises(ValueError, match="qualify first"):
        matched.run(args, {})


@pytest.mark.parametrize("qualification_status", [0, 1])
def test_one_command_runs_inverse_only_after_qualification(tmp_path, monkeypatch, qualification_status):
    events = []
    def qualify(args, evidence):
        events.append("qualify")
        return qualification_status
    def inverse(args, evidence):
        events.append("inverse")
        return 0
    monkeypatch.setattr(matched, "qualify", qualify)
    monkeypatch.setattr(matched, "run", inverse)
    assert matched.main(["--action", "all", "--output-dir", str(tmp_path)]) == qualification_status
    assert events == (["qualify", "inverse"] if qualification_status == 0 else ["qualify"])


def test_one_command_uses_fresh_output_by_default():
    first = matched.parse_args(["--action", "all"])
    second = matched.parse_args(["--action", "all"])
    assert first.output_dir != second.output_dir
    assert first.accepted_updates == 5 and first.candidate_cap == 120


@pytest.mark.parametrize("fail_posthoc", [False, True])
def test_both_training_arms_finish_before_evaluation_and_share_saved_start(tmp_path, monkeypatch, fail_posthoc):
    model, controller, _, data, geometry = neural_case()
    vector = controller.parameter_vector()
    initial = {"state_dict": copy.deepcopy(model.state_dict()), "parameter_vector": vector,
               "optimizer_state_dict": torch.optim.Adam(model.parameters(), lr=.001).state_dict()}
    torch.save(initial, tmp_path / "shared_initial.pt")
    np.savez(tmp_path / "observations.npz", E0=data.observed_scattered_response,
             E1=data.observed_scattered_response, evaluation=data.observed_scattered_response)
    args = matched.parse_args(["--output-dir", str(tmp_path), "--accepted-updates", "1"])
    events = []
    monkeypatch.setattr(matched, "require_qualification", lambda *a: {"initial_sha256": "shared"})
    monkeypatch.setattr(matched, "build_problem", lambda *a: data.forward_problem)

    def restore(*args):
        cloned = copy.deepcopy(model)
        control = TorchParameterController(cloned, lower_bounds=-10., upper_bounds=10.,
                                            max_parameters=controller.num_parameters)
        return cloned, control, geometry, {}

    def inverse(model, control, data, geometry, **kwargs):
        events.append("training")
        np.testing.assert_array_equal(control.parameter_vector(), vector)
        assert kwargs["optimizer_state_dict"] == initial["optimizer_state_dict"]
        assert kwargs["config"].max_iterations == 1
        assert kwargs["config"].max_candidate_evaluations == 120
        record = SimpleNamespace(iteration=0, parameter_vector=vector, loss=.1, objective=.11,
                                 eikonal_loss=1., data_gradient_norm=1., weighted_eikonal_gradient_norm=.1,
                                 conversion_error_m=0., conversion_refinement_change_m=0.,
                                 boundary_movement_m=0., geometry_points=np.array([[.45, .45], [.55, .45], [.5, .55]]))
        return SimpleNamespace(iterations=[record], final_iteration=record,
                               diagnostics={"trial_records": [], "rejection_reason_counts": {}},
                               stop_reason="test", total_seconds=.01)

    def evaluation(*args, **kwargs):
        assert events[:2] == ["training", "training"]
        events.append("evaluation")
        if fail_posthoc and len(events) == 3:
            raise RuntimeError("failed independent evaluation")
        return SimpleNamespace(scattered_response=data.observed_scattered_response)

    monkeypatch.setattr(matched, "load_initial", restore)
    monkeypatch.setattr(matched, "run_implicit_mlp_adjoint_inverse", inverse)
    monkeypatch.setattr(matched, "predict_indexed_response", evaluation)
    monkeypatch.setattr(matched, "geometry_diagnostics", lambda *a: None)
    assert matched.run(args, {}) == (2 if fail_posthoc else 0)
    assert events == ["training", "training", "evaluation", "evaluation"]
    summary = json.loads((tmp_path / "metrics.json").read_text())
    assert summary["status"] == ("inverses_complete_posthoc_incomplete" if fail_posthoc else "complete")
    if fail_posthoc:
        assert summary["arms"]["E0"]["trajectory"][0]["evaluation_3ghz_relative_l2"] is None
        assert (tmp_path / "E0" / "inverse_result.pt").exists()
        assert (tmp_path / "E1" / "inverse_result.pt").exists()


def test_long_profile_declares_bounded_acquisition_and_deterministic_reporting_without_work(monkeypatch, capsys):
    monkeypatch.setattr(matched, "load_initial", lambda *a: pytest.fail("A plan must not load weights"))
    monkeypatch.setattr(matched, "qualify", lambda *a: pytest.fail("A plan must not qualify"))
    assert matched.main(["--experiment", "long"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["experiment"] == "long"
    assert plan["caps_per_arm"] == {"accepted_updates": 60, "attempted_candidates": 1440, "wall_seconds": 3600.}
    assert plan["required_evidence"] == ["stage7_supports_long_acquisition"]
    assert plan["initialization"]["state"] == 0
    assert [arm[1] for arm in plan["arms"]] == ["paired", "multistatic"]
    assert plan["reporting_policy"]["proposal_selection_uses_target_or_evaluation"] is False
    first = matched.parse_args(["--experiment", "long", "--action", "all"])
    second = matched.parse_args(["--experiment", "long", "--action", "all"])
    assert first.output_dir.name.startswith("long-acquisition-")
    assert first.output_dir != second.output_dir


@pytest.mark.parametrize("options", [
    ["--accepted-updates", "61"], ["--candidate-cap", "1441"],
    ["--comparison", "sampling"], ["--comparison", "high_band"],
    ["--sampling", "contour_band"], ["--state", "1"],
])
def test_long_profile_rejects_extra_factors_unreviewed_start_and_unbounded_work(options):
    with pytest.raises(SystemExit):
        matched.parse_args(["--experiment", "long", *options])


def _long_evidence(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "kress_model.pt").write_bytes(b"reviewed saved checkpoint bytes")
    (bundle / "kress_trajectory.csv").write_text("iteration,raw_weight\n0,1\n")
    args = matched.parse_args(["--experiment", "long", "--bundle", str(bundle),
                                "--evidence", str(tmp_path / "decisions.json")])
    promotion = {"reviewed_initialization": matched.reviewed_initialization(args),
                 "selected_principal_factor": "acquisition", "status": "supports_long_controlled_comparison"}
    report_path = tmp_path / "promotion.json"
    report_path.write_text(json.dumps(promotion))
    evidence = {"stage7_supports_long_acquisition": {
        "supported": True, "reason": "Measured signed geometry improvement at matched work",
        "report": "promotion.json", "report_sha256": matched.sha256(report_path)}}
    args.evidence.write_text(json.dumps(evidence))
    return args, promotion, evidence


def test_long_profile_requires_hash_bound_promotion_for_the_requested_initialization(tmp_path):
    args, promotion, evidence = _long_evidence(tmp_path)
    assert matched.validate_evidence(args)["decisions"] == evidence
    (args.bundle / "kress_trajectory.csv").write_text("iteration,raw_weight\n0,2\n")
    with pytest.raises(ValueError, match="reviewed_initialization"):
        matched.validate_evidence(args)


@pytest.mark.parametrize("changed", ["checkpoint_sha256", "trajectory_sha256", "state"])
def test_hash_bound_but_unrelated_promotion_cannot_authorize_long_inverse(tmp_path, changed):
    args, promotion, evidence = _long_evidence(tmp_path)
    promotion["reviewed_initialization"][changed] = 47 if changed == "state" else "unrelated"
    report_path = args.evidence.parent / "promotion.json"
    report_path.write_text(json.dumps(promotion))
    evidence["stage7_supports_long_acquisition"]["report_sha256"] = matched.sha256(report_path)
    args.evidence.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="reviewed_initialization"):
        matched.validate_evidence(args)


def test_long_missing_evidence_stops_before_frozen_work(tmp_path, monkeypatch):
    monkeypatch.setattr(matched, "qualify", lambda *a: pytest.fail("No qualification without promotion evidence"))
    with pytest.raises(SystemExit, match="stage7_supports_long_acquisition"):
        matched.main(["--experiment", "long", "--action", "all", "--output-dir", str(tmp_path)])
    assert not (tmp_path / "run.log").exists()


def test_long_qualification_signature_binds_profile_caps_and_reporting(tmp_path):
    args, _, _ = _long_evidence(tmp_path)
    evidence = matched.validate_evidence(args)
    signature = matched.settings_signature(args, evidence)
    assert signature["experiment"] == "long"
    assert signature["reporting_policy"] == matched.reporting_policy("long")
    assert signature["caps_per_arm"]["attempted_candidates"] == 1440
    args.accepted_updates = 10
    assert matched.settings_signature(args, evidence) != signature


@pytest.mark.parametrize("dependency", [
    "solvers/gpr_bem_kress/shape_derivative.py",
    "solvers/gpr_bem_kress/geometry_pullback.py",
    "solvers/sdf_inverse/nystrom_oracle.py",
    "solvers/gpr_bem_ref/neural_sdf.py",
])
def test_numerical_dependency_change_invalidates_qualification_signature(tmp_path, monkeypatch, dependency):
    args, _, _ = _long_evidence(tmp_path)
    evidence = matched.validate_evidence(args)
    signature = matched.settings_signature(args, evidence)
    assert dependency in signature["source_sha256"]
    original_sha256 = matched.sha256
    def changed_hash(path):
        return "changed numerical dependency" if path == matched.ROOT / dependency else original_sha256(path)
    monkeypatch.setattr(matched, "sha256", changed_hash)
    assert matched.settings_signature(args, evidence) != signature


@pytest.mark.parametrize("count,expected", [(0, []), (1, [0]), (5, [0, 4]),
                                            (11, [0, 10]), (60, [0, 10, 20, 30, 40, 50, 59])])
def test_long_finite_probe_selection_is_bounded_and_retains_terminal_proposal(count, expected):
    records = [{"iteration": i, "loss": count-i} for i in range(count)]
    assert matched.selected_proposal_iterations(records, "long") == expected
    assert matched.selected_proposal_iterations(records, "short") == list(range(count))
    for record in records:
        record["loss"] = -record["loss"]
    assert matched.selected_proposal_iterations(records, "long") == expected


def test_long_optimizer_checkpoints_write_each_full_record_once_and_preserve_short_layout(tmp_path, monkeypatch):
    saves = []
    real_save = matched.torch.save
    def save(value, path):
        saves.append((type(value), str(path)))
        real_save(value, path)
    monkeypatch.setattr(matched.torch, "save", save)
    callback, manifest = matched.optimizer_checkpoint_writer(tmp_path, "long")
    for i in range(3):
        callback({"iteration": i, "raw_adam_proposal": np.array([i]),
                  "optimizer_before": {"state": {"exp_avg": torch.tensor([float(i)])}}})
    assert len(saves) == 3
    assert all(kind is dict for kind, _ in saves)
    assert not (tmp_path / "optimizer_records.pt").exists()
    assert [row["iteration"] for row in manifest] == [0, 1, 2]
    for row in manifest:
        saved = torch.load(tmp_path / row["file"], weights_only=False)
        assert saved["iteration"] == row["iteration"]
        assert "optimizer_before" in saved
    short, _ = matched.optimizer_checkpoint_writer(tmp_path, "short")
    short({"iteration": 0})
    short({"iteration": 1})
    assert torch.load(tmp_path / "optimizer_records.pt", weights_only=False) == [{"iteration": 0}, {"iteration": 1}]


def test_long_orchestration_saves_all_optimizer_states_before_evaluation_and_subsamples_only_finite_geometry(tmp_path, monkeypatch):
    model, controller, _, data, geometry = neural_case()
    vector = controller.parameter_vector()
    initial = {"state_dict": copy.deepcopy(model.state_dict()), "parameter_vector": vector,
               "optimizer_state_dict": torch.optim.Adam(model.parameters(), lr=.001).state_dict()}
    torch.save(initial, tmp_path / "shared_initial.pt")
    np.savez(tmp_path / "observations.npz", E0=data.observed_scattered_response,
             E1=data.observed_scattered_response, evaluation=data.observed_scattered_response)
    args = matched.parse_args(["--experiment", "long", "--accepted-updates", "13",
                                "--output-dir", str(tmp_path)])
    events = []
    monkeypatch.setattr(matched, "require_qualification", lambda *a: {"initial_sha256": "shared"})
    monkeypatch.setattr(matched, "build_problem", lambda *a: data.forward_problem)

    def restore(*args):
        cloned = copy.deepcopy(model)
        control = TorchParameterController(cloned, lower_bounds=-10., upper_bounds=10.,
                                           max_parameters=controller.num_parameters)
        return cloned, control, geometry, {}

    def inverse(model, control, data, geometry, **kwargs):
        events.append("training")
        np.testing.assert_array_equal(control.parameter_vector(), vector)
        assert kwargs["optimizer_state_dict"] == initial["optimizer_state_dict"]
        assert kwargs["config"].max_iterations == 13
        assert kwargs["config"].max_candidate_evaluations == 1440
        proposals = []
        records = []
        for i in range(14):
            record = SimpleNamespace(iteration=i, parameter_vector=vector, loss=.1, objective=.11,
                eikonal_loss=1., data_gradient_norm=1., weighted_eikonal_gradient_norm=.1,
                conversion_error_m=0., conversion_refinement_change_m=0., boundary_movement_m=0.,
                geometry_points=np.array([[.45, .45], [.55, .45], [.5, .55]]))
            records.append(record)
            kwargs["progress_callback"](record)
            if i < 13:
                proposal = {"iteration": i, "parameter_vector": vector, "raw_adam_proposal": np.zeros_like(vector),
                            "optimizer_before": {"state": {"step": i, "exp_avg": torch.tensor([float(i)])}}}
                proposals.append(proposal)
                kwargs["optimizer_callback"](proposal)
        return SimpleNamespace(iterations=records, final_iteration=records[-1],
            diagnostics={"optimizer_records": proposals, "trial_records": [], "rejection_reason_counts": {}},
            stop_reason="maximum_iterations", total_seconds=.01)

    def evaluation(*args, **kwargs):
        assert events[:2] == ["training", "training"]
        assert all((tmp_path / arm / "inverse_result.pt").is_file() for arm in ("E0", "E1"))
        events.append("evaluation")
        return SimpleNamespace(scattered_response=data.observed_scattered_response)

    def posthoc(model, control, geometry, result, directory, *, proposal_iterations):
        events.append("geometry")
        assert proposal_iterations == [0, 10, 12]
        assert len(result.iterations) == 14
        assert len(result.diagnostics["optimizer_records"]) == 13

    monkeypatch.setattr(matched, "load_initial", restore)
    monkeypatch.setattr(matched, "run_implicit_mlp_adjoint_inverse", inverse)
    monkeypatch.setattr(matched, "predict_indexed_response", evaluation)
    monkeypatch.setattr(matched, "geometry_diagnostics", posthoc)
    assert matched.run(args, {}) == 0
    assert events.count("training") == 2
    assert events.count("evaluation") == 28
    assert events.count("geometry") == 2
    for arm in ("E0", "E1"):
        directory = tmp_path / arm
        assert len(list(directory.glob("accepted_*.pt"))) == 14
        assert len(list(directory.glob("optimizer_*.pt"))) == 13
        assert not (directory / "optimizer_records.pt").exists()
        manifest = json.loads((directory / "optimizer_manifest.json").read_text())
        assert manifest["optimizer_record_count"] == 13
        assert [row["iteration"] for row in manifest["records"]] == list(range(13))
        result = torch.load(directory / "inverse_result.pt", weights_only=False)
        assert len(result.diagnostics["optimizer_records"]) == 13
        selection = json.loads((directory / "proposal_geometry_selection.json").read_text())
        assert selection["selected_optimizer_iterations"] == [0, 10, 12]
        assert selection["accepted_geometry_state_count"] == 14
        summary = json.loads((directory / "metrics.json").read_text())
        assert summary["optimizer_record_count"] == 13
        assert summary["finite_proposal_optimizer_iterations"] == [0, 10, 12]
