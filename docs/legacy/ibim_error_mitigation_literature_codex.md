# IBIM Forward Solver Error Mitigation — Literature Review and Historical Implementation Record

> **Status: historical research and planning record.** This document contains
> several generations of superseded “current” plans and Codex instructions.
> Preserve them as reasoning history; do not execute them as the current
> roadmap. See [`../current_architecture.md`](../current_architecture.md) for
> present behavior and
> [`../ordered_boundary_nystrom_plan.md`](../ordered_boundary_nystrom_plan.md)
> for the only live forward-solver plan.

## Purpose

This note is meant to be read by **Codex together with the repository**.

Start by reading:

- `forward_solver_validation.md`
- `gpr_bem/ibim_tmz_forward.py`
- `gpr_bem/ibim_tmz_system.py`
- `gpr_bem/ibim_geometry.py`
- `gpr_bem/ibim_tmz_adjoint.py`
- `gpr_bem/ibim_inverse.py`
- `run_ibim_rectangular_scan_forward.py`

The validation report identified four error mechanisms:

1. finite stand-off trace evaluation;
2. irregular projected boundary nodes;
3. the 2 GHz relative-error spike;
4. conditioning / hypersingular cancellation.

A fifth was found later, during a code read rather than by measurement, and is
documented in §4b:

5. `K'` and `T` assembled by finite-differencing lower-order potentials along the
   normal instead of from their own analytic kernels.

The purpose here is to explain **how past BIE/IBIM literature mitigates each mechanism** and turn that into a concrete implementation/testing sequence for this repo.

Current status, to avoid a recurring ambiguity:

> The repo is **not currently implementing literature-accurate volume IBIM
> quadrature**. The tubular/narrow-band sampling is used as a geometry
> extraction step: it gives projected/compressed boundary points, normals, and
> weights. The boundary integral operators are then assembled as quadrature on
> that estimated boundary point cloud, and the same point cloud is used as the
> collocation/trace-evaluation set. Literature volume IBIM - where Cartesian
> narrow-band nodes remain the quadrature nodes and singular corrections are
> derived for the lifted closest-point volume integral - is background and a
> possible future fallback, not the near-term implementation path.

> **Disposition update, 2026-09-01:** the compressed-boundary kdiff/QBX route
> described as the near-term plan in historical sections below has now been
> measured and closed as an active production direction. See
> [`qbx_closure.md`](../qbx_closure.md). The next production candidate keeps the
> SDF but extracts ordered components and applies a coherent Kress/Nyström
> discretization. True Cartesian volume IBIM remains a separate fallback.

---

# 0. Important constraints for Codex

## Do not fix inverse/adjoint code before the forward solver is finalized

First establish a correct and accurate **forward operator**.

The inverse and adjoint depend on the forward discretization, so changes there before
validating the forward solver will make debugging much harder.

This is a hard sequencing rule, not just a preference:

- do not port `ibim_tmz_adjoint.py` to a new formulation yet;
- do not repair inverse-loop failures caused by a forward-formulation mismatch;
- do not tune `SirenSDF2D`, inverse losses, learning rates, regularizers, or shape
  updates while the forward operator is still moving;
- do not run the inverse pipeline as evidence for or against a forward change.

If `gpr_bem_mod` forward changes make an adjoint or inverse test fail, treat that
failure as an expected downstream mismatch and leave it visible. The right response is
to finish the forward validation, not to make the inverse/adjoint agree with an
operator that may still change.

Recommended order:

1. audit the current transmission BIE;
2. verify/correct operator signs and solve strategy;
3. build an independent high-accuracy explicit BIE reference;
4. improve singular/near-singular quadrature;
5. only then propagate the chosen formulation into the adjoint/inverse.

For this document, "forward finalized" means at least:

- the selected forward formulation is derived and mapped to code;
- circle validation against the Fourier-Bessel reference is automatic;
- solver-specific driver defaults and stored metadata are correct;
- an independent high-order explicit reference exists, or the decision not to build
  one is documented with measurements;
- the remaining 8 GHz / non-circular-shape questions have been either resolved or
  explicitly scoped out of the current forward target.

## Terminology: current method is compressed-boundary quadrature, not volume IBIM

The repo currently does approximately

\[
\text{SDF}
\rightarrow
\text{Cartesian narrow band}
\rightarrow
\text{projected/compressed boundary cloud}
\rightarrow
\text{surface-cloud BIE quadrature}
\rightarrow
\text{trace/collocation on the same cloud}.
\]

In the current code path, the tubular region is **not** retained as the
operator quadrature domain. It is a way to obtain an approximate boundary
discretization from the SDF. After compression, the solver is much closer to a
low-order surface-cloud Nyström/BEM discretization than to the volume
quadrature in the implicit-boundary-integral papers.

The original implicit-boundary-integral literature works more directly with

\[
\text{SDF}
\rightarrow
\text{Cartesian narrow band}
\rightarrow
\text{closest-point volume quadrature}
\rightarrow
\text{singularity correction / regularization}
\rightarrow
\text{true boundary operator}.
\]

This distinction matters in both directions:

- Do not claim the current solver has implemented the singular/volume IBIM
  quadrature from the literature. It has not.
- Do not assume a volume IBIM prototype must reject coincident closest-point
  projections. In that literature, multiple narrow-band grid points projecting
  to the same or nearly the same surface point are part of the lifted singular
  structure and require a quadrature correction.
- When this document says "current IBIM" or refers to `gpr_bem_mod`, read that
  as "SDF-derived compressed-boundary quadrature" unless it explicitly says
  "volume IBIM" or "lifted narrow-band quadrature".

## Do not blindly flip signs

The validation report suspects that exterior and interior blocks are being **summed** where the Müller construction should contain a **difference**.

Do not patch `+` to `-` by inspection.

Instead:

1. fix one global normal convention;
2. derive both one-sided trace equations;
3. apply the transmission conditions;
4. simplify the final block system;
5. verify that the leading hypersingular principal parts cancel.

The cancellation is the invariant mathematical check.

## Do not blindly delete the `A²` solve either

First identify why it exists.

If it is intended as a Calderón-type preconditioner, document the exact operator identity it is using.

If there is no such derivation and it is literally only

\[
Aq=b
\quad\mapsto\quad
A^2 q = Ab,
\]

then compare it against a direct solve of \(Aq=b\) and prefer the latter unless there is a demonstrated reason not to.

---

# 1. Mechanism 6.1 — finite stand-off trace evaluation

## 1.1 Current problem

The current solver avoids evaluating layer potentials exactly on the boundary by evaluating at points

\[
x^\pm = x \pm d\,n(x).
\]

This makes the trace approximation itself depend on \(d\).

The validation report found a practical conflict:

\[
d \gg h
\]

is needed so plain quadrature does not become near-singular, while

\[
d \ll \lambda
\]

is needed so the field at \(x\pm dn\) is close to the true boundary trace.

At the operating frequency, the residual error behaves approximately like

\[
E \sim O(kd),
\]

so tuning \(d\) cannot remove the structural error.

---

## 1.2 How classical BIE literature fixes this

Classical boundary integral methods normally do **not** approximate the boundary trace using a finite stand-off.

They use analytical jump relations.

For a double-layer potential, schematically,

\[
\gamma^\pm D\phi
=
K\phi
\pm \frac12 \phi,
\]

with the exact sign depending on the normal/time convention.

The solver then evaluates the limiting boundary operator \(K\) using a quadrature designed for its singularity.

Therefore the classical remedy is:

> **evaluate the actual limiting boundary operator, not the physical field at a surrogate point off the surface.**

### Relevant literature

**Kress, 1991 — boundary integral equations in time-harmonic acoustic scattering**

- Reviews 2D Helmholtz BIEs on smooth curves.
- Uses equidistant parameter grids together with quadrature rules that explicitly account for logarithmic kernel singularities.
- Reports rapid/exponential convergence for analytic boundaries and data.

Reference:

R. Kress, *Boundary integral equations in time-harmonic acoustic scattering*, Mathematical and Computer Modelling 15 (1991), 229–243.  
DOI: https://doi.org/10.1016/0895-7177(91)90068-I

**Kress, 1995 — hypersingular Helmholtz integral equation**

- Treats a hypersingular integral equation directly.
- Uses a fully discrete collocation/trigonometric method.
- Proves exponential convergence for analytic boundaries/data.

Reference:

R. Kress, *On the numerical solution of a hypersingular integral equation in scattering theory*, Journal of Computational and Applied Mathematics 61 (1995), 345–360.  
DOI: https://doi.org/10.1016/0377-0427(94)00073-7

---

## 1.3 QBX: relevant because it also uses an off-surface distance, but correctly

Quadrature by Expansion (QBX) places an expansion center off the boundary:

\[
c = x + r\,n(x).
\]

But it does **not** use

\[
u(x) \approx u(c).
\]

Instead, it constructs a local analytic expansion of the layer potential around \(c\) and evaluates that expansion **back at the boundary point \(x\)**.

Thus \(r\) is an expansion radius, not a trace approximation.

This distinction eliminates the fundamental \(O(kd)\) stand-off error.

QBX is designed for:

- singular kernels,
- nearly singular kernels,
- one-sided traces,
- even hypersingular operators.

Reference:

A. Klöckner, A. Barnett, L. Greengard, M. O'Neil,  
*Quadrature by expansion: A new method for the evaluation of layer potentials*, Journal of Computational Physics 252 (2013), 332–349.  
DOI: https://doi.org/10.1016/j.jcp.2013.06.027  
Preprint: https://arxiv.org/abs/1207.4461

### Codex implication

If retaining a surface-node formulation, QBX is a serious alternative to the current stand-off method.

Do **not** implement it first, however. A high-order explicit Nyström reference is easier to validate and should come first.

**Update, 2026-08-27:** `nystrom_ref` now exists and is the trusted oracle, so
this precondition is satisfied. QBX has been implemented, as
`solvers/gpr_bem_qbx/` forked from `gpr_bem_kdiff` (see
`docs/validation_change_log.md`, "`gpr_bem_qbx` built and measured"). It is
verified correct against the closed-form kernel (1e-13 agreement on
well-separated pairs) and does genuinely execute a near-diagonal correction
band, but that correction changes matrix entries by only ~1e-8 to 1e-11
relative even on the highest-curvature test shape (star), and the solved
field is numerically indistinguishable from `gpr_bem_kdiff` at every tested
frequency on circle/ellipse/star. So: QBX itself works, but the specific gap
it was built to close (`gpr_bem_kdiff`'s missing off-diagonal-but-nearby
log-singular correction for T) is not, in fact, the dominant error source on
curved targets at the resolutions tested -- that source has not yet been
isolated (most likely the shared local-osculating-circle diagonal fit,
unchanged in this fork). QBX was also, deliberately, not extended to the
exact diagonal itself: the construction has a genuine, measured degeneracy
there (target and source sit at exactly equal distance from the expansion
center, the boundary of Graf's addition theorem's convergence, not strictly
inside it) that no expansion radius or truncation order fixes -- see the
module docstrings in `solvers/gpr_bem_qbx/` for the derivation. The auxiliary
radius used (expansion radius below local node spacing, capped by local
radius of curvature) is exactly the kind of "numerical quadrature parameter
with a demonstrated convergence theory" the acceptance criteria below ask
for, not a tuned physical offset.

**Closure update, 2026-09-01:** later full-row experiments sharpened this
result. QBX T reaches approximately `1e-9`--`1e-7` action error on coherently
ordered analytic curves, so the mathematics is retained. On compressed IBIM
targets, however, same-node QBX is underresolved, every stored oversampled row
has invalid expansion clearance, Fourier transfer is ill-conditioned on the
ellipse/star, and exact source-side geometry plus one ordered-transfer
construction still leaves a forward-error plateau. The local-circle diagonal
is therefore not established as the sole or leading remaining cause, and
further QBX/source tuning on this cloud is not the current plan. The complete
evidence and limitations are in [`qbx_closure.md`](../qbx_closure.md).

---

## 1.4 Literature background: implicit BIEs

### Kublik, Tanushev & Tsai, 2013

The original implicit interface boundary integral method rewrites a surface integral as a volume integral over a thin tubular neighborhood of the implicitly represented boundary.

Schematically,

\[
\int_\Gamma f(x)\,ds_x
=
\int_{T_\epsilon}
f(P_\Gamma y)
J_\Gamma(y)
\delta_\epsilon(d(y))
\,dy.
\]

Here:

- \(d(y)\) is signed distance;
- \(P_\Gamma y\) is the closest-point projection;
- \(J_\Gamma\) is the Jacobian factor;
- \(\delta_\epsilon\) localizes the integral to the narrow band.

The key computational feature is that the quadrature lives on the regular Cartesian lattice; an explicit surface parameterization is not required.

Reference:

C. Kublik, N. M. Tanushev, R. Tsai,  
*An implicit interface boundary integral method for Poisson's equation on arbitrary domains*, Journal of Computational Physics 247 (2013), 279–311.  
DOI: https://doi.org/10.1016/j.jcp.2013.03.049

### Why this matters to the current repo

This section is not a description of the current implementation. The repo does
not currently carry Cartesian narrow-band nodes into operator assembly as the
volume quadrature nodes. The repo compresses/projections them into an estimated
boundary cloud first, then integrates on that cloud.

The literature still matters for two reasons:

- it explains why the current compressed-cloud route is not the only possible
  SDF-compatible route;
- it remains the fallback if the near-term compressed-boundary
  kernel-differenced plan cannot handle irregular nodes or corners.

The repo's compressed surface cloud is therefore **not required by the core
IBIM idea**, but it is the current design choice.

The original method is designed precisely so the SDF / closest-point / Cartesian-grid representation can be retained.

---

## 1.5 Chen & Tsai, 2017 — Helmholtz + hypersingular implicit BIE

This paper is especially relevant because it extends the implicit-boundary approach to the Helmholtz equation and explicitly discusses hypersingular integrals.

They develop an implicit formulation that:

- works with an implicitly represented boundary;
- avoids requiring an explicit surface mesh;
- handles the singular/hypersingular operators through regularization/extrapolation rather than a fixed stand-off trace.

Reference:

C. Chen, R. Tsai,  
*Implicit boundary integral methods for the Helmholtz equation in exterior domains*, Research in the Mathematical Sciences 4, 19 (2017).  
DOI: https://doi.org/10.1186/s40687-017-0108-y

### Codex task

Read this paper before redesigning the volumetric path.

Specifically identify:

1. how the Helmholtz layer operators are rewritten in the narrow band;
2. how the limiting/hypersingular integrals are regularized;
3. what extrapolation parameter replaces the repo's fixed `offset_distance`;
4. which components can be transferred to the scalar TMz transmission system.

---

## 1.6 Izzo, Runborg & Tsai, 2022 — corrected trapezoidal singular IBIM

This is probably the **single most relevant paper** for the current numerical problem.

The key observation is:

> when the boundary integral is lifted to the narrow-band volume, the original point singularity becomes a singularity along the surface-normal line.

The paper then derives **local corrections to the Cartesian trapezoidal rule** around that singular structure.

This is directly relevant to the repo's observation that many narrow-band nodes project onto the same or nearly the same boundary point.

Those coincident/near-coincident projections are not inherently a reason to reject the volumetric path. They are part of the singular structure that a corrected quadrature must handle.

Reference:

F. Izzo, O. Runborg, R. Tsai,  
*Corrected trapezoidal rules for singular implicit boundary integrals*, Journal of Computational Physics 461 (2022), 111193.  
DOI: https://doi.org/10.1016/j.jcp.2022.111193  
Preprint: https://arxiv.org/abs/2107.01438

Follow-up:

F. Izzo, O. Runborg, R. Tsai,  
*High-order corrected trapezoidal rules for a class of singular integrals*, Advances in Computational Mathematics 49, 60 (2023).  
DOI: https://doi.org/10.1007/s10444-023-10060-0

### Codex task

Treat this as the main candidate for a **final SDF-compatible solution** to mechanisms 6.1 and 6.2.

Do not integrate it into the inverse immediately.

First implement a standalone forward-only prototype for the analytic circle and test against the existing Fourier–Bessel reference.

---

# 2. Mechanism 6.2 — irregular projected boundary nodes

## 2.1 Current problem

The validation report found persistent irregularity in the compressed projected nodes:

- spacing standard deviation is a large fraction of mean spacing;
- local spacing ratios can be very large;
- irregularity does not disappear cleanly under grid refinement.

A single global stand-off therefore cannot match the local discretization scale.

---

## 2.2 Classical BEM mitigation

Classical Nyström/BEM avoids this by explicitly controlling the boundary discretization.

For a smooth periodic parameterization

\[
x=x(t),
\qquad
0\le t<2\pi,
\]

one uses:

- uniform parameter nodes;
- Gaussian panels;
- adaptive panels;
- graded meshes near nonsmooth points.

The local quadrature scale is therefore known.

This is why the report's uniform-arclength experiment improves low-frequency error.

However, the report also showed that at the important 2.5 GHz operating frequency, uniform nodes give only a modest gain because stand-off consistency error has already become dominant.

Therefore:

> **Do not spend major effort on arclength resampling as the main fix.**

It fixes only mechanism 6.2 while leaving mechanism 6.1.

---

## 2.3 Literature volume-IBIM mitigation: retain the Cartesian lattice

The more natural answer in the volume-IBIM literature is not to regularize the
projected points into a conventional surface mesh.

The actual quadrature nodes remain the regular Cartesian narrow-band points \(y_j\).

The surface is sampled through \(P_\Gamma(y_j)\), with narrow-band weights such as

\[
w_j
\sim
h^d
J(y_j)
\delta_\epsilon(d(y_j)).
\]

Several \(y_j\) may project to the same or nearly the same point on \(\Gamma\).

That is acceptable **if the singular quadrature has been derived for this lifted formulation**.

### Codex implication

This is future/fallback guidance, not a statement about how `gpr_bem_mod`
currently assembles operators. The current assembly works on a compressed
surface cloud and therefore has conventional surface-node assumptions.

The current check that rejects mutually coincident projected points should not
be treated as a universal mathematical requirement.

Before keeping that validation rule, determine whether it only exists because the current kernel assembly assumes conventional distinct surface nodes.

For a future corrected volume-IBIM implementation, that assumption likely needs
to be removed or replaced.

---

## 2.4 Cartesian-lattice orientation error

A newer analysis studies how IBIM quadrature error depends on the geometry's position relative to the underlying Cartesian grid.

It shows that curvature and grid alignment affect the convergence, and derives variance bounds under random shifts/rotations of the lattice.

Reference:

Y. Zhong, K. Ren, O. Runborg, R. Tsai,  
*Error analysis for the implicit boundary integral method*, BIT Numerical Mathematics 65, 8 (2025).  
DOI: https://doi.org/10.1007/s10543-024-01051-8  
Preprint: https://arxiv.org/abs/2312.07722

### Relation to the repo

This is relevant to the reported four-fold Cartesian ripple.

A practical secondary experiment is **grid-shift averaging**:

\[
I
\approx
\frac{1}{M}
\sum_{m=1}^{M}
I_{h,\xi_m},
\]

where \(\xi_m\) are sub-cell translations of the Cartesian lattice.

This may reduce alignment artifacts.

### Priority

Low-to-medium.

Do this only after the singular/trace treatment is correct.

It cannot fix the main \(O(kd)\) stand-off error.

---

## 2.5 Optional diagnostic: local offset

If Codex wants one cheap diagnostic while preserving the existing compressed formulation, test

\[
d_i = C h_i
\]

instead of a single global \(d\), where \(h_i\) is a local neighbor-spacing estimate.

This tests how much of the error comes specifically from local spacing variation.

### Do not treat this as the final method

It still approximates the true trace using an off-surface field:

\[
u(x)\approx u(x+d_i n),
\]

so the finite-\(d_i\) consistency error remains.

---

# 3. Mechanism 6.3 — the 2 GHz relative-error spike

## 3.1 This is not primarily a forward-solver defect

The validation report showed that the true scattered field is near a physical null around 2 GHz.

Therefore

\[
E_{\mathrm{rel}}(f)
=
\frac{\|u_h(f)-u(f)\|}
{\|u(f)\|}
\]

becomes very large simply because the denominator is small.

The absolute error continues to converge normally.

Do **not** attempt to "fix" the forward operator merely to flatten this relative-error spike.

---

## 3.2 Change validation metrics

Add at least these metrics:

### Absolute frequency-resolved error

\[
E_{\mathrm{abs}}(f)
=
\|u_h(f)-u(f)\|_2.
\]

### Mixed relative/absolute error

\[
E_{\mathrm{mixed}}(f)
=
\frac{
\|u_h(f)-u(f)\|_2
}{
\max(\|u(f)\|_2,\tau)
}.
\]

Choose and document \(\tau\).

Prefer a physically interpretable scale, e.g. a fixed fraction of the peak exact scattered-field norm across the tested band.

### Broadband relative error

\[
E_{\mathrm{band}}
=
\frac{
\left(
\sum_f \|u_h(f)-u(f)\|_2^2
\right)^{1/2}
}{
\left(
\sum_f \|u(f)\|_2^2
\right)^{1/2}
}.
\]

This prevents a single physical scattering null from dominating the validation.

### Time-domain gated error

Retain the late-time gate metric because that is closer to what the inverse actually fits.

---

## 3.3 Avoid accidental inverse weighting by zeros

Check the inverse objective.

Do not use a loss like

\[
J
=
\sum_f
\frac{
\|u_{\rm pred}(f)-u_{\rm obs}(f)\|^2
}{
\|u_{\rm obs}(f)\|^2
}
\]

unless that weighting is deliberately derived from a noise model.

Otherwise frequencies where the measured scattering is nearly zero receive enormous and usually unphysical weight.

---

# 4. Mechanism 6.4 — conditioning and hypersingular cancellation

## 4.1 Why the Müller formulation matters

For penetrable Helmholtz/dielectric transmission, a Müller-type formulation combines interior and exterior operators so that the leading singular parts cancel.

Schematically, the hypersingular block appears as

\[
T^{k_{\rm out}}-T^{k_{\rm in}}.
\]

Each \(T^k\) is individually hypersingular.

But the leading local singularity is independent of \(k\), so the difference cancels that principal hypersingular term.

The remaining difference kernel is substantially weaker.

A directly relevant 2D acoustic/electromagnetic reference is:

J. Lai, M. Kobayashi, L. Greengard,  
*A fast solver for multi-particle scattering in a layered medium*, Optics Express 22 (2014), 20481–20499.  
DOI: https://doi.org/10.1364/OE.22.020481  
Preprint: https://arxiv.org/abs/1407.3868

They write a Fredholm second-kind transmission system containing differences such as

\[
S^{k_2}-S^{k_p},
\qquad
D^{k_2}-D^{k_p},
\qquad
N^{k_2}-N^{k_p},
\qquad
T^{k_2}-T^{k_p},
\]

and explicitly note that although \(T^k\) is hypersingular, the difference

\[
T^{k_2}-T^{k_p}
\]

is only logarithmically singular/compact for smooth boundaries.

They discretize using high-order Alpert hybrid Gauss-trapezoidal quadrature.

### Codex implication

Audit `gpr_bem/ibim_tmz_system.py` against a carefully derived scalar TMz transmission system.

If the code truly reinforces the principal hypersingular parts rather than cancelling them, fix the formulation before spending time on low-level conditioning tricks.

---

## 4.2 Concrete derivation task for Codex

Create a developer note, e.g.

`docs/tmz_transmission_bie_derivation.md`

with:

1. time convention;
2. exterior/interior wave numbers;
3. chosen normal orientation;
4. definitions of \(S_k,D_k,N_k,T_k\);
5. exterior and interior representation formulas;
6. one-sided jump relations;
7. TMz transmission conditions;
8. final \(2\times2\) block operator;
9. explicit indication of which principal singularities cancel.

Then map every mathematical block to the corresponding code assembly.

Do not merge a sign change without this derivation.

---

## 4.3 Do not evaluate two huge hypersingular operators and subtract them naively if avoidable

Even if the correct continuum formula is

\[
T_{k_1}-T_{k_2},
\]

a robust implementation should preferably expose the cancellation analytically.

Useful literature techniques include:

- singularity subtraction;
- Maue-type identities;
- integration by parts;
- tangential derivative formulations;
- direct evaluation of a difference kernel whose leading singular terms have already cancelled.

This is preferable to forming two very large nearly equal floating-point values and subtracting them afterward.

---

## 4.4 Direct solve versus `A²`

The validation report measured approximately

\[
\kappa(A)\sim10^{11},
\qquad
\kappa(A^2)\sim10^{22}.
\]

Even though the current physical right-hand side happens not to excite the worst-conditioned directions strongly, this is a latent risk.

### Codex experiment

For the same assembled \(A,b\), compare:

1. current `A²q=Ab` route;
2. direct `Aq=b` solve;
3. residual \(\|Aq-b\|/\|b\|\);
4. solution difference;
5. condition estimates;
6. forward scattered-field error against the analytic circle.

Do this in float64.

If the direct solve is at least as accurate and stable, remove the squaring unless a real operator-preconditioning derivation justifies it.

---

## 4.5 Important nuance: Calderón preconditioning may also contain operator products

Do not confuse the warning above with a claim that all squared boundary operators are wrong.

Calderón preconditioning deliberately composes specific boundary operators using Calderón identities in order to obtain better spectral properties.

That is mathematically different from indiscriminately left-multiplying a system by itself.

Useful references:

I. Fierro, C. Jerez-Hanckes,  
*Fast Calderón preconditioning for Helmholtz boundary integral equations*, Journal of Computational Physics 409 (2020), 109355.  
DOI: https://doi.org/10.1016/j.jcp.2020.109355

For electromagnetic dielectric transmission, see also the broader PMCHWT/Calderón literature. Note that some PMCHWT Calderón schemes intentionally involve an operator square, but the beneficial conditioning follows from the **specific Calderón identities and compatible discretization**, not from squaring an arbitrary matrix.

---

# 4b. Mechanism 6.5 — normal-derivative traces built by finite differences

## 4b.1 What the code does

`K'` (adjoint double layer) and `T` (hypersingular) are **not** assembled from their
own kernels. Both are obtained by finite-differencing a lower-order potential along
the normal:

- `implicit_single_layer_normal_derivative_trace_from_band` (`ibim_tmz_forward.py:342`)
  evaluates the *single-layer* potential at \(x \pm m d\,n(x)\) for \(m=1,2,3\);
- `implicit_double_layer_normal_derivative_trace_from_band` (`:402`) does the same with
  the *double-layer* potential;
- `_one_sided_normal_derivative` (`:813`) then applies

\[
f'(0)\;\approx\;\frac{-5 f(d) + 8 f(2d) - 3 f(3d)}{2d},
\]

with the sign flipped on the interior side.

`build_implicit_adjoint_double_layer_boundary_matrix` (`:568`) and
`build_implicit_hypersingular_boundary_matrix` (`:597`) are thin wrappers over those,
so **half of the multitrace block system is a finite difference**.

The stencil is algebraically correct: it is the standard second-order one-sided
extrapolation of \(f'(0)\) from samples at \(d, 2d, 3d\), and because the layer
potential is smooth up to \(\Gamma\) from each side, extrapolating to \(t=0\) targets
the true one-sided trace. That part is sound and should be credited — it is a crude
cousin of the extrapolation-to-the-limit idea in Chen & Tsai 2017.

## 4b.2 Why it is nevertheless the wrong construction

The evaluation points already stand off the surface by \(d>0\). At that distance the
kernel is **not singular**, so the analytic normal derivative is directly evaluable.
The closed forms are elementary:

\[
\frac{\partial}{\partial n_x}\,\frac{i}{4}H_0^{(1)}(k r)
= -\frac{i k}{4} H_1^{(1)}(k r)\,\frac{(x-y)\cdot n_x}{r},
\]

\[
\frac{\partial^2}{\partial n_x \partial n_y}\,\frac{i}{4}H_0^{(1)}(k r)
= \frac{i k}{4}\left[
H_1^{(1)}(kr)\,\frac{n_x\cdot n_y}{r}
- k\,H_2^{(1)}(kr)\,
\frac{\bigl((x-y)\cdot n_x\bigr)\bigl((x-y)\cdot n_y\bigr)}{r^2}
\right],
\]

up to the sign convention fixed by the derivation task in §4.2. Both reuse the
`displacement` / `distance` arrays already formed in
`implicit_double_layer_potential_from_band`.

Three concrete costs of differencing instead:

**(a) Noise amplification \(\sim 1/d\).** The stencil coefficients sum to
\(|{-5}|+|8|+|{-3}| = 16\) over a denominator \(2d\). A relative quadrature error
\(\varepsilon\) in the individual potentials becomes \(\approx 8\varepsilon/d\) in the
derivative. Near-singular plain quadrature is exactly where \(\varepsilon\) is worst,
and this construction divides it by the small number.

> **Measured 2026-08-24 — this argument is real but was never the binding constraint.**
> Under the Müller formulation the finite difference is well behaved down to
> \(d = 0.125\,\text{md}\), a sixteenth of the historical stand-off, and its error keeps
> falling as \(d\) shrinks. The small-\(d\) blow-up that motivated this point belongs to
> the first-kind formulation, not to the differencing: the analytic kernels, which do no
> differencing whatsoever, blow up there by exactly the same amount. See
> `validation_change_log.md`. The differencing costs roughly a factor 1.4–2.4 in
> accuracy at matched optima, not the order of magnitude implied here.

**(b) The third stencil point sits deep in the bad region.** With
`offset = 2 × merge_distance = 0.0025` and a mean node gap of `0.00115` at the
pipeline's 257² grid, the three samples lie at roughly **2.2h, 4.3h and 6.5h** in units
of node spacing. `forward_solver_validation.md` §6.1 measured the standalone trace
error at \(d=8h\) as **0.347 / 1.821 / 3.885** at 0.5 / 1.5 / 2.5 GHz. The
\(m=3\) sample is therefore drawn from a regime where the offset error already
dominates, and it enters the derivative with coefficient \(3/2d\).

**(c) Cost.** Six dense Hankel assemblies per operator per frequency (3 offsets × 2
sides) where the analytic kernel needs two. Across `K'` and `T` that is 12 versus 4
\(N\times N\) kernel builds, at 385 frequencies.

## 4b.3 It also blocks the Müller fix

§4.1 and §4.3 require the hypersingular cancellation \(T^{k_{\rm out}} - T^{k_{\rm in}}\)
to be exposed **analytically**, ideally as a single difference kernel whose leading
singular terms have already cancelled. That is not expressible when each \(T^k\) is
itself a finite difference of separately assembled double-layer potentials: the
cancellation can only happen after two large, noisy, independently differenced
matrices are subtracted — precisely the pattern §4.3 warns against.

**Analytic `K'` and `T` kernels are therefore a prerequisite for a clean Müller
implementation, not an independent cleanup.**

> **Measured 2026-08-24 — this is the strongest claim in §4b and it is false.** Müller
> was implemented and measured with the finite-difference blocks left exactly as they
> were, and it works: a 390x / 56x / 10x accuracy win and `cond(A)` down seven orders of
> magnitude, before any analytic kernel is involved. §4.1's cancellation is a statement
> about the *continuous* operators; the discrete blocks do not have to expose it
> term-by-term for the second-kind structure to appear, because what bounds the spectrum
> is the surviving identity on the diagonal, not the smoothness of the `T` difference.
> The pattern §4.3 warns against — subtracting two large noisy matrices — is real, and
> is why the analytic kernels still buy 1.4–2.4x, but it is a refinement, not a gate.
> §4b is an independent cleanup after all, and should have been ordered after §4.

## 4b.4 Codex task

Three variants, in increasing ambition:

- **(B) Analytic kernel at \(\pm d\).** Replaces the FD with the exact off-surface
  normal-derivative kernel. Removes (a) and (c) entirely. Retains the \(O(kd)\)
  consistency error of the stand-off — and gives up the FD's implicit extrapolation
  to \(t=0\), so it is *not* guaranteed to be more accurate. Its value is diagnostic:
  it isolates how much of the `K'`/`T` error is FD noise versus stand-off consistency.
- **(C) Analytic kernel at \(d, 2d, 3d\) + Richardson extrapolation to \(t=0\).**
  Keeps the extrapolation-to-the-limit benefit while never differencing nearly equal
  potential values. Same assembly cost as the current code. This is the expected
  best of the three, and the natural stepping stone toward Chen & Tsai's
  regularization/extrapolation parameter replacing `offset_distance`.
- **(D) Analytic difference kernel** \(T^{k_1}-T^{k_2}\) formed at the kernel level,
  for use once the Müller derivation in §4.2 is complete.

### Tests

1. **Kernel correctness, no solver involved.** Compare the analytic `K'`/`T` kernel
   against the current FD at a large stand-off (\(d = 8\)–\(16h\)) where the FD is
   well conditioned; they must agree to the FD truncation order.
2. **Convergence in \(d\).** Sweep \(d\) and confirm the analytic variants no longer
   show the \(1/d\) noise blow-up at small \(d\) that the FD does. This is the
   measurement that decides whether the current `offset` lower bound is set by the
   quadrature or by the differencing.

   > **Answered 2026-08-24: neither.** It is set by the formulation. All three schemes
   > blow up identically at small \(d\) under the first-kind system (2.442 / 2.442 /
   > 2.441 at \(d = 0.125\,\text{md}\)) and none of them does under Müller. This sweep
   > was the most valuable thing in §4b, exactly as predicted, but it refuted §4b rather
   > than confirming it.
3. **Fourier–Bessel regression.** Rerun `pytest/test_ibim_tmz_theory_validation.py`
   at 0.5 / 1.5 / 2.5 GHz. Record absolute, relative and mixed error per §3.2.
4. **Assembly timing**, to confirm the expected ~3× reduction on the `K'`/`T` blocks.

### Ordering

Do this **before** the Müller audit in Phase B, not after. It is cheap, it is
independently testable against a kernel identity rather than against the full solver,
and Phase B's cancellation check is much harder to interpret while `T` is a finite
difference.

---

# 5. How the four mechanisms interact

The most important structural conclusion is:

\[
\boxed{
\text{mechanism 6.1 and mechanism 6.2 are strongly coupled}
}
\]

The current chain

\[
\text{narrow band}
\rightarrow
\text{compressed irregular nodes}
\rightarrow
\text{global stand-off}
\]

creates both:

- local-spacing sensitivity;
- finite-offset trace error.

Here "narrow band" is only the geometry-extraction stage. By the time the
operators are assembled, the quadrature/collocation nodes are the compressed
surface points.

The singular-IBIM literature suggests one possible future way to attack the
two mechanisms together:

\[
\text{narrow band}
\rightarrow
\text{closest-point volume quadrature}
\rightarrow
\text{corrected singular quadrature}
\rightarrow
\text{true boundary trace}.
\]

Mechanism 6.3 should be separated from this: it is mainly a metric issue.

Mechanism 6.4 should be audited **before** a large quadrature redesign because a formulation/sign error could contaminate all later conclusions.

Mechanism 6.5 sits underneath 6.4. The finite-difference construction of `K'` and `T`
both amplifies whatever quadrature error mechanism 6.1 leaves behind (by \(1/d\)) and
makes the Müller cancellation impossible to expose analytically. It is cheap to fix
and should be done first, so that the 6.4 audit is performed on operators assembled
from their own kernels.

---

# 6. Recommended implementation sequence

## Phase A — preserve the existing validated baseline

Before changing anything:

1. run the current post-fix analytic-circle validation;
2. save metrics for at least:
   - 0.5 GHz,
   - 1.5 GHz,
   - 2.0 GHz,
   - 2.5 GHz,
   - 4.0 GHz,
   - 8.0 GHz;
3. save:
   - absolute error,
   - relative error,
   - system condition estimate,
   - residual,
   - number of boundary/narrow-band nodes,
   - effective merge distance,
   - trace offset,
   - runtime.

Put results in a machine-readable `.npz`/`.json` and a Markdown table.

Do not rely on plots alone.

---

## Phase B — audit the Müller/transmission operator

### Deliverables

- `docs/tmz_transmission_bie_derivation.md`
- a code-to-equation mapping for `ibim_tmz_system.py`
- a unit test that checks the expected difference/cancellation structure

### Tests

Use the analytic circle and compare against the Fourier–Bessel solution.

Test the current operator and any corrected operator at identical discretization.

Acceptance is not merely "condition number smaller."

A corrected formulation should also:

- satisfy the transmission conditions numerically;
- converge toward the analytic reference;
- not degrade the low-frequency solution.

---

## Phase C — compare `Aq=b` against the current `A²q=Ab`

Do this after the operator audit.

Record:

- \(\kappa(A)\);
- \(\kappa(A^2)\);
- forward residual;
- solution difference;
- analytic-reference field error.

Unless the current squaring is tied to a justified operator identity and helps accuracy/robustness, prefer the direct second-kind solve.

---

## Phase D — build a high-accuracy explicit reference solver

Implement a standalone 2D smooth-boundary Nyström solver using a standard parameterization.

This is not yet the production SDF solver.

Its purpose is to answer:

> if the transmission BIE and singular quadrature are implemented conventionally, what accuracy is achievable at the same frequency and number of degrees of freedom?

### Minimum geometries

1. circle;
2. ellipse;
3. one smooth non-circular star-shaped boundary.

### Minimum tests

For the circle:

- compare against the exact Fourier–Bessel series;
- verify monotonic convergence under node refinement;
- sweep the same frequency set.

For non-circles:

- self-convergence under refinement;
- optional comparison against an independent package if available.

### Suggested quadrature

Start with Kress/Alpert-style smooth-curve Nyström rather than trying to build the final implicit method immediately.

Relevant references:

- Kress 1991
- Kress 1995
- Lai, Kobayashi & Greengard 2014

---

## Phase E — prototype compressed-boundary kernel-differenced quadrature

After Phases B-D, return to the SDF-derived geometry path, but stay clear
about what is being prototyped:

\[
\text{SDF}
\rightarrow
\text{Cartesian narrow band}
\rightarrow
\text{projected/compressed boundary cloud}
\rightarrow
\text{kernel-differenced surface-cloud quadrature}.
\]

This is **not** the literature volume-IBIM quadrature. The narrow band still
only provides the approximate boundary points, normals, and weights. The
operator assembly uses those compressed boundary samples directly as both
quadrature nodes and collocation/trace nodes.

### Historical near-term target (completed and closed)

The following was the 2026-08-26 plan. It produced `gpr_bem_kdiff` and the QBX
follow-ups; the measured outcome is now closed in
[`qbx_closure.md`](../qbx_closure.md). It is retained to explain the experiment,
not to direct current work.

Build a third solver package, `solvers/gpr_bem_kdiff/`, forked from
`gpr_bem_mod`.

Keep the geometry/SDF machinery byte-identical to `gpr_bem_mod`. The only
intended change is how the boundary integral operators are assembled:

- `gpr_bem_mod` assembles exterior and interior operators separately using
  finite stand-off traces at `boundary_points +- offset * normals`, then
  subtracts those already-assembled operators in the Muller system.
- `gpr_bem_kdiff` should form the exterior-minus-interior Muller kernels
  analytically first, then evaluate those difference kernels directly between
  the compressed boundary nodes.
- Off-diagonal entries are direct pairwise evaluations on the point cloud.
- Diagonal/self entries are the only special case. The open plan is a local
  Richardson-style limit using each node's nearest already-stored neighbors
  from the same compressed cloud. Do not assume a continuum parameterization,
  curvature field, or global arclength ordering unless measurement shows that
  the simpler local correction fails.

The reason this became the plan was the 2026-08-26 `kernel_diff_ref` result:
on a perfect circle, the same kernel-differenced Muller construction hosted on
`ImplicitBoundarySamples2D` reaches ~1e-8 to 1e-13 relative error against the
Mie series at 0.5-8 GHz, with no trace offset and no lifted volume
quadrature. That does not prove the compressed irregular cloud is good enough,
but it isolates the next unknown to the diagonal/local correction on the real
cloud.

### Validation order

Validate `gpr_bem_kdiff` against the existing explicit references before
touching adjoint or inverse code:

1. circle, to check that the new package reproduces the already-understood
   `kernel_diff_ref` behavior when the boundary is benign;
2. ellipse and star, because `nystrom_ref` gives a high-accuracy smooth-shape
   yardstick;
3. square last, because corners are the most likely place for a nearest-neighbor
   diagonal correction to break.

### Future/fallback: true volume IBIM

If the compressed-boundary kernel-differenced route fails - especially on
irregular samples or square corners - then revisit a literature-accurate
volume-IBIM prototype based on:

- Kublik et al. 2013;
- Chen & Tsai 2017;
- Izzo, Runborg & Tsai 2022/2023.

That fallback would keep Cartesian narrow-band nodes as volume quadrature nodes
and derive singular corrections for the lifted closest-point integral. It is a
different method from the current repo path, not a cleanup of the existing
surface-cloud assembly.

---

## Phase F — test whether the new compressed-boundary quadrature actually solves the reported error

At identical physical settings compare:

1. current compressed + stand-off solver;
2. uniform-arclength explicit Nyström reference;
3. `gpr_bem_kdiff` on the real compressed boundary;
4. future volume-IBIM prototype, only if that fallback has actually been built.

Measure:

\[
E_{\rm abs}(f),
\quad
E_{\rm mixed}(f),
\quad
E_{\rm band},
\]

plus runtime and memory.

### Desired result

The corrected compressed-boundary method should show convergence without having
to enforce the contradictory requirements

\[
d\gg h,\qquad d\ll \lambda.
\]

If it still exhibits an \(O(kh)\)-type floor, diagnose whether the cause is the
compressed boundary cloud, the local diagonal correction, or the remaining
surface quadrature approximation before integrating it into the inverse.

---

## Phase G — investigate 8 GHz separately

The validation report explicitly says the 8 GHz non-convergence remains unexplained even with uniform arclength nodes.

Do not assume corrected node spacing alone will fix it.

After the Müller audit and high-order reference solver exist, compare at 8 GHz:

- exact Fourier–Bessel solution;
- high-order Nyström;
- current compressed-boundary stand-off solver;
- `gpr_bem_kdiff` compressed-boundary solver;
- future volume-IBIM prototype, if one exists.

Possible categories to test:

- formulation/sign issue;
- insufficient singular quadrature order;
- loss of accuracy in kernel derivatives;
- cancellation error in hypersingular differences;
- inadequate resolution;
- numerical precision;
- Bessel/Hankel evaluation scaling.

Document which hypothesis is ruled in/out.

---

## Phase H — only then restore differentiability

This phase is explicitly blocked until the forward solver is finalized under the
criteria in §0. Do not start it merely because `gpr_bem_mod` has an adjoint-gradient
failure after a forward formulation change. That failure is useful because it marks the
old adjoint as stale; it is not permission to work on inverse/adjoint code yet.

Once a forward discretization has been chosen and validated:

1. derive its discrete/continuous shape dependence;
2. update `ibim_tmz_adjoint.py`;
3. verify gradients by directional finite differences;
4. test on the analytic circle before SIREN;
5. only then run the inverse pipeline.

Do not preserve a flawed forward assembly solely because the current adjoint already differentiates it.
Do not preserve a half-validated forward assembly by immediately adapting the adjoint to
it either; the adjoint should follow the final forward operator, not an intermediate
prototype.

---

# 7. Acceptance criteria

The exact numerical thresholds may be refined after the explicit reference solver exists, but use these principles.

## Forward correctness

For a circle:

- exact Fourier–Bessel comparison must be automatic;
- errors must be stored, not only plotted;
- transmission-condition residuals should be checked;
- convergence under refinement must be visible.

## No hidden offset dependence

A final singular-quadrature solution should not rely on a manually tuned physical trace offset whose optimal value changes with \(h\) or frequency.

If any auxiliary radius remains, e.g. QBX expansion radius, it must be a numerical quadrature parameter with a demonstrated convergence theory, not an approximation \(u(x)\approx u(x+dn)\).

## Conditioning

The formulation should exhibit the expected Müller cancellation structure.

Do not accept a "fix" based only on the fact that one RHS still solves despite a condition number around \(10^{22}\).

## Metric handling around scattering zeros

The 2 GHz null should no longer appear as evidence of solver instability when absolute error is normal.

Always report absolute or mixed/broadband metrics beside pure relative error.

## SDF compatibility

The final production route should ideally preserve:

- implicit geometry;
- topology flexibility;
- no mandatory remeshing each inverse iteration;
- differentiability or a tractable adjoint.

The current path keeps the SDF as the geometry and optimization variable, but
changes the discretization consumed by the forward solver: extract ordered
zero-level components before compression, fit solver-grade periodic curves,
and assemble Kress/Nyström quadrature on those curves. Extraction/remeshing can
remain frozen within each forward/adjoint/backward step and be repeated after
an outer SDF update; differentiating through marching squares is not required.
A literature-accurate volume-IBIM route remains a distinct future option.

---

# 8. Things Codex should *not* spend time on first

Do not prioritize:

1. topology-blind arclength resampling of the already compressed cloud
   (extract ordered components before compression instead);
2. retuning `offset_distance`;
3. changing `band_half_width` alone;
4. float32/float64 changes as the main cure;
5. suppressing the 2 GHz relative-error spike by changing physics;
6. inverse/SIREN experiments before forward validation;
7. deleting coincident projected points merely to imitate a conventional surface mesh.

The validation report already provides evidence that several of these are secondary.

---

# 9. Current concrete TODO list

Already completed or superseded, per `validation_change_log.md`:

- [x] Reproduce the post-fix baseline.
- [x] Add absolute, mixed, broadband, and gated validation metrics.
- [x] Compare direct `Aq=b` against `A²q=Ab`.
- [x] Replace the finite-difference `K'`/`T` traces with analytic kernels (§4b).
- [x] Confirm the Müller formulation change in `gpr_bem_mod`.
- [x] Build and validate the standalone Nyström reference for circle, ellipse,
  and smooth star.
- [x] Add the gprMax cache-based independent cross-check.
- [x] Add the perfect-circle sampling diagnostic.
- [x] Add `kernel_diff_ref` for perfect-circle, no-offset, kernel-differenced
  quadrature on `ImplicitBoundarySamples2D`.
- [x] Build and measure `gpr_bem_kdiff` on the real compressed boundary.
- [x] Test near-band and full-row QBX, ordered analytic sources, raw SDF-band
  sources, and ordered density transfer.
- [x] Close compressed-cloud QBX/kdiff as an active production direction; see
  [`qbx_closure.md`](../qbx_closure.md).

Current next work:

- [ ] Harden the existing ordered zero-level contour extraction: reject open
  contours, preserve stable component identity/orientation/phase, diagnose
  topology changes, and reproject nodes to `phi=0`.
- [ ] Fit one smooth periodic evaluator per smooth component and derive points,
  tangents, speeds, normals, curvature, and weights consistently from it.
- [ ] Build a production-candidate Nyström backend, independent of
  `nystrom_ref`, with analytically differenced Müller kernels and
  component-wise Kress quadrature for all four blocks.
- [ ] Independently refine extraction-grid and Nyström-node resolution on
  circle, ellipse, star, and disconnected smooth components.
- [ ] Derive and finite-difference-check the adjoint only after that forward
  discretization passes its accuracy gates.

Future/fallback only:

- [ ] Add a piecewise-smooth panel backend with graded corner quadrature; do
  not silently smooth exact squares in the global periodic path.
- [ ] Read/revisit Kublik 2013, Chen & Tsai 2017, and Izzo et al. 2022/2023 for
  a true volume-IBIM prototype if an ordered-surface route is unsuitable.
- [ ] In that future prototype, allow normal-line/coincident projected points
  where mathematically required by the lifted singular quadrature.

Blocked until forward finalization:

- [ ] Update adjoint/inverse code to match the final forward operator.
- [ ] Validate new gradients by directional finite differences.
- [ ] Rerun the inverse pipeline.

Until the ordered-boundary forward solver is accepted, its new adjoint and
inverse integration are intentionally blocked. Existing `gpr_bem_mod`
inverse/adjoint work may continue as the operational baseline, but it is not
evidence that a future Nyström derivative is correct.

---

# 10. Reference list

## Implicit boundary integral methods

1. **Kublik, Tanushev & Tsai (2013)**  
   C. Kublik, N. M. Tanushev, R. Tsai,  
   *An implicit interface boundary integral method for Poisson's equation on arbitrary domains*,  
   Journal of Computational Physics 247, 279–311.  
   DOI: https://doi.org/10.1016/j.jcp.2013.03.049

2. **Chen & Tsai (2017)**  
   C. Chen, R. Tsai,  
   *Implicit boundary integral methods for the Helmholtz equation in exterior domains*,  
   Research in the Mathematical Sciences 4, 19.  
   DOI: https://doi.org/10.1186/s40687-017-0108-y

3. **Izzo, Runborg & Tsai (2022)**  
   F. Izzo, O. Runborg, R. Tsai,  
   *Corrected trapezoidal rules for singular implicit boundary integrals*,  
   Journal of Computational Physics 461, 111193.  
   DOI: https://doi.org/10.1016/j.jcp.2022.111193  
   arXiv: https://arxiv.org/abs/2107.01438

4. **Izzo, Runborg & Tsai (2023)**  
   F. Izzo, O. Runborg, R. Tsai,  
   *High-order corrected trapezoidal rules for a class of singular integrals*,  
   Advances in Computational Mathematics 49, 60.  
   DOI: https://doi.org/10.1007/s10444-023-10060-0

5. **Zhong, Ren, Runborg & Tsai (2025)**  
   Y. Zhong, K. Ren, O. Runborg, R. Tsai,  
   *Error analysis for the implicit boundary integral method*,  
   BIT Numerical Mathematics 65, 8.  
   DOI: https://doi.org/10.1007/s10543-024-01051-8  
   arXiv: https://arxiv.org/abs/2312.07722

## Classical singular / hypersingular BIE quadrature

6. **Kress (1991)**  
   R. Kress,  
   *Boundary integral equations in time-harmonic acoustic scattering*,  
   Mathematical and Computer Modelling 15, 229–243.  
   DOI: https://doi.org/10.1016/0895-7177(91)90068-I

7. **Kress (1995)**  
   R. Kress,  
   *On the numerical solution of a hypersingular integral equation in scattering theory*,  
   Journal of Computational and Applied Mathematics 61, 345–360.  
   DOI: https://doi.org/10.1016/0377-0427(94)00073-7

## Near-singular evaluation

8. **Klöckner, Barnett, Greengard & O'Neil (2013)**  
   *Quadrature by expansion: A new method for the evaluation of layer potentials*,  
   Journal of Computational Physics 252, 332–349.  
   DOI: https://doi.org/10.1016/j.jcp.2013.06.027  
   arXiv: https://arxiv.org/abs/1207.4461

## Müller/transmission formulation

9. **Lai, Kobayashi & Greengard (2014)**  
   J. Lai, M. Kobayashi, L. Greengard,  
   *A fast solver for multi-particle scattering in a layered medium*,  
   Optics Express 22, 20481–20499.  
   DOI: https://doi.org/10.1364/OE.22.020481  
   arXiv: https://arxiv.org/abs/1407.3868

   Especially relevant because the paper explicitly uses differences of interior/exterior operators and states that the hypersingular difference is only logarithmically singular/compact for smooth boundaries.

## Operator preconditioning

10. **Fierro & Jerez-Hanckes (2020)**  
    I. Fierro, C. Jerez-Hanckes,  
    *Fast Calderón preconditioning for Helmholtz boundary integral equations*,  
    Journal of Computational Physics 409, 109355.  
    DOI: https://doi.org/10.1016/j.jcp.2020.109355

---

# 11. Bottom line

The near-term architecture is **not**

\[
\text{better surface compression}
+
\text{better tuning of }d.
\]

It is also **not yet** a literature-accurate volume IBIM implementation.

The historical compressed-cloud plan was

\[
\boxed{
\text{correct Müller transmission BIE}
+
\text{kernel-differenced limiting quadrature}
+
\text{SDF-derived compressed boundary cloud}
}
\]

with a high-order explicit Nyström solver retained as an independent reference.

That investigation produced `gpr_bem_kdiff` and the QBX diagnostics and is now
closed for production use. The current plan as of 2026-09-01 is

\[
\boxed{
\text{neural SDF}
+
\text{ordered, component-aware zero-level curves}
+
\text{coherent Kress/Nyström Müller quadrature}
}
\]

The highest-priority implementation is therefore:

1. **promote the existing ordered contour extraction into solver-grade smooth
   curve geometry, then build a production-candidate Nyström backend while
   retaining `nystrom_ref` as an independent oracle.**

The literature volume-IBIM path remains valuable as a distinct fallback. It
must not be conflated with the repository's projected/compressed surface-cloud
quadrature.

The 2 GHz spike should be handled at the metric level, while the 8 GHz issue should remain explicitly open until the formulation and quadrature controls are in place.

---

# 12. Historical verdicts, confidence, and implementation plan

Added 2026-08-24. This section records a judgement on each open issue: how important
it is, how confident I am that it can be implemented, and how confident I am that
implementing it will actually reduce error. Those last two are deliberately separate —
several items here are easy to write and uncertain to help.

Status update, 2026-08-26: the table below is partly historical. Issues 1, 4,
4b, 5, and 7 now have implementations or validation artifacts recorded in
`validation_change_log.md`. Issue 2 has been re-scoped: the next implementation
is **compressed-boundary kernel differencing** in a new `gpr_bem_kdiff`
package, not a literature volume-IBIM prototype. True volume IBIM is fallback
work if that compressed-boundary route fails.

The historical first set of changes happened in `solvers/gpr_bem_mod/`.
`solvers/gpr_bem_ref/` is frozen as the control. The subsequently completed
work happened in `solvers/gpr_bem_kdiff/` so the no-offset compressed-boundary
experiment could be compared against both `ref` and `mod`. The comparison
files are `pytest/test_circle_comparison.py`,
`pytest/test_ellipse_comparison.py`, `pytest/test_star_comparison.py`, and
`pytest/test_square_comparison.py`.

Status update, 2026-09-01: the compressed-boundary kdiff/QBX investigation is
closed. The remainder of this section is retained to explain historical
decisions and confidence estimates; it is not the current task order. See
[`qbx_closure.md`](../qbx_closure.md).

## 12.1 Summary table

| # | Issue | Where | Importance | Confidence: can implement | Confidence: will help |
|---|---|---|---|---|---|
| 1 | Operator **sum** where Muller needs a **difference**, and no identity terms | `ibim_tmz_system.py:113-118` | **High** | ~85% | ~60% |
| 2 | Finite stand-off trace, `E ~ O(kd)`; near-term fix is compressed-boundary kernel differencing | `gpr_bem_kdiff` planned | **High** | ~65% for compressed-boundary prototype | ~70% |
| 3 | True volume-IBIM fallback / coincident-projection assumptions | future prototype | Medium | ~35% | n/a unless fallback is needed |
| 4 | `A^2 q = Ab` conditioning | `ibim_tmz_system.py` | **Done** | — | — |
| 5 | 2 GHz relative-error spike is a metric artifact | `validation.py` | Low-medium | ~95% | ~90% |
| 6 | 8 GHz non-convergence | unknown | Medium | ~50% | n/a (diagnostic) |
| 7 | No reference for non-circular / SIREN shapes | new module | **High** | ~70% | ~85% |
| 8 | Adjoint must follow the forward | `ibim_tmz_adjoint.py` | Blocking, later | ~30% | n/a |
| 4b | `K'` and `T` built by finite differences | `ibim_tmz_forward.py:342,402,813` | **Medium-high** | ~90% | ~55% |

**Outcome, 2026-08-24.** Issues 1 and 4b are both implemented in `gpr_bem_mod`. Issue 1
delivered far more than the ~60% confidence anticipated: `cond(A)` fell seven orders of
magnitude and the error fell 10–390x. Issue 4b landed close to its ~55%: it works, and
adds 1.4–2.4x on top of Müller, but it is not the main effect and the mechanism argued
for it in §4b turned out to be wrong. Full numbers and corrections in
`validation_change_log.md`. Issue 2 has since been re-scoped to the
compressed-boundary `gpr_bem_kdiff` plan rather than immediate volume IBIM.

Issue 8 has now materialised as a failing adjoint gradient test on `mod`, but it remains
blocked by the forward-work gate in §0. Do **not** fix `ibim_tmz_adjoint.py` or the
inverse pipeline next. The failure should remain visible until the forward formulation,
quadrature/reference decision, and remaining forward diagnostics are settled.

## 12.2 Verdicts in detail

### Issue 1 — the operator sum. Importance: high.

Both Calderon systems (interior and exterior) can be combined two ways. Adding them
gives the Muller system: identity terms survive and the operators appear as
**differences**, whose leading singularities cancel. Subtracting them annihilates the
identity terms and leaves **sums**, which reinforce the singularities and produce a
first-kind system with an unbounded hypersingular block.

The code does the second. Every block is a sum, and there is no `I` anywhere: the
operators are built from `average_potentials`, which is exactly the construction that
cancels the `±½` jump terms. That is consistent with the measured `cond(A) ~ 1e11`,
which is what a first-kind hypersingular system looks like, not a second-kind one.

Confidence in implementation ~85%: the derivation is standard and the change is
localized to one assembly function. The residual 15% is sign convention — the code's
normal orientation and RHS construction must be pinned down before the Muller
combination can be written with correct signs, and getting it wrong is silent.

Confidence it helps ~60%: it should collapse the condition number by orders of
magnitude, which is unambiguous. Whether the *accuracy* improves at 2.5 GHz is less
certain, because §5 argues the stand-off error (issue 2) may already dominate there.
Expect a large conditioning win and a modest-to-moderate accuracy win.

### Issue 4b — finite-difference `K'` and `T`. Importance: medium-high.

Detailed in §4b. Reclassified upward from "minor" because it **gates issue 1**: the
Muller cancellation `T_i - T_e` has to be expressed at the kernel level, and it cannot
be while each `T` is a finite difference of separately assembled potentials.

> **Measured 2026-08-24: it does not gate issue 1.** Müller works with the finite
> difference untouched and delivers essentially the whole win that way. 4b's correct
> classification is "medium, independent, worth 1.4–2.4x", and it should have been
> ordered *after* issue 1 rather than before it. See §4b.3.

Confidence in implementation ~90%. The 2D Helmholtz kernels are textbook, both are
written out in §4b, and they reuse arrays already formed in the potential routines.
Roughly 60 lines. It is also unusually testable: the analytic kernel can be checked
against the existing finite difference at a large stand-off, which is a kernel
identity with no solver involved.

Confidence it helps ~55%. The finite difference extrapolates to `t=0`, so it is
partly compensating for the stand-off consistency error rather than merely adding
noise. Variant (B) in §4b may therefore be *worse* on its own. Variant (C) —
analytic kernels plus Richardson extrapolation — is the one expected to win.

The most valuable output here is not the accuracy delta but the `d`-sweep: it
determines whether the current lower bound on `offset_distance` is set by the
quadrature or by the differencing. If it is the differencing, the accuracy valley of
§4 moves and the `d >> h` / `d << λ` bind of §1.1 loosens.

> **Measured 2026-08-24.** The sweep was indeed the valuable output, and the answer was
> neither option offered above: the lower bound was set by the **formulation**. Under
> Müller the valley moves inward by 8–16x for every scheme, and the `d >> h` / `d << λ`
> bind of §1.1 does loosen substantially — but the credit goes to §4, not to §4b.

### Issue 2 — the stand-off trace. Historical outcome: measured and closed.

The dominant measured error, and the one that needs a genuine redesign rather
than more offset tuning.

The first redesign deliberately did **not** implement corrected trapezoidal
volume IBIM end to end. It built the narrower `gpr_bem_kdiff` prototype on the
SDF-derived compressed boundary cloud, formed exterior-minus-interior Müller
kernels analytically, and used a local self-term correction. That experiment
was fast but did not remove the noncircular/high-frequency accuracy floor.
Near-band and full-row QBX follow-ups likewise did not produce a robust,
admissible improvement; see [`qbx_closure.md`](../qbx_closure.md).

The true volume-IBIM route remains research-grade fallback work. The current
implementation target is ordered SDF contours plus Kress/Nyström.

### Issue 7 — non-circular reference. Importance: high, done for smooth analytic shapes.

The single highest-value *decision-making* item, because it bounds whether issue 2 is
worth attempting. If a conventional Kress/Alpert Nystrom solver reaches ~1e-8 at 272
nodes and 2.5 GHz, the redesign is justified and quantified. If it stalls, a rewrite
is avoided. This now exists as `solvers/nystrom_ref/` for circle, ellipse, and
smooth star-shaped boundaries. It is still not a SIREN/implicit-shape oracle.

### Issue 5 — the 2 GHz metric. Importance: low-medium, but nearly free.

`validation.py` already has a mixed metric, but the stored table shows
`mixed = rel = 3.398` at 2.0 GHz — the floor only engages at 8 GHz. A few lines.
Worth doing first purely so the null stops masking real regressions in everything
else on this list.

### Issues 3, 6, 8

3 is no longer the immediate enabler for 2; it is the fallback path if
compressed-boundary kernel differencing fails. 6 should stay open until
`gpr_bem_kdiff` gives it a no-offset control. 8 is downstream of the entire
forward decision and is the largest file in the package; do not touch it until the forward
discretization is final. This includes not "just fixing the failing mod adjoint test":
that test is failing because the adjoint differentiates the old forward operator, and
the new forward operator is still under forward-only evaluation.

## 12.3 Current recommended order (updated 2026-09-01)

1. **Completed controls** — metric floor, direct solve, Müller formulation,
   analytic `K'`/`T`, Nyström, gprMax, perfect sampling, `kernel_diff_ref`,
   kdiff, and QBX are recorded in `validation_change_log.md`.
2. **Ordered geometry** — harden zero-level component extraction, projection,
   orientation, stable component identity, and periodic curve fitting.
3. **Coherent forward solver** — assemble all four analytically differenced
   Müller blocks using per-component Kress/Nyström quadrature and validate it
   independently against `nystrom_ref`.
4. **Adjoint** — derive the complete geometry derivative only after the new
   forward path passes circle/ellipse/star/multicomponent refinement gates.
5. **Corner/panel or true volume-IBIM fallback** — pursue separately if the
   smooth ordered path cannot cover the required geometry.

The next change is item 2 above, not another kdiff diagonal or QBX parameter
sweep.

## 12.4 Historical "done" criteria for completed steps

For **4b**: `cond(A)` unchanged (the formulation has not changed), assembly of the
`K'`/`T` blocks ~3x faster, agreement with the old finite difference at large `d`,
and a `d`-sweep showing whether the small-`d` blow-up was quadrature or differencing.

For **1**: `cond(A)` falling by several orders of magnitude, the hypersingular
difference visibly weaker than either operand, transmission-condition residuals still
satisfied, and the Fourier-Bessel error at 0.5 / 1.5 / 2.5 GHz no worse than the
current 0.10 / 0.24 / 0.15. An accuracy improvement is hoped for but is not the
acceptance criterion; conditioning and structure are.
