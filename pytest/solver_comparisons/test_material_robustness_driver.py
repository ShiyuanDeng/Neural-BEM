"""Immutable replay, independent data generation and selection/audit barrier."""

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_material_robustness_comparison as driver


def test_circle_data_acquisition_and_initials_are_verbatim_historical_replay(monkeypatch):
    # A regeneration call would fail this test; the loader must only read.
    import run_material_inverse_comparison as historical_driver
    monkeypatch.setattr(historical_driver, "mie_response", lambda *args, **kwargs: pytest.fail("Regenerated circle data"))
    circle = driver.load_frozen_circle()
    manifest = json.loads((driver.FROZEN_D/"manifest.json").read_text())
    with np.load(driver.FROZEN_D/"arrays.npz", allow_pickle=False) as source:
        for name, values in circle.arrays().items():
            np.testing.assert_array_equal(values, source[name])
            assert not values.flags.writeable
        np.testing.assert_array_equal(circle.train_problem.source_strengths, source["train_source_strengths"])
        np.testing.assert_array_equal(circle.holdout_problem.source_points, source["holdout_source_points"])
    assert circle.provenance["regenerated"] is False
    definitions = driver.workflow_definitions(circle)
    assert len(definitions) == 15
    assert sum(not definition["joint_shape"] for definition in definitions) == 3
    historical = next(arm["initial"] for arm in manifest["arms"] if arm["name"] == "joint_clean_start2")
    np.testing.assert_array_equal(definitions[0]["initial_physical"], historical)


def test_new_target_has_opposite_contrast_and_independent_oracle_not_kress(monkeypatch):
    circle = driver.load_frozen_circle()
    assert driver.NONCIRCULAR_TRUTH[5] > circle.train_problem.exterior.epsr > circle.truth_physical[5]
    assert np.linalg.norm(driver.NONCIRCULAR_TRUTH[3:5]) > 0
    calls = []
    def fake_oracle(problem, parameterization, *, num_nodes, curve_name):
        calls.append((problem.interior.epsr, num_nodes))
        points, derivatives = parameterization(np.arange(16)*2*np.pi/16)
        assert points.shape == derivatives.shape == (16, 2)
        assert np.min(np.linalg.norm(derivatives, axis=1)) > 0
        return types.SimpleNamespace(scattered_response=np.ones((problem.num_pairs, problem.num_frequencies), complex)*(1+1j),
            num_nodes=num_nodes, maximum_linear_system_relative_residual=1e-14)
    monkeypatch.setattr(driver, "nystrom_paired_response", fake_oracle)
    monkeypatch.setattr(driver, "MaterialCurveEvaluator", lambda *args, **kwargs: pytest.fail("Production forward generated truth"))
    case = driver.independent_noncircular(circle, oracle_nodes=(32, 64))
    assert calls == [(8.4, 32), (8.4, 64), (8.4, 32), (8.4, 64)]
    assert case.train_problem.interior.epsr == circle.train_problem.interior.epsr  # Not a truth prior.
    assert case.provenance["train_reference"]["passed"]
    assert np.linalg.norm(case.train_noise) > 0
    first = driver.noisy_copy(case.train_clean, seed=4306)
    np.testing.assert_array_equal(first[0], case.train_noisy)
    assert not case.holdout_clean.flags.writeable


def test_unresolved_oracle_is_not_accepted_as_data(monkeypatch):
    circle = driver.load_frozen_circle()
    def drifting(problem, parameterization, *, num_nodes, curve_name):
        return types.SimpleNamespace(scattered_response=np.full((problem.num_pairs, problem.num_frequencies), complex(num_nodes)), num_nodes=num_nodes)
    monkeypatch.setattr(driver, "nystrom_paired_response", drifting)
    with pytest.raises(RuntimeError, match="refinement gate"):
        driver.refined_native_oracle(circle.train_problem, driver.NONCIRCULAR_TRUTH, nodes=(32, 64))


def test_all_selections_are_sealed_before_any_holdout_or_truth_qualification(monkeypatch, tmp_path):
    @dataclass(frozen=True)
    class Config:
        policy: str
        nodes: int
        stage_max_evaluations: tuple
        maximum_forward_solves: int
        maximum_direction_evaluations: int
        screening_keep: int
    circle = driver.load_frozen_circle()
    definitions = driver.workflow_definitions(circle)[:3]
    calls, qualifications = [], []
    def solve(problem, observed, initial_physical, *, joint_shape, config):
        assert qualifications == []
        assert problem is circle.train_problem
        np.testing.assert_array_equal(observed, circle.train_clean)
        calls.append(config.policy)
        physical, state = driver.candidate_state(driver.scaled_parameters(initial_physical))
        selected = types.SimpleNamespace(physical=physical, state=state, scaled=driver.scaled_parameters(physical))
        return selected, {"selected_physical": physical.tolist(), "selected_training_loss": 1.,
            "verified_stationarity": False, "search_completed": True, "budget_exhausted": False,
            "status": "fixture_only", "stages": [], "screening": [], "candidates": [],
            "work": {"forward_solves": 1, "analytic_direction_evaluations": 0}, "selected_diagnostics": {}}
    fake = types.ModuleType("sdf_inverse.robust_material_inverse")
    fake.RobustMaterialConfig, fake.solve_robust_material = Config, solve
    monkeypatch.setitem(sys.modules, "sdf_inverse.robust_material_inverse", fake)
    monkeypatch.setattr(driver, "load_frozen_circle", lambda *args, **kwargs: circle)
    monkeypatch.setattr(driver, "independent_noncircular", lambda *args, **kwargs: replace(circle, name="noncircular"))
    monkeypatch.setattr(driver, "workflow_definitions", lambda *args: definitions)
    def qualification(case, definition, selected, report, args, arrays):
        assert len(calls) == len(definitions)
        checkpoint = json.loads((args.output/"selections.json").read_text())
        assert checkpoint["phase_complete"] and not checkpoint["qualification_started"]
        assert len(checkpoint["selected_parameter_hashes"]) == len(definitions)
        qualifications.append(definition["name"])
        return {"status": "fixture_only", "physical_recovery_passed": False, "seconds": 0., "work": {}}
    monkeypatch.setattr(driver, "qualify_selected", qualification)
    args = driver.parser().parse_args(["--output", str(tmp_path/"artifact")])
    result = driver.run(args)
    assert len(qualifications) == len(definitions)
    assert result["observations_and_acquisition_unchanged"]
    assert result["selection_checkpoint_unchanged"]
    assert result["workflow_work_totals"]["forward_solves"] == 3
    assert hashlib.sha256((args.output/"selections.json").read_bytes()).hexdigest() == result["selection_file_sha256"]
    with np.load(args.output/"arrays.npz", allow_pickle=False) as archive:
        assert all(not archive[name].dtype.hasobject for name in archive.files)
        np.testing.assert_array_equal(archive["circle_train_clean"], circle.train_clean)
    json.loads((args.output/"metrics.json").read_text(), parse_constant=lambda value: pytest.fail(value))
    with pytest.raises(FileExistsError):
        driver.run(args)


def test_no_selected_candidate_is_explicitly_unqualified():
    audit = driver.qualify_selected(None, None, None, {}, None, {})
    assert audit["status"] == "no_selected_candidate"
    assert not audit["physical_recovery_passed"]
    assert audit["forward_audits"] == []


def test_tiny_real_core_workflow_replays_selected_fullband_objective(monkeypatch, tmp_path):
    circle = driver.load_frozen_circle()
    definition = next(item for item in driver.workflow_definitions(circle)
                      if item["name"] == "circle_fixed_clean_full_band")
    monkeypatch.setattr(driver, "load_frozen_circle", lambda *args, **kwargs: circle)
    monkeypatch.setattr(driver, "independent_noncircular", lambda *args, **kwargs: replace(circle, name="noncircular"))
    monkeypatch.setattr(driver, "workflow_definitions", lambda *args: [definition])
    args = driver.parser().parse_args(["--output", str(tmp_path/"real_core"), "--nodes", "16",
        "--audit-nodes", "16", "32", "--stage-max-evaluations", "1", "1"])
    result = driver.run(args)
    record = result["records"][0]
    assert record["workflow"]["work"]["forward_solves"] > 0
    assert record["qualification"]["selected_training_loss_replay_absolute_difference"] < 1e-12
    assert not record["qualification"]["physical_recovery_passed"]
    assert result["selection_checkpoint_unchanged"]
