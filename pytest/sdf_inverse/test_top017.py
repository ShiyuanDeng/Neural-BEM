"""Safety/identifiability checks, with zero physical solves."""
from dataclasses import replace
import inspect
import json
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import time
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import run_top017 as m
from sdf_inverse.runtime import inverse_runtime


@pytest.fixture(autouse=True)
def historical_fd_profile():
    # These controls prescribe FD probes and mocked residuals. Fast defaults
    # have separate real-operator integration coverage in test_spd002.py.
    with inverse_runtime('reference'):
        yield


@pytest.fixture
def state():
    return m.p.driver.deserialize_state(m.read(m.SOURCE/'runs/S-far-two-stars/metrics.json')['final_state'])


def dummy_score():
    return dict(training_errors=[.1,.2,.3,.4],numerically_qualified=True,original_gates_pass=False)


@pytest.mark.parametrize('arm',['S','F'])
def test_valid_quotas_reach_all_stages_without_prefix_replay(tmp_path,state,arm):
    ledger=m.Ledger()
    seen=[]
    def fit(initial,data,nodes,solve,optimizer,floor,ledger,output):
        freqs=(data.forward_problem.angular_frequencies/(2*np.pi)).tolist()
        seen.append((ledger.stage,freqs,m.state_hash(initial)))
        active=len(freqs);q=len(initial.gauge_tangent_basis())
        ledger.reserve(active+2*q*active+3*active)
        ledger.attempted['initial_objective']+=active
        ledger.attempted['derivative']+=2*q*active
        ledger.attempted['candidate']+=3*active
        # Leave less than one next complete batch, preserving unused quota.
        remaining=12+2*q*active+3*active-1
        ledger.attempted['mock_remaining_work']+=ledger.stage_quota-(ledger.total-ledger.stage_start)-remaining
        with pytest.raises(m.StageQuota):ledger.reserve(2*q*active+3*active)
        return initial,dict(stage_outcome='STAGE_QUOTA_REACHED',effective_training_exposure=True,
            convergence='UNCONFIRMED',work=ledger.snapshot())
    def score(s):
        with ledger.endpoint_scope():
            ledger.reserve(12);ledger.attempted['endpoint']+=12
        return dummy_score()
    r=m.run_schedule(state,arm,np.ones((24,4),complex),m.NODES,None,None,.008,ledger,tmp_path,
        dummy_score(),score,fit=fit,feasibility=lambda *a:True)
    assert r['status']=='COMPLETED_SCHEDULE'
    assert [s[0] for s in seen]==[2,3,4]
    assert all(s[2]==m.state_hash(state) for s in seen)
    assert [len(s[1]) for s in seen]==([1,1,1] if arm=='S' else [2,3,4])
    assert ledger.total<7000
    assert r['convergence']=='UNCONFIRMED'


@pytest.mark.parametrize('code',['TRIAL_SOLVE_CAP','TRIAL_WALL_LIMIT','UNRESOLVED_DERIVATIVE',
    'PHYSICAL_SOLVE_FAILED','NUMERICAL_FAILURE','IMPLEMENTATION_ERROR'])
def test_hard_stop_never_advances_or_scores(tmp_path,state,code):
    calls=[]
    def fit(initial,*args):
        calls.append('fit')
        return initial,dict(stage_outcome=code,effective_training_exposure=False,convergence='UNCONFIRMED')
    def score(s):raise AssertionError('hard stop must not score')
    r=m.run_schedule(state,'F',np.ones((24,4),complex),m.NODES,None,None,.008,m.Ledger(),tmp_path,
                     dummy_score(),score,fit=fit)
    assert r['status']=='HARD_STOP' and r['reason']==code and calls==['fit']
    assert 'final' not in r


def test_budget_boundaries_no_partial_batch_or_endpoint_consumption():
    ledger=m.Ledger(cap=7000,seconds=1800);ledger.begin_stage(2,1250)
    ledger.attempted['initial']=1100
    before=ledger.total
    with pytest.raises(m.StageQuota):ledger.reserve(136+6)
    assert ledger.total==before
    with ledger.endpoint_scope():ledger.reserve(12)
    ledger.attempted['endpoint']=12
    ledger.begin_stage(3,1750)
    assert ledger.stage_start==1112
    ledger.attempted['other']=5880
    with pytest.raises(m.TrialSolveCap):ledger.reserve(1)


def test_clock_not_reset_between_stages():
    now=[0.];ledger=m.Ledger(clock=lambda:now[0]);ledger.begin_stage(2,1250)
    now[0]=1801.
    with pytest.raises(m.TrialWallLimit):ledger.begin_stage(3,1750)


@pytest.mark.parametrize('failure',[ValueError('physical failure'),m.rt.OrderedSDFGeometryError('geometry in physical solve')])
def test_failed_physical_calls_are_counted_and_not_geometry_refusals(monkeypatch,failure):
    def physical(*args,**kwargs):raise failure
    monkeypatch.setattr(m.p.physical,'solve_multicomponent_kress_tmz_total_field_batch',physical)
    ledger=m.Ledger()
    with ledger.instrument(),pytest.raises(m.PhysicalFailure):
        m.p.physical.solve_multicomponent_kress_tmz_total_field_batch(None,None,None,2*np.pi*.5e9)
    assert ledger.total==1 and sum(ledger.failed.values())==1 and sum(ledger.completed.values())==0


def test_actual_wall_signal_interrupts_batch_and_counts_attempt(monkeypatch):
    def physical(*args,**kwargs):time.sleep(.2)
    monkeypatch.setattr(m.p.physical,'solve_multicomponent_kress_tmz_total_field_batch',physical)
    ledger=m.Ledger(seconds=.02)
    with pytest.raises(m.TrialWallLimit),ledger.instrument():
        m.p.physical.solve_multicomponent_kress_tmz_total_field_batch(None,None,None,2*np.pi*.5e9)
    assert ledger.total==1 and sum(ledger.failed.values())==1


def fake_objective(initial):
    center=initial.components[0].center[0]
    def objective(candidate,data,geometry,*,solve_config=None):
        value=candidate.components[0].center[0]-(center-.001)
        prediction=np.ones_like(data.observed_scattered_response)+value
        residual,_=m.p.normalized_complex_residual(prediction,data.observed_scattered_response,data.frequency_weights)
        return m.rt.MultiRadialObjectiveEvaluation(candidate,.5*float(residual@residual),float(np.linalg.norm(residual)),residual,prediction,0.,0.)
    return objective


def optimizer(state):
    return m.rt.ParameterFDConfig(**m.read(m.SOURCE/'runs/S-far-two-stars/stage_1/optimizer.json')['config'])


def test_real_optimizer_mock_forward_binds_exposure_gradient_and_rejections(tmp_path,monkeypatch,state):
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',fake_objective(state))
    ledger=m.Ledger();ledger.begin_stage(2,1250)
    data=m.p.training_data(m.p.TRAIN[:2],np.ones((24,2),complex))
    final,t=m.fit_stage(state,data,m.NODES,m.p.driver.baseline.iteration01_solve_config(),
        replace(optimizer(state),max_iterations=1),.008,ledger,tmp_path/'stage')
    assert t['stage_outcome']=='NORMAL_OPTIMIZER_RETURN'
    assert t['exposure']['jacobian_batches_completed']==2 and t['accepted_steps']==1
    assert t['exposure']['candidate_attempts']>=1
    assert t['gradient']['state_sha256']==m.state_hash(final)
    assert t['gradient']['active_frequencies_hz']==[.5e9,.75e9]
    assert t['gradient']['normalization']==m.NORMALIZATION
    assert t['gradient']['production_nodes']==128
    assert ledger.total==0


def test_latest_accepted_checkpoint_survives_refused_next_jacobian(tmp_path,monkeypatch,state):
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',fake_objective(state))
    class RefuseSecond(m.Ledger):
        batches=0
        def reserve(self,n):
            if n==71:
                self.batches+=1
                if self.batches==2:raise m.StageQuota('mock next batch')
            super().reserve(n)
    ledger=RefuseSecond();ledger.begin_stage(2,1250)
    data=m.p.training_data((.5e9,),np.ones((24,1),complex))
    final,t=m.fit_stage(state,data,m.NODES,m.p.driver.baseline.iteration01_solve_config(),
        optimizer(state),.008,ledger,tmp_path/'stage')
    assert t['stage_outcome']=='STAGE_QUOTA_REACHED' and t['accepted_steps']==1
    assert t['gradient'] is None
    assert t['last_measured_gradient']['state_sha256']==m.state_hash(state)
    assert m.read(tmp_path/'stage/accepted_state.json')['state_sha256']==m.state_hash(final)
    assert m.state_hash(final)!=m.state_hash(state)


def test_unresolved_jacobian_stops_before_candidate(tmp_path,monkeypatch,state):
    def objective(candidate,data,geometry,*,solve_config=None):
        if m.state_hash(candidate)!=m.state_hash(state):raise m.rt.OrderedSDFGeometryError('mock both sides refused')
        return fake_objective(state)(candidate,data,geometry,solve_config=solve_config)
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',objective)
    ledger=m.Ledger();ledger.begin_stage(2,1250)
    data=m.p.training_data((.5e9,),np.ones((24,1),complex))
    final,t=m.fit_stage(state,data,m.NODES,m.p.driver.baseline.iteration01_solve_config(),optimizer(state),.008,ledger,tmp_path/'stage')
    assert t['stage_outcome']=='UNRESOLVED_DERIVATIVE'
    assert t['unresolved_columns']==34
    assert t['exposure'].get('candidate_attempts',0)==0
    assert t['gradient'] is None and m.state_hash(final)==m.state_hash(state)


def test_insufficient_initial_quota_exposes_no_model(tmp_path,state):
    ledger=m.Ledger();ledger.begin_stage(2,20)
    data=m.p.training_data((.5e9,),np.ones((24,1),complex))
    _,t=m.fit_stage(state,data,m.NODES,m.p.driver.baseline.iteration01_solve_config(),optimizer(state),.008,ledger,tmp_path/'stage')
    assert t['stage_outcome']=='EXPOSURE_OBSTRUCTION' and ledger.total==0


def test_training_only_interface_and_equal_frequency_objective():
    # SC-034 adds one optimizer control, not data: an opt-in step-safeguard
    # config whose default (None) leaves the historical call unchanged.
    parameters=inspect.signature(m.fit_stage).parameters
    assert set(parameters)=={'initial','data','nodes','solve','optimizer','floor','ledger','output','step_safeguards'}
    assert parameters['step_safeguards'].default is None
    observed=np.arange(1,49).reshape(24,2).astype(complex)*(1+1j)
    predicted=observed+np.array([.1+.3j,.5+.8j])
    data=m.p.training_data(m.p.TRAIN[:2],observed)
    residual,_=m.p.normalized_complex_residual(predicted,observed,data.frequency_weights)
    expected=.5*np.mean(np.sum(abs(predicted-observed)**2,axis=0)/np.sum(abs(observed)**2,axis=0))
    assert .5*(residual@residual)==pytest.approx(expected,rel=1e-14)
    with pytest.raises(ValueError):m.p.training_data((1.5e9,),observed[:,:1])


def test_final_planned_quota_can_complete_at_global_boundary():
    ledger=m.Ledger();ledger.attempted['prior_stages']=3000;ledger.begin_stage(4,4000)
    ledger.attempted['stage4']=3988
    with pytest.raises(m.StageQuota):ledger.reserve(272)
    with ledger.endpoint_scope():
        ledger.reserve(12);ledger.attempted['endpoint']=12
    assert ledger.total==7000
    with pytest.raises(m.TrialSolveCap):ledger.begin_stage(5,1000)


def test_global_smaller_than_stage_is_hard_stop():
    ledger=m.Ledger(cap=100);ledger.begin_stage(2,1250)
    with pytest.raises(m.TrialSolveCap):ledger.reserve(136)
    assert ledger.total==0


def test_state_hash_matches_serialized_archive(state):
    serialized=m.read(m.SOURCE/'runs/S-far-two-stars/metrics.json')['final_state']
    assert m.state_hash(state)==m.state_hash(serialized)=='8fa832c90e40dd36ee4912ec924788d98ddff3390e28c57eef4d21b2a3101559'


def test_reuse_manifest_and_resolved_inputs_without_physics(tmp_path,state):
    # The old contract rejects the later, explicitly authorized SPD kernel
    # changes. Preserve that guard instead of rewriting its frozen baseline.
    import hashlib, subprocess
    name='solvers/gpr_bem_kress/_kernels.py'
    original=subprocess.check_output(['git','show',f'{m.BASE}:{name}'],cwd=m.ROOT)
    if hashlib.sha256(original).hexdigest()!=m.p.digest(m.ROOT/name):
        with pytest.raises(m.ImplementationError,match='unplanned inherited source change'):
            m.freeze_inputs(tmp_path)
        return
    spec,states,opts=m.freeze_inputs(tmp_path)
    assert m.state_hash(states['far-two-stars'])==m.state_hash(state)
    assert opts['far-two-stars']==m.read(m.SOURCE/'runs/S-far-two-stars/stage_1/optimizer.json')
    for scene in m.SCENES:
        assert m.p.digest(tmp_path/'inputs'/scene/'observations.json')==m.p.digest(m.SOURCE/'phase0/inputs'/scene/'observations.json')
        assert m.read(tmp_path/'reuse.json')[scene]['source'].endswith('metrics.json::final_state')


def test_clock_before_stage_has_unconfirmed_convergence(tmp_path,state):
    now=[0.];ledger=m.Ledger(clock=lambda:now[0]);now[0]=1801.
    r=m.run_schedule(state,'F',np.ones((24,4),complex),m.NODES,None,None,.008,ledger,tmp_path,
                     dummy_score(),lambda s:None)
    assert r['status']=='HARD_STOP' and r['stages']==[] and r['convergence']=='UNCONFIRMED'


def test_global_tighter_than_stage_even_when_batch_exceeds_both():
    ledger=m.Ledger(cap=100);ledger.begin_stage(2,200)
    with pytest.raises(m.TrialSolveCap):ledger.reserve(250)


def test_watchdog_does_not_dispatch_after_deadline(tmp_path):
    import run_top017_campaign as c
    def forbidden(*a,**k):raise AssertionError('expired campaign must not dispatch')
    row=c.run_worker(tmp_path,'late',['--phase','trial'],deadline=100.,clock=lambda:101.,popen=forbidden)
    assert row['status']=='NOT_DISPATCHED' and row['exit_code'] is None and row['campaign_timeout']
