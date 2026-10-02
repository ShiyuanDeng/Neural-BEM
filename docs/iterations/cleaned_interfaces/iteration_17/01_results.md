# NF-001: outsider review, integrated corrections and bounded experiments

2026-10-02–03. Executed the [advance plan](../iteration_16/03_plan.md) under the
user's authorization to fix and experiment without further approval. Work
stayed on the existing `feature/shape-frequency-continuation` checkout, starting
at `31f12978`. Owner: Codex; independent reviewer: unassigned. “Outsider” here
means a critical audit of the claims, not a second person's independent review.

## Verdict

**Reject an unqualified, end-to-end “node-free” claim. Retain the narrower
claim: boundary-collocation-free Fourier–Galerkin physics, with spline-free
quadrature geometry when explicitly selected.** This distinction describes
the implemented numerical method without changing its successful calculations.

| Part | What the implementation actually does | Decision |
|---|---|---|
| Modal operator and unknown traces | Laurent arrays and Fourier–Galerkin traces; padded convolution; no boundary collocation unknowns | Retain the coefficient-space claim |
| Geometry move and reparameterization | Samples normal displacement; FFT fit; integrates nonlinear speed and oscillatory phase on a uniform grid | Call this spline-free quadrature; retain refinement checks |
| Metric, step measurement and frontier | Sampled normals, speeds and arclength harmonics | Include in the declared sampling scope |
| Validity interval proposal | Samples a torus grid to propose a lower endpoint; checks a full coefficient residual afterwards | Samples propose, residual decides; do not call it sample-free |
| Validity decisions | Positive-area/increment/full-residual tiers, then polygon/speed fallback if inconclusive | Six successful cases without fallback do not remove the fallback |
| Certificate arithmetic | Exact-arithmetic theorem evaluated by float64 FFTs and an empirical allowance | Numerical certificate conditional on that allowance; not a computer-assisted proof |
| Public runner before this work | `ProjectedUpdate` still selected spline geometry; NU-006 required an experimental global substitution | Integrated explicit geometry selection and truthful receipts |

The original fixed NU-007 relative gate remains a failed experiment. A
threshold-scaled diagnostic is sensible, but reinterpreting old results does
not establish a fresh campaign or justify an automatic default switch.

## Corrections integrated

- `fit(..., geometry_update=...)` and `--geometry-update` now select `spline`,
  `spectral`, `certified_spectral` (NU-006), or experimental `analytic_spectral`.
  The selection reaches campaign workers, is part of resume identity, and
  appears in plans, resolved operations, decisions, configuration and results.
  No process-global monkeypatch is needed. Existing omitted-selection callers
  and experiment wrappers keep their behavior; the public default remains spline.
- Modal receipts distinguish operator collocation from interval-proposal and
  frontier samples. CPU/CUDA geometry diagnostics scope `boundary_nodes=0`
  explicitly to operator collocation. Interval receipts expose the proposal
  grid and `arithmetic_verified=false`.
- CPU/CUDA log intervals and NU-007 reject invalid tolerances and nonfinite
  residual calculations. A sampled-minimum failure now reports an inconclusive
  proposal, not a proof that the curve intersects.
- A zero geometry step clears per-trial validity records. Previously it could
  leave the preceding nonzero step's certificate tiers attached to the update.
- The NU-005 drift report no longer overwrites its campaign path with a case
  dictionary before reading work totals; the documented `TypeError` is fixed
  in the maintained entry point as well as the earlier workaround.

These changes leave existing acceptance tolerances, observations, optimizer
policy, modal cutoffs and historical results intact. New campaign source seals
are required because maintained source files changed.

## Derivations supporting the decisions

### Residual certificates are mathematically sound but conditional in floating point

For `W(w,v)=(z(w)-z(v))/(w-v)` and `lambda=|W|²`, let Y be **any** finite Laurent
polynomial. If the complete, untruncated residual satisfies

`r = ||1 - lambda Y||_1 < 1`,

then on the unit torus `|1-lambda Y| <= r` and `|Y| <= ||Y||_1`, hence

`lambda >= (1-r)/||Y||_1 > 0`.

The off-diagonal implication is injectivity; the diagonal limit is regularity.
The trial-increment tier follows by writing `W_new=W+W_D` and using
`||W_D||_1 <= nu(D)=sum |j||D_j|`, giving

`||lambda_new-lambda||_1 <= 2 nu(z) nu(D) + nu(D)^2`.

No proof is needed that Y itself accurately approximates the reciprocal: the
full residual is the check. However, a floating-point proof must enclose the
errors in W, its squared modulus, convolution, norms and arithmetic. The
current `80 * product.size * eps * Lambda * ||Y||_1` allowance has no such
implementation-specific derivation. Merely relabeling it a certificate cannot
make it verified. Rump's review describes verification with explicit error
control: [Verification methods, Acta Numerica 19 (2010)](https://www.tuhh.de/ti3/paper/rump/Ru10.pdf).

Certificate refusal is one-sided evidence. For `z=w+a*w²`, `0<=a<1/2`,
`W=1+a(w+v)` and the exact minimum is `(1-2a)²>0`. The method can still fail its
finite degree/window budget on this demonstrably simple family.

### Quadrature and repeatedly cropped nonlinear functions are not exact products

An N-point periodic trapezoidal average obeys

`Q_N(f) = sum_l f_hat[l N]`.

The difference from the integral coefficient is the sum of nonzero aliased
modes. Speed `|z'|`, its reciprocal and `exp(-ik alpha)` generally have infinite
Fourier support even when z has finite support. Padding that suffices for a
polynomial product does not make these nonlinear operations exact. Analytic
periodic functions can converge exponentially, but their complex singularities
control the rate; see [Trefethen–Weideman, SIAM Review 56 (2014)](https://people.maths.ox.ac.uk/trefethen/publication/PDF/2014_149.pdf).

Likewise, repeated cropping represents functions of a compressed multiplication
operator, not generally a final crop of the full function. For example, with
`p=w+w^-1` and B=0, the cropped first product is zero and its repeated square
is zero, while the constant coefficient of `p²` is 2. The production method's
window refinement remains necessary even when every convolution is padded.

### Analytic derivative of the actual discrete trial

Write the implemented quadrature as

`R_k = mean(z sigma/mu * exp(-ik alpha))`, `mu=mean(sigma)`, `sigma=|z'|`.

For a displacement d, including the trial's Nyquist-mode removal,

`dot_sigma = Re(conj(z') d')/sigma`, `dot_mu=mean(dot_sigma)`.

If s is the spectral primitive anchored at theta=0 and `alpha=s/mu`, then
`dot_alpha=(dot_s-alpha*dot_mu)/mu`. Consequently

`dot_R_k = mean(exp(-ik alpha) * [d*sigma/mu + z*dot_sigma/mu`
`             - z*sigma*dot_mu/mu² - ik*z*sigma*dot_alpha/mu])`.

The new implementation differentiates this finite sum, its spectral primitive
and its normalization directly. It uses no integration-by-parts approximation
and no finite difference of geometry. Differentiation is exact for the
discrete smooth map in exact arithmetic; quadrature and floating-point errors
remain. The finite trial, projected increment and validity rules are unchanged.

## Measurements and decisions

Raw results and source/environment hashes:
[NF-001 bundle](../../../../results/validation/cleaned_interfaces/NF-001-outsider-review/README.md).
The numerical script finished in 45.3 s, sequentially with single-threaded
CPU BLAS. Host-wide load was not controlled; timings are diagnostic.

| Curve | K / M | Worst analytic versus existing FD column error | Analytic tangent grid-refinement error | Median preparation: CPU FD / analytic CPU / batched CUDA FD |
|---|---:|---:|---:|---:|
| Circle | 8 / 3 | 4.60e-10 | 2.38e-15 | 8.45 / 2.41 / 1.78 ms |
| Kite | 24 / 7 | 7.55e-10 | 1.57e-14 | 19.7 / 3.57 / 1.94 ms |
| Ellipse, aspect 10 | 24 / 7 | 7.47e-10 | 2.64e-14 | 19.3 / 4.50 / 1.88 ms |
| Saved core hook endpoint | 192 / 37 | 4.13e-9 | 4.81e-13 | 2854 / 225 / 35.6 ms |

All four finite trial curves were bit-identical at the same seeded step.
Centered differences improve quadratically before roundoff dominates; on the
hook their directional errors at steps 1e-5, 1e-6 and 1e-7 m are 2.38e-5,
2.38e-7 and 3.33e-9. Reducing the step to 1e-9 m worsens error to 2.25e-7.

On the kite and saved hook, real k=2 and damped k=2+0.5i, contrast 0.5, complete
finite-trial field derivatives agree with the reciprocal Jacobian within
2.42e-9 at step 1e-7 m. These include independent trace refinements 64→96.
The bounded two-frequency LM comparison accepts the same two steps, returns
normally, charges 18 units in each arm, and differs by 2.98e-13 relatively in
endpoint coefficients. Final losses are 6.4028071e-13 and 6.4028006e-13.

**Retain the analytic tangent as opt-in experimental code.** It removes the
FD step-size tradeoff and is 12.7× faster than sequential CPU preparation on
this hook. It is still 6.3× slower than the retained CUDA batching there, so
this does not justify replacing NU-006 by default. Local derivative success
and one small inverse are not full-trajectory/high-contrast qualification.

For the adversarial family, CPU and CUDA agree in status at windows 16/32.
All 12 accepted bounds (a=0, 0.25, 0.45, two windows, two devices) are below
the analytically known minimum. The 400-degree diagnostic cap makes a=0.49
and 0.499 inconclusive despite simplicity. The cusp a=0.5 and regular crossing
a=1 are not certified, and the reversed circle is refused for orientation.
The cap is a declared diagnostic budget, not a production-default change.

Quadrature on the aspect-100 ellipse has coefficient errors versus a 16384-point
reference of 6.06e-4, 5.50e-6, 2.83e-10 and 3.80e-15 at N=64, 256, 1024 and
2048. This demonstrates why “only exact transform engines” is too strong even
though refinement works well. The circle reaches roundoff already at N=64.

Independent reanalysis of all 3824 saved NU-007 bounds across 72 states finds
the original worst relative discrepancy 1.5356e-5, worst threshold-scaled gap
5.9667e-12, no threshold-side changes and minimum margin 0.0063912. **Retain
this as diagnostic support for a new gate, not retroactive adoption.** No fresh
NU-007 campaign was run, and the regularity lower-bound gate also matters.

## Remaining limits

Validation: the full cleaned-interface suite plus adjacent maintained-adapter
and control regressions passed **101 tests in 107.41 s**. A final focused run
passed **14 tests**, including an added odd-grid tangent regression (102
distinct tests covered). Complete runner tests exercise localization, fitting,
cleanup, frontier and endpoint audits with the legacy, NU-006 and analytic
selections. CLI plans and campaign selection identity are checked. The first
broader attempt caught a default-plan wording regression; it is corrected and
the original failed log is retained. Source hashes and logs are in
`validation.json`, `validation.log` and `validation_focused.log` in the bundle.

No all-36 campaign, interval-verified convolution, sample-free intersection
refusal, automatic independent trace/window/radial-degree controller, or
analytic-tangent CUDA implementation is established here. Those are separate
pieces of work, not conclusions that can be inferred from the present tests.
The original fitted results and failed arms remain intact.
