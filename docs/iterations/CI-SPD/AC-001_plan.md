# AC-001: analytic radial Chebyshev coefficients

2026-10-05. Authorized by the user's request to implement and validate direct
analytic coefficients. This is a bounded numerical implementation study, not
a new inverse campaign. Preserve existing workspace changes and all archived
evidence; use the current branch unless the user selects the usual branch.

## Construction

Replace the production radial-value DCT with analytic Bessel products.
For `a=k*sqrt(U)/2`, `x=2R/U-1` and `e_n=2-delta_n0`, Graf's addition theorem
gives the Chebyshev coefficients of `J_(2m)(k*sqrt(R))` as
`e_n J_(m+n)(a) J_(m-n)(a)`. In particular, `J0` has coefficients
`e_n (-1)^n J_n(a)^2`.

Use DLMF 10.23.16 to regularize the Hankel function analytically:

```
P_k(R) = -J0(k sqrt(R))/(4 pi)
Q_k(R) = C_k J0(k sqrt(R))
         + (1/pi) sum_(m>=1) (-1)^m J_(2m)(k sqrt(R))/m
C_k = i/4 - (gamma + log(k/2))/(2 pi).
```

Build P and Q coefficients from these identities. Form their material
differences, derivatives, the regular quotient `(P_o-P_i)/R`, and k-squared
weights in coefficient space. Both CPU and CUDA assembly share the routine.
No radial samples or DCT are allowed on the production coefficient path.
Keep the old value evaluator as an independent reference, and preserve the
old DCT algorithm in validation code only.

Sources: [Graf addition](https://dlmf.nist.gov/10.23#E7),
[regular Neumann expansion](https://dlmf.nist.gov/10.23#E16).

## Predeclared validation

1. Compare all six reconstructed functions and coefficients with independent
   high-precision Bessel/Hankel evaluations and an oversampled DCT. Cover
   contrasts 0.5, 4, 13.3, real and 25%-damped wavenumbers, small and large
   radial intervals, endpoints, and zero material contrast.
2. Test that the production routine cannot call the radial sampler or DCT.
   Check derivative/quotient identities and resolution/refusal behavior.
3. Run maintained package and existing modal regression tests, including
   projected nodal matrices, fields and complete-trial derivatives. Exercise
   CPU/CUDA parity if GPU access is available. Existing test fixtures are
   regression checks, not new legacy-scene inverse experiments.
4. Record scalar construction timings and numerical errors. Require
   scale-relative errors <=1e-11 against independent scalar references in the
   representative envelope and retain existing matrix/field/Jacobian gates.
   Do not claim speedup or inverse recovery from these bounded checks.
5. Preserve failed-run evidence, document results and limitations, validate
   the diff, commit only task-owned files, push, and verify remote/worktree.

Revise or refuse the implementation if analytic summation or differentiation
fails accuracy gates; do not silently fall back to the DCT.

## Follow-up registered before execution

The scalar stress study found large origin absolute errors under the strongest
damping, despite small errors relative to the exponentially large coefficient
norm. Compare analytic and archived DCT matrices/fields on TG-002 circle and
C-shape truths at 2.5 GHz, contrast 13.3, real and 25%-damped k. Use K_trace=96,
window=160, and an independent N1024 nodal reference. Gates: real matrix 1e-12
and field 1e-10; damped matrix max(1e-8, twice the DCT error) and field
max(1e-7, twice the DCT error). These are bounded forward checks, not new inverse
runs or claims of pointwise accuracy in the extreme scalar stress case.

The first forward comparison failed the damped C matrix gate. Replacing
coefficient differentiation with direct even-Bessel weights also failed in
float64. Preserve both versions and results. The revised construction uses
direct weights for P' and S=Q'+(P-P(0))/R, and scaled Miller recurrence plus
product summation in extended precision before returning complex128 arrays.
Retain the original forward gates, add high-precision recurrence checks, and
rerun scalar, package/shared, and CUDA regressions. No acceptance gate is relaxed.
