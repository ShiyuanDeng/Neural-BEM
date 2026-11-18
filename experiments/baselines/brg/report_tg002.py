"""Write the provisional baseline report from saved receipts, without solver calls."""
import datetime
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/brg/tg002_shapes/2026-11-17';DOC=ROOT/'docs/iterations/brg_adaptation/04_run_brg_on_tg002_shapes'

def main():
    state=json.loads((BASE/'campaign.json').read_text());rows=[];details=[]
    for case in state['cases']:
        p=BASE/case/'metrics.json'
        if not p.exists():continue
        m=json.loads(p.read_text());attempts=[json.loads(p.read_text()) for p in sorted((BASE/case).glob('attempt_*.json'))]
        wall=sum(a.get('case_wall_seconds',a.get('wall_seconds',0)) for a in attempts)
        residual=m['max_final_curve_residual'];res='not saved' if residual is None else f'{residual:.6g}'
        rows.append(f"| {case} | {m['status']} | {m['completed_frequencies']}/37 | {m['area_error']:.8g} | {res} | {m['data_seconds']:.2f} | {m['inverse_seconds']:.2f} | {m['residual_check_seconds']:.2f} | {m['scoring_seconds']:.2f} | {wall:.2f} |")
        details.append((case,m,attempts,wall))
    text=f'''# Run BRG on TG-002 shapes: provisional baseline results

## Status and ownership

Campaign started {state['started']}; {len(details)}/20 cases have saved scores.
Queue state: `{state['status']}`; last update {state.get('ended',state.get('updated','not recorded'))}.
All data and results here are **provisional BRG-forward data**. The BEM side
owns generating and freezing the shared plane-wave data. These are TG-002
shapes with BRG-style observations, not the sealed TG-002 measurements.
No BEM forward, BEM fit or solver edit was performed in this activity.

The [approved plan](plan.md) records the pilot rule and all choices. The
[single data request](../../../../results/brg/tg002_shapes/2026-11-17/data_request.json)
contains the 37 exact k values, layouts, units, signs, eta values and all ten
true coefficient arrays with source and coefficient hashes. The BEM-side
cross-solver checks and inverse sections remain unexecuted here.

## Actual settings and scoring

Pinned upstream `bda24bddbf4562497280b671bc174ef891b47c6b`, approved patches
03/04, seven-argument RLA call. No new upstream patch. MATLAB R2026a,
8 compute threads per process, with concurrent CSI fits. Times are indicative.
Known eta 0.5 or 4, equal density, unit-amplitude plane waves, finite-radius
scattered fields, negative time convention and outgoing Hankel first kind.

37 frequencies preserve TG-002's 19 labels and add midpoints: exterior
k=0.834234519 to 8.342345186. Each has floor(10k) directions and receivers
on radius 10. One centred unit-disk start; lengths are divided by 65 mm.
Frozen target offsets and rotations remain. Data use 100 exterior points
per wavelength and inversion 70, with public resolution behavior.

The shipped curvature values 0.1 / minimum band 20, better-of-GN/SD,
Gaussian filter, 50 iterations and 1e-5 residual/update stops are unchanged.
No added zero-gradient guard or tuning run. Every inverse frequency saves
its curve, residual history, iterations, exit flag, time and exact state.

Scoring imports `experiments.comparison.scoring` protocol version 1 unchanged.
All components are retained; no alignment is fitted. Returned uniform-
parameter nodes define a Fourier interpolant without truncation or smoothing.
Coordinates return to the benchmark's 50 mm units; truth uses 16,384 samples,
with its existing 201-by-201 material grid and boundary scoring functions.
The table's area error is the raw symmetric-difference area divided by true
area (not percent). Signed susceptibility and known-contrast scores are saved.

Residuals are recomputed on the returned curve at its own saved resolution
for all 37 frequencies, using BRG's forward. The table gives their maximum,
not the history of curves from earlier frequencies. The unchanged clean
residual limit is 0.003; added midpoints are never passed as sealed labels.
This final-curve evaluation has its own time column. No BEM solve is involved.

## Results

| Case | State | Frequencies | Raw area error | Max final residual | Data s | Inverse s | Residual check s | Score s | Case wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'\n\n'
    if details and details[0][0]=='asymmetric__c4':
        _,m,a,w=details[0]
        text+=f'''## Timed pilot and forecast

Asymmetric eta=4: data {m['data_seconds']:.2f} s, inversion
{m['inverse_seconds']:.2f} s, final residual evaluation {m['residual_check_seconds']:.2f} s,
scoring/figure {m['scoring_seconds']:.2f} s; complete case {w:.2f} s.
The pilot {'passes' if w<=900 else 'exceeds'} the 900-second continuation rule.
Twenty times its measured phase costs gives data {20*m['data_seconds']/60:.2f} min,
inverse {20*m['inverse_seconds']/60:.2f} min and residual checks
{20*m['residual_check_seconds']/60:.2f} min; aggregate case wall forecast
{20*w/60:.2f} min before parallelism. This is a one-shape estimate, not a
promise for thin strokes or deep concavities. No case is rerun to tune it.

'''
    if len(details)>1:
        aggregate=sum(d[3] for d in details)
        text+=f"Completed-case aggregate wall time: {aggregate/60:.2f} min across {len(details)} cases.\n"
        if len(details)<len(state['cases']):
            text+=f"A running-mean projection for all 20 is {aggregate/len(details)*20/60:.2f} min before parallelism; the still-unrun difficult shapes make this uncertain.\n"
        text+='\n'
    if state.get('ended'):
        elapsed=(datetime.datetime.fromisoformat(state['ended'])-datetime.datetime.fromisoformat(state['started'])).total_seconds()
        text+=f"Actual queue elapsed time: {elapsed/60:.2f} min; ended {state['ended']}. The campaign limit was 240 min.\n\n"
        if state.get('stop_reason'):text+=f"Queue stop reason: {state['stop_reason']}. Unfinished cases remain unfinished.\n\n"
    resources=BASE/'resources.jsonl'
    if resources.exists():
        samples=[json.loads(l) for l in resources.read_text().splitlines()]
        text+=f"Memory: minimum observed available {min(s['available_gib'] for s in samples):.2f} GiB; maximum active BRG workers {max(len(s['active']) for s in samples)}. The required reserve is 14 GB. Start/end CSI/MATLAB overlap is retained in each attempt.\n\n"
    text+='## Checks, failures and evidence\n\n'
    checks=[]
    for case,m,attempts,w in details:
        p=BASE/case/'saved_output_check.json'
        if p.exists():checks.append(json.loads(p.read_text()))
    if checks:
        issues=[f"{c['case']}: {issue}" for c in checks for issue in c['issues']]
        text+=f"Saved-output checks cover {len(checks)}/{len(details)} scored cases. They read existing curves and histories, file counts, receipts, logs and manifest sizes; no inversion or scoring was repeated. Each receipt is saved as `saved_output_check.json` beside its metrics.\n\n"
        text+=('Issues: '+'; '.join(issues) if issues else 'No saved-output check failed.')+'\n\n'
    for case,m,attempts,w in details:
        text+=f"- {case}: maximum data-geometry resampling point error {m['geometry_resampling_max_error']:.6g} BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/{case}/metrics.json), [curve](figures/{case}.png).\n"
        for a in attempts:
            if a.get('supervisor_failure'):text+=f"  Wrapper failure: {a['supervisor_failure']} See `supervisor_failure.log` in this case folder.\n"
            if a.get('returncode') or a.get('scoring_failure'):text+=f"  Attempt {a['started']}: return code {a.get('returncode')}; {a.get('scoring_failure','')}; log `{a['log']}`.\n"
    text+='''
The frozen-input geometry checks verify source hashes, agreement with the
benchmark's scene definitions, positive orientation, closure, simple curves,
nonzero speed and the 65 mm start. Data resampling errors are measured against
the exact coefficients at the public resampler's returned parameters.

Compact results are committed by batch. Bulk fields, continuation states and
logs remain ignored locally with reproduction commands and SHA-256 manifests.
See [campaign receipt](../../../../results/brg/tg002_shapes/2026-11-17/campaign.json)
and [geometry checks](../../../../results/brg/tg002_shapes/2026-11-17/geometry_checks.json).

## Frozen-data replacement and handoff

Frozen BEM-side observations do not yet exist and were not compared here.
The agreed relative complex-field tolerance is max(1e-5, ten times measured
BRG refinement error); refinement error above 1e-4 returns to the coordinator.
Compare every frequency after units/order/signs are matched. Rerun only cases
whose fields differ beyond that threshold. Preserve these provisional results.
Both BEM rows and cross-solver checks belong to the separate BEM coordinator.
Paper k=30 resumes remain deferred while CSI runs overnight.
'''
    report=DOC/'results.md'
    existing=report.read_text() if report.exists() else ''
    if '## State at handoff' in existing:
        handoff=existing[existing.index('## State at handoff'):existing.index('## Status and ownership')]
        text=text.replace('## Status and ownership',handoff+'## Status and ownership',1)
    report.write_text(text)

if __name__=='__main__':main()
