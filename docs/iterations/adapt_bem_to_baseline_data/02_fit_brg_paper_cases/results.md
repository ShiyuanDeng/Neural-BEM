# BRG paper-case BEM: reported GPU pass

The four-case GPU pass is complete, 18 November 2026. Glider_033 and both
stars reached k=15. Glider_10 is a failed fit at k=12, with a later series
refusal entering 15; it is not a series-limit skip. Both cavities are
skipped by the user, with no reported GPU score.
K=192 and all scientific settings remain fixed. The CPU early look and
original forward checks below are retained as history.

## Original forward-check stop, 18 November 2026

18 November 2026, 00:22 UTC. No inverse fit has run. The fixed wrapper and
plan are in place; forward qualification stopped at glider_10 k=7. No solver,
baseline-owned file, comparison scoring or coordination file was edited.

## Fixed settings and evidence

All checks use saved BRG observations and frozen true curves, known eta,
CPU table mode and series_loss=1e-6. The declared ladder has 16 frequencies
through k=15. Production and refined settings come from the unchanged
solver profile for the true curve band. Thresholds are relative BRG field
difference <=1e-5 and refinement difference <=1e-6. No threshold or setting
changed after seeing a check. The wrapper stops the batch at the first failure.

Command: `/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/brg_paper.py forward --case all`.
Total batch wall time: 33.698 s. Individual numerical checks record source
data SHA-256, solver start/end hashes, commit and dirty status. All 28 checks
used clean, unchanged solver sources. Shared-checkout HEAD moved from
`3da19bb0f240a6fa9862afd50929013c31a7ee89` to
`26d95baf257697d2aed6052c21d96f0a75e633ff`; solver hashes stayed identical.
Logs and full field arrays remain in each `forward/local/`, with hashes in
the qualification records. No tuning rerun was attempted.

## True-shape wave radii

These use the solver's coefficient wave-radius rule, excluding the constant
translation coefficient. The k=15 series estimate is the solver's own
round-off estimate, computed before the batch for all six cases.

| Case | Wave radius | k=15 estimate | Passes 1e-6 series limit | Forward status |
|---|---:|---:|---|---|
| glider_033 | 1.278 | 4.30898e-9 | Yes | All 16 frequencies pass through 15 |
| glider_10 | 1.278 | 4.30898e-9 | Yes | Passes through 6; refinement/BRG failure at 7 |
| star_full | 1.5571909958762484 | 2.56863e-7 | Yes | Not run after stop |
| star_limited | 1.5571909958762484 | 2.56863e-7 | Yes | Not run after stop |
| cavity_09 | 2.919025118615278 | 139.2155 | No | Not run after stop |
| cavity_2 | 2.919025118615278 | 139.2155 | No | Not run after stop |

[Raw radius records](../../../../results/bem/baseline_data/brg_paper/2026-11-18/wave_radii.json).
The star and cavity geometries remain labelled as recovered from paper
figure files. Radius checks alone do not qualify a forward comparison or
guarantee that an evolving fitted curve will pass the series limit.

## Glider eta 0.33

All 16 frequencies pass; maximum relative BRG difference is 1.30165074e-6
and maximum refinement difference is 2.88918130e-8. At k=15 the relative
BRG difference is 2.89071914e-8. Qualification wall time is 19.107 s.

Peak worker RSS across this case is 0.2875 GiB; the first numerical worker
peaked at 0.208 GiB. Minimum available memory was 20.437 GiB. Single BLAS
and frequency threads were used; no GPU work was launched.

[Qualification](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_033/forward/qualification.json)
and [k=15 record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_033/forward/k_15.json).
The prior k=10 inverse result in BRG activity 03 remains intact.

## Glider eta 10: forward resolution failure

Eleven frequencies pass through k=6. At k=7 the production/refined
difference is **3.90199046e-5**, and production/BRG difference is
**3.90199158e-5**. Both thresholds fail. This is a forward-resolution
failure, without a solver exception or series-limit refusal.

The profiles have trace cutoffs 64 and 96, coefficient windows 128 and
160. Their linear-system residuals are 7.22e-15 and 9.40e-15; these small
residuals do not establish forward convergence. No resolution adjustment
or additional solve was made. Qualification wall time is 14.368 s.

Peak worker RSS is 0.3041 GiB and minimum available memory is 20.167 GiB.
[Failure record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_10/forward/k_7.json)
and [qualification](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_10/forward/qualification.json).
The saved solver profile and radial diagnostics are available there.

## Limits and next step

No memory or time limit was reached. The six-case forward phase is
incomplete: 28 frequency checks ran, with 27 passing. Four cases and
glider_10 above k=7 remain unchecked; no inverse fits or scores exist.
Only about 0.6 MB of compact JSON evidence is committed; bulk is ignored.

Stop for the coordinator: decide how to handle the glider_10 resolution
failure and the cavity series estimates before further checks or fits.
The current settings cannot qualify all six cases through k=15. Solver
changes, if chosen, belong to its lock holder. CPU and GPU passes wait.

## Resolution amendment and final forward checks, 18 November 2026

The coordinator authorized true-shape resolution selection, then allowed
converged BRG differences to remain failed thresholds without blocking fits.
The original checks and plan text above remain history.

The smallest qualifying minimum is **160**. Candidate minima 32/64 and 96
fail glider_10 at k=15; 128 has refinement difference 1.13619648e-6 and
also fails. All admitted frequencies qualify at 160 under the revised rule.
The fixed dataset minimum is **K=192**, adding the agreed 32 margin.
All final profiles have production/refined trace cutoffs 192/224.

At K=192 all 90 series-admitted frequency checks pass refinement. Both
gliders and both stars admit k=15. Both cavities admit k=8 and actually
refuse the next ladder frequency, k=10, with series estimate 7.8e-5 above
1e-6. Fits consume each checked prefix; fitted curves may refuse sooner.

BRG thresholds remain failed at 12 frequencies in each star (k=1 through
7 on the ladder) and two in cavity_09 (k=1 and 1.25). They are recorded
per frequency, with production/refined BRG differences. Gliders and
cavity_2 pass every BRG threshold. No field, truth curve or threshold changed.

| Case | Last admitted k | First refused k | Max BRG difference | Max refinement difference | Production solve median [min, max], s | Refined solve median [min, max], s |
|---|---:|---:|---:|---:|---|---|
| glider_033 | 15 | none | 1.30165e-06 | 1.11862e-09 | 0.293 [0.257, 1.294] | 0.408 [0.365, 1.825] |
| glider_10 | 15 | none | 3.21481e-06 | 1.50984e-09 | 0.308 [0.271, 1.333] | 0.430 [0.376, 1.877] |
| star_full | 15 | none | 0.00723226 | 2.6459e-09 | 0.296 [0.252, 2.666] | 0.376 [0.351, 3.109] |
| star_limited | 15 | none | 0.00723226 | 2.69243e-09 | 0.302 [0.281, 2.679] | 0.407 [0.376, 3.303] |
| cavity_09 | 8 | 10.0 | 2.93592e-05 | 3.19757e-12 | 0.362 [0.313, 23.093] | 0.457 [0.423, 26.355] |
| cavity_2 | 8 | 10.0 | 3.19542e-06 | 4.55965e-12 | 0.353 [0.316, 25.438] | 0.472 [0.429, 28.302] |

Timings include shared-machine contention. First solves include geometry
preparation; later frequencies reuse geometry. The initial workers measured
up to 1.234 GiB RSS; first-fit launch reserves that peak plus 20%.

[Fixed resolution and per-case evidence](../../../../results/bem/baseline_data/brg_paper/2026-11-18/resolution_selection/fixed_resolution.json).
The original search supervisor was stopped after its current numerical
worker completed when the coordinator changed the BRG-mismatch rule.
Saved checks were reused; no inverse fit or numerical row was discarded.
The pre-change candidate summary and pause record are retained.

### Bounded cavity cause check

The full band-100 Python truth matches all 2,048 saved BRG truth points
to maximum 2.48253e-15. Truncating to bands 25, 50 and 75 gives maximum
point differences 0.016719, 0.00232104 and 0.000427872, respectively; the
difference falls to round-off at band 100. This rules out a coefficient
loading or band mismatch against that saved truth polygon.

The source makes the saved truth without resampling, but resamples each
forward-data boundary. The low-frequency cavity data use 300 boundary
points. Those actual resampled points are absent from the retained data
records, so discretization or resampling remains a possible cause, not a
proved explanation. Inspection and the check stayed below the ten-minute
budget; no data or coefficients were changed.

[Raw geometry comparison and data records](../../../../results/bem/baseline_data/brg_paper/2026-11-18/resolution_selection/cavity_truth_check.json).

### CPU pass

Authorized immediately after these checks. The six fits use the same
fixed K=192, saved BRG observations and known contrast, starting at the
unit disk. Single BLAS and frequency threads; 120 s supervisor limit.
Per-fit endpoints and failures are recorded in `cpu_pass_progress.md`.

## Completed CPU pass, 18 November 2026

All six fits used K=192, known contrast, unit-disk starts, modal_muller
with slider, real saved BRG data and no localization. Every numerical
worker was stopped at 120 s by its own process-group supervisor. There
were no scoring failures or memory stops, and no fit reruns. These are
partial CPU endpoints; the later GPU pass is the reported comparison.

| Case | Qualified forward cap | Last active fitted k | Area error, % | Maximum active residual | Last accepted work units | Wall, s | Peak RSS, GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| glider_033 | 15 | 2.5 | 13.9387 | 0.0131199 | 606 | 120.102 | 1.2673 |
| glider_10 | 15 | 2 | 19.678 | 0.569761 | 529 | 120.107 | 1.3888 |
| star_full | 15 | 2 | 19.8453 | 0.01142 | 379 | 120.039 | 1.2836 |
| star_limited | 15 | 2 | 19.8392 | 0.0114193 | 379 | 120.109 | 1.3209 |
| cavity_09 | 8 | 1.5 | 162.882 | 0.765238 | 155 | 120.046 | 1.1718 |
| cavity_2 | 8 | 1.5 | 158.832 | 0.649911 | 159 | 120.041 | 1.1517 |

Last active k identifies an accepted state within that stage; it does not
mean the stage converged. Work units are the last accepted ledger count,
a lower bound on work at interruption. The killed workers did not return
a final ledger snapshot; that missing value is retained as null.

Raw scores use the unedited comparison region functions with 16,384
points on both curves. Each case has `raw_region_scores.json`,
`metrics.json`, the input/solver manifest, supervisor receipt and hashes
for the local optimizer records, logs and curve arrays. All six outcomes
are `SUPERVISOR_STOP` with `wall limit 120 seconds`.

The CPU batch took **409.505 s** (6 min 49.5 s), with up to three fits
overlapping. First-fit peak RSS was 1.2673 GiB; the largest worker peak
was 1.3888 GiB. The lowest observed available memory was **16.1347 GiB**.
Single BLAS/frequency threads and idle-core counts were recorded at launch.
All fits started and ended with clean solver sources, with one identical
solver source-hash map across all six. Every case was committed and pushed
after scoring; source commit hashes are retained per run.

[CPU campaign and launch records](../../../../results/bem/baseline_data/brg_paper/2026-11-18/cpu_pass.json)
and [per-fit progress](cpu_pass_progress.md).

### Handoff stop

No GPU fit has been launched. Use the same fixed-resolution file and the
existing `brg_paper.py fit --case CASE --device cuda` commands after the
coordinator gives the GPU go. No CPU tuning rerun is planned. Cavity data
above the admitted k=8 prefix still need the separate user decision on
a solver redesign; series_loss remains 1e-6.

## User skips, 18 November 2026, about 01:05 UTC

The coordinator relayed the user decision: "skip the case and similiar ones
that have this problem". The reported GPU pass now contains glider_033,
glider_10, star_full and star_limited only. No solver change is made.

Both cavity_09 and cavity_2 are **skipped by the user's decision: the series
limit refuses the true shape above k=8**. No cavity GPU fit had started.
They receive no score in this pass and are not fit failures. Their forward
checks and CPU early-look evidence remain history.

A star series refusal below k=15 is retained and reported immediately,
without a rerun, for the coordinator to apply the same user decision.

During the queue change, the queue supervisor was paused, also pausing
its guard during part of glider_10. This was corrected before the fit
finished. The receipt records observed memory minima; guard coverage has
a known gap. The numerical fit was not restarted, and its ledger ceiling
remained active. This limit-check limitation is retained in its metrics.

## Reported GPU pass, 18 November 2026

Four numerical fits ran, each once, in the authorized order. There were
no memory-killed attempts, memory retries or one-hour stops. Glider_033
was reported immediately on completion. Both stars reached k=15 without
a series refusal. No cavity GPU fit was launched.

All four CPU/GPU manifests have identical observation hashes, eta, K=192,
series_loss=1e-6 and serialized scientific operations. Solver source hashes
are identical between CPU and GPU, and clean at every fit start/end.
Only execution and the authorized wall ceiling differ. No solver, baseline
or shared scoring file was edited.

| Case | Last active k | Stop reason | Area error, % | Maximum active residual | Work units | Fit / process wall, s | Host peak / sampled GPU peak, GiB |
|---|---:|---|---:|---:|---:|---:|---:|
| glider_033 | 15 | Completed schedule | 0.061412 | 2.20683e-05 | 2161 | 69.548 / 71.472 | 2.514 / 2.574 |
| glider_10 | 12 | Series refusal entering k=15 | 14.0568 | 0.730212 | 6156 | 215.742 / 217.481 | 2.328 / 5.180 |
| star_full | 15 | Completed schedule | 0.582861 | 0.00723138 | 8248 | 332.512 / 334.318 | 2.662 / 2.400 |
| star_limited | 15 | Completed schedule | 0.602698 | 0.00723138 | 6453 | 271.782 / 273.675 | 2.507 / 2.641 |

The complete queue took **1,032.004 s** (17 min 12 s), including its queue
reconfiguration and postprocessing. Timings are indicative on the shared
machine. Process wall time includes startup; fit time and exact work
counts come from the returned ledger. Maximum host peak was 2.662 GiB
and largest sampled GPU memory was 5.180 GiB. The lowest observed
available host memory was 17.662 GiB. GPU memory is sampled every two
seconds, not an allocator high-water bound.

### Glider eta 10 refusal and monitoring limitation

Entering k=15 returned `NUMERICAL_FAILURE`: "initial state is not
solver-ready". The underlying saved physics failure is "Regular-wave
series cancellation 1.6e-06 exceeds 1e-06 (|k| rho=25.2)." Its accepted
k=12 curve and raw score are retained, with no rerun. The coordinator
was told this is another series-limited case. Its user decision is pending.

The glider_10 queue supervisor was paused during the cavity queue change,
which also paused its guard. The guard was restored before the numerical
fit ended. The resource log has a **121.298 s sampling gap**, from elapsed
93.742 to 215.040 s. Its minimum-memory receipt therefore covers observed
samples, not continuous guard coverage over the whole fit. This limitation
is explicit in its metrics and supervisor receipt. Its native work/time
ledger remained active; the numerical fit was never restarted.

[Glider_10 endpoint, refusal and monitoring record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_10/cuda_fit/attempt_01/metrics.json).

### CPU/GPU comparisons at shared frequencies

The GPU columns below use the last accepted state at the highest shared
k. Each CPU state was cut short within that stage by its 120 s limit,
while the GPU completed more iterations. These are common-frequency
endpoint comparisons, not equal-budget fits or numerical-agreement claims.

| Case | Common k | CPU area error, % | GPU common-stage area error, % | CPU / GPU common-stage last iteration | Same-iteration relative curve difference |
|---|---:|---:|---:|---:|---:|
| glider_033 | 2.5 | 13.9387 | 13.5827 | 7 / 22 | 0.0603138 |
| glider_10 | 2 | 19.678 | 19.6779 | 17 / 21 | 1.32902e-05 |
| star_full | 2 | 19.8453 | 22.6102 | 3 / 22 | 3.9761e-05 |
| star_limited | 2 | 19.8392 | 22.6194 | 3 / 22 | 1.6315e-05 |

The accepted paths are not identical. Glider_033 differs materially even
at the matching k=2.5, iteration 7: CPU/GPU truth-area errors are
13.9387% and 13.3874%; their regions differ by 6.65461% of the CPU region
area. Its accepted work counts also differ (606 and 618). This path
difference is flagged, without assigning a cause or making a tuning rerun.

For the other three cases, same-iteration relative curve differences are
1.33e-5 to 3.98e-5. Their CPU/GPU truth-area scores and residuals at those
matching iterations are saved separately from the later GPU stage endpoint.
All comparisons use saved accepted states; no extra fit or forward solve
was run. Raw region scores use the unedited comparison functions.

Per-fit evidence and comparisons:

- [glider_033](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_033/cuda_fit/attempt_01/metrics.json) and [CPU comparison](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_033/cuda_fit/attempt_01/cpu_comparison.json).
- [glider_10](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_10/cuda_fit/attempt_01/metrics.json) and [CPU comparison](../../../../results/bem/baseline_data/brg_paper/2026-11-18/glider_10/cuda_fit/attempt_01/cpu_comparison.json).
- [star_full](../../../../results/bem/baseline_data/brg_paper/2026-11-18/star_full/cuda_fit/attempt_01/metrics.json) and [CPU comparison](../../../../results/bem/baseline_data/brg_paper/2026-11-18/star_full/cuda_fit/attempt_01/cpu_comparison.json).
- [star_limited](../../../../results/bem/baseline_data/brg_paper/2026-11-18/star_limited/cuda_fit/attempt_01/metrics.json) and [CPU comparison](../../../../results/bem/baseline_data/brg_paper/2026-11-18/star_limited/cuda_fit/attempt_01/cpu_comparison.json).

### Final stop

The four requested GPU cases are complete. Both cavities remain **skipped
by the user's decision: the series limit refuses the true shape above
k=8**. They have no reported GPU score and are not fit failures. Their
forward and CPU evidence remain history. No solver redesign or further
fit is started. The glider_10 series refusal and glider_033 CPU/GPU path
difference are handed to the coordinator.

[Queue record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/gpu_pass.json),
[skip record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/gpu_skips.json)
and [GPU progress](gpu_pass_progress.md).

## Coordinator follow-up checks, 18 November 2026

The coordinator accepts the three completed k=15 results and classifies
glider_10 as a **failed fit**, not a series-limit skip. Its k=12 residual
0.7302 and area error 14.0568% already show failure; the subsequent
refusal entering 15 is caused by the bad fitted curve. This classification
supersedes the earlier pending-decision note; numerical scores stay intact.

Checks only were authorized, with a 20-minute total limit from 01:24:50
UTC. No fit, fit rerun, setting change, solver edit or baseline edit was
made. The requested stop condition was met at the third isolated check,
unit disk k=15: native-basis B7 difference exceeds 1e-10. Numerical checks
stopped immediately; the three true-curve checks were not run.

### A. Glider eta 10, saved stage endpoints

Residual is the saved maximum relative field residual across active
frequencies. Work is cumulative at the last accepted callback, before
its next derivative rebuild, so it can be below full stage/end-of-fit
work. Every score and wave radius below comes from saved accepted
coefficients only, using unedited comparison scoring. True wave radius
is **1.278**. There is no accepted state at k=15.

| Stage k | Residual at last acceptance | Area error, % | Wave radius | Cumulative accepted work |
|---|---:|---:|---:|---:|
| 1 | 0.0469832 | 16.4165 | 1.05367237 | 45 |
| 1.25 | 0.100937 | 16.1534 | 1.17460505 | 100 |
| 1.5 | 0.0847259 | 14.8831 | 1.18598233 | 147 |
| 1.75 | 0.573109 | 14.9732 | 1.17865838 | 330 |
| 2 | 0.569763 | 19.6779 | 1.24397901 | 579 |
| 2.5 | 0.53147 | 18.6338 | 1.35086862 | 878 |
| 3 | 0.50364 | 19.7186 | 1.53283838 | 1171 |
| 3.5 | 0.523759 | 16.5443 | 1.55265855 | 2258 |
| 4 | 0.537064 | 14.8207 | 1.57922651 | 2671 |
| 5 | 0.562548 | 16.5973 | 1.54785918 | 3140 |
| 6 | 0.581192 | 15.4965 | 1.61252617 | 3645 |
| 7 | 0.63533 | 15.2993 | 1.63195816 | 4196 |
| 8 | 0.610591 | 15.1426 | 1.66630629 | 4793 |
| 10 | 0.683118 | 14.7867 | 1.67096863 | 5436 |
| 12 | 0.730212 | 14.0568 | 1.68189098 | 6125 |

The saved endpoints never approach the truth closely: the first stage
already has 16.42% area error. The marked residual break is k=1.75,
where the residual rises from 0.08473 at k=1.5 to 0.57311. Later stages
retain roughly 14–20% area errors. The radius reaches 1.68189 at k=12;
the refusal at k=15 is a consequence of this bad fit, not its first failure.

[Raw per-stage endpoint table](../../../../results/bem/baseline_data/brg_paper/2026-11-18/followup_checks/glider_10_stage_endpoints.json).

### B1. CPU/CUDA forward and B7 checks

K_trace=192, series_loss=1e-6, eta=0.33, table mode and one frequency
thread. Update band and storage follow the fixed stage rule (M=3/7/45,
K_geometry=8/16/92). Relative differences use the CPU complex-array
Frobenius norm as denominator. Fixed-basis B7 uses identical CPU-prepared
B6 directions on both physics states. Native-basis B7 uses each device
's own slider-prepared directions, as in the original fits.

| Shape | k | Prediction difference | B7, identical B6 directions | B7, native B6 directions | B6 direction difference |
|---|---:|---:|---:|---:|---:|
| Unit disk | 1 | 8.76139e-16 | 4.86153e-16 | 6.02108e-14 | 1.12312e-13 |
| Unit disk | 2.5 | 6.84266e-15 | 6.62255e-15 | 1.71086e-12 | 1.76527e-12 |
| Unit disk | 15 | 1.06377e-13 | 1.04886e-13 | 1.18561e-10 | 9.82882e-11 |

**Stop finding:** native-basis B7 differs by **1.18561e-10** at k=15,
above the coordinator's 1e-10 limit. With fixed directions, B7 differs
by 1.04886e-13 and predictions by 1.06377e-13. The above-limit component
therefore enters through the device-dependent B6 direction preparation,
not the isolated fixed-direction B7/forward comparison. All three
true-glider checks remain unrun under the explicit stop rule.

In the A1–C12 chain, the forward comparison checks A1–A4; the identical
direction comparison isolates B7, and the native comparison also includes
B6. The selected slider path follows the execution device by default.
[`SliderUpdate.prepare`](../../../../solvers/bem_inverse/geometry_update_methods/slider.py#L92)
uses NumPy `lstsq` on CPU and
[`_cuda_solve`](../../../../solvers/bem_inverse/geometry_update_methods/slider.py#L168)
uses Torch `eigh` on CUDA. The nominal cutoff rule is the same; these are
different dense numerical implementations. This is existing default
device-follow behavior for slider, not a setting changed by this check.
BRG table acquisition remains an explicit opt-in path. No code was fixed.

[Physics/B7 checks and stop record](../../../../results/bem/baseline_data/brg_paper/2026-11-18/followup_checks/physics_comparison.json).

### B2. First saved trajectory divergence

The first accepted curve difference above 1e-10 is **k=1, iteration 3**,
at relative difference **3.22927e-8** (maximum point difference
3.11387e-8). Iterations 1 and 2 differ only by 3.78e-15 and 8.07e-15.
At iteration 3 both use one accepted trial, no backtrack, damping
9e-5 followed by 2.7e-5, and the same work: 7 at acceptance, 8 after
linearization. Their residuals differ only in the last reported digits.
Thus the first jump is not an accept/reject, damping or evaluation-count
branch difference; numerical curve differences are amplified before a
recorded discrete-decision change.

| Saved state | Relative curve difference | CPU / GPU accepted work |
|---|---:|---:|
| k_1, iteration 1 | 3.77943e-15 | 3 / 3 |
| k_1, iteration 2 | 8.06836e-15 | 5 / 5 |
| k_1, iteration 3 | 3.22927e-08 | 7 / 7 |
| k_1, iteration 4 | 1.18543e-07 | 9 / 9 |
| k_1, iteration 6 | 1.09463e-06 | 13 / 13 |
| k_1, iteration 8 | 3.77864e-05 | 17 / 17 |
| k_1, iteration 10 | 0.0011823 | 21 / 21 |
| k_1, iteration 22 | 0.000301098 | 45 / 45 |
| k_2.5, iteration 0 | 0.0168956 | 522 / 402 |
| k_2.5, iteration 7 | 0.0603138 | 606 / 618 |

Differences grow non-monotonically within the first stage. All matched
accepted-iteration decision signatures in the collected completed-stage
records agree. By the k=2.5 entry, cumulative work differs (522 versus
402), and by iteration 7 it is 606 versus 618. That later work divergence
is distinct from the initial k=1 iteration-3 jump; unmatched terminal
trials and the exact later branch were not investigated after the stop.

The changed B6 numerical implementation is a concrete device-dependent
component and accounts for the isolated native-Jacobian finding. It is
**not yet a demonstrated cause** of the early 3.23e-8 jump or eventual
6.03e-2 curve difference. No inverse replay or further probe was made
after the stop condition.

[Saved accepted-state growth and recorded decisions](../../../../results/bem/baseline_data/brg_paper/2026-11-18/followup_checks/accepted_trace_comparison.json).

### B3. Configuration and control paths

- Both passes use `frequency_threads=1`, the same input hashes, eta,
  scientific operations, trace/storage profiles and solver source hashes.
- Both have `preparation_device=follow`; effective B6 preparation is CPU
  versus CUDA, with the two dense solves named above. This effective
  implementation difference was not visible in the scientific-operation
  equality check alone, but is explicit in saved update settings.
- With one frequency thread,
  [`ordered_calls`](../../../../solvers/bem_inverse/continuation/forward.py#L147)
  returns deferred serial calls. No speculative frequency evaluations run.
- Both set `stage_entry_reuse=False`; the default-path
  [runner](../../../../solvers/bem_inverse/runner.py#L100) does not carry
  stage entries in either run. This does not explain the early divergence.
- The intentional wall limits are 120 s CPU and 3,600 s GPU; both use the
  same ledger logic, with matching 13,412-unit caps. Neither wall limit
  is active at the first divergence. CPU interruption explains its partial
  endpoint, not the preceding iteration-3 jump. The GPU queue
  reconfiguration/monitoring gap happened only in glider_10, not this
  glider_033 comparison.

The unchanged default C11/C12 path in
[`fit_stage`](../../../../solvers/bem_inverse/fit_stage.py#L391) accepts
lower-loss trials, then commits the curve, updates damping and rebuilds
the derivative. The first-divergence records show the same choices on
this path. No stopping, reuse or speculative-work setting was retuned.

[Saved execution/update configurations](../../../../results/bem/baseline_data/brg_paper/2026-11-18/followup_checks/pass_configuration_comparison.json).

### Follow-up limit and failure record

The initial check wrapper called an unavailable `ModalMuller.close`
after saving the passing k=1 row. This was a wrapper cleanup error,
not a solver failure. Its exit status/log are retained. The wrapper was
corrected to guard optional cleanup and continued only unfinished rows;
the completed row was not recalculated. Initial and continuation worker
process times were 2.814 s and 7.251 s. Peak worker RSS was 2.052 GiB;
no memory guard stopped a check.

The B1 threshold finding stopped numerical work well inside the
20-minute budget. True-curve checks and a proof of the early trajectory
amplification cause remain incomplete by instruction. All collected
records and failed-wrapper evidence are retained; no fit, fit rerun,
setting change or solver edit was made.
