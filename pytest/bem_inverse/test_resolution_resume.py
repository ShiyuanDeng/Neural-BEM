"""Resolution response, exact accepted-state resume, and threaded reservations."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from bem_inverse.continuation import lm_backend as lm
from bem_inverse.continuation.forward import ordered_calls
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.physics import Prediction


class ScalarUpdate:
    length_unit_m = 1.

    def settings(self):
        return dict(name='scalar_radius', length_unit_m=1.)

    def prepare(self, curve, *_):
        return SimpleNamespace(curve=curve, orders=np.array([0]))

    def trial(self, space, step):
        return FourierCurve.circle(space.curve.coefficients[-1].real+step[0]), {}


class ScalarPhysics:
    def __init__(self, mode='refine'):
        self.mode, self.calls, self.derivatives = mode, [], []

    def ordered_calls(self, function, items):
        return ordered_calls(function, items, threads=4)

    def evaluate(self, curve, obs, contrast, nodes):
        radius = curve.coefficients[-1].real
        self.calls.append((nodes, radius))
        bias = 0.
        changed = radius < (2.-1e-10 if self.mode == 'exhaust' else 1.5)
        if changed:
            if nodes == 8:
                bias = .04
            if nodes == 16 and self.mode in ('backtrack', 'exhaust'):
                bias = .02
        if self.mode == 'base_failure' and nodes == 32 and radius >= 1.5:
            bias = .02
        if self.mode == 'implementation_error' and nodes == 32:
            raise RuntimeError('bad implementation')
        return Prediction(np.array([radius+bias], complex), dict(resolution=nodes), nodes)

    def derivative(self, evaluation, update, space):
        self.derivatives.append(evaluation._handle)
        return np.ones((1, 1), complex)


def setup(mode='refine', iterations=2, nodes=8):
    physics = ScalarPhysics(mode)
    observation = SimpleNamespace(scattered=np.array([.1], complex), wavenumber=1.)
    stage = lm.FitStage('scalar', (observation,), (1.,), (1e-3,), 0, 1,
                        nodes, 2*nodes, iterations)
    config = lm.BackendConfig(step_bounds_m=(.8, .8, .8), max_damping_trials=1)
    ledger = lm.Ledger(cap=500, endpoint_reserve=0)
    ledger.begin_stage(stage.label, None)
    return physics, stage, config, ledger


def run(mode, *, nodes=8, response=True, iterations=2):
    physics, stage, config, ledger = setup(mode, iterations, nodes)
    result = lm.fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, ledger,
        physics=physics, resolution_response=lm.ResolutionResponse(16, 32, physics) if response else None)
    return result, physics, ledger


def test_default_stops_but_promotion_accepts_and_rebuilds_derivatives():
    old, _, _ = run('refine', response=False)
    assert old.outcome == 'NUMERICAL_FAILURE' and old.accepted_steps == 0
    new, physics, ledger = run('refine')
    assert new.accepted_steps == 2
    assert (new.final_nodes, new.final_refined_nodes) == (16, 32)
    assert physics.derivatives == [8, 16, 16]
    assert sum(r['action'] == 'promoted' for r in new.resolution_events) == 1
    assert ledger.units == len(physics.calls)+len(physics.derivatives)


@pytest.mark.parametrize('nodes', [8, 16])
def test_inaccurate_proposal_is_rejected_then_half_step_accepted(nodes):
    result, physics, ledger = run('backtrack', nodes=nodes, iterations=1)
    assert result.accepted_steps == 1 and result.final_nodes == nodes
    assert result.trials[0]['status'] == 'numerical_rejection'
    assert result.trials[1]['status'] == 'accepted' and result.trials[1]['backtrack'] == 1
    assert result.curve.coefficients[-1].real == pytest.approx(1.6)
    assert ledger.units == len(physics.calls)+len(physics.derivatives)


def test_finer_base_failure_is_explicit_and_keeps_last_accepted_curve():
    result, _, _ = run('base_failure')
    assert result.outcome == 'NUMERICAL_FAILURE'
    assert 'unresolved accepted base' in result.detail
    assert result.accepted_steps == 0 and result.curve.coefficients[-1] == 2


def test_exhausted_accuracy_trials_are_not_stationary():
    result, _, _ = run('exhaust')
    assert result.accepted_steps == 0
    assert result.stop_reason == 'accuracy_limited_trials_exhausted'


def test_implementation_errors_are_not_resolution_retries():
    with pytest.raises(RuntimeError, match='bad implementation'):
        run('implementation_error')


def restore(work):
    ledger = lm.Ledger(cap=work['cap'], endpoint_reserve=0)
    ledger.units = work['work_units']
    ledger.stage, ledger.stage_quota = work['stage'], work['stage_quota']
    ledger.stage_start = ledger.units-work['stage_units']
    ledger.solves, ledger.reciprocal, ledger.failed = (dict(work[k]) for k in ('solves', 'reciprocal_batches', 'failed'))
    ledger.started -= work['seconds']
    return ledger


def test_pause_resume_preserves_damping_trajectory_counters_and_cache():
    physics, stage, config, ledger = setup('refine', iterations=4, nodes=16)
    full = lm.fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, ledger, physics=physics)
    physics2, _, _, split_ledger = setup('refine', iterations=4, nodes=16)
    part = lm.fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, split_ledger,
                        physics=physics2, pause_after=2)
    assert part.outcome == 'PAUSED'
    checkpoint = part.checkpoint
    resumed = lm.fit_stage(part.curve, stage, .5, ScalarUpdate(), config, restore(checkpoint.work),
                           physics=physics2, resume=checkpoint)
    assert np.array_equal(full.curve.coefficients, resumed.curve.coefficients)
    assert full.accepted_steps == resumed.accepted_steps
    assert full.trials == resumed.trials
    for key in ('work_units', 'solves', 'reciprocal_batches', 'failed'):
        assert full.work[key] == resumed.work[key]
    assert [h['next_damping'] for h in full.history] == [h['next_damping'] for h in resumed.history]
    assert physics.calls == physics2.calls and physics.derivatives == physics2.derivatives
    bad = restore(checkpoint.work)
    bad.units += 1
    with pytest.raises(ValueError, match='ledger mismatch'):
        lm.fit_stage(part.curve, stage, .5, ScalarUpdate(), config, bad, physics=physics2, resume=checkpoint)
    with pytest.raises(ValueError, match='does not match'):
        lm.fit_stage(part.curve, stage, .6, ScalarUpdate(), config, restore(checkpoint.work),
                     physics=physics2, resume=checkpoint)


def test_threaded_batch_cap_checked_before_any_dispatch():
    ledger = lm.Ledger(cap=3, endpoint_reserve=0, strict_dispatch=True)
    observed = []
    with pytest.raises(lm.TrialSolveCap):
        with ledger.calls(lambda f, items: ordered_calls(f, items, threads=4),
                          lambda x: observed.append(x), range(4), 'solve', 'test') as calls:
            for call in calls:
                call()
    assert not observed and ledger.units == 0


def test_all_threaded_failures_charged_even_after_first_consumer_raises():
    ledger = lm.Ledger(cap=20, endpoint_reserve=0, strict_dispatch=True)
    observed = []
    def fail(x):
        observed.append(x)
        raise ValueError('failed solve')
    with pytest.raises(ValueError, match='failed solve'):
        with ledger.calls(lambda f, items: ordered_calls(f, items, threads=4),
                          fail, range(8), 'solve', 'failed') as calls:
            calls[0]()
    assert ledger.units == len(observed)
    assert sum(ledger.failed.values()) == len(observed)


def test_real_projected_stage_and_policy_resume_match_uninterrupted(tmp_path):
    from bem_inverse import Observation, Problem, Execution
    from bem_inverse.continuation.forward import PointSourceAcquisition
    from bem_inverse.geometry import ProjectedUpdate, resize
    from bem_inverse.physics import NodalKress
    from bem_inverse.policy import CumulativePolicy, Operation
    from bem_inverse.runner import fit, FitResume

    class SmallPhysics(NodalKress):
        def resolution_profile(self, storage):
            return dict(production=64, refined=128)

    class ShortPolicy(CumulativePolicy):
        def operations(self, problem, physics):
            return (Operation('audit', 'initial', '', '', ''),
                    self._fit(problem, physics, 'first', problem.real, 1, 4, 200, iterations=4),
                    self._fit(problem, physics, 'second', problem.real, 1, 4, 200, iterations=2),
                    Operation('audit', 'final', '', '', ''))

    execution = Execution(device='cpu', frequency_threads=1)
    physics = SmallPhysics(execution)
    theta = np.arange(6)*2*np.pi/6
    sources = 5*np.column_stack((np.cos(theta), np.sin(theta)))
    acquisition = PointSourceAcquisition(sources, sources*1.1, 1e-6)
    observation = Observation(.6, acquisition, np.ones(6, complex)*1e-6, .25e9)
    observation = replace(observation, scattered=physics.evaluate(FourierCurve.circle(), observation, .5, 128).prediction)
    problem = Problem(FourierCurve.circle(1.08), (observation,),
                      (replace(observation, wavenumber=.6*(1+.25j)),), .5)
    policy = ShortPolicy(fit_units=500, fit_seconds=60)
    audit_calls = []
    def audit(curve, *args):
        audit_calls.append(curve)
        return dict(passed=True, work=dict(work_units=0), seconds=0)
    full = fit(problem, physics=physics, policy=policy, audit_adapter=audit)
    first, second = policy.operations(problem, physics)[1:3]
    ledger = lm.Ledger(cap=policy.fit_units, seconds=policy.fit_seconds)
    ledger.begin_stage(first.label, first.stage.quota)
    part = lm.fit_stage(resize(problem.initial, 4), first.stage, problem.contrast,
                        ProjectedUpdate(problem.length_unit_m), first.optimizer, ledger,
                        physics=physics, pause_after=1)
    assert part.outcome == 'PAUSED'
    checkpoint = part.checkpoint
    resume = FitResume(checkpoint, (first, second), initial_audit=dict(passed=True))
    audit_calls.clear()
    actual = fit(problem, physics=physics, policy=policy, resume=resume,
                 audit_adapter=audit, output=tmp_path/'resumed')
    assert len(audit_calls) == 1  # only the endpoint audit
    assert actual['outcome'] == full['outcome']
    for component in ('real', 'imag'):
        np.testing.assert_array_equal(actual['final_curve'][component], full['final_curve'][component])
    assert actual['fit_and_localization_units'] == full['fit_and_localization_units']
    assert [s['accepted_steps'] for s in actual['stages']] == [s['accepted_steps'] for s in full['stages']]
    assert actual['historical_seconds'] == checkpoint.work['seconds']
    assert actual['fresh_fit_units'] == actual['fit_and_localization_units']-checkpoint.work['work_units']
