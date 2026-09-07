# Ordered-boundary Nyström validation

This run contains actual Müller operator, direct-solve, and off-surface receiver errors. It is not a geometry-only or scalar Kress-proxy study.

Preset `quick`; nodes `[128, 256]`; frequencies `[0.5, 2.5, 8.0]` GHz; 4 sources × 4 receivers.

Circle truth is the analytic penetrable-cylinder Mie series. Ellipse, star, and frozen Fourier curves use the independently implemented `nystrom_ref` solver frozen at N=512.

Frozen Fourier bundles are first reconstructed exactly, then scaled uniformly about their mode-zero center to the configured physical mean radius and translated to the benchmark center. Candidate and reference receive that same normalized parameterization.

Times below are medians over 3 repeat(s). `total ms` includes the candidate forward call and the separately timed 2-norm condition estimate; oracle time is reported separately in the detailed CSV.
`Rx+leak ms` includes both the physical receiver representation and the second incident-representation convention check.

`raw cond.` is a mixed-unit nodal diagnostic, not a scale-invariant quality score. `core MiB` is exact retained storage for the four difference matrices plus the system matrix, not process peak RSS.

## Largest-N configured checks

| Shape | GHz | N | Mixed receiver error | Max trace error | Raw cond. (diag.) | Residual | Leak | Circle block | Block ms | Cond. ms | Solve ms | Rx+leak ms | Total ms | Core MiB | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| frozen-circle__g257x257__m256__b__k004 | 0.5 | 256 | 4.65e-13 | 3.86e-13 | 1.19e+02 | 6.25e-16 | 7.24e-17 | — | 135.4 | 53.3 | 10.9 | 1.5 | 203.1 | 8.00 | pass |
| frozen-circle__g257x257__m256__b__k004 | 2.5 | 256 | 4.92e-12 | 5.25e-12 | 1.21e+04 | 4.40e-15 | 5.10e-16 | — | 255.1 | 50.5 | 10.9 | 1.1 | 319.6 | 8.00 | pass |
| frozen-circle__g257x257__m256__b__k004 | 8 | 256 | 1.84e-09 | 1.02e-09 | 5.06e+05 | 1.22e-14 | 3.91e-15 | — | 211.0 | 49.7 | 11.0 | 1.0 | 274.8 | 8.00 | pass |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 0.5 | 256 | 1.94e-12 | 5.82e-12 | 8.48e+01 | 6.09e-16 | 1.37e-16 | — | 135.5 | 53.9 | 10.7 | 1.4 | 203.5 | 8.00 | pass |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 2.5 | 256 | 4.73e-11 | 5.55e-11 | 1.73e+04 | 1.24e-14 | 8.92e-16 | — | 257.3 | 49.8 | 11.0 | 1.1 | 321.6 | 8.00 | pass |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 8 | 256 | 4.79e-09 | 3.56e-09 | 2.84e+05 | 4.92e-14 | 1.02e-14 | — | 211.3 | 50.1 | 10.9 | 1.0 | 275.2 | 8.00 | pass |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 0.5 | 256 | 1.95e-13 | 3.87e-13 | 9.56e+01 | 6.29e-16 | 1.64e-16 | — | 135.6 | 54.5 | 10.8 | 1.4 | 204.8 | 8.00 | pass |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 2.5 | 256 | 8.18e-12 | 8.49e-12 | 1.41e+04 | 4.63e-15 | 9.10e-16 | — | 255.9 | 49.7 | 11.0 | 1.1 | 319.8 | 8.00 | pass |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 8 | 256 | 1.32e-09 | 1.40e-09 | 3.71e+05 | 2.04e-14 | 7.80e-15 | — | 215.5 | 49.7 | 10.9 | 1.0 | 278.9 | 8.00 | pass |

## Nyström node refinement

| Shape | GHz | N | Relative receiver error | Mixed error | Adjacent-N difference | Error ratio | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| frozen-circle__g257x257__m256__b__k004 | 0.5 | 128 | 4.65e-13 | 4.65e-13 | — | — | 48.5 |
| frozen-circle__g257x257__m256__b__k004 | 0.5 | 256 | 4.65e-13 | 4.65e-13 | 1.14e-15 | 1.00e+00 | 203.1 |
| frozen-circle__g257x257__m256__b__k004 | 2.5 | 128 | 4.92e-12 | 4.92e-12 | — | — | 75.9 |
| frozen-circle__g257x257__m256__b__k004 | 2.5 | 256 | 4.92e-12 | 4.92e-12 | 1.47e-14 | 1.00e+00 | 319.6 |
| frozen-circle__g257x257__m256__b__k004 | 8 | 128 | 1.84e-09 | 1.84e-09 | — | — | 64.8 |
| frozen-circle__g257x257__m256__b__k004 | 8 | 256 | 1.84e-09 | 1.84e-09 | 5.87e-14 | 1.00e+00 | 274.8 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 0.5 | 128 | 1.94e-12 | 1.94e-12 | — | — | 47.8 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 0.5 | 256 | 1.94e-12 | 1.94e-12 | 8.58e-15 | 1.00e+00 | 203.5 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 2.5 | 128 | 4.96e-11 | 4.96e-11 | — | — | 77.2 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 2.5 | 256 | 4.73e-11 | 4.73e-11 | 1.65e-11 | 9.54e-01 | 321.6 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 8 | 128 | 6.91e-07 | 6.91e-07 | — | — | 64.3 |
| frozen-radial_fourier_star__g257x257__m256__b__k032 | 8 | 256 | 4.79e-09 | 4.79e-09 | 6.89e-07 | 6.93e-03 | 275.2 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 0.5 | 128 | 1.95e-13 | 1.95e-13 | — | — | 48.0 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 0.5 | 256 | 1.95e-13 | 1.95e-13 | 1.01e-15 | 1.00e+00 | 204.8 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 2.5 | 128 | 8.18e-12 | 8.18e-12 | — | — | 76.8 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 2.5 | 256 | 8.18e-12 | 8.18e-12 | 1.21e-14 | 1.00e+00 | 319.8 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 8 | 128 | 1.31e-09 | 1.31e-09 | — | — | 66.3 |
| frozen-rotated_ellipse__g257x257__m256__b__k032 | 8 | 256 | 1.32e-09 | 1.32e-09 | 2.04e-11 | 1.01e+00 | 278.9 |

## Interpretation

Only the largest requested N is checked against this run's configurable smoke thresholds. Earlier rows are deliberately retained as convergence evidence. Passing these checks is not Phase-4 acceptance or solver promotion; reference self-convergence, transmission residuals, and the broader frequency ladder remain separate gates.

Execution failures: 0. Largest-N check failures: 0.

No dense matrices or solution arrays are stored by this runner.
