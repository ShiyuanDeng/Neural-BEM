# Seven GauGal-style restructurings: integration and mathematical review

Prepared 2026-10-05. Integrates the user's report, **GauGal-Style
Restructurings for a Node-Free Fourier–Galerkin Boundary Solver: Seven Ideas,
Prior Art, and What to Try First**. This is a planning amendment, not run
approval or numerical evidence. All new arms below remain proposed.

The strongest immediate move is geometry-aware clipping, followed by a
Gaussian displacement if clipping prevents useful progress. Keep the
required-accuracy exit and reduced-frequency proposal work: current TG-002
receipts support those opportunities independently. Put Ewald factorization
in a separate forward experiment with a clear route to a larger contribution.
This gives us a practical overnight bet and a distinct architectural bet.

## Where all seven ideas go

| Report idea | Decision and experiment | What earns further work |
|---|---|---|
| 1a Reach-limited normal step | First geometry arm G in [ON-001](../03_plan.md), before a new finite map | Retained recoveries plus useful total-time savings or new recovery |
| 1b Gaussian Lipschitz displacement | Replace ON-001's RK4 flow proposal with conditional F; same normal coordinates initially | Raw admissibility translates into useful progress after Fourier projection |
| 2 Ewald modal Müller | Separate [ON-003 forward feasibility](../../../CI-SPD/iteration_01/04_ON003_ewald_plan.md) | Qualified full fields and derivatives at useful measured cost |
| 3 Shape-Taylor/reference operators | Reserve after profiling; cheap trial screening is more relevant than replacing small LU | A prospective error bound and lower total trial cost, including right-hand side/readout changes |
| 4 T-matrix acquisition factorization | Reuse existing cylindrical-wave structure first; pursue for many/moving sensors | A matched acquisition workload amortizes construction and extra right-hand sides |
| 5 Gaussian level set with IBIM/KFBI | Long-term sharp-interface/SDF route; ON-002's volume hybrid is the cheaper bridge now | A qualified transmission operator and derivative, not merely a smooth occupancy image |
| 6 Operator atlas/RB/EIM | Deferred; fixed dimension helps but does not remove non-affinity or prior negative atlas evidence | Prospective interpolation error and total cost on a held-out continuation segment |
| 7 Matrix-free/recycled Krylov | Defer for present 2D sizes; pair with a later large-system operator study | Assembly/apply/solve measurements show a real crossover |

[ON-002](../../../CI-SPD/iteration_01/03_plan.md) remains the direct adapted
GauGal parity and volume-to-boundary option. ON-001, ON-002 and ON-003 are
separate bounded campaigns, not three jobs promised inside one night.

## Correct the cost attribution before choosing a mechanism

The GGB-001 hard case motivates this work, but its roughly 320 seconds is
**total time minus logged physics time**, not measured geometry time. It
also includes bookkeeping, scoring/output and other work. Of 845 proposals,
669 had geometry refusals and four were unresolved, leaving 172 candidate
physics dispatches: 99 accepted and 73 physics refusals. The physics ledger
contains other evaluations and derivative batches. Dividing 28.9 by 176 or
320 by 845 does not identify measured service costs.

Current recovered TG-002 modal paths attributed roughly 13–18% to geometry
in the prior assessment; the difficult failures can have a different profile.
Accordingly ON-001 times projection, certification, physics, derivatives,
audits and output separately. It does not forecast a several-fold speedup
from the old 92% remainder. The new runs use TG-002, not the retired GGB
acquisition. [GGB receipts and comparison](../../../CI-SPD/01_results.md).

The maintained implementation already reuses exact-curve geometry and solved
systems/right-hand sides in relevant paths. Reuse across changed curves is
an approximation requiring new analysis. Likewise, the fixed length of a
Fourier vector does not make its physical function unchanged after arclength
reparameterization or a cutoff change. A recycled vector must be represented
in the current coordinates and checked by the current residual.

GauGal's local source and the measured adapter are the comparison evidence.
The report's public-paper availability statement and its short novelty search
are dated observations, not proof of absence of prior work.

## 1a: a useful reach proxy now, a certificate only when justified

For an embedded smooth curve and its **actual** reach rho, a smooth normal
graph with `||h||_infinity < rho` is embedded and regular. With counterclockwise
orientation, outward normal and positive circle curvature, `n_s = kappa*t`,
so `(gamma+h*n)_s = (1+kappa*h)*t + h_s*n`. The absolute-value argument works
with either consistent sign convention; the report mixed conventions.

For real normal harmonics, use the tighter inexpensive bound

`S(c) = |c0| + sum_m hypot(c_cos_m, c_sin_m) >= ||h||_infinity`.

The first implementable controller scales the whole direction by
`alpha = min(1, 0.8*rho_est/S(c))`, with the zero direction handled directly.
Both radius and coefficients must use the same physical length unit; the
implementation converts the stored-coordinate radius to metres first.
This retains its direction and allows the LM prediction to be recomputed for
the actual proposed step. It avoids introducing another constrained optimizer.

The reach can be characterized through all curve pairs by
`inf_{x!=y} |x-y|^2 / (2*dist(y-x, T_x Gamma))`, with its local curvature
limit included. Sampling this infimum gives an estimate **from above**, not
a certified lower bound. Sampling curvature maxima has the same issue. Even
agreement between 1024 and 2048 samples does not turn the estimate into a
proof. ON-001 therefore uses a cached proxy and retains the final checks.
A future interval/coefficient bound could justify calling the implemented
radius certified. See the reach characterization in
[Breiding et al.](https://doi.org/10.1007/s13163-018-0273-6).

The report's exact `32+11=43` band calculation does not apply to a generic
stored Fourier curve. Normalization `n=R gamma'/|gamma'|` and the arclength
coordinate both introduce additional Fourier content. A noncircular finite
Fourier curve is not generally exactly arclength-parameterized. Consequently
projection error and final-curve admissibility remain part of the experiment.
The raw normal graph and its projected stored curve have different guarantees.

Clipping relative to today's reach also does not preserve a fixed reach floor
for all later shapes. It cannot justify dropping Ewald near interactions or
excluding the thin TG-002 targets.

## 1b: use the displacement guarantee directly

For fixed Gaussian centres, let
`v(x)=b+sum_i p_i exp(-|x-q_i|^2/(2*sigma^2))` and `phi(x)=x+v(x)`.
Then

`Lip(v) <= C = exp(-1/2)*sum_i ||p_i||_2/sigma`.

Scaling the direction and its linearly fitted momenta by
`alpha=min(1,0.8/C)` gives
`|phi(x)-phi(y)| >= 0.2*|x-y|`. Translation contributes zero to C.
The exact map is globally injective and has nonsingular derivative; composing
such maps permits large cumulative motion. No ODE integration is needed for
this particular guarantee. This is why F now replaces the proposed RK4 flow
with one bounded displacement, while retaining the same geometry interface.

The global bound may be restrictive when Gaussian supports barely overlap
or interpolation requires cancelling large momenta. Log clipping and useful
decrease rather than treating zero raw intersections as the success metric.
Fourier reprojection still needs validation, and the complete projected map
needs its own tangent qualification. If a later experiment optimizes momenta
directly, its constraint is a sum of vector norms: a group-l1 ball with block
shrinkage, not elementwise scalar l1 clipping. Gaussian diffeomorphic maps and
shape optimization have established prior art; novelty must come from the
qualified inverse pipeline and demonstrated benefit.

## 2: preserve the Ewald idea, repair the operator claims

With outgoing limiting absorption, `a=|q|^2-(k+i0)^2`, the finite split

`1/a = (1-exp(-a*tau))/a + exp(-a*tau)/a`

is valid. For the report's convention `tau=1/(4*xi^2)`, the flat single-layer
near symbol is
`erf(sqrt((omega^2-(k+i0)^2)*tau))/(2*sqrt(omega^2-(k+i0)^2))`.
At grazing its removable limit is `sqrt(tau/pi)`. For propagating modes,
`beta=sqrt(k^2-omega^2)`, it equals `erfi(beta*sqrt(tau))/(2*beta)` and grows
as tau increases. It does **not** approach the full outgoing line symbol as
tau tends to infinity; that symbol requires cancellation with the far term.
ON-003 explicitly tests evanescent, grazing and propagating modes.

The flat near diagonal is an initial approximation to one operator. Relative
single-layer curvature corrections can scale like `kappa^2*tau`; double
layers have linear curvature terms, and hypersingular traces require jumps
and finite-part treatment. Close but arclength-distant segments create
nonlocal near interactions. A reach rule alone, without a tolerance-dependent
tail bound, does not remove them. One bounded numerical near correction is
preferable to claiming an unproved all-block diagonal formula.

The package stores `(u, J*partial_n u)` in parameter-Fourier coordinates,
where `J=|gamma'|`, not two arbitrary arclength densities. Its single-layer,
double-layer, adjoint and hypersingular differences must be derived with
consistent speed/mass factors, signs and jump terms. The shape derivative
must include `delta J=gamma' dot V'/J` and `delta(nJ)=R V'`, both target/source
maps and the near correction. If the basis or grid changes with geometry,
its derivative is not optional.

A fixed grid/window can share geometry maps across both media and multiple
frequencies at a fixed curve. Select its scale using the maximum wavenumber
over that entire intended group, including the interior factor `sqrt(13.3)`.
There is no cross-geometry reuse claim. A scalar map at trace cutoff 64 has
129 columns; 258 is the two-trace system size. At cutoff 128 the corresponding
counts are 257 and 514. Dense `B^H D B` construction can be expensive at these
sizes: GPU milliseconds and a smaller total time must be measured.

The outgoing Fourier shell cannot be replaced by an ordinary sampled pole.
Physical truncation and heat smoothing do not commute. Use a matched
truncated far kernel or explicitly bound the buffer error; do not combine a
truncated full-kernel multiplier with the original near correction without
derivation. [Vico, Greengard and Ferrando](https://arxiv.org/abs/1604.03155)
provide the free-space truncation framework. Existing qualified source and
receiver/Graf waves stay initially; replacing them is separate work.

The closest 2026 references support the architecture, with different scope:
[symbol-based potential theory](https://arxiv.org/abs/2604.11436) treats Poisson
and strongly elliptic systems, while the
[unified layer/volume algorithm](https://arxiv.org/abs/2606.28865) treats
modified Helmholtz. Neither establishes this radiating Müller inverse.
Boundary quadrature used to build moments must be disclosed. Fourier unknowns
and absence of boundary collocation do not imply a sample-free construction.

## Claim and longer-term direction

The strongest immediate claim is an adaptive, qualified transmission inverse
whose geometry map and frequency work produce more recovery per second.
If ON-003 succeeds, the stronger operator claim is a shared geometry
factorization of the **complete** transmission service and its derivative.
Ewald splitting, reach and Gaussian diffeomorphisms alone are not new.

For 3D Maxwell, the Fourier multiplier becomes dyadic and tangential currents,
charge, jumps and divergence conformity must be handled together. A scalar
2D success is a useful precursor, not a Maxwell result. For SDF/IBIM, the
normal/closest-point geometry and singular corrections still depend on shape;
geometry is not generally only one diagonal weight. Box-clipped Gaussian
level-set coefficients do not guarantee a regular zero set or a single
admissible component. The existing
[neural implicit inverse-obstacle work](https://arxiv.org/abs/2206.02027)
also narrows the novelty of a generic SDF claim.

The plans consequently give each mechanism a success, repair and closure
branch. A major ON-001 win closes into confirmation; it does not release an
unbounded operator rewrite. An ON-003 forward win earns a separately proposed
inverse comparison. These are deliberate bets with decisive outputs, not
an obligation to implement all seven ideas.
