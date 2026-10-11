# Track 12 — literature, derivation and conclusion audit

2026-10-11. Post-run interpretation audit of CG-001/002, requested by the
user. This adds primary-source checks and deductions from saved evidence;
it changes no experiment, frozen route, preregistration or raw receipt.

**Conclusion:** The scattering-derived scalar objective exhibits the local
sheet exchange predicted by classical simple-fold theory. Real
pseudo-arclength can traverse the same fold. The three tested positive
complex routes reach a nonreal stationary radius at measured-data t=1,
so they do not deliver a recovered real shape. Neither theory nor these
experiments establishes a global obstruction to useful complex continuation,
or guarantees that a useful real endpoint is accessible from this start.

## Claims and their support

| Claim | Mathematical basis | Experimental evidence and scope |
|---|---|---|
| Complex radius defines an analytic scattering instrument locally. | Finite cylindrical-wave sum, analytic derivatives and nonzero transmission denominators; [derivation](DERIVATION.md#a-stable-exact-scattering-coefficient). | Nodal, Cauchy and cutoff checks qualify the implementation numerically. No analytic tail bound or whole-domain pole exclusion. |
| A small loop around an isolated simple fold exchanges two roots; two loops restore the start. | Exact local coordinate `t-tf=h0*u^2`, derived below and in the [full proof](DERIVATION.md#exact-local-fold-mechanics). | One-loop exchange, two-loop error 7.64e-14, reverse, half-step and half-radius controls. The finite experimental loop is numerically qualified, not interval-certified. |
| This scalar exchange swaps a minimum and maximum. | Opposite signs of `Fq` on the local real pair. | Recorded Hessians +3751.70 and −9453.63 at the same interpolated-data t. No automatic measured-data improvement follows. |
| The fold does not defeat all real continuation. | The real augmented Jacobian has determinant `-/+Ft`, nonzero at the fold. | CG-001's completed real pseudo-arclength control passes it. CG-002's later corrector failure is not a proved branch barrier. |
| The fixed doglegs fail the requested real-return criterion. | A real shape requires a real radius; stationarity in complex space alone is insufficient. | 0/3 positive heights return real at t=1. Their imaginary radius is about 24.43 micrometres, 48,858 times the declared tolerance. This is a result about those routes. |
| Equal dogleg endpoints establish unchanged winding. | **Unsupported converse.** Distinct path classes can act identically on one root. | Endpoint equality is established; the path classes and full sheet permutations are not. |

The quantities above concern a fixed-center disk unable to represent the
displaced TG-002 circle exactly. They do not measure unrestricted shape
recovery. Here “exact transmission disk” describes the separated physical
model; computation uses a finite modal cutoff and floating-point arithmetic.

## Primary literature and assumption matching

1. **Glendinning and Simpson, _Normal forms for saddle-node bifurcations:
   Takens’ coefficient and applications in climate models_ (2022).**
   Section 1, Eq. (4), gives the scalar fold nondegeneracy conditions;
   §4, Eq. (11), gives the quadratic stationary-curve expansion. This
   supports the real local fold model. The analytic sheet-exchange proof
   below is our application of holomorphic factorization, rather than a
   claim that a smooth dynamical conjugacy itself proves monodromy.
   [Primary full text](https://arxiv.org/pdf/2208.09633).

2. **Duff, Hill, Jensen, Lee, Leykin and Sommars, _Solving polynomial systems
   via homotopy continuation and monodromy_.** Section 2.1 defines the
   permutation induced by lifting a loop; Remark 2.1 separates the
   finite-covering argument from algebraic assumptions. This provides the
   correct path-action framework. Their polynomial completeness and
   irreducibility results do not establish a global finite covering for
   this meromorphic Bessel family with bounded geometry domain.
   [Primary full text](https://arxiv.org/pdf/1609.08722).

3. **Dickson, Kelley, Ipsen and Kevrekidis, _Condition Estimates for
   Pseudo-Arclength Continuation_ (2006).** Definition 2.5,
   Eqs. (2.3)–(2.4), and Corollary 2.6 describe the augmented continuation
   system and local Newton framework. Our explicit 2×2 determinant below
   establishes scalar regularity directly; we do not substitute dimension
   one into a higher-dimensional singular-value bound or infer global
   corrector convergence. [Primary full text](https://arxiv.org/pdf/math/0603716).

4. **Dölz and Henríquez, _Parametric Shape Holomorphy of Boundary Integral
   Operators with Applications_.** Proposition 5 states holomorphic
   inversion and local inverse stability under
   `||M-T|| < 1/||M^(-1)||`; §3.3 uses invertibility for solution
   holomorphy. Their detailed scattering application is sound-soft in a
   three-dimensional Lipschitz setting. It motivates a conditional operator
   construction, not certification of our two-dimensional transmission
   implementation or arbitrary complex shapes.
   [Primary full text, v2](https://arxiv.org/html/2305.19853v2).

5. **Hiptmair, Schwab and Spence, _Frequency-Explicit Shape Holomorphy in
   Uncertainty Quantification for Acoustic Scattering_.** Theorem 4.1
   establishes solvability bounds and **Corollary 4.2** gives holomorphy in
   a controlled complex radial neighborhood. They require `n_i<1`, the
   stated star-shaped geometry bounds, and a frequency-dependent bound on
   the imaginary perturbation. In their Helmholtz normalization `n_i`
   corresponds to our squared wave-number ratio, i.e. contrast. Thus the
   theorem's quantitative domain does not cover contrasts 4 or 13.3.
   Section 1.3 discusses scaling and high-index resonances. This is a
   reason to monitor poles, not evidence that a pole caused our endpoint
   failure. [Primary full text, v2](https://arxiv.org/html/2408.01194v2).

6. **NIST Digital Library of Mathematical Functions.**
   [Eq. 10.6.7](https://dlmf.nist.gov/10.6.E7) supplies the cylindrical
   derivative recurrence used in the radius jets;
   [§10.11](https://dlmf.nist.gov/10.11) supplies analytic continuation and
   conjugation identities. These justify the local special-function
   algebra, not a global pole-free transmission region.

## Derived theory used in the conclusion

Write `F=Phi_q`, with Phi the analytic mirror extension of the real
least-squares loss. At an exact real fold assume
`F=Fq=0`, `a=Ft!=0`, `b=Fqq!=0`. Locally solve `t=T(q)` and factor

    T(q)-tf = (q-qf)^2 h(q),    h(qf) = h0 = -b/(2a).
    u = (q-qf) sqrt(h(q)/h0),    t-tf = h0*u^2.

The local square root is analytic and `u'(qf)=1`. This is the exact local
sheet-exchange proof. A loop changes the sign of u; two loops restore it.
It requires the loop to lie in the isolated analytic fold chart. Merely
detecting a small stationarity residual at sampled states does not prove
that requirement for an entire finite loop.

For the observed `a,b>0`, let `epsilon=tf-t>0`, `s=sqrt(2*a*epsilon/b)`.
Then the upper/lower roots have Hessians `+/-b*s+O(epsilon)` and hence are
a local minimum/maximum. The root separation and intervening loss barrier
satisfy

    Delta_q = 2*s + O(epsilon^(3/2)),
    Delta_Phi = (2/3)*b*s^3 + O(epsilon^(5/2)).

These are deductions for this loss, with the parity and integration argument
in the [derivation](DERIVATION.md#minimummaximum-exchange-and-quantitative-predictions).
They predict relative errors of order epsilon. In multiple shape dimensions
a generic fold changes the Hessian index by one; a minimum usually pairs
with an index-one saddle, not a maximum.

At the fold, the real tangent is `(+/-1,0)` and the pseudo-arclength
Jacobian is `[[0,a],[+/-1,0]]`. Its nonzero determinant explains why the
successful real control is expected. Finally, mirror symmetry gives
`F(conj(q),conj(t))=conj(F(q,t))`: uniqueness of regular continuation
forces reflected paths to have conjugate endpoints, without forcing either
endpoint to be real.

## Quantitative check against saved evidence

The stored fold gives `a=46.21381446298`, `b=35979230.42020`, and original
`epsilon=0.01156901262290102`. Substitution into the derived formulas gives:

| Diagnostic | Original loop | Half-radius loop |
|---|---:|---:|
| Observed / predicted root separation | 1.0365596571 | 1.0180096250 |
| Predicted loss barrier | 0.000122893798119 | 0.0000434495190077 |
| Observed loss barrier | 0.000125042412211 | 0.0000438261313451 |
| Observed / predicted loss barrier | 1.0174835030 | 1.0086678137 |

Halving epsilon approximately halves both relative discrepancies, consistent
with the derived O(epsilon) correction. Two radii support this interpretation;
they do not establish an asymptotic convergence rate or a remainder bound.
The separation check was preregistered. The loss-barrier comparison is
**post hoc**, with no new parameter fitting, forward evaluation or trajectory.
Its half-radius minimum loss comes from the saved restored two-loop endpoint,
which differs from the starting radius by 1.26e-13 or less.

All numbers are recomputed by
`python -m experiments.benchmark.cg001_report --no-plots` from the immutable
[CG-001 run-02 receipts](../../../results/validation/complex_geometry/CG-001/run-02/continuation.json).
The [generated report](../../../results/validation/complex_geometry/report/README.md)
and [validation JSON](../../../results/validation/complex_geometry/report/validation.json)
retain these arithmetic diagnostics separately from experimental gates.

## Research consequence

The next discriminating question is whether a real minimum at t=1 lies in
the continuation orbit accessible from the prescribed start, within a
qualified analytic domain. If it does, one can investigate ordered loop
sequences and their observed sheet permutations to reach it. Equal endpoints
for three dogleg heights do not answer this question: even zero and two
windings around one simple fold have the same action on the starting root.

A rigorous result for this particular scattering instrument would additionally
need an enclosed exact fold, a controlled analytic domain, uniform derivative
remainder bounds and a modal-tail bound. General complex Fourier geometry
would also require its own operator and derivative qualification. These
are open research tasks; no global return, inverse convergence, or speed
advantage follows from the current evidence. The contribution so far is the
physical scattering test and its reproducible controls, not a new monodromy
theorem.
