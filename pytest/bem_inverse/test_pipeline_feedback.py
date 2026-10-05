"""Behavioral regressions for the CI-SPD controller and repeated-work repairs."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest

from bem_inverse.continuation import lm_backend as lm
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.continuation.globalization import damping_floor
from bem_inverse.modal_geometry import WaveArrays
from bem_inverse.physics import Execution
from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
from bem_inverse.geometry import ProjectedUpdate
from bem_inverse import runner
from experiments.cleaned_interface.test_audit_streaming import fixture, reference_dense_audit
from test_resolution_resume import setup, ScalarUpdate


def run_scalar(config, *, update=None, iterations=1, ledger=None, pause_after=None):
    physics, stage, _, original = setup(mode='exact', iterations=iterations)
    result = lm.fit_stage(FourierCurve.circle(2), stage, .5, update or ScalarUpdate(),
        config, ledger or original, physics=physics, pause_after=pause_after)
    return result, physics


def test_shortened_accepted_step_increases_damping_and_keeps_line_search():
    class ShortMove(ScalarUpdate):
        def trial(self, space, step):
            if abs(step[0]) > .01:
                raise UpdateRefused('self_intersection', 'fixture rejects large moves')
            return super().trial(space, step)
    config = lm.BackendConfig(damping_rule='agreement', step_bounds_m=(.8,)*3, max_damping_trials=1)
    result, _ = run_scalar(config, update=ShortMove())
    accepted = next(t for t in result.trials if t['status']=='accepted')
    assert accepted['backtrack'] > 0 and accepted['accepted_fraction'] < .25
    assert accepted['gain_ratio'] == pytest.approx(1., rel=1e-11)
    assert result.history[-1]['next_damping'] >= 10*accepted['damping']
    assert accepted['damping_feedback'] == 'severely_shortened'


def test_floor_tracks_scaled_curvature_and_cannot_underflow():
    metric = np.diag([4.,9.])
    a = np.array([[8.,2.],[2.,18.]])
    floor = damping_floor(a,metric,1e-6)
    assert damping_floor(100*a,metric,1e-6) == pytest.approx(100*floor)
    assert floor > 1e-6


class Refuses(ScalarUpdate):
    def __init__(self, clock=None):
        self.calls=0; self.clock=clock
    def trial(self, space, step):
        self.calls+=1
        if self.clock is not None:
            self.clock[0]+=1.
        raise UpdateRefused('self_intersection','fixture refusal')


def test_deadline_is_checked_between_geometry_only_refusals():
    clock=[0.]
    ledger=lm.Ledger(cap=500,seconds=.5,clock=lambda:clock[0],endpoint_reserve=0)
    ledger.begin_stage('scalar',None)
    update=Refuses(clock)
    result,_=run_scalar(lm.BackendConfig(damping_rule='agreement'),update=update,ledger=ledger)
    assert result.outcome=='TRIAL_WALL_LIMIT'
    assert update.calls==result.geometry_proposals==1


def test_geometry_cap_does_not_require_dispatching_more_physics():
    update=Refuses()
    result,physics=run_scalar(lm.BackendConfig(damping_rule='agreement',geometry_proposal_cap=2),update=update)
    assert result.outcome=='GEOMETRY_PROPOSAL_CAP'
    assert update.calls==2
    assert len(physics.calls)==1


def test_failed_candidate_retains_exception_and_exact_identity():
    physics,stage,config,ledger=setup(mode='exact',iterations=1)
    original=physics.evaluate
    def fail(curve,obs,contrast,nodes):
        if curve.coefficients[-1].real < 2:
            raise ValueError('fixture numerical refusal')
        return original(curve,obs,contrast,nodes)
    physics.evaluate=fail
    result=lm.fit_stage(FourierCurve.circle(2),stage,.5,ScalarUpdate(),config,ledger,physics=physics)
    assert result.outcome=='NUMERICAL_FAILURE'
    failure=result.physics_failures[0]
    assert failure['exception_type']=='ValueError'
    assert failure['message']=='fixture numerical refusal'
    assert len(failure['candidate_sha256'])==64
    assert failure['candidate_coefficients']['real'][-1] < 2
    assert result.trials[-1]['status']=='physics_failed'


def test_terminal_tangent_is_skipped_but_pause_retains_resume_state():
    config=lm.BackendConfig(step_bounds_m=(.4,)*3,avoid_terminal_linearization=True)
    result,physics=run_scalar(config)
    assert result.accepted_steps==1 and len(physics.derivatives)==1
    assert result.history[-1]['gradient_inf'] is None
    paused,physics=run_scalar(config,iterations=2,pause_after=1)
    assert paused.checkpoint is not None and len(physics.derivatives)==2


def test_incremental_wave_extension_preserves_cells_and_matches_fresh_build():
    coefficients=np.array([.015+.01j,.2+.1j,.7+.05j],complex)
    waves=WaveArrays(coefficients,12)
    first=waves.ensure(3,4).copy()
    waves.ensure(6,4)
    np.testing.assert_array_equal(waves.arrays[:4,:4],first)
    waves.ensure(6,8)
    np.testing.assert_array_equal(waves.arrays[:4,:4],first)
    reference=WaveArrays(coefficients,12).ensure(6,8)
    np.testing.assert_array_equal(waves.arrays,reference)


def test_parallel_audit_matches_dense_reference_with_same_work():
    p=fixture()
    settings=ModalSettings(trace_minimum=16,trace_step=8,window_margin=16)
    serial=ModalMuller(Execution(device='cpu',frequency_threads=1),settings)
    parallel=ModalMuller(Execution(device='cpu',frequency_threads=2,audit_frequency_batch=2),settings)
    stage=lm.FitStage('audit',p.real,(.2,)*5,(1e-5,)*3+(1e-7,)*2,3,8,token(16),token(24),1)
    args=(p.initial,stage,lm.BackendConfig(),p)
    expected=reference_dense_audit(*args,serial,ProjectedUpdate(.05),300.)
    actual=runner.audit(*args,parallel,ProjectedUpdate(.05),300.)
    for key in expected.keys()-{'work'}:
        np.testing.assert_array_equal(actual[key],expected[key],err_msg=key)
    assert actual['frequency_batch']==2
    for key in ('work_units','solves','reciprocal_batches','failed'):
        assert actual['work'][key]==expected['work'][key]


def test_failed_modal_phase_keeps_elapsed_receipt():
    physics=ModalMuller(Execution(device='cpu'))
    with pytest.raises(ValueError):
        with physics._stage('assembly'):
            raise ValueError('fixture phase failure')
    receipt=physics.receipt()
    assert receipt['counts']['assembly']==1 and receipt['seconds']['assembly'] > 0
