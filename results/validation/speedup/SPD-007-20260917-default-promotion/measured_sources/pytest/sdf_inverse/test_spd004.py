"""A task-level stop must use all training data and retain independent checks."""
import inspect
from types import SimpleNamespace
import numpy as np
import pytest
from sdf_inverse.readiness import training_readiness
from experiments.top025 import readiness as r


def test_readiness_is_per_frequency_and_at_both_resolutions():
    observed=np.ones((24,4),complex)
    assert training_readiness(observed,observed,observed)['ready']
    wrong=observed.copy();wrong[:,-1]*=1.00002
    assert not training_readiness(observed,wrong,wrong)['ready']
    # Both fits are good, but numerical disagreement exceeds the last-frequency gate.
    wrong=observed.copy();wrong[:,-1]*=1.000001
    decision=training_readiness(observed,wrong,observed)
    assert decision['training_fit_pass'] and not decision['numerical_pass']
    assert not decision['ready']


@pytest.mark.parametrize('kind',['nan','infinity','zero','missing_frequency','mismatch'])
def test_invalid_inputs_never_release_continuation(kind):
    observed=np.ones((24,4),complex);low=observed.copy();high=observed.copy()
    if kind=='nan':low[0,0]=np.nan
    if kind=='infinity':high[0,0]=np.inf
    if kind=='zero':observed[:,0]=0
    if kind=='missing_frequency':observed=low=high=observed[:,:3]
    if kind=='mismatch':high=high[:12]
    with pytest.raises(ValueError):training_readiness(observed,low,high)


def test_gate_has_no_scene_or_independent_evaluation_input():
    assert list(inspect.signature(training_readiness).parameters)==['observed','production','refined']
    assert list(inspect.signature(r.screen_training).parameters)==['state','observed','solve','floor','ledger']


@pytest.fixture
def stubbed(monkeypatch):
    calls=[]
    monkeypatch.setattr(r,'asdict',lambda config:{})
    monkeypatch.setattr(r.p,'training_data',lambda fs,y: calls.append(('training_only',tuple(fs))))
    monkeypatch.setattr(r.p,'feasible',lambda *a:True)
    monkeypatch.setattr(r.m,'state_hash',lambda s:'frozen-state')
    monkeypatch.setattr(r.p.driver,'serialize_state',lambda s:[])
    def prediction(state,frequencies,nodes,solve,ledger,category):
        calls.append((category,tuple(frequencies),nodes))
        ledger.reserve(len(frequencies))
        ledger.attempted[category]+=len(frequencies)
        ledger.completed[category]+=len(frequencies)
        return np.ones((24,len(frequencies)),complex)
    monkeypatch.setattr(r.p,'prediction',prediction)
    return calls


@pytest.mark.parametrize('independent_pass',[True,False])
def test_ready_route_still_checks_independent_quality(tmp_path,monkeypatch,stubbed,independent_pass):
    monkeypatch.setattr(r.pipeline,'run_scheduled_continuation',lambda *a:pytest.fail('ready state must skip fitting'))
    def score(*a):
        assert len([x for x in stubbed if x[0]=='readiness'])==2
        assert len([x for x in stubbed if x[0]=='endpoint'])==2
        return dict(original_gates_pass=independent_pass,numerically_qualified=True)
    monkeypatch.setattr(r.pipeline.base,'score_predictions',score)
    result=r.readiness_continuation(tmp_path/'F',object(),None,np.ones((24,4)),
        object(),object(),object(),SimpleNamespace(minimum_component_radius_m=.008),None)
    assert result['status']=='READY_WITHOUT_CONTINUATION'
    assert result['skipped_continuation']
    assert result['fresh_recovery_pass']==independent_pass
    assert result['work']['total_attempted']==12
    assert result['work']['budget_work_units']==12
    assert result['schedule']['stages']==[] and not result['schedule']['complete_effective_exposure']
    assert result['schedule']['convergence']=='STATIONARITY_NOT_MEASURED'


def test_unready_route_preserves_original_fallback_and_charges_screen(tmp_path,monkeypatch,stubbed):
    sentinel=object();seen=[]
    def original(folder,state,optimizer,observed,evaluation,scene,spec,control,solve):
        assert optimizer is sentinel
        seen.append(state)
        work=r.m.Ledger(cap=8012,seconds=7200)
        work.attempted['derivative']=1;work.completed['derivative']=1
        work.derivative_attempted['derivative']=34;work.derivative_completed['derivative']=34
        return dict(status='COMPLETED_SCHEDULE',fresh_recovery_pass=True,work=work.snapshot())
    monkeypatch.setattr(r.pipeline,'run_scheduled_continuation',original)
    monkeypatch.setattr(r.pipeline.base,'score_predictions',lambda *a:pytest.fail('fallback owns scoring'))
    state=object()
    result=r.readiness_continuation(tmp_path/'F',state,sentinel,np.full((24,4),2),
        None,None,None,SimpleNamespace(minimum_component_radius_m=.008),None)
    assert seen==[state] and not result['skipped_continuation']
    assert result['work']['total_attempted']==9 and result['work']['budget_work_units']==43
    assert result['work']['solve_cap']==8020 and result['work']['within_solve_cap']


def test_failure_in_final_evaluation_retains_attempts(tmp_path,monkeypatch,stubbed):
    original=r.p.prediction
    def fail(state,frequencies,nodes,solve,ledger,category):
        if category=='endpoint':
            ledger.attempted[category]+=1;ledger.failed[category]+=1
            raise RuntimeError('injected independent solve failure')
        return original(state,frequencies,nodes,solve,ledger,category)
    monkeypatch.setattr(r.p,'prediction',fail)
    result=r.readiness_continuation(tmp_path/'F',object(),None,np.ones((24,4)),
        None,None,None,SimpleNamespace(minimum_component_radius_m=.008),None)
    assert result['status']=='HARD_STOP' and not result['fresh_recovery_pass']
    assert result['work']['total_attempted']==9 and sum(result['work']['failed'].values())==1
