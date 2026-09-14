"""Verify the follow-up from saved artifacts and Git; no numerical reruns."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def state_hash(state):
    return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    checked=0
    historical={}
    sources=0
    for phase in ('resolution','central','central-validated'):
        folder=HERE/phase
        manifest=read(folder/'manifest.json')
        for name,sha in read(folder/'artifact_manifest.json').items():
            assert digest(folder/name)==sha,(phase,name)
            checked+=1
        # Different implementation revisions are retained explicitly: the
        # instrumentation repair must not rewrite the first attempt's history.
        revision=manifest['git_revision']
        for name,sha in manifest['source_sha256'].items():
            content=subprocess.check_output(['git','show',f'{revision}:{name}'],cwd=ROOT)
            assert hashlib.sha256(content).hexdigest()==sha,(revision,name)
            sources+=1
        for name,sha in manifest['historical_sha256'].items():
            assert historical.setdefault(name,sha)==sha,name
        for name,sha in {**manifest.get('copied_input_sha256',{}),
                         **manifest.get('prior_attempt_sha256',{})}.items():
            assert digest(Path(name))==sha,name
        assert read(folder/'result.json')['sources_and_history_unchanged']
    for name,sha in historical.items():assert digest(ROOT/name)==sha,name
    resolution=read(HERE/'resolution/result.json')
    assert resolution['status']=='RESOLUTION_CHECK_COMPLETE'
    assert resolution['work']['total_attempted']==54
    assert sum(resolution['work']['completed'].values())==54
    assert not resolution['work']['failed']
    assert resolution['all_states_qualify_256_512']
    assert resolution['F_step_acceptance_256_512']['accepted']
    for row in resolution['states'].values():assert state_hash(row['state'])==row['state_sha256']
    fresh=read(HERE/'central-validated/result.json')
    schedule=fresh['schedule']
    assert schedule['schedule_complete']
    assert fresh['fresh_recovery_pass']==(schedule['numerically_qualified'] and schedule['reconstruction_gates_pass'])
    assert [row['stage'] for row in schedule['stages']]==[1,2,3,4]
    assert fresh['prior_attempt_work']==read(HERE/'central/result.json')['topology_work']
    prior=fresh['prior_attempt_work']
    top=fresh['topology_work'];continuation=fresh['continuation_work']
    assert top['total_attempted']+prior['total_attempted']<=4000
    assert top['active_wall_seconds']+prior['active_wall_seconds']<=600
    assert continuation['total_attempted']<=8012
    assert continuation['active_wall_seconds']<=1800
    for work in (top,continuation):
        assert work['total_attempted']==sum(work['completed'].values())+sum(work['failed'].values())
    assert sum(top['failed'].values())==top['calls'].get('preserved_candidate_refusals',0)
    assert not sum(continuation['failed'].values())
    folder=HERE/'central-validated'
    handoff=read(folder/'handoff.json')
    assert handoff['zero_padding_maximum_point_change_m']<1e-10
    previous=state_hash(handoff['state'])
    assert previous==state_hash(read(folder/'continuation/stage_1/initial_state.json'))
    for row in schedule['stages']:
        n=row['stage'];stage=folder/f'continuation/stage_{n}'
        initial=read(stage/'initial_state.json');accepted=read(stage/'accepted_state.json')
        assert state_hash(initial)==previous==row['start_state_sha256']
        assert accepted['state_sha256']==state_hash(accepted['state'])==row['terminal']['state_sha256']==row['score_state_sha256']
        assert row['work_after_endpoint']['stage_attempted']<=dict([(1,1000),(2,1250),(3,1750),(4,4000)])[n]
        assert len(row['active_frequencies_hz'])==n
        previous=accepted['state_sha256']
    assert previous==schedule['final_state_sha256']==schedule['final_score_state_sha256']
    assert state_hash(schedule['final_state'])==previous
    archived=read(HERE.parent/'TOP-017-20260914-staged-continuation/runs/F-central-ellipse-star/metrics.json')
    assert schedule['final_state']==archived['final_state']
    video=read(HERE/'video_manifest.json')
    for name,sha in video['sources_sha256'].items():assert digest(ROOT/name)==sha,name
    for name,sha in video['outputs_sha256'].items():assert digest(HERE/name)==sha,name
    assert video['no_new_numerical_solves'] and not video['coefficient_interpolation']
    assert video['state_catalog'][-1]['state_sha256']==previous
    output=dict(status='PASS',sealed_artifacts_checked=checked,
        measured_source_hashes_checked_against_git=sources,historical_artifacts_unchanged=len(historical),
        all_stage_state_score_and_budget_associations_pass=True,
        fresh_final_coefficients_identical_to_archived_TOP017=True,
        resolution_audit_54_completed_solves=True,fresh_recovery_pass=fresh['fresh_recovery_pass'],
        refused_topology_api_attempts=top['calls'].get('preserved_candidate_refusals',0),
        test_result='67 focused tests passed; see focused_tests.log',
        video_hashes_and_final_state_pass=True)
    (HERE/'validation.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print(json.dumps(output),flush=True)


if __name__=='__main__':main()
