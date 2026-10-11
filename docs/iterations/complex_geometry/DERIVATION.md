# Complex radius as a physical geometry chart

2026-10-11. Mathematical companion to [CG-001](CG-001_plan.md).
The [literature and conclusion audit](LITERATURE_THEORY_AUDIT.md) maps the
claims to primary sources, numerical evidence and remaining assumptions.

## What becomes complex

The boundary is `(x(theta), y(theta)) = (q cos(theta), q sin(theta))`.
For nonreal q, both Cartesian coordinates are complex numbers. This differs
from storing an ordinary real planar curve as the single number `x+i*y`.
The package's `FourierCurve.nodes` splits that encoding into real coordinates;
it cannot implement this chart by merely accepting complex coefficients.

The analytic metric uses a bilinear dot product. Consequently speed squared
is q², and the regularized squared pair distance is also q². In a simply
connected neighborhood of a positive real radius, choosing `sqrt(q²)=q`
continues the real disk geometry. The exact separated transmission solution
encodes the same continuation without constructing sampled complex normals.
Principal Hankel functions are analytic in the chosen right-half-plane radius
chart. Transmission quotients can have poles where their denominators vanish.
This meromorphic construction is sufficient locally, but is not a global
nonsingularity guarantee.

## A stable exact scattering coefficient

For angular mode n, incident field coefficient a, exterior outgoing
coefficient b and interior regular coefficient c, the interface conditions are

    a Jn(kq) + b Hn(kq) = c Jn(ki q)
    a k Jn'(kq) + b k Hn'(kq) = c ki Jn'(ki q).

Eliminating c gives

    b/a = [ki Jn'(ki q) Jn(kq) - k Jn(ki q) Jn'(kq)]
          / [k Jn(ki q) Hn'(kq) - ki Jn'(ki q) Hn(kq)].

Graf's source expansion contributes `(i/4) Hn(k rho_source)` and the angular
phase; evaluation at a receiver contributes its Hankel wave. Only the 24
observed paired entries are evaluated. This is the same equal-density
transmission physics used by the real Müller solver.

For any cylindrical function Z,

    d^m Z_n(kq)/dq^m = (k/2)^m sum_{l=0}^m (-1)^l C(m,l) Z_{n-m+2l}(kq).

Apply Leibniz to numerator N and denominator D. If C=N/D, then

    C^(m) = [N^(m) - sum_{l=1}^m C(m,l) D^(l) C^(m-l)] / D.

The cylindrical derivative identity is [DLMF 10.6.7](https://dlmf.nist.gov/10.6.E7)
with the chain rule. Hankel continuation and conjugation are described in
[DLMF §10.11](https://dlmf.nist.gov/10.11). In particular, reflection and
conjugation exchange outgoing/incoming Hankel functions; the mirror must
not be replaced by the unchanged outgoing function at q.

The implementation evaluates these analytic derivatives through order three.
Independent controls use the maintained Wronskian form, Cauchy contour
derivatives, nodal fields and a Hadamard radial shape derivative. The highest
order here is needed to classify folds, not just predict scattering fields.
The implemented map is a fixed finite-mode truncation of the exact separated
solution. Its local analyticity follows directly from the finite sum and
nonzero denominators. Agreement after adding 12 modes is numerical evidence,
not a certified bound on the infinite-series tail.

## Holomorphic least squares and its exact Hessian

Fix real frequency and normalize observed channels by a fixed real weight.
Let `gsharp(q) = conj(g(conj(q)))`. If `g(q)=sum a_j q^j` locally, the mirror
has coefficients `conj(a_j)`, hence is holomorphic in q. Set

    d(t) = g(q0) + t delta,    delta = d_observed-g(q0)
    dsharp(t) = conj(g(q0)) + t conj(delta).

Conjugating t would destroy holomorphy. With `r=g-d` and `rs=gsharp-dsharp`,

    PhiC = rs.T r / 2
    F = (gsharp'.T r + g'.T rs)/2
    Fq = (gsharp''.T r + g''.T rs)/2 + gsharp'.T g'
    Fqq = (gsharp'''.T r + g'''.T rs)/2
          + 3(gsharp''.T g' + gsharp'.T g'')/2.

On the real axis PhiC is the ordinary nonnegative least-squares objective,
F its derivative and Fq its Hessian. Off the real axis PhiC is complex and
has no ordinary minimization ordering. The tracker solves a square analytic
stationarity equation; it does not minimize a complex loss.

The residual terms in Fq matter at nonzero-residual folds. Replacing Fq by
`gsharp'.T g'` is a Gauss–Newton approximation and cannot establish the same
fold of the actual objective. One real observable fitted exactly at its
turning point is a misleading control: `F=p'(p-d)` then has Ft=0 and is
not the generic simple stationarity fold tested here.

## Exact local fold mechanics

Because d(t) is affine, `F(q,t)=A(q)-t B(q)`. Wherever B is nonzero, the
real stationary curve can be parameterized independently as `t(q)=A/B`.
Assume F is holomorphic near an **exact real fold** `(qf,tf)` with

    F = Fq = 0,    a = Ft != 0,    b = Fqq != 0.

These are the classical scalar fold conditions; compare
[Glendinning–Simpson, §1 Eq. (4), §4 Eq. (11)](https://arxiv.org/pdf/2208.09633).
Their real smooth normal-form result alone is not a complex continuation
theorem. The following analytic factorization supplies that step here.

Since a is nonzero, the holomorphic implicit-function theorem gives a local
stationary curve `t=T(q)`. Differentiating `F(q,T(q))=0` twice gives

    T'(qf) = 0,    T''(qf) = -b/a.
    T(q)-tf = (q-qf)^2 h(q),    h(qf) = h0 = -b/(2a) != 0.

Choose the analytic square root of `h(q)/h0` equal to 1 at qf, in a sufficiently
small neighborhood where h has no zeros. Then

    u = (q-qf) sqrt(h(q)/h0),    u'(qf) = 1,
    t-tf = h0 u^2.                                      (1)

Thus u is an invertible local coordinate and (1) is exact, not a truncated
Taylor model. Within this isolated fold chart, one circuit of t around tf
changes u to -u and exchanges the two stationary roots; two restore the start.
Because F is real on real `(q,t)`, this coordinate respects conjugation.
On the side `(t-tf)/h0>0`, the two local roots are real; on the other side
they form a nonreal conjugate pair. The theorem establishes a sufficiently
small chart; it does not bound the size of the particular experimental loop.

## Minimum/maximum exchange and quantitative predictions

For the selected fold, a and b are positive. Write `epsilon=tf-t>0` and
`s=sqrt(2*a*epsilon/b)`. Equation (1) and its inverse imply

    q_plus/minus = qf +/- s + O(epsilon),
    Fq(q_plus/minus,t) = +/- b*s + O(epsilon).

For sufficiently small epsilon, the upper-radius root is a strict local
minimum and the lower-radius root a strict local maximum of the real
radius-family objective. More precisely, the two roots are values of the
same analytic inverse coordinate at +s and -s. Even powers cancel from
their difference, giving

    q_plus-q_minus = 2*s + O(epsilon^(3/2)).              (2)

Integrate `F = -a*epsilon + b*(q-qf)^2/2 + ...` between these stationary
points. The leading loss barrier is

    Phi(q_minus,t)-Phi(q_plus,t)
        = (2/3)*b*s^3 + O(epsilon^(5/2)).                (3)

For the remainder order in (3), put `epsilon=m^2`: the two stationary values
are exchanged under `m -> -m`, so their difference is odd in m; stationarity
eliminates the linear term. The first terms are therefore cubic and quintic.
Both (2) and (3) have relative corrections O(epsilon). The saved full- and
half-radius loops give separation ratios 1.03656 and 1.01801 and loss-barrier
ratios 1.01748 and 1.00867, consistent with that order. The barrier comparison
is a **post hoc derived diagnostic**, not an added preregistered success gate;
see the [audit](LITERATURE_THEORY_AUDIT.md#quantitative-check-against-saved-evidence).

Here `R=50 mm*q`, so `Phi_RR=Fq/(50 mm)^2`. Rescaling changes Hessian
magnitudes but preserves their signs. For multiple shape parameters, a
generic corank-one gradient fold instead changes the number of negative
Hessian eigenvalues by one. To see the distinction, eliminate transverse
variables using their invertible Hessian block; completing the quadratic
form leaves that block plus the scalar reduced Hessian. Only the latter
changes sign. A minimum then pairs with an index-one saddle, generally not
a maximum. No such multidimensional fold has been tested here.

This is a topological branch exchange, not automatic progress in data fitting.
An adjacent fold may exchange the maximum for a different minimum, but its
attachment path and final data parameter must themselves be qualified. A
real endpoint at t below 1 is stationary for interpolated data, not necessarily
for the measured-data objective at t=1. Both losses must be reported.

## Why real pseudo-arclength also crosses the fold

At the fold a unit real tangent `(qdot,tdot)` satisfies
`Fq*qdot+Ft*tdot=0`, hence `(qdot,tdot)=(+/-1,0)` in these unscaled coordinates.
Adding the tangent constraint gives the augmented Jacobian

    J_aug = [[0, a], [+/-1, 0]],    det(J_aug) = -/+a != 0.

The local stationary curve is regular even though q cannot be represented as
a single-valued differentiable function of t there. Real pseudo-arclength
can pass the fold while t reverses. This direct scalar calculation is the
appropriate specialization of the framework in
[Dickson et al., Definition 2.5 and Eqs. (2.3)–(2.4)](https://arxiv.org/pdf/math/0603716).
It does not guarantee success of a finite-precision corrector over the whole
branch. Stopping natural-parameter continuation is therefore an inadequate
sole control for an inverse advantage.

## Symmetry, path dependence and real return

The mirror construction gives

    F(conj(q),conj(t)) = conj(F(q,t)).                    (4)

Starting at a real root, conjugating a regular solution along a parameter
path produces a solution along the conjugate path with the same start.
Where analytic continuation is unique, the reflected lift is therefore the
conjugate lift. The negative-height arms check (4); conjugate endpoints need
not be real, and those arms are not independent discoveries of new topology.

If regular stationary sheets form a covering over a parameter domain,
homotopic paths with fixed endpoints induce the same continuation action.
The converse fails: different path classes can act identically on a chosen
root. Already in (1), zero and two windings restore the same root. Thus the
three positive doglegs' equal endpoints do **not** establish equal winding,
equal homotopy classes, or equal permutations of all roots. With several
critical values, even the ordered sequence of loops can matter; integer
winding counts alone can omit that order. The covering formulation and its
assumptions are explicit in
[Duff et al., §2.1 and Remark 2.1](https://arxiv.org/pdf/1609.08722).

For this meromorphic, domain-restricted problem, a global covering without
escape or pole encounters has not been proved. Neither local fold theory nor
the nonreal endpoint at t=1 determines whether another real minimum belongs
to the start-accessible continuation orbit. Establishing such a target's
accessibility is a prerequisite to a guaranteed route-selection claim.

## Applicability boundaries

The proof above is local to a simple fold and a holomorphic, finite forward
map. Pole cancellation margins sampled along a path do not prove that its
interior contains no poles or other critical values. Half-radius, half-step,
modal refinement and local square-root splitting checks test the proposed
interpretation, without converting floating-point tracking into a rigorous
interval certificate.

The [literature audit](LITERATURE_THEORY_AUDIT.md) records the precise source
assumptions. In particular, the transmission shape-holomorphy result's
quantitative nontrapping domain does not transfer unchanged to the
high-index benchmark. No certified fold enclosure, uniform derivative
remainder or modal-tail bound has been computed. Local expansions cannot
be extrapolated quantitatively from tf≈0.649 to t=1 without such control.
This study qualifies uniform complex scaling and scalar stationary sheets;
general complex Fourier boundaries, close-interaction quadrature, winding
selection in many dimensions, and an unchanged TG-002 recovery comparison
remain distinct research questions.
