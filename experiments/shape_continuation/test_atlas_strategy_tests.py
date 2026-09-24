"""SC-028 schedule, budget and failure handling contracts."""
from types import SimpleNamespace

import numpy as np
import pytest

from . import atlas_strategy_tests as study
from .geometry import FourierCurve
from .lm_backend import Ledger, NORMAL_RETURN, STAGE_QUOTA, TrialSolveCap, NumericalFailure


def test_protection_changes_exactly_one_prefix_band():
    catalog = study.catalog_only("wrong_circle")
    baseline, cfg = study.schedules(catalog, "baseline")
    protect, cfg2 = study.schedules(catalog, "protect")
    assert cfg == cfg2
    assert [s.update_modes for s in baseline] == [3, 5, 7, 9]
    assert [s.update_modes for s in protect] == [2, 5, 7, 9]
    from dataclasses import replace
    assert replace(protect[0], update_modes=3) == baseline[0]
    assert protect[1:] == baseline[1:]
    assert [s.quota for s in baseline] == [1000, 1250, 1750, 4000]


def test_extension_control_has_same_bands_quotas_and_iterations_but_old_data():
    catalog = study.catalog_only("wrong_circle")
    repeat, _ = study.schedules(catalog, "baseline", "repeat")
    extend, _ = study.schedules(catalog, "protect", "extend")
    assert [s.update_modes for s in repeat] == [s.update_modes for s in extend] == [11, 13, 15, 17, 19]
    for n, (r, e) in enumerate(zip(repeat, extend), 5):
        assert r.quota == e.quota == 1500 and r.iterations == e.iterations == 22
        assert len(r.observations) == 4 and len(e.observations) == n
        np.testing.assert_allclose(r.weights, np.full(4, .25))
        np.testing.assert_allclose(e.weights, np.full(n, 1/n))
        assert all(x is y for x, y in zip(r.observations, e.observations[:4]))
        assert e.observations[-1] is catalog[study.ac.CATALOG_HZ.index(study.EXTRA_HZ[n-5])]
        assert e.discrepancy_tolerances == (1e-5, *([1e-7]*(n-1)))
    assert study.PATH_CAP == study.PREFIX_CAP + sum(s.quota for s in extend)


def test_suffix_charges_sunk_work_and_preserves_remaining_wall_budget():
    parent = dict(inverse_seconds=240., work=dict(work_units=200, solves={"stage_1:initial":100},
                    reciprocal_batches={"stage_1:derivative":100}, failed={}))
    ledger = study.restored_ledger(parent)
    assert ledger.units == 200 and ledger.cap == 15512 and ledger.seconds == 3360.
    ledger.charge("solve", "new")
    assert ledger.units == 201 and parent["work"]["work_units"] == 200
    assert "None:new" not in parent["work"]["solves"]
    ledger.units = ledger.cap-1
    with pytest.raises(TrialSolveCap):
        ledger.reserve(2)


@pytest.mark.parametrize("outcome,expected_stages", [(NORMAL_RETURN, 2), (STAGE_QUOTA, 2), ("NUMERICAL_FAILURE", 1)])
def test_segment_advances_only_after_normal_or_quota_return(tmp_path, monkeypatch, outcome, expected_stages):
    curve = FourierCurve.circle()
    called = []

    def fake_fit(initial, stage, contrast, update, config, ledger):
        assert initial is curve
        called.append(stage.label)
        return SimpleNamespace(curve=curve, history=[], trials=[], acceptance_checks=[],
                               outcome=outcome, stop_reason=None)

    monkeypatch.setattr(study, "fit_stage", fake_fit)
    stages = [SimpleNamespace(label=f"s{i}", quota=100) for i in (1, 2)]
    final, records, status, reason = study.optimize_segment(curve, stages, .5, None, None, Ledger(), tmp_path)
    assert final is curve and len(records) == len(called) == expected_stages
    assert status == ("HARD_STOP" if outcome == "NUMERICAL_FAILURE" else "COMPLETED_SCHEDULE")
    assert (tmp_path / "checkpoint.json").exists()


def test_segment_records_stop_at_stage_boundary_without_attempting_fit(tmp_path, monkeypatch):
    ledger = Ledger(seconds=0.)
    monkeypatch.setattr(study, "fit_stage", lambda *a: pytest.fail("Work dispatched after wall cap"))
    curve = FourierCurve.circle()
    final, records, status, reason = study.optimize_segment(curve,
        [SimpleNamespace(label="s1", quota=100)], .5, None, None, ledger, tmp_path)
    assert final is curve and not records and status == "HARD_STOP" and reason == "TRIAL_WALL_LIMIT"


def test_fitting_data_loader_never_opens_truth_or_evaluation(monkeypatch):
    original = study.sc.read
    opened = []

    def reader(path):
        opened.append(str(path))
        assert path.name == "observations.json"
        return original(path)

    monkeypatch.setattr(study.sc, "read", reader)
    assert len(study.catalog_only("kite")) == 19
    assert len(opened) == 1


def test_unrecognized_arm_fails_before_loading_schedule():
    with pytest.raises(ValueError):
        study.schedules((), "chosen_by_truth")
