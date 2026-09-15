"""TOP-018 dispatch/provenance checks; mocked forwards and geometry only."""
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top018 import run as n

m, p = n.m, n.p


def mock_score():
    return dict(training_errors=[.1,.2,.3,.4],numerically_qualified=True,
                original_gates_pass=False,production_nodes=256,refined_nodes=512)


@pytest.fixture
def inputs():
    return n.validated_inputs()


def test_saved_inputs_reuse_and_exact_candidate(inputs):
    states, observed, evaluation, optimizer, provenance = inputs
    assert set(states) == {'COMMON', 'F_RETAINED', 'F_REJECTED', 'S_ENDPOINT'}
    assert observed.shape == (24, 4) and evaluation.shape == (24, 2)
    assert optimizer.finite_difference_steps == 1e-4
    assert provenance['historical_prediction_solves'] == 54
    assert m.state_hash(states['COMMON']) == n.COMMON_HASH
    assert m.state_hash(states['F_REJECTED']) != m.state_hash(states['F_RETAINED'])


def test_release_gate_including_optional_rejected_candidate():
    rows = {name:dict(feasible={'256':True,'512':True}, qualified_256_512=True)
            for name in ('COMMON','F_RETAINED','S_ENDPOINT','F_REJECTED')}
    audit = dict(states=rows, derivative={'passed':True}, inputs_verified=True,
                 tests_verified=True, source_integrity=True)
    assert n.release_gate(audit)['passed']
    rows['F_REJECTED']['qualified_256_512'] = False
    assert not n.release_gate(audit)['passed']
    rows['F_REJECTED'] = {'status':'NOT_RECOVERABLE'}
    assert n.release_gate(audit)['passed']
    audit['derivative']['passed'] = False
    assert not n.release_gate(audit)['passed']


@pytest.mark.parametrize('passed', [False, True])
def test_gate_dispatches_only_approved_arms(passed):
    assert n.released_arms({'status':'PHASE_A_PASS' if passed else 'PHASE_A_FAIL',
                            'gate':{'passed':passed}}) == (('S','F') if passed else ())
    assert n.released_arms({'status':'PHASE_A_FAIL','gate':{'passed':True}}) == ()


def test_discrepancy_denominator_and_zero_guard():
    high = np.array([[2+1j,3j],[1,4]])
    low = high + .001
    np.testing.assert_array_equal(n.discrepancy(low,high),p.relative(low,high))
    with pytest.raises(m.NumericalFailure): n.discrepancy(low,np.zeros_like(high))


def test_feasible_side_stencils_and_refusal():
    base=np.array([1.,2.]); direction=np.array([3.,4.]); h=1e-4
    for sides,kind in [({-1:base-h*direction,1:base+h*direction},'central'),
                       ({1:base+h*direction},'forward'),
                       ({-1:base-h*direction},'backward')]:
        value,stencil=n.quotient(base,sides,h)
        np.testing.assert_allclose(value,direction,rtol=1e-11)
        assert stencil==kind
    with pytest.raises(m.UnresolvedDerivative):n.quotient(base,{},h)


def test_two_scale_and_floor_guards():
    d=np.array([1.,2.])
    assert n.derivative_qualified(d,d,1e-4,1e-12)['passed']
    assert not n.derivative_qualified(d,2*d,1e-4,1e-12)['passed']
    assert not n.derivative_qualified(d,d,1e-4,1.)['passed']
    assert not n.derivative_qualified(d,np.zeros(2),1e-4,1e-12)['passed']


@pytest.mark.parametrize('arm',['S','F'])
def test_matching_start_resolution_frequencies_and_quota_transitions(tmp_path,inputs,arm):
    states,obs,_,optimizer,_=inputs
    state=states['COMMON']; seen=[]
    initial=mock_score()
    def fit(start,data,nodes,solve,opt,floor,ledger,output):
        seen.append((ledger.stage,m.state_hash(start),nodes,len(data.frequency_weights)))
        q=len(start.gauge_tangent_basis());active=len(data.frequency_weights)
        ledger.reserve(active+2*q*active+3*active)
        ledger.attempted['mock']=active+2*q*active+3*active
        return start,dict(stage_outcome='STAGE_QUOTA_REACHED',effective_training_exposure=True,
                          convergence='UNCONFIRMED',gradient=None,final_state=p.driver.serialize_state(start))
    ledger=m.Ledger(seconds=7200)
    result=n.schedule(state,arm,obs,optimizer,.008,ledger,tmp_path,initial,
                      lambda s:mock_score(),fit=fit,feasibility=lambda *a:True)
    assert result['schedule_complete']
    assert [(i,h,nodes) for i,h,nodes,_ in seen]==[(i,n.COMMON_HASH,n.NODES) for i in (2,3,4)]
    assert [x[-1] for x in seen]==([1,1,1] if arm=='S' else [2,3,4])
    assert result['initial']['production_nodes']==256


@pytest.mark.parametrize('code,report', [('NUMERICAL_FAILURE',True),
    ('UNRESOLVED_DERIVATIVE',False),('TRIAL_WALL_LIMIT',False),
    ('TRIAL_SOLVE_CAP',False),('PHYSICAL_SOLVE_FAILED',False),('IMPLEMENTATION_ERROR',False)])
def test_hard_stop_does_not_advance_and_reporting_cannot_release(tmp_path,inputs,code,report):
    states,obs,_,opt,_=inputs;calls=[]
    def fit(state,*args):
        calls.append('fit')
        return state,dict(stage_outcome=code,effective_training_exposure=False,
                          convergence='UNCONFIRMED',gradient=None,final_state=p.driver.serialize_state(state))
    def scorer(state):calls.append('score');return mock_score()
    ledger=m.Ledger(seconds=7200)
    result=n.schedule(states['COMMON'],'F',obs,opt,.008,ledger,tmp_path,mock_score(),scorer,
                      fit=fit,feasibility=lambda *a:True)
    assert calls==(['fit','score'] if report else ['fit'])
    assert not result['schedule_complete'] and result['reason']==code
    assert not result['numerically_qualified']
    assert ('reporting_score' in result)==report


def test_real_fit_has_new_resolution_cache_and_state_associations(tmp_path,monkeypatch,inputs):
    states,obs,_,opt,_=inputs;state=states['COMMON'];seen=[]
    center=state.components[0].center[0]
    def objective(candidate,data,geometry,**kwargs):
        seen.append(geometry.num_nodes)
        prediction=data.observed_scattered_response*(1+candidate.components[0].center[0]-center+.001)
        residual,_=p.normalized_complex_residual(prediction,data.observed_scattered_response,data.frequency_weights)
        return m.rt.MultiRadialObjectiveEvaluation(candidate,.5*float(residual@residual),
            float(np.linalg.norm(residual)),residual,prediction,0.,0.)
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',objective)
    ledger=m.Ledger(seconds=7200);ledger.begin_stage(2,1250)
    data=p.training_data(p.TRAIN[:2],obs[:,:2])
    final,t=m.fit_stage(state,data,n.NODES,n.solve_config(),replace(opt,max_iterations=1),.008,ledger,tmp_path/'stage')
    assert set(seen)=={256,512} and ledger.total==0
    assert t['production_nodes']==256 and t['refined_nodes']==512
    assert t['gradient']['state_sha256']==m.state_hash(final)
    assert t['gradient']['active_frequencies_hz']==list(p.TRAIN[:2])


def test_reservation_counts_complete_batch_and_endpoint_before_dispatch():
    ledger=m.Ledger(cap=7000,seconds=7200);ledger.begin_stage(2,1250)
    ledger.attempted['prior']=1100
    with pytest.raises(m.StageQuota):ledger.reserve(2*34*2+3*2)
    assert ledger.total==1100
    with ledger.endpoint_scope():ledger.reserve(12)
    assert m.NODES==(128,256) and m.QUOTAS==(1250,1750,4000)


def test_existing_bundle_refused_and_expired_worker_not_dispatched(tmp_path):
    with pytest.raises(FileExistsError):n.prepare(tmp_path,tmp_path/'validation.json')
    def forbidden(*a,**k):pytest.fail('expired worker dispatched')
    result=n.run_worker(tmp_path,'S',10.,clock=lambda:11.,popen=forbidden)
    assert result['status']=='NOT_DISPATCHED'


def test_objective_identity_includes_data_resolution_and_state(inputs):
    states,observed,*_=inputs
    a=n.objective_identity(states['COMMON'],p.TRAIN[:2],observed[:,:2])
    b=n.objective_identity(states['COMMON'],p.TRAIN[:1],observed[:,:1])
    assert a['objective_sha256']!=b['objective_sha256']
    assert a['state_sha256']==n.COMMON_HASH
    assert a['production_nodes']==256 and a['refined_nodes']==512


def test_rejected_fine_candidate_snapshot_preserves_checkpoint(tmp_path,monkeypatch,inputs):
    states,obs,_,opt,_=inputs
    base,candidate=states['F_RETAINED'],states['F_REJECTED']
    def evaluation(state,factor):
        return SimpleNamespace(state=state,loss=.02 if state is base else .01,
                               prediction=obs[:,:2]*factor)
    def objective(state,data,geometry,**kw):
        assert geometry.num_nodes==512
        return evaluation(state,1+2e-6)
    def inverse(initial,data,geometry,**kw):
        assert geometry.num_nodes==256
        kw['accepted_state_callback'](0,evaluation(base,1.))
        kw['candidate_acceptance_callback'](evaluation(base,1.),evaluation(candidate,1.))
        pytest.fail('rejected candidate returned')
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',objective)
    monkeypatch.setattr(m.rt,'run_multiradial_fd_inverse',inverse)
    ledger=m.Ledger(seconds=7200);ledger.begin_stage(2,1250)
    final,t=m.fit_stage(base,p.training_data(p.TRAIN[:2],obs[:,:2]),n.NODES,n.solve_config(),opt,.008,
                        ledger,tmp_path/'stage')
    failure=m.read(tmp_path/'stage/numerical_failure.json')
    assert t['stage_outcome']=='NUMERICAL_FAILURE'
    assert failure['accepted_state_sha256']==m.state_hash(final)==m.state_hash(base)
    assert failure['production_candidate']['state_sha256']==m.state_hash(candidate)
    assert failure['refined_candidate']['state_sha256']==m.state_hash(candidate)
    assert failure['production_nodes']==256 and failure['refined_nodes']==512
    assert ledger.total==0
