# Node free geometry updates and coefficient certificates

2026-10-11. Investigation of Track 7 in the
[architectural backlog](architectural_experiment_backlog_2026-10-11.md).
Implementation inspected at `e09be526` on the existing
`feature/shape-frequency-continuation` checkout. This is a literature and
theory assessment, with read-only checks of saved evidence. No new numerical
experiment or solver change accompanies it.

**A geometry update without curve quadrature is mathematically feasible. The
best supported first construction preserves our centred arclength update and
computes its nonlinear functions in coefficient space, with complete residual
and tail bounds.** The previous failed coefficient update changed the physical
update space and the finite map as well as removing quadrature. Its failure
does not establish that coefficient computation of the maintained map fails.

The difficult parts are managing nonlinear approximation errors, preserving
the complete trial derivative, and making geometry certificates decisive near
thin gaps. A direct divided-difference perturbation bound gives a stronger
cheap certificate than our present squared-modulus perturbation bound.
Interval subdivision provides a complementary route for difficult curves and
crossing witnesses. Neither practical cost nor full inverse retention follows
from these mathematical observations.

## Scope of the requirement

For this investigation, **node free geometry** means that production geometry
construction and its decisions use coefficients, algebraic operations and
verified bounds, without a discretization of the curve into evaluation nodes.
In particular, computing speed or a nonlinear phase at points and transforming
those values back is quadrature, even when the transform is an FFT.

Padded FFTs implementing finite linear convolution are compatible with this
requirement. So are coefficient crops whose discarded terms are bounded,
coefficient linear solves, and subdivision certificates that bound entire
parameter intervals. A certificate cell is a range enclosure; accepting it
cannot rest on values at its vertices. Fixing a phase origin by a coefficient
sum is an algebraic normalization, rather than a quadrature discretization.
These distinctions should be explicit in any eventual implementation receipt.

This is stronger than the existing project's physics-only use of “node free”,
which permits parameter-space geometry quadrature. That existing claim is not
being reinterpreted retrospectively. See the current
[sampling scope](../reference/node_free_scope.md).

Three independent properties must remain visible:

| Property | What establishes it |
|---|---|
| Geometry does not use nodes | The operations actually used in construction, derivatives and decisions |
| Geometry approximation is accurate | Bounds on nonlinear approximation, discarded coefficients and complete derivatives |
| Validity is rigorous in floating point | Outward enclosures for coefficients, arithmetic, residuals and inequalities |

A sample-free float64 calculation can have the first property without the
third. An interval proof may still be expensive. Geometry certification alone
does not certify the accuracy of the Müller forward operator.

## Evidence that constrains the design

### The maintained map contains an essential centring operation

In physical length units, the intended continuous construction is

$$
T_z(a)=z+\Pi_K\{R[z+h_a(\alpha_z)n_z]-R[z]\},\qquad
n_z=-i z'/|z'|.
$$

Here $R$ returns Fourier coefficients in normalized arclength, $K$ is the
stored geometry band, and the scalar update $h_a$ has its own band $M$.
The present implementation approximates the moved curve on a uniform grid,
then computes $R$ by quadrature. The base projection is cached and subtracted.
The subtraction gives an exact zero update and cancels the baseline projection
bias in the increment. It does not make the stored curve exactly constant
speed. Code:
[spectral.py](../../solvers/bem_inverse/spectral.py),
[certified.py](../../solvers/bem_inverse/certified.py),
[geometry.py](../../solvers/bem_inverse/geometry.py).

The old proposal's suggested replacement Jacobian is not the Jacobian of this
map. Its code review found a worst column discrepancy of **66%** for the
simple weight $\cos(m\alpha)|z'|$, compared with the complete projected
tangent. At low storage bands, cropping also changed the direct normal
weights by up to **10%**. The correct implementation contract is the
coefficient velocity of the *complete finite trial*, followed by its Hadamard
weight. [Review against code](../iterations/cleaned_interfaces/iteration_08/02_proposals/02_review_against_code.md).

### Direct coefficient normal moves failed through parameter distortion

The NU-001 map was affine in the update coordinates:

$$
z_{\rm new}=\Pi_K[z+g_a(-iz')].
$$

Before cropping, its physical normal displacement is $g_a|z'|$. It is
therefore a different update space from a fixed unit-normal displacement in
arclength. The tangential variant attempted to control speed with a linear
correction around nearly uniform speed.

| Historical case | Baseline maximum speed ratio | Direct normal arm | Tangential arm |
|---|---:|---:|---:|
| C shape | 1.154 | 21.304 | 12.103 |
| Hook | 1.182 | 288.247 | 12.869 |
| Kite | 1.078 | 3914.595 | 1.700 |

The direct arm matched **2/6** cases and the tangential arm **3/6**, under the
frozen historical rules. Neither met the drift criterion. These figures were
checked against the saved `max_speed_ratio` fields, rather than inferred from
the later narrative. [Results](../iterations/cleaned_interfaces/iteration_09/01_results.md),
[raw drift record](../../results/validation/cleaned_interfaces/NU-001-drift/drift.json).

This is negative evidence about those finite constructions. It does not
compare coefficient algebra with quadrature for an otherwise identical map.
Also, first-order tangential invariance does not imply that a finite Euler
step containing a tangential displacement preserves shape. Cropping can
introduce a first-order normal component too.

### A separate arclength reset cannot repair low band drift harmlessly

NU-002 replayed 196 historical states. At $K=8$–20, even all 19 selected
baseline states with speed ratio above 1.02 failed the shape-preservation gate
when reset to arclength at their existing band. Their measured shape changes
were $2.2\times10^{-4}$–$2.2\times10^{-3}$ of mean speed, above the
$10^{-5}$ gate. At $K=192$, all 36 baseline states reset within
$8.1\times10^{-12}$ of mean speed. Severe drifted states still failed there.
[Reset replay](../iterations/cleaned_interfaces/iteration_10/01_results.md).

The implication is specific: **preserve the centred increment first**. A
threshold-triggered reset at low $K$ changes the represented shape and cannot
be assumed to be a harmless coordinate operation. Increasing the working
band for nonlinear calculations is different from increasing the stored
shape band or the allowed update band.

### The spectral centred map has substantial retention evidence

NU-003 retained all six historical comparisons and the same accepted steps in
72 stages, with endpoints within $6.0\times10^{-8}$ of mean speed of the
spline reference. It removed splines and inverse arclength interpolation, but
retained quadrature. Its sequential CPU geometry preparation was slower.
[NU-003 results](../iterations/cleaned_interfaces/iteration_11/01_results.md).

The more recent TG-002 geometry replay GC-001 covered 31 states and 279 common
moves. All four implementations accepted 277 and made the same two sampled
self-intersection refusals. Of 278 qualified refined references, the worst
parameter-aligned curve error was **400.83 nm** for spline and **0.1855 nm**
for spectral. One curve reference remained unresolved and was excluded from
accuracy rankings. The large spline discrepancies were traced mainly to
aliasing at the final uniform-arclength sampling and FFT crop.
[GC-001 results](../iterations/cleaned_interfaces/iteration_30/01_results.md),
[raw report](../../results/validation/cleaned_interfaces/GC-001/report.json).

This strengthens the case for computing retained arclength coefficients
directly. It does not make the present spectral quadrature sample free.

### The validity fallback is active on the difficult TG-002 cases

The ON-001 baseline has 2,631 trial constructions, including audit moves.
Read-only aggregation of its 30 `fit_result.json` files gives:

| Case | Coarse moved curve accepted by sampled fallback | Coarse moved curve refused by sampled fallback |
|---|---:|---:|
| Aphex contrast 0.5 | 2 | 5 |
| Aphex contrast 4 | 1 | 1 |
| Aphex contrast 13.3 | 27 | 37 |
| Hook contrast 13.3 | 16 | 0 |
| Other 26 cases | 0 | 0 |
| Total | 46 | 43 |

The fine moved role repeats the 46 acceptances. Candidate stored curves have
zero sampled fallback acceptances and refusals. These are *recorded sampled
verdicts*, not independently proved crossing witnesses. Simply deleting the
fallback changes the decision contract on these paths.
[Raw receipts](../../results/validation/cleaned_interfaces/ON-001/all_B/runs/),
[scope audit](../reference/node_free_scope.md).

### Existing counterexamples prohibit convenient shortcuts

The regular crossing curve $z(w)=w+w^2$ has $W=1+w+v$ and a zero on the
two-torus. Nevertheless, a finite compressed positivity test accepted a
positive proposed lower bound. Repeatedly cropped products also need not
equal a final crop of the true nonlinear function. A simple example is
$p=w+w^{-1}$: at working band zero, squaring the cropped $p$ gives zero,
although $[p^2]_0=2$.

Thus a positive finite Toeplitz matrix, a bounded compressed Chebyshev
recurrence, or agreement between two working windows cannot alone certify
global geometry. [Independent review](../iterations/cleaned_interfaces/node_free_modal_muller_review.md),
[NF-001 audit](../iterations/cleaned_interfaces/iteration_17/01_results.md).

## Literature and applicability

The following are primary papers, author texts or official implementation
documentation. Equations derived below are adaptations for this repository,
rather than claims that a cited paper implemented our geometry engine.

| Source and location | What it supplies | Applicability here |
|---|---|---|
| [Borges, Rachh and Greengard, penetrable inverse scattering](https://arxiv.org/html/2210.11607v1), Section 2.2, equations 10–12 | Normal perturbations in arclength harmonics followed by Fourier representation in the new arclength | Strong precedent for preserving the gauge. Their quadrature, acquisition and trust region differ from ours. |
| [Koga, periodic planar curve reparametrization](https://arxiv.org/pdf/2110.12432), equations 2.9, 3.6–3.7 | Tangential speed control and direct access to arclength Fourier coefficients by change of variables | The identity applies to a regular periodic curve. Koga evaluates it with sampled quadrature and a NUFFT; the coefficient implementation below is an adaptation. |
| [Gröchenig, Wiener lemma](https://homepage.univie.ac.at/karlheinz.groechenig/preprints/inzell.pdf), classical formulation and polynomial norm estimates | Inversion of nonvanishing absolutely convergent Fourier series; finite polynomial norm estimates | Supports coefficient inverses. For our finite Laurent polynomials, analyticity near the torus also gives a direct route to convergent reciprocal coefficients. |
| [Lessard, verified convolution](https://www.math.mcgill.ca/jplessard/Publications_files/rig_FFT.pdf), Sections 2–4 and Remark 1.3 | FFT convolution enclosures combined with Banach algebra tail estimates, including multidimensional extensions | A concrete arithmetic model for our residual checks. It is not a certification of our NumPy or CUDA FFT implementation. |
| [NIST DLMF, Jacobi–Anger expansions](https://dlmf.nist.gov/10.12), equations 10.12.1–10.12.3 | Bessel expansions of oscillatory exponentials | Supplies explicit scalar Chebyshev coefficients for the arclength phase. Composing the scalar polynomial with a Fourier polynomial is a separate coefficient operation. |
| [Dritschel and Rovnyak, operator Fejér–Riesz theorem](https://arxiv.org/pdf/0903.3639), Theorem 2.1 and Section 5 | Coefficient factorization of nonnegative univariate trigonometric polynomials; multivariate positivity distinctions | Useful for speed and box constraints. A factor identity differs from testing positivity of a finite Toeplitz compression. |
| [Dritschel, Klep, McCullough and Volčič, 2026 addendum](https://arxiv.org/html/2608.23073v1), Theorem 1.1 and Section 2.2 | Bivariate matrix factorization existence and correction of an earlier degree bound | No universal total factor-degree bound from input degree alone. This prevents treating a small fixed SOS program as a universally decisive certificate. |
| [Yap, complete subdivision for Bézier intersection](https://cs.nyu.edu/exact/doc/subdiv1.pdf), abstract and separation criteria | Exact adaptive subdivision, including tangential intersection under the stated algebraic hypotheses | Supports the geometric approach. Our rational torus charts and self-intersection diagonal need their own adaptation. |
| [Ham, Mitchell, Paganini and Wechsung, automated shape differentiation](https://link.springer.com/article/10.1007/s00158-019-02281-z), Section 2 | Perturbation-of-identity diffeomorphisms and derivatives of the transformed problem | Precedent for ambient deformations. The finite polynomial coefficient map and its bounds below are our construction. |
| [Beceanu, Hong, Kwon and Lim, conformal Laplacian formulation](https://arxiv.org/pdf/2112.11026), Section 2 and equation 2.4 | Exterior conformal coordinates and coefficient recurrences for Faber and Grunsky structure | Relevant alternative coordinates. This is a Laplacian eigenvalue study using Helmholtz layers, not an inverse transmission qualification. |
| [Kozak, Krajnc, Rogina and Vitrih, PH cycloidal curves](https://osebje.famnit.upr.si/~vito.vitrih/papers/PHC_JNM.pdf), Sections 1–2 and Lemma 3.4 | Trigonometric extensions of Pythagorean-hodograph curves with accessible speed and length | Motivates a different coordinate family. The periodic Laurent square construction below is derived here and needs separate representation analysis. |
| [Rump, verification methods](https://www.tuhh.de/ti3/paper/rump/Ru10.pdf), Sections 1.1–1.4, 8, 13 and 14.2 | Inclusion arithmetic, distinction between failed sufficient tests and invalidity, verified roots and semidefinite problems | Governs what can be claimed when a certificate succeeds, fails or meets a degenerate input. |

Coefficient-function validation is an established computational practice.
[RadiiPolynomial.jl](https://github.com/OlivierHnt/RadiiPolynomial.jl/blob/main/docs/src/radii_polynomial_approach.md)
documents the separation between approximation, finite/tail bounds and an
existence conclusion. The recent
[Lean radii-polynomial framework](https://arxiv.org/html/2610.02335v1), Section 5,
also gives a formalized square-root example. These are useful precedents for
error accounting; neither directly provides our periodic arclength update.
Formalizing the entire solver is not a prerequisite for a useful geometry
engine.

## Computing the centred update in coefficients

The deductions in this section concern smooth regular real planar curves.
Complexified geometry is a different problem: absolute value, positivity and
the real arclength map cannot simply be continued holomorphically.

Write

$$
z(\theta)=\sum_{|j|\le K}z_j e^{ij\theta},\quad
S=z'\overline{z'},\quad \sigma=\sqrt S,\quad
\mu=[\sigma]_0=L/(2\pi).
$$

For a Fourier series, define the coefficient norms

$$
\|f\|_A=\sum_j|f_j|,\qquad
\nu(f)=\sum_j |j|\,|f_j|.
$$

They bound the uniform function and derivative norms. Products are linear
convolutions. In two variables the first norm sums over both indices.

### Exact constant speed is incompatible with a general finite Laurent curve

**Deduction.** Let the nonzero extreme modes of $z'$ be $p<q$. The coefficient
of order $q-p$ in $z'\overline{z'}$ is uniquely
$(z')_q\overline{(z')_p}$ and cannot vanish. Constant speed therefore requires
a single derivative mode. Periodicity excludes derivative mode zero, and
integration gives a circle traversed an integer number of times. Simplicity
and counterclockwise orientation select one positive traversal.

This prohibits an exactly constant-speed finite Laurent representation of a
general shape. It does **not** prohibit a coefficient computation to controlled
tolerance, extra working modes, or a different representation. It also does
not say that the present baseline stores exact arclength curves.

### Speed and reciprocal speed can be bounded by algebraic residuals

A coefficient algorithm can construct a real Laurent polynomial $q$ intended
to approximate $\sigma$. One possibility is Newton iteration for
$q^2=S$ in a working window. Another is a scalar polynomial approximation to
$\sqrt x$ on a certified positive interval, composed with $S$ by convolution.
Both need control of the full residual and of $q$'s sign.

**Deduction.** If $q\ge m_q>0$, $S\ge a>0$, and the *complete* residual
satisfies

$$
r_s=\|q^2-S\|_A,
$$

then

$$
\|q-\sqrt S\|_\infty\le
\frac{r_s}{m_q+\sqrt a}.
$$

The proof divides $q^2-S$ by $q+\sqrt S$. If no independent $a$ is available,
$r_s<m_q^2$ proves $S\ge m_q^2-r_s>0$ and supplies one. A cheap positive
bound is $m_q=q_0-\sum_{j\ne0}|q_j|$ when this is positive. Interval
subdivision or a verified univariate factor certificate can handle harder
cases. A positive mean alone is insufficient.

Similarly, let a real polynomial $u>0$ approximate $S^{-1/2}$, with
$r_u=\|1-Su^2\|_A<1$ and $S\ge a$. Then

$$
\|u-S^{-1/2}\|_\infty\le
\frac{r_u}{\sqrt a\,[1+\sqrt{1-r_u}]}.
$$

This follows from $(\sqrt S u)^2=1-(1-Su^2)$ and selects the positive branch.
It permits a cropped iterative *proposer*, provided verification recomputes
the untruncated residual. For derivative bounds, also enclose weighted tails
or differentiate the defining coefficient equations and verify their full
residuals. A value bound alone does not establish a tangent bound.

There is a concrete derivative bound for the square root. Set
$r=q^2-S$ and let $\varepsilon_s$ denote the preceding value bound. Then

$$
\|q'-\sigma'\|_\infty\le
\frac{\nu(r)}{2m_q}
+\frac{\nu(S)\varepsilon_s}{2m_q\sqrt a}.
$$

Indeed, $q'=(S'+r')/(2q)$ and $\sigma'=S'/(2\sigma)$.
For a parameter direction, replace $\nu(r),\nu(S)$ by bounds on
$\dot r,\dot S$. The derivative of the *actual finite approximation*
must supply $\dot r$. Solving the continuous linearized square-root equation
and ignoring the finite residual derivative would not justify this bound.

### Arclength harmonics need no inverse correspondence

With the origin fixed by $\alpha(0)=0$, write

$$
\alpha(\theta)=\theta+\eta(\theta),\qquad
\eta_j=\frac{\sigma_j}{ij\mu}\quad(j\ne0),\qquad
\eta_0=-\sum_{j\ne0}\eta_j.
$$

Then

$$
H_m=e^{im\alpha}=w^m e^{im\eta},\qquad w=e^{i\theta}.
$$

The normal move is assembled by coefficient products of the $H_m$,
$N=-iz'$ and the reciprocal speed. Exponentials can be proposed by
polynomial composition, scaling and squaring, or a constrained coefficient
solve of the phase equation. Pointwise exponentiation on an FFT grid would
reintroduce the geometry quadrature being removed.

Naive Wiener-norm exponential bounds can grow like
$\exp(|m|\|\eta\|_A)$ even though the true phase has unit modulus. There is
a more useful real-curve stability argument.

**Phase residual deduction.** Let $\alpha_B=\theta+\eta_B$ with real
$\eta_B$ and $\alpha_B(0)=0$, and let a finite polynomial $P_m$ approximate
$e^{im\alpha_B}$. Form the full residual

$$
r_m=P_m'-im\alpha_B'P_m.
$$

An integrating factor of unit modulus gives

$$
\|P_m-e^{im\alpha_B}\|_\infty
\le |P_m(0)-1|+2\pi\|r_m\|_A.
$$

Both the anchor $P_m(0)=\sum_j(P_m)_j$ and the residual are coefficient
operations. If $\|\alpha-\alpha_B\|_\infty\le\varepsilon_\alpha$,
add $|m|\varepsilon_\alpha$ to bound error against the true phase. This
avoids an exponential amplification factor in the *verification bound*.
It does not ensure that the proposed polynomial is cheap to construct or
that its coefficient residual is small.

The arclength error itself can also be supplied explicitly. Use the positive
speed approximation $q$, let $\mu_B=q_0$, and certify
$q\le b_q$ and $\|q-\sigma\|_\infty\le\varepsilon_s<\mu_B$.
For $\alpha_B'=q/\mu_B$ with the same origin,

$$
\|\alpha'-\alpha_B'\|_\infty\le
\frac{\varepsilon_s}{\mu_B-\varepsilon_s}
\left(1+\frac{b_q}{\mu_B}\right),\qquad
\varepsilon_\alpha\le2\pi\|\alpha'-\alpha_B'\|_\infty.
$$

These follow from $|\mu-\mu_B|\le\varepsilon_s$ and integration.
They are conservative but require no curve evaluations. The positive $q$
also makes the approximate arclength correspondence strictly increasing.

For a spatial derivative of the phase error, the residual equation gives

$$
\|(P_m-e^{im\alpha_B})'\|_\infty\le
|m|\|\alpha_B'\|_\infty\varepsilon_{P,m}+\|r_m\|_A,
$$

where $\varepsilon_{P,m}$ is its preceding value bound. This is useful
when bounding the derivative error of the intermediate normal move.

### A scalar Chebyshev expansion supplies a concrete phase proposer

Certify a real range $\eta_B\in[c-A,c+A]$, $A>0$, and set
$x=(\eta_B-c)/A$. The
[Jacobi–Anger identity](https://dlmf.nist.gov/10.12) gives

$$
e^{im\eta_B}=e^{imc}\left[J_0(mA)+
2\sum_{n=1}^{\infty}i^nJ_n(mA)T_n(x)\right].
$$

Truncating at $d$ gives a scalar polynomial that can be composed with
$x$ using linear convolution and the Chebyshev recurrence. The uniform
value error is bounded by $2\sum_{n>d}|J_n(mA)|$. Its derivative with
respect to $\eta_B$ has error at most
$2A^{-1}\sum_{n>d}n^2|J_n(mA)|$, since
$\|T_n'\|_{[-1,1]}\le n^2$. Bessel values and the infinite tail need
verified enclosures. Multiplying by $w^m$ produces the arclength harmonic;
the complete phase residual gives an additional independent check after
any Fourier crop. The case $A=0$ is a constant phase and needs no expansion.

An elementary alternative is the Taylor polynomial for $e^{it}$ on a real
interval $|t|\le A_t$. Its integral remainder gives
$A_t^{d+1}/(d+1)!$, without an $e^{A_t}$ factor, because all derivatives
of the real-axis oscillatory exponential have unit modulus. Large degree
and cancellation can nevertheless make that proposer unattractive.

The scalar expansion is established; its composition and the tail-bound
construction here are adaptations for the proposed implementation.
Chebyshev polynomials in $x$ can be reused for multiple $m$. A recurrence
from a single phase is another possibility, but each product and crop has
its own error. Avoid claiming that cropping a recurrence is evaluation of
the exact scalar polynomial. The uncropped composition can reach band $dB$,
so these constructions make feasibility explicit without resolving cost.

### Arclength coefficients are zero coefficient contractions

For any regular periodic moved curve $p$, use its own speed and normalized
arclength $\alpha_p$. Change of variables gives

$$
R_k[p]=[p\,\alpha_p'e^{-ik\alpha_p}]_0.
$$

Integrating by parts removes the speed factor for nonzero output modes:

$$
R_k[p]=\frac{1}{ik}[p'e^{-ik\alpha_p}]_0\quad(k\ne0),\qquad
R_0[p]=[p\sigma_p]_0/\mu_p.
$$

This is the coefficient adaptation of Koga's equation 3.6. It avoids
computing $\theta(\alpha)$ and evaluating the reparameterized curve at an
output grid. An error $\varepsilon_{H,k}$ in the phase alone contributes at
most $\nu(p)\varepsilon_{H,k}/|k|$ to the corresponding nonzero coefficient.
Errors in $p$, its derivative, speed and normalization must be added.

Choose which contraction defines the finite map. Replacing the exact phase
by $P_{-k}$ in the two displayed forms does not make them identical:
their difference is $[p\,r_{-k}]_0/(ik)$. The integration-by-parts form
is an attractive definition for nonzero output coefficients, and the phase
residual bounds its difference from the continuous arclength coefficient.
Differentiate that chosen finite formula throughout.

The finite algorithm must specify its actual intermediate curve. For example,
construct a polynomial $p_B$ approximating the normal move, certify $p_B$,
and apply the coefficient arclength map to that polynomial. If a statement
also covers the uncropped intended move, its omitted derivative tail must be
bounded. Certification of $p_B$ alone does not prove validity of an unspecified
infinite series close to it only in position.

Finally retain

$$
T_z^{\rm coeff}(a)=z+\Pi_K\{R_B[p_B(a)]-R_B[p_B(0)]\}.
$$

Cache the exact same approximate base used by the finite map. This preserves
$T_z^{\rm coeff}(0)=z$ algebraically. Error tolerances govern approximation
to the continuous map; exact identity at zero governs the implemented map.

### The derivative must include the entire arclength operation

**Deduction.** For a Cartesian perturbation $v$ of $p$,

$$
\dot\sigma=\frac{\operatorname{Re}(\overline{p'}v')}{\sigma},\quad
\dot\mu=[\dot\sigma]_0,\quad
\dot\alpha'=\frac{\dot\sigma}{\mu}
-\frac{\sigma\dot\mu}{\mu^2},\quad \dot\alpha(0)=0.
$$

Differentiating $R_k[p]$ gives

$$
\dot R_k=
[e^{-ik\alpha}\{v\alpha'+p\dot\alpha'-ikp\alpha'\dot\alpha\}]_0
=[e^{-ik\alpha}\{v\alpha'-p'\dot\alpha\}]_0.
$$

The second form uses periodic integration by parts. These are identities for
the continuous map. The finite coefficient implementation must differentiate
its own actual polynomial approximations, normalization, contractions and
crops. If a converged projected solve defines the approximation, differentiate
its finite defining equations and bound solve error. If a fixed number of
Newton iterations defines it, differentiate those iterations. For polynomial
composition, use its polynomial chain rule.

The output columns are
$V_q=\partial T_z^{\rm coeff}/\partial a_q$ at zero. The maintained modal
service already contracts

$$
\omega_q=\operatorname{Re}(V_q\overline N)
$$

in coefficients. The physical derivative machinery can be retained.
[modal_muller.py](../../solvers/bem_inverse/modal_muller.py).
The NF-001 analytic implementation supplies a useful derivation/control, but
currently differentiates quadrature. [analytic_projection.py](../../solvers/bem_inverse/analytic_projection.py).

Changing approximation windows inside a derivative calculation can introduce
algorithmic kinks. Prepare a locally fixed degree/window with sufficient
margin, and bound approximation errors independently. The tangent of a
different, more convenient normal-only map cannot substitute for this one.

A differentiated phase residual gives a useful sensitivity check too. Let
$e_m=P_m-e^{im\alpha_B}$ and differentiate with respect to a real update
parameter while fixing $\alpha_B(0)=0$. The equation for the error is

$$
\dot e_m'-im\alpha_B'\dot e_m
=\dot r_m+im\dot\alpha_B'e_m.
$$

The same unit-modulus integrating factor proves

$$
\|\dot e_m\|_\infty\le|\dot P_m(0)|+
2\pi\left(\|\dot r_m\|_A+
|m|\|\dot\alpha_B'\|_\infty\varepsilon_{P,m}\right).
$$

Thus value residuals can be accompanied by directional residuals for the
actual finite algorithm. Error against the true phase also needs the bounds
on $\alpha-\alpha_B$ and $\dot\alpha-\dot\alpha_B$; the displayed
inequality alone concerns the approximate arclength correspondence.

### Three bandwidths and a separate approximation degree are needed

Keep distinct $M$ for allowed shape directions, $K$ for stored geometry, $B$
for nonlinear working coefficients, and $d$ for a scalar function approximation.
Multiplication padding is determined by actual factor support. Increasing $B$
improves a nonlinear computation without granting extra inverse shape modes.

As a rate estimate, mapping $[a,b]$ to a Chebyshev interval places the square
root singularity at zero at ellipse parameter

$$
\rho_*=(\sqrt b+\sqrt a)/(\sqrt b-\sqrt a)
=(r+1)/(r-1),\quad r=\sqrt{b/a}.
$$

An indicative degree is $d\approx\log(1/\varepsilon)/\log\rho_*$.
For $\varepsilon=10^{-12}$ this gives approximately 12, 25, 54 and 165 at
$r=1.2,2,4,12$. These are asymptotic scale estimates, not certified degree
choices; an actual bound needs a strictly smaller analytic ellipse and a
prefactor. The favourable baseline drift and the failed arm's severe drift
predict very different costs.

Repeated cropping must be recorded in the error model. A full polynomial in
$S$ can grow to band $2Kd$; compressed recurrences cannot silently inherit
its exact function identity. Residual verification is what permits a practical
working window instead of retaining every such intermediate coefficient.

## Geometry certificates without sampled proposals

### What the divided difference proves

For $z(w)$ define

$$
W_z(w,v)=\frac{z(w)-z(v)}{w-v},\qquad |w|=|v|=1,
$$

extended continuously to $w=v$. It is a finite bivariate Laurent polynomial.
Off the diagonal, nonvanishing means injectivity. On the diagonal its modulus
is $|z'(\theta)|$. A strictly positive global lower bound therefore establishes
both simplicity and regularity. A positive signed area then selects the
counterclockwise orientation of a simple closed curve.

The signed area formula

$$
\operatorname{Area}(z)=\pi\sum_j j|z_j|^2
$$

is already coefficient based. Positive area alone does not establish
simplicity. Near zero area, its sign also requires an arithmetic enclosure.

### A stronger cheap certificate follows from the existing bound

**Deduction.** Suppose $|W_z|\ge b>0$ and the trial increment is $D$.
For every integer mode $j$, the Laurent divided difference of $w^j$ has
$|j|$ terms of unit magnitude. Consequently,

$$
\|W_D\|_\infty\le\|W_D\|_A\le\nu(D).
$$

The reverse triangle inequality gives

$$
\boxed{\quad |W_{z+D}|\ge b-\nu(D).\quad}
$$

Thus $\nu(D)<b$ certifies a regular simple stored trial in $O(K)$ work
once $b$ is available. An intermediate curve at working band $B$ costs
$O(B)$ for this test. If the accepted bound is $|W_z|^2\ge\beta$, use
$b=\sqrt\beta$ with downward rounding. The updated squared lower bound is
$(\sqrt\beta-\nu(D))^2$. Check the requested numerical regularity floor
and orientation as well.

For comparison, our present scalar reuse test uses an approximate reciprocal
$Y$ of $|W_z|^2$. Ignoring roundoff notation, let
$r=\|1-|W_z|^2Y\|_A$ and $\beta=(1-r)/\|Y\|_A$.
Its positivity condition is

$$
2\nu(z)\nu(D)+\nu(D)^2<\beta.
$$

It permits $\nu(D)<\sqrt{\nu(z)^2+\beta}-\nu(z)$, approximately
$\beta/(2\nu(z))$ when $\beta$ is small. The direct bound instead permits
$\nu(D)<\sqrt\beta$. For the same base certificate, the ratio of these
positivity-only thresholds is

$$
\frac{\sqrt{\nu(z)^2+\beta}+\nu(z)}{\sqrt\beta}.
$$

This is an algebraically stronger sufficient test, with a potentially large
advantage near a small certificate margin. It is **not a measured reduction
in refusals or runtime**. Repeatedly carrying forward a weakened bound can
exhaust its margin; refresh an accepted curve's certificate when needed.

The norm test still ignores direction. For $z=Rw$, an outward expansion
$D=cRw$, $c>1$, remains a circle but fails $\nu(D)<b=R$. Opening a thin
gap can also fail a direction-blind margin test. Refreshing or a local range
proof remains necessary for such valid moves.

This argument also certifies a crop: if the full polynomial curve $p$ has
bound $b_p$, and the discarded tail $E=p-\Pi_Kp$ satisfies
$\nu(E)<b_p$, then the cropped curve remains simple and regular. This is
why a position-only projection tolerance is insufficient.

### Coefficient reciprocals can be proposed without a sampled minimum

The existing residual theorem is sound in exact arithmetic:

$$
r=\|1-\lambda Y\|_A<1,\quad \lambda=|W|^2
\quad\Longrightarrow\quad
\lambda\ge(1-r)/\|Y\|_A.
$$

The proposer for $Y$ need not already be a certified approximation. A
coefficient linear or least-squares solve, continuation from an accepted
reciprocal, or Newton–Schulz iteration can propose it. Its full residual
decides. The current sampled minimum is not a mathematical requirement of
this theorem.

For an uncropped Newton–Schulz step, set $E=1-\lambda Y$ and
$Y_+=Y(1+E)$. Then $1-\lambda Y_+=E^2$. If $Y_+$ is cropped to $\widetilde
Y_+$, the additional residual is $\lambda(Y_+-\widetilde Y_+)$. Verify
the full product or bound the entire discarded term. The identity $E^2$
alone does not justify repeated cropping.

There is even a slow constructive bootstrap that needs only an upper bound.
Take $U\ge\max\lambda$, $U>0$, and

$$
E_0=1-\lambda/U,\qquad
Y_N=U^{-1}\sum_{n=0}^{N}E_0^n.
$$

Its exact residual is $E_0^{N+1}$. If the curve is regular and simple, then
$\min\lambda=b_\lambda>0$ and
$\|E_0\|_\infty\le1-b_\lambda/U<1$. For a bivariate polynomial of
coordinate band at most $D$, Parseval and Cauchy–Schwarz give

$$
\|E_0^n\|_A\le(2nD+1)\|E_0\|_\infty^n\longrightarrow0.
$$

Therefore a finite coefficient residual certificate eventually succeeds in
exact arithmetic. **This proves existence of a node-free bootstrap, not useful
cost.** Near thin gaps its degree can grow roughly with $U/b_\lambda$,
and coefficient storage grows too. A practical constrained inverse solve or
subdivision should be tried before this worst-case construction.

An alternative is a complex reciprocal $Q\approx1/W$. The sufficient test
$\|1-WQ\|_A<1$ gives
$|W|\ge(1-\|1-WQ\|_A)/\|Q\|_A$. It avoids squaring $W$ in the verification
product. Whether its working bandwidth and conditioning are better is an
open component question; complex winding prevents blindly copying the
positive scalar interval algorithm.

### Subdivision complements global coefficient norms

Global Wiener bounds lose cancellation and can be conservative. On an arc,
write $w=e^{i\theta_0}(1+it)/(1-it)$ using a bounded half-angle coordinate.
A finite Laurent polynomial becomes a rational polynomial in $t$. In two
variables, clearing denominators of the form $(1+t^2)^a(1+s^2)^b$ converts
$|W|^2-\beta$ into a real polynomial with an everywhere positive denominator.

Convert the numerator to Bernstein coefficients on a rectangle. Strictly
positive interval-enclosed coefficients prove positivity on the entire cell.
Otherwise subdivide. For a strictly positive polynomial on a compact chart,
coefficient range bounds converge under subdivision in exact arithmetic.
Conditioning of the conversion and rounding require explicit treatment.

Cover all torus charts, their boundaries and the diagonal. Positive cells
can be retained and revalidated cheaply under a coefficient perturbation;
difficult cells near a close pair are refined. A direct rational representation
of the curve can also separate pairs of arcs. This replaces a large uniform
torus grid by an adaptive *range proof*, with no point samples serving as the
acceptance criterion.

For an invalidity witness, solve the two real equations
$z(\theta)-z(\phi)=0$ on a parameter rectangle separated from the diagonal.
Interval Newton or a Krawczyk inclusion can prove a transverse root when its
Jacobian is nonsingular. Tangential contact and exact cusps are degenerate;
those require stronger algebraic methods or an unresolved result. Yap's
complete algorithm shows why separation and degeneracy hypotheses matter.
It is not a turnkey theorem for our Laurent curves.

### A strict geometry service needs three outcomes

| Outcome | Meaning and action |
|---|---|
| Valid | The declared conditions proved for the stored trial and every required intermediate role; these include simplicity, regularity floor, orientation and domain containment where required |
| Invalid | A crossing witness, a proved orientation/domain violation, or another proved failure of the declared admissibility condition |
| Unresolved | The certificate budget or arithmetic precision cannot decide; refine, shorten the step or report an unresolved geometry obstruction |

Failure to invert $W$, absence of a positive Bernstein bound, or exhaustion
of the degree budget does not prove self-intersection. If an unresolved trial
is refused operationally, record that reason explicitly. A strict path cannot
accept it through a polygon test while retaining the stronger assurance claim.

The 89 coarse sampled-fallback trials are a natural evidence panel for
decisiveness. Saved polygon refusals cannot be used as the sole independent
truth labels for a new certified classifier.

### Sum of squares is useful but not a default global solution

For a univariate real trigonometric polynomial $p$, a coefficient identity
$p-\beta=q^*q$ or $p-\beta=v^*Gv$, $G\succeq0$, proves a lower bound.
Fejér–Riesz supplies existence. In a numerical certificate, account for the
coefficient residual and verify positivity of $G$; a floating-point optimizer
report is insufficient.

This is attractive for $S=|z'|^2$ and the four box inequalities. For the
bivariate global simplicity polynomial, dense Gram storage grows as
$O(K^4)$. Even a monomial basis with degree 192 in each variable has 37,249
entries and its dense Gram matrix has over 1.38 billion entries, before solver
workspace. The 2026 addendum also warns against universal fixed factor-degree
claims. Sparse or local SOS certificates remain possible, but a full dense
global SDP is a poor first implementation at our high band.

### Arithmetic verification should be a separate layer

Our present `80 * size * eps * Lambda * ||Y||_1` allowance is heuristic.
Replacing the proposal grid or the trial quadrature does not change that.
Use a fast float proposer and a smaller independent verifier with outward
coefficient/convolution bounds. Lessard's verified FFT work gives a relevant
construction; direct interval convolution may suffice at small verifier bands.

Represent the input finite floating-point coefficients as the exact dyadic
curve to certify, or include coefficient uncertainty explicitly. Then enclose
all products and norms. Interval roundoff, omitted Fourier tails and deliberate
storage projection are different error sources and must be charged separately.
Ordinary window doubling remains a numerical check, not a substitute for these
enclosures.

## Completing the geometry scope

Replacing the move and arclength reset alone leaves other sampled decisions.
The geometry engine should supply their coefficient replacements too.

| Current sampled operation | Replacement and qualification issue |
|---|---|
| Squared divided-difference interval proposal | Reused accepted bounds, coefficient inverse residuals, or subdivision; also pass certified intervals to modal physics rather than recomputing a sampled proposal there |
| Coarse/fine sampled maximum | $\sum_j|c_j-f_j|$ plus certified errors of both approximations; the coefficient sum is conservative and two approximations can share an unresolved bias |
| Sampled domain box | First try $x_0\pm\sum_{j\ne0}|x_j|$, $y_0\pm\sum_{j\ne0}|y_j|$; then univariate range subdivision or factor certificates |
| Speed ratio diagnostic | Certified upper and lower speed bounds, with reported uncertainty; $\sqrt{b/a}$ is an upper bound if the interval is conservative |
| Arclength frontier weights | Reuse $H_m$ and $\sigma$ coefficient functions, normalize with coefficient means, and preserve the existing column ordering and paired frontier rule |
| Physical displacement metric | With $\omega_p=\operatorname{Re}(V_p\overline N)$, $G_{pq}=2\pi[\omega_p\omega_q/\sigma]_0/L$; include physical unit factors and bound reciprocal-speed errors |
| Max/RMS displacement receipts | Uniform coefficient/range bounds and coefficient means; optional plots may sample, but sampled diagnostics must not determine trial acceptance |

The Cartesian components are real Fourier series obtained algebraically:
$x_j=(z_j+\overline{z_{-j}})/2$ and
$y_j=(z_j-\overline{z_{-j}})/(2i)$.
Their bounds can be substantially tighter than a single enclosing disk.
Containment in an open box requires a strict margin, not an interval touching
its boundary.

The default coefficient step clip and Marquardt metric already avoid geometry
quadrature. The mass-metric formula above is for the optional physical metric.
An eventual sample-free scope must also audit runner initialization, stage
changes, cleanup, endpoint qualification and frontier calls. Truth-based
benchmark scoring and visualization can remain sampled outside the numerical
geometry service if the claim states that boundary clearly.

## Alternative ideas worth retaining

### Polynomial ambient deformations preserve a simple raw boundary

Let a real polynomial vector field $u_a(x,y)$ define $F_a(x)=x+u_a(x)$.
If a convex set containing the curve and every chord between its points has
$\sup\|Du_a\|_2\le q<1$, then

$$
|F_a(x)-F_a(y)|\ge(1-q)|x-y|.
$$

This proves injectivity there and preserves regularity of the raw deformed
curve. It does not assert a global diffeomorphism of the entire plane for an
unbounded polynomial vector field. Jacobian bounds on a box can be enclosed
through Bernstein coefficients or interval matrix bounds.

Compose the polynomial with the Laurent coefficients of $x(\theta)$ and
$y(\theta)$. A field of total degree $d$ yields a finite curve of band at
most $dK$ by exact convolution. No curve collocation is needed. Translation,
rotation and affine deformations are the simplest exact cases.

If the accepted boundary has $|W_z|\ge b$, the raw composed curve has a lower
bound $(1-q)b$. Its crop remains simple if the omitted derivative norm is
smaller than this margin. Thus injectivity survives storage projection only
when projection error is also certified. A subsequent centred arclength
increment is another changed map and needs its own certificate.

This is a genuinely different finite deformation family. Its normal boundary
directions need comparison with the existing arclength space; a global ambient
polynomial may require high degree to create opposite motions across a thin
gap. Near an already tiny gap, a global Lipschitz restriction can be too tight.

There is relevant negative evidence: ON-001's Gaussian ambient arm qualified
only **10/16** saved states after its correction and ran zero fresh fits.
Its conservative momenta bound activated clipping at some curved states on
the fixed derivative probe scale. That limits that construction and its usable
local neighbourhood; it does not refute injectivity-preserving deformations
as a family. A polynomial arm would need tighter range bounds and a different
field approximation, rather than reproducing that bound.
[ON-001 results](../iterations/cleaned_interfaces/iteration_31/01_results.md),
[scientific review](../iterations/cleaned_interfaces/iteration_31/02_claude_review.md).

### A Pythagorean hodograph representation can remove the speed square root

**Derived candidate, not a qualified replacement.** For a complex Laurent
polynomial $q(\theta)$, prescribe

$$
z'(\theta)=i e^{i\theta}q(\theta)^2.
$$

Then the speed is exactly $|q|^2$, a real Laurent polynomial. Its primitive
and mean are coefficient operations, and
$n=e^{i\theta}q/\overline q$ is rational. Periodic closure requires

$$
[e^{i\theta}q^2]_0=0,
$$

which is one complex coefficient constraint. A constant nonzero $q$ gives a
circle. For a simple counterclockwise boundary, the derivative winding is
one; in this chart it is $1+2\operatorname{wind}(q)$, so the intended branch
has winding zero and $q$ must be nonvanishing.

Conversely, a regular analytic simple counterclockwise curve has a
nonvanishing function $z'/(iw)$ of winding zero, with a periodic square-root
branch on a sufficiently small annulus. Its Fourier series suggests an
approximation route to this representation. Enforcing the closure constraint
after truncating that square root needs a separate local analysis; no finite
band density or competitive representation theorem is asserted here.

This family removes an expensive nonlinear speed operation structurally.
It does not automatically guarantee simplicity, good speed conditioning or
easy arclength phases. The exponentials of the arclength primitive are still
nonpolynomial. PH literature supplies the speed/length principle, not evidence
of retention on our concave TG-002 targets. This belongs with Track 8 as an
open representation study if the existing-chart coefficient route proves too
costly.

### Positive speed and tangent angle coordinates separate regularity from closure

Writing
$z'=\exp\{\ell(\theta)+i[\theta+\psi(\theta)]\}$ with real periodic
$\ell,\psi$ makes speed positive and fixes tangent winding one before
approximations. Closure requires $[z']_0=0$, two real constraints.
Coefficient exponentials and integration then construct the curve.

This makes local regularity easier but leaves nonintersection unresolved.
Forcing curvature positive would restrict the family to convex geometry and
exclude important targets. Finite coefficient crops also need certified
regularity margins. The coordinate choice changes the local inverse subspace
and its metric, so it cannot be assessed by raw coefficient norms alone.

### Exterior conformal coefficients offer a canonical chart with crowding limits

The normalized exterior map has form

$$
z(w)=a w+b_0+\sum_{n\ge1}b_n w^{-n},\qquad a>0.
$$

It fixes much of the arbitrary parameter gauge and fits our Laurent storage.
On the boundary, the coefficient condition
$\sum_n n|b_n|<a$ gives $|W|\ge a-\sum_n n|b_n|>0$ directly.
It is a useful sufficient family, not a universal admission test for complex
concave geometry.

The ellipse $aw+b_1/w$ is simple for $0<b_1<a$ but its speed ratio is
$(a+b_1)/(a-b_1)$, which diverges as the ellipse thins. A canonical chart
does not remove distortion. Conformal crowding in narrow features and
verification of univalence remain substantial tasks. Finite Grunsky sections
cannot certify an infinite criterion without an accompanying tail bound.

The coefficient recurrences in the conformal literature are worth retaining
as a comparison. A conformal change of variables also introduces the scale
factor into Helmholtz physics; Laplace conformal invariance does not make
finite-frequency transmission geometry dependence disappear.

## What should be established before another inverse campaign

The research question is:

> Can coefficient computation of the existing centred arclength map deliver
> its finite trial and complete tangent to controlled tolerance, while deciding
> geometry without a sampled proposal or fallback at practical cost?

The present answer is **mathematically supported and numerically unqualified**.
The assessment suggests the following sequence. These are component research
questions, not new runs or a registered experiment claim.

1. **Specify the coefficient map and its error model.** Define the actual
   finite intermediate curve, fixed local approximation windows, zero-update
   cancellation, positive branches and all value/derivative tail bounds.
   Start with the existing centred map. Keep $M$, $K$, $B$ and $d$ separate.
2. **Qualify the algebra on analytic controls and saved TG-002 moves.** Circle
   coefficients give an exact arclength control. An ellipse checks nonlinear
   speed. The family $z=w+a w^2$ gives the known divided-difference minimum
   $(1-2a)^2$ for $0\le a<1/2$, a cusp at $a=1/2$, and the regular crossing
   example at $a=1$. Reuse GC-001's TG-002 state/move panel without selecting
   directions by truth. Compare against independently refined quadrature as
   a numerical reference, keeping references that fail refinement unresolved.
3. **Qualify complete derivatives separately.** Compare the differentiated
   coefficient trial with the analytic quadrature control, then complete
   finite-trial field derivatives. Use absolute floors for near-null columns
   declared in advance. A small speed or phase residual alone does not qualify
   the inverse Jacobian.
4. **Test certificates on the difficult saved decisions.** Compare the stronger
   direct perturbation bound, coefficient reciprocal refresh and subdivision
   on the 89 coarse sampled-fallback trials. Verify crossing labels
   independently. Retain inconclusive outputs and their cost. Include known
   regular crossings and near-cusps; do not score sampled agreement as rigor.
5. **Close every sampled decision in the intended scope.** Supply box bounds,
   frontier weights, trial accuracy gates and certified physics intervals.
   Charge arithmetic verification, refreshing, failed certificate attempts
   and all nonlinear preparations. Freeze operational handling of unresolved
   geometry before fitting.
6. **Only then assess inverse retention.** Every new inverse comparison uses
   [TG-002](../../experiments/benchmark/README.md): ten scenes, three contrasts,
   the prescribed centred start, localization off and unchanged scoring.
   Historical six-case successes remain prior evidence, not a new benchmark.
   Register the specific hypothesis and stopping criteria under
   `docs/iterations/` before any new numerical experiment.

One falsifying outcome for the preferred construction would be that, on the
declared saved-state panel, complete error bounds require working bands or
verification costs beyond a predeclared resource budget. That would refute
its proposed practical regime, rather than mathematical node-free feasibility.
Another would be accurate finite trials but an unqualified tangent, requiring
derivative work before any inverse conclusion. Certificate indecisiveness on
regular thin-gap curves would identify a certification limitation separately.

The geometry engine should initially be isolated from maintained defaults.
Its numerical implementation belongs in `solvers/bem_inverse/`; campaign
selection, truth scoring and saved evidence belong in experiments/results.
Independent plotting or quadrature references may use samples outside the
production geometry path. Their use must remain visible in scope receipts.

## Cost and scientific limits

GC-001's saved PC-001 modal context attributes **19.10%** of summed whole-run
time to boundary-update geometry. Under an unchanged path and unchanged
other costs, making that category free gives a ceiling of **1.236x** overall;
halving it gives **1.106x**. Geometry assembly inside physics is outside that
category. These are arithmetic forecasts, not measured speedups for a
coefficient method. The source report includes audits in both numerator and
denominator, which is essential to this comparison.

Individual difficult cases spend much more on failed certificates. They could
benefit disproportionately from reuse and adaptive local proofs, but a smaller
certification bill is not evidence of improved recovery. The four persistent
TG-002 failures occur across modal and nodal comparisons; current evidence
does not isolate geometry quadrature as their cause.

The useful scientific objective is therefore explicit: a geometry calculus
that computes finite updates and sensitivities without sampled discretization,
with error and admissibility statements that survive thin gaps, cropping and
floating-point arithmetic. A speed advantage is a separate measured claim.

## Decision

Retain **coefficient computation of the centred arclength increment** as the
first direction. Its geometry and derivative contract have the strongest
relevant evidence, and the required coefficient identities are available.
Pair it with the stronger direct divided-difference reuse bound and adaptive
range certificates. Treat rigorous arithmetic as an explicit verifier layer.

Keep polynomial ambient maps and the PH coordinate family open as genuinely
different constructions. Revisit them if the preferred map's nonlinear phase
or certification costs are the demonstrated obstruction. Do not return to
the failed affine normal map with the expectation that removing nodes alone
will control its drift, and do not replace complete tangent columns by
normal-only weights.

The immediate deliverable from Track 7 is a mathematical specification and
component qualification of that geometry engine. The investigation establishes
a plausible, technically concrete route and several useful deductions; it
does not establish a working sample-free inverse or a performance gain.
