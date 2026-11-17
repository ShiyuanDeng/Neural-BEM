# Rebuild the paper's single-component examples: results

## Status

Campaign started 17 November 2026. 1/6 cases complete.
This report is updated after each run. The full case budget is four hours,
including data and all attempts; the optional glider alternative shares it.
These are rebuilt paper cases, distinct from activity 01's shipped example.

## Actual settings and provenance

The [plan](plan.md) records the coordinator's decisions and all differences
between paper prose and public code. All cases use k=1:0.25:30, known eta,
equal density, unit-amplitude plane waves and finite-radius scattered fields.
Full tables have floor(10k) directions and receivers at radius 10; the
limited star has 10 directions and 200 receivers. No noise or extra starts.

Data use 100 exterior points per wavelength and inversion uses 70, with
public frequency-start behavior. At eta=10 the corresponding interior
counts are 31.62 and 22.14; at eta=2 they are 70.71 and 49.50.
The public better-of-GN/SD option, Gaussian filter, 50-iteration limit and
1e-5 residual/update stops are retained. Initial curve: public unit disk.
No zero-gradient guard or added frequency-start resampling was introduced.
Area scores compare the fixed 2,048-point truth polygon with each saved
inverse curve, without an extra resampling of the inverse endpoint.

MATLAB R2026a runs at 8 compute threads, set only in the wrapper. The
activity 01 dense-solve check measured a 3.68-fold improvement over one
thread. CSI may overlap; start/end MATLAB process lists are in every attempt
receipt. An observed overlap during glider 0.33 data generation is recorded
separately. All times here are indicative, not clean-machine comparisons.

Pinned upstream: `bda24bddbf4562497280b671bc174ef891b47c6b`.
Approved patches 03 and 04 preserve transmission derivative fields and
update interior k with exterior k. No new upstream change was needed for
these runs. The wrapper uses the current seven-argument RLA call.

## Shape recovery

Glider: exact radial coefficients from section 4.1, recorded in the plan.
Star and cavity: **recovered from the paper's figure files**, not claimed
to be the authors' absent original analytic curves. Both were extracted from
solid vector paths in two obstacle-solver panels and mapped with axis ticks.
No pixels were traced and no shipped cavity was substituted.

| Shape | Cross-panel maximum | Fourier band | Fit RMS at vector points | Maximum fit-to-polyline distance |
|---|---:|---:|---:|---:|
| Star | 1.060e-4 | 35 | 1.751e-4 | 5.594e-4 |
| Cavity | 9.154e-5 | 100 | 1.596e-5 | 1.424e-4 |

Errors are in data-coordinate units. Conservative recovered-geometry
accuracy is about 6e-4 for the star and 2e-4 for the cavity, relative to the
vector centerlines. This uncertainty limits comparison with the paper's
original experiment. It does not excuse a BEM/BRG mismatch on the same
frozen recovered shape.

[Star overlay](figures/star_vector_recovery.png),
[cavity overlay](figures/cavity_vector_recovery.png), and
[vector evidence](../../../../results/brg/paper_examples/2026-11-17/shapes/)
include coefficients, both panels, calibration, path indices and hashes.

## Outcomes

| Case / curvature | Frequencies | Relative area error at last k | Field residual | Iterations | Data min | Inverse min | Process min |
|---|---:|---:|---:|---:|---:|---:|---:|
| glider_033 / shipped | 117/117 | 0.00311943% | 4.79883e-07 | 280 | 18.72 | 46.29 | 68.52 |

Process time includes MATLAB startup and I/O; data and inverse columns
measure those phases separately. Fine-grid checks, when present, are listed
below and included in process time. Per-frequency records retain k,
iterations, residual history, exit flag, time and curve.

- glider_033 / shipped: UTC 2026-11-17T20:16:16.608701+00:00 to 2026-11-17T21:24:47.514919+00:00; 117 newly generated data frequencies.
  Process time is a conservative upper bound because the terminal supervisor was lost; phase times remain measured.

## Curvature comparison

The first glider comparison is pending. No later case has started.

- glider_033 / shipped: Figure 1 k<=10 RMS log10 difference 0.904393; median absolute difference 0.728363; k=10 area-error ratio 0.41022.

The predeclared trigger is RMS above 0.30 decades or endpoint disagreement
above a factor of two. Exactly one no-limit glider alternative is allowed
if triggered; choose the lower RMS distance and retain both. The purpose is to
reproduce the published result; the closer candidate may still disagree.
No other case is tuned.

[Figure 1 comparison](figures/glider_033_figure1_comparison.png) shows both permitted candidates when available.

## Numerical checks and failures

- glider_033 / shipped: maximum interior-source diagnostic 7.34431e-07; exit flags {'2': 73, '1': 44}.

Exit 1 means residual stop; 2 update stop; 3 iteration limit; -1 means
the public update returned a failure code (including filtered-step failure),
not proof that the accepted final curve intersects itself. The manufactured
source is verified inside each true curve and is diagnostic only.

- glider_033/shipped/attempt_01.json: Terminal-launched supervisor disappeared before final receipt; reason unverified. MATLAB completed all 117 endpoints and ended. No process return code is available. Recovered receipt uses observation time as a conservative budget debit. Later runs use detached supervisors. Log: `results/brg/paper_examples/2026-11-17/glider_033/shipped/local/matlab_01.log`.

## Figures and evidence

- glider_033 / shipped: [curves](figures/glider_033_shipped_curves.png), [errors](figures/glider_033_shipped_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/glider_033/shipped/metrics.json).

All bulk observations, dense continuation states and full logs stay local in
ignored `local/` directories. Each completed attempt has a bulk manifest
with reproduction command, file sizes and SHA-256. Compact curves, residuals,
times and logs are committed; figures are in this report folder.

Commands: `python experiments/baselines/brg/run_paper.py --case <case>
--curvature <choice> --detach`, then `summarize_paper_case.py` with the case and curvature arguments,
and `python experiments/baselines/brg/update_paper_report.py`.
Resuming the run command loads each saved data frequency and the last exact
inverse state; all attempts share the case's four-hour limit.

## BEM handoff and next activity

The data layout, signs and field definition are unchanged from the
[activity 01 handoff](../01_run_published_examples/data_handoff.md), with
paper floor counts, the six case/material assignments and the frozen true geometries
recorded here. Our adapter must consume exactly these saved observations.

[Activity 03 draft](../03_adapt_bem_to_brg_data/plan.md) maps the required
plane-wave and full-table extensions onto A1–C12, including variable table
sizes, fixed eta, units, per-shape forward checks and high-k risks. Known eta
below one is already accepted by our core; it is not negative susceptibility.
No BEM solver or shared comparison code has been edited or run.
