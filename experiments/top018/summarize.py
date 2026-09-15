"""Rebuild/verify TOP-018 from saved JSON and source hashes; no physical imports."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def state_hash(state):return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def score_row(label,score,state=None,**extra):
    if score is None:return dict(label=label,status='SCORE_UNAVAILABLE',**extra)
    return dict(label=label,state_sha256=state or score.get('state_sha256'),
        boundary_mm=score['geometry']['maximum_matched_hausdorff_m']*1000,
        iou=score['geometry']['union_iou'],errors=score['training_errors']+score['evaluation_errors'],
        gates=score['gates'],original_gates_pass=score['original_gates_pass'],
        numerically_qualified=score['numerically_qualified'],**extra)


def summarize(bundle):
    manifest=read(bundle/'manifest.json');audit=read(bundle/'phase_a/audit.json');campaign=read(bundle/'campaign.json')
    for name,sha in manifest['source_sha256'].items():assert digest(ROOT/name)==sha,('source',name)
    for name,sha in manifest['input_sha256'].items():assert digest(bundle/name)==sha,('input',name)
    for name,sha in manifest['historical_sha256'].items():assert digest(ROOT/name)==sha,('history',name)
    common=read(bundle/'inputs/far-two-stars/state.json');common_hash=state_hash(common)
    work=[audit['work']];rows=[];trials={};unavailable=[]
    if 'common_score' in audit:
        rows.append(score_row('COMMON',audit['common_score'],common_hash,production_nodes=256,refined_nodes=512))
    for arm in ('S','F'):
        path=bundle/'runs'/f'{arm}-far-two-stars/metrics.json'
        if not path.exists():
            unavailable.append(dict(arm=arm,status='NOT_RUN' if audit['status']!='PHASE_A_PASS' else 'METRICS_UNAVAILABLE'))
            rows.append(dict(label=f'{arm} final stage 4',status=unavailable[-1]['status']))
            continue
        trial=read(path);trials[arm]=trial
        assert audit['status']=='PHASE_A_PASS' and audit['gate']['passed']
        assert trial['initial_state_sha256']==state_hash(trial['initial_state'])==common_hash
        assert trial['final_state_sha256']==state_hash(trial['final_state'])
        assert trial['source_integrity']
        assert [x['stage'] for x in trial['stages']]==[2,3,4][:len(trial['stages'])]
        work.append(trial['work'])
        previous=common_hash
        for index,stage in enumerate(trial['stages']):
            t=stage['terminal'];h=state_hash(t['final_state']);active=1 if arm=='S' else stage['stage']
            assert stage['start_state_sha256']==previous
            assert t['state_sha256']==h and t['production_nodes']==256 and t['refined_nodes']==512
            assert stage['active_frequencies_hz']==[.5e9,.75e9,1e9,1.25e9][:active]
            gradient=t.get('gradient')
            if gradient is not None:
                assert gradient['state_sha256']==h and gradient['production_nodes']==256 and gradient['refined_nodes']==512
                assert gradient['active_frequencies_hz']==stage['active_frequencies_hz']
                assert gradient['objective_sha256']==t['objective_identity']['objective_sha256']
            if 'score' in stage:
                assert stage['score_state_sha256']==stage['score']['state_sha256']==h
                assert stage['score']['objective_sha256']==t['objective_identity']['objective_sha256']
            start=t['work']['total_attempted']-t['work']['stage_attempted']
            if index+1<len(trial['stages']):
                following=trial['stages'][index+1]['terminal']['work']
                end=following['total_attempted']-following['stage_attempted']
            else:end=trial['work']['total_attempted']
            assert end-start<=t['work']['stage_quota']
            score=stage.get('score')
            if score is None and index==len(trial['stages'])-1 and trial.get('reporting_score'):
                score=trial['reporting_score']
                assert trial['reporting_score_state_sha256']==h and trial['reporting_score_releases_stage'] is False
            rows.append(score_row(f'{arm} stage {stage["stage"]}',score,h,
                stage=stage['stage'],arm=arm,active_frequencies_hz=stage['active_frequencies_hz'],
                production_nodes=256,refined_nodes=512,production_objective=t['production_loss'],
                refined_objective=None if score is None else .5*sum(x*x for x in score['training_errors'][:active])/active,
                effective_training_exposure=t['effective_training_exposure'],configured_convergence=t['convergence'],
                stop=t['stage_outcome'],optimizer_stop=t['optimizer_stop'],stop_detail=t['reason'],
                accepted_steps=t['accepted_steps'],candidate_attempts=t['exposure'].get('candidate_attempts',0),
                solve_attempts_including_endpoint=end-start,work=t['work'],gradient=t.get('gradient'),
                reporting_only='score' not in stage,stage_complete=stage.get('stage_complete',False)))
            previous=h
        if not any(s['stage']==4 for s in trial['stages']):
            rows.append(dict(label=f'{arm} final stage 4',status='NOT_REACHED'))
        failure_paths=list(path.parent.glob('stage_*/numerical_failure.json'))
        for failure_path in failure_paths:
            failure=read(failure_path)
            assert failure['accepted'] is False
            checkpoint=read(failure_path.parent/'accepted_state.json')
            assert failure['accepted_state_sha256']==checkpoint['state_sha256']==state_hash(checkpoint['state'])
            for key in ('production_base','production_candidate','refined_base','refined_candidate'):
                assert failure[key]['state_sha256']==state_hash(failure[key]['state'])
    if audit['status']!='PHASE_A_PASS':assert not trials and not campaign['workers']
    totals={key:Counter() for key in ('attempted','completed','failed')}
    for w in work:
        assert w['total_attempted']==sum(w['attempted'].values())<=w['solve_cap']
        assert w['total_attempted']==sum(w['completed'].values())+sum(w['failed'].values())
        for key in totals:totals[key].update(w[key])
    assert audit['work']['total_attempted']<=256
    assert sum(totals['attempted'].values())<=14256
    complete=len(trials)==2 and all(t['schedule_complete'] and t['numerically_qualified'] for t in trials.values())
    if audit['status']!='PHASE_A_PASS':
        outcome='PHASE_A_NOT_QUALIFIED'
        decision='Scope one examination of the recorded Phase-A obstruction before considering any further inverse.'
    elif not complete:
        outcome='MATCHED_PAIR_INCOMPLETE'
        decision='Scope one examination of the retained runtime obstruction; do not extend the resolution ladder or restart these trials.'
    elif trials['F']['final']['original_gates_pass']:
        if trials['S']['final']['original_gates_pass']:
            outcome='BOTH_ARMS_RECOVERED'
        else:outcome='F_RECOVERED_RELATIVE_TO_MATCHED_S'
        decision='Consider one separately scoped merge-capacity qualification before a broader integration comparison.'
    else:
        sf,ss=trials['F']['final'],trials['S']['final']
        improved=(sf['geometry']['maximum_matched_hausdorff_m']<ss['geometry']['maximum_matched_hausdorff_m'] and
                  sf['maximum_evaluation_error']<ss['maximum_evaluation_error'])
        outcome='PARTIAL_F_BENEFIT_WITHOUT_RECOVERY' if improved else 'NO_DEMONSTRATED_F_ADVANTAGE'
        decision='Consider one separately scoped fixed-topology recovery limitation study using these qualified endpoints; no automatic restart.'
    central_path=ROOT/'results/validation/topology/TOP-017-20260914-staged-continuation/runs/F-central-ellipse-star/metrics.json'
    central=read(central_path)
    central_row=score_row('TOP-017 central F (reused)',central['final'],central['final_state_sha256'],
                          production_nodes=128,refined_nodes=256,source=str(central_path.relative_to(ROOT)),source_sha256=digest(central_path))
    scorecard=dict(outcome=outcome,decision=decision,pair_complete_and_qualified=complete,rows=rows,
        reused_central=central_row,unavailable_arms=unavailable,
        trials={a:{k:t[k] for k in ('status','schedule_complete','numerically_qualified','convergence',
            'complete_effective_exposure','reconstruction_gates_pass','work')} for a,t in trials.items()})
    ledger=dict(total_attempted=sum(totals['attempted'].values()),total_completed=sum(totals['completed'].values()),
        total_failed=sum(totals['failed'].values()),by_category={key:dict(value) for key,value in totals.items()},
        phase_a=work[0],trials={a:t['work'] for a,t in trials.items()},
        summed_active_wall_seconds=sum(w['active_wall_seconds'] for w in work),campaign_elapsed_seconds=campaign['elapsed_seconds'],
        historical_reused_solves=54,attempt_counts_complete=not unavailable or audit['status']!='PHASE_A_PASS')
    write(bundle/'scorecard.json',scorecard);write(bundle/'work_ledger.json',ledger)
    audit_table=['| State | Pair | 0.5 GHz | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Qualified |',
                 '|---|---|---:|---:|---:|---:|---:|---:|---|']
    for name,row in audit['states'].items():
        for pair,value in row['comparisons'].items():
            audit_table.append('| '+name+' | '+pair+' | '+' | '.join(f'{x:.8g}' for x in value['discrepancy'])+' | '+str(value['qualified'])+' |')
    (bundle/'resolution_table.md').write_text('# Fixed-state resolution audit\n\n'+ '\n'.join(audit_table)+
        '\n\nThresholds: 1e-7 at 0.75/1.0/1.25 GHz; 1e-5 at 0.5/1.5/2.5 GHz. '+
        '[Full state, threshold-distance and contraction records](phase_a/audit.json).\n')
    table=['| Endpoint | Boundary mm | IoU | 0.5 GHz | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Gates | Qualified | Stop | New solves |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|']
    for row in rows+[central_row]:
        if 'boundary_mm' not in row:
            table.append(f'| {row["label"]} | — | — | — | — | — | — | — | — | — | — | {row["status"]} | 0 |')
        else:
            table.append(f'| {row["label"]} | {row["boundary_mm"]:.7g} | {row["iou"]:.7g} | '+
                ' | '.join(f'{x:.7g}' for x in row['errors'])+
                f' | {row["original_gates_pass"]} | {row["numerically_qualified"]} | {row.get("optimizer_stop") or row.get("stop","reused/start")} | {row.get("solve_attempts_including_endpoint",0)} |')
    summary=f'''# TOP-018: resolution qualification and matched two-star pair

**{outcome}.** {decision}

Approved 2026-09-15 by the user's “yesh” response to the named TOP-018 approval
request. Owner/reviewer: Codex `/root` (owner review; no independent-agent review).
The existing checkout and branch were used. No production promotion or successor
is authorized. The fresh central recovery and TOP-016 merge regression remain
separate, preserved evidence.

## Audit and release

Phase A: **{audit['status']}**, {audit['work']['total_attempted']} new attempted
frequency solves. The earlier 54-solve audit supplies verified predictions for
three historical states; it does not supply new inverse results. COMMON is the
same saved K=9 endpoint for both arms. [Resolution table](resolution_table.md),
[full audit](phase_a/audit.json), [reuse provenance](reuse.json).

## Endpoint scorecard

{chr(10).join(table)}

The final endpoint is prescribed stage 4. Earlier stages are never selected as
the final answer. Both two-star arms use 256/512; the separate central row reuses
TOP-017 at 128/256 and has no new solves. The fixed count was supplied by COMMON.
S fits only 0.5 GHz; its other frequency scores are endpoint audits. F fits the
prescribed cumulative frequencies. Errors at 1.5/2.5 GHz are development
evaluation scores. Geometry gates are boundary <=1 mm and IoU >=0.90; prediction
gates are original-training error <=0.003 and worst evaluation error <=0.05.

Aggregate objectives change with the active set. The [JSON scorecard](scorecard.json)
keeps production/refined objectives, exposure, convergence, actual stops,
acceptances, gradients and state associations separate. Reporting-only scores
cannot release a stopped stage.

## Work, provenance and verification

New calls: **{ledger['total_attempted']} attempted, {ledger['total_completed']} completed,
{ledger['total_failed']} failed**. Historical reused calls: 54, excluded from new
work. Summed active numerical wall time: {ledger['summed_active_wall_seconds']:.3f} s;
campaign elapsed: {ledger['campaign_elapsed_seconds']:.3f} s. At most two workers,
single-thread BLAS. This is not a runtime comparison with TOP-017.

[Work ledger](work_ledger.json) · [frozen contract](contract.json) ·
[source/input manifest](manifest.json) · [approved plan](approved_plan.md) ·
[implementation review](implementation_review.md) · [tests](pre_dispatch_tests.log) ·
[environment and exact command](environment.json) · [worker commands](campaign.json).

Rebuild without physical solves:

```bash
python experiments/top018/summarize.py --bundle {bundle.relative_to(ROOT)}
```
'''
    (bundle/'README.md').write_text(summary)
    verification=dict(status='PASS',source_files=len(manifest['source_sha256']),
        historical_files=len(manifest['historical_sha256']),input_files=len(manifest['input_sha256']),
        source_input_state_score_gradient_and_solve_associations_verified=True,
        complete_pair=complete,new_physical_solves_in_verification=0)
    write(bundle/'verification.json',verification)
    write(bundle/'artifact_manifest.json',{str(x.relative_to(bundle)):digest(x) for x in sorted(bundle.rglob('*'))
          if x.is_file() and x.name!='artifact_manifest.json'})
    print(json.dumps(dict(outcome=outcome,total_attempted=ledger['total_attempted'],verification=verification)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    summarize(parser.parse_args().bundle.resolve())
