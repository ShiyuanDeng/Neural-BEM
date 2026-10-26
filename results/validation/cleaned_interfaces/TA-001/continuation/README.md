# TA-001 continuation: no new recoveries

The four fresh chart fits recover **0/4 cases**, the same as NR-001.
The saved-step success does not transfer to a complete recovering trajectory.
Keep this chart experimental; the result does not support a default change.

## Quality and stopping

| Case | NR RMS mm | Chart RMS mm | Chart Hausdorff upper mm | Maximum residual | Final check | Chart stop |
|---|---:|---:|---:|---:|---|---|
| aphex c0.5 | 3.953 | 7.874 | 22.895 | 1.336 | pass | stage_1_damped |
| aphex c4 | 5.266 | 5.940 | 16.638 | 1.896 | pass | stage_2_damped |
| aphex c13.3 | 4.283 | 5.975 | 15.089 | 1.798 | fail | stage_2_damped |
| hook c13.3 | 8.281 | 6.193 | 23.409 | 1.185 | fail | release_M15 |

Every fit ends with `NUMERICAL_FAILURE` on a trial curve. NR-001 stopped
at stage_3_damped, stage_2_damped, stage_4_undamped and release_M11,
respectively. All four NR-001 final checks failed.

The unchanged recovery requirements are RMS <=1 mm, Hausdorff upper
<=2 mm, every relative frequency residual <=0.003 and a passed final check.
Passing a numerical check on a returned accepted curve is not recovery.

Hook reaches a later shape release and improves RMS by 25.21%, but its
returned curve contains visible ripples. Its maximum production/refined
field difference is 5.76%; its full-trial difference is 6.88%. The endpoint
is not numerically qualified. Aphex c13.3 fails field agreement as well.
Hook also uses 2,152 fit work units versus NR-001's 695. The RMS improvement
therefore comes with about three times the work and no qualified recovery.

## What fails now

Analysis of the saved failed chart candidates uses no additional physics.
All four have off-diagonal divided-difference minima and adequate speed:

| Case | Minimum separation rad | Minimum speed / mean | Distant gap mm | Physics message |
|---|---:|---:|---:|---|
| aphex c0.5 | 1.998 | 0.726 | 0.118 | coefficient residual 2.88 |
| aphex c4 | 0.995 | 0.607 | 0.245 | >4000 Chebyshev terms |
| aphex c13.3 | 2.412 | 0.231 | 1.127 | >4000 Chebyshev terms |
| hook c13.3 | 1.276 | 0.567 | 6.799 | coefficient residual 1.07 |

The chart avoids a speed collapse in these particular failed trials.
It still permits distant boundary parts to approach. Hook's 6.799 mm
gap also cautions against treating every certificate failure as an actual
self-touch: the approximation/certificate remains part of the limitation.

This sharpens D08 and Haibing item 3. Positive speed addresses one failure
mechanism, while the full trajectories still require nonlocal separation
control and accurate coefficient geometry. The simple Wiener bound is
already inconclusive on all four original accepted states.

The concrete next proposal is a nonlocal divided-difference or self-touch
barrier around the actual stored trial curve, together with investigation
of the hook's high-frequency geometry. No such barrier or extra fit was run.
Haibing's Möbius-energy and algebraic-barrier references remain relevant.

## Settings, validation and resources

Exactly four centred TG-002 fits, one per planned case, with default
`CumulativePolicy()` (13,412 work units, 1,800 s allowance), modal Müller
CUDA physics and no localization. No control reruns, retries or searches.
The adapter stays under `experiments/geometry_charts/`.

The actual chart derivative is its spectral B6 tangent basis. All four
wrapper zero steps are coefficient-exact; central finite-difference errors
are <=2.26e-9 relative. The known failed closure becomes `UpdateRefused`
and can backtrack. The four fits themselves encounter no closure refusals.

The standard independent final check uses the actual chart adapter.
Truth is first read after it returns. Existing TG-002 scoring and recovery
limits are unchanged. No maintained solver code was edited.

| Case | Fit work units | Fit seconds | Total numerical seconds |
|---|---:|---:|---:|
| aphex c0.5 | 28 | 1.043 | 1.977 |
| aphex c4 | 65 | 1.246 | 2.066 |
| aphex c13.3 | 152 | 5.957 | 9.092 |
| hook c13.3 | 2152 | 124.688 | 133.471 |

One frequency worker, CPU B6 preparation, cores 6–11 and single-thread
BLAS. GPU: exclusive RTX 5090, PyTorch allocator limited to 5 GiB.
Maximum CPU resident memory 3,250 MiB; GPU reserved memory 1,806 MiB.
Recorded one-minute load averages at completion range from 0.56 to 1.25.

These timings describe this machine only. NR-001's Mac CPU controls are
used for recovery and geometry comparison, not as a speed comparison.

A JSON tuple/list settings mismatch stopped the first command before any
fit or case folder was created. Its log is preserved as
`aphex_twin__c0.5_preflight_failure.log`; normalizing settings fixed the
driver. This did not add a fifth fit.

## Evidence

- [Full comparison](comparison.csv), [comparison JSON](comparison.json),
  [failed-candidate geometry](refused_geometry.json), [endpoint figure](endpoints.png).
- [Adapter checks](adapter_checks.json), [four-case summary](chart/summary.json).
- `chart/runs/<case>/`: plans, accepted states, trials, failure coefficients,
  returned curve, final check, score, environment and resource receipts.
- [Continuation plan](../../../../../docs/iterations/geometry_charts/iteration_02/03_plan.md),
  [adapter](../../../../../experiments/geometry_charts/adapter.py),
  [driver](../../../../../experiments/geometry_charts/continuation.py).
- [Main saved-step answer](../README.md),
  [Haibing item 3](../../../../../Haibing_directions.md#3-coefficient-based-geometry-safe-region).
