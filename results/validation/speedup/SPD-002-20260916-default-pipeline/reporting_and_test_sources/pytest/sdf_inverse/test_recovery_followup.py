"""Focused follow-up checks. No physical solves are performed by these tests."""
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import run_topology_recovery_followup as f

m,p = f.m,f.p


def test_rejected_candidate_replays_exact_archived_hash():
    states = f.archived_states()
    acceptance = m.read(f.HISTORY/'runs/F-far-two-stars/stage_2/acceptance.json')[-1]
    assert m.state_hash(states['F_rejected']) == acceptance['candidate_state_sha256']
    assert m.state_hash(states['F_retained']) == acceptance['base_state_sha256']
    assert m.state_hash(states['F_rejected']) != m.state_hash(states['F_retained'])


def test_numerical_failure_saves_exact_predictions_without_accepting_candidate(tmp_path,monkeypatch):
    states = f.archived_states()
    base,candidate = states['F_retained'],states['F_rejected']
    values = {m.state_hash(base):np.full((24,2),1.1+0.3j),
              m.state_hash(candidate):np.full((24,2),1.05+0.2j)}
    def objective(state,*a,**k):
        return SimpleNamespace(state=state,loss=.02 if state is base else .01,
                               prediction=values[m.state_hash(state)]*(1+2e-6))
    def inverse(initial,data,geometry,**kwargs):
        eb = SimpleNamespace(state=base,loss=.02,prediction=values[m.state_hash(base)])
        ec = SimpleNamespace(state=candidate,loss=.01,prediction=values[m.state_hash(candidate)])
        kwargs['accepted_state_callback'](0,eb)
        kwargs['candidate_acceptance_callback'](eb,ec)
        pytest.fail('numerically invalid candidate escaped the hard stop')
    monkeypatch.setattr(m.rt,'evaluate_multiradial_objective',objective)
    monkeypatch.setattr(m.rt,'run_multiradial_fd_inverse',inverse)
    ledger=m.Ledger();ledger.begin_stage(2,1250)
    opt=m.rt.ParameterFDConfig(**m.read(f.HISTORY/'inputs/far-two-stars/optimizer.json')['config'])
    final,terminal=m.fit_stage(base,p.training_data(p.TRAIN[:2],np.ones((24,2))),m.NODES,
        p.driver.baseline.iteration01_solve_config(),opt,.008,ledger,tmp_path/'stage')
    failure=m.read(tmp_path/'stage/numerical_failure.json')
    assert terminal['stage_outcome']=='NUMERICAL_FAILURE'
    assert m.state_hash(final)==m.state_hash(base)==failure['accepted_state_sha256']
    for prefix,state in [('base',base),('candidate',candidate)]:
        for resolution,factor in [('production',1),('refined',1+2e-6)]:
            snapshot=failure[f'{resolution}_{prefix}']
            assert m.state_hash(snapshot['state'])==m.state_hash(state)==snapshot['state_sha256']
            np.testing.assert_array_equal(np.array(snapshot['prediction_real'])+
                1j*np.array(snapshot['prediction_imag']),values[m.state_hash(state)]*factor)
    assert ledger.total==0 and failure['accepted'] is False


def test_all_four_stages_use_declared_frequencies_and_retained_handoff(tmp_path):
    state=f.archived_states()['F_retained'];seen=[]
    score=dict(training_errors=[.1]*4,numerically_qualified=True,original_gates_pass=False)
    def fit(initial,data,nodes,solve,optimizer,floor,ledger,output):
        seen.append((ledger.stage,len(data.frequency_weights),m.state_hash(initial)))
        return initial,dict(stage_outcome='STAGE_QUOTA_REACHED',effective_training_exposure=True,
                            convergence='UNCONFIRMED')
    result=m.run_schedule(state,'F',np.ones((24,4)),m.NODES,None,None,.008,
        m.Ledger(cap=8012),tmp_path,score,lambda s:score,fit=fit,
        feasibility=lambda *a:True,stage_plan=f.FULL_PLAN)
    assert result['schedule_complete'] and result['complete_effective_exposure']
    assert [(n,freq) for n,freq,_ in seen]==[(1,1),(2,2),(3,3),(4,4)]
    assert all(h==m.state_hash(state) for _,_,h in seen)


@pytest.mark.parametrize('stop',['topology_stationary','recovered'])
def test_autonomous_handoff_does_not_require_two_components(tmp_path,stop):
    spec=m.read(p.DATA/'scene_spec.json')
    scene=next(s for s in spec['scenes'] if s['id']==f.CENTRAL)
    initial=p.benchmark.initial_state(scene)
    control=p.benchmark.controller_config(spec,'H')
    def controller(start,data,production,refined,**kwargs):
        assert start is initial and 'truth' not in kwargs and 'target_count' not in kwargs
        assert len(data.frequency_weights)==1
        return SimpleNamespace(final_state=initial,stop_reason=stop,events=[],passes=[],work={})
    state=f.topology_prefix(initial,p.training_data(p.TRAIN[:1],np.ones((24,1))),
        control,p.driver.baseline.iteration01_solve_config(),f.TopologyLedger(),
        tmp_path/'topology',controller=controller)
    padded,opt,delta=f.continuation_start(state,control,p.driver.baseline.iteration01_solve_config())
    assert len(padded.components)==1 and padded.components[0].maximum_mode==9
    assert delta<1e-10 and opt.loss_tolerance==1e-14
    assert not ({'scene','truth','target_count','evaluation'} & set(inspect.signature(f.topology_prefix).parameters))


def test_topology_resource_stop_does_not_release_continuation(tmp_path):
    initial=f.archived_states()['F_retained']
    def controller(*a,**k):
        return SimpleNamespace(final_state=initial,stop_reason='maximum_events',events=[],passes=[],work={})
    with pytest.raises(m.NumericalFailure,match='handoff'):
        f.topology_prefix(initial,p.training_data(p.TRAIN[:1],np.ones((24,1))),None,None,
                          f.TopologyLedger(),tmp_path/'topology',controller=controller)


@pytest.mark.parametrize('failure',[False,True])
def test_td_attempt_completion_failure_cap_and_restoration(monkeypatch,failure):
    build=lambda *a,**k:object()
    monkeypatch.setattr(m.rt,'build_multicomponent_kress_tmz_frequency_system',build)
    record=f.work_accounting.record_work
    ledger=f.TopologyLedger(cap=1)
    with ledger.instrument():
        m.rt.build_multicomponent_kress_tmz_frequency_system(None,2*np.pi*.5e9)
        if not failure:
            f.work_accounting.record_work(td_frequency_solve_count=1)
        with pytest.raises(m.TrialSolveCap):
            m.rt.build_multicomponent_kress_tmz_frequency_system(None,2*np.pi*.5e9)
    assert ledger.total==1
    assert sum(ledger.completed.values())==int(not failure)
    assert sum(ledger.failed.values())==int(failure)
    assert m.rt.build_multicomponent_kress_tmz_frequency_system is build
    assert f.work_accounting.record_work is record


def test_topology_preserves_expected_candidate_geometry_refusal(monkeypatch):
    from gpr_bem_kress.multicomponent import MultiComponentTopologyError
    error=MultiComponentTopologyError('candidate components too close')
    def forward(*a,**k):raise error
    monkeypatch.setattr(p.physical,'solve_multicomponent_kress_tmz_total_field_batch',forward)
    ledger=f.TopologyLedger()
    with ledger.instrument(),pytest.raises(MultiComponentTopologyError) as caught:
        p.physical.solve_multicomponent_kress_tmz_total_field_batch(None,None,None,2*np.pi*.5e9)
    assert caught.value is error and ledger.total==1
    assert ledger.calls['preserved_candidate_refusals']==1
    assert ledger.failed['unclassified']==1  # refused physical API attempt, not a completed BIE solve


def test_integrity_check_refuses_changed_copied_input(tmp_path,monkeypatch):
    source=tmp_path/'input.json';source.write_text('{}')
    manifest=dict(source_sha256={},historical_sha256={},copied_input_sha256={str(source):p.digest(source)})
    monkeypatch.setattr(m,'verify_sources',lambda expected:None)
    f.verify(manifest)
    source.write_text('{"changed":true}')
    with pytest.raises(m.ImplementationError,match='copied input'):
        f.verify(manifest)


def test_existing_output_is_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        f.freeze(tmp_path,'resolution')
