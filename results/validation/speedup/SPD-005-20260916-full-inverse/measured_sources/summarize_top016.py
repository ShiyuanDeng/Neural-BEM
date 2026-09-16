"""Rebuild TOP-016 closeout from artifacts, with zero physical forward solves."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path


def read(path):return json.loads(Path(path).read_text())
def write(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
SCENES=('far-two-stars','central-ellipse-star','merge')


def summarize(bundle):
    root=Path(__file__).resolve().parent
    phase0=read(bundle/'phase0/preflight.json');screen=read(bundle/'phase1/sensitivity.json')
    if screen['status'] not in ('OBSTRUCTION','SCREEN_PASS'):
        raise ValueError('cannot close a running or erroneous screen')
    main=[];local=[]
    if screen['status']=='SCREEN_PASS':
        main=[read(bundle/'runs'/f'{a}-{s}'/'metrics.json') for s in SCENES for a in ('S','F')]
        if any(r['status'] in ('IN_PROGRESS','IMPLEMENTATION_ERROR') for r in main):
            raise ValueError('main trial still running or needs implementation repair')
        eligible=not any(r.get('final',{}).get('original_gates_pass',False) for r in main if r['scene'] in SCENES[:2])
        if eligible:
            local=[read(bundle/'runs'/f'local-{a}-far-two-stars'/'metrics.json') for a in ('S','F')]
            if any(r['status'] in ('IN_PROGRESS','IMPLEMENTATION_ERROR') for r in local):
                raise ValueError('eligible local control still running or erroneous')
    else:eligible=False
    work_rows=[phase0['work'],screen['work'],*[r['work'] for r in main+local]]
    attempted=Counter();completed=Counter();failed=Counter();calls=Counter()
    for w in work_rows:
        attempted.update(w['attempted']);completed.update(w['completed']);failed.update(w['failed']);calls.update(w.get('calls',{}))
    phase01=phase0['work']['total_attempted']+screen['work']['total_attempted']
    assert phase01<=5000
    assert phase0['work']['active_wall_seconds']+screen['work']['active_wall_seconds']<=1200.
    for trial in main+local:
        assert trial['work']['total_attempted']<=trial['work']['solve_cap']
        assert trial['work']['active_wall_seconds']<=trial['work']['wall_ceiling_seconds']
        starts=[stage['terminal']['work']['total_attempted']-stage['terminal']['work']['stage_attempted']
                for stage in trial['stages']]
        ends=starts[1:]+[trial['work']['total_attempted']]
        trial['derived_stage_work_including_endpoint']=[]
        for stage,start,end in zip(trial['stages'],starts,ends):
            count=end-start;cap=stage['terminal']['work']['stage_cap']
            assert count<=cap
            trial['derived_stage_work_including_endpoint'].append(dict(stage=stage['stage'],attempted=count,cap=cap))
    work=dict(attempted=dict(attempted),completed=dict(completed),failed=dict(failed),calls=dict(calls),
        total_attempted=sum(attempted.values()),total_completed=sum(completed.values()),total_failed=sum(failed.values()),
        phase01_attempted=phase01,phase01_active_seconds=phase0['work']['active_wall_seconds']+screen['work']['active_wall_seconds'],
        sum_active_trial_seconds=sum(r['work']['active_wall_seconds'] for r in main+local),
        sum_active_worker_seconds=sum(w['active_wall_seconds'] for w in work_rows),
        screen_concurrency=1,pilot_concurrency=2,blas_threads=1)
    by={(r['scene'],r['arm']):r for r in main}
    promotable=False
    criteria={}
    if main and all(r['status']=='COMPLETE' for r in main):
        for scene in SCENES[:2]:
            f=by[scene,'F'];s=by[scene,'S'];fi=f['initial'];ff=f['final'];sf=s['final']
            bi=fi['geometry']['maximum_matched_hausdorff_m'];bf=ff['geometry']['maximum_matched_hausdorff_m'];bs=sf['geometry']['maximum_matched_hausdorff_m']
            criteria[scene]=dict(boundary_improvement=1-bf/bi,F_advantage_over_S=1-bf/bs,
                not_worse_than_S=bf<=bs,IoU_not_worse=ff['geometry']['union_iou']>=fi['geometry']['union_iou'],
                evaluation_improvement=1-ff['maximum_evaluation_error']/fi['maximum_evaluation_error'],
                original_gates_pass=ff['original_gates_pass'],numerically_qualified=ff['numerically_qualified'])
        merge=by['merge','F']['final']['gates'];merge_ok=merge['count'] and merge['boundary'] and merge['iou']
        promotable=(all(c['boundary_improvement']>=.3 and c['not_worse_than_S'] and c['IoU_not_worse'] and
                        c['evaluation_improvement']>=.2 and c['numerically_qualified'] for c in criteria.values()) and
                    any(c['F_advantage_over_S']>=.2 for c in criteria.values()) and
                    any(c['original_gates_pass'] for c in criteria.values()) and merge_ok)
    if screen['status']=='OBSTRUCTION':
        outcome='preflight_or_screen_obstruction';reason=screen['reason']
        decision='Close this protocol at its measured screen/numerical obstruction; decide whether a separately scoped diagnostic is warranted.'
    elif any(r['status']!='COMPLETE' for r in main):
        outcome='inconclusive_within_declared_budgets_or_numerics';reason='At least one main arm did not complete its four-stage contract.'
        decision='Review whether a revised fixed-topology contract is warranted, addressing both the merge-control regression and the stage-1 budget obstruction before committing more compute.'
    elif promotable:
        outcome='F_candidate_for_separate_qualification';reason='All predeclared F promotion criteria passed.'
        decision='Review one separately scoped matched twelve-scene qualification; do not run it under TOP-016.'
    else:
        outcome='completed_pilot_not_promoted';reason='The completed pilot did not satisfy every predeclared F promotion criterion.'
        decision='Use the terminal and local-control evidence to select one separately scoped continuous-inverse diagnostic; do not automatically implement a new optimizer.'
    adverse_merge=None
    if main and by['merge','F']['status']=='COMPLETE':
        m=by['merge','F'];fi=m['initial'];ff=m['final']
        adverse_merge=dict(new_boundary_gate_failure=fi['gates']['boundary'] and not ff['gates']['boundary'],
            boundary_initial_mm=1000*fi['geometry']['maximum_matched_hausdorff_m'],
            boundary_final_mm=1000*ff['geometry']['maximum_matched_hausdorff_m'],
            evaluation_initial=fi['maximum_evaluation_error'],evaluation_final=ff['maximum_evaluation_error'])
    report=dict(experiment='TOP-016',status='COMPLETE',outcome=outcome,reason=reason,decision=decision,
        pilot_released=screen['status']=='SCREEN_PASS',F_promotable=bool(promotable),promotion_criteria=criteria,work=work,
        measured_merge_regression=adverse_merge,
        diagnostic_limitations=['Rejected-gain logs cover only production-decreasing candidates reaching refined validation.',
            'Full feasibility rejection counts were not preserved; interrupted one-sided/unresolved totals are unavailable.',
            'Capped endpoints lack terminal gradients; earlier terminal_gradient.json files are last measured pre-terminal gradients.'],
        information_screen={s:r.get('gate',dict(passed=None)) for s,r in screen.get('scenes',{}).items()},
        main_trials=main,local_trials=local,local_control_eligible=eligible,
        missing_trials=[] if main else [dict(scene=s,arm=a,status='NOT_RUN') for s in SCENES for a in ('S','F')])
    write(bundle/'pilot_metrics.json',report);write(bundle/'sensitivity.json',screen)
    manifest=read(bundle/'phase0/manifest.json')
    manifest['phase0_source_sha256']=manifest.pop('source_sha256')
    manifest['final_source_sha256']={str(p.relative_to(root)):digest(p) for p in
        [*sorted((root/'solvers').rglob('*.py')),*sorted(root.glob('*top016*.py')),
         root/'config/topology_TOP016_fixed_topology_pilot.json']}
    manifest['inputs']=phase0['inputs'];manifest['environment']=read(bundle/'environment.json')
    manifest['phase0_manifest_sha256']=digest(bundle/'phase0/manifest.json')
    manifest['phase1_manifest_sha256']=digest(bundle/'phase1/manifest.json')
    write(bundle/'manifest.json',manifest)
    rows=[]
    for r in main+local:
        initial=r.get('initial',{});final=r.get('final',{})
        label=('local ' if r['truth_assisted_local_control'] else '')+r['scene']+' '+r['arm']
        def mm(score):
            v=score.get('geometry',{}).get('maximum_matched_hausdorff_m');return 'unavailable' if v is None else f'{1000*v:.5g}'
        def number(score,key):
            v=score.get(key);return 'unavailable' if v is None else f'{v:.5g}'
        iou=final.get('geometry',{}).get('union_iou')
        rows.append(f"| {label} | {len(r['stages'])}/4 | {r['status']} | {mm(initial)} → {mm(final)} | {'unavailable' if iou is None else f'{iou:.5g}'} | {number(initial,'maximum_evaluation_error')} → {number(final,'maximum_evaluation_error')} | {r['work']['total_attempted']} |")
    table='\n'.join(rows) if rows else '| No pilot released | — | NOT_RUN | — | — | — | 0 |'
    info_rows=[]
    for name,r in screen.get('scenes',{}).items():
        g=r.get('gate',{});info_rows.append(f"| {name} | {g.get('usable','unmeasured')} | {g.get('median_gain','unmeasured')} | {g.get('passed','unmeasured')} |")
    info='\n'.join(info_rows)
    total=work['total_attempted']
    text=f'''# TOP-016 — fixed-topology recovery, bounded preflight and paired pilot

**{outcome.replace('_',' ')}.** {reason} F promotion: **{promotable}**.

[Approved plan](../../../../docs/iterations/topology/iteration_09/03_plan.md) · [Preflight and independent review](preflight.md) · [Frozen contract](contract.json) · [Screen](sensitivity.json) · [Complete scorecard and work](pilot_metrics.json)

## Information and numerical gates

Original 24-pair observation files and prescribed retained states were preserved byte-for-byte. K=9 padding preserved IDs, curves and predictions. The retained gauge-constrained Cartesian chart approximated the principal truths to **0.001675 mm** and **0.039482 mm**, below 0.1 mm. The smallest qualifying common training pair was **128/256 nodes**. New-frequency oracle and frozen-pair evaluation-geometry convergence checks passed. Details: [Phase 0](phase0/preflight.json) and [Phase 1](phase1/sensitivity.json).

The weak directions were fixed from the 0.5-GHz reduced Jacobian, scaled by arclength-weighted RMS normal displacement, then measured at both signs, both amplitudes, and both resolutions. Gains use base-subtracted data changes and equal per-frequency normalization.

| Principal case | Usable directions | Median F/S gain | Gate passed |
|---|---:|---:|---|
{info}

The screen establishes useful added local sensitivity under this protocol. It does not establish reconstruction success.

## Paired pilot and bounded controls

| Trial | Stages reached | Status | Boundary error, initial → last accepted (mm) | Final IoU | Worst evaluation error, initial → final | Frequency solves |
|---|---:|---|---:|---:|---:|---:|
{table}

Stage IDs, accepted coefficients, per-frequency errors, aggregate objectives, measured gradients, actual stops and refined-validation decisions are retained under [runs](runs/). These rows describe the final **retained** endpoint, including budget-limited ones. A budget-limited endpoint is not a completed negative reconstruction experiment. The 1.5/2.5-GHz data remained unfitted development evaluation data, and endpoint scores never selected training updates, directions, restarts or stages.

The principal S/F pairs stopped during the shared 0.5-GHz first stage, before the acquisitions diverged. Their equal endpoints cannot establish a frequency-continuation advantage or failure. The completed F-merge control **does** establish a regression for that case: 0.554 → 1.108 mm creates a new boundary gate failure, and worst evaluation error rises from 0.09398 to 0.16795. This independently prevents promotion.

The local rows, if present, use only the prescribed truth representation translated by (+2 mm, −1 mm). They are truth-assisted local controls and cannot count as automatic recovery. The archived machine-readable `recovered` semantics and v1/v2 benchmarks were not changed.

## Work, implementation and limitations

**{total:,} attempted frequency solves; {work['total_completed']:,} completed; {work['total_failed']} failed.** Phases 0/1: **{phase01:,} solves / {work['phase01_active_seconds']:.2f} s**, below 5,000/1,200. Sum of active pilot/control worker times: **{work['sum_active_trial_seconds']:.2f} s**; concurrent worker times are not end-to-end elapsed time. All per-trial/stage work ceilings are verified from artifacts. Phase 0/1 used one worker; pilot/control used at most two, each with single-thread BLAS. [Hardware/environment](environment.json).

The only solver-side source changes are opt-in fixed-topology optimizer hooks for independent loss-change stopping, candidate validation, batch reservations, checkpointing before Jacobians and cache accounting. LM equations and defaults remain unchanged. Candidate acceptance uses both-resolution decreases and the factor-5 disagreement allowance. Runtime resolution failures stop a trial. The tests include exact comparison with the archived default trajectory; all focused tests use mocked physical forwards or geometry only. [Tests](pilot_tests.log). The [independent closeout review](closeout_review.md) verified source/input hashes, paired coefficients, stage work including endpoint scoring, and wall ceilings, with zero new physical solves.

Diagnostics have explicit limits: rejected-gain logs cover only production-decreasing candidates that reached refined validation, not every rejected production trial. Full feasibility rejection counts were not preserved; interrupted runs also lack complete one-sided/unresolved column totals. A capped endpoint's `terminal.json` correctly records its gradient as unavailable. An older `terminal_gradient.json` is the **last measured pre-terminal gradient**, not endpoint stationarity evidence; its association is documented in [gradient associations](gradient_associations.json). These gaps do not invalidate retained states, scores or exact physical-solve counts, and no completed trial was repeated to fill them.

No topology policy, physical BIE solver, representation chart, original observations or historical result bundle was modified. No full twelve-scene suite was run. This experiment does not establish global identifiability, a unique failure cause, or that frequency diversity succeeds or fails outside the measured scope.

## Reproduction and summary rebuild

[Commands](commands.md), manifests and per-worker logs preserve execution provenance. The Phase-0 driver and pre-hook optimizer source are archived alongside their evidence. The final source hashes and original producing revision are in [manifest.json](manifest.json).

Rebuild this report and the full scorecard **without rerunning an inverse or forward**:

```bash
python summarize_top016.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology
```

Fresh numerical reruns must use fresh directories and the approved scripts with the recorded single-thread environment. Do not repeat completed runs merely to regenerate a report.

## Single next decision

{decision} TOP-016 is closed; no successor cycle is automatically executed. Validated changes are committed locally on `track/topology-TOP-016`; push and merge require a separate user instruction.
'''
    (bundle/'README.md').write_text(text)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    report=summarize(parser.parse_args().bundle.resolve())
    print(json.dumps({k:report[k] for k in ('outcome','reason','decision','work')},indent=2))
