"""Frozen model and damping contracts, with a synthetic residual and zero BIE."""
import copy
import inspect
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top023 import run as r
from experiments.top023 import summarize as report


def test_inputs_strip_development_samples_and_bind_exact_terminal():
    inputs, history = r.terminal_inputs()
    assert inputs['state_sha256'] == 'e2eb3a012a29ff2df07fb6539b33e04c91bff1c627daf3fd697c6f6bac381f61'
    assert not {'truth', 'scene', 'evaluation', 'score'} & inputs.keys()
    assert all(r.qualified.complex_array(v).shape == (24, 4) for v in inputs['base_predictions'].values())
    assert inputs['next_damping'] == r.DAMPINGS[0] and len(history) == 9
    assert set(inspect.signature(r.audit).parameters) == {'inputs', 'ledger', 'output'}


def test_changed_inherited_source_is_not_a_silent_new_intervention(monkeypatch):
    monkeypatch.setattr(r.previous,'source_hashes',lambda:{})
    with pytest.raises(r.m.ImplementationError,match='source changed'):r.terminal_inputs()


@pytest.mark.parametrize('gradient,expected', [([1,3,2],(1,2)), ([1,1,1],(0,2)), ([1,2,4],(2,0))])
def test_direction_selection_uses_training_gradient_only(gradient, expected):
    assert r.selected_rows(gradient) == expected


def test_step_is_existing_damped_model_then_reduced_coordinate_clip():
    matrix = np.diag([2.,3.]); basis = np.eye(2); gradient = np.array([8.,-18.])
    proposal = r.lm_proposal(matrix, gradient, basis, np.array([.3,.4]), .5)
    np.testing.assert_allclose(proposal['raw_reduced_step'], [-8/6,18/13.5])
    np.testing.assert_allclose(proposal['reduced_step'], [-.3,.4])
    assert proposal['active_bounds'].tolist() == [True,True]


@pytest.mark.parametrize('gain,calls,expected', [(2.,8,True),(1.99,8,False),(3.,9,False)])
def test_operational_gain_and_cost_both_bind(gain,calls,expected):
    arms=[dict(label='A',accepted=dict(production_gain=1.),candidate_calls=8),
          dict(label='B',accepted=dict(production_gain=gain),candidate_calls=calls)]
    assert r.operational_gate(arms)['passed'] is expected
    arms[0].pop('accepted')
    assert r.operational_gate(arms)['passed']


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    inputs, _ = r.terminal_inputs(); inputs=copy.deepcopy(inputs)
    state=r.p.driver.deserialize_state(inputs['state']); basis=state.gauge_tangent_basis()
    initial=state.parameter_vector(); q=len(basis)
    rng=np.random.default_rng(23); orthogonal=np.linalg.qr(rng.normal(size=(192,q)))[0]
    matrix=orthogonal*np.linspace(10.,100.,q)
    target=np.linspace(2e-5,6e-5,q); residual=-matrix@target
    observed=np.array(inputs['training']['observed_real'])+1j*np.array(inputs['training']['observed_imag'])
    scale=np.linalg.norm(observed,axis=0)[None,:]*2
    response=lambda v:observed+(v[:96]+1j*v[96:]).reshape(24,4)*scale
    inputs['base_predictions']={str(n):r.previous.follow.complex_record(response(residual)) for n in r.NODES}
    inputs['base_objectives']={str(n):.5*float(residual@residual) for n in r.NODES}
    inputs['saved_gradient']['coefficient_gradient']=(basis.T@(matrix.T@residual)).tolist()
    mode={'name':'linear'};calls=[]
    def prediction(s,frequencies,nodes,solve,ledger,category):
        assert tuple(frequencies)==tuple(r.p.TRAIN)
        calls.append((category,nodes))
        z=basis@(s.parameter_vector()-initial)
        argument=z+4*z**3/1e-8 if mode['name']=='unstable' else z
        value=response(residual+matrix@argument)
        if mode['name']=='bad_candidate' and category.startswith('candidate_') and nodes==512:
            value=value*1.001
        for f in frequencies:
            ledger.reserve(1)
            key=f'None:{category}:{f:.0f}'
            ledger.attempted[category]+=1;ledger.completed[category]+=1
            ledger.frequency_attempted[key]+=1;ledger.frequency_completed[key]+=1
        return value
    monkeypatch.setattr(r.p,'prediction',prediction)
    monkeypatch.setattr(r.p,'feasible',lambda *a:True)
    monkeypatch.setattr(r.m.rt,'run_multiradial_fd_inverse',lambda *a,**k:pytest.fail('diagnostic must not launch inverse'))
    monkeypatch.setattr(r,'terminal_inputs',lambda:(inputs,{}))
    log=tmp_path/'mock-tests.log';log.write_text('mock qualification; no physical solves')
    validation=tmp_path/'validation.json'
    r.write(validation,dict(status='PASS',source_sha256=r.source_hashes(),test_sha256={},log=log.name,log_sha256=r.p.digest(log)))
    return inputs,mode,calls,tmp_path/'run',validation,basis,matrix,residual


def test_full_training_diagnostic_and_independent_replay(synthetic):
    inputs,mode,calls,output,validation,*_=synthetic
    result=r.run(output,validation)
    assert result['status']=='COMPLETED_DIAGNOSTIC',result
    assert not result['inverse_executed'] and not result['full_suite_released'] and not result['operational_improvement']
    assert result['sources_and_inputs_unchanged'] and result['work']['total_attempted']<=580
    assert len([c for c in calls if c[0]=='repeatability'])==1
    verification,arms=report.verify(output)
    assert verification['status']=='PASS' and len(arms)==4 and all(a['accepted'] for a in arms)
    assert r.read(output/'inputs.json')['state']==inputs['state']
    model=r.read(output/'model.json');model['jacobian'][0][0]+=1
    r.write(output/'model.json',model)
    r.write(output/'artifact_manifest.json',{str(p.relative_to(output)):r.p.digest(p)
        for p in output.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
    with pytest.raises(AssertionError):report.verify(output)


def test_complete_jacobian_must_fit_before_any_call(synthetic):
    inputs,_,calls,output,*_=synthetic;output.mkdir()
    with pytest.raises(r.m.TrialSolveCap):r.audit(inputs,r.m.Ledger(cap=271),output)
    assert calls==[] and not r.read(output/'model.json').get('jacobian')


def test_candidate_batch_cannot_start_with_only_seven_calls_left(synthetic):
    inputs,_,calls,output,*_=synthetic;output.mkdir()
    ledger=r.m.Ledger(cap=331)
    with pytest.raises(r.m.TrialSolveCap):r.audit(inputs,ledger,output)
    assert ledger.total==324 and not any(category.startswith('candidate_') for category,_ in calls)


@pytest.mark.parametrize('changed',['frequency','backtracks','damping'])
def test_input_protocol_change_is_rejected_before_prediction(synthetic,changed):
    inputs,_,calls,output,*_=synthetic;output.mkdir()
    if changed=='frequency': inputs['training']['frequencies_hz'][-1]=1.5e9
    elif changed=='backtracks': inputs['optimizer']['max_backtracks']=8
    else: inputs['next_damping']=.001
    with pytest.raises(r.m.ImplementationError):r.audit(inputs,r.m.Ledger(),output)
    assert not calls


def test_unresolved_stencil_stops_without_a_zero_column(synthetic,monkeypatch):
    _,_,calls,output,validation,*_=synthetic
    monkeypatch.setattr(r.p,'feasible',lambda *a:False)
    result=r.run(output,validation)
    assert result['status']=='DIAGNOSTIC_STOP' and result['reason']=='UNRESOLVED_DERIVATIVE'
    assert not calls and not r.read(output/'model.json').get('jacobian')
    assert report.verify(output)[0]['status']=='PASS'


def test_one_sided_stencil_retains_correct_direction(synthetic,monkeypatch):
    inputs,_,_,output,validation,basis,*_=synthetic
    initial=r.p.driver.deserialize_state(inputs['state']).parameter_vector()
    monkeypatch.setattr(r.p,'feasible',lambda s,*a:float(basis[0]@(s.parameter_vector()-initial))>=-2.5e-5)
    result=r.run(output,validation)
    assert result['status']=='COMPLETED_DIAGNOSTIC',result
    model=r.read(output/'model.json')
    assert model['estimates']['0:0.0001:256']['stencil']=='forward'
    assert report.verify(output)[0]['status']=='PASS'


def test_bad_directional_scale_gate_prevents_all_candidates(synthetic):
    inputs,mode,calls,output,validation,basis,matrix,residual=synthetic
    mode['name']='unstable'
    inputs['saved_gradient']['coefficient_gradient']=(basis.T@(5*matrix.T@residual)).tolist()
    result=r.run(output,validation)
    assert result['status']=='SELECTED_DIRECTION_GATE_FAILED',result
    assert not any(category.startswith('candidate_') for category,_ in calls)
    assert all(a['status']=='NOT_STARTED' for a in r.read(output/'arms.json'))
    assert report.verify(output)[0]['status']=='PASS'


def test_candidate_numerical_obstruction_stops_later_arms(synthetic):
    _,mode,calls,output,validation,*_=synthetic;mode['name']='bad_candidate'
    result=r.run(output,validation)
    assert result['status']=='DIAGNOSTIC_STOP' and result['reason']=='NUMERICAL_FAILURE',result
    assert not result['operational_improvement']
    arms=r.read(output/'arms.json')
    assert all(a['status']=='NOT_STARTED' for a in arms[1:])
    assert report.verify(output)[0]['status']=='PASS'


def test_stale_validation_fails_before_output(tmp_path):
    r.write(tmp_path/'validation.json',dict(status='PASS',source_sha256={}))
    with pytest.raises(r.m.ImplementationError):r.prepare(tmp_path/'run',tmp_path/'validation.json')
    assert not (tmp_path/'run').exists()
