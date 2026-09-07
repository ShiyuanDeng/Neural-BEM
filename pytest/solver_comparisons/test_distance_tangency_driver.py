"""Small driver checks; no training or full benchmark in regressions."""

import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_distance_tangency_comparison as driver


def test_ellipse_distance_has_same_zero_and_correct_offsurface_metric():
    cases = driver.build_cases(include_neural=False)
    exact, distorted = cases[2:]
    t = 2*np.pi*np.arange(48)/48+.002
    evaluation = exact.reference.native.to_parameterization().evaluate(t)
    derivative = evaluation.first_derivatives
    normal = np.column_stack((derivative[:, 1], -derivative[:, 0]))
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    offset = .003*np.where(np.arange(len(t))%2, -1., 1.)
    points = evaluation.points+offset[:, None]*normal
    np.testing.assert_allclose(exact.field.value(points), offset, atol=1e-13)
    np.testing.assert_allclose(exact.field.gradient(points), normal, atol=1e-11)
    np.testing.assert_allclose(distorted.field.value(evaluation.points), 0, atol=1e-13)
    np.testing.assert_allclose(np.linalg.norm(distorted.field.gradient(evaluation.points), axis=1), 1, atol=1e-11)
    assert np.max(np.abs(distorted.field.value(points)-offset)) > 1e-4


def test_tiny_artifact_is_strict_replayable_and_counts_provisioned_fallback(monkeypatch, tmp_path):
    circle = driver.build_cases(include_neural=False)[0]
    monkeypatch.setattr(driver, "build_cases", lambda **kwargs: [circle])
    args = driver.parser().parse_args(["--output", str(tmp_path/"tiny"), "--no-neural",
        "--bandwidths", "1", "--nodes", "16", "32", "--grid", "33", "--samples", "32",
        "--audit-samples", "16", "--oracle-max-nodes", "256", "--iterations", "20"])
    result = driver.run(args)
    assert len(result["records"]) == 5
    saved = json.loads((args.output/"metrics.json").read_text(), parse_constant=lambda x: pytest.fail(x))
    manifest = json.loads((args.output/"manifest.json").read_text())
    assert "run_distance_tangency_comparison.py" in manifest["provenance"]["sha256"]
    assert saved["physics"]["noise"] == {"kind": "none", "added": False}
    assert saved["cases"][0]["input_arrays_unchanged"]
    stage = saved["cases"][0]["shared_stage_queries"]
    contact = next(row for row in saved["records"] if row["arm"] == "distance_tangent_jet")
    assert contact["field_queries"] == driver.add_counts(stage["frontend"], stage["proposal"], stage["distance_contact_queries"])
    assert contact["fallback_provisioning_seconds"] > 0
    assert stage["distance_contact_queries"]["value_points"] == 64
    with np.load(args.output/"arrays.npz", allow_pickle=False) as archive:
        assert all(not archive[key].dtype.hasobject for key in archive.files)
        assert "source_strengths" in archive
        assert any(key.endswith("raw_cosine") for key in archive.files)
    with pytest.raises(FileExistsError):
        driver.run(args)


def test_decisions_exclude_fallbacks_even_when_returned_geometry_is_good():
    record = {"case": "distorted", "arm": "distance_contacts", "status": "fallback",
              "returned_audit": {"lowest_qualified_nodes": 64}}
    result = driver.decisions([record])
    assert result[0]["best_qualified"]["distance_contacts"] is None
    assert not any(item["matched_error_work_win"] for item in result[0]["comparisons"])


def test_minimum_bandwidth_is_not_confused_with_fastest_timed_bandwidth():
    def record(arm, bandwidth, seconds):
        return {"case": "circle", "arm": arm, "bandwidth": bandwidth, "status": "success",
            "conversion_seconds": seconds, "field_queries": {},
            "returned_audit": {"lowest_qualified_nodes": 64,
                "geometry": {"symmetric_set_distance_m": 1e-9},
                "physical": [{"nodes": 64, "bem_seconds": .01, "maximum_relative_field_error": 1e-6}]}}
    rows = [record("shared_zero_method_b", 1, .2), record("shared_zero_method_b", 4, .19),
            record("distance_tangent_jet", 1, .3)]
    result = driver.decisions(rows)[0]
    assert result["best_qualified"]["shared_zero_method_b"]["bandwidth"] == 4
    assert result["best_qualified"]["shared_zero_method_b"]["minimum_qualified_bandwidth"] == 1
    comparison = next(x for x in result["comparisons"]
                      if x["candidate"] == "distance_tangent_jet" and x["baseline"] == "shared_zero_method_b")
    assert comparison["lower_usable_bandwidth"] is False


@pytest.mark.skipif(not driver.FROZEN_B.exists(), reason="saved B numeric artifact unavailable")
def test_frozen_neural_numeric_state_matches_saved_values_without_training():
    case = driver.build_cases(include_neural=True)[-1]
    with np.load(driver.FROZEN_B/"arrays.npz", allow_pickle=False) as archive:
        points = archive["star_independent_points"][:32]
        values = archive["star_smooth_curve_field_distance"][:32]
    np.testing.assert_allclose(case.field.value(points), values, atol=1e-14, rtol=1e-12)
    assert driver.state_hash(case.frozen_model) == case.definition["initial_state_hashes"]
    assert not any(parameter.requires_grad for parameter in case.frozen_model.parameters())
