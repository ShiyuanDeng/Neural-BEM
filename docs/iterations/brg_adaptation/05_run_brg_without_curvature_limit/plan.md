# Run BRG without the curvature limit

## Authority and question

The coordinator authorized this control on 18 November 2026: "the same
20 cases with only the curvature limit removed (eps_curv unset, which is
the public code's default; use the wrapper's curvature switch)."

Activity 04 continues untouched until its existing queue ends by itself.
Then this activity asks how much its recovery failures depend on the
shipped example driver's curvature limit. Keep both rows provisional.
No BEM work, upstream patch, tuning or other setting change is authorized.

The coordinator found that BRG rejected both GN and SD candidates with
geometry ier 2 on stalled cases. Its independent true-curve curvature-tail
ratios at band 20 were 0.38 kite, 0.28 star, 0.26 asymmetric, 0.24 cog and
0.33 aphex_twin, against the shipped limit 0.1. These are coordinator
findings, not new measurements by this activity.

## Settings and comparison

Use all 20 activity-04 TG-002 shape/contrast pairs, including failed fits.
The only inverse change is the public default curvature option: omit
`eps_curv`, using the existing public-default curvature switch convention.
The minimum curvature band is unused without that limit. Keep
self-intersection checks.

Everything else follows [04's plan](../04_run_brg_on_tg002_shapes/plan.md):
37 real frequencies, identical observations and order, one centred unit-disk
start, known eta 0.5 or 4, equal density, 70 exterior inverse points per
wavelength, public update bands, min(GN,SD), Gaussian filtering, 50 iterations,
1e-5 residual/update stops, eight MATLAB threads, patches 03/04, and the
seven-argument public inverse call. No warm start from an activity-04 fit.

Use the existing 04 data files in place, read-only. Verify each against its
committed SHA-256 manifest before its case starts. Save a reuse manifest
with all 37 hashes and paths; missing or mismatched data stop the queue.
Never regenerate data or charge the old data-generation time to this row.
Reuse the exact shape input and its hash. Save fresh continuation states.

Use unchanged protocol-1 scoring and final-curve residual checks. Retain
raw area error, maximum residual, contrast error (known contrast), all
per-frequency curves/histories, stopping codes and timings. Count terminal
geometry/filter and iteration ier codes from the saved MATLAB logs only.
Compare each result directly with 04; do not choose a new success cutoff.

## Order, budget and success criteria

Run `kite__c0.5` alone first as the timed pilot. No additional pilot cutoff
was specified: its existing one-hour case cap applies. Report its cost
before launching the rest. Next run cases whose last frequency ended with a rejected update
(exit -1) in 04, preserving 04 order within that group; then the
remaining cases. Both circle cases run last. Save the exact order and the
log-derived grouping before launch.

The coordinator set two workers, at least 14 GiB available memory, one hour
per case and five hours elapsed for the queue. Both limits include checks,
scoring and receipts. Reserve estimated worker growth before each launch.
Use a separate detached supervisor with `campaign.json`, `resources.jsonl`,
`STOP` and `STOPPED.json` in the new result directory. `STOP` prevents new
launches and asks active workers to save and end at the next checkpoint;
hard deadlines still apply. A memory breach also terminates the newest
control MATLAB process group to release memory promptly; saved frequency
checkpoints remain. Keep failed and partial outputs and report them.
Do not restart or retry without another coordinator decision.

Success for the activity means answering the curvature-control question
with matched data and raw metrics under those limits. An improvement is a
measurement, not a requirement for keeping a case. Check finite saved curves
and histories, output counts, return codes, budgets, data hashes and reserve.
Inspect the figures. Commit roughly 5 MB per case at most, by owned paths.

## Commands and evidence

Commands will use `/home/drdeng/miniconda3/envs/EMNerf/bin/python` with
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.

- `experiments/baselines/brg/log_tg002_rejections.py`: read existing logs only.
- `experiments/baselines/brg/run_tg002_control.py --prepare`: freeze order,
  data provenance and the source snapshot without launching MATLAB.
- `experiments/baselines/brg/run_tg002_control.py --campaign --detach`:
  start only after activity 04 ends normally.
- `experiments/baselines/brg/report_tg002_control.py`: report saved outputs.

Results: `results/brg/tg002_no_curvature/2026-11-18/`. Large states and logs
stay in its ignored `local/` directories with SHA-256 manifests. Figures:
`docs/iterations/brg_adaptation/05_run_brg_without_curvature_limit/figures/`.
Record dates, actual settings, elapsed times, failures, comparison with 04
and any remaining uncertainty in `results.md`. Commit and push each batch.

## Preparation checks, 18 November

Python syntax passed. A read-only launch check refused to proceed while
activity 04 was active. Two simulated queues (no subprocesses) checked that
the pilot runs alone, the worker count never exceeds two, and STOP retains
the unrun cases. The scorer's reconstruction and frozen score call match
04 exactly apart from output paths and the row label; only timing metadata
separates reused data from new work. Existing kite logs confirm 37 terminal
curvature rejections, with iteration 7 retaining iteration 6 at the first
frequency. These checks launched no MATLAB process or numerical experiment.
