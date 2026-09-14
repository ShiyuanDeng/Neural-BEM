"""Rebuild TOP-017 tables and decision from JSON, with no numerical imports."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'results/validation/topology/TOP-016-20260914-fixed-topology'
SCENES=('far-two-stars','central-ellipse-star')
FREQUENCIES=[.5e9,.75e9,1e9,1.25e9,1.5e9,2.5e9]
NORMALIZATION='0.5 * mean_f(||prediction_f-observed_f||_2^2 / ||observed_f||_2^2)'


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');os.replace(tmp,path)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def state_hash(state):return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def objective(score,m):return .5*sum(x*x for x in score['training_errors'][:m])/m


def merge_audit(bundle):
    rows=[]
    associations={r['path']:r for r in read(SOURCE/'gradient_associations.json')}
    first_geometry=first_prediction=None
    for arm in ('S','F'):
        trial=read(SOURCE/'runs'/f'{arm}-merge/metrics.json')
        stages=trial['stages']
        starts=[s['terminal']['work']['total_attempted']-s['terminal']['work']['stage_attempted'] for s in stages]
        ends=starts[1:]+[trial['work']['total_attempted']]
        previous=trial['initial'];start_state=trial['initial_state']
        for stage,start,end in zip(stages,starts,ends):
            n=stage['stage'];m=len(stage['active_frequencies_hz']);score=stage['score']
            association=associations.get(f'runs/{arm}-merge/stage_{n}/terminal_gradient.json')
            row=dict(arm=arm,stage=n,active_frequencies_hz=stage['active_frequencies_hz'],
                all_frequencies_hz=FREQUENCIES,start_errors=previous['training_errors']+previous['evaluation_errors'],
                endpoint_errors=score['training_errors']+score['evaluation_errors'],
                start_boundary_mm=1000*previous['geometry']['maximum_matched_hausdorff_m'],
                endpoint_boundary_mm=1000*score['geometry']['maximum_matched_hausdorff_m'],
                start_iou=previous['geometry']['union_iou'],endpoint_iou=score['geometry']['union_iou'],
                same_active_refined_objective_start=objective(previous,m),
                same_active_refined_objective_endpoint=objective(score,m),
                same_active_refined_gain=objective(previous,m)-objective(score,m),
                start_state_sha256=state_hash(start_state),endpoint_state_sha256=state_hash(stage['terminal']['final_state']),
                normalization=NORMALIZATION,production_nodes=128,refined_nodes=256,
                actual_stop=stage['terminal']['stop_reason'],failure_type=stage['terminal']['failure_type'],
                attempted_solves_including_endpoint=end-start,accepted_steps=stage['terminal']['accepted_steps'],
                gradient=stage['terminal']['gradient'],gradient_association=association,
                numerical_checks=score['numerical_checks'],numerically_qualified=score['numerically_qualified'])
            row['prediction_worsened_at_hz']=[f for f,a,b in zip(FREQUENCIES,row['start_errors'],row['endpoint_errors']) if b>a]
            if first_prediction is None and row['prediction_worsened_at_hz']:first_prediction=dict(arm=arm,stage=n,frequencies_hz=row['prediction_worsened_at_hz'])
            if first_geometry is None and row['endpoint_boundary_mm']>row['start_boundary_mm']:first_geometry=dict(arm=arm,stage=n)
            rows.append(row);previous=score;start_state=stage['terminal']['final_state']
    report=dict(source_bundle=str(SOURCE.relative_to(ROOT)),source_metrics_sha256={a:digest(SOURCE/'runs'/f'{a}-merge/metrics.json') for a in ('S','F')},
        rows=rows,first_recorded_prediction_deterioration=first_prediction,first_recorded_geometry_deterioration=first_geometry,
        limitations=['Historical refined rejection log only covers production-decreasing candidates.',
                    'Historical feasibility refusal and interrupted derivative counts are incomplete.',
                    'Projection audit cannot replace or excuse the measured merge inverse regression.'])
    write(bundle/'merge_stage_audit.json',report)
    table=['| Arm/stage | GHz | Boundary mm start → end | IoU end | 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Same-objective gain | Stop | Solves |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        errors=' | '.join(f'{x:.7g}' for x in r['endpoint_errors'])
        freqs=','.join(f'{x/1e9:g}' for x in r['active_frequencies_hz'])
        table.append(f"| {r['arm']} {r['stage']} | {freqs} | {r['start_boundary_mm']:.7g} → {r['endpoint_boundary_mm']:.7g} | {r['endpoint_iou']:.7g} | {errors} | {r['same_active_refined_gain']:.7g} | {r['actual_stop']} | {r['attempted_solves_including_endpoint']} |")
    (bundle/'merge_stage_audit.md').write_text('# Saved TOP-016 merge audit\n\nRebuilt from immutable JSON; no inverse or forward reruns. [Full table, starts, gradients and hashes](merge_stage_audit.json).\n\n'+ '\n'.join(table)+'\n\nPrediction deterioration first appears in the shared stage 1 at 2.5 GHz. Geometric deterioration first appears at F stage 2. Every F stage decreases its own active refined objective; those differently normalized objectives are not compared across stage changes. The adverse inverse result remains in force.\n')
    return report


def summarize(bundle):
    merge=merge_audit(bundle)
    audit=read(bundle/'phase_a/audit.json');reuse=read(bundle/'reuse.json') if (bundle/'reuse.json').exists() else {}
    manifest=read(bundle/'manifest.json') if (bundle/'manifest.json').exists() else {}
    trials=[];missing=[]
    for scene in SCENES:
        for arm in ('S','F'):
            path=bundle/'runs'/f'{arm}-{scene}'/'metrics.json'
            if path.exists():trials.append(read(path))
            else:missing.append(dict(scene=scene,arm=arm,status='NOT_RUN'))
    checks=[]
    for name,sha in read(bundle/'historical_manifest.json').items():
        if digest(ROOT/name)!=sha:raise ValueError(f'historical evidence changed: {name}')
    for name,sha in manifest.get('source_sha256',{}).items():
        if digest(ROOT/name)!=sha:raise ValueError(f'measured source changed: {name}')
    for trial in trials:
        assert trial['status']!='IN_PROGRESS'
        assert trial['work']['total_attempted']<=7000
        assert trial['work']['active_wall_seconds']<=1800 or trial.get('reason')=='TRIAL_WALL_LIMIT'
        assert state_hash(trial['initial_state'])==reuse[trial['scene']]['state_sha256']
        assert [s['stage'] for s in trial['stages']]==[2,3,4][:len(trial['stages'])]
        for i,stage in enumerate(trial['stages']):
            t=stage['terminal'];state=state_hash(t['final_state'])
            assert state==t['state_sha256']
            if t['gradient'] is not None:assert t['gradient']['state_sha256']==state
            if 'score' in stage:assert stage['score_state_sha256']==state
            start=t['work']['total_attempted']-t['work']['stage_attempted']
            if i+1<len(trial['stages']):
                nxt=trial['stages'][i+1]['terminal']['work'];end=nxt['total_attempted']-nxt['stage_attempted']
            else:end=trial['work']['total_attempted']
            assert end-start<=t['work']['stage_quota']
            stage['derived_attempted_including_endpoint']=end-start
            stage['unused_quota']=t['work']['stage_quota']-(end-start)
            if 'aggregate_endpoint_objective' in stage:
                stage['same_active_refined_gain']=stage['aggregate_start_objective']-stage['aggregate_endpoint_objective']
        if 'final' in trial:assert trial['final_score_state_sha256']==trial['final_state_sha256']
    work=Counter();completed=Counter();failed=Counter()
    all_work=[audit['work']]+[t['work'] for t in trials]
    for w in all_work:work.update(w['attempted']);completed.update(w['completed']);failed.update(w['failed'])
    assert sum(work.values())<=28256 and audit['work']['total_attempted']<=256
    all_exposed=len(trials)==4 and all(t['complete_effective_exposure'] and t['schedule_complete'] and t['numerically_qualified'] for t in trials)
    criteria={};promising=False
    if trials:
        by={(t['scene'],t['arm']):t for t in trials}
        for scene in SCENES:
            if not all((scene,a) in by and by[scene,a]['schedule_complete'] and
                       by[scene,a]['numerically_qualified'] for a in ('S','F')):continue
            f=by[scene,'F'];s=by[scene,'S'];a=f['initial'];b=f['final'];c=s['final']
            boundary=lambda x:x['geometry']['maximum_matched_hausdorff_m']
            criteria[scene]=dict(boundary_improvement=1-boundary(b)/boundary(a),
                evaluation_improvement=1-b['maximum_evaluation_error']/a['maximum_evaluation_error'],
                iou_not_lower=b['geometry']['union_iou']>=a['geometry']['union_iou'],
                F_not_worse_boundary_than_S=boundary(b)<=boundary(c),
                F_not_worse_evaluation_than_S=b['maximum_evaluation_error']<=c['maximum_evaluation_error'],
                F_boundary_advantage=1-boundary(b)/boundary(c),
                F_evaluation_advantage=1-b['maximum_evaluation_error']/c['maximum_evaluation_error'],
                original_gates_pass=b['original_gates_pass'])
        promising=(all_exposed and all(c['boundary_improvement']>=.3 and c['evaluation_improvement']>=.2 and c['iou_not_lower'] and
             c['F_not_worse_boundary_than_S'] and c['F_not_worse_evaluation_than_S'] for c in criteria.values()) and
             any(c['original_gates_pass'] for c in criteria.values()) and
             any(max(c['F_boundary_advantage'],c['F_evaluation_advantage'])>=.2 for c in criteria.values()))
    if promising:
        outcome='PROMISING_PRINCIPAL_RESULT_NOT_PROMOTED'
        decision='Consider one separately approved control-qualified follow-up, scoped using the preserved merge audit.'
    elif all_exposed:
        outcome='FULL_EXPOSURE_PROTOCOL_NOT_QUALIFIED'
        decision='Close this bounded fixed-K cumulative protocol as not qualified; require one separately justified representation/regularization or optimizer question before more inverse work.'
    else:
        outcome='INCOMPLETE_EXPOSURE_OR_NUMERICAL_OBSTRUCTION'
        decision='Decide whether a separately scoped numerical-resolution check of the saved two-star states is justified before any further continuation experiment.'
    obstructions=[]
    for t in trials:
        if t['status']!='HARD_STOP':continue
        stage=t['stages'][-1] if t['stages'] else None
        item=dict(scene=t['scene'],arm=t['arm'],reason=t.get('reason'),detail=t.get('detail'),
                  stage=None if stage is None else stage['stage'])
        if stage:
            item['terminal_reason']=stage['terminal']['reason']
            item['retained_state_sha256']=stage['terminal']['state_sha256']
            if 'score' in stage:item['endpoint_numerical_checks']=stage['score']['numerical_checks']
            path=bundle/'runs'/f"{t['arm']}-{t['scene']}"/f"stage_{stage['stage']}"/'acceptance.json'
            if path.exists():
                item['rejected_numerically_unqualified_candidates']=[r for r in read(path) if r.get('numerical_obstruction')]
        obstructions.append(item)
    successes=[dict(scene=t['scene'],arm=t['arm'],stage=s['stage'],score=s['score'])
               for t in trials for s in t['stages'] if s.get('score',{}).get('numerically_qualified') and
               s['score']['original_gates_pass']]
    report=dict(experiment='TOP-017',execution_status='COMPLETE',outcome=outcome,decision=decision,
        all_pairs_complete_exposure_and_numerics=all_exposed,promising_principal_predicate=promising,
        production_promotion=False,criteria=criteria,phase_a=audit,trials=trials,missing_trials=missing,
        work=dict(total_attempted=sum(work.values()),total_completed=sum(completed.values()),total_failed=sum(failed.values()),
            attempted_by_category=dict(work),completed_by_category=dict(completed),failed_by_category=dict(failed),
            audit_attempted=audit['work']['total_attempted'],sum_active_worker_seconds=sum(w['active_wall_seconds'] for w in all_work)),
        historical_common_prefix={s:r['common_prefix_per_old_arm_solves'] for s,r in reuse.items()},
        merge_regression_preserved=True,diagnostic_limitations=[
            'Quota/hard-stop endpoints may lack a newly measured terminal gradient; last measured values bind their own exact state.',
            'Interrupted Jacobian one-sided/unresolved counts are complete only through the last completed batch.',
            'Per-frequency requested objective events are distinguished from actual attempted/completed physical calls.',
            'No matrix factorization/RHS instrumentation was added; work counts physical frequency solves.',
            'Original gates are development evaluation criteria, not new benchmark passes or untouched generalization.'])
    report['numerical_obstructions']=obstructions
    report['qualified_successful_predetermined_endpoints']=successes
    write(bundle/'scorecard.json',report)
    rows=[]
    for t in trials:
        def row(label,score,solves='—',stop='—'):
            if not score:return f'| {label} | unavailable | — | — | — | — | — | {solves} | {stop} |'
            g=score['geometry'];e=score['maximum_evaluation_error']
            return f"| {label} | {1000*g['maximum_matched_hausdorff_m']:.6g} | {g['union_iou']:.6g} | {score['training_errors'][0]:.6g} | {e:.6g} | {score['original_gates_pass']} | {score['numerically_qualified']} | {solves} | {stop} |"
        label=f"{t['scene']} {t['arm']}"
        rows.append(row(label+' original TOP-016 start',reuse[t['scene']]['original_top016_start_score']))
        rows.append(row(label+' reused start',t['initial']))
        for s in t['stages']:rows.append(row(label+f" stage {s['stage']}",s.get('score'),s['derived_attempted_including_endpoint'],s['terminal']['stage_outcome']))
    table='\n'.join(rows)
    exposure=[]
    for t in trials:
        for s in t['stages']:
            term=s['terminal'];e=term['exposure'];f=','.join(f'{v/1e9:g}' for v in s['active_frequencies_hz'])
            exposure.append(f"| {t['scene']} {t['arm']} {s['stage']} | {f} | {e.get('jacobian_batches_completed',0)} | {e.get('candidate_attempts',0)} | {term['accepted_steps']} | {term['optimizer_stop']} | {term['convergence']} | {s['unused_quota']} |")
    projections=[]
    for k,r in sorted(audit.get('merge_projection',{}).items(),key=lambda x:int(x[0])):
        sc=r.get('score',{});geom=r['benchmark_geometry']
        projections.append(f"| {k} | {1000*geom['maximum_matched_hausdorff_m']:.7g} | {1000*r['dense_geometry']['16384']['bidirectional_sample_distance_m']:.7g} | {1000*r['dense_geometry']['32768']['bidirectional_sample_distance_m']:.7g} | {sc.get('maximum_evaluation_error')} | {r.get('numerically_qualified')} |")
    benefits=[]
    for t in trials:
        if t['schedule_complete'] and t['numerically_qualified'] and t.get('final',{}).get('original_gates_pass'):
            a=t['initial'];b=t['final']
            benefits.append(f"**{t['scene']} {t['arm']} recovered within the original gates:** boundary {1000*a['geometry']['maximum_matched_hausdorff_m']:.6g} → {1000*b['geometry']['maximum_matched_hausdorff_m']:.6g} mm, IoU {b['geometry']['union_iou']:.6g}, worst evaluation error {a['maximum_evaluation_error']:.6g} → {b['maximum_evaluation_error']:.6g}. This is fixed-count recovery on this development case, not a new benchmark-suite pass.")
    positive='\n\n'.join(benefits)
    obstruction_text='\n'.join(f"- {r['scene']} {r['arm']}, stage {r['stage']}: {r.get('detail') or r.get('terminal_reason') or r['reason']}." for r in obstructions)
    text=f'''# TOP-017 — remaining principal frequency exposure

**{outcome}.** Promising principal predicate: **{promising}**. Production promotion: **False**.

{positive}

[Approved contract](../../../../docs/iterations/topology/iteration_10/03_plan.md) · [Implementation review](preflight.md) · [Independent closeout](closeout_review.md) · [Full scorecard](scorecard.json) · [Frozen configuration](contract.json) · [Saved merge audit](merge_stage_audit.md)

## Principal endpoints

Comparisons start from the same reused stage-1 coefficients. Original TOP-016 starts provide context only. Stage 1 was not replayed. Every new stage resets optimizer state identically for both arms; S trains only 0.5 GHz, F follows the cumulative schedule. All reported scores belong to predetermined retained endpoints.

| Case/arm/endpoint | Boundary mm | IoU | Refined 0.5-GHz error | Worst 1.5/2.5-GHz error | Original gates | Numerically qualified | New stage solves | Optimizer-stage outcome |
|---|---:|---:|---:|---:|---|---|---:|---|
{table}

[Endpoint quality figure](endpoint_quality.png) · [SVG](endpoint_quality.svg). The final predetermined stage 4 is the headline endpoint, even though central F stage 3 had slightly smaller boundary/evaluation errors. No best-stage selection was performed.

## Training exposure and stopping

Schedule exposure, bounded completion, numerical qualification, configured convergence and reconstruction quality are separate fields in the scorecard. Completed quota-limited stages do not establish stationarity. Scoring frequencies are excluded from training exposure.

| Case/arm/stage | Active GHz | Complete Jacobians | Candidate attempts | Accepted steps | Actual optimizer stop | Convergence | Unused quota |
|---|---|---:|---:|---:|---|---|---:|
{chr(10).join(exposure)}

## Merge representation audit

Fixed evaluation-only projections use the inherited truth-to-polar-angle-gauged Cartesian fitter at K9 and K17. The 16,384-sample procedure is predetermined; 32,768 samples check projection/distance stability, never select a better fit. These states never enter an inverse. A poor projection is not an approximation lower bound; a good projection is not recovery evidence.

| K | Benchmark boundary mm | Dense 16,384 mm | Dense 32,768 mm | Worst evaluation error | 128/256 qualified |
|---|---:|---:|---:|---:|---|
{chr(10).join(projections)}

The [saved merge stages](merge_stage_audit.md) retain the measured adverse inverse result: prediction deterioration at shared stage 1, geometric deterioration beginning at F stage 2. Audit capacity does not resolve that regression.

## Work and limits

New attempted/completed/failed frequency solves: **{report['work']['total_attempted']}/{report['work']['total_completed']}/{report['work']['total_failed']}**. Phase A: **{audit['work']['total_attempted']}/256** attempted. Each trial cap 7000 and each stage quota include endpoint scoring; unused quota is not transferred. Historical common-prefix costs are separate in the scorecard. At most two numerical workers, single-thread BLAS; summed worker time is not campaign elapsed time. See [campaign](campaign.json) and [environment](environment.json).

Last gradients carry exact state/objective/resolution associations. Interrupted derivative diagnostics may be partial; no terminal Jacobian was run solely for reporting. Exact frequency solves are counted; factorization/RHS counts are unavailable. Development evaluation frequencies never fit updates and do not establish generalization.

## Recorded obstructions

{obstruction_text}

The scorecard retains exact failed discrepancies and associations with rejected candidates and retained states. The two-star pair did not complete effective exposure to the whole schedule; these stops do not decide its frequency-recovery benefit. The measured central recovery is retained separately.

## Next decision

{decision} No successor, merge inverse, local control or suite was executed or authorized by this closeout.
'''
    (bundle/'README.md').write_text(text)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--merge-only',action='store_true')
    args=parser.parse_args()
    result=merge_audit(args.bundle.resolve()) if args.merge_only else summarize(args.bundle.resolve())
    print('merge audit rebuilt' if args.merge_only else result['outcome'])
