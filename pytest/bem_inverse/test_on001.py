from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.reach import harmonic_bound, sampled_reach, clip_direction
from bem_inverse.policy import CumulativePolicy, Operation
from bem_inverse.physics import Execution, NodalKress
from bem_inverse import runner
from experiments.cleaned_interface.test_audit_streaming import fixture


def test_circle_reach_physical_units_and_harmonic_bound():
    curve = FourierCurve.circle(1.3, .4-.2j)
    assert sampled_reach(curve, 1024) == pytest.approx(1.3, rel=1e-9)
    a = np.array([.004, .06, .015, -.02, .008])
    theta = np.linspace(0, 2*np.pi, 10001)
    h = a[0]+np.cos(theta[:, None]*[1, 2])@a[1:3]+np.sin(theta[:, None]*[1, 2])@a[3:]
    assert max(abs(h)) <= harmonic_bound(a)
    cache = {}
    clipped, receipt = clip_direction(a, curve, .05, .8, cache)
    assert harmonic_bound(clipped) == pytest.approx(.8*.05*1.3)
    assert receipt["reach_alpha"] < 1
    _, reused = clip_direction(a, curve, .05, .8, cache)
    assert reused["reach_seconds"] == 0
    zero, receipt = clip_direction(a*0, curve, .05, .8, cache)
    np.testing.assert_array_equal(zero, a*0)
    assert receipt["reach_alpha"] == 1


class ShortPolicy(CumulativePolicy):
    def operations(self, problem, physics):
        return (Operation("audit", "initial", "", "", ""),
                self._fit(problem, physics, "full", problem.real, 1, 8, 200, iterations=1),
                Operation("audit", "final", "", "", ""))


@pytest.mark.parametrize("full, passed", [(True, True), (True, False), (False, True)])
def test_early_exit_requires_full_catalog_and_audit_and_charges_failure(monkeypatch, full, passed):
    p = fixture()
    calls = []
    def audit(curve, stage, config, problem, physics, update, seconds):
        calls.append(seconds)
        return dict(passed=True if len(calls) == 1 else passed, seconds=1., work=dict(work_units=7))
    class Policy(ShortPolicy):
        def operations(self, problem, physics):
            ops = list(super().operations(problem, physics))
            if not full:
                ops[1] = self._fit(problem, physics, "subset", problem.real[:2], 1, 8, 200, iterations=1)
            return tuple(ops)
    def stage(curve, stage, contrast, update, config, ledger, on_accept, **kwargs):
        evaluation = SimpleNamespace(curve=curve, loss=0., prediction=np.column_stack(
            [o.scattered for o in stage.observations]))
        outcome = runner.NORMAL_RETURN
        try:
            on_accept(0, evaluation)
            # The failed audit cannot retry at the same residual/resolution.
            on_accept(1, evaluation)
        except runner.RequiredAccuracyReached:
            outcome = "REQUIRED_ACCURACY_REACHED"
        return SimpleNamespace(curve=curve, outcome=outcome, stop_reason="test", detail=None,
            accepted_steps=0, initial_loss=0., final_loss=0., seconds=0., history=[], trials=[], acceptance_checks=[])
    monkeypatch.setattr(runner, "fit_stage", stage)
    row = runner.fit(p, physics=NodalKress(Execution(device="cpu", frequency_threads=1)),
        policy=Policy(required_accuracy=.003, audit_aggregate_seconds=30., audit_seconds=30.), audit_adapter=audit)
    assert (row["outcome"] == "REQUIRED_ACCURACY_REACHED") == (full and passed)
    assert len(calls) == (2 if passed else 3) if full else len(calls) == 2
    assert row["audit_units"] == 7*len(calls)
    assert calls[0] == 20.
    if full:
        assert calls[1] == 19.
        assert len(row["early_audits"]) == 1
    assert row["audit_seconds"] == len(calls)
