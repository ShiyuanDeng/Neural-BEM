# Independent review of the proposed Chebyshev Müller fix

2026-09-30. Reviewed `node_free_modal_muller_summary.pdf`, pulled at
`1723dbee` on `feature/shape-frequency-continuation`. The pull supplied the
PDF only. The calculations below use a new, independent implementation of
its equations, with the repository's native code and nodal Kress as controls.
They do not rely on the seven scripts mentioned in the PDF.

**Verdict: the central radial-kernel fix works, the log-of-squared-modulus
extension works on the tested C curves, and all three recorded stage
decisions reproduce. The claimed geometric certificates are false. Treat
this as a successful numerical prototype, not a complete correctness
qualification or a ready production backend.**

The reproducible scripts and raw receipts are in
[the review bundle](../../../results/validation/cleaned_interfaces/chebyshev-review-20260930/).
No production solver, optimizer, policy, or hash-pinned native source was edited.

## What independently reproduces

### 1. The existing radial assembler loses precision at high contrast

The implementation at
[`CoefficientGeometry.radial`](../../../experiments/modal_muller_research/coefficient_operator.py)
really does accumulate the six radial functions against powers of `R`.
The diagnosis applies directly to this implementation. Its existing 30-test
suite passes, but those tests do not qualify the reported high-contrast regime.

On the PDF's SC star, at 2.5 GHz, `Ku=64`, `B=160`, against a 1024-node Kress
matrix projected with the repository's flux similarity and Fourier transform:

| Contrast | Best monomial error, tested 28/48/80/120 terms | Chebyshev degree 40 | Degree 60 | Degree 80 |
|---|---:|---:|---:|---:|
| 0.5 | 1.72e-11 | 1.18e-14 | 1.90e-14 | 1.98e-14 |
| 4 | 8.44e-5 | 2.13e-14 | 2.47e-14 | 2.13e-14 |
| 13.3 | 6.03e6 | 9.53e-8 | 4.26e-14 | 3.17e-14 |

These are relative Frobenius matrix errors. Each of `V`, `K`, `Kp`, and `T`
was also checked separately; the degree-60 worst block at contrast 13.3 is
4.28e-14. The PDF's table is independently reproduced to the expected
floating-point variation. More monomial terms remove truncation error but
do not remove the eventual cancellation floor.

The analytic identity in Lemma 2 follows from
[DLMF's addition theorem and square-sum identity](https://dlmf.nist.gov/10.23#E3).
At real `alpha=29.25`, the independently computed absolute Chebyshev
coefficient sum is `0.9999999999999992`. The complex extension in Lemma 3
also holds: the tested sums for `Im(alpha)=2.4,4.75,11.9` are approximately
22.794, 1753.481, and 1.783e9, matching `I0(2|Im(alpha)|)`.
The [generating function](https://dlmf.nist.gov/10.12) and
[modified-Bessel integral representation](https://dlmf.nist.gov/10.32#E1)
support the Parseval derivation of that scalar identity.

Scope matters: the unit coefficient sum is for **J0 with real argument**.
It is not a unit bound for all six functions, their derivatives, the assembled
matrix error, or the error after solving an ill-conditioned system. The
`eps*I0` estimates are useful cancellation scales, not full forward-error
certificates.

### 2. Expanding log(|W|²) removes the half-plane obstacle on the tested C

Equation (7) and the logarithm expansion are correct when a valid positive
lower bound for `|W|²` is available. The old half-plane condition is a
sufficient analytic-log condition; describing it as equivalent to
star-shapedness is too strong.

For the C rebuilt from `atlas_cases.c_shape_curve`, at 2.5 GHz and `Ku=64`:

| Contrast | B=96 | B=128 | B=192 |
|---|---:|---:|---:|
| 0.5 | 3.75e-14 | 3.78e-14 | 3.76e-14 |
| 13.3 | 2.88e-10 | 1.46e-13 | 1.46e-13 |

These are matrix errors against 2048-node Kress. The 1024/2048 projected
oracle differences are 8.15e-16 and 3.03e-15 respectively. This reproduces
the reported coefficient-window effect and high-contrast accuracy.

This review uses the stated `beta=0.05` **as a fixture-specific assumption**,
with an explicit `lower_certified=false` receipt. It does not promote a
passing RMS test to a proof. The radial interval uses coefficient triangle
bounds, rather than the proposed RMS bisection.

### 3. Fields and the SC coefficient Jacobian work at adequate trace cutoff

Using the saved SC-050 C truth, actual SC paired acquisition, contrast 13.3,
and the maintained `ProjectedUpdate` velocity coefficients at `K=M=24`:

| Frequency | Ku | Relative field error | Relative Jacobian error |
|---|---:|---:|---:|
| 1 GHz | 32 | 1.37e-6 | 1.21e-5 |
| 1 GHz | 64 | 1.82e-13 | 2.40e-13 |
| 2.5 GHz | 32 | 8.67e-2 | 3.18e-1 |
| 2.5 GHz | 48 | 1.90e-4 | 4.19e-4 |
| 2.5 GHz | 64 | 1.37e-8 | 9.11e-8 |
| 2.5 GHz | 96 | 1.57e-12 | 4.51e-12 |

References are independent 2048-node SC fields/Jacobians; native coefficient
bandwidth is 128. These results support Sections 7.1 and 7.2 and demonstrate
why field agreement alone is insufficient at small `Ku`.

On the saved `shifted_rotated_c` DF endpoint (`fixed_M67`, `K=192`, `M=67`),
at 2.5 GHz, holding **B=160 fixed** to separate it from trace refinement:

| Ku | Relative field error | Relative Jacobian error | Worst relative column error |
|---:|---:|---:|---:|
| 64 | 6.77e-7 | 5.97e-5 | 3.64e-3 |
| 96 | 1.57e-10 | 8.72e-8 | 1.34e-5 |
| 128 | 1.76e-12 | 5.16e-12 | 1.35e-10 |

The forward and intermediate-cutoff Jacobian behavior reproduce the PDF.
Our refined Jacobian is more accurate than its reported value; the
independent implementation uses degree 100, a coefficient-based upper
interval, and fixed B=160, so exact equality of the small error floors is
not expected.

An additional check differentiates the **complete finite SC trial**, not
another Hadamard implementation. For a fixed seeded mixed update direction:

| Curve | FD step 1e-6 m | FD step 5e-7 m |
|---|---:|---:|
| C, K=24/M=24 | 1.81e-6 | 4.52e-7 |
| DF endpoint, K=192/M=67 | 4.68e-6 | 1.17e-6 |

These are relative directional-derivative errors at 2.5 GHz, contrast 13.3,
Ku=128. The fourfold reduction is consistent with centered-difference
truncation error. It is a local qualification on two curves, not a uniform
derivative guarantee over an inverse trajectory.

`space.derivatives` has the right coefficient layout, but the PDF's word
"exactly" needs qualification: the maintained geometry implementation
constructs these columns by centered finite differences of geometry with
step `1e-7 m`. They approximate the complete-trial velocities. The modal
contraction itself introduces no boundary quadrature. Geometry preparation
and validity checks still use nodes and splines.

### 4. Damping and the scalar evaluator

The six scalar formulas, including the cancellation in Equation (10), were
checked against a 60-digit mpmath calculation at 22 squared radii from
1e-12 through 16, for real and `1+0.25i` wavenumbers. Per-function vector
relative errors were at most 4.81e-16 on this sample. This supports the
scalar evaluator; it is not a uniform relative bound near its zeros.

On the saved C, contrast 13.3, damping 0.25, B=128, Ku=64, field errors
against 2048-node complex Kress are 8.63e-15 at 0.5 GHz, 4.42e-14 at
1 GHz, and 7.16e-9 at 2.5 GHz. Increasing Ku to 96 leaves the last error
essentially unchanged. The prefix works; at stronger damping/electrical
size there is still a cancellation floor. Our radial upper bound is
16.554, tighter than the PDF's loose triangle bound 25.3 but larger than
its unproven RMS-derived bound 8.44. The different high-frequency error
therefore does not contradict its 3.9e-7 result.

### 5. Recorded stage replays

The independent service runs through the existing `fit_stage(..., physics=...)`
hook. It uses the archived initial state, observations, LM configuration,
stage quota, and SC geometry update; it does not replay saved steps or
replace the optimizer. Production/refined trace cutoffs are 64/96 for
small-K stages and 96/128 for K=192. The coefficient bandwidth is 128 or
160 respectively. The original source/receiver Laurent series is retained.

| Stage | Trial decisions matching | Accepted steps | Forward solves / reciprocal batches | Maximum endpoint difference, package units |
|---|---:|---:|---:|---:|
| D `stage_2_damped` | 25/25 | 10 | 104 / 22 | 2.96e-12 |
| D `release_M11` | 7/7 | 7 | 304 / 152 | 1.51e-12 |
| DF `fixed_M43` | 1/1 | 1 | 76 / 38 | 1.76e-13 |

Every trial's iteration, damping, backtrack, and status matches. Accepted
iteration indices, stopping outcomes/reasons, and **stage-specific** work
counts also match. Final losses are respectively
`0.004376567107229170`, `0.009759024799210021`, and
`2.472356556561334e-11`; relative changes from the archived nodal losses are
2.48e-14, 1.71e-12, and 2.59e-8. The last relative number reflects a tiny
absolute loss near convergence.

The endpoint metric is the maximum difference of the Fourier curves on
8192 parameter values. The largest difference is 1.48e-13 metres. Thus the
near-roundoff agreement and decision-reproduction claim are independently
supported, but **this implementation does not reproduce the PDF's exact
6e-13-package-unit endpoint bound**. Its coefficient-vector differences also
exceed 6e-13 in the first two stages. That is a numerical difference between
implementations, not evidence that the unsupplied original runs could not
have attained their reported values.

The individual replay receipts contain every trial, accepted state, and
acceptance check. [summary.json](../../../results/validation/cleaned_interfaces/chebyshev-review-20260930/summary.json)
independently recomputes the comparisons from those records and the archives.
Archive work ledgers are cumulative; the summary filters their stage prefixes
before comparing them with this service's actual calls.

## Claims that need correction

### The finite Parseval test is not a bound or a simplicity certificate

This is a substantive counterexample to Sections 4 and 8, not merely the
absence of a formal proof. The PDF acknowledges on page 5 that the test
is not a proof, then claims that no positive beta can pass for a crossing
curve. That latter statement is false for its finite-window computation.

Consider the regular curve `z(w)=w+w²`. Its speed is at least 1, but the two
distinct parameters `w=exp(±2πi/3)` both map to -1. It self-intersects.
Its divided difference is `W=1+w+v`, so the true minimum of `|W|²` is zero.

At B=16, the compressed multiplication matrix for `|W|²` has smallest
eigenvalue 0.0161229. Choose **beta=0.00806145 > 0** and Lambda=9. The
mapped compressed matrix has spectrum inside [-1,1], so its Chebyshev
recurrence passes for every degree in exact arithmetic. Numerically, the
largest coefficient L2 norm over degrees 1–1000 is **0.78764 < 1**.
The proposed test accepts a positive lower bound on a regular crossing curve.

The upper-bound version and its 2% safety factor also lack a guarantee.
For the simple circle `z(w)=w`, B=1 and tau=3.41521356 pass all degrees
through 60 with maximum norm 0.97671, yet `1.02*tau=3.48352 < max R=4`.
This small-window example disproves a universal guarantee; it does not
claim the PDF's particular B=128 C interval is wrong.

The underlying distinction is

`T_n(P_B M_lambda P_B) 1 != P_B T_n(M_lambda) 1`.

Parseval measures the arrays actually computed. It does not restore
discarded modes or recover the extrema of the original multiplication
function. Use the RMS test as a numerical warning only. Retain independent
geometry validity and an actual interval-bound method if a certificate is
required. A sampled dense check alone is also not a rigorous certificate.

One possible coefficient-only replacement follows directly from the triangle
inequality: for a Laurent polynomial `v`, if the **full** coefficient residual
obeys `r=||1-Wv||_1 < 1`, then
`|W| >= (1-r)/||v||_1 > 0` on the torus. The residual must include discarded
tails and arithmetic error before calling this rigorous. This is a suggested
certificate, not an implemented or qualified feature of this review.

### The linear rounding-error conclusion does not follow

Page 9 correctly identifies a self-adjoint compressed multiplication
operator, **provided the interval is valid**. This prevents exponential
growth of the exact recurrence. It does not imply that accumulated local
roundoff grows at most linearly with degree.

At the permitted endpoint A=1, a local-error recurrence
`e_(n+1)=2e_n-e_(n-1)+delta` accumulates quadratically. Starting with two
zero errors, 100 equal perturbations produce `5050*delta`, not an O(100)
bound. The second-kind Chebyshev error propagators give an O(n²) worst-case
sum. This correction does not invalidate the observed numerical accuracy.

### Cropping is exact only under the lemma's support hypothesis

Lemma 4 is correct for one product when the first factor already has
support in [-B,B]. It does not prove that repeatedly cropped recurrences
equal the final crop of the untruncated analytic function. Bandwidth
refinement remains a separate error check, as the existing native code
already states. FFT multiplication must also use enough padding for linear
convolution; circular wraparound would be a different error.

### Three stages do not finish backend qualification

The phrase "what remains is speed ... not correctness" is too broad.
Local forward/Jacobian agreement and recorded-stage agreement are strong
evidence, but do not validate full localization-to-tail behavior, the other
scenes, all contrasts/damped catalogs, close or multiple components,
automatic resolution selection, or every failure/validity path.

The old `RegularWaves` source/receiver and cross-component expansions have
their own series and Graf convergence requirements. Fixing the self radial
kernel does not remove those limits. Warm-starting interval searches can
be useful; reusing Chebyshev arrays unchanged at a different geometry
would change the operator and needs its own controlled approximation.

For integration, use `register_backend` and the cleaned physics-service
contract. `SC_FORWARD_BACKEND` currently selects CPU/CUDA execution, not
nodal versus native discretization. The repository still correctly refuses
`solver='modal_muller'` until a backend is registered and qualified.

Timing fields in this review are diagnostic only: some checks ran
concurrently. Neither these runs nor the PDF's CPU-versus-archived-GPU
comparison establishes runtime retention. The subsequent
[sequential comparison against maintained CUDA Kress](../../../results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/README.md)
provides separate matched forward/Jacobian timings. No full 36-case native
campaign has been run.

The appropriate next implementation is a separate Chebyshev backend with
explicit interval assumptions/failures, independent trace/window/degree
refinement, complete-trial derivative checks, and the full cleaned-interface
contract. Preserve the old hash-pinned sources and their recorded evidence.
