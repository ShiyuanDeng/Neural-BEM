# Fit BEM to the six saved BRG paper cases

Approved by the BEM-side coordinator, 18 November 2026. Work in the shared
checkout on `organised`; no branch, worktree, solver edit or baseline edit.

Question: does our BEM fit the saved glider_033, glider_10, star_full,
star_limited, cavity_09 and cavity_2 observations through k=15, and what
raw shape error, residual, work and runtime does each endpoint give?

## Fixed settings before any fit

Read and import the BRG adapter and frozen true curves. Use unit-amplitude
plane waves and finite-radius scattered fields without conjugation or gain
fitting. Contrast is the saved squared wavenumber ratio and is known.
One centred unit-disk start; modal_muller + slider; real observations only;
table mode; series_loss=1e-6; no localization, warm-up or noise estimate.

One rule for all six cases: saved k = 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5,
4, 5, 6, 7, 8, 10, 12, 15. Grow cumulative prefixes with equal frequency
weights. Preserve BRG 03 quotas: 1000, 1250, 1750, 4000, then 1500 per
stage; 22 iterations; update band floor(3k); storage band 2M+2. Global cap
13,412 work units, 1 hour; CPU pass stops at 120 s and waits for GPU.
No per-case tuning or tuning reruns. Old glider k=10 evidence stays intact.

## Checks and review stops

Before any fit, compare production and refined BEM on each true frozen
shape/material with each of the 16 saved tables. Require relative complex
field difference <=1e-5 and refinement difference <=1e-6 (the conservative
BRG 03 thresholds used by its executable check). Save row/column errors,
maximum absolute error, solver diagnostics and source hashes. Record the
coefficient wave radius and k=15 cancellation estimate at series_loss=1e-6.
Budget: 30 minutes per case. Stop and report a refusal below k=15.

**First stop:** report all forward checks and radii; wait for coordinator go.
**Second stop:** CPU pass on idle cores; wait for GPU completion and go.
The GPU pass is the reported result; CPU outcomes remain a cross-check.
Score accepted endpoints, including failures, with unedited comparison
region/region_scores. No truth enters the Problem or fit stopping rules.

## Resources and evidence

EMNerf Python from repository root; BLAS and frequency workers pinned to
one per fit. First check measures process peak RSS. Launch only when the
expected peak leaves 16 GiB available; stop the run's own process group
below 14 GiB. Count spare CPU cores before parallel CPU fits. GPU belongs
to bem-gpu until released. Every run records HEAD, solver dirty status and
solver source hashes at start/end; dirty fits are not reported results.

Code: `experiments/bem_on_baseline_data/brg_paper.py`.
Outputs: `results/bem/baseline_data/brg_paper/2026-11-18/<case>/`.
Raw large arrays/logs live in ignored `local/`, with hashes and command.
Compact JSON evidence is committed, at most about 5 MB per run. Report
figures, if needed, go in this activity's `figures/` directory. Commit and
push own code/docs/evidence after runs, failures included.

Commands (CPU fits and GPU fits require their respective coordinator go):

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_paper.py forward --case all
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_paper.py fit --case CASE --device cpu
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_paper.py fit --case CASE --device cuda
```

Success of a forward check qualifies the data convention and numerical
resolution. Fit success is reported through raw scores and actual last k;
no new classification or superiority claim is made. Solver crashes and
forward failures go to the coordinator without editing the solver.

## Amendment, 18 November 2026: coordinator's forward-resolution decision

The original plan above and its first failed checks remain history. The
coordinator now authorizes a wrapper-only resolution setting and continuation
without another forward-check stop. No inverse fit has yet run.

Set `ModalSettings(trace_minimum=K)` for this entire dataset. On true shapes
only, find the smallest multiple of 32, starting at 32 and at most 256,
for which every case passes both unchanged thresholds at every frequency
admitted by the unchanged series_loss=1e-6. Then add 32 as a margin and
fix that one setting for all six cases and CPU/GPU passes before any fit.
Check the final setting too; stop if it fails. A failed frequency suffices
to reject a candidate; check high frequencies first to avoid needless work.
Previously saved checks may reject an identical resolution profile without
repeating it. Actual production/refined profiles are recorded; the existing
storage-based floor can exceed a low candidate minimum. At the final K,
production/refined trace cutoffs must be K and K+32 for all used bands.

For each cavity, check every admitted ladder frequency, through k=8, and
save an actual check at the first refused k=10. The cavity fit consumes
the qualified prefix, with its forward refusal recorded as the data cap.
An evolving fit may refuse sooner; retain that outcome. Check both stars
through k=15. Do not loosen series_loss or rerun a failed fit.

Budget remains 30 minutes of accumulated forward time per case, including
candidate selection and final qualification. Stop if no candidate through
256 passes, if a solver edit would be required, or if resources prevent
progress. Candidate/refinement checks and original failures are retained
under `results/bem/baseline_data/brg_paper/2026-11-18/resolution_selection/`.
Final qualifications and fits carry the fixed setting explicitly.

Once final forward checks pass, run all six CPU fits without a further
stop. Count idle cores, reserve memory from the observed first-fit peak,
and run in parallel only while those limits permit. Stop numerical work at
120 s per CPU fit; score the last saved accepted curve if interrupted.
Save raw scoring output and work/state records for failures too. Report
the selected K, production/refined time per forward solve, each case's
last admitted k and all CPU endpoints. Then wait for the GPU go.

Commands added by this amendment:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_resolution.py
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_cpu_pass.py
```

## Amendment, 18 November 2026: retain converged BRG mismatches

The coordinator supersedes the BRG-threshold blocking rule above. Choose K
on refinement <=1e-6, and on BRG <=1e-5 where that difference decreases
with increasing resolution. If refinement passes and both production and
refined solutions retain a BRG difference above 1e-5, record the failed
BRG threshold at that frequency. A stable converged difference does not
block a fit on the saved BRG observations. Neither threshold is loosened.
Keep the original and rejected checks; reuse them under this new decision.

Stop the repeated K search on cavity_09's converged k=1.25 mismatch. Spend
at most ten minutes comparing our Fourier truth with saved BRG boundary
points, including a band-convergence check. Read baseline files only;
do not fix data or choose inverse settings from this investigation.
Then fix the common K plus margin, finish final forward checks and run the
CPU pass without another review stop. Fits still consume BRG's saved data.

## GPU-pass go, 18 November 2026

The coordinator accepted the CPU pass as the early look and authorized
the GPU pass as the reported one. GPU table support is committed at
`3612f5195`; verify clean solver sources before each launch. No solver,
data, scoring or scientific-setting change is authorized here.

Keep K=192, series_loss=1e-6, known contrast, unit-disk start, real data,
modal_muller + slider, no localization and the fixed qualified prefixes.
Execution is cuda with one frequency/BLAS thread. Per fit: 13,412 work
units and 3,600 s; a time-limited fit is retained without a rerun.

Use one sequential queue: glider_033, glider_10, star_full, star_limited,
cavity_09, cavity_2. The coordinator supersedes the old launch memory
rule for this pass: start only if available memory minus 1.5 GiB leaves
at least 14.5 GiB; kill the fit's own process group below 14 GiB available.
GPU sharing with bem-csi is allowed. Timings remain indicative.

A memory-killed attempt is retained but is not a reported result. Requeue
it once at the end of the queue, restarting from the same unit disk with
unchanged settings. Save both attempts separately; a second memory kill
remains a no-result failure. No other rerun is authorized.

Commit and push each completed attempt, failures included. Report
glider_033 immediately in one line (last k, stop reason, area error, time),
then continue. When all six cases are done, stop with per-case last active
k, stop reason, area error, residual, work, wall time and peak memory.
Compare CPU/GPU saved accepted states at their highest common k; distinguish
a CPU stage cut short by time from a completed GPU stage. Where available,
also compare the same stage/iteration to expose numerical differences.

Outputs are `<case>/cuda_fit/attempt_01/` (and `attempt_02/` for a memory
retry), plus `gpu_pass.json` and an activity `gpu_pass_progress.md`.
Large optimizer files and logs remain local with hashes. The one command:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_gpu_pass.py
```

## User decision, 18 November 2026, about 01:05 UTC: skip series-limited cases

The coordinator relayed the user's words: "skip the case and similiar ones
that have this problem". No solver change will be made. Remove cavity_09
and cavity_2 from the reported GPU pass. Record each as **skipped by the
user's decision: the series limit refuses the true shape above k=8**.
They receive no reported GPU fit score and are not fit failures. Retain
all forward checks and CPU early-look results as history.

The reported queue is now glider_033, glider_10, star_full, star_limited,
in that order. Other settings and limits remain fixed. If a star fit is
refused by the series limit before k=15, retain its last accepted endpoint
and refusal, do not rerun, and report immediately to the coordinator for
the same user decision. Queue changes apply between numerical fits;
completed native fits are finalized without restarting them.

## Follow-up checks, 18 November 2026: 20-minute total limit

The coordinator accepts three reported results. Glider_10 remains a
failed fit, not a series-limit skip: its k=12 residual and shape error
were already large before the bad fitted curve refused k=15.

Checks only: no fit, rerun, solver edit or setting change. From saved
accepted glider_10 states, score each stage endpoint and record k,
maximum active residual, area error, coefficient wave radius and work.
For glider_033, compare CPU/CUDA forward predictions and B7 Jacobians at
K=192, eta=0.33 and one frequency thread on the unit disk and true curve
at k=1, 2.5 and 15. Keep B6 directions identical for the B7 physics
comparison, and record any difference from native slider preparation.
If any requested physics/B7 relative difference exceeds 1e-10, retain
the check, stop and report immediately. No tolerance is changed.

Compare saved glider_033 accepted states from the start to find the first
curve difference above 1e-10 and its growth. Compare trial decisions,
damping and charged evaluations there. Inspect execution settings,
speculative work, wall-limit handling and stage-entry reuse from saved
receipts and current matching solver source. Distinguish measured causes
from unproved amplification mechanisms. No new inverse trajectory is run.

Total limit: 20 minutes from 01:24:50 UTC, deadline 01:44:50 UTC.
Owned check script: `experiments/bem_on_baseline_data/brg_followup_checks.py`.
Evidence: `results/bem/baseline_data/brg_paper/2026-11-18/followup_checks/`.
Write findings here in results.md, commit, push and stop. Solver changes
and tuning reruns remain outside scope; diagnosis fix phases do not apply.
