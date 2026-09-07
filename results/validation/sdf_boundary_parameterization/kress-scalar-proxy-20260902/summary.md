# Frozen SDF boundary: isolated Kress proxy

Generated: 2026-09-02T10:15:55.699532+00:00

## Verdict

**PASS.** The independent manufactured-circle identity reaches floating-point accuracy, and every selected frozen A/B/C curve meets its configured convergence gate.

This validates a scalar logarithmic product-rule seam only. It does not validate Müller blocks, diagonal kernel formulas, a linear solve, or a production BIE pipeline.

**None of the errors below is a PDE solution, boundary-density, receiver-field, or scattered-field error.**

## Configuration

- Source study: `results/sdf_boundary_parameterization/study-20260902` (162 rows)
- Curve inputs: `results/sdf_boundary_parameterization/study-20260902/curves` (SHA-256 recorded per bundle)
- Self-contained replay inputs: `frozen_curves/` beside this summary
- Frozen source grid / projected samples: finest available per shape
- Node ladder: `[32, 64, 128, 256, 512, 1024, 2048]`
- Fitted-curve errors: `16` fixed nested targets; timings use all N targets
- Manufactured weighted density: Poisson kernel with `a=0.75`, `beta=0.37`
- Independent remainder reference: composite Gauss-Legendre orders `(24, 40)`; agreement tolerance `1.0e-11`
- Timing: warm-up plus median of `9` dense scalar-proxy full-grid matrix-formation/actions

## Analytic circle control

The reference is closed form; no numerical reference quadrature is used.

| N | max abs error | mixed relative error | dense scalar-proxy action median |
|---:|---:|---:|---:|
| 32 | 1.79e-02 | 7.30e-04 | 0.204 ms |
| 64 | 3.35e-05 | 1.36e-06 | 0.246 ms |
| 128 | 5.90e-10 | 2.40e-11 | 0.435 ms |
| 256 | 2.13e-14 | <1e-14 | 1.062 ms |
| 512 | 3.91e-14 | <1e-14 | 3.553 ms |
| 1024 | 3.91e-14 | <1e-14 | 22.020 ms |
| 2048 | 6.04e-14 | <1e-14 | 78.032 ms |

## Skimmed fitted-curve table

The zero-set column is the normalized maximum implicit-field residual from the source study (a first-order distance proxy). The smooth log-remainder column compares one manufactured scalar integral with an independent Gauss reference; `ref-limited` means the error is no larger than the float64/reference-disagreement floor. The scalar-action error also includes the common manufactured Poisson convolution.

| Shape | Frozen curve | status | zero-set distance proxy | smooth log-remainder quadrature error, N=64 → 128 → 256 → 1024 → 2048 | manufactured scalar-action error N=256 | conversion | dense scalar-proxy action ms, N=256 / 1024 / 2048 |
|---|---|---|---:|---|---:|---:|---:|
| circle | A spline | success | 6.80e-10 | 2.20e-09 → 7.62e-10 → 7.65e-10 → 2.99e-12 → 1.88e-13 | 1.47e-10 | 2.695 s | 1.05 / 23.37 / 77.07 |
| circle | B K=4 | success | 1.23e-14 | 2.38e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 2.678 s | 1.11 / 23.37 / 78.33 |
| circle | C K=4 | success | 1.08e-14 | 2.38e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 7.628 s | 1.20 / 23.50 / 77.99 |
| circle | B K=32 | success | 6.66e-15 | 2.38e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 2.707 s | 1.45 / 24.87 / 80.26 |
| rotated_ellipse | A spline | success | 3.70e-08 | 2.47e-08 → 3.50e-08 → 3.83e-08 → 1.53e-10 → 9.59e-12 | 9.30e-09 | 2.029 s | 1.03 / 23.46 / 76.76 |
| rotated_ellipse | B K=8 | success | 2.23e-03 | 7.12e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 1.987 s | 1.17 / 23.47 / 77.71 |
| rotated_ellipse | C K=8 | success | 3.95e-04 | 7.41e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 6.792 s | 1.19 / 23.68 / 77.91 |
| rotated_ellipse | B K=32 | success | 5.97e-08 | 7.73e-09 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 2.075 s | 1.45 / 24.75 / 79.98 |
| radial_fourier_star | A spline | success | 2.56e-06 | 1.20e-05 → 1.69e-07 → 3.43e-07 → 1.46e-09 → 9.19e-11 | 8.67e-08 | 2.861 s | 1.05 / 23.63 / 76.85 |
| radial_fourier_star | B K=8 | success | 2.05e-02 | 1.18e-08 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 2.864 s | 1.19 / 23.47 / 77.53 |
| radial_fourier_star | C K=8 | success | 1.15e-02 | 1.29e-08 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 8.000 s | 1.22 / 23.95 / 77.83 |
| radial_fourier_star | B K=32 | success | 3.98e-04 | 2.16e-07 → ref-limited → ref-limited → ref-limited → ref-limited | <1e-14 | 2.881 s | 1.48 / 24.75 / 80.06 |

`conversion` is copied from the earlier study and includes the shared front end in every row; do not sum it across methods or read it as incremental fit cost. `dense scalar-proxy action` includes curve discretization, weight construction, dense N×N smooth-remainder matrix formation, and one matrix-vector action. It is neither an FFT-only weight application nor a four-block BIE assembly/solve.

Selection is fixed rather than visual: at the finest grid and largest projected sample count, retain A, the highest-bandwidth accepted C with its same-bandwidth B initializer, and the highest tested B. High-bandwidth C fallbacks are omitted because their serialized geometry is bit-identical to B, but their overall status remains reported below.

## Gates and interpretation

- **PASS:** analytic circle mixed-relative error at N=256 is 8.656e-16 < 1e-12, with N=32→64→128 ratios 1.866e-03, 1.764e-05 < 1e-2
- **PASS:** circle__g257x257__m256__a spline smooth-remainder error at N=2048 is 1.877e-13 < 1e-8 and final ratios are 0.063, 0.063 < 0.2 or reference limited
- **PASS:** circle__g257x257__m256__b__k004 manufactured scalar-action error at N=256 is 4.336e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 1.583e-05, 5.544e-07 < 0.25 or reference limited
- **PASS:** circle__g257x257__m256__c__k004 manufactured scalar-action error at N=256 is 4.336e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 1.583e-05, 5.544e-07 < 0.25 or reference limited
- **PASS:** circle__g257x257__m256__b__k032 manufactured scalar-action error at N=256 is 2.168e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 1.583e-05, 6.336e-07 < 0.25 or reference limited
- **PASS:** rotated_ellipse__g257x257__m256__a spline smooth-remainder error at N=2048 is 9.590e-12 < 1e-8 and final ratios are 0.063, 0.063 < 0.2 or reference limited
- **PASS:** rotated_ellipse__g257x257__m256__b__k008 manufactured scalar-action error at N=256 is 5.813e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 4.105e-05, 1.468e-07 < 0.25 or reference limited
- **PASS:** rotated_ellipse__g257x257__m256__c__k008 manufactured scalar-action error at N=256 is 5.822e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 4.146e-05, 1.612e-07 < 0.25 or reference limited
- **PASS:** rotated_ellipse__g257x257__m256__b__k032 manufactured scalar-action error at N=256 is 5.810e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 4.306e-05, 3.488e-07 < 0.25 or reference limited
- **PASS:** radial_fourier_star__g257x257__m256__a spline smooth-remainder error at N=2048 is 9.187e-11 < 1e-8 and final ratios are 0.064, 0.063 < 0.2 or reference limited
- **PASS:** radial_fourier_star__g257x257__m256__b__k008 manufactured scalar-action error at N=256 is 5.464e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 4.348e-05, 1.333e-07 < 0.25 or reference limited
- **PASS:** radial_fourier_star__g257x257__m256__c__k008 manufactured scalar-action error at N=256 is 4.717e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 4.673e-05, 1.311e-07 < 0.25 or reference limited
- **PASS:** radial_fourier_star__g257x257__m256__b__k032 manufactured scalar-action error at N=256 is 6.155e-16 < 1e-11; N=32→64→128 smooth-remainder error ratios 2.102e-04, 1.423e-07 < 0.25 or reference limited
- **PASS:** the two composite-Gauss reference orders agree to 2.220e-14 < 1.0e-11

Method C in the complete source sweep: 28 accepted and 44 guarded fallbacks. A fallback returns B's geometry and is not an independent curve.

The proxy makes the separation especially visible: a Fourier curve can become reference/roundoff limited while still having appreciable implicit zero-set geometry error. Quadrature convergence does not repair an under-resolved boundary.

Current preference remains **Method B with adaptive bandwidth**. B and accepted C both show spectral smooth-remainder convergence here, with no demonstrated quadrature advantage for C. B avoids nonlinear cost and fallback behavior. A is the useful finite-smoothness control and shows post-knot algebraic convergence.
