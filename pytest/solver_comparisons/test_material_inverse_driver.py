"""Bounded D data, sensitivity and artifact contracts."""

import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_material_inverse_comparison as driver


def test_noise_cohorts_are_reproducible_and_holdout_angles_disjoint():
    train, holdout = driver.acquisition(), driver.acquisition(holdout=True)
    first = driver.frozen_observations(train)
    second = driver.frozen_observations(train)
    for a, b in zip(first[:3], second[:3]):
        np.testing.assert_array_equal(a, b)
        assert not a.flags.writeable
    assert np.linalg.norm(first[2]) > 0
    assert first[3]["passed"]
    distances = np.linalg.norm(train.source_points[:, None]-holdout.source_points[None], axis=-1)
    assert np.min(distances) > .01


def test_mie_sensitivity_call_accounting_and_frozen_gate(monkeypatch):
    problem = driver.acquisition(pairs=4)
    observed = driver.mie_response(problem, interior_epsr=3.)
    original = driver.mie_response
    calls = []
    def counted(*args, **kwargs):
        calls.append(kwargs["interior_epsr"])
        return original(*args, **kwargs)
    monkeypatch.setattr(driver, "mie_response", counted)
    records, arrays = driver.sensitivity_audit(problem, observed, nodes=64)
    assert len(calls) == 15
    assert sum(r["Mie_frequency_evaluations"] for r in records) == len(calls)*problem.num_frequencies
    assert all(r["passed"] for r in records)
    assert all(r["analytic_material_jvp_relative_error_to_Mie_FD"] < 1e-5 for r in records)
    assert len(arrays) == 6


def test_tiny_driver_keeps_independent_data_and_optimizer_flags_separate(monkeypatch, tmp_path):
    # One fixed-material arm; full resolution audit is unnecessary for schema.
    definition = driver.arm_definitions()[0]
    monkeypatch.setattr(driver, "arm_definitions", lambda: [definition])
    monkeypatch.setattr(driver, "sensitivity_audit", lambda *args, **kwargs:
                        ([{"passed": True, "work": {}, "Mie_frequency_evaluations": 0}], {}))
    args = driver.parser().parse_args(["--output", str(tmp_path/"tiny"), "--nodes", "32",
        "--audit-nodes", "32", "64", "--max-evaluations", "1"])
    result = driver.run(args)
    record = result["records"][0]
    assert record["status"] == "completed"
    assert not record["fit"]["optimizer_success"]
    assert not record["fit"]["verified_stationarity"]
    assert not record["physical_recovery_passed"]
    assert result["observations_unchanged"]
    assert result["material_sensitivity_validation_passed"]
    manifest = json.loads((args.output/"manifest.json").read_text())
    assert any(name.startswith("solvers/periodic_kress/") for name in manifest["provenance"]["source_sha256"])
    assert manifest["holdout_observations"]["clean_sha256"]
    json.loads((args.output/"metrics.json").read_text(), parse_constant=lambda x: pytest.fail(x))
    with np.load(args.output/"arrays.npz", allow_pickle=False) as archive:
        assert all(not archive[name].dtype.hasobject for name in archive.files)
        assert "train_noisy" in archive and "holdout_clean" in archive
    with pytest.raises(FileExistsError):
        driver.run(args)
