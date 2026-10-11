# Complex radius as a physical geometry chart

2026-10-11. Mathematical companion to [CG-001](CG-001_plan.md).

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
chart except where a transmission denominator vanishes. Their meromorphic
extension is sufficient locally, but not a global nonsingularity guarantee.

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

The implementation evaluates these analytic derivatives through order three.
Independent controls use the maintained Wronskian form, Cauchy contour
derivatives, nodal fields and a Hadamard radial shape derivative. The highest
order here is needed to classify folds, not just predict scattering fields.

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

## Fold mechanics and what a loop proves

Because d(t) is affine, `F(q,t)=A(q)-t B(q)`. Wherever B is nonzero, the
real stationary curve can be parameterized independently as `t(q)=A/B`.
At a fold `(qf,tf)`, require `F=Fq=0`, `Ft=-B != 0`, `Fqq != 0`.
Taylor expansion gives

    (q-qf)^2 = -2 Ft/Fqq * (t-tf) + higher-order terms.

The square root changes sign after one circuit around tf. A semicircle
to the side with no local real pair yields genuinely complex geometry. A
complete circuit returns to the other real root at the same t. Two circuits
restore the first root. The returned pair have opposite signs of Fq to leading
order, so a minimum normally becomes a maximum in this scalar family.

This is a topological branch exchange, not automatic progress in data fitting.
An adjacent fold may exchange the maximum for a different minimum, but its
attachment path and final data parameter must themselves be qualified. A
real endpoint at t below 1 is stationary for interpolated data, not necessarily
for the measured-data objective at t=1. Both losses must be reported.

Real pseudo-arclength introduces an augmented tangent constraint and can pass
the fold with real q while t reverses. Thus stopping natural-parameter
continuation is an inadequate sole control. A complex method must establish
additional useful branch access or a better endpoint before an inverse
advantage can be claimed.

## Applicability boundaries

The proof above is local to a simple fold and a holomorphic, finite forward
map. Pole cancellation margins sampled along a path do not prove that its
interior contains no poles or other critical values. Half-radius, half-step,
modal refinement and local square-root splitting checks test the proposed
interpretation, without converting floating-point tracking into a rigorous
interval certificate.

The source assumptions and primary links are in the pre-registered plan.
In particular, the transmission shape-holomorphy result's quantitative
nontrapping domain does not transfer unchanged to the high-index benchmark.
This study qualifies uniform complex scaling and scalar stationary sheets;
general complex Fourier boundaries, close-interaction quadrature, winding
selection in many dimensions, and an unchanged TG-002 recovery comparison
remain distinct research questions.
