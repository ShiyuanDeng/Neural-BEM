"""Suite release, capacity, all-row reporting and budget boundaries; mocked BIE."""
import copy
from dataclasses import replace
import inspect
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.top021 import run as r
from experiments.top021 import summarize as report


def manifest(folder):
    r.write(folder/'artifact_manifest.json',{str(x.relative_to(folder)):r.p.digest(x)
        for x in folder.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'})


@pytest.mark.parametrize('pass_result,pass_verification',[(False,True),(True,False),(True,True)])
def test_fresh_integration_release_is_binding(tmp_path,pass_result,pass_verification):
    r.write(tmp_path/'contract.json',dict(experiment='TOP-020',scene='far-two-stars',stage_plan=r.STAGE_PLAN))
    r.write(tmp_path/'result.json',dict(fresh_recovery_pass=pass_result))
    r.write(tmp_path/'verification.json',dict(status='PASS',fresh_recovery_pass=pass_verification))
    manifest(tmp_path)
    if pass_result and pass_verification:
        assert r.release_gate(tmp_path)['fresh_recovery_pass']
        r.write(tmp_path/'result.json',dict(fresh_recovery_pass=False))
        with pytest.raises(r.m.ImplementationError):r.release_gate(tmp_path)
    else:
        with pytest.raises(r.m.ImplementationError):r.release_gate(tmp_path)


def test_a_different_successful_protocol_does_not_release_staged_suite(tmp_path):
    r.write(tmp_path/'contract.json',dict(experiment='TOP-022',scene='far-two-stars',stage_plan=[[4,8000]]))
    r.write(tmp_path/'result.json',dict(fresh_recovery_pass=True))
    r.write(tmp_path/'verification.json',dict(status='PASS',fresh_recovery_pass=True));manifest(tmp_path)
    with pytest.raises(r.m.ImplementationError,match='staged protocol'):r.release_gate(tmp_path)


@pytest.mark.parametrize('scene_id,mode,count',[('merge',9,2),('central-ellipse-star',17,1),('death',9,3)])
def test_capacity_policy_uses_returned_count_not_truth(scene_id,mode,count,monkeypatch):
    spec=r.read(r.p.DATA/'scene_spec.json');scene=next(x for x in spec['scenes'] if x['id']==scene_id)
    state=r.p.benchmark.initial_state(scene)
    monkeypatch.setattr(r.p,'feasible',lambda *args:True)
    padded,opt,capacity=r.capacity_start(state,r.p.benchmark.controller_config(spec,'H'),None)
    assert len(padded.components)==count and all(c.maximum_mode==mode for c in padded.components)
    assert padded.component_ids==state.component_ids and capacity['maximum_point_change_m']<=1e-10
    assert opt.max_parameters>=padded.parameter_count and len(opt.max_steps)==padded.parameter_count
    assert not {'scene','truth','target_count','evaluation'} & set(inspect.signature(r.capacity_start).parameters)


def test_capacity_refuses_infeasible_or_empty_endpoint(monkeypatch):
    with pytest.raises(r.m.NumericalFailure):r.capacity_start(None,None,None)
    spec=r.read(r.p.DATA/'scene_spec.json');scene=next(s for s in spec['scenes'] if s['id']=='merge')
    monkeypatch.setattr(r.p,'feasible',lambda *args:False)
    with pytest.raises(r.m.NumericalFailure):
        r.capacity_start(r.p.benchmark.initial_state(scene),r.p.benchmark.controller_config(spec,'H'),None)


def test_stage_one_release_requires_qualified_record():
    assert r.shared_stage_one({}) is None
    assert r.shared_stage_one(dict(schedule=dict(stages=[dict(stage_complete=False)]))) is None
    assert r.shared_stage_one(dict(schedule=dict(stages=[dict(stage_complete=True,score_state_sha256='same')])))=='same'


def test_exact_campaign_cap_is_sum_of_declared_maxima():
    assert r.TOTAL_CAP==72+12*(4000+2*8012)
    assert sum(q for _,q in r.STAGE_PLAN)+12==8012


@pytest.fixture
def prepared(tmp_path,monkeypatch,request):
    plan=tmp_path/'plan.md';plan.write_text('mock approved contract')
    monkeypatch.setattr(r,'PLAN',plan)
    monkeypatch.setattr(r,'release_gate',lambda _:dict(path='mock',result_sha256='mock',verification_sha256='mock',fresh_recovery_pass=True))
    log=tmp_path/'tests.log';log.write_text('mocked qualification')
    validation=tmp_path/'validation.json'
    r.write(validation,dict(status='PASS',source_sha256=r.source_hashes(),test_sha256={},log=log.name,log_sha256=r.p.digest(log)))
    calls=[]
    def oracle(scene,frequencies,nodes,solve,ledger):
        calls.append((scene['id'],tuple(frequencies),nodes))
        ledger.reserve(len(frequencies))
        for f in frequencies:
            ledger.attempted['mock_oracle']+=1;ledger.completed['mock_oracle']+=1
            ledger.frequency_attempted[str(f)]+=1;ledger.frequency_completed[str(f)]+=1
        factor=1.001 if getattr(request,'param',None)=='bad_oracle' and nodes==512 else 1.
        return np.full((24,3),(1.+.1j)*factor)
    monkeypatch.setattr(r.screen,'oracle',oracle)
    output=tmp_path/'suite'
    audit=r.prepare(output,validation,tmp_path/'unused_top020')
    return output,audit,calls


def test_full_matrix_reuses_original_data_and_only_nine_added_oracles(prepared):
    output,audit,calls=prepared
    assert audit['status']=='PASS' and len(audit['scenes'])==12
    assert audit['work']['total_attempted']==54 and len(calls)==18
    assert {name for name,_,_ in calls}.isdisjoint(r.REUSED)
    spec=r.read(output/'scene_spec.json')
    for scene in spec['scenes']:
        name=scene['id'];initial,observed,evaluation,_,_=r.load_scene(output,name)
        assert r.p.digest(output/'inputs'/name/'initial_state.json')==r.p.digest(r.p.DATA/'scenes'/name/'initial_state.json')
        assert r.p.digest(output/'inputs'/name/'observations.json')==r.p.digest(r.p.DATA/'scenes'/name/'observations.json')
        assert observed.shape==(24,4) and evaluation.shape==(24,2)


@pytest.mark.parametrize('prepared',['bad_oracle'],indirect=True)
def test_failed_oracle_stops_before_later_oracles_or_inversion(prepared):
    output,audit,calls=prepared
    assert audit['status']=='HARD_STOP' and audit['reason']=='NUMERICAL_FAILURE'
    assert len(calls)==2 and audit['work']['total_attempted']==6
    assert not (output/'runs').exists()


@pytest.mark.parametrize('matching',[False,True])
def test_f_stage_one_identity_gates_later_frequencies(tmp_path,monkeypatch,matching):
    spec=r.read(r.p.DATA/'scene_spec.json');scene=next(s for s in spec['scenes'] if s['id']=='central-ellipse-star')
    state=r.p.benchmark.initial_state(scene);control=r.p.benchmark.controller_config(spec,'H')
    seen=[]
    def fit(initial,data,nodes,solve,opt,floor,ledger,output):
        seen.append(len(data.frequency_weights));output.mkdir(parents=True)
        return initial,dict(stage_outcome='NORMAL_OPTIMIZER_RETURN',effective_training_exposure=True,
            convergence='UNCONFIRMED')
    monkeypatch.setattr(r.m,'fit_stage',fit)
    monkeypatch.setattr(r,'verify',lambda bundle:None)
    monkeypatch.setattr(r.p,'feasible',lambda *args:True)
    monkeypatch.setattr(r.base,'score_endpoint',lambda *args:dict(training_errors=[.1]*4,
        numerically_qualified=True,original_gates_pass=False))
    result=r.run_arm(tmp_path,'central-ellipse-star','F',state,None,np.ones((24,4)),
        np.ones((24,2)),scene,spec,control,None,r.m.state_hash(state) if matching else 'wrong')
    assert seen==([1,2,3,4] if matching else [1])
    assert result['status']==('COMPLETED_SCHEDULE' if matching else 'HARD_STOP')
    assert result['work']['total_attempted']==0


def test_all_twenty_four_rows_survive_when_nothing_is_dispatched(prepared):
    output,audit,calls=prepared
    r.write(output/'campaign.json',dict(status='ORACLE_GATE_STOP',workers=[],elapsed_wall_seconds=0))
    # Real geometry-only reporting runs with a zero-call physical ledger.
    r.saved_geometry(output)
    manifest(output)
    summary=report.summarize(output,render=False)
    assert len(summary['rows'])==24 and summary['recovery_counts']==dict(S=0,F=0)
    assert not summary['complete_matrix_measured'] and not summary['full_candidate_recovery']
    assert summary['work']['actual_attempted_calls']==54


def test_zero_remaining_campaign_time_never_spawns_worker(tmp_path,monkeypatch):
    monkeypatch.setattr(r.subprocess,'Popen',lambda *args,**kwargs:pytest.fail('late worker started'))
    result=r.run_job(tmp_path,'merge',r.time.monotonic()-1)
    assert result['status']=='NOT_DISPATCHED_CAMPAIGN_WALL_LIMIT'


def test_worker_launch_failure_is_a_saved_outcome(tmp_path,monkeypatch):
    def refuse(*args,**kwargs):raise OSError('mock process resource limit')
    monkeypatch.setattr(r.subprocess,'Popen',refuse)
    result=r.run_job(tmp_path,'merge',r.time.monotonic()+100)
    assert result['status']=='WORKER_LAUNCH_FAILED' and result['scene']=='merge'


def test_failed_oracle_never_constructs_inversion_worker_pool(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'prepare',lambda *args:dict(status='HARD_STOP'))
    monkeypatch.setattr(r,'verify',lambda *args:None)
    monkeypatch.setattr(r,'ThreadPoolExecutor',lambda *args,**kwargs:pytest.fail('oracle failure dispatched workers'))
    result=r.campaign(tmp_path,None,None)
    assert result['status']=='ORACLE_GATE_STOP' and result['workers']==[]


def test_geometry_reporting_selects_latest_retained_state_not_best_score(tmp_path):
    folder=tmp_path/'runs/merge/F';folder.mkdir(parents=True)
    r.write(folder/'result.json',dict(schedule=dict(final_state=['terminal'],initial_state=['initial'],
        final={'score':'bad'},stages=[dict(score={'score':'better'},terminal=dict(final_state=['earlier']))])))
    assert r.retained_state(tmp_path,'merge','F')[0]==['terminal']
    assert report.retained_state(tmp_path,'merge','F')==['terminal']
