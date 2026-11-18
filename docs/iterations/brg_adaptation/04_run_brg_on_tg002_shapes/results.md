# Run BRG on TG-002 shapes: provisional baseline results

## Status and ownership

Campaign started 2026-11-17T23:41:28.138975+00:00; 5/20 cases have saved scores.
All data and results here are **provisional BRG-forward data**. The BEM side
owns generating and freezing the shared plane-wave data. These are TG-002
shapes with BRG-style observations, not the sealed TG-002 measurements.
No BEM forward, BEM fit or solver edit was performed in this activity.

The [approved plan](plan.md) records the pilot rule and all choices. The
[single data request](../../../../results/brg/tg002_shapes/2026-11-17/data_request.json)
contains the 37 exact k values, layouts, units, signs, eta values and all ten
true coefficient arrays with source and coefficient hashes. The BEM-side
cross-solver checks and inverse sections remain unexecuted here.

## Actual settings and scoring

Pinned upstream `bda24bddbf4562497280b671bc174ef891b47c6b`, approved patches
03/04, seven-argument RLA call. No new upstream patch. MATLAB R2026a,
8 compute threads per process, with concurrent CSI fits. Times are indicative.
Known eta 0.5 or 4, equal density, unit-amplitude plane waves, finite-radius
scattered fields, negative time convention and outgoing Hankel first kind.

37 frequencies preserve TG-002's 19 labels and add midpoints: exterior
k=0.834234519 to 8.342345186. Each has floor(10k) directions and receivers
on radius 10. One centred unit-disk start; lengths are divided by 65 mm.
Frozen target offsets and rotations remain. Data use 100 exterior points
per wavelength and inversion 70, with public resolution behavior.

The shipped curvature values 0.1 / minimum band 20, better-of-GN/SD,
Gaussian filter, 50 iterations and 1e-5 residual/update stops are unchanged.
No added zero-gradient guard or tuning run. Every inverse frequency saves
its curve, residual history, iterations, exit flag, time and exact state.

Scoring imports `experiments.comparison.scoring` protocol version 1 unchanged.
All components are retained; no alignment is fitted. Returned uniform-
parameter nodes define a Fourier interpolant without truncation or smoothing.
Coordinates return to the benchmark's 50 mm units; truth uses 16,384 samples,
with its existing 201-by-201 material grid and boundary scoring functions.
The table's area error is the raw symmetric-difference area divided by true
area (not percent). Signed susceptibility and known-contrast scores are saved.

Residuals are recomputed on the returned curve at its own saved resolution
for all 37 frequencies, using BRG's forward. The table gives their maximum,
not the history of curves from earlier frequencies. The unchanged clean
residual limit is 0.003; added midpoints are never passed as sealed labels.
This final-curve evaluation has its own time column. No BEM solve is involved.

## Results

| Case | State | Frequencies | Raw area error | Max final residual | Data s | Inverse s | Residual check s | Score s | Case wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| asymmetric__c4 | complete | 37/37 | 0.27669129 | 0.893277 | 19.79 | 717.43 | 25.92 | 2.47 | 771.81 |
| asymmetric__c0.5 | complete | 37/37 | 0.11053017 | 0.133603 | 20.99 | 386.54 | 20.33 | 2.32 | 436.54 |
| circle__c0.5 | complete | 37/37 | 2.3469481e-08 | 1.03264e-10 | 18.88 | 91.08 | 16.53 | 2.28 | 134.82 |
| circle__c4 | complete | 37/37 | 2.0352808e-06 | 4.87606e-10 | 18.19 | 58.54 | 18.51 | 2.15 | 103.57 |
| kite__c0.5 | complete | 37/37 | 0.47527995 | 0.390121 | 13.07 | 205.36 | 8.88 | 2.35 | 235.83 |

## Timed pilot and forecast

Asymmetric eta=4: data 19.79 s, inversion
717.43 s, final residual evaluation 25.92 s,
scoring/figure 2.47 s; complete case 771.81 s.
The pilot passes the 900-second continuation rule.
Twenty times its measured phase costs gives data 6.60 min,
inverse 239.14 min and residual checks
8.64 min; aggregate case wall forecast
257.27 min before parallelism. This is a one-shape estimate, not a
promise for thin strokes or deep concavities. No case is rerun to tune it.

Completed-case aggregate wall time: 28.04 min across 5 cases. A running-mean projection for all 20 is 112.17 min before parallelism; the still-unrun difficult shapes make this uncertain.

Memory: minimum observed available 21.57 GiB; maximum active BRG workers 2. The required reserve is 14 GB. Start/end CSI/MATLAB overlap is retained in each attempt.

## Checks, failures and evidence

- asymmetric__c4: maximum data-geometry resampling point error 1.66371e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/asymmetric__c4/metrics.json), [curve](figures/asymmetric__c4.png).
  Wrapper failure: Python 3.10 lacks hashlib.file_digest; MATLAB and scoring completed. Receipt repaired with streaming SHA-256; no numerical rerun. See `supervisor_failure.log` in this case folder.
- asymmetric__c0.5: maximum data-geometry resampling point error 1.66371e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/asymmetric__c0.5/metrics.json), [curve](figures/asymmetric__c0.5.png).
- circle__c0.5: maximum data-geometry resampling point error 1.81942e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/circle__c0.5/metrics.json), [curve](figures/circle__c0.5.png).
- circle__c4: maximum data-geometry resampling point error 1.81942e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/circle__c4/metrics.json), [curve](figures/circle__c4.png).
- kite__c0.5: maximum data-geometry resampling point error 1.80062e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/kite__c0.5/metrics.json), [curve](figures/kite__c0.5.png).

The frozen-input geometry checks verify source hashes, agreement with the
benchmark's scene definitions, positive orientation, closure, simple curves,
nonzero speed and the 65 mm start. Data resampling errors are measured against
the exact coefficients at the public resampler's returned parameters.

Compact results are committed by batch. Bulk fields, continuation states and
logs remain ignored locally with reproduction commands and SHA-256 manifests.
See [campaign receipt](../../../../results/brg/tg002_shapes/2026-11-17/campaign.json)
and [geometry checks](../../../../results/brg/tg002_shapes/2026-11-17/geometry_checks.json).

## Frozen-data replacement and handoff

Frozen BEM-side observations do not yet exist and were not compared here.
The agreed relative complex-field tolerance is max(1e-5, ten times measured
BRG refinement error); refinement error above 1e-4 returns to the coordinator.
Compare every frequency after units/order/signs are matched. Rerun only cases
whose fields differ beyond that threshold. Preserve these provisional results.
Both BEM rows and cross-solver checks belong to the separate BEM coordinator.
Paper k=30 resumes remain deferred while CSI runs overnight.
