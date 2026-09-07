"""A real small C1/C2 solve and replayable, strict artifact checks."""

import json

import numpy as np
import pytest

from ordered_boundary import BoundaryValidationConfig, validate_periodic_parameterization
from run_parameterization_aware_comparison import build_case, decision_records, main, parse_args


@pytest.fixture(scope="module")
def ellipse_bundle(tmp_path_factory):
    output = tmp_path_factory.mktemp("parameter-aware") / "bundle"
    argv = ["--output", str(output), "--cases", "ellipse", "--bandwidths", "1",
            "--bem-nodes", "32,64", "--grid-size", "65", "--projected-samples", "32",
            "--audit-samples", "32", "--localization-samples", "128",
            "--fit-iterations", "40", "--oracle-initial-nodes", "64",
            "--oracle-maximum-nodes", "128"]
    assert main(argv) == 0
    return output, argv


def _read(path):
    def invalid_constant(value):
        raise AssertionError(f"Non-standard JSON numeric constant {value}")
    return json.loads(path.read_text(), parse_constant=invalid_constant)


def test_exact_ellipse_control_keeps_set_fixed_and_refines_actual_fields(ellipse_bundle):
    output, _ = ellipse_bundle
    payload = _read(output/"metrics.json")
    rows = [row for row in payload["rows"] if row["comparison"] == "C1"]
    assert len(rows) == 4
    assert max(row["geometry"]["symmetric_set_distance_m"] for row in rows) < 1e-12
    assert all(row["fit_diagnostics"]["finite_band_refit"] is False for row in rows)
    finest = [row for row in rows if row["bem_nodes"] == 64]
    assert max(row["field_relative_l2"] for row in finest) < 1e-6
    assert _read(output/"manifest.json")["references"]["ellipse"]["passed"]


def test_all_fits_use_identical_frozen_input_and_preserve_replay_coefficients(ellipse_bundle):
    output, _ = ellipse_bundle
    payload = _read(output/"metrics.json")
    rows = [row for row in payload["rows"] if row["comparison"] == "C2"]
    hashes = {row["frozen_projected_points_sha256"] for row in rows}
    assert len(hashes) == 1 and None not in hashes
    coarse = {row["arm"]: row for row in rows if row["bem_nodes"] == 32}
    assert coarse["ordered-label-unregularized"]["field_relative_l2"] < coarse["skip-arclength"]["field_relative_l2"] / 100
    for path in output.rglob("*.npz"):
        with np.load(path, allow_pickle=False) as arrays:
            assert all(not arrays[name].dtype.hasobject for name in arrays.files)
    with np.load(output/"curves"/"C2-ellipse-ordered-label-unregularized-k1.npz", allow_pickle=False) as arrays:
        labels = arrays["optimized_labels"]
        assert labels[0] == 0 and labels[-1] < 2*np.pi and np.all(np.diff(labels) > 0)
        assert arrays["cosine_coefficients"].shape == (2, 2)
        assert arrays["predictions"].shape == (2, 12, 2)


def test_artifact_has_physical_and_dirty_content_provenance_and_refuses_overwrite(ellipse_bundle):
    output, argv = ellipse_bundle
    manifest = _read(output/"manifest.json")
    assert manifest["experiment"]["exterior"]["epsr"] == 6
    assert len(manifest["experiment"]["source_points"]) == 12
    assert manifest["experiment"]["source_strengths"][0]["imag"] == pytest.approx(.2e-6)
    hashes = manifest["provenance"]["source_sha256"]
    assert len(hashes["solvers/sdf_to_ordered_boundary/parameter_aware.py"]) == 64
    assert "docs/codex_sdf_kress_priorities_2026-09-05.md" in hashes
    assert "kress_solve_config" in manifest
    before = (output/"metrics.json").read_bytes()
    with pytest.raises(FileExistsError, match="nonempty"):
        main(argv)
    assert (output/"metrics.json").read_bytes() == before


def test_nonstar_reference_is_simple_general_cartesian_curve_with_empty_visibility_kernel():
    case = build_case("nonstar")
    curve = case.native.to_parameterization()
    samples = curve.evaluate(np.arange(512)*2*np.pi/512)
    assert case.native.bandwidth == 2
    assert np.max(np.abs(case.field.value(samples.points))) < 1e-12
    gradient = case.field.gradient(samples.points)
    assert np.max(np.abs(np.sum(gradient*samples.first_derivatives, axis=-1))) < 1e-11
    report = validate_periodic_parameterization(curve, BoundaryValidationConfig(
        num_samples_per_component=512), raise_on_error=True)
    assert report.valid and report.orientation == "counterclockwise"
    assert case.physical_parameters["visibility_kernel_upper_y"] < case.physical_parameters["visibility_kernel_lower_y"]


def test_odd_bem_counts_are_rejected_before_writing(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(["--output", str(tmp_path/"unused"), "--bem-nodes", "31"])
    assert not (tmp_path/"unused").exists()


def test_bandwidth_benefit_is_separate_from_runtime_and_unqualified_baselines():
    from types import SimpleNamespace
    args = SimpleNamespace(cases=("ellipse", "star"), bandwidths=(1, 8, 16), bem_nodes=(32, 64))
    def row(case, arm, bandwidth, *, condition, cost):
        return {"case": case, "arm": arm, "bandwidth": bandwidth, "bem_nodes": 32,
                "maximum_system_condition": condition, "total_work_seconds": cost,
                "field_relative_l2": 1e-5, "comparison": "C2", "status": "success",
                "accuracy_gate_passed": True}
    rows = [row("ellipse", "B-arclength", 16, condition=3500, cost=1.0),
            row("ellipse", "ordered-label-unregularized", 1, condition=3400, cost=.98),
            row("star", "ordered-label-unregularized", 8, condition=6000, cost=1.2)]
    decisions = decision_records(rows, args)
    ellipse = next(item for item in decisions if item["case"] == "ellipse"
                   and item["arm"] == "ordered-label-unregularized")
    assert not ellipse["matched_work_win_observed"]
    assert ellipse["bandwidth_comparison"]["lower_bandwidth_without_observed_node_or_condition_increase"]
    star = next(item for item in decisions if item["case"] == "star"
                and item["arm"] == "ordered-label-unregularized")
    assert star["candidate_eligible"] and not star["baseline_eligible"]
    assert star["bandwidth_comparison"]["baseline_unqualified_within_ladder"]
    assert not star["bandwidth_comparison"]["lower_usable_bandwidth_observed"]


def test_decision_supplement_preserves_all_measured_artifacts(ellipse_bundle):
    output, _ = ellipse_bundle
    before = {name: (output/name).read_bytes() for name in ("manifest.json", "metrics.json", "summary.md")}
    assert main(["--output", str(output), "--summarize-existing"]) == 0
    assert all((output/name).read_bytes() == value for name, value in before.items())
    supplement = _read(output/"decision_supplement.json")
    assert supplement["measurements_changed"] is False
    assert len(supplement["source_metrics_sha256"]) == 64
    assert len(supplement["postprocessing_driver_sha256"]) == 64
