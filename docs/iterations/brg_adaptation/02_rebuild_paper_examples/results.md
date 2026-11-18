# Rebuild the paper's single-component examples: results

## Handoff update, 18 November 2026

The coordinator accepted all six k=15 outcomes and their evidence. Do not
resume to k=30 while CSI runs its overnight campaign. Glider eta 0.33 already
has all 117 states; the other five need only missing data/states on a later
authorized resume. Retained data counts are 117, 117, 108, 57, 57, 57 for
glider 0.33, glider 10, star full, star limited, cavity 0.9 and cavity 2.
The no-limit glider alternative stopped at k=12.75 and must never resume.

The Figure 1 gap remains unexplained; both curvature choices were identical
and the coordinator accepted the lower rebuilt errors. Spend no more runs
on it. Cavity eta 2's k=30 finer-grid check remains deferred; glider eta 10's
check passed. Every case's original four-hour budget includes prior attempts.
`completion_k15.json` records all retained data times; the older metric named
`all_saved_data_generation_seconds` only sums the current data-summary range.

Activity 03's one-fit handover is accepted and BEM work is transferred to the
BEM side. The activity 04 hold mentioned in this historical report was later
lifted for the baseline half only; its provisional TG-002 campaign is now
running. See activity 04's State at handoff; do not launch another campaign.

## Status

Campaign started 17 November 2026. 6/6 cases complete through k=15.
This report is updated after each run. The full case budget is four hours,
including data and all attempts; the optional glider alternative shares it.
These are rebuilt paper cases, distinct from activity 01's shipped example.

## Actual settings and provenance

The [plan](plan.md) records the coordinator's decisions and all differences
between paper prose and public code. All current endpoints use k=1:0.25:15, known eta,
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

| Case / curvature | Frequencies | Last k | Relative area error | Field residual | Iterations | Data min | Inverse min | Process min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| glider_033 / shipped | 57/57 | 15 | 0.0517798% | 1.65792e-05 | 203 | 2.20 | 8.24 | 68.52 |
| glider_10 / shipped | 57/57 | 15 | 0.00362365% | 1.16845e-06 | 335 | 2.16 | 14.40 | 35.03 |
| star_full / shipped | 57/57 | 15 | 0.523044% | 0.000816685 | 592 | 2.30 | 89.27 | 103.86 |
| star_limited / shipped | 57/57 | 15 | 0.805104% | 0.000335598 | 535 | 2.41 | 76.28 | 78.83 |
| cavity_09 / shipped | 57/57 | 15 | 134.196% | 0.846008 | 102 | 8.70 | 10.96 | 19.79 |
| cavity_2 / shipped | 57/57 | 15 | 134.087% | 0.762657 | 129 | 8.62 | 45.21 | 54.00 |

The coordinator shortened the active campaign to k=15. The completed
glider eta 0.33 full sweep and all higher-frequency data/states are retained.
Resumes to k=30 are low priority and require an otherwise idle machine or
a coordinator request. Phase columns below cover only k<=15; process time
includes any already-spent higher-frequency work.

The paper’s section 4.3 reports that its obstacle solver fails to resolve
the cavity at both contrasts. Our large cavity errors agree with that
qualitative outcome; they do not establish identical reconstructions. See
the [paper](https://arxiv.org/pdf/2210.11607) and the source panels below.

Both star endpoints closely follow the recovered true curve at k=15,
as the paper’s obstacle panels show qualitatively. The k=1 outlines differ
visibly from the paper’s plotted outlines. These rebuilt cases therefore
provide a reproducible public-code check, not an exact reproduction of the
authors’ unavailable experiment drivers. No extra tuning run was made.

Process time includes MATLAB startup and I/O; data and inverse columns
measure those phases separately. Fine-grid checks, when present, are listed
below and included in process time. Per-frequency records retain k,
iterations, residual history, exit flag, time and curve.

- glider_033 / shipped: UTC 2026-11-17T20:16:16.608701+00:00 to 2026-11-17T21:24:47.514919+00:00; 57 newly generated data frequencies.
  Process time is a conservative upper bound because the terminal supervisor was lost; phase times remain measured.
- glider_10 / shipped: UTC 2026-11-17T21:33:15.946290+00:00 to 2026-11-17T22:08:18.060887+00:00; 57 newly generated data frequencies.
- star_full / shipped: UTC 2026-11-17T21:49:26.601598+00:00 to 2026-11-17T23:33:51.533206+00:00; 57 newly generated data frequencies.
- star_limited / shipped: UTC 2026-11-17T22:04:28.037267+00:00 to 2026-11-17T23:23:18.045784+00:00; 57 newly generated data frequencies.
- cavity_09 / shipped: UTC 2026-11-17T22:04:28.062807+00:00 to 2026-11-17T22:24:15.773264+00:00; 57 newly generated data frequencies.
- cavity_2 / shipped: UTC 2026-11-17T22:04:28.080930+00:00 to 2026-11-17T22:58:28.302750+00:00; 57 newly generated data frequencies.

Resource monitor: minimum observed available memory 18.18 GiB; maximum observed MATLAB process count 5. Samples are every 10 s, from 2026-11-17T22:10:20.755251+00:00. The required reserve is 14 GB. [Resource log](../../../../results/brg/paper_examples/2026-11-17/resource_monitor_k15.jsonl).

## Curvature comparison

Frozen choice: **shipped**. Both candidates have bit-for-bit identical relative area errors for all 37 Figure 1 frequencies. Retain the published shipped-driver values in this tie. Neither candidate matches Figure 1; no further tuning is authorized.

- glider_033 / shipped: Figure 1 k<=10 RMS log10 difference 0.904393; median absolute difference 0.728363; k=10 area-error ratio 0.41022.
- glider_10 / shipped: Figure 1 k<=10 RMS log10 difference 0.827051; median absolute difference 0.520904; k=10 area-error ratio 0.523732.

The predeclared trigger is RMS above 0.30 decades or endpoint disagreement
above a factor of two. Exactly one no-limit glider alternative is allowed
if triggered; choose the lower RMS distance and retain both. The purpose is to
reproduce the published result; the closer candidate may still disagree.
No other case is tuned.

[Figure 1 comparison](figures/glider_033_figure1_comparison.png) shows both permitted candidates when available.

The coordinator stopped the no-limit alternative after 48 completed
frequencies (through k=12.75): its question was already answered by identical
errors at all 37 Figure 1 frequencies. Its partial record is retained and
must not be resumed. The coordinator accepted the paper gap because rebuilt
BRG has lower errors throughout the plotted range and is not handicapped.
No more runs will be spent on this gap.

Reading alone leaves three unconfirmed candidate causes:

1. The authors' actual example drivers are absent. The public filter sequence
   and candidate acceptance differ from the printed algorithm, independently
   of the curvature restriction that this comparison ruled out.
2. Initial node counts, the 300-node update minimum and frequency-start
   resampling are not fully specified in the paper. Public behavior may
   differ from the private experiment's discretization and parameterization.
3. The paper defines a relative polygon set-difference error but supplies no
   scoring code, polygon resolutions or numerical Figure 1 arrays. Its
   post-processing or normalization may differ from our documented symmetric
   difference divided by the 2,048-point true-polygon area. The vector axis
   calibration was checked; no axis-reading error has been found.

These are possibilities, not diagnoses or reasons to change the campaign.

## Numerical checks and failures

- glider_033 / shipped: maximum interior-source diagnostic 7.34431e-07; exit flags {'2': 57}.
- glider_10 / shipped: maximum interior-source diagnostic 1.78275e-06; exit flags {'3': 4, '2': 13, '1': 40}.
- star_full / shipped: maximum interior-source diagnostic 0.000501696; exit flags {'2': 17, '3': 4, '-1': 36}.
- star_limited / shipped: maximum interior-source diagnostic 0.000501696; exit flags {'2': 16, '3': 4, '-1': 37}.
- cavity_09 / shipped: maximum interior-source diagnostic 1.49366e-07; exit flags {'-1': 56, '2': 1}.
- cavity_2 / shipped: maximum interior-source diagnostic 2.26727e-07; exit flags {'-1': 57}.
- glider_10: k=30 data grid 3412 versus 6824 nodes; relative complex-field difference 8.21949e-12; check time 144.120 s.
- Cavity eta 2: the k=30 finer-grid check is deferred with the coordinator’s k=30 hold; it has not been performed.

Exit 1 means residual stop; 2 update stop; 3 iteration limit; -1 means
the public update returned a failure code (including filtered-step failure),
not proof that the accepted final curve intersects itself. The manufactured
source is verified inside each true curve and is diagnostic only.

All 342 target-frequency records have finite saved curves and residual
histories. Their data files and exact continuation states are present. No
NaN/Inf or crash message was found in the completed MATLAB logs; the known
zero-gradient failure was not observed. Every case stayed within four hours.
[Completion check](../../../../results/brg/paper_examples/2026-11-17/completion_k15.json).

- glider_033/default/attempt_01.json: coordinator stop/redirect, not a numerical crash; return code -15; log `results/brg/paper_examples/2026-11-17/glider_033/default/local/matlab_01.log`.
- glider_033/shipped/attempt_01.json: Terminal-launched supervisor disappeared before final receipt; reason unverified. MATLAB completed all 117 endpoints and ended. No process return code is available. Recovered receipt uses observation time as a conservative budget debit. Later runs use detached supervisors. Log: `results/brg/paper_examples/2026-11-17/glider_033/shipped/local/matlab_01.log`.
- glider_10/shipped/attempt_01.json: coordinator stop/redirect, not a numerical crash; return code -15; log `results/brg/paper_examples/2026-11-17/glider_10/shipped/local/matlab_01.log`.
- star_full/shipped/attempt_01.json: coordinator stop/redirect, not a numerical crash; return code -15; log `results/brg/paper_examples/2026-11-17/star_full/shipped/local/matlab_01.log`.

## Figures and evidence

Paper source panels for visual comparison: [star](figures/paper_star_reference.png) and [cavity](figures/paper_cavity_reference.png). These are direct PDF renders, not inputs to curve recovery. The obstacle-solver panels contain the paper’s k=1, 15 and 30 curves; our endpoint figures stop at the currently requested k=15.

- glider_033 / shipped: [curves](figures/glider_033_shipped_k15_curves.png), [errors](figures/glider_033_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/glider_033/shipped/metrics_k15.json).
- glider_10 / shipped: [curves](figures/glider_10_shipped_k15_curves.png), [errors](figures/glider_10_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/glider_10/shipped/metrics_k15.json).
- star_full / shipped: [curves](figures/star_full_shipped_k15_curves.png), [errors](figures/star_full_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/star_full/shipped/metrics_k15.json).
- star_limited / shipped: [curves](figures/star_limited_shipped_k15_curves.png), [errors](figures/star_limited_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/star_limited/shipped/metrics_k15.json).
- cavity_09 / shipped: [curves](figures/cavity_09_shipped_k15_curves.png), [errors](figures/cavity_09_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/cavity_09/shipped/metrics_k15.json).
- cavity_2 / shipped: [curves](figures/cavity_2_shipped_k15_curves.png), [errors](figures/cavity_2_shipped_k15_errors.png), [metrics](../../../../results/brg/paper_examples/2026-11-17/cavity_2/shipped/metrics_k15.json).

All bulk observations, dense continuation states and full logs stay local in
ignored `local/` directories. Each completed attempt has a bulk manifest
with reproduction command, file sizes and SHA-256. Compact curves, residuals,
times and logs are committed; figures are in this report folder.

Commands: `python experiments/baselines/brg/run_paper.py --case <case>
--curvature shipped --max-k 15 --detach`, then
`python experiments/baselines/brg/summarize_paper_case.py --case <case>
--curvature shipped --max-k 15`, and
`python experiments/baselines/brg/update_paper_report.py --max-k 15`.
Resuming the run command loads each saved data frequency and the last exact
inverse state; all attempts share the case's four-hour limit.

## BEM handoff and next activity

The data layout, signs and field definition are unchanged from the
[activity 01 handoff](../01_run_published_examples/data_handoff.md), with
paper floor counts, the six case/material assignments and the frozen true geometries
recorded here. Our adapter must consume exactly these saved observations.

[Activity 03 report](../03_adapt_bem_to_brg_data/results.md) records the implemented
plane-wave and full-table extensions onto A1–C12, including variable table
sizes, fixed eta, units, per-shape forward checks and high-k risks. Known eta
below one is already accepted by our core; it is not negative susceptibility.
The CPU table adapter is implemented and the paired default regression is bit-identical.
One BEM glider fit reached k=10 and refused k=12 under the unchanged
cancellation check. Shared comparison code was not edited.
The [activity 04 plan](../04_run_brg_on_tg002_shapes/plan.md) proposes the main
BRG table on TG-002 shapes; it was pushed before the ownership hold and is
now held. No activity 04 run has started.
