"""Current-code all-scene contracts, with no physical BIE solves."""
import copy
from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.top025 import run as r
from experiments.top025 import summarize as report
from experiments.top025 import render


def test_campaign_is_single_candidate_and_bounded_for_every_scene():
    assert r.TOTAL_CAP==72+12*(4000+8012)
    assert sum(q for _,q in r.STAGE_PLAN)+12==8012
    assert r.WORKERS==4 and r.SCENE_TIMEOUT==7900
    assert r.WALL_SECONDS>=3*(r.SCENE_TIMEOUT+10)+300


@pytest.fixture
def prepared(tmp_path,monkeypatch,request):
    log=tmp_path/'tests.log';log.write_text('mocked preparation tests; zero BIE')
    validation=tmp_path/'validation.json'
    r.write(validation,dict(status='PASS',source_sha256=r.source_hashes(),test_sha256={},log=log.name,log_sha256=r.p.digest(log)))
    calls=[]
    def oracle(scene,frequencies,nodes,solve,ledger):
        calls.append((scene['id'],tuple(frequencies),nodes));ledger.reserve(len(frequencies))
        for f in frequencies:
            ledger.attempted['mock']+=1;ledger.completed['mock']+=1
            ledger.frequency_attempted[str(f)]+=1;ledger.frequency_completed[str(f)]+=1
        factor=1.01 if getattr(request,'param',None)=='bad' and nodes==512 else 1.
        return np.full((24,3),(1+.1j)*factor)
    monkeypatch.setattr(r.suite.screen,'oracle',oracle)
    monkeypatch.setattr(r.suite,'release_gate',lambda *a:pytest.fail('TOP-021 success gate must not be claimed or altered'))
    output=tmp_path/'suite';audit=r.prepare(output,validation)
    return output,audit,calls


def test_all_twelve_fresh_inputs_and_only_missing_added_data(prepared):
    output,audit,calls=prepared
    assert audit['status']=='PASS' and audit['work']['total_attempted']==54 and len(calls)==18
    assert {name for name,_,_ in calls}.isdisjoint(r.suite.REUSED)
    contract=r.read(output/'contract.json')
    assert contract['arms']==['F'] and contract['evaluation_only'] and not contract['top021_release_claim']
    assert not contract['damping_reset'] and not contract['supplied_target_count']
    screen_cap=8 if contract['inverse_runtime']['continuation_readiness'] else 0
    assert contract['continuation_solve_cap']==8012+screen_cap
    assert contract['campaign_solve_cap']==r.TOTAL_CAP+12*screen_cap
    for scene in r.read(output/'scene_spec.json')['scenes']:
        name=scene['id'];initial,observed,evaluation,_,_=r.suite.load_scene(output,name)
        assert r.m.state_hash(initial)==r.m.state_hash(r.p.benchmark.initial_state(scene))
        assert r.p.digest(output/'inputs'/name/'observations.json')==r.p.digest(r.p.DATA/'scenes'/name/'observations.json')
        assert observed.shape==(24,4) and evaluation.shape==(24,2)
    r.verify(output)
    contract['continuation_solve_cap']+=1;r.write(output/'contract.json',contract)
    with pytest.raises(r.m.ImplementationError):r.verify(output)


@pytest.mark.parametrize('prepared',['bad'],indirect=True)
def test_oracle_failure_stops_preparation_before_inversion(prepared):
    output,audit,calls=prepared
    assert audit['status']=='HARD_STOP' and len(calls)==2 and audit['work']['total_attempted']==6
    assert not (output/'runs').exists()


def test_stale_source_validation_stops_before_output(tmp_path):
    r.write(tmp_path/'validation.json',dict(status='PASS',source_sha256={}))
    with pytest.raises(r.m.ImplementationError):r.prepare(tmp_path/'out',tmp_path/'validation.json')
    assert not (tmp_path/'out').exists()


def test_fresh_scene_calls_topology_before_single_continuation(prepared,monkeypatch):
    output,_,_=prepared;name='central-ellipse-star';initial,*_=r.suite.load_scene(output,name);order=[]
    def prefix(state,data,control,solve,ledger,folder):
        order.append('topology');assert r.m.state_hash(state)==r.m.state_hash(initial)
        assert data.observed_scattered_response.shape==(24,1)
        folder.mkdir(parents=True)
        r.write(folder/'terminal.json',dict(final_state=r.p.driver.serialize_state(state),controller_work=dict(totals=dict(bie_frequency_solve_count=0))))
        return state
    def continuation(folder,state,optimizer,observed,evaluation,scene,spec,control,solve):
        order.append('F');folder.mkdir(parents=True)
        assert all(c.maximum_mode==17 for c in state.components)
        assert optimizer.initial_damping==r.p._optimizer_config(state,control).initial_damping
        return dict(status='COMPLETED_SCHEDULE',fresh_recovery_pass=False,work=r.m.Ledger(cap=8012,seconds=7200).snapshot())
    monkeypatch.setattr(r.follow,'topology_prefix',prefix)
    monkeypatch.setattr(r.base,'topology_checks',lambda *args:dict(monotone=True,event_margins=True))
    monkeypatch.setattr(r,'run_continuation',continuation)
    result=r.run_scene(output,name)
    assert order==['topology','F'] and result['sources_and_inputs_unchanged']
    assert not result['fresh_recovery_pass'] and result['actual_attempted_calls']==0


def test_prefix_failure_preserves_scene_and_does_not_start_refinement(prepared,monkeypatch):
    output,_,_=prepared
    def fail(*args):raise r.m.TrialWallLimit('synthetic topology wall stop')
    monkeypatch.setattr(r.follow,'topology_prefix',fail)
    monkeypatch.setattr(r,'run_continuation',lambda *args:pytest.fail('failed prefix must not release continuation'))
    result=r.run_scene(output,'far-two-stars')
    assert result['status']=='HARD_STOP' and result['reason']=='TRIAL_WALL_LIMIT'
    assert result['sources_and_inputs_unchanged'] and result['actual_attempted_calls']==0
    assert r.read(output/'runs/far-two-stars/result.json')==result


def test_schedule_receives_training_only_and_preserves_failure(tmp_path,monkeypatch):
    spec=r.read(r.p.DATA/'scene_spec.json');scene=spec['scenes'][1]
    state=r.p.benchmark.initial_state(scene);control=r.p.benchmark.controller_config(spec,'H')
    monkeypatch.setattr(r.base,'score_endpoint',lambda *a:dict(numerically_qualified=True,training_errors=[.1]*4,geometry='evaluation only'))
    def schedule(state,arm,observed,nodes,solve,optimizer,floor,ledger,folder,initial_score,scorer,stage_plan):
        assert observed.shape==(24,4) and arm=='F' and nodes==(256,512)
        assert set(initial_score)=={'numerically_qualified','training_errors'}
        assert stage_plan==r.STAGE_PLAN and ledger.cap==8012 and ledger.seconds==7200
        raise r.m.NumericalFailure('synthetic candidate obstruction')
    monkeypatch.setattr(r.m,'run_schedule',schedule)
    result=r.run_scheduled_continuation(tmp_path/'F',state,None,np.ones((24,4)),np.ones((24,2)),scene,spec,control,None)
    assert result['status']=='HARD_STOP' and result['reason']=='NUMERICAL_FAILURE'
    assert result['work']['total_attempted']==0 and not result['fresh_recovery_pass']


def test_missing_predictions_are_never_reported_as_recovery():
    row=dict(count=2,truth_count=2,boundary_mm=.1,iou=.99,prediction_errors=None,
        numerically_qualified=False,topology_pass=True,schedule_complete=False,reason='TRIAL_WALL_LIMIT')
    labels=report.failure_labels(row)
    assert 'final prediction score unavailable' in labels and 'TRIAL_WALL_LIMIT' in labels
    assert 'continuation incomplete' in labels


def test_video_contains_every_saved_record_and_exact_final_state(tmp_path):
    import json
    name='example';inputs=tmp_path/'inputs'/name;inputs.mkdir(parents=True)
    r.write(inputs/'initial_state.json',None)
    spec=r.read(r.p.DATA/'scene_spec.json');state=r.p.driver.serialize_state(r.p.benchmark.initial_state(spec['scenes'][1]))
    state=json.loads(json.dumps(state,default=lambda value:value.tolist()))
    later=copy.deepcopy(state);later[0]['parameters'][0]+=1e-4
    topology=tmp_path/'runs'/name/'topology';topology.mkdir(parents=True)
    (topology/'trajectory.jsonl').write_text(json.dumps(dict(state=state,cycle=0,label='birth'))+'\n')
    r.write(topology/'terminal.json',dict(final_state=state))
    stage=tmp_path/'runs'/name/'F/stage_1';stage.mkdir(parents=True)
    (stage/'trajectory.jsonl').write_text(json.dumps(dict(state=state,iteration=0))+'\n')
    r.write(stage/'accepted_state.json',dict(state=later,iteration=1))
    data=render.collect(tmp_path,name)
    assert data['catalog'][0]['state'] is None and data['catalog'][-1]['state']==later
    assert set(range(len(data['catalog']))).issubset({i for i,_ in data['timeline']})
    for record in data['catalog']:
        assert record['state_sha256']==r.m.state_hash(record['state'])
        assert record['state'] in (None,state,later)
    assert data['timeline'][-1][1]=='Final retained state'


def test_video_encoder_roundtrip_counts_every_frame(tmp_path):
    fig,axis=render.plt.subplots(figsize=(3.2,2.4),dpi=50)
    line,=axis.plot([0,1],[0,0]);axis.set_ylim(0,1)
    result=render.encode(fig,tmp_path/'smoke.mp4',[0,0,1],lambda value:line.set_ydata([value,value]))
    render.plt.close(fig)
    assert result['frames']==3 and int(result['probe']['nb_frames'])==3
    assert result['probe']['width']==160 and result['probe']['height']==120
