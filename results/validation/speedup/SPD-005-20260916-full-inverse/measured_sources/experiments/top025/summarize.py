"""Verify TOP-025 and report every scene, including failures, without BIE work."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.top021 import summarize as old

read,write,digest,state_hash=old.read,old.write,old.digest,old.state_hash


def geometry_scores(bundle):
    # Geometry evaluation is explicitly guarded against any physical solve.
    from experiments.top025 import run as run
    ledger=run.m.Ledger(cap=0,seconds=1800);result={}
    with ledger.instrument():
        for scene in read(bundle/'scene_spec.json')['scenes']:
            state=old.retained_state(bundle,scene['id'],'F')
            result[scene['id']]=dict(state_sha256=state_hash(state),
                geometry=run.p.benchmark.geometry_metrics(run.p.driver.deserialize_state(state),scene,read(bundle/'scene_spec.json')))
    assert ledger.total==0
    write(bundle/'geometry_scores.json',dict(new_physical_solves=0,scenes=result))
    return result


def failure_labels(row):
    labels=[]
    if row['count']!=row['truth_count']: labels.append('wrong component count')
    if row['boundary_mm'] is None or row['boundary_mm']>1: labels.append('boundary > 1 mm or unmatched')
    if row['iou']<.90: labels.append('IoU < 0.90')
    errors=row['prediction_errors']
    if errors is None: labels.append('final prediction score unavailable')
    else:
        if errors[0]>.003: labels.append('training error > 0.003')
        if max(errors[4:])>.05: labels.append('development error > 0.05')
    if not row['numerically_qualified']: labels.append('numerical qualification incomplete/failed')
    if not row['topology_pass']: labels.append('topology handoff incomplete/failed')
    if not row['schedule_complete']: labels.append('continuation incomplete')
    if row.get('reason'): labels.append(str(row['reason']))
    return labels


def summarize(bundle):
    manifest=read(bundle/'manifest.json')
    old.saved.verify_inputs(bundle,{**manifest,'historical_sha256':manifest['historical_input_sha256']})
    for name,sha in read(bundle/'artifact_manifest.json').items(): assert digest(bundle/name)==sha,name
    contract=read(bundle/'contract.json');spec=read(bundle/'scene_spec.json');audit=read(bundle/'oracle_audit.json')
    campaign=read(bundle/'campaign.json')
    assert contract['experiment']=='TOP-025' and contract['arms']==['F']
    assert contract['scenes']==[s['id'] for s in spec['scenes']] and len(spec['scenes'])==12
    assert contract['stage_plan']==[[1,1000],[2,1250],[3,1750],[4,4000]]
    geometry=geometry_scores(bundle);works=[audit['work']];rows=[];stages={};complete=True
    workers={w['scene']:w for w in campaign['workers']}
    for scene in spec['scenes']:
        name=scene['id'];folder=bundle/'runs'/name;result=old.maybe(folder/'result.json')
        continuation=old.maybe(folder/'F/result.json') or result.get('continuation',{})
        schedule=continuation.get('schedule',{})
        inputs=bundle/'inputs'/name
        topology_pass=all((folder/'topology'/name).exists() for name in
            ('terminal.json','events.json','trajectory.jsonl')) and old.verify_topology(folder/'topology',contract['topology_controller'])
        train=old.maybe(inputs/'training_observations.json');original=read(inputs/'observations.json')
        stages[name]=old.verify_arm(folder/'F',continuation,train,original,'F')
        prefix=result.get('topology_work') or old.latest_work(folder/'topology')
        work=continuation.get('work') or old.latest_work(folder/'F')
        for item in (prefix,work):
            if item: works.append(item)
        retained=old.retained_state(bundle,name,'F');h=state_hash(retained)
        g=geometry[name];assert g['state_sha256']==h
        score=schedule.get('final')
        if score is not None:
            assert score['state_sha256']==h and score['geometry']==g['geometry']
        if result:
            assert result['original_start_sha256']==state_hash(read(inputs/'initial_state.json'))
            assert not result['supplied_target_count'] and not result['archived_optimized_state_used']
        integrity=bool(result.get('sources_and_inputs_unchanged'))
        accounting_complete=bool(integrity and result.get('status')!='IN_PROGRESS' and workers.get(name,{}).get('exit_code')==0)
        recovered=bool(integrity and topology_pass and schedule.get('schedule_complete') and
            schedule.get('complete_effective_exposure') and schedule.get('numerically_qualified') and schedule.get('reconstruction_gates_pass'))
        assert bool(result.get('fresh_recovery_pass',False))==recovered
        if accounting_complete:
            assert result['actual_attempted_calls']==sum(item['total_attempted'] for item in (prefix,work) if item)
        else: complete=False
        row=dict(scene=name,title=scene['title'],status=result.get('status',workers.get(name,{}).get('status','NOT_DISPATCHED')),
            reason=result.get('reason',continuation.get('reason',schedule.get('reason'))),recovered=recovered,
            topology_pass=topology_pass,schedule_complete=schedule.get('schedule_complete',False),
            numerically_qualified=schedule.get('numerically_qualified',False),convergence=schedule.get('convergence','UNAVAILABLE'),
            state_sha256=h,count=g['geometry']['component_count'],truth_count=g['geometry']['truth_component_count'],
            boundary_mm=None if g['geometry']['maximum_matched_hausdorff_m'] is None else 1000*g['geometry']['maximum_matched_hausdorff_m'],
            iou=g['geometry']['union_iou'],prediction_errors=None if score is None else score['training_errors']+score['evaluation_errors'],
            gates=None if score is None else score['gates'],capacity=result.get('capacity'),
            prefix_attempted_calls=0 if prefix is None else prefix['total_attempted'],
            continuation_attempted_calls=0 if work is None else work['total_attempted'],work_is_lower_bound=not accounting_complete,
            worker_exit_code=workers.get(name,{}).get('exit_code'))
        row['attempted_calls']=row['prefix_attempted_calls']+row['continuation_attempted_calls']
        row['failure_labels']=failure_labels(row);rows.append(row)
    for work in works: old.verify_work(work)
    total=sum(w['total_attempted'] for w in works)
    assert total<=contract['campaign_solve_cap'] and len(rows)==12 and len({r['scene'] for r in rows})==12
    ledger=dict(total_attempted_calls=total,completed_solves=sum(sum(w['completed'].values()) for w in works),
        failed_or_refused_calls=sum(sum(w['failed'].values()) for w in works),
        geometry_refused_calls=sum(w['calls'].get('preserved_candidate_refusals',0) for w in works),
        summed_active_seconds=sum(w['active_wall_seconds'] for w in works),elapsed_seconds=campaign['elapsed_wall_seconds'],
        counts_complete=complete,oracle_work=audit['work'])
    report=dict(experiment='TOP-025',rows=rows,stages=stages,recovered_count=sum(row['recovered'] for row in rows),
        scene_count=12,all_scenes_attempted=len(workers)==12,work=ledger,production_promotion=False,
        source_revision=manifest['git_revision'],source_files=len(manifest['source_sha256']))
    write(bundle/'scorecard.json',report);write(bundle/'work_ledger.json',ledger)
    write(bundle/'verification.json',dict(status='PASS',new_physical_solves=0,scene_rows=12,
        sources_inputs_predictions_events_gradients_acceptance_and_work_verified=True,counts_complete=complete))
    fields=['scene','status','recovered','count','truth_count','boundary_mm','iou','numerically_qualified',
        'schedule_complete','convergence','attempted_calls','work_is_lower_bound','reason','failure_labels']
    with (bundle/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    return report


def write_index(bundle):
    report=read(bundle/'scorecard.json');work=report['work']
    lines=['# Latest pipeline — all twelve scenes','',
        f"**{report['recovered_count']} / 12 scenes pass all original recovery and numerical gates.**",'',
        '[Watch the all-scene overview](videos/all_scenes.mp4) · [Final contact sheet](all_scenes.png) · [Machine-readable table](comparison.csv)','',
        'Every scene was run freshly from its original initialization with the same frozen current source. '
        'Pipeline: automatic H topology → cumulative four-frequency refinement at 256/512; '
        'K17 for one returned component, K9 otherwise. No scene-specific method choice or diagnostic damping reset.','',
        f"Source base `{report['source_revision'][:12]}` plus the [frozen source manifest](manifest.json). "
        'All measured source files are archived under `measured_sources/`. This is a descriptive current-code evaluation, not a matched policy comparison.','',
        '## Scene gallery','',
        '| Scene / video | Outcome | Count | Boundary (mm) | IoU | Worst development error | What failed |',
        '|---|---|---:|---:|---:|---:|---|']
    for row in report['rows']:
        error='unmatched' if row['boundary_mm'] is None else f"{row['boundary_mm']:.4f}"
        prediction='unavailable' if row['prediction_errors'] is None else f"{max(row['prediction_errors'][4:]):.5g}"
        outcome='PASS' if row['recovered'] else ('STOPPED' if not row['schedule_complete'] else 'FAIL')
        failures='—' if row['recovered'] else '; '.join(row['failure_labels'])
        lines.append(f"| [{row['title']}](videos/{row['scene']}.mp4) | **{outcome}** | {row['count']}/{row['truth_count']} | {error} | {row['iou']:.4f} | {prediction} | {failures} |")
    lines+=['','## How to read the videos','',
        'Dashed outlines are targets; solid teal outlines are actual saved accepted reconstructions. '
        'Phases and frequency sets are labelled. Repeated frames slow playback; coefficients are never interpolated. '
        'Playback duration does not represent computational time. Empty starts and failed/partial runs stay visible. '
        'Final metric panels describe the exact retained state; unavailable prediction scores are explicitly marked.','',
        'Recovery requires the correct component count, boundary error ≤1 mm, IoU ≥0.90, original training error ≤0.003, '
        'worst development error ≤0.05, valid topology events and numerical checks. A small training residual is insufficient.','',
        '## Work and reproducibility','',
        f"{work['total_attempted_calls']:,} charged calls; {work['completed_solves']:,} completed systems; "
        f"{work['failed_or_refused_calls']:,} failed/refused calls, including {work['geometry_refused_calls']:,} handled geometry refusals. "
        f"Campaign elapsed {work['elapsed_seconds']/60:.2f} min with at most four BLAS-1 workers. "
        f"Complete accounting: {work['counts_complete']}. Partial counts are labelled as lower bounds.",'',
        '[Contract](approved_plan.md) · [Artifact verification](verification.json) · [Work ledger](work_ledger.json) · '
        '[Worker commands and exits](campaign.json) · [Video provenance](video_manifest.json)','',
        'The original observations, starts and success thresholds are unchanged. Added training frequencies and the '
        'capacity policy are explicit parts of this candidate. All failures remain in the table; no production promotion '
        'or corrective redesign is implied by completing the evaluation.']
    (bundle/'README.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    result=summarize(parser.parse_args().bundle.resolve())
    print(json.dumps({k:result[k] for k in ('recovered_count','scene_count','all_scenes_attempted','work')}))
