# Ordered-boundary Nyström evidence

These are solver/operator measurements from the direct-import
`gpr_bem_kress` sibling solver. They are distinct from the geometry
and manufactured scalar-quadrature metrics under
`results/sdf_boundary_parameterization/`.

## Skim first

The table reports the worst largest-`N` value across the three frequencies in
each checked run. Per-case times include the Kress forward call and a
separately timed raw condition estimate; the whole-run wall time also includes
the independent reference solves.

| Run | Curves | Largest N | Worst receiver error | Worst trace error | Slowest case | Retained core | Whole run | Checks |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| [`quick-20260902`](quick-20260902/summary.md) | exact circle, ellipse, star | 256 | 1.22e-8 | 1.11e-8 | 326.5 ms | 8.00 MiB | 16.04 s | 9/9 pass |
| [`method-b-frozen-20260902`](method-b-frozen-20260902/summary.md) | frozen SDF Method-B circle K=4, ellipse/star K=32 | 256 | 4.79e-9 | 3.56e-9 | 321.6 ms | 8.00 MiB | 18.00 s | 9/9 pass |

Read each linked `summary.md` for the short convergence and runtime tables,
`metrics.csv` for analysis, `metrics.json` for typed records and check details,
and `manifest.json` for exact inputs, source hashes, environment, and artifact
hashes. The raw matrix condition number is mixed-unit and diagnostic; it must
not be used to rank geometries or parameterization methods.

These configured smoke checks are not promotion of the backend. A broader
frequency sweep, reference self-convergence, explicit transmission residuals,
lossy-convention validation (lossy material inputs are currently rejected),
and production-pipeline integration remain open.
No dense matrix, trace, or receiver array is persisted here.

## Relation to the same-SDF solver comparison

These stored tables validate Kress blocks and fields on exact or frozen
curves; they are not the MOD/gprMax comparison table. The integration tests for
smooth circle, ellipse, and star start the MOD and `gpr_bem_kress` branches
from the same callable SDF, then independently build a compressed MOD cloud
and a Method-B `PeriodicCurve2D`. Kress returns the full source-by-receiver
matrix; the 24 paired scan values are its diagonal.

The existing gprMax cache covers only Tx/Rx pair index 0. Consequently, its
table entry is a one-pair relative error at each frequency, not a full-ring
24-pair receiver L2. New
same-scene comparison evidence belongs under `results/solver_comparisons/`,
not in this implementation-convergence directory. The first checked snapshot
is [`kress-peer-20260902/summary.md`](../solver_comparisons/kress-peer-20260902/summary.md).
