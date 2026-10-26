# TA-001: tangent-angle chart replay

The chart gives a lower exact loss in **three of four** saved refusals at
the same recorded step fraction. The exception is the genuine distant
near-touch, aphex at contrast 0.5. This is a finite-map result, not recovery.

## The four answers

| Case | Original minimum | Original speed / mean | Distant gap, mm | Last accepted loss | Chart loss at refused fraction | Decrease |
|---|---|---:|---:|---:|---:|---:|
| aphex c0.5 | Distant near-touch | 0.824236 | 0.481 | 0.005584453 | Physics refused | — |
| aphex c4 | Near-cusp with tiny local loop | 6.12e-8 | 10.310 | 0.142197070 | 0.140972618 | 0.861% |
| aphex c13.3 | Diagonal, cusp-like | 0.044328 | 8.269 | 0.263904466 | 0.234229133 | 11.245% |
| hook c13.3 | Local fold, no distant near-touch | 0.195458 | 12.332 | 0.592447989 | 0.583786234 | 1.462% |

The matched fractions of the bounded proposal are 1/4, 1/128, 1/4 and 1/2.
The chart's corresponding minimum speed / mean is 0.816432, 0.019574,
0.076806 and 0.169883. All three finite-loss trials pass the recorded domain,
area, sampled-speed and sampled-intersection checks, then modal physics.

The best of the already tried fractions is 1/2 for aphex c4 and c13.3:
losses 0.093390605 and 0.218337297, reductions of 34.323% and 17.267%.
These larger successful moves strengthen the local result but do not show
that a fit would choose or retain them.

The hook minimum is off the diagonal by only 0.033267 rad. Its distant gap
is 12.332 mm, so calling it a distant near-touch would be misleading.
Its moderate minimum speed also shows that certificate failure need not
mean an actual near-cusp. The coefficient residual remains part of the cause.

Aphex c13.3's accepted speed / mean was already 0.039766; the refused
trial improves it to 0.044328. A small diagonal minimum describes this
geometry, but does not establish that worsening speed caused the refusal.

## Haibing item 3

All four simple coefficient lower bounds are **inconclusive**, including
on their last accepted curves. The bounds for `|W|²` are -3.18636,
-1.92271, -6.07312 and -6.18745, respectively (see the JSON for exact values).
They cannot certify these non-convex states before the step is attempted.

This supports Haibing's warning about non-convex curves. Failure of this
sufficient bound must not be treated as evidence of invalidity. A useful
near-touch remedy remains necessary for aphex c0.5; positive speed alone
does not preserve injectivity.

## Reconstruction and chart

The NR-001 failure records contain the exact refused coefficients, despite
the original plan saying they were unavailable. We rebuilt C9 proposals
from A1–A4 and B5–B8 at the saved accepted curves and recorded damping.

All four reproduced: maximum pointwise curve error 3.03e-9 mm, maximum
relative error among step norm, maximum normal move and sampled speed ratio
3.51e-9. Saved accepted losses reproduce within 9.82e-14 relative error.
Every original modal refusal also reproduces; its exact loss is unavailable.

The chart stores length, normalized log-speed density, tangent angle and
mean position. Unlike a constant-speed chart, it preserves the accepted
parameter. The chart exponentiates speed and angle increments, solves two
angle corrections for closure, integrates, then crops to the saved band K.

The increment is the original complete B6 Cartesian velocity. Retaining
its tangential gauge makes its normal component and coefficient derivative
match the original map to first order. Removing the tangential part before
cropping would introduce a different first-order approximation.

The closure corrections begin at second order. Central finite differences
at fractions 0.001 and 0.0005 verify the actual map: error falls by about
four, to at most 1.12e-7 relative coefficient error. Zero-step round-trip
error is at most 6.48e-14 mm, below the required 0.001 mm.

Positive speed is guaranteed only before the finite-band crop. We measure
and check the actual stored curve after cropping. The prototype has no
general global closure or injectivity guarantee: aphex c4's full step fails
closure; aphex c0.5's full step self-intersects. Both are preserved in `replay/`.

## Measurements and limits

This uses exactly four saved NR-001 states and their already tried full
steps and halvings: 16 chart trials total, no inverse fits. One fails
construction; 15 reach physics. Ten have lower exact loss, across three cases.

The minimum is located by a 1024-by-1024 torus search and continuous local
refinement using a stable finite sine quotient. These are estimates,
not rigorous lower bounds. Distant gap excludes parameter separations
below pi/4; it is a diagnostic, not a geometric certificate.

Aphex c4 contains a tiny local loop: its divided-difference minimum is
about 2.8e-30 at separation 0.000178 rad. Its continuous speed / mean is
6.12e-8 although the saved sampled max/min ratio is only 84.5. This is a
concrete limit of the existing sampled geometry checks.

CPU cores 6–11, one frequency at a time, single-thread BLAS, no GPU.
Peak resident memory was below 2.5 GB in reconstruction and replay.
Each receipt records load, affinity, BLAS settings, revision and timings;
no speed comparison against the original Mac run is claimed.

## Evidence and reproduction

- [Full numeric table](table.csv), [compact table](table.md), [summary and checks](summary.json).
- `rebuild/`: proposals, exact coefficients, scalar comparisons, original refusals.
- `classification/`: accepted/original minima and coefficient bounds.
- `replay/`: every fraction, closure failure, cropped curve checks and exact loss.
- [aphex c0.5](aphex_twin__c0.5.png), [aphex c4](aphex_twin__c4.png),
  [aphex c13.3](aphex_twin__c13.3.png), [hook c13.3](hook__c13.3.png).

```bash
taskset -c 6-11 env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.geometry_charts.replay rebuild
# Same prefix, then: replay classify; replay replay; report
```

[Plan](../../../../docs/iterations/geometry_charts/iteration_01/03_plan.md),
[driver](../../../../experiments/geometry_charts/replay.py),
[Haibing item 3](../../../../Haibing_directions.md#3-coefficient-based-geometry-safe-region).
The main answer led to the four pre-planned continuation fits.
[They recover 0/4 cases](continuation/README.md), as in NR-001. The chart
remains experimental; those results do not change this saved-step table.
