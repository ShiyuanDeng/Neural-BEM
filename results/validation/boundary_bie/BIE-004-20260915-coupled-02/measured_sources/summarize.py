"""Audit and summarize BIE-004 saved measurements without new physics calls."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics
import time
import numpy as np


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_output(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader()
        writer.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path);args=parser.parse_args()
    p=args.bundle;tick=time.perf_counter();m=read(p/'manifest.json')
    data={name:read(p/(name+'.json')) for name in ('controls','operator_checks','direction_checks',
        'jacobians','refinements','taylor','timings','gauge')}
    attempts=[];location=p
    while True:
        mm=read(location/'manifest.json')
        attempts.append(dict(path=str(location),status=mm['status'],failure=mm.get('failure'),counts=mm['counts']))
        previous=mm.get('previous_attempt')
        if not previous:break
        location=Path(previous)
    events=[json.loads(line) for line in (p/'work_ledger.jsonl').read_text().splitlines()]
    counts={k:0 for k in m['counts']}
    for event in events:
        if event['status']=='attempted':
            for k,v in event.get('reserved',{}).items():counts[k]+=v
    if m.get('previous_attempt'):
        old=read(Path(m['previous_attempt'])/'manifest.json')
        counts={k:counts[k]+old['counts'][k] for k in counts}
    assert counts==m['counts']
    assert all(counts[k]<=m['limits'][k] for k in counts)
    assert m['numerical_seconds']<=1800 and m['peak_rss_bytes']<8*1024**3
    assert m['source_hashes']==m['source_hashes_after']
    for name,h in m['source_hashes'].items():assert sha(name)==h,name
    for name,h in m['input_hashes'].items():assert sha(name)==h,name
    for name,h in m['experiment_hashes'].items():
        assert sha(p/'measured_sources'/Path(name).name)==h,name
    assert sha(p/'approved_plan.md')==m['plan_sha256']
    replay=[]
    for row in data['jacobians']:
        analytic=np.array(read(p/f"{row['case']}_analytic_jacobian.json")['matrix'])
        fd=np.array(read(p/f"{row['case']}_fd_jacobian.json")['matrix'])
        error=float(np.linalg.norm(analytic-fd)/np.linalg.norm(fd))
        worst=float(np.max(np.linalg.norm(analytic-fd,axis=0)/np.maximum(
            np.linalg.norm(fd,axis=0),1e-12*np.linalg.norm(fd))))
        assert np.isclose(error,row['relative_frobenius_error'],rtol=1e-12)
        assert np.isclose(worst,row['worst_column_relative_error'],rtol=1e-12)
        replay.append(dict(case=row['case'],rows=analytic.shape[0],columns=analytic.shape[1],
                           relative_error=error,worst_column_error=worst))
    def worst(rows,key):return max((r[key] for r in rows if r.get(key) is not None),default=None)
    selected=[r for r in data['direction_checks'] if r.get('role')!='current_optimizer_step_accuracy_only']
    optimizer_steps=[r for r in data['direction_checks'] if r.get('role')=='current_optimizer_step_accuracy_only']
    timing={};speed=None;nonoverlap=False
    pairs=[r for r in data['timings'] if r['stage']=='paired_timing']
    for method in ('analytic','fd'):
        rows=[r for r in pairs if r['method']==method]
        if rows:
            values=[r['total_seconds'] for r in rows]
            timing[method]=dict(repetitions=len(rows),median=statistics.median(values),
                minimum=min(values),maximum=max(values),seconds=values,counts_per_repeat=rows[0]['counts'])
    uncontaminated=bool(pairs) and not any(r['external_numerical_processes'] for r in pairs)
    if len(timing)==2 and all(r['repetitions']==3 for r in timing.values()):
        speed=timing['fd']['median']/timing['analytic']['median']
        nonoverlap=timing['analytic']['maximum']<timing['fd']['minimum']
    qualified=m['accuracy_passed']
    promoted=bool(qualified and speed and speed>=1.3 and nonoverlap and uncontaminated)
    verdict=('ANALYTIC_JACOBIAN_QUALIFIED_AND_FASTER' if promoted else
             'ANALYTIC_JACOBIAN_QUALIFIED_SPEED_UNPROVEN' if qualified else 'SENSITIVITY_UNQUALIFIED')
    recommendation=('Prepare one opt-in integration and matched inverse validation after topology reaches a stable integration point; preserve current defaults.'
                    if promoted else 'Close the current measurement and resolve the recorded accuracy or timing gate before any production integration.')
    summary=dict(verdict=verdict,accuracy_qualified=qualified,promotion_screen_passed=promoted,
        full_jacobians=replay,operator_checks=len(data['operator_checks']),
        failed_operator_checks=sum(not r['passed'] for r in data['operator_checks']),
        worst_operator_relative_error=worst(data['operator_checks'],'relative_error'),
        worst_small_step_jvp_relative_error=worst(selected,'relative_error'),
        worst_current_fd_step_relative_error=worst(optimizer_steps,'relative_error'),
        worst_forward_refinement=max((r['relative_error'] for r in data['refinements'] if r['quantity']=='forward'),default=None),
        worst_sensitivity_refinement=max((r['relative_error'] for r in data['refinements'] if r['quantity']=='sensitivity'),default=None),
        taylor_ratios=[r['halving_ratio'] for r in data['taylor'] if r['halving_ratio'] is not None],
        timing=timing,speedup=speed,timing_ranges_nonoverlapping=nonoverlap,uncontaminated_timing=uncontaminated,
        benchmark_status=m['benchmark'],counts=counts,numerical_seconds=m['numerical_seconds'],
        peak_rss_bytes=m['peak_rss_bytes'],attempts=attempts,recommendation=recommendation,
        numerical_source_unchanged=True,inverse_executed=False)
    (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for name in ('operator_checks','direction_checks','jacobians','refinements','taylor','timings','gauge'):
        csv_output(p/(name+'.csv'),data[name])
    def sci(v):return 'unavailable' if v is None else f'{v:.3e}'
    text=f'''# BIE-004 — coupled analytic shape Jacobians

**{verdict}**. Execution status: **{m['status']}**.

The experiment differentiates the actual multi-interface Kress system, including
both directions of every cross-object interaction, incident traces, receiver
weights and normals. One base LU is reused for all 34 gauge-coordinate
directions and all 24 source right-hand sides. The existing self-interface
derivative machinery is imported unchanged. Production numerical files and the
topology controller remain unchanged; no inverse was executed.

## Accuracy

| Saved two-star state, 1.25 GHz / 256 nodes per object | Full residual Jacobian relative error | Worst column relative error |
|---|---:|---:|
'''
    for r in replay:text+=f"| {r['case']} | {r['relative_error']:.3e} | {r['worst_column_error']:.3e} |\n"
    text+=f'''
Both matrices have 48 real residual rows and 34 production gauge-coordinate
columns. The reference is central FD with coefficient step 1e-5, using the
actual `incremented(...).polar_angle_gauge_fixed()` retraction and fixed
production residual normalization. Full-matrix and worst-column thresholds
are 1e-4. Saved matrices can be re-audited without physical solves.

- Operator comparisons: **{summary['operator_checks']}**, failures:
  **{summary['failed_operator_checks']}**. Worst nonzero scaled block relative
  error: **{sci(summary['worst_operator_relative_error'])}**. Zero-derivative
  blocks use the declared base-scaled roundoff allowance, not an arbitrary
  unit-size absolute tolerance.
- Worst selected JVP error against 1e-5/5e-6 FD:
  **{sci(summary['worst_small_step_jvp_relative_error'])}**, threshold 1e-4.
- Worst 256/512 forward discrepancy:
  **{sci(summary['worst_forward_refinement'])}**, threshold 2e-7.
- Worst sampled 256/512 analytic sensitivity discrepancy:
  **{sci(summary['worst_sensitivity_refinement'])}**, threshold 2e-5.
- The current optimizer's 1e-4 FD step was also measured on selected directions;
  its worst discrepancy against the analytic value is
  **{sci(summary['worst_current_fd_step_relative_error'])}**. This is a separate
  scale-accuracy observation, not an inverse-recovery claim.
- Noncircular mixed-direction Taylor ratios on step halving:
  **{', '.join(f'{v:.4f}' for v in summary['taylor_ratios'])}** (expected local
  second-order ratio 4). The displacement of the gauge retraction is recorded
  in [gauge.csv](gauge.csv).

Wiring includes reduction to the existing single-interface analytic routine,
unequal component node counts (24/32) and native periods (2π/3.7), individual
translations, collective translation and a noncircular shape direction. Moving
one object changes cross blocks; translating both leaves A invariant. All
physical checks are charged to the same ledger.

## Full-Jacobian cost

Benchmark status: **{m['benchmark']['status']}**. Timing includes fresh geometry,
retraction, full parent assembly, primal solve, derivative assembly, tangent
solves, receiver evaluation, primal consistency checks and ledger overhead.
The benchmark uses the terminal state, 1.25 GHz, 256 nodes per object, 34
directions and 24 source RHS in both arms. It compares the production FD
mechanism at the finer declared step of 1e-5 against analytic derivatives.

| Method | Paired repetitions | Median [min, max], seconds | LU factorizations per full Jacobian | RHS batches |
|---|---:|---:|---:|---:|
'''
    for name,row in timing.items():
        text+=f"| {name} | {row['repetitions']} | {row['median']:.3f} [{row['minimum']:.3f}, {row['maximum']:.3f}] | {row['counts_per_repeat']['factorizations']} | {row['counts_per_repeat']['solves']} |\n"
    if speed is not None:text+=f"\nMeasured median speedup: **{speed:.2f}x**. Timing ranges nonoverlapping: **{nonoverlap}**. No detected concurrent repository numerical worker: **{uncontaminated}**.\n"
    else:text+='\nNo qualified three-pair speed claim is available. See the recorded benchmark reason and operation counts.\n'
    text+=f'''
Assembly-equivalent counts conservatively charge one full assembly for every
analytic directional recomputation. Actual recomputed/skipped self and cross
kernel blocks appear in [controls.json](controls.json); unchanged blocks are
reused. Derivative matrices are streamed, not retained for all 34 directions.
Finite differences are used for validation/comparison only.

## Work and reproducibility

Counts across attempts: **{counts['assemblies']}/800** assembly equivalents,
**{counts['derivatives']}/300** analytic directional calls,
**{counts['factorizations']}/600** factorizations,
**{counts['solves']}/1000** RHS batches. Numerical wall time:
**{m['numerical_seconds']:.2f}/1800 s**. Peak process RSS:
**{m['peak_rss_bytes']/1024**3:.3f}/8 GiB**. Four algebra tests passed in the
continuation. The first attempt had a malformed negative test: it omitted the
mandatory first-derivative array and therefore raised before the intended
node-grid check. That one test-input correction is preserved in the previous
bundle; it consumed zero physical assemblies and its elapsed time is carried
forward. There was no change to a numerical formula or a scientific threshold.

See [manifest.json](manifest.json), [approved_plan.md](approved_plan.md),
[commands.md](commands.md), [work_ledger.jsonl](work_ledger.jsonl), and
[tests.log](tests.log). Exact experiment sources are preserved in
`measured_sources/`; saved geometry coefficients, observations, acquisition,
source hashes and package versions are in the manifest. The reporting audit
replays the Jacobian errors from the stored matrices and reconciles counters.

The support is fixed topology, shape-only, disjoint lossless nonmagnetic
same-material inclusions, fixed acquisition, and the tested gauge-fixed
Cartesian subspace. Magnetic/lossy media, material/source derivatives,
off-subspace re-gauging, topology-event derivatives and inverse integration are
outside this experiment. Accuracy here is a diagnostic tier, not qualification
for every existing inverse endpoint tolerance.

## Single recommended next action

**{recommendation}** No successor or inverse is executed by this closeout.
'''
    (p/'README.md').write_text(text)
    report=dict(status='PASS',counts_reconciled=True,jacobian_metrics_replayed=replay,
                source_and_inputs_unchanged=True,approved_plan_hash_verified=True,
                physical_reexecution=False,reporting_seconds=time.perf_counter()-tick,
                reporting_script_sha256=sha(__file__))
    (p/'measured_sources'/'summarize.py').write_bytes(Path(__file__).read_bytes())
    (p/'reporting_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
