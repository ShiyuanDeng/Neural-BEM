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


def working_fixture():
    from bem_inverse.continuation import lm_backend as lm
    from bem_inverse.continuation.forward import ordered_calls
    from bem_inverse.physics import Prediction
    from bem_inverse.working_frequency import WorkingObjective
    from test_resolution_resume import ScalarUpdate
    class Physics:
        def __init__(self):
            self.calls, self.derivatives = [], []
        def ordered_calls(self, f, items):
            return ordered_calls(f, items, threads=1)
        def evaluate(self, curve, obs, contrast, nodes):
            r = curve.coefficients[-1].real
            slope = -10. if obs.index == 3 else 1.
            self.calls.append((r, obs.index, nodes))
            return Prediction(np.array([2.+slope*(r-2)], complex), {}, slope)
        def derivative(self, evaluation, update, space):
            self.derivatives.append(evaluation._handle)
            return np.array([[evaluation._handle]], complex)
    observations = tuple(SimpleNamespace(scattered=np.ones(1, complex), index=i, wavenumber=1.) for i in range(19))
    stage = lm.FitStage("working", observations, (1/19,)*19, (1e-8,)*19, 0, 1, 8, 16, 1)
    ledger = lm.Ledger(cap=10000, endpoint_reserve=0)
    ledger.begin_stage("working", None)
    config = lm.BackendConfig(step_bounds_m=(.8,)*3, max_damping_trials=1, log_model=True)
    physics = Physics()
    return lm, WorkingObjective, stage, ledger, config, physics, ScalarUpdate()


def test_working_subset_improvement_with_full_increase_rejects_and_reuses_evaluations():
    from bem_inverse.working_frequency import WorkingSetChanged
    lm, factory, stage, ledger, config, physics, update = working_fixture()
    objective = factory(stage, .5, config, ledger, physics=physics)
    base = objective.production(FourierCurve.circle(2.), "initial")
    matrix = objective.jacobian(base, update, update.prepare(base.curve))
    assert objective.indices == (0, 1, 2, 4, 9, 14, 18)
    assert matrix.shape == (14, 1)
    np.testing.assert_allclose(.5*np.linalg.norm(objective.model_residual(base))**2, .5)
    previous = len(physics.calls)
    with pytest.raises(WorkingSetChanged):
        objective.candidate(base, FourierCurve.circle(1.2))
    assert len(physics.calls)-previous == 19  # seven reused, twelve added, none duplicated
    assert objective.last_trial["working_candidate_loss"] < .5
    assert objective.last_trial["full_candidate_loss"] > .5
    assert 3 in objective.indices and len(objective.indices) == 8
    assert ledger.units == len(physics.calls)+len(physics.derivatives)


def test_working_expansion_rebuilds_model_and_accepts_only_full_decrease():
    lm, factory, stage, ledger, config, physics, update = working_fixture()
    result = lm.fit_stage(FourierCurve.circle(2), stage, .5, update, config, ledger,
                          physics=physics, objective_factory=factory)
    assert result.trials[0]["status"] == "working_model_rebuild"
    assert result.trials[-1]["status"] == "accepted"
    assert result.final_loss < result.initial_loss
    assert result.acceptance_checks[-1]["accepted"]
    assert all(c["refined_candidate_loss"] < c["refined_base_loss"] for c in result.acceptance_checks if c["accepted"])
    assert len(physics.derivatives) > 7  # rebuild after rejected full-data proposal
    assert ledger.units == len(physics.calls)+len(physics.derivatives)


def test_working_final_polishing_and_renormalized_full_weights():
    lm, factory, stage, ledger, config, physics, update = working_fixture()
    weights = tuple(np.arange(1, 20)/190.)
    stage = replace(stage, weights=weights)
    objective = factory(stage, .5, config, ledger, physics=physics)
    base = objective.production(FourierCurve.circle(2.), "initial")
    objective.jacobian(base, update, update.prepare(base.curve))
    subset = objective.model_residual(base)
    assert .5*float(subset@subset) == pytest.approx(.5)
    assert sum(objective._subset(objective.indices).stage.weights) == pytest.approx(1.)
    accurate = replace(base, prediction=objective.observed*1.005)
    objective.jacobian(accurate, update, update.prepare(base.curve))
    assert objective.indices == tuple(range(19))
