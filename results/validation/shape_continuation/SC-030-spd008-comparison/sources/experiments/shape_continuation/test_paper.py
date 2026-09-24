"""Cheap controls for paper setup, area scoring and bounded execution."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from . import paper
from .forward import BudgetExceeded, Work
from .geometry import FourierCurve
from .metrics import area_error, polygon_area_error


def test_default_plan_has_both_contrasts_full_grid_and_no_physics(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A plan must not execute forward or inverse physics.")
    monkeypatch.setattr(paper, "solve", forbidden)
    monkeypatch.setattr(paper, "run_adaptive", forbidden)
    output = tmp_path / "plan"
    paper.main(["--output", str(output)])
    plan = json.loads((output / "plan.json").read_text())
    assert plan["status"] == "plan_only" and plan["forward_solves"] == 0
    assert [c["settings"]["contrast"] for c in plan["cases"]] == [.33, 10.]
    for case in plan["cases"]:
        assert len(case["stages"]) == 117
        assert [s["initial_circle_stage"]["wavenumber"] for s in case["stages"]] == list(np.arange(1, 30.25, .25))
        assert case["stages"][-1]["directions"] == case["stages"][-1]["receivers"] == 300
        assert case["settings"]["config"]["max_iterations"] == 50
        assert case["settings"]["config"]["backtracks"] == 0


def test_profile_separates_exterior_storage_from_shortest_wavelength_nodes():
    low = paper.Figure1Case(.33).stage(FourierCurve.circle(), 1.)
    high = paper.Figure1Case(10.).stage(FourierCurve.circle(), 1.)
    assert low.update_modes == 3 and high.update_modes == 9
    assert low.curve_modes == high.curve_modes == 70
    assert low.nodes == 142 and high.nodes == 222
    padded = FourierCurve(np.pad(FourierCurve.circle().coefficients, (199, 199)))
    later = paper.Figure1Case(.33).stage(padded, 1.)
    assert later.curve_modes == 200 and later.nodes > 400


@pytest.mark.parametrize("arguments", [
    ["--mode", "run"], ["--mode", "run", "--max-forwards", "10"],
    ["--mode", "smoke", "--k-stop", "5"],
    ["--mode", "smoke", "--max-forwards", "1000"], ["--k-stop", "1.1"],
    ["--mode", "run", "--max-forwards", "1", "--max-seconds", "nan"],
])
def test_expensive_work_requires_explicit_budgets_and_smoke_cannot_expand(tmp_path, arguments):
    output = tmp_path / "absent"
    with pytest.raises(SystemExit):
        paper.main(["--output", str(output), *arguments])
    assert not output.exists()


def test_smoke_uses_one_shared_small_budget_and_one_iteration(tmp_path, monkeypatch):
    calls = []
    def capture(case, output, work):
        calls.append((case, work))
        return dict(status="ladder_completed")
    monkeypatch.setattr(paper, "run_case", capture)
    paper.main(["--mode", "smoke", "--output", str(tmp_path / "smoke")])
    assert len(calls) == 2 and calls[0][1] is calls[1][1]
    for case, work in calls:
        assert list(case.wavenumbers) == [1.]
        assert case.config.max_iterations == 1
        assert work.max_forwards == 16 and work.max_seconds == 30


def test_failed_reference_stops_before_inverse_and_preserves_evidence(tmp_path, monkeypatch):
    pytest.importorskip("shapely")
    predictions = iter([np.zeros((10, 10), complex), np.ones((10, 10), complex)])
    monkeypatch.setattr(paper, "solve", lambda *a, **kw: SimpleNamespace(prediction=next(predictions)))
    def forbidden(*args, **kwargs):
        pytest.fail("Unqualified observations must not enter the inverse.")
    monkeypatch.setattr(paper, "run_adaptive", forbidden)
    output = tmp_path / "failed_reference"
    summary = paper.run_case(paper.Figure1Case(.33, k_stop=1.), output, Work())
    assert summary["status"] == "unqualified_observations"
    assert not summary["decisions"]
    assert (output / "observation_000.npz").exists() and (output / "endpoint.npz").exists()
    assert not summary["observation_checks"][0]["passed"]


def test_reference_budget_failure_retains_summary(tmp_path, monkeypatch):
    pytest.importorskip("shapely")
    def exhausted(*args, **kwargs):
        raise BudgetExceeded("test budget")
    monkeypatch.setattr(paper, "solve", exhausted)
    output = tmp_path / "budget"
    report = paper.run_case(paper.Figure1Case(10., k_stop=1.), output, Work())
    assert report["status"] == "budget_exhausted"
    assert json.loads((output / "summary.json").read_text())["status"] == "budget_exhausted"


def test_area_score_detects_equal_area_translation_and_is_not_area_size_error():
    pytest.importorskip("shapely")
    square = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    score = polygon_area_error(square, square + [0.5, 0.])
    assert score["relative_symmetric_difference"] == 1.
    assert score["relative_missing_area"] == score["relative_excess_area"] == .5
    assert score["true_polygon_area"] == score["recovered_polygon_area"]
    assert polygon_area_error(square, square[::-1])["relative_symmetric_difference"] == 0.
    assert polygon_area_error(square, square + 3)["relative_symmetric_difference"] == 2.


def test_area_score_handles_nonconvex_shapes_and_rejects_crossed_polygons():
    pytest.importorskip("shapely")
    square = np.array([[0., 0.], [2., 0.], [2., 2.], [0., 2.]])
    elbow = np.array([[0., 0.], [2., 0.], [2., 1.], [1., 1.], [1., 2.], [0., 2.]])
    assert polygon_area_error(square, elbow)["relative_symmetric_difference"] == .25
    with pytest.raises(ValueError, match="valid simple"):
        polygon_area_error(square, square[[0, 2, 1, 3]])


def test_curve_area_score_refines_towards_independent_circle_overlap_formula():
    pytest.importorskip("shapely")
    distance = .5
    overlap = 2 * np.arccos(distance / 2) - .5 * distance * np.sqrt(4 - distance**2)
    expected = 2 - 2 * overlap / np.pi
    truth, recovered = FourierCurve.circle(), FourierCurve.circle(center=distance)
    low = area_error(truth, recovered, count=128)
    high = area_error(truth, recovered, count=512)
    assert abs(high["relative_symmetric_difference"] - expected) < 3e-6
    assert high["refinement_absolute_change"] < low["refinement_absolute_change"] / 8
    assert high["relative_symmetric_difference"] == pytest.approx(
        high["relative_missing_area"] + high["relative_excess_area"])
    assert area_error(truth, truth, count=128)["relative_symmetric_difference"] == 0.
