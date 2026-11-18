# BRG paper-case forward checks: stopped for coordinator review

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
