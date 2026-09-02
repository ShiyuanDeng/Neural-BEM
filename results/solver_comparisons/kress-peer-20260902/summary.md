# Same-SDF Kress peer comparison — 2026-09-02

This is the skimmed forward-field acceptance snapshot for the new
`gpr_bem_kress` sibling package. Circle, ellipse, and star use a `161 x 161`
Torch implicit field. The exact same callable independently feeds:

- MOD's implicit-band compression; and
- marching squares, Newton projection, Method B (`M=256`, `K=48`), and a
  `PeriodicCurve2D` with `N=128` for Kress.

All BEM errors below are relative scattered-receiver L2 over the same 24
paired Tx/Rx locations at each frequency. Circle truth is the analytic Mie
series; ellipse/star truth is independent `nystrom_ref` at `N=512`.

## Full-ring receiver error

| Scene | Solver | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4 GHz | 6 GHz | 8 GHz |
|---|---|---:|---:|---:|---:|---:|---:|
| Circle | MOD | 3.24e-4 | 3.55e-3 | 3.42e-2 | 2.98e-2 | 1.57e-1 | 1.80e+0 |
| Circle | Kress | 3.56e-11 | 2.63e-10 | 6.00e-10 | 1.09e-9 | 2.34e-9 | 1.17e-8 |
| Ellipse | MOD | 3.18e-3 | 1.46e-2 | 5.29e-2 | 1.91e-1 | 6.52e-1 | 9.05e-1 |
| Ellipse | Kress | 1.38e-12 | 5.96e-12 | 6.89e-11 | 1.18e-9 | 3.96e-9 | 2.48e-8 |
| Star | MOD | 4.11e-3 | 8.70e-3 | 3.58e-2 | 7.62e-2 | 2.76e-1 | 7.48e-1 |
| Star | Kress | 5.19e-6 | 1.77e-5 | 1.21e-4 | 3.02e-4 | 1.15e-3 | 7.49e-3 |

The ordinary system residual for every Kress cell is below `1.1e-14`. That
confirms the dense solve, but the receiver errors—not the residual—are the
physical acceptance metric. The separate incident-representation leak remains
near machine precision for circle and ellipse but reaches about `4.24e-5` for
the star at 8 GHz. That is a high-frequency geometry/node-refinement warning,
not a linear-system failure, and it remains visible in the JSON diagnostics.

## Common one-pair oracle error

Existing gprMax caches contain only Tx/Rx pair index 0. The following table is
therefore the only common error coverage across all three methods. Each cell is
the scalar relative error for pair 0 at that frequency; it is **not** a
24-receiver L2. The gprMax scene has the same analytic zero set and material
configuration but was generated procedurally out of process, not by evaluating
the Torch callable.

| Scene | Method | 0.5 GHz | 1.5 GHz | 2.5 GHz | 4 GHz | 6 GHz | 8 GHz |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Circle | MOD | 3.41e-4 | 3.59e-3 | 3.19e-2 | 9.59e-3 | 1.86e-1 | 1.80e+0 |
| Circle | Kress | 2.58e-11 | 3.52e-10 | 7.62e-10 | 1.05e-9 | 2.01e-9 | 1.09e-8 |
| Circle | gprMax | 1.04e-2 | 2.33e-2 | 1.88e-2 | 7.66e-2 | 1.09e-1 | 1.73e-1 |
| Ellipse | MOD | 5.72e-3 | 8.47e-3 | 3.27e-2 | 2.47e-1 | 3.43e-2 | 9.72e-1 |
| Ellipse | Kress | 4.54e-12 | 1.43e-11 | 2.76e-11 | 4.87e-10 | 2.71e-10 | 4.78e-9 |
| Ellipse | gprMax | 8.39e-3 | 1.86e-2 | 2.27e-2 | 1.03e-1 | 2.70e-2 | 3.08e-1 |
| Star | MOD | 4.13e-3 | 1.35e-2 | 8.45e-2 | 5.91e-2 | 2.32e-1 | 5.86e-1 |
| Star | Kress | 4.91e-6 | 2.91e-5 | 2.09e-4 | 3.82e-4 | 1.43e-3 | 4.26e-3 |
| Star | gprMax | 3.46e-3 | 1.37e-2 | 8.91e-2 | 8.31e-2 | 2.00e-2 | 2.85e-1 |

## Runtime

The BEM times are from one thread-limited aggregate run and cover the complete
six-frequency sweep; gprMax times are provenance loaded from the existing
caches. They are useful magnitudes, not a formal benchmark.
MOD and Kress solve 24 right-hand sides and materialize a full `24 x 24`
receiver matrix before selecting the 24 paired entries. Kress additionally
evaluates an incident-representation consistency leak. Cached gprMax time is
the total for six frequencies, with a target and matched-background execution
at every frequency (12 one-pair FDTD executions), so no speedup ratio is valid
across that column.

| Scene | Method | SDF/boundary prep | Forward sweep | End to end | Receiver work |
|---|---|---:|---:|---:|---|
| Circle | MOD | 0.01 s | 2.05 s | 2.05 s | full 24 x 24 |
| Circle | Kress | 0.68 s | 0.37 s | 1.04 s | full 24 x 24 |
| Circle | gprMax cache | — | — | 124.83 s | 1 pair |
| Ellipse | MOD | 0.01 s | 1.07 s | 1.08 s | full 24 x 24 |
| Ellipse | Kress | 0.62 s | 0.37 s | 1.00 s | full 24 x 24 |
| Ellipse | gprMax cache | — | — | 133.28 s | 1 pair |
| Star | MOD | 0.01 s | 1.61 s | 1.62 s | full 24 x 24 |
| Star | Kress | 0.58 s | 0.29 s | 0.87 s | full 24 x 24 |
| Star | gprMax cache | — | — | 127.07 s | 1 pair |

## Reproduction and verdict

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py -s -q
```

The final aggregate exporter passed (`1 passed` in `42.52 s`; `43.93 s`
process wall time) and regenerated the ignored working report at
`results/solver_comparisons/current/aggregate_metrics.md`, plus per-scene JSON,
field arrays, geometry plots, and Kress-curve samples. The focused run passed
all three Kress field gates plus two cache-coordinate contract tests
(`5 passed` in `30.72 s`). These acceptance gates cover all six frequencies,
including the explicitly looser high-frequency star thresholds.

For the supported smooth, one-component, lossless cases, Kress is the preferred
forward discretization: it is decisively more accurate than MOD at every tested
frequency and its measured end-to-end time is lower in this run despite the
additional incident-representation check. The star's error growth with
frequency shows why the geometry/bandwidth and node-refinement studies remain
acceptance requirements.
This result does not make Kress operational or adjoint-ready: it remains out of
`solver_select`, and its geometry/system/receiver shape derivatives still need
finite-difference and adjoint-gradient validation.
