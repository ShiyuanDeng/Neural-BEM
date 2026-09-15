"""Write documentation only after the all-scene numerical and video work passes QA."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re

root=Path('/home/drdeng/Neural_SDF_BEM_AD')
out=Path((root/'experiments/top025/output_path.txt').read_text().strip())
read=lambda p:json.loads(p.read_text())
score=read(out/'scorecard.json');verification=read(out/'verification.json');videos=read(out/'video_manifest.json')
assert verification['status']=='PASS' and len(score['rows'])==12 and len(videos['outputs'])==13
assert score['all_scenes_attempted']
rows=score['rows'];work=score['work'];count=score['recovered_count'];relative=out.relative_to(root).as_posix()
date=datetime.now(timezone.utc).strftime('%Y-%m-%d')
successes=', '.join(row['scene'] for row in rows if row['recovered']) or 'none'
failures='\n'.join('- **'+row['scene']+'**: '+'; '.join(row['failure_labels'])+'.' for row in rows if not row['recovered']) or '- None.'
details=[];failure_sections=[]
for row in rows:
    if row['recovered']: continue
    path=out/'runs'/row['scene']/'result.json';raw=read(path) if path.exists() else {}
    continuation=raw.get('continuation',{});schedule=continuation.get('schedule',{})
    detail=raw.get('detail') or continuation.get('detail') or schedule.get('detail')
    if not detail:
        stages=schedule.get('stages',[])
        detail=stages[-1]['terminal'].get('reason') if stages else None
    details.append(dict(scene=row['scene'],recorded_detail=detail,reason=row.get('reason'),failure_labels=row['failure_labels']))
    section='- **'+row['scene']+'**: '+'; '.join(row['failure_labels'])+'.'
    if detail: section+='\n  Recorded stop detail: '+str(detail)+'.'
    failure_sections.append(section)
failures='\n'.join(failure_sections) or '- None.'
(out/'failure_details.json').write_text(json.dumps(details,indent=2)+'\n')
gallery=out/'README.md'
gallery.write_text(gallery.read_text().replace('## How to read the videos\n',
    '## Final scenes at a glance\n\n![Final accepted reconstructions against their targets](all_scenes.png)\n\n## How to read the videos\n',1))
with (out/'README.md').open('a') as stream:
    stream.write('\n## Where the unsuccessful cases stopped\n\n'+failures+'\n\nThese descriptions use the recorded stop and endpoint checks; they do not claim an unmeasured root cause.\n')
    stream.write('\nA [geometry-only replay](qa/handoff_geometry.json) explains the two ellipse/star handoff stops: both retained states pass at 64/128 nodes, but a component gap measures about 9.989 mm at 512 nodes, below the unchanged 10 mm clearance requirement. Their component radii exceed the 8 mm floor. This replay used zero physical solves and did not change the retained states or gates.\n')
    stream.write('\nWork accounting includes 1,512 handled geometry refusals and one call interrupted by the declared wall timer in the three-shape scene. That interruption is preserved in its [raw result](runs/far-three-shapes/result.json).\n')
    stream.write('\n## Coverage\n\nThis gallery covers all twelve scenes in the frozen v1 Cartesian Fourier automatic-topology benchmark. The measured implementation is the explicit Fourier recovery pipeline. Other solver families and the neural-SDF inverse method are outside this evaluation.\n')
(out/'closeout_review.md').write_text(f"""# TOP-025 owner closeout review

Completed {date}. Codex `/root`; owner review, no independent-agent review claimed.

**{count}/12 original scenes pass every recovery and numerical gate.**
Successful scenes: {successes}.

## Failed or incomplete scenes

{failures}

## Execution and validation

- The user explicitly requested current-code results and videos for all scenes.
  TOP-025 is a descriptive single-candidate evaluation; TOP-021's old conditional
  matched-comparison gate was not declared passed or bypassed in that code.
- Every scene was freshly initialized from the immutable v1 inputs. Current
  H topology, returned-count K17/K9 capacity and cumulative F used one fixed
  protocol. No diagnostic damping reset, best-iterate choice or scene-specific
  rescue was introduced. No shared solver/default or recovery gate changed.
- 86 source-bound pre-dispatch tests pass, including MP4 encoding. All
  {score['source_files']} measured Python files are archived and verified.
- Saved arrays replay every scored endpoint, accepted-step margin, trajectory,
  terminal gradient association and work ledger with zero new BIE calls.
  Retained geometry reporting is guarded by a zero-call ledger. Missing
  predictions and partial counters remain explicitly unavailable/lower bounds.
- {work['total_attempted_calls']:,} charged calls, {work['completed_solves']:,}
  completed systems, {work['failed_or_refused_calls']:,} failed/refused calls,
  including {work['geometry_refused_calls']:,} handled geometry refusals.
  Campaign elapsed {work['elapsed_seconds']/60:.2f} min, at most four BLAS-1
  numerical workers. Timing is descriptive. Exact commands/exits are preserved.
- Twelve scene videos plus one overview were rendered from saved accepted
  states. Every scene ends at its reported retained state; every saved accepted
  record appears at least once. No coefficient interpolation or new numerical
  solve was used. All MP4s pass ffprobe; final overlays and representative
  frames were visually checked. See `video_manifest.json` and `qa/`.

This completes the requested all-case visual inventory. It does not establish
causal improvement over old policies, generalization beyond these development
scenes, or production reliability. No corrective redesign or successor was run.
""")
iteration=root/'docs/iterations/topology/iteration_18';iteration.mkdir(exist_ok=True)
(iteration/'01_results.md').write_text(f"""# TOP-025 — latest integrated pipeline across all twelve scenes

Completed {date} under the user's request for current-code videos of successes
and failures and the [iteration-17 plan](../iteration_17/03_plan.md).

**{count}/12 fresh scenes pass every original recovery and numerical gate.**
Successful scenes: {successes}.

[All-scene gallery and scores](../../../../{relative}/README.md) ·
[Overview video](../../../../{relative}/videos/all_scenes.mp4) ·
[Final contact sheet](../../../../{relative}/all_scenes.png).

## What still fails

{failures}

## Scope and verification

One fixed current H → cumulative-F pipeline, original starts and observations,
256/512 continuation, and returned-count K17/K9 capacity were used throughout.
No saved optimized starts, supplied count, case-specific rescue or damping reset.
TOP-025 was explicitly authorized as an all-case evaluation despite TOP-024's
negative result; TOP-021's conditional matched comparison remains undispatched.

86 pre-dispatch tests pass. All twelve rows, source/input hashes, saved
predictions, events, gradients, acceptance margins and work replay are verified.
New work: {work['total_attempted_calls']:,} charged calls / {work['completed_solves']:,}
completed systems. Elapsed {work['elapsed_seconds']/60:.2f} min with up to four
BLAS-1 numerical workers. Twelve per-scene videos and one overview contain only
saved accepted states and pass encoding/provenance checks.

This is a completed visual performance inventory, not a matched comparison or
promotion decision. Review the scene-level evidence before choosing further work.
""")

plan=root/'docs/iterations/topology/iteration_17/03_plan.md';text=plan.read_text()
text=text.replace('**Execution:** IN PROGRESS.','**Execution:** COMPLETE.')
text+=f'\n## Closeout\n\n[{out.name}](../../../../{relative}/README.md):\n{count}/12 scenes pass. All twelve scenes were attempted; videos and verification\nare complete. Results open [iteration 18](../iteration_18/01_results.md).\n'
plan.write_text(text)

def insert_after_title(path,content):
    text=path.read_text();first,rest=text.split('\n',1);path.write_text(first+'\n\n'+content.strip()+'\n'+rest)

insert_after_title(root/'README.md',f'**Latest all-scene results:** [TOP-025 video gallery]({relative}/README.md) · '
    f'[Overview video]({relative}/videos/all_scenes.mp4) · [Final scenes]({relative}/all_scenes.png). '
    f'Fresh current-pipeline runs: **{count}/12 pass all gates**. Every success, failure and work stop is included.')
insert_after_title(root/'results/README.md',f'**Latest Cartesian topology evaluation:** '
    f'[All twelve scenes and videos](validation/topology/{out.name}/README.md), '
    f'**{count}/12 passing**, using the frozen current integrated pipeline and original starts.')
insert_after_title(root/'results/inverse/cartesian_fourier/README.md',f'**Current all-scene visual review:** '
    f'[TOP-025 gallery](../../validation/topology/{out.name}/README.md) — {count}/12 fresh scenes pass; '
    'one video per scene, overview, complete failure reasons and work accounting.')
insert_after_title(root/'docs/README.md',f'**Latest topology results:** [TOP-025 all-scene videos](../{relative}/README.md) '
    f'and [iteration 18](iterations/topology/iteration_18/01_results.md): {count}/12 scenes pass all gates.')

index=root/'results/validation/topology/README.md';text=index.read_text()
text=text.replace('|---|---|','|---|---|\n'+f'| [TOP-025 all-scene gallery]({out.name}/README.md) | '
    f'{count}/12 fresh scenes pass the current H → cumulative-F protocol; twelve scene videos plus overview; all failures retained |',1)
index.write_text(text)

handoff=root/'docs/iterations/topology/README.md';text=handoff.read_text()
text=re.sub(r'^\| Active iteration \|.*$', '| Active iteration | [Iteration 18 results](iteration_18/01_results.md); iteration 17 holds the executed TOP-025 plan |',text,flags=re.M)
text=re.sub(r'^\| Stage \|.*$',f'| Stage | TOP-025 COMPLETE: all twelve fresh scenes attempted; {count}/12 pass; video gallery verified |',text,flags=re.M)
text=re.sub(r'^\| Next expected action \|.*$','| Next expected action | Review the all-scene inventory with the user; no corrective redesign or successor is included |',text,flags=re.M)
text=re.sub(r'^\| Evidence interpretation \|.*$',f'| Evidence interpretation | TOP-025 freshly measures all twelve scenes: {count}/12 pass the original recovery and numerical gates. The descriptive inventory is complete; automatic reliability and the conditional matched comparison remain unqualified |',text,flags=re.M)
text=text.replace('TOP-020/022/023/024: Codex','TOP-020/022/023/024/025: Codex')
text=text.replace('## Latest measurement\n',f'## Latest measurement\n\n[TOP-025](iteration_18/01_results.md) completes the user-requested all-case visual\nevaluation: **{count}/12 fresh scenes pass**, with every failure retained.\n[Video gallery](../../../{relative}/README.md) includes twelve scene MP4s, an\noverview, a final contact sheet and exact scores. This is a single-candidate\nmeasurement, not a matched improvement claim.\n',1)
text=text.replace('**Restart action:** read this handoff, [iteration 17](iteration_17/01_results.md),\nthe completed [TOP-024 plan](iteration_16/03_plan.md)',
    '**Restart action:** read this handoff, [iteration 18](iteration_18/01_results.md),\nthe completed [TOP-025 plan](iteration_17/03_plan.md)')
text=text.replace('do not replay completed TOP-019/020/022/023/024.','do not replay completed TOP-019/020/022/023/024/025.')
text=text.replace('1. This handoff and [the latest iteration-17 results](iteration_17/01_results.md).',
    '1. This handoff and [the latest iteration-18 results](iteration_18/01_results.md).')
text+=f'\n## All-scene evaluation update — {date}\n\nThe user requested the full current-code visual inventory despite the earlier\nfocused failure. TOP-025 completes that request with {count}/12 passing scenes.\nThe result does not retrospectively release TOP-021 or erase the focused\nfailures. The [gallery](../../../{relative}/README.md) is the current scene-level\nperformance reference; the broader reliability question remains evidence-based.\n'
handoff.write_text(text)

shared=root/'docs/iterations/README.md';text=shared.read_text()
start=text.index('Topology’s latest executed closeout is ');end=text.index('On 2026-09-15 the user authorized finishing the',start)
text=text[:start]+f'Topology’s latest executed closeout is [iteration 18](topology/iteration_18/01_results.md):\nTOP-025 completes the user-requested current-code all-case video inventory.\n**{count}/12 scenes pass all gates**; all twelve fresh cases and their failures\nare retained. Its [plan](topology/iteration_17/03_plan.md) is COMPLETE.\n'+text[end:]
shared.write_text(text)

catalog=root/'results/catalog.csv'
with catalog.open(newline='') as stream:reader=csv.DictReader(stream);entries=list(reader);fields=reader.fieldnames
assert not any(row['run_id']==out.name for row in entries)
template=next(row for row in entries if row['run_id'].startswith('TOP-022-'));new=[]
for row in rows:
    item=template.copy();errors=row['prediction_errors'];capacity=row['capacity'] or {}
    item.update(run_id=out.name,row_id=out.name+'::'+row['scene']+'::F',original_path=relative,current_path=relative,
        date_label=date,date_source='UTC suite closeout date; manifest records preparation time',scene_target=row['scene'],
        pipeline='cartesian_fourier_automatic_topology_and_continuation',
        accepted_geometry='automatic polar-gauge Cartesian Fourier; returned-count K17/K9 capacity; 256/512 continuation',
        derivative_optimizer='H automatic controller; existing feasible FD LM; cumulative four-frequency stages',arm_or_policy='H then cumulative F',
        initialization='immutable original v1 initialization for '+row['scene']+'; no supplied count or optimized checkpoint',
        execution_outcome=row['status'],recovery_outcome='PASS' if row['recovered'] else 'FAIL / incomplete',
        representation_outcome='capacity rule selected from returned count; not truth',stop_reason=row.get('reason') or row['convergence'],
        training_relative_l2='' if errors is None else errors[0],holdout_relative_l2='' if errors is None else max(errors[4:]),
        geometry_error_m='' if row['boundary_mm'] is None else row['boundary_mm']/1000,
        field_metric_scope='prescribed retained endpoint; predictions unavailable after unscored hard stops',
        takeaway=('All original gates pass.' if row['recovered'] else '; '.join(row['failure_labels']))+f" {row['attempted_calls']} charged calls; lower bound: {row['work_is_lower_bound']}.",
        implication_for_strict_mlp_method_b='Explicit automatic development-case evidence; no neural recovery claim.',
        source_metadata=relative+'/manifest.json; '+relative+'/scorecard.json; '+relative+'/video_manifest.json',
        source_revision=score['source_revision']+' + frozen measured sources',
        recorded_command='experiments/top025/run.py campaign --bundle '+relative+' --validation experiments/top025/validation.json',
        rerun_disposition='preserve all twelve outcomes; no corrective successor in this request')
    new.append(item)
with catalog.open('a',newline='') as stream:csv.DictWriter(stream,fieldnames=fields).writerows(new)
p=root/'results/README.md';text=p.read_text();text=re.sub(r'contains \*\*\d+ rows\*\*',f'contains **{len(entries)+len(new)} rows**',text);p.write_text(text)
print(json.dumps(dict(outcome=f'{count}/12 recovered',bundle=str(out),catalog_rows_added=len(new))))
