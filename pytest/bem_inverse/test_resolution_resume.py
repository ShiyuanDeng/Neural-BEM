"""Exact accepted-state resume and threaded reservations."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from bem_inverse.errors import TrialSolveCap
from bem_inverse.fit_stage import fit_stage
from bem_inverse.stage_types import BackendConfig, FitStage
from bem_inverse.work import Ledger
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.physics import Prediction


class ScalarUpdate:
    length_unit_m = 1.

    def settings(self):
        return dict(name='scalar_radius', length_unit_m=1.)

    def prepare(self, curve, *_):
        return SimpleNamespace(curve=curve, orders=np.array([0]))


def scalar_trial(normal_update, *, prepared):
    """The geometry update of ``ScalarUpdate``: change the circle's radius."""
    return FourierCurve.circle(prepared.curve.coefficients[-1].real+normal_update[0]), {}


class ScalarPhysics:
    """Prediction = radius, so the fit moves a circle of radius 2 towards the data 0.1."""
    execution = SimpleNamespace(frequency_threads=4)

    def __init__(self):
        self.calls, self.derivatives = [], []

    def forward_solve(self, curve, obs, contrast, nodes):
        radius = curve.coefficients[-1].real
        self.calls.append((nodes, radius))
        return Prediction(np.array([radius], complex), dict(resolution=nodes), nodes)

    def derivative(self, evaluation, update, space):
        self.derivatives.append(evaluation._handle)
        return np.ones((1, 1), complex)


def scalar_stage(iterations=2, nodes=8):
    physics = ScalarPhysics()
    observation = SimpleNamespace(scattered=np.array([.1], complex), wavenumber=1.)
    stage = FitStage('scalar', (observation,), (1.,), 0, 1, nodes, iterations)
    config = BackendConfig(step_bounds_m=(.8, .8, .8), max_damping_trials=1)
    ledger = Ledger(cap=500, endpoint_reserve=0)
    ledger.begin_stage(stage.label, None)
    return physics, stage, config, ledger


def restore(work):
    return Ledger.restore(work, seconds=7200., endpoint_reserve=0)


def test_pause_resume_preserves_damping_trajectory_and_counters():
    physics, stage, config, ledger = scalar_stage(iterations=4, nodes=16)
    full = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, ledger,
                     physics=physics, forward_solve=physics.forward_solve, geometry_update=scalar_trial)
    physics2, _, _, split_ledger = scalar_stage(iterations=4, nodes=16)
    part = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, split_ledger,
                        physics=physics2, forward_solve=physics2.forward_solve, geometry_update=scalar_trial, pause_after=2)
    assert part.outcome == 'PAUSED'
    checkpoint = part.checkpoint
    resumed = fit_stage(part.curve, stage, .5, ScalarUpdate(), config, restore(checkpoint.work),
                           physics=physics2, forward_solve=physics2.forward_solve, geometry_update=scalar_trial, resume=checkpoint)
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
        fit_stage(part.curve, stage, .5, ScalarUpdate(), config, bad, physics=physics2, forward_solve=physics2.forward_solve, geometry_update=scalar_trial, resume=checkpoint)
    with pytest.raises(ValueError, match='does not match'):
        fit_stage(part.curve, stage, .6, ScalarUpdate(), config, restore(checkpoint.work),
                     physics=physics2, forward_solve=physics2.forward_solve, geometry_update=scalar_trial, resume=checkpoint)


def test_threaded_batch_cap_checked_before_any_dispatch():
    ledger = Ledger(cap=3, endpoint_reserve=0, strict_dispatch=True)
    observed = []
    with pytest.raises(TrialSolveCap):
        with ledger.calls(lambda x: observed.append(x), range(4), 'solve', 'test', threads=4) as calls:
            for call in calls:
                call()
    assert not observed and ledger.units == 0


def test_all_threaded_failures_charged_even_after_first_consumer_raises():
    ledger = Ledger(cap=20, endpoint_reserve=0, strict_dispatch=True)
    observed = []
    def fail(x):
        observed.append(x)
        raise ValueError('failed solve')
    with pytest.raises(ValueError, match='failed solve'):
        with ledger.calls(fail, range(8), 'solve', 'failed', threads=4) as calls:
            calls[0]()
    assert ledger.units == len(observed)
    assert sum(ledger.failed.values()) == len(observed)


def test_real_projected_stage_and_policy_resume_match_uninterrupted(tmp_path):
    from bem_inverse import Observation, Problem, Execution
    from bem_inverse.continuation.forward import PointSourceAcquisition
    from functools import partial
    from bem_inverse.continuation.geometry import resize
    from bem_inverse.forward_solvers.nodal_kress import NodalKress, forward_solve
    from bem_inverse.geometry_selection import make_update
    from bem_inverse.policy import CumulativePolicy
    from bem_inverse.runner import fit, FitResume

    class SmallPhysics(NodalKress):
        def resolution_profile(self, storage):
            return dict(production=64, refined=128)

    class ShortPolicy(CumulativePolicy):
        def operations(self, problem, physics):
            return (self._fit(problem, physics, 'first', problem.real, 1, 4, 200, iterations=4),
                    self._fit(problem, physics, 'second', problem.real, 1, 4, 200, iterations=2))

    execution = Execution(device='cpu', frequency_threads=1)
    physics = SmallPhysics(execution)
    solve = partial(forward_solve, context=physics)
    theta = np.arange(6)*2*np.pi/6
    sources = 5*np.column_stack((np.cos(theta), np.sin(theta)))
    acquisition = PointSourceAcquisition(sources, sources*1.1, 1e-6)
    observation = Observation(.6, acquisition, np.ones(6, complex)*1e-6, .25e9)
    observation = replace(observation, scattered=solve(FourierCurve.circle(), observation, .5, 128).prediction)
    problem = Problem(FourierCurve.circle(1.08), (observation,),
                      (replace(observation, wavenumber=.6*(1+.25j)),), .5)
    policy = ShortPolicy(fit_units=500, fit_seconds=60)
    full = fit(problem, physics=physics, forward_solve=solve, policy=policy)
    first, second = policy.operations(problem, physics)
    ledger = Ledger(cap=policy.fit_units, seconds=policy.fit_seconds)
    ledger.begin_stage(first.label, first.stage.quota)
    update, trial = make_update('spline', problem.length_unit_m, execution)
    part = fit_stage(resize(problem.initial, 4), first.stage, problem.contrast, update, first.optimizer, ledger,
                     physics=physics, forward_solve=solve, geometry_update=trial, pause_after=1)
    assert part.outcome == 'PAUSED'
    checkpoint = part.checkpoint
    resume = FitResume(checkpoint, (first, second))
    actual = fit(problem, physics=physics, forward_solve=solve, policy=policy, resume=resume,
                 output=tmp_path/'resumed')
    assert actual['outcome'] == full['outcome']
    for component in ('real', 'imag'):
        np.testing.assert_array_equal(actual['final_curve'][component], full['final_curve'][component])
    assert actual['fit_and_localization_units'] == full['fit_and_localization_units']
    assert [s['accepted_steps'] for s in actual['stages']] == [s['accepted_steps'] for s in full['stages']]
    assert actual['historical_seconds'] == checkpoint.work['seconds']
    assert actual['fresh_fit_units'] == actual['fit_and_localization_units']-checkpoint.work['work_units']
