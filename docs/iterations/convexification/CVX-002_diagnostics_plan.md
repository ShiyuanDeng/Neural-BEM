# CVX-002 supplementary phase and readout diagnostics

Registered 2026-10-11 after the 41-grid screen was committed as fdc4f6a0,
before these supplementary computations. The 57-grid conditional refinement
is running under its original plan. These diagnostics do not change either
inverse, endpoint selection, or the registered refinement rule.

1. Save raw exact centered-disk complex field ratios for contrasts 4 and 13.3
   on grids 41, 81 and 161 at the same three real frequencies. Record positive,
   negative and total plaquette indices per frequency; their sum and outer
   boundary winding; minimum sampled magnitude; maximum wrapped phase increment;
   and defect centers. Qualify Mie cutoffs 36/46 at relative 1e-8. Require finite
   arrays, indices within 1e-10 of integers, and discrete telescoping within
   1e-10. Compare counts and same-sign nearest-neighbor locations on refinement.
   Count instability remains visible. Stable sampled winding is not a rigorous
   continuous zero count or proof of no between-sample phase excursions.
2. Save the C-shape contrast13.3 boundary ratios at the same three frequencies
   with 160, 320 and 640 unique box-perimeter points. Qualify CPU nodal Kress
   N512/N1024 at relative 1e-7 for total field and record sampled winding,
   minimum magnitude, and maximum wrapped increment. No phase unwrapping alters
   the data. Initial-field failures and measured-boundary failures remain
   distinct conclusions.
3. Evaluate the exact prescribed centered65mm initial circle against all19
   original real paired frequencies for circle contrast0.5, using the same
   N256/N512 and optional N1024 qualification and normalization as endpoints.
   Compare all four saved endpoints (41/57 grids, spans0/4) without rerunning
   optimization or selecting an intermediate iterate.
4. Score each saved largest-contour Fourier readout with dense16384 parameter
   samples resampled uniformly by arclength to16384 points. Compute symmetric
   RMS and sampled Hausdorff distances to an equally sampled truth curve.
   These are additional sampled metrics, not replacements for all-contour
   scores or certified TG-002 geometry bounds. Preserve the number of discarded
   components and their geometric areas. No clipping or material fitting.

Save sources/hashes, raw arrays, complete per-frequency receipts, a summary,
and phase plots in a fresh diagnostics directory. No new inverse experiment,
new acquisition hypothesis, branch, or worktree is introduced. Validate and
commit/push the diagnostics with their code and report before finishing.
