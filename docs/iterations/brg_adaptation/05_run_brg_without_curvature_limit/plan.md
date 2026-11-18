# Run BRG without the curvature limit

## Authority and question

The coordinator authorized this control on 18 November 2026: "the same
20 cases with only the curvature limit removed (eps_curv unset, which is
the public code's default; use the wrapper's curvature switch)."

Activity 04 continues untouched until its existing queue ends by itself.
The coordinator subsequently authorized a no-time-cap completion of the
shipped row after the old supervisor exits; see [04 continuation plan](../04_run_brg_on_tg002_shapes/continuation_plan.md).
Only after all 20 shipped-limit cases finish does this activity ask how
much its recovery failures depend on the
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

## Order, time targets and success criteria

Run `kite__c0.5` alone first as the timed pilot. It has no time cutoff.
Report its cost
before launching the rest. Next run cases whose last frequency ended with a rejected update
(exit -1) in 04, preserving 04 order within that group; then the
remaining cases. Both circle cases run last. Save the exact order and the
log-derived grouping before launch.

The user's 18 November 01:18 UTC correction supersedes the original hard
caps: "the time limit isnt for you to cutoff agent, but something as a
design requirement. do not stop running terminal ifi didnt say so. keep it
as it is now". Activity 04's existing processes and loaded files stay
untouched. Its later authorized continuation uses only new entry points
after the old supervisor ends.

For this unstarted activity, two workers and the 14 GiB start guard remain.
One hour per case and five hours for the queue are reporting targets only.
Record and tell the coordinator when either is passed, then keep running.
There is no per-case timeout, queue deadline, time stop or kill path.
Memory pressure delays a new start; it never stops an active fit.

Use a separate detached supervisor with `campaign.json`, `resources.jsonl`,
`STOP` and `STOPPED.json` in the new result directory. Only a STOP requested
by the user ends the queue early. The agent never creates STOP on elapsed
time, memory pressure or failure. STOP prevents new launches and active
MATLAB workers save and end at their next frequency checkpoint. Normal
completion also ends the queue. Keep failed outputs and proceed to the
other cases without retries. Missing or mismatched source data block
preparation and go to the coordinator; they do not authorize regeneration.

Success for the activity means answering the curvature-control question
with matched data and raw metrics against those targets. An improvement is a
measurement, not a requirement for keeping a case. Check finite saved curves
and histories, output counts, return codes, elapsed targets, data hashes and reserve.
Inspect the figures. Commit roughly 5 MB per case at most, by owned paths.

## Commands and evidence

Commands will use `/home/drdeng/miniconda3/envs/EMNerf/bin/python` with
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.

- `experiments/baselines/brg/log_tg002_rejections.py`: read existing logs only.
- `experiments/baselines/brg/run_tg002_control.py --row control --prepare`: freeze order,
  data provenance and the source snapshot without launching MATLAB.
- `experiments/baselines/brg/run_tg002_control.py --row control --campaign --detach`:
  start only after activity 04 ends normally.
- `experiments/baselines/brg/report_tg002_control.py`: report saved outputs.

Results: `results/brg/tg002_no_curvature/2026-11-18/`. Large states and logs
stay in its ignored `local/` directories with SHA-256 manifests. Figures:
`docs/iterations/brg_adaptation/05_run_brg_without_curvature_limit/figures/`.
Record dates, actual settings, elapsed times, failures, comparison with 04
and any remaining uncertainty in `results.md`. Commit and push each batch.

## Preparation checks, 18 November (before the time-policy correction)

Python syntax passed. A read-only launch check refused to proceed while
activity 04 was active. Two simulated queues (no subprocesses) checked that
the pilot runs alone, the worker count never exceeds two, and STOP retains
the unrun cases. The scorer's reconstruction and frozen score call match
04 exactly apart from output paths and the row label; only timing metadata
separates reused data from new work. Existing kite logs confirm 37 terminal
curvature rejections, with iteration 7 retaining iteration 6 at the first
frequency. These checks launched no MATLAB process or numerical experiment.

The time-policy correction above supersedes the old cap-related checks.
Recheck the new launcher with simulated elapsed time beyond both targets,
low memory and a user STOP; it must continue past time targets, delay only
new starts under memory pressure, and contain no termination call. No
additional numerical experiment is needed for this check.

Updated checks passed on 18 November: a simulated queue ran for 55,000 s,
recorded both time-target overruns, waited through 12 GiB available memory,
and finished all three mock cases with at most two workers. A second mock
queue stopped only on the simulated user STOP and retained its unrun list.
Static checks found no timeout keyword, deadline, signal or kill path in
the new launcher and no elapsed-time stop in its MATLAB wrapper. No real
process was launched or stopped by these checks.

The user's final clarification at about 01:24 UTC applies: time alone is
never a reason to stop; a stuck or faulty run may be stopped after telling
the coordinator what happened, unless urgent. The memory guard may act as
designed. The new runner conservatively delays starts under memory pressure
and leaves active fits running; intervention on a fault is a separate call.
The same new runner completes the shipped-limit row first with `--row shipped`,
then executes this row with `--row control`; they never overlap.

## Resource allocation update, 18 November about 02:20 UTC

The user-authorized monitor in w3:p1 raised the limit to **four BRG fits
in total**, across the shipped completion, aphex retries and this control.
Prioritize aphex data. Do not interrupt or restart active numerical fits.
The running shipped supervisors retain their own limits. The new control
supervisor reserves their possible next launches before claiming a slot.

This supersedes the earlier start-after-all-04-data rule for the **kite 0.5
pilot only**. Prepare available hashed datasets with `--prepare --pilot-only`,
and start the control queue in the free slot. No missing data are generated.
After the pilot, the queue waits for a recorded first-case review and for
full preparation. Once all 20 shipped cases are complete, run
`--finish-preparation` to verify the remaining hashes and finalize stalled-
case-first ordering. Record the pilot check and report its result before
writing `PILOT_REVIEW.json`; continuation is already authorized.

The fresh launch check reads machine MemAvailable, outstanding BRG worker
growth and B1's active worker reservations. It reserves 3 GiB per new BRG
worker, 4 GiB per active B1 worker less its observed fit-process memory,
and keeps a 14 GiB floor plus a 2 GiB margin. It rereads
`results/brg/resource_policy.json` at every control launch boundary.
It never changes scientific settings, starts CSI or stops on elapsed time.
Current effective counts and any held slots are recorded in campaign state.
The pilot remains the sole active control fit until it finishes and is
reviewed. The baseline result rows and all failed attempts remain intact.

## Resource allocation update, 18 November 02:40 UTC

The baseline coordinator passed on the user-directed resource monitor
(w3:p1) allocation: raise the control ceiling from four to six while CSI
stays held. The change is in `results/brg/resource_policy.json`, read at
each launch boundary. Each new worker still reserves at least 3 GiB and
keeps the 14 GiB host floor plus 2 GiB margin after shared reservations.
No supervisor restart, numerical setting change or time kill. When CSI is
released the coordinator will set a lower ceiling for new launches; active
fits continue. Policy history retains the prior four-worker allocation.

## Resource allocation update, 18 November 02:51 UTC

The coordinator passed on the same monitor's increase to eight control
fits while CSI stays held. The unchanged memory guard may leave slots
empty. No active fit or numerical setting changes. Each completed case
receipt now records peak concurrent other BRG/B1 fits and the distinct
overlapping fit receipts, using saved process intervals only. The new
`record_tg002_overlap.py` reads B1 timing records without editing them.
BRG intervals include final residual evaluation; other host work is not
counted as a fit. These remain shared-machine timings.
