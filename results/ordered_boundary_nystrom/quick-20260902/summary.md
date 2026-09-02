# Ordered-boundary Nyström validation

This run contains actual Müller operator, direct-solve, and off-surface receiver errors. It is not a geometry-only or scalar Kress-proxy study.

Preset `quick`; nodes `[64, 128, 256]`; frequencies `[0.5, 2.5, 8.0]` GHz; 4 sources × 4 receivers.

Circle truth is the analytic penetrable-cylinder Mie series. Ellipse, star, and frozen Fourier curves use the independently implemented `nystrom_ref` solver frozen at N=512.

Frozen Fourier bundles are first reconstructed exactly, then scaled uniformly about their mode-zero center to the configured physical mean radius and translated to the benchmark center. Candidate and reference receive that same normalized parameterization.

Times below are medians over 3 repeat(s). `total ms` includes the candidate forward call and the separately timed 2-norm condition estimate; oracle time is reported separately in the detailed CSV.
`Rx+leak ms` includes both the physical receiver representation and the second incident-representation convention check.

`raw cond.` is a mixed-unit nodal diagnostic, not a scale-invariant quality score. `core MiB` is exact retained storage for the four difference matrices plus the system matrix, not process peak RSS.

## Largest-N configured checks

| Shape | GHz | N | Mixed receiver error | Max trace error | Raw cond. (diag.) | Residual | Leak | Circle block | Block ms | Cond. ms | Solve ms | Rx+leak ms | Total ms | Core MiB | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| circle | 0.5 | 256 | 1.44e-15 | 1.28e-15 | 1.19e+02 | 6.15e-16 | 7.34e-17 | 2.57e-15 | 135.3 | 54.0 | 11.7 | 1.5 | 204.1 | 8.00 | pass |
| circle | 2.5 | 256 | 1.59e-14 | 1.87e-13 | 1.21e+04 | 4.31e-15 | 1.61e-16 | 1.71e-14 | 254.8 | 50.6 | 11.0 | 1.1 | 319.8 | 8.00 | pass |
| circle | 8 | 256 | 4.48e-14 | 1.51e-13 | 5.06e+05 | 1.12e-14 | 9.12e-16 | 1.25e-13 | 210.3 | 50.0 | 11.0 | 1.0 | 274.4 | 8.00 | pass |
| ellipse | 0.5 | 256 | 8.59e-14 | 4.23e-13 | 9.61e+01 | 6.23e-16 | 5.31e-17 | — | 145.3 | 54.7 | 10.9 | 1.5 | 214.7 | 8.00 | pass |
| ellipse | 2.5 | 256 | 1.18e-11 | 1.43e-11 | 1.44e+04 | 5.74e-15 | 3.61e-16 | — | 257.4 | 50.8 | 11.1 | 1.1 | 323.0 | 8.00 | pass |
| ellipse | 8 | 256 | 2.76e-09 | 3.06e-09 | 3.78e+05 | 1.60e-14 | 1.60e-15 | — | 211.1 | 50.2 | 10.9 | 1.0 | 275.1 | 8.00 | pass |
| star | 0.5 | 256 | 2.14e-12 | 1.27e-12 | 7.27e+01 | 5.72e-16 | 8.29e-17 | — | 139.6 | 54.0 | 10.8 | 1.4 | 208.0 | 8.00 | pass |
| star | 2.5 | 256 | 1.09e-10 | 1.05e-10 | 2.40e+04 | 2.21e-14 | 5.85e-16 | — | 261.6 | 50.6 | 11.1 | 1.1 | 326.5 | 8.00 | pass |
| star | 8 | 256 | 1.22e-08 | 1.11e-08 | 3.84e+05 | 3.88e-14 | 2.99e-15 | — | 215.2 | 50.8 | 11.2 | 1.0 | 281.0 | 8.00 | pass |

## Nyström node refinement

| Shape | GHz | N | Relative receiver error | Mixed error | Adjacent-N difference | Error ratio | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| circle | 0.5 | 64 | 1.57e-15 | 1.57e-15 | — | — | 13.4 |
| circle | 0.5 | 128 | 1.36e-15 | 1.36e-15 | 1.20e-15 | 8.68e-01 | 47.2 |
| circle | 0.5 | 256 | 1.44e-15 | 1.44e-15 | 1.24e-15 | 1.06e+00 | 204.1 |
| circle | 2.5 | 64 | 1.72e-14 | 1.72e-14 | — | — | 20.0 |
| circle | 2.5 | 128 | 1.08e-14 | 1.08e-14 | 1.31e-14 | 6.31e-01 | 76.0 |
| circle | 2.5 | 256 | 1.59e-14 | 1.59e-14 | 1.35e-14 | 1.47e+00 | 319.8 |
| circle | 8 | 64 | 8.83e-03 | 8.83e-03 | — | — | 16.0 |
| circle | 8 | 128 | 5.16e-14 | 5.16e-14 | 8.83e-03 | 5.85e-12 | 64.3 |
| circle | 8 | 256 | 4.48e-14 | 4.48e-14 | 4.15e-14 | 8.67e-01 | 274.4 |
| ellipse | 0.5 | 64 | 8.57e-14 | 8.57e-14 | — | — | 14.0 |
| ellipse | 0.5 | 128 | 8.66e-14 | 8.66e-14 | 1.59e-15 | 1.01e+00 | 50.0 |
| ellipse | 0.5 | 256 | 8.59e-14 | 8.59e-14 | 1.35e-15 | 9.92e-01 | 214.7 |
| ellipse | 2.5 | 64 | 1.18e-11 | 1.18e-11 | — | — | 20.4 |
| ellipse | 2.5 | 128 | 1.18e-11 | 1.18e-11 | 1.16e-14 | 1.00e+00 | 77.2 |
| ellipse | 2.5 | 256 | 1.18e-11 | 1.18e-11 | 9.04e-15 | 1.00e+00 | 323.0 |
| ellipse | 8 | 64 | 1.32e-02 | 1.32e-02 | — | — | 16.5 |
| ellipse | 8 | 128 | 6.93e-09 | 6.93e-09 | 1.32e-02 | 5.26e-07 | 65.7 |
| ellipse | 8 | 256 | 2.76e-09 | 2.76e-09 | 5.82e-09 | 3.98e-01 | 275.1 |
| star | 0.5 | 64 | 1.33e-09 | 1.33e-09 | — | — | 13.7 |
| star | 0.5 | 128 | 2.14e-12 | 2.14e-12 | 1.33e-09 | 1.62e-03 | 48.6 |
| star | 0.5 | 256 | 2.14e-12 | 2.14e-12 | 1.69e-15 | 1.00e+00 | 208.0 |
| star | 2.5 | 64 | 7.79e-07 | 7.79e-07 | — | — | 20.9 |
| star | 2.5 | 128 | 1.09e-10 | 1.09e-10 | 7.79e-07 | 1.41e-04 | 79.2 |
| star | 2.5 | 256 | 1.09e-10 | 1.09e-10 | 2.35e-14 | 1.00e+00 | 326.5 |
| star | 8 | 64 | 5.55e-01 | 5.55e-01 | — | — | 16.7 |
| star | 8 | 128 | 8.89e-05 | 8.89e-05 | 5.55e-01 | 1.60e-04 | 65.9 |
| star | 8 | 256 | 1.22e-08 | 1.22e-08 | 8.89e-05 | 1.38e-04 | 281.0 |

## Interpretation

Only the largest requested N is checked against this run's configurable smoke thresholds. Earlier rows are deliberately retained as convergence evidence. Passing these checks is not Phase-4 acceptance or solver promotion; reference self-convergence, transmission residuals, and the broader frequency ladder remain separate gates.

Execution failures: 0. Largest-N check failures: 0.

No dense matrices or solution arrays are stored by this runner.
