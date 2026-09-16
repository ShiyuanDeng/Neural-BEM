# SPD-004 — avoid unnecessary inverse phases

The first architectural change removes mandatory continuation when a
training-only check finds the handoff already adequate. **All ten fresh full
workers pass the original recovery checks.** Both death/split repetitions skip
continuation; merge fails the readiness screen and completes the unchanged
fallback. Performance-contract verdict: **PASS**.

| Full case | Fast baseline | Readiness pipeline | Speedup | Repetitions per arm |
|---|---:|---:|---:|---:|
| death | 236.26 s | 46.12 s | 5.12x | 2 |
| split | 222.32 s | 33.10 s | 6.72x | 2 |
| merge | 406.34 s | 403.52 s | 1.01x | 1 |

Death and split rows use median worker times from two interleaved pairs each.
Merge is one complete pair; its relative runtime change is -0.69%.
Treat that small difference as effectively unchanged runtime, not an established
fallback speedup. The screen still adds eight physical systems.
Times include startup, original-start topology, screening, any continuation,
and independent endpoint checks. Baseline is the already accelerated analytic
CPU pipeline, not historical FD. No GPU change is involved.

Maximum paired difference in 4096-point sampled boundaries: `0.000e+00 m`;
maximum coefficient difference: `0.000e+00 m`. All topology event,
geometry, training, independent evaluation and numerical gates pass. Actual
physical and directional work reconciles, and source/input integrity passes.

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

| Full case / arm | Physical systems | Derivative assemblies |
|---|---:|---:|
| death / baseline | 157 | 470 |
| death / readiness | 89 | 130 |
| split / baseline | 193 | 451 |
| split / readiness | 125 | 111 |
| merge / baseline | 308 | 1768 |
| merge / readiness | 316 | 1768 |

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
