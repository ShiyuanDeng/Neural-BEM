"""Build the SPD-004 human reports from verified saved summaries; no solves."""
import json
from pathlib import Path

bundle = Path(__file__).resolve().parents[1]
root = bundle.parents[3]
report = json.loads((bundle/'summary.json').read_text())
verification = json.loads((bundle/'verification.json').read_text())
assert report['complete'] and verification['status'] == 'PASS'
assert len(report['rows']) == 5
table = ['| Full case | Fast baseline | Readiness pipeline | Speedup | Repetitions per arm |',
         '|---|---:|---:|---:|---:|']
for row in report['aggregate']:
    table.append(f"| {row['scene']} | {row['baseline_seconds']:.2f} s | {row['readiness_seconds']:.2f} s | {row['speedup']:.2f}x | {row['repetitions']} |")
table = '\n'.join(table)
maximum = max(r['boundary_difference_m'] for r in report['rows'])
coefficient = max(r['coefficient_difference_m'] for r in report['rows'])
merge = next(r for r in report['aggregate'] if r['scene']=='merge')
overhead = merge['readiness_seconds']/merge['baseline_seconds']-1
archive = json.loads((bundle/'archive/audit.json').read_text())
counts = ['| Full case / arm | Physical systems | Derivative assemblies |', '|---|---:|---:|']
for row in report['rows']:
    if row['repetition']:
        continue
    for arm in ('baseline','readiness'):
        counts.append(f"| {row['scene']} / {arm} | {row[arm+'_systems']} | {row[arm+'_derivatives']} |")
counts = '\n'.join(counts)
common = f"""The first architectural change removes mandatory continuation when a
training-only check finds the handoff already adequate. **All ten fresh full
workers pass the original recovery checks.** Both death/split repetitions skip
continuation; merge fails the readiness screen and completes the unchanged
fallback. Performance-contract verdict: **{report['status']}**.

{table}

Death and split rows use median worker times from two interleaved pairs each.
Merge is one complete pair; its relative runtime change is {overhead:+.2%}.
Treat that small difference as effectively unchanged runtime, not an established
fallback speedup. The screen still adds eight physical systems.
Times include startup, original-start topology, screening, any continuation,
and independent endpoint checks. Baseline is the already accelerated analytic
CPU pipeline, not historical FD. No GPU change is involved.

Maximum paired difference in 4096-point sampled boundaries: `{maximum:.3e} m`;
maximum coefficient difference: `{coefficient:.3e} m`. All topology event,
geometry, training, independent evaluation and numerical gates pass. Actual
physical and directional work reconciles, and source/input integrity passes.
"""
body = '# SPD-004 — avoid unnecessary inverse phases\n\n'+common+f"""
## What changed

The experimental callback checks all four training frequencies at 256 and 512
nodes before fitting. Each relative residual must be <= 1e-5, and numerical
agreement must pass the existing frequency-specific tolerances. Its decision
receives no truth, scene identity, target count or independent evaluation data.
Geometry is checked at both grids. Ready states still receive independent final
assessment, using the exact training predictions already computed.

The returned status explicitly says `READY_WITHOUT_CONTINUATION`; no skipped
stage exposure or terminal stationarity measurement is claimed. The intended
completion target is the original reconstruction quality, not completion of a
research schedule. Unready states run the original continuation and charge
eight additional training systems for the screen.

{counts}

The easy cases eliminate 340 continuation derivative assemblies each. In the
first death pair the continuation/check portion falls from about 199 seconds
to 9.5 seconds; topology then dominates the remaining full runtime.

## The broader architectural findings

- Four of eight available historical handoffs pass the conservative training
  screen; all four pass independent recovery. Four other scenes have no usable
  handoff. This is an archive audit, not twelve new full inverses.
- Already accurate two-circle cases are expanded from 6 to 34 accessible
  shape directions; repeated birth expands from 9 to 51. The existing
  continuation protocol then requests models even when no updates are taken.
- Merge and central ellipse/star need actual continuation. Mixed is already
  adequate by independent gates but the conservative rule keeps refining it.
- Far/empty ellipse-star handoffs fail at finer geometry grids; enclosing and
  three-shape cases hit topology wall limits. A readiness check cannot fix
  those earlier failures.
- Expensive unsuccessful topology passes motivate an adaptive choice between
  another candidate fit, added frequency information and richer shape freedom.
  This is a next investigation, not an implemented recovery improvement.

See [the architecture audit](architecture_audit.md) for the complete scene
classification, exact supporting counts, limitations and source links.

## Validation and limits

26 focused tests pass. Fresh qualification uses 32 physical systems over four
stored handoffs, including central ellipse/star and two-star negative controls;
maximum discrepancy against archived predictions is 5.244e-15. Tests cover
per-frequency/two-grid decisions, invalid inputs, training-only routing,
independent assessment failures, honest skipped-stage reporting, unchanged
fallback and work accounting. Qualification cost is separate from timed full
workers and retained in its ledger.

Only three distinct scenes were freshly timed. The archive and these controls
are noiseless; 1e-5 is deliberately conservative and is not a calibrated noisy
data stopping rule. The gate's success is empirical and does not prove unique
geometry recovery from training residuals. No production default is promoted.

All arms used one CPU BLAS thread and ran sequentially. Host-wide process
isolation is unverified because tools expose a restricted PID namespace;
load/CPU/thread information is retained for each worker. Two repetitions are
limited timing evidence, and merge has only one pair. Report these measured
case ratios without extrapolating them to all scenes or multiplying them by
historical FD ratios.

## Evidence and reproduction

- [Raw timings](timings.json), [all paired comparisons](comparison.csv),
  [summary](summary.json), [verification](verification.json).
- [Saved-data audit](archive/audit.json), [architecture findings](archive/architecture_findings.json),
  [physical qualification](qualification.json), [test log](tests.log).
- [Dispatch plan](approved_plan.md), [source/input manifest](manifest.json),
  `measured_sources/`, per-arm `runs/` and [execution status](execution_status.json).
- [Artifact hashes](artifact_manifest.json) and [closeout checks](closeout_checks.json).
- [Experiment instructions](../../../../experiments/spd004_pipeline_readiness/README.md).

Rebuild numeric reporting with
`python -m experiments.spd004_pipeline_readiness.summarize BUNDLE`, then this
file with `python BUNDLE/reporting_sources/build_report.py`, from the repository
root with `PYTHONPATH=solvers`. Both read saved evidence and run no BIE solves.
"""
(bundle/'README.md').write_text(body)
doc = root/'docs/iterations/speedup/iteration_04/01_results.md'
doc.parent.mkdir(parents=True,exist_ok=True)
relative = '../../../../'+str(bundle.relative_to(root))
doc.write_text('# SPD-004 — a pipeline change delivers additional full-inverse speedups\n\n'
    '2026-09-16. **Execution COMPLETE.** The user authorized the architecture\n'
    'investigation with “investigate go”; [dispatch plan](../iteration_03/03_plan.md).\n'
    'Owner/reviewer: Codex `/root`, self-review; no independent review claimed.\n\n'
    +common+'\n'
    f'[Full measured report]({relative}/README.md) · [paired CSV]({relative}/comparison.csv) · '
    f'[verification]({relative}/verification.json).\n\n'
    '## What the big-picture investigation found\n\n'
    'The pipeline was imposing continuation exposure after some cases had already\n'
    'reached adequate reconstruction quality. A full-training readiness decision\n'
    'removes that whole optimizer phase on those cases. It preserves independent\n'
    'endpoint assessment and explicitly leaves stationarity/stage exposure unmeasured.\n'
    'The gate uses residual <=1e-5 at every training frequency on both grids, plus\n'
    'the original numerical tolerances; evaluation data and truth never select it.\n\n'
    'The saved twelve-scene audit separates different architectural problems:\n\n'
    '| Situation | Cases | Next decision |\n|---|---|---|\n'
    '| Adequate handoffs | repeated-birth, death, split, far-two-circles | Stop before mandatory fitting |\n'
    '| Conservative gate retains an adequate handoff | mixed | Keep fallback; later study task/noise-aware stopping |\n'
    '| Real shape/frequency refinement needed | merge, central-ellipse-star | Preserve continuation; investigate adaptive capacity |\n'
    '| Continuation still fails recovery | far-two-stars | Diagnose search/information choices |\n'
    '| Finer-grid handoff refused | far-ellipse-star, empty-ellipse-star | Bring final numerical feasibility into topology search |\n'
    '| Topology wall limit reached | enclosing-ellipse-star, far-three-shapes | Investigate topology growth and effort allocation |\n\n'
    f'[Detailed audit and provenance]({relative}/architecture_audit.md).\n\n'
    '## Qualification, scope and next priority\n\n'
    '26 focused tests pass; four saved-handoff physics checks use 32 systems and\n'
    'agree with archived predictions to 5.244e-15. Full-case work counts reconcile.\n'
    'The timed controls cover three scenes, not the entire suite; the data are\n'
    'noiseless and the conservative gate has not been qualified for noisy data.\n'
    'Host-wide process isolation is unverified in the sandbox. All arms are\n'
    'sequential with single-thread BLAS; individual timings remain available.\n\n'
    'The implementation is experimental, with no production-default promotion.\n'
    'After early completion, topology is the dominant remaining cost on the\n'
    'measured easy cases. Prioritize earlier final-grid feasibility and adaptive\n'
    'topology/shape/data decisions for harder scenes, and reprofile before a GPU\n'
    'port. SPD-003 exact reuse remains an unexecuted compatible optimization.\n')
print(doc)
