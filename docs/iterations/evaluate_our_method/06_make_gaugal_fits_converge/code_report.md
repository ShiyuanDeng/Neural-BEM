# GauGal converged variant

The converged variant projects the fixed Green matrix with GauGal’s pixel
FFT and computes the separable Gaussian mass matrix. GauGal’s dense LU
solves the forward and adjoint systems with one factorization per frequency
and coefficient update. The original pixel operators check each solution.

The relative residual limit is 1e-4 for every source. The frequency-by-
iteration arrays in `fit.npz` retain the worst relative residual over
the 24 sources for each forward, adjoint and endpoint solve.

The 51-by-51 lattice, width 0.7, TV scale 0.5, step 0.05 and bounds
−0.9 to 15 are unchanged. The original TV schedule runs through iteration
80 and holds its final weight thereafter.

The fit stops when the range of 51 successive weighted squared mismatches
is less than 1% of the first value in that window. All 51 values must
use the final TV weight. The cap is 3,000 evaluations. Both time limits
are disabled. A cap stop is recorded separately from a plateau.

## Gradient and default checks

On the clean blind kite, all 19 frequencies contributed to a central
difference at three lattice coefficients. The perturbation was 1e-4.
The calculation used complex128 and coefficients of 0.04 plus a sinusoid
of amplitude 0.02 and angular increment 0.017 per lattice index.

| Coefficient, zero-based | Adjoint derivative of half weighted squared mismatch | Central difference | Relative difference |
|---:|---:|---:|---:|
| 1134 | 0.0161402080648 | 0.0161402080687 | 2.44e-10 |
| 1300 | 0.000169199420711 | 0.000169199427112 | 3.78e-8 |
| 1635 | 0.00801431441756 | 0.00801431442310 | 6.90e-10 |

The worst checked linear residual in this diagnostic was 4.11e-16.
The fit uses the reference complex64 field precision. The stored
`default_n1d0_uc_fs` settings matched exactly. The default branch still
uses the original BiCGStab gradient, TV schedule and time limits.

The GauGal-only parser change admits the new run name through the normal
comparison CLI. The BEM parser continued to reject `converged`.

## Cumulative frequency continuation

The coordinator fixed this follow-up before the continuation run. It uses
the lowest 1, 2, 4, 8, 16 and 19 frequencies in order. Every stage uses
step 0.2 and the same 51-value plateau test, with a 1,000-iteration cap.

Only the previous stage’s endpoint coefficients initialize the next stage.
Each stage restarts momentum, the TV variables and its 80-iteration TV
schedule. The TV scale uses that stage’s frequency count. The fixed
matrices are reused across stages.

The case’s `stages.json` is written after each endpoint prediction. It
records starting and final mismatch, per-frequency field residuals,
iterations, elapsed time, stop reason and cap status.
