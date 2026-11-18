# Run BRG without the curvature limit: provisional control

## Status and settings

Started 2026-11-18T02:28:20.793603+00:00; queue state `running`;
16/20 cases have scores. Last update: 2026-11-18T02:56:47.937199+00:00.
These are **provisional BRG-forward data**, identical to activity 04 by
SHA-256. This is the control row alongside its shipped-limit row.

The [plan](plan.md) records the coordinator's decision. The only inverse
change is removing the curvature constraint with the wrapper's existing
switch: it omits `eps_curv` and the inactive `n_curv_min` parameter.
The public default `eps_curv=Inf` never rejects on curvature. Self-intersection
checks remain. Same 37 frequencies, one centred unit-disk start, known
contrast, update bands, eight threads, public stops/filter and patches 03/04.
No BEM run or edit. No new upstream patch. Every case starts afresh.

The original data files are read in place, with no data generation. Each
`data_reuse.json` records their paths and SHA-256 plus the geometry-input
hash; the runner verifies hashes before fitting. Original data-generation
cost is retained in metrics as `reused_data_generation_seconds`; new data
cost is zero. The resource monitor raised the BRG ceiling from four to six
at 02:40 UTC and to eight at 02:51 UTC, only while CSI stays held; the policy applies at
new launch boundaries, without changing active fits.
The queue overlaps other work, so times are indicative.

Scoring follows unchanged protocol 1, with all components, no fitted
alignment, raw set-difference area divided by true area and known-contrast
error. Final-curve residuals use all 37 observations. Both rows stay
provisional until the BEM side freezes and checks the shared data.

## Results against the shipped curvature limit

Area errors are raw fractions, not percentages. Each case links to its
compact metrics and figure. No new success cutoff is selected.

| Case | State | Frequencies | 04 area | 05 area | 04 max residual | 05 max residual | Inverse s | Residual s | Score s | Case wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kite__c0.5 | complete | 37/37 | 0.47527995 | 0.33866574 | 0.390121 | 0.205149 | 338.74 | 27.39 | 2.20 | 374.85 |
| asymmetric__c4 | complete | 37/37 | 0.27669129 | 0.43916114 | 0.893277 | 1.17113 | 600.67 | 35.14 | 2.58 | 654.67 |
| asymmetric__c0.5 | complete | 37/37 | 0.11053017 | 0.005359107 | 0.133603 | 0.000625268 | 293.03 | 19.79 | 2.04 | 321.55 |
| kite__c4 | complete | 37/37 | 0.46463161 | 0.54391802 | 0.861585 | 1.03227 | 242.05 | 8.67 | 2.34 | 259.70 |
| peanut__c0.5 | complete | 37/37 | 0.11768157 | 0.0068889169 | 0.116288 | 0.000871915 | 242.06 | 13.54 | 1.88 | 264.24 |
| peanut__c4 | complete | 37/37 | 0.50390252 | 0.17578467 | 1.30272 | 0.916535 | 241.24 | 8.31 | 2.16 | 258.57 |
| c_shape__c4 | complete | 37/37 | 0.44474779 | 0.16654318 | 0.891051 | 0.753086 | 282.80 | 8.59 | 2.46 | 300.58 |
| hook__c4 | complete | 37/37 | 0.52228048 | 0.1848404 | 0.940662 | 0.770997 | 258.31 | 8.47 | 2.40 | 275.78 |
| cross__c4 | complete | 37/37 | 0.24642363 | 0.24041865 | 0.81336 | 0.88416 | 227.92 | 8.34 | 2.31 | 245.36 |
| aphex_twin__c0.5 | complete | 37/37 | 0.80147523 | 0.64108951 | 0.559174 | 0.503557 | 385.48 | 8.19 | 2.33 | 402.74 |
| aphex_twin__c4 | complete | 37/37 | 0.89878857 | 1.0626189 | 0.979737 | 1.05886 | 194.53 | 8.23 | 2.68 | 211.91 |
| star__c0.5 | complete | 37/37 | 0.0025279893 | 0.0024260803 | 2.80675e-05 | 2.90794e-05 | 292.63 | 30.15 | 2.17 | 331.92 |
| star__c4 | complete | 37/37 | 0.00039247399 | 0.17542513 | 3.11609e-06 | 0.739178 | 395.46 | 8.61 | 2.53 | 414.96 |
| c_shape__c0.5 | complete | 37/37 | 0.052557715 | 0.0015837012 | 0.0537632 | 1.67175e-05 | 371.38 | 31.29 | 2.17 | 415.74 |
| hook__c0.5 | complete | 37/37 | 0.57706138 | 0.64609499 | 0.480827 | 0.531757 | 336.81 | 8.47 | 2.44 | 354.34 |
| circle__c0.5 | complete | 37/37 | 2.3469481e-08 | 2.3469481e-08 | 1.03264e-10 | 1.03264e-10 | 83.83 | 15.38 | 2.12 | 108.32 |

## Time, limits and saved-output checks

Kite eta 0.5 pilot: 374.85 s. It ran alone before the rest.

Aggregate case wall time: 86.59 min. New data-generation time: zero.

Minimum sampled available memory: 29.86 GiB; maximum simultaneous control workers: 6. Each launch checks fresh shared memory, reserves at least 3 GiB for the new BRG fit and retains the 14 GiB floor plus 2 GiB margin, allowing for other queues and B1 reservations. The guard delays starts; it never kills running fits.

- kite__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/kite__c0.5/metrics.json), [figure](figures/kite__c0.5.png).
- asymmetric__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/asymmetric__c4/metrics.json), [figure](figures/asymmetric__c4.png).
- asymmetric__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/asymmetric__c0.5/metrics.json), [figure](figures/asymmetric__c0.5.png).
- kite__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/kite__c4/metrics.json), [figure](figures/kite__c4.png).
- peanut__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/peanut__c0.5/metrics.json), [figure](figures/peanut__c0.5.png).
- peanut__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/peanut__c4/metrics.json), [figure](figures/peanut__c4.png).
- c_shape__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/c_shape__c4/metrics.json), [figure](figures/c_shape__c4.png).
- hook__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/hook__c4/metrics.json), [figure](figures/hook__c4.png).
- cross__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/cross__c4/metrics.json), [figure](figures/cross__c4.png).
- aphex_twin__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/aphex_twin__c0.5/metrics.json), [figure](figures/aphex_twin__c0.5.png).
- aphex_twin__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/aphex_twin__c4/metrics.json), [figure](figures/aphex_twin__c4.png).
- star__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/star__c0.5/metrics.json), [figure](figures/star__c0.5.png).
- star__c4: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/star__c4/metrics.json), [figure](figures/star__c4.png).
- c_shape__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/c_shape__c0.5/metrics.json), [figure](figures/c_shape__c0.5.png).
- hook__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/hook__c0.5/metrics.json), [figure](figures/hook__c0.5.png).
- circle__c0.5: saved-output check passed; [metrics](../../../../results/brg/tg002_no_curvature/2026-11-18/circle__c0.5/metrics.json), [figure](figures/circle__c0.5.png).

Completed attempt receipts also record peak other simultaneous BRG/B1 fits, distinct overlapping fit receipts, and original MATLAB snapshots. Counts use saved process intervals; BRG intervals include residual evaluation. No B1 files are changed.

## Frequency-ending rejection codes

The first two columns count the selected final geometry/filter code on rejected frequency exits. The last counts final iteration ier -5. They overlap: the public routine replaces geometry rejection by -5 when the old residual is kept. Counts come only from existing logs; each case retains full codes and log hashes.

| Case | Final filter ier 2 | Final filter ier 1 | Final iteration ier -5 |
|---|---:|---:|---:|
| kite__c0.5 | 0 | 24 | 37 |
| asymmetric__c4 | 0 | 34 | 37 |
| asymmetric__c0.5 | 0 | 0 | 31 |
| kite__c4 | 0 | 35 | 37 |
| peanut__c0.5 | 0 | 0 | 34 |
| peanut__c4 | 0 | 36 | 37 |
| c_shape__c4 | 0 | 33 | 37 |
| hook__c4 | 0 | 36 | 37 |
| cross__c4 | 0 | 33 | 37 |
| aphex_twin__c0.5 | 0 | 28 | 37 |
| aphex_twin__c4 | 0 | 37 | 37 |
| star__c0.5 | 0 | 0 | 5 |
| star__c4 | 0 | 32 | 36 |
| c_shape__c0.5 | 0 | 0 | 13 |
| hook__c0.5 | 0 | 34 | 36 |
| circle__c0.5 | 0 | 0 | 6 |

## Interpretation and next step

The first case, kite at contrast 0.5, reduced area error from 47.53% to 33.87% and maximum final residual from 0.3901 to 0.2051 in 374.85 s. It still failed to recover the shape. Its saved curve has loops and ripples; unchanged scoring reports a repaired ring and two components. There were no terminal curvature rejections, but 24 terminal self-intersection rejections and 37 final iteration ier -5 codes. The saved checks and settings review passed; the remaining cases were released without a supervisor restart. See `PILOT_REVIEW.json`.

Interpretation remains partial until the queue ends. All failed or user-stopped cases remain in the record.

Bulk observations remain in activity 04. Fresh exact states and logs stay local with SHA-256 manifests. Source snapshots, order, overlap and receipts are retained. Shared-data qualification and BEM rows belong to the BEM side. Any further tuning or experiment needs a new coordinator decision.
