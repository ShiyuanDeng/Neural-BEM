"""Write a cumulative report from completed case receipts; no solver work."""
import json
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/brg/paper_examples/2026-11-17'
DOC=ROOT/'docs/iterations/brg_adaptation/02_rebuild_paper_examples/results.md'
CASES=['glider_033','glider_10','star_full','star_limited','cavity_09','cavity_2']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--max-k',type=int,default=30);args=parser.parse_args()
    target=args.max_k;suffix='' if target==30 else f'_k{target}'
    expected=round((target-1)*4)+1
    choice_path=BASE/'curvature_choice.json'
    choice=json.loads(choice_path.read_text()) if choice_path.exists() else None
    entries=[]
    for case in CASES:
        for variant in (['shipped','default'] if target==30 else ['shipped']):
            path=BASE/case/variant/f'metrics{suffix}.json'
            if path.exists(): entries.append(json.loads(path.read_text()))
    completed={r['case'] for r in entries if r['status'].startswith('complete')}
    rows=[]
    for r in entries:
        f=r['final']; rows.append(f"| {r['case']} / {r['curvature']} | {r['frequencies']}/{expected} | {f['k']:g} | {f['relative_area_error']*100:.6g}% | {f['residual']:.6g} | {r['iterations']} | {r['data_seconds']/60:.2f} | {r['inverse_seconds']/60:.2f} | {r['attempts_wall_seconds']/60:.2f} |")
    text=f'''# Rebuild the paper's single-component examples: results

## Status

Campaign started 17 November 2026. {len(completed)}/6 cases complete through k={target}.
This report is updated after each run. The full case budget is four hours,
including data and all attempts; the optional glider alternative shares it.
These are rebuilt paper cases, distinct from activity 01's shipped example.

## Actual settings and provenance

The [plan](plan.md) records the coordinator's decisions and all differences
between paper prose and public code. All current endpoints use k=1:0.25:{target}, known eta,
equal density, unit-amplitude plane waves and finite-radius scattered fields.
Full tables have floor(10k) directions and receivers at radius 10; the
limited star has 10 directions and 200 receivers. No noise or extra starts.

Data use 100 exterior points per wavelength and inversion uses 70, with
public frequency-start behavior. At eta=10 the corresponding interior
counts are 31.62 and 22.14; at eta=2 they are 70.71 and 49.50.
The public better-of-GN/SD option, Gaussian filter, 50-iteration limit and
1e-5 residual/update stops are retained. Initial curve: public unit disk.
No zero-gradient guard or added frequency-start resampling was introduced.
Area scores compare the fixed 2,048-point truth polygon with each saved
inverse curve, without an extra resampling of the inverse endpoint.

MATLAB R2026a runs at 8 compute threads, set only in the wrapper. The
activity 01 dense-solve check measured a 3.68-fold improvement over one
thread. CSI may overlap; start/end MATLAB process lists are in every attempt
receipt. An observed overlap during glider 0.33 data generation is recorded
separately. All times here are indicative, not clean-machine comparisons.

Pinned upstream: `bda24bddbf4562497280b671bc174ef891b47c6b`.
Approved patches 03 and 04 preserve transmission derivative fields and
update interior k with exterior k. No new upstream change was needed for
these runs. The wrapper uses the current seven-argument RLA call.

## Shape recovery

Glider: exact radial coefficients from section 4.1, recorded in the plan.
Star and cavity: **recovered from the paper's figure files**, not claimed
to be the authors' absent original analytic curves. Both were extracted from
solid vector paths in two obstacle-solver panels and mapped with axis ticks.
No pixels were traced and no shipped cavity was substituted.

| Shape | Cross-panel maximum | Fourier band | Fit RMS at vector points | Maximum fit-to-polyline distance |
|---|---:|---:|---:|---:|
| Star | 1.060e-4 | 35 | 1.751e-4 | 5.594e-4 |
| Cavity | 9.154e-5 | 100 | 1.596e-5 | 1.424e-4 |

Errors are in data-coordinate units. Conservative recovered-geometry
accuracy is about 6e-4 for the star and 2e-4 for the cavity, relative to the
vector centerlines. This uncertainty limits comparison with the paper's
original experiment. It does not excuse a BEM/BRG mismatch on the same
frozen recovered shape.

[Star overlay](figures/star_vector_recovery.png),
[cavity overlay](figures/cavity_vector_recovery.png), and
[vector evidence](../../../../results/brg/paper_examples/2026-11-17/shapes/)
include coefficients, both panels, calibration, path indices and hashes.

## Outcomes

| Case / curvature | Frequencies | Last k | Relative area error | Field residual | Iterations | Data min | Inverse min | Process min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'\n\n'
    text+='The coordinator shortened the active campaign to k=15. The completed\nglider eta 0.33 full sweep and all higher-frequency data/states are retained.\nResumes to k=30 are low priority and require an otherwise idle machine or\na coordinator request. Phase columns below cover only k<=15; process time\nincludes any already-spent higher-frequency work.\n\n' if target==15 else ''
    text+='The paper’s section 4.3 reports that its obstacle solver fails to resolve\nthe cavity at both contrasts. Our large cavity errors agree with that\nqualitative outcome; they do not establish identical reconstructions. See\nthe [paper](https://arxiv.org/pdf/2210.11607) and the source panels below.\n\n'
    text+='Process time includes MATLAB startup and I/O; data and inverse columns\nmeasure those phases separately. Fine-grid checks, when present, are listed\nbelow and included in process time. Per-frequency records retain k,\niterations, residual history, exit flag, time and curve.\n\n'
    for r in entries:
        text+=f"- {r['case']} / {r['curvature']}: UTC {r.get('started')} to {r.get('ended')}; {r.get('new_data_frequencies',117)} newly generated data frequencies.\n"
        if r.get('process_time_is_upper_bound'):
            text+='  Process time is a conservative upper bound because the terminal supervisor was lost; phase times remain measured.\n'
    text+='\n'
    monitor=BASE/'resource_monitor_k15.jsonl'
    if monitor.exists():
        resources=[json.loads(line) for line in monitor.read_text().splitlines()]
        text+=f"Resource monitor: minimum observed available memory {min(r['available_gib'] for r in resources):.2f} GiB; maximum observed MATLAB process count {max(len(r['matlab_pid_rss_kib']) for r in resources)}. Samples are every 10 s, from {resources[0]['utc']}. The required reserve is 14 GB. [Resource log](../../../../results/brg/paper_examples/2026-11-17/resource_monitor_k15.jsonl).\n\n"
    text+='## Curvature comparison\n\n'
    if choice:
        text+=f"Frozen choice: **{choice['selected']}**. {choice['reason']}\n\n"
    else:
        text+='The first glider comparison is pending. No later case has started.\n\n'
    for r in entries:
        if 'figure1_comparison' in r:
            c=r['figure1_comparison']
            text+=f"- {r['case']} / {r['curvature']}: Figure 1 k<=10 RMS log10 difference {c['rms_log10_difference']:.6g}; median absolute difference {c['median_absolute_log10_difference']:.6g}; k=10 area-error ratio {c['endpoint_ratio']:.6g}.\n"
    text+='\nThe predeclared trigger is RMS above 0.30 decades or endpoint disagreement\nabove a factor of two. Exactly one no-limit glider alternative is allowed\nif triggered; choose the lower RMS distance and retain both. The purpose is to\nreproduce the published result; the closer candidate may still disagree.\nNo other case is tuned.\n\n'
    text+='[Figure 1 comparison](figures/glider_033_figure1_comparison.png) shows both permitted candidates when available.\n\n'
    if (BASE/'glider_033/default/coordinator_stop.json').exists():
        text+='''The coordinator stopped the no-limit alternative after 48 completed
frequencies (through k=12.75): its question was already answered by identical
errors at all 37 Figure 1 frequencies. Its partial record is retained and
must not be resumed. The coordinator accepted the paper gap because rebuilt
BRG has lower errors throughout the plotted range and is not handicapped.
No more runs will be spent on this gap.

Reading alone leaves three unconfirmed candidate causes:

1. The authors' actual example drivers are absent. The public filter sequence
   and candidate acceptance differ from the printed algorithm, independently
   of the curvature restriction that this comparison ruled out.
2. Initial node counts, the 300-node update minimum and frequency-start
   resampling are not fully specified in the paper. Public behavior may
   differ from the private experiment's discretization and parameterization.
3. The paper defines a relative polygon set-difference error but supplies no
   scoring code, polygon resolutions or numerical Figure 1 arrays. Its
   post-processing or normalization may differ from our documented symmetric
   difference divided by the 2,048-point true-polygon area. The vector axis
   calibration was checked; no axis-reading error has been found.

These are possibilities, not diagnoses or reasons to change the campaign.

'''
    text+='## Numerical checks and failures\n\n'
    for r in entries:
        text+=f"- {r['case']} / {r['curvature']}: maximum interior-source diagnostic {r['max_analytic_error']:.6g}; exit flags {r['exit_flags']}.\n"
    for case in CASES:
        p=BASE/case/'accuracy_k30.json'
        if p.exists():
            a=json.loads(p.read_text());text+=f"- {case}: k=30 data grid {a['coarse_points']} versus {a['fine_points']} nodes; relative complex-field difference {a['relative_field_difference']:.6g}; check time {a['wall_seconds']:.3f} s.\n"
    if target==15 and not (BASE/'cavity_2/accuracy_k30.json').exists():
        text+='- Cavity eta 2: the k=30 finer-grid check is deferred with the coordinator’s k=30 hold; it has not been performed.\n'
    text+='\nExit 1 means residual stop; 2 update stop; 3 iteration limit; -1 means\nthe public update returned a failure code (including filtered-step failure),\nnot proof that the accepted final curve intersects itself. The manufactured\nsource is verified inside each true curve and is diagnostic only.\n\n'
    failed=[]
    for p in sorted(BASE.glob('*/*/attempt_*.json')):
        a=json.loads(p.read_text())
        if a.get('returncode',0):
            label='coordinator stop/redirect, not a numerical crash' if a.get('status') in ('stopped_by_coordinator','redirected_to_max_k','stopped_at_requested_max_k') else 'failed attempt'
            failed.append(f"- {p.relative_to(BASE)}: {label}; return code {a['returncode']}; log `{a['log']}`.")
        if a.get('supervisor_failure'): failed.append(f"- {p.relative_to(BASE)}: {a['supervisor_failure']} Later runs use detached supervisors. Log: `{a['log']}`.")
    text+='\n'.join(failed) if failed else 'No failed MATLAB attempt is recorded among the completed runs so far.'
    text+='\n\n## Figures and evidence\n\n'
    text+='Paper source panels for visual comparison: [star](figures/paper_star_reference.png) and [cavity](figures/paper_cavity_reference.png). These are direct PDF renders, not inputs to curve recovery. The obstacle-solver panels contain the paper’s k=1, 15 and 30 curves; our endpoint figures stop at the currently requested k=15.\n\n'
    for r in entries:
        label=f"{r['case']}_{r['curvature']}{suffix}"
        text+=f"- {r['case']} / {r['curvature']}: [curves](figures/{label}_curves.png), [errors](figures/{label}_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/{r['case']}/{r['curvature']}/metrics{suffix}.json).\n"
    text+=f'''
All bulk observations, dense continuation states and full logs stay local in
ignored `local/` directories. Each completed attempt has a bulk manifest
with reproduction command, file sizes and SHA-256. Compact curves, residuals,
times and logs are committed; figures are in this report folder.

Commands: `python experiments/baselines/brg/run_paper.py --case <case>
--curvature shipped --max-k {target} --detach`, then
`python experiments/baselines/brg/summarize_paper_case.py --case <case>
--curvature shipped --max-k {target}`, and
`python experiments/baselines/brg/update_paper_report.py --max-k {target}`.
Resuming the run command loads each saved data frequency and the last exact
inverse state; all attempts share the case's four-hour limit.

## BEM handoff and next activity

The data layout, signs and field definition are unchanged from the
[activity 01 handoff](../01_run_published_examples/data_handoff.md), with
paper floor counts, the six case/material assignments and the frozen true geometries
recorded here. Our adapter must consume exactly these saved observations.

[Activity 03 report](../03_adapt_bem_to_brg_data/results.md) records the implemented
plane-wave and full-table extensions onto A1–C12, including variable table
sizes, fixed eta, units, per-shape forward checks and high-k risks. Known eta
below one is already accepted by our core; it is not negative susceptibility.
The CPU table adapter is implemented and the paired default regression is bit-identical.
One BEM glider fit reached k=10 and refused k=12 under the unchanged
cancellation check. Shared comparison code was not edited.
The [activity 04 plan](../04_run_brg_on_tg002_shapes/plan.md) proposes the main
BRG table on TG-002 shapes; it was pushed before the ownership hold and is
now held. No activity 04 run has started.
'''
    DOC.write_text(text)


if __name__=='__main__': main()
