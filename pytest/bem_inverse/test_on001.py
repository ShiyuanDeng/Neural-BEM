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


def test_gaussian_zero_expansion_and_raw_lipschitz_scaling_once():
    from bem_inverse.gaussian_displacement import GaussianDisplacement, kernel
    from bem_inverse.geometry import resize
    update = GaussianDisplacement(.05, device="cpu")
    space = update.prepare(resize(FourierCurve.circle(), 8), 3, 8)
    assert update.trial(space, np.zeros(7))[0] is space.curve
    a = np.zeros(7); a[0] = .001
    candidate, receipt = update.trial(space, a)
    assert abs(candidate.coefficients[candidate.band+1]) > 1
    large = a*100
    candidate, receipt = update.trial(space, large)
    assert receipt["gaussian_alpha"] < 1
    assert receipt["raw_lower_lipschitz"] >= .2-1e-14
    assert receipt["a_used"][0] == pytest.approx(receipt["gaussian_alpha"]*large[0])
    w, b = space.weights@large, space.translation@large
    rng = np.random.default_rng(0)
    x = rng.normal(size=100)+1j*rng.normal(size=100)
    mapped = x+receipt["gaussian_alpha"]*(kernel(x, space.centres, space.width)@w+b)
    assert np.all(abs(mapped[:, None]-mapped[None]) >= .2*abs(x[:, None]-x[None])-1e-12)
    # Original momenta/translation are retained; only the evaluation is scaled.
    assert receipt["gaussian_momenta_norm_sum"] == pytest.approx(sum(abs(w)))
    assert receipt["gaussian_translation"] == pytest.approx(b)


def test_gaussian_complete_projected_tangent_and_active_finite_direction():
    from bem_inverse.gaussian_displacement import GaussianDisplacement
    from bem_inverse.geometry import resize
    curve = FourierCurve(np.array([.01j, .02, .02j, .1-.05j, 1., .07, .01]))
    curve = resize(curve, 16)
    update = GaussianDisplacement(.05, device="cpu")
    space = update.prepare(curve, 5, 16)
    direction = np.random.default_rng(3).normal(size=11); direction /= np.linalg.norm(direction)
    eps = 1e-7
    plus = update.trial(space, eps*direction)[0].coefficients
    minus = update.trial(space, -eps*direction)[0].coefficients
    fd = (plus-minus)/(2*eps)
    assert np.linalg.norm(fd-space.derivatives@direction)/np.linalg.norm(fd) < 1e-5
    a = .05*direction
    assert update.trial(space, a)[1]["gaussian_alpha"] < 1
    tangent = np.random.default_rng(4).normal(size=11); tangent /= np.linalg.norm(tangent)
    fds = []
    for h in (eps, eps/2):
        p = update.trial(space, a+h*tangent)[0].coefficients
        m = update.trial(space, a-h*tangent)[0].coefficients
        fds.append((p-m)/(2*h))
    assert np.linalg.norm(fds[0]-fds[1])/np.linalg.norm(fds[1]) < 1e-5
    strict = GaussianDisplacement(.05, device="cpu", projection_tolerance=1e-16)
    from bem_inverse.continuation.updates import UpdateRefused
    with pytest.raises(UpdateRefused, match="projection"):
        strict.trial(strict.prepare(curve, 5, 16), a)


@pytest.mark.parametrize("damped", [False, True])
def test_gaussian_reciprocal_matches_full_field_fd_at_zero_and_active_clip(damped):
    from bem_inverse.gaussian_displacement import GaussianDisplacement
    from bem_inverse.geometry import resize
    from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
    p = fixture()
    observation = (p.damped if damped else p.real)[-1]
    physics = ModalMuller(Execution(device="cpu", frequency_threads=1),
                          ModalSettings(trace_minimum=16, trace_step=8, window_margin=16))
    update = GaussianDisplacement(p.length_unit_m, device="cpu")
    curve = resize(FourierCurve.circle(1., .03+.02j), 8)
    space = update.prepare(curve, 3, 8)
    direction = np.random.default_rng(7).normal(size=7); direction /= np.linalg.norm(direction)
    tangent = np.random.default_rng(8).normal(size=7); tangent /= np.linalg.norm(tangent)
    for a in (direction*0, .05*direction):
        current, receipt = update.trial(space, a)
        h = 1e-7
        plus = update.trial(space, a+h*tangent)[0]
        minus = update.trial(space, a-h*tangent)[0]
        if not np.any(a):
            delta = space.derivatives@tangent
        else:
            assert receipt["gaussian_alpha"] < 1
            hp = h/2
            delta = (update.trial(space, a+hp*tangent)[0].coefficients-
                     update.trial(space, a-hp*tangent)[0].coefficients)/(2*hp)
        predicted = physics.evaluate(current, observation, p.contrast, token(24))
        derivative = physics.derivative(predicted, update, SimpleNamespace(curve=current, derivatives=delta[:, None]))[:, 0]
        fd = (physics.evaluate(plus, observation, p.contrast, token(24)).prediction-
              physics.evaluate(minus, observation, p.contrast, token(24)).prediction)/(2*h)
        assert np.linalg.norm(derivative-fd)/np.linalg.norm(fd) < 1e-3


def test_gaussian_clip_kink_has_distinct_one_sided_derivatives():
    from bem_inverse.gaussian_displacement import GaussianDisplacement
    from bem_inverse.geometry import resize
    update = GaussianDisplacement(.05, device="cpu")
    space = update.prepare(resize(FourierCurve.circle(), 8), 3, 8)
    direction = np.zeros(7); direction[0] = 1.
    C = np.exp(-.5)*sum(abs(space.weights@direction))/space.width
    a = .8/C*direction
    middle = update.trial(space, a)[0].coefficients
    h = 1e-7
    right = (update.trial(space, a+h*direction)[0].coefficients-middle)/h
    left = (middle-update.trial(space, a-h*direction)[0].coefficients)/h
    assert np.linalg.norm(right) < 1e-6
    assert np.linalg.norm(left) > 1e-3
