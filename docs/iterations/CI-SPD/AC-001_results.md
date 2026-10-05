# AC-001: direct analytic radial coefficients

2026-10-05. Implemented on `feature/shape-frequency-continuation`, as explicitly
selected by the user. [Plan](AC-001_plan.md),
[derivation](../../reference/modal_radial_coefficients.md),
[raw evidence](../../../results/validation/cleaned_interfaces/AC-001/).

## Outcome

CPU and CUDA modal assembly now obtain all six radial coefficient arrays from
analytic Bessel-product formulas. The regularized Hankel term uses the Neumann
expansion; direct even-Bessel weights give both derivative combinations.
No radial-function samples, DCT, or sampled fallback occur on this path.
Scaled Miller recurrence and coefficient summation use extended precision,
then return complex128 arrays. Linux working precision here has a 64-bit
significand. The geometry-dependent Chebyshev arrays are unchanged.

The 24 scalar cases cover contrasts 0.5/4/13.3, real/25%-damped wavenumbers,
small arguments and large intervals, with maximum alpha 96.49. Against a
4096-point independent DCT, the maximum coefficient l1 discrepancy divided by
the reference coefficient l1 norm is **6.37e-13**. Against 80-digit Bessel/Hankel
values at six points including the origin and upper endpoint, the largest
absolute error divided by coefficient l1 norm is **2.18e-13**. All cases pass
the predeclared 1e-11 gates. These are norm-scaled errors, not uniform pointwise
relative errors. [Scalar results](../../../results/validation/cleaned_interfaces/AC-001/scalars.json)
include source hashes, per-function errors, diagnostics and timings.

## Independent forward comparisons

TG-002 circle and C-shape truths, 2.5 GHz, contrast 13.3, K_trace=96,
coefficient window=160, CPU N1024 nodal reference. Matrix errors are relative
Frobenius norms after projecting the independent nodal matrix into the modal
flux basis. Field errors are relative Euclidean norms.

| Geometry / damping | Analytic matrix | DCT matrix | Analytic field | DCT field |
|---|---:|---:|---:|---:|
| Circle / real | 2.79e-13 | 2.76e-13 | 1.43e-13 | 1.38e-13 |
| Circle / 25% | 2.58e-11 | 2.81e-11 | 5.35e-12 | 9.28e-12 |
| C-shape / real | 3.62e-13 | 3.82e-13 | 9.01e-13 | 1.19e-12 |
| C-shape / 25% | 9.07e-9 | 1.13e-8 | 2.85e-9 | 5.10e-9 |

All four cases pass the unchanged predeclared gates. The hardest damped case
improves over the DCT control in both matrix and field error.
[Forward results](../../../results/validation/cleaned_interfaces/AC-001/forward.json).
This is bounded forward qualification; no new inverse campaign was run.

## Regressions and retained failures

The focused scalar suite has 35 passing checks, including high-precision
Miller recurrence checks, all six functions, exact zero contrast, no sampling,
non-finite refusal and unresolved-tail refusal. The final combined package,
cleaned-interface, continuation, Kress and ordered-boundary suite passed
**628 tests**, with 46 skips and 15 warnings. A separate run with GPU access
passed all **5 CUDA checks** (otherwise skipped in the sandbox). Existing
matrix, field, complete-trial Jacobian and bounded inverse regressions pass.
The warnings concern existing Matplotlib/Pyparsing deprecations and an
atlas-video test's multiply warning. See `final-suite.*` and `cuda-final.xml`
in the evidence directory. Documentation links, source hashes and
`git diff --check` also pass.

Three intermediate problems are retained:

1. The initial scalar implementation failed three small-argument cases by
   subtracting nearly equal constant P coefficients. Reconstructing that
   coefficient from the exact origin identity fixed this without relaxing gates.
2. Differentiating float64 Q coefficients produced a damped C matrix error
   of 3.63e-8, exceeding the 2.26e-8 comparison gate.
3. Direct derivative weights alone, still using float64 SciPy Bessel values,
   produced 5.46e-8 and also failed. Extended-precision Bessel recurrence and
   product sums reduced the error to 9.07e-9.

Logs, JSON comparisons and source snapshots for all three are kept in the
evidence directory. The final implementation has no DCT fallback.

## Cost and limits

Median scalar construction time over the 24 cases is **1.00 ms**, versus
**0.354 ms** for the archived adaptive DCT. The median paired ratio is **2.76x
slower**. This measures scalar setup only; no end-to-end timing or speedup
claim is made.

Strong damping still makes complex128 reconstruction near small function
values ill-conditioned. At the largest synthetic stress case (U=64,
contrast 13.3, 25% damping), the worst origin absolute error over the six
functions is 4.16e4, versus 2.73e5 for the DCT control. At U=12 the respective
maxima are 1.20e-7 and 8.19e-7. Large coefficient norms explain why these can
coexist with small norm-scaled errors; they are not pointwise accuracy claims.
The internal tail majorant covers truncation, not full floating-point error,
geometry truncation or solve conditioning. Existing endpoint audits and
resolution checks remain necessary.

The independent forward tests above exercise actual TG-002 geometry bounds
(U=4 and approximately 10.796). Qualification of the extended-precision path
is specific to the tested platform; the actual work precision is recorded in
`radial_work_precision_bits`.

Diagnostics now identify `analytic_bessel`, zero radial sample points, and
the internal term count. `amplification` uses coefficient-derived weighted
RMS rather than the old sampled peak, with its changed scope recorded.
Other workspace edits are preserved and excluded from this task's commit.
