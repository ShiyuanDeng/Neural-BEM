# BRG paper-case BEM: forward checks and CPU pass

CPU pass complete, 18 November 2026. One dataset setting, **K=192**, is fixed
for both passes. All six CPU fits reached the 120 s limit; each accepted
endpoint is scored and retained. The GPU pass waits for the coordinator.

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
