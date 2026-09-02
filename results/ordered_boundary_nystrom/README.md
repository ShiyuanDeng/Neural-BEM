# Ordered-boundary Nyström evidence

These are solver/operator measurements from the isolated
`gpr_bem_mod.ordered_nystrom` candidate. They are distinct from the geometry
and manufactured scalar-quadrature metrics under
`results/sdf_boundary_parameterization/`.

## Skim first

The table reports the worst largest-`N` value across the three frequencies in
each checked run. Per-case times include the candidate forward call and a
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
