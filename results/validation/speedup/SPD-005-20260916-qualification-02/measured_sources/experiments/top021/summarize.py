"""Replay TOP-021 saved predictions and report all twelve matched scene rows."""
from collections import Counter
import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top019 import summarize as saved

read, write, digest, state_hash = saved.read, saved.write, saved.digest, saved.state_hash


def maybe(path): return read(path) if path.exists() else {}


def retained_state(bundle, scene, arm):
    folder = bundle/'runs'/scene
    record = maybe(folder/arm/'result.json')
    if 'schedule' in record: return record['schedule']['final_state']
    stages = sorted((folder/arm).glob('stage_*/accepted_state.json'))
    if stages: return read(stages[-1])['state']
    for name, field in (('handoff.json', 'state'), ('topology/terminal.json', 'final_state'), ('topology/checkpoint.json', 'state')):
        if (folder/name).exists(): return read(folder/name)[field]
    return read(bundle/'inputs'/scene/'initial_state.json')


def latest_work(folder):
    candidates = []
    for path in folder.rglob('*.json') if folder.exists() else []:
        record = read(path)
        if isinstance(record, dict) and isinstance(record.get('work'), dict):
            candidates.append(record['work'])
    return max(candidates, key=lambda w:w.get('total_attempted', 0), default=None)


def verify_work(work):
    assert work['total_attempted'] == sum(work['attempted'].values()) == sum(work['per_frequency_attempted'].values())
    assert work['total_attempted'] == sum(work['completed'].values())+sum(work['failed'].values())
    for key in ('completed','failed'):
        assert sum(work[key].values()) == sum(work['per_frequency_'+key].values())
    assert work['calls'].get('preserved_candidate_refusals',0) <= sum(work['failed'].values())
    assert work['total_attempted'] <= work['solve_cap']
    assert work['active_wall_seconds'] <= work['wall_ceiling_seconds'] + 5


def verify_arm(folder, record, train, original, arm):
    schedule = record.get('schedule', {})
    initial_file = folder/'initial_endpoint_predictions.json'
    if initial_file.exists():
        initial = read(initial_file)
        saved.verify_prediction_scores(initial, initial['score'], train, original)
    previous = schedule.get('initial_state_sha256')
    rows = []
    for stage in schedule.get('stages', []):
        number = stage['stage']; active = 1 if arm == 'S' else number
        terminal = stage['terminal']; state = terminal['final_state']; h = state_hash(state)
        path = folder/f'stage_{number}'
        assert terminal['state_sha256'] == h
        assert stage['start_state_sha256'] == previous == state_hash(read(path/'initial_state.json'))
        assert read(path/'terminal.json') == terminal
        assert terminal['production_nodes'] == 256 and terminal['refined_nodes'] == 512
        assert stage['active_frequencies_hz'] == saved.TRAIN[:active]
        gradient = terminal.get('gradient')
        if gradient is not None:
            assert gradient['state_sha256'] == h and gradient['active_frequencies_hz'] == saved.TRAIN[:active]
        if 'score' in stage:
            prediction = read(path/'endpoint_predictions.json')
            assert prediction['state_sha256'] == state_hash(prediction['state']) == stage['score_state_sha256'] == h
            assert prediction['score'] == stage['score']
            saved.verify_prediction_scores(prediction, stage['score'], train, original)
            assert stage['work_after_endpoint']['stage_attempted'] <= saved.QUOTAS[number-1]
        for accepted in maybe(path/'acceptance.json'):
            if accepted['accepted']:
                assert min(accepted['production_gain'], accepted['refined_gain']) > accepted['margin']+accepted['disagreement_allowance']
        trajectory = path/'trajectory.jsonl'
        if trajectory.exists():
            losses = [json.loads(line)['loss'] for line in trajectory.read_text().splitlines()]
            assert all(b <= a+1e-15 for a,b in zip(losses,losses[1:]))
        rows.append(saved.score_row(f'{arm} stage {number}', stage.get('score'), h,
            active_frequencies_hz=stage['active_frequencies_hz'], stop=terminal['stage_outcome'],
            optimizer_stop=terminal['optimizer_stop'], effective_training_exposure=terminal['effective_training_exposure'],
            convergence=terminal['convergence'], accepted_steps=terminal['accepted_steps'], gradient=gradient))
        previous = h
    if schedule.get('schedule_complete'):
        assert [s['stage'] for s in schedule['stages']] == [1,2,3,4]
        assert previous == schedule['final_state_sha256'] == state_hash(schedule['final_state'])
        assert schedule['final'] == schedule['stages'][-1]['score']
    return rows


def verify_topology(folder, control):
    terminal = maybe(folder/'terminal.json')
    if not terminal: return False
    events = read(folder/'events.json')
    rows = [json.loads(line) for line in (folder/'trajectory.jsonl').read_text().splitlines()]
    assert rows and all(b['loss'] <= a['loss']+1e-12*max(1,abs(a['loss'])) for a,b in zip(rows,rows[1:]))
    for event in events:
        dp = event['production_before']-event['production_after']; dr=event['refined_before']-event['refined_after']
        margin = control['acceptance_absolute_margin']+control['acceptance_relative_margin']*event['production_before']
        assert min(dp,dr) > margin+control['cross_resolution_factor']*abs(dp-dr)
    return terminal['stop_reason'] in ('topology_stationary','recovered')


def summarize(bundle, render=True):
    manifest = read(bundle/'manifest.json')
    saved.verify_inputs(bundle, {**manifest, 'historical_sha256':manifest['historical_input_sha256']})
    for name,sha in read(bundle/'artifact_manifest.json').items(): assert digest(bundle/name) == sha, name
    contract = read(bundle/'contract.json'); spec = read(bundle/'scene_spec.json')
    assert len(spec['scenes']) == 12 and contract['scenes'] == [s['id'] for s in spec['scenes']]
    geometry = read(bundle/'geometry_scores.json'); assert geometry['new_physical_solves'] == 0
    audit, campaign = read(bundle/'oracle_audit.json'), read(bundle/'campaign.json')
    works = [audit['work']]; rows=[]; stages={}; complete=True
    for scene in spec['scenes']:
        name=scene['id']; folder=bundle/'runs'/name; result=maybe(folder/'result.json')
        topology_pass=verify_topology(folder/'topology', contract['topology_controller'])
        prefix=result.get('topology_work') or latest_work(folder/'topology')
        if prefix: works.append(prefix)
        input_folder=bundle/'inputs'/name
        train=maybe(input_folder/'training_observations.json'); original=read(input_folder/'observations.json')
        arm_records={arm:maybe(folder/arm/'result.json') or result.get('arms',{}).get(arm,{}) for arm in ('S','F')}
        scene_works=[]
        for arm in ('S','F'):
            record=arm_records[arm]; schedule=record.get('schedule',{})
            stages[name+'/'+arm]=verify_arm(folder/arm,record,train,original,arm)
            work=record.get('work') or latest_work(folder/arm)
            if work: works.append(work); scene_works.append(work)
            retained=retained_state(bundle,name,arm); h=state_hash(retained)
            g=geometry['scenes'][name][arm]; assert g['state_sha256'] == h
            score=schedule.get('final')
            if score is not None:
                assert score['state_sha256'] == h
                assert score['geometry'] == g['geometry']
            recovered=bool(topology_pass and record.get('sources_and_inputs_unchanged') and
                schedule.get('schedule_complete') and schedule.get('complete_effective_exposure') and
                schedule.get('numerically_qualified') and schedule.get('reconstruction_gates_pass'))
            assert bool(record.get('fresh_recovery_pass',False)) == recovered
            row=dict(scene=name,arm=arm,status=record.get('status', result.get('status','NOT_DISPATCHED')),
                reason=record.get('reason',schedule.get('reason',result.get('reason'))), recovered=recovered,
                topology_pass=topology_pass, schedule_complete=schedule.get('schedule_complete',False),
                numerically_qualified=schedule.get('numerically_qualified',False),
                convergence=schedule.get('convergence','UNAVAILABLE'), state_sha256=h,
                count=g['geometry']['component_count'], truth_count=g['geometry']['truth_component_count'],
                boundary_mm=None if g['geometry']['maximum_matched_hausdorff_m'] is None else
                    1000*g['geometry']['maximum_matched_hausdorff_m'], iou=g['geometry']['union_iou'],
                prediction_errors=None if score is None else score['training_errors']+score['evaluation_errors'],
                gates=None if score is None else score['gates'], capacity=result.get('capacity'),
                prefix_attempted_calls=0 if prefix is None else prefix['total_attempted'],
                continuation_attempted_calls=0 if work is None else work['total_attempted'],
                work_is_lower_bound=not bool(result.get('sources_and_inputs_unchanged')))
            row['standalone_attempted_calls']=row['prefix_attempted_calls']+row['continuation_attempted_calls']
            rows.append(row)
        if result.get('sources_and_inputs_unchanged'):
            assert result['actual_attempted_calls'] == (0 if prefix is None else prefix['total_attempted'])+sum(w['total_attempted'] for w in scene_works)
        else: complete=False
        s,f=(arm_records[a].get('schedule',{}).get('stages',[]) for a in ('S','F'))
        if len(f)>=2: assert s[0]['score_state_sha256'] == f[0]['score_state_sha256']
    for work in works: verify_work(work)
    actual=sum(w['total_attempted'] for w in works)
    assert actual <= contract['campaign_solve_cap']
    assert len(rows)==24 and len({(r['scene'],r['arm']) for r in rows})==24
    counts={a:sum(r['recovered'] for r in rows if r['arm']==a) for a in ('S','F')}
    regressions=[name for name in contract['scenes'] if next(r for r in rows if r['scene']==name and r['arm']=='S')['recovered']
        and not next(r for r in rows if r['scene']==name and r['arm']=='F')['recovered']]
    ledger=dict(actual_attempted_calls=actual, actual_completed_solves=sum(sum(w['completed'].values()) for w in works),
        actual_failed_or_refused_calls=sum(sum(w['failed'].values()) for w in works),
        actual_geometry_refused_calls=sum(w['calls'].get('preserved_candidate_refusals',0) for w in works),
        summed_active_seconds=sum(w['active_wall_seconds'] for w in works),
        elapsed_seconds=campaign['elapsed_wall_seconds'], attempt_counts_complete=complete,
        oracle_work=audit['work'], shared_prefix_counted_once=True)
    report=dict(rows=rows, stages=stages, recovery_counts=counts, adverse_matched_scenes=regressions,
        complete_matrix_measured=complete, full_candidate_recovery=counts['F']==12 and complete,
        outcome='FULL_CANDIDATE_RECOVERY' if counts['F']==12 and complete else 'REQUIRED_RECOVERY_GATES_REMAIN_OPEN',
        work=ledger, no_production_promotion=True)
    write(bundle/'scorecard.json',report)
    write(bundle/'work_ledger.json',ledger)
    write(bundle/'verification.json',dict(status='PASS',new_physical_solves=0,scene_rows=12,arm_rows=24,
        sources_inputs_predictions_events_gradients_acceptance_and_work_verified=True,attempt_counts_complete=complete))
    fields=['scene','arm','status','recovered','count','truth_count','boundary_mm','iou','numerically_qualified',
        'schedule_complete','convergence','prefix_attempted_calls','continuation_attempted_calls','standalone_attempted_calls',
        'work_is_lower_bound','reason']
    with (bundle/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    if render: figures(bundle,spec,rows)
    write(bundle/'artifact_manifest.json',{str(x.relative_to(bundle)):digest(x) for x in sorted(bundle.rglob('*'))
        if x.is_file() and x.name!='artifact_manifest.json'})
    return report


def truth_points(item):
    points=[]
    for i in range(513):
        t=2*math.pi*i/512
        if item['kind']=='circle': x,y=item['radius']*math.cos(t),item['radius']*math.sin(t)
        elif item['kind']=='ellipse':
            a,b=item['semi_major']*math.cos(t),item['semi_minor']*math.sin(t)
            c,s=math.cos(item['rotation']),math.sin(item['rotation']);x,y=c*a-s*b,s*a+c*b
        else:
            radius=item['mean_radius']*(1+item['amplitude']*math.cos(item['lobes']*(t-item['rotation'])))
            x,y=radius*math.cos(t),radius*math.sin(t)
        points.append((item['center'][0]+x,item['center'][1]+y))
    return points


def figures(bundle,spec,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    states={}
    for arm in ('S','F'):
        fig,axes=plt.subplots(4,3,figsize=(13,16))
        for axis,scene in zip(axes.flat,spec['scenes']):
            name=scene['id'];row=next(r for r in rows if r['scene']==name and r['arm']==arm)
            state=retained_state(bundle,name,arm);states[name+'/'+arm]=state_hash(state)
            for i,item in enumerate(scene['truth']):
                axis.plot(*zip(*truth_points(item)),'--',color='#475569',linewidth=1.3,label='Target' if i==0 else None)
            for i,component in enumerate(state or []):
                axis.plot(*zip(*saved.curve_points(component)),color='#0d9488',linewidth=1.5,label='Saved endpoint' if i==0 else None)
            error='unmatched' if row['boundary_mm'] is None else f"{row['boundary_mm']:.3f} mm"
            axis.set(title=name+'\n'+('PASS' if row['recovered'] else 'NOT QUALIFIED')+' · '+error,
                aspect='equal',xlim=(.28,.72),ylim=(.28,.74),xlabel='x (m)',ylabel='y (m)')
            axis.grid(alpha=.2)
        axes.flat[0].legend(fontsize=8)
        fig.suptitle(f'TOP-021 · {arm} · all twelve frozen scenes',fontsize=16)
        fig.tight_layout();fig.savefig(bundle/f'{arm}_all_scenes.svg',metadata={'Date':None})
        fig.savefig(bundle/f'{arm}_all_scenes.png',dpi=130);plt.close(fig)
    write(bundle/'figure_manifest.json',dict(new_physical_solves=0,states=states,truth_source='scene_spec.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    report=summarize(parser.parse_args().bundle.resolve())
    print(json.dumps({k:report[k] for k in ('outcome','recovery_counts','adverse_matched_scenes','complete_matrix_measured')}))
