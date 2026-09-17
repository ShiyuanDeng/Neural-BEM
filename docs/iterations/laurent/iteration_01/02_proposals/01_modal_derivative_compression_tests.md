# Modal Müller compression: bounded test plan for local agents

**Prepared:** 17 September 2026  
**Project:** `ShiyuanDeng/Neural-BEM`  
**Working checkout:** `/home/drdeng/Neural_SDF_BEM_AD`  
**Working branch:** `feature/ordered-boundary-nystrom`  
**Execution status:** NOT STARTED by the author of this handoff  
**Owner / independent reviewer:** unassigned / unassigned

> **Test whether adaptive retention of modal couplings can preserve both receiver fields and geometry derivatives. Do not begin by writing a new assembler.**

This document turns the main recommendation in *Research Directions for Modal Boundary-Integral Inverse Scattering* into an executable diagnostic. The report's hypothesis and provisional accuracy/retention gates are retained. Projection conventions, mask-consistency rules, concrete controls, budgets, and reporting requirements below are proposed implementation details, not results or theorems supplied by that report. Sources are indexed at the end.

## 1. Placement, authorization, and scope

At the inspected repository state, the active Boundary–BIE exploration is `iteration_05`. Place this proposal at:

```text
docs/iterations/boundary_bie/iteration_05/02_proposals/01_modal_derivative_compression_tests.md
```

Check the live handoff before installation. If the filename is occupied, use the next proposal number; do not overwrite or renumber existing records. Follow `docs/iterations/README.md`: consolidate the reviewed contract into the active cycle's `03_plan.md`; results open the next cycle rather than replacing the executed plan. Do not create fictitious results to fill a folder.

Use working label **`MDC-SCREEN`** until the owner reconciles it with the current experiment-ID register. Record the actual authorization and named ID in the local plan before numerical execution. The Boundary–BIE handoff records a 16 September open-exploration authorization beyond the earlier contracts; check its continuing applicability rather than reinstating the obsolete BIE-006 hold. This handoff itself neither records completed execution nor authorizes production promotion. [P1–P3]

**In scope:** read-only reuse of existing solvers, diagnostic Fourier projection, directional derivatives, protected-part/remainder decomposition where already supported, coupling masks, forward/gradient checks, and honest cost accounting.

**Out of scope:** topology changes, MLP work, material inversion, new physical models, multi-object campaigns, a replacement singular quadrature, a new Laurent assembler, geometry–frequency surrogates, reduced-basis methods, optimizer changes, and default promotion. Existing multi-object/native code remains untouched. A full inverse and a hybrid assembler are later decisions, not automatic follow-ons.

Work on the existing branch and checkout. Do not create branches/worktrees without the user's separate explicit approval. Preserve unrelated work; never reset, clean, or discard changes to obtain a clean tree. One implementation writer at a time. Review can be read-only. No commit/push is implied by this document; follow the user's actual instruction and `AGENTS.md`. [P1–P2]

## 2. Starting evidence: this is not a fresh modal project

Read these records before changing code:

| Recorded evidence | Consequence for this experiment |
|---|---|
| BIE-002 already qualified full-mode coordinate controls, tested trace reduction and centered bands, and stopped the simple projected-field/band prototype. Noncircular fixed-band gates failed. [P4–P5] | Reuse its fixtures, projection checks, manifests, and reporting. A repeat of those bands is a negative control, not the new contribution. |
| BIE-002's sorted-magnitude profiles suggested stronger structure than its prescribed bands, but did not establish an adaptive sparse algorithm or preserved derivatives after truncation. [P5] | The new question is **adaptive/derivative-aware selection, solved accuracy, and its cost**, not another coefficient heatmap. |
| Iteration 05 records a working native Laurent/modal inverse and both operator and reciprocal/Hadamard derivative paths. It explicitly distinguishes the continuous reciprocal formula from the derivative of the finite modal system. [P6] | Do not rebuild the native solver. Use it as a secondary control when it qualifies; distinguish discrete derivative correctness from continuous sensitivity convergence. |
| The recorded nodal reciprocal inverse is faster than the native modal reciprocal inverse on the documented cases; the root README also records a newer compiled/reciprocal production profile. [P6, P8] | Do not demonstrate a speedup only against the old, slower operator-derivative baseline. Include the current qualified nodal reciprocal/compiled path in cost comparisons. |
| BIE-006 stopped first-order geometry-operator reuse at its tested accuracy and cost limits. [P7] | Do not silently append a first-order reuse experiment. The report's joint frequency–geometry alternative is a separate question. |

These are repository documentation claims inspected for this handoff, not newly reproduced measurements. Pin the local source state and establish which claims still apply. Do not rely on the older dashboard's statement that no modal prototype exists; the later Boundary–BIE handoff and iteration-05 records supersede that description. [P3, P6]

## 3. Scientific contract

**Question.** At qualified trace resolution, does a modest set of remainder couplings preserve the full transmission solution, receiver predictions, and the derivative of the actual approximate forward model on noncircular geometries?

**Hypothesis.** Protecting the appropriate structured part and selecting couplings using both forward and directional-derivative information yields a useful accuracy/retention tradeoff beyond BIE-002's centered bands. The hypothesis is empirical here; neither sparsity nor end-to-end speed is assumed. [R1, pp. 5–7, 13–14]

**Intervention.** Change only which couplings of a fixed modal operator are retained. Keep geometry bandwidth, trace bandwidth, physical frequency, materials, acquisition, observation data, and solver tolerances fixed within each paired comparison.

**Controls.** Independently refined Kress; uncompressed projected Kress at the identical trace bandwidth; full-mode coordinate equivalence; forward-only masks; the previously tested centered band; and the existing native/reciprocal paths where qualified.

**Primary deliverable.** A reproducible go/stop/inconclusive decision, including negative cases. A dense matrix with entries zeroed is an accuracy experiment, not automatically an accelerated algorithm.

## 4. Mathematical conventions — preserve these

### 4.1 Geometry, traces, and physical frequency

Use the established parameterization and outward normal:

$$
Z(t;\mathbf c)=x(t)+iy(t)=\sum_{p=-K_\gamma}^{K_\gamma}c_p e^{ipt},
\qquad J(t)=|\gamma'(t)|,\qquad t\in[0,2\pi).
$$

$$
u_D=u|_\Gamma,\qquad u_N=\partial_nu|_\Gamma,\qquad q=Ju_N.
$$

The flux `q` is the parameter-weighted Neumann trace, not an additional independent physical field.

Write the coefficient vector as

$$
\mathbf x=\begin{pmatrix}\widehat{\mathbf u}_D\\\widehat{\mathbf q}\end{pmatrix},
\qquad A_M(\mathbf c,\omega)\mathbf x=\mathbf b_M(\mathbf c,\omega).
$$

Use `K_gamma` for geometry half-bandwidth, `K_u` for trace half-bandwidth, and **`M = 2*K_u + 1` for the number of coefficients per trace in this document**. Record `N` separately for Nyström nodes and `B` separately for any native intermediate coefficient half-bandwidth.

**Naming trap:** iteration-05 native documentation uses examples such as `M=24` to mean 49 modes per trace. Translate that implementation argument to `K_u=24, M=49` in the new output schema. Do not change an existing public API merely to rename it. [P6]

The indices `m,n` are output/input boundary modes. The index `ell` identifies physical frequencies `omega_ell = 2*pi*f_ell`. Solve independently at each physical frequency; share a factorization only across RHS at that same geometry/frequency. Never add different-frequency matrices into one physical solve.

Differentiate with respect to independent **real** geometry coordinates `eta`, obtained from the real/imaginary parts of the applicable Cartesian coefficients. Do not impose `c[-p] = conj(c[p])` on the complex-valued curve `Z`: that is not a general Cartesian-curve constraint. Do not change the geometry chart or apply a fresh gauge/retraction inside derivative probes.

For equal permeability and `Delta = exterior - interior`, the conversational convention is

$$
\mathcal A_q=
\begin{pmatrix}
I-\Delta K & \Delta VJ^{-1}\\
-J\Delta T & I+J\Delta K'J^{-1}
\end{pmatrix},
\qquad
\mathcal A_q\binom{u_D}{q}=
\binom{u_D^{\rm inc}}{J u_N^{\rm inc}}.
$$

Audit signs, normal orientation, material assumptions, and any existing row/unknown scaling against the actual solver. Derive an adapter; do not edit the trusted solver to force superficial notation agreement.

### 4.2 The diagnostic projection must include RHS and receivers

For uniform parameter samples `t_j = 2*pi*j/N`, define

$$
F_{jn}=e^{int_j},\qquad
P=\operatorname{diag}(F,F),\qquad
E=\operatorname{diag}(F^*/N,F^*/N).
$$

Here `*` is conjugate transpose. Provided the retained modes are distinct modulo `N`, `E P = I`. These are physical Fourier coefficients with expansion `sum_n xhat_n exp(i*n*t)`, not unit-normalized coefficients.

If the existing nodal equation uses `(u_D,u_N)`, define

$$
S_q=\operatorname{diag}(I,\operatorname{diag}J),\qquad
A_N^q=S_q A_N S_q^{-1},\quad b_N^q=S_q b_N,\quad C_N^q=C_N S_q^{-1}.
$$

Then use

$$
A_M^{\rm proj}=E A_N^q P,\qquad
b_M=E b_N^q,\qquad C_M=C_N^q P.
$$

`C_N` maps nodal traces to receiver data. Preserve any direct/incident contribution separately and consistently. If the solver already uses `q`, do not apply `S_q` twice. If it uses other scalings, document the complete change of coordinates.

**Do not multiply an already assembled Nyström matrix by another quadrature-weight matrix.** Its source integration weights are already present. The `1/N` above defines Fourier coefficient extraction in `dt/(2*pi)`; an additional arclength weight would change the test space and requires a separately derived mass matrix.

A unitary-DFT implementation is also valid, but all state, RHS, receiver, derivative, and normalization conversions must agree. For the full-mode sanity check on even `N`, use exactly `N` distinct DFT modes, e.g. `-N/2,...,N/2-1`; do not double-count the Nyquist mode. That square control is a coordinate change, not compression.

Keep `P,E` fixed while perturbing geometry at fixed `N,K_u`. Geometry dependence of `J`, RHS, and receiver maps must remain in derivatives. For the uncompressed projected solution also measure the lifted residual

$$
r_N=A_N^qP\mathbf x-b_N^q.
$$

A small projected residual alone is insufficient. `A_M^proj` is a diagnostic/control; do not label it the independently constructed continuous Fourier–Galerkin operator. [R1, pp. 13–16]

### 4.3 Define exactly what is protected and what is compressed

Use a decomposition

$$
A_M=S_M+R_M,\qquad
\widetilde A_M=S_M+\Pi_{\mathcal S}R_M.
$$

The retention set `mathcal S` includes **block labels** as well as `(m,n)`. It retains interactions, not trace unknowns. Keep the same `M` across all masks in a paired test.

Support two explicitly labeled diagnostics:

| Label | Protected part | What it establishes |
|---|---|---|
| `IDENTITY_ONLY` | Exact identity/jump contributions supported by the audited formulation | Compressibility of the remaining **nonidentity operator**. Do not call that entire remainder smooth. |
| `VERIFIED_SINGULAR_SPLIT` | Identity plus an already available, independently verified analytic singular contribution | A more direct test of the report's desingularized-remainder hypothesis. |

Start with available infrastructure. If the existing Kress/native implementation exposes a verified split, reuse it through a read-only adapter and check reconstruction of every block. If obtaining it requires a new hypersingular derivation or substantial solver work, stop that subtask and record `SPLIT_UNAVAILABLE`; do not turn this screen into a new assembler project.

The logarithmic kernel

$$
\ell(\theta)=\log\!\left(4\sin^2\frac{\theta}{2}\right),\qquad
\widehat\ell_0=0,\quad\widehat\ell_h=-1/|h|\;(h\ne0)
$$

has known Fourier coefficients. However, the amplitude in `a(t,tau)*ell(t-tau)` is geometry dependent and generally mixes modes. **Do not replace the complete singular contribution by a universal diagonal.** Its derivative is generally nonzero. The `T` block must use the verified regularized/Maue route, never direct evaluation of the raw diagonal hypersingularity. [R1, pp. 5–7, 14]

A failure of `IDENTITY_ONLY` does not disprove compression after a genuinely different singular split. A success obtained by protecting a large dense `S_M` is not a storage or arithmetic saving unless its cost is included.

## 5. Gate G0 — inspect and freeze the experiment

Before numerical implementation:

1. Read `AGENTS.md`, the live Boundary–BIE handoff, the iteration workflow, and `implementation_principles.md`. Inspect BIE-002 and the latest native/reciprocal records; identify reusable code and saved fixtures.
2. Record the actual commit, dirty status/diff, imported numerical source hashes, environment, thread settings, and any concurrent work. Do not assume the documentation reads were all pinned to one immutable commit.
3. Write an `audit.md` mapping existing functions for geometry evaluation, Kress matrices/blocks, RHS, receivers, reference solves, native modal solves, and both derivative paths. Verify the exact meaning of all returned traces/scalings.
4. Freeze a config, output directory, masks, error gates, and work budget. Explain in a short paragraph what this adds beyond BIE-002. If the answer is only “try centered bands again,” do not dispatch the campaign.

Create a small isolated diagnostic package, for example:

```text
experiments/modal_derivative_compression/
    __init__.py
    adapters.py
    projection.py
    masks.py
    metrics.py
    run_screen.py
    test_algebra.py
    test_derivatives.py
```

These are **proposed new filenames**, not claims that these modules already exist. Prefer reuse over duplication. Shared numerical solver, geometry, inverse, and topology files remain read-only. Do not import a private implementation and then patch it globally at runtime.

## 6. Gate G1 — qualify the oracle and uncompressed modal control

### Case matrix

Use fixed-material, equal-permeability, single-interface full-space TMz physics. The recorded native benchmark uses lossless relative permittivities 6 outside and 3 inside and unit relative permeability; reuse those values unless the local audit identifies a different approved comparison. [P6]

| Geometry | Purpose |
|---|---|
| Circle | Analytic cylindrical-wave sanity and modal indexing/sign checks; never sufficient for a positive research verdict. |
| Ellipse | First noncircular case; reuse BIE-002's fixed Cartesian coefficients. |
| Smooth mixed Laurent curve | Include several positive and negative Laurent modes; reuse the documented mixed-harmonic/native truth or an existing qualified noncircular fixture. Freeze coefficients directly, without radial re-fitting or gauge changes. |

Prefer an already available noncircular fixture over designing a conveniently easy new one. Plot and validate the actual curve, periodic seam, orientation, simplicity, and positive minimum `J`. Known geometry is permitted for a forward diagnostic; it must not select masks using a desired reconstruction outcome.

For the main electrical-size sweep use the report's provisional exterior `k_out*a_ref` values **2, 5, 10**, where `a_ref` is the equivalent-area radius of the **anchor geometry**. Record the resulting frequencies in Hz/GHz and both media's electrical sizes. Hold those physical frequencies fixed during shape perturbations; do not recompute frequency to preserve `ka`. Include 0.5/1.25 GHz checks by reuse of prior evidence or as a small bridge where the budget permits. [R1, p. 13; P6]

Use the existing 24-pair acquisition when feasible. Freeze source/receiver coordinates and strengths; use all RHS at a frequency with one factorization. Declare separate validation illuminations or a rotated receiver/source set, not used to choose masks.

### Refinement and equivalence

Start with `N=128,256`, increasing to `512` only when needed. Start trace half-bandwidth at `K_u=24` and compare with `48` (49 versus 97 coefficients per trace), or begin higher if existing evidence already shows those are insufficient. Always maintain `N > 2*K_u`. Increase `N` and `K_u` independently; cache one nodal matrix for all modal projections that use it.

Before testing coupling masks:

- Verify `E P = I`, identity projection, mode ordering, and complete RHS/receiver conversion.
- At the square full-DFT cutoff, match nodal receiver predictions to relative `1e-10` or better. Reproduce the circle analytic solution.
- Qualify the independently refined nodal receiver reference to relative `1e-8` or better and relevant data directional derivatives to `1e-5` or better.
- Qualify the uncompressed modal control against the refined nodal reference: receiver error at most `1e-7`; lifted, consistently scaled full-system residual at most `1e-7`; non-negligible data directional-derivative error at most `1e-4`.
- Test convergence of the projected matrices at fixed `K_u` when refining `N`; reference finite differences cannot be trusted merely because the primal fields converge.

These control tolerances are proposed safety margins below the report's final gates. If a reference or modal control cannot qualify within budget, mark that case **UNQUALIFIED**, not a compression failure. Do not reduce `M` until it is too small and then blame the retained-coupling rule.

## 7. Gate G2 — establish trustworthy geometry derivatives

### Directions and finite differences

At each noncircular anchor choose four linearly independent training directions spanning low/high admissible Fourier modes and both real coordinate types. Reserve two directions not used to construct the mask; at least one should involve an admissible harmonic outside the training-direction span, where the chart permits. Save all direction coefficients and singular values of their coordinate matrix.

Normalize each direction `v` so the RMS boundary displacement produced by a unit parameter step is `a_ref`. Thus `eta(epsilon)=eta_0+epsilon*v` has a dimensionless relative deformation amplitude. Record the normal component as well: a nearly tangential direction is not a strong physical sensitivity test.

Use centered differences of **independently assembled perturbed geometries**:

$$
D_v A\approx\frac{A(\eta_0+h v)-A(\eta_0-h v)}{2h}.
$$

Begin with `h = 1e-3, 5e-4, 2.5e-4`. Continue downward only if the convergence/roundoff study requires it and budget remains. The chosen `h` must show a stable interval, with an independently refined-`N` check. Apply the same checks to `b`, `C`, and any available split `S,R`. Cache samples; do not rebuild them for each mask or trace cutoff.

Do not use an arbitrarily tiny step, a single-step match, or generic complex-step differentiation through `abs`, normals, conjugations, or a non-holomorphic geometry path. If a probe is inadmissible, reduce the symmetric step or label it unqualified; never substitute a zero derivative.

Where existing analytic derivatives are available, compare them with these finite differences. Add an optional parameter-shift/tangential-null control for **receiver data**, not for `D_v A` itself: reparameterization can change matrix entries while leaving physical data unchanged to first order.

### Differentiate the same approximate model that is solved

Construct a mask at an anchor, then freeze it through derivative checks and paired perturbed solves:

$$
D_v\widetilde A=D_v S+\Pi_{\mathcal S}D_v R.
$$

The same `mathcal S` must be used for the forward matrix and its derivative. Independently keeping entries only in a derivative matrix does not generally yield the derivative of the approximate forward model. Re-thresholding at `eta+h*v` and `eta-h*v` would instead test a piecewise-defined adaptive algorithm; keep that distinct from this fixed-mask check.

With `Y=C x+Y_direct`, compute a tangent using the already factored system:

$$
A\,D_v x=D_v b-(D_v A)x,
$$

$$
D_vY=(D_vC)x+C D_vx+D_vY_{\rm direct}.
$$

Apply the identical formulas to the compressed model. Include the geometry dependence introduced by `J`, sources, and receivers. Do not differentiate only `A` and omit the other terms.

For a fixed observation dataset and fixed whitening/weight operator `W`, define

$$
r=W(Y-Y^{\rm obs}),\qquad L=\tfrac12\|r\|_2^2,
\qquad D_vL=\operatorname{Re}\{r^*W D_vY\}.
$$

An adjoint implementation is equivalent, with

$$
A^*\lambda=C^*W^*r,
$$

$$
D_vL=\operatorname{Re}\{\lambda^*(D_v b-(D_vA)x)
+r^*W[(D_vC)x+D_vY_{\rm direct}]\}.
$$

For multiple RHS/frequencies sum the corresponding real contributions; do not mix physical frequencies in a system solve. Keep regularization absent for the core diagnostic or unchanged and separately reported.

Generate one nearby but distinct synthetic truth per fixture with refined Kress and freeze its observations before testing derivatives. The anchor must not be the exact minimizer: zero-residual gradients are not an informative accuracy test. A small unmodeled shape harmonic is useful when feasible. No noise is needed for this numerical screen; noisy inversion belongs to a later gate.

Require two distinct checks:

1. **Discrete correctness:** compressed tangent/adjoint versus finite differences of the **same frozen-mask compressed objective**.
2. **Physical accuracy:** that compressed derivative versus the qualified uncompressed/refined Kress derivative.

Also evaluate the existing reciprocal/Hadamard derivative using the compressed traces when its assumptions hold. Label this separately: the continuous reciprocity formula is not automatically the derivative of a finite masked matrix. It can converge to the physical sensitivity without satisfying discrete consistency at a coarse cutoff. Both errors matter. [P6]

## 8. Gate G3 — compare retention rules at fixed trace dimension

Use separate masks per physical frequency; cross-frequency reuse is not required. Store masks and hashes. Exclude exact identity terms from the candidate pool but retain and count them in total storage/work.

### Required arms

| Arm | Rule | Role |
|---|---|---|
| `FULL` | No coupling truncation | Same-`M` accuracy control. |
| `BAND` | Existing centered-band rule | BIE-002 negative/control arm; reuse known widths rather than searching endlessly. |
| `FORWARD` | Magnitude-based retention using only `R` | Is derivative information actually needed? |
| `DERIVATIVE_AWARE` | One common mask selected from `R` and training `D_vR` | Main candidate. |

Sweep nominal retained fractions **0.10, 0.20, 0.30, 0.50, 1.00**. A band need not match them exactly; report its actual fraction. Treat allocation across the four blocks explicitly, not as a flattened matrix where the numerically largest block wins by units.

A suitable first derivative-aware score within block `b` is

$$
s_{mn}^{(b)}=
\max\left\{
\frac{|R_{mn}^{(b)}|}{s_R^{(b)}},\;
\max_{v\in\mathcal V_{\rm train}}
\frac{|(D_vR^{(b)})_{mn}|}{s_{D,v}^{(b)}}
\right\},
$$

where the denominators are the relevant block Frobenius norms with declared, reference-noise-based floors. Directions were physically normalized above. Do not amplify a derivative block that is numerically zero into a dominant score. Start with the same retained fraction in each nontrivial block, rank by score, and use deterministic ties. Record any additional protected rows/couplings and charge their union.

This score is a **proposed baseline algorithm**, not a selection law established by the report. A forward-only score with identical normalization, retention accounting, and tie-breaking is the ablation.

Optional post-processing, without new forward assemblies: obtain a best-magnitude tail profile or a mask that also sees held-out derivatives. Label it **ORACLE / TEST-INFORMED**, never the deployed candidate. It diagnoses headroom but cannot certify held-out performance or sparse assembly.

For every retained matrix, solve the actual transmission system and evaluate data and derivatives. Heatmaps, Frobenius tails, and random-vector action errors alone are not acceptance tests. Do not assume Hermitian symmetry or enforce conjugate-symmetric masks unless the audited operator representation proves the required relation.

A useful synthetic algebra unit test is `R(eta)=eta*H` at `eta=0`: the forward remainder is zero but its derivative is not. The derivative-aware construction must not silently discard all sensitivity in this case.

## 9. Gate G4 — held-out checks and resolution robustness

For each candidate that meets training tolerances:

- Evaluate both held-out geometry directions and validation illuminations, with the mask unchanged. Do not select a new threshold after seeing the result and still call it held-out.
- Repeat at approximately doubled trace dimension (`K_u` to `2*K_u`) using independently qualified `N`. Rebuild the anchor mask from training information at the new dimension, then test held-outs again. Report the retained fraction and absolute retained count at both resolutions.
- At the mixed curve and intermediate electrical size, apply the fixed anchor mask at two small, previously unseen geometry offsets, initially RMS displacement `0.005*a_ref` and `0.01*a_ref`. Reassemble exact `S,R` at those geometries, apply the same mask, and test fields/derivatives. This is a local mask-robustness test, **not** an operator surrogate or a claimed reusable inverse step.
- Check normal geometry admissibility at every offset. Separate invalid geometry from a numerical approximation failure.
- Report the worst case and each frequency separately. A pooled error can hide a high-frequency or low-amplitude failure.

A mask derived from four directions is not validated for arbitrary geometry derivatives. State exactly which independent directions and harmonics were covered. Expand derivative coverage only under a later decision, not by silently declaring this screen a full-Jacobian theorem.

## 10. Metrics, tolerances, and decision gates

### Record at every paired point

**Structure:** per-block and total retained fraction; identity/protected-part representation; actual stored values/indices; derivative-support union; coefficient and mode ordering; optional band/off-band profiles.

**Accuracy:** operator-action error on reproducible random vectors, forward solution vectors, and adjoint-relevant vectors; data errors per frequency/RHS; data directional-derivative errors; objective directional derivatives; modal and lifted full-system residuals; condition number/solve-sensitivity estimate in declared scaling.

**Derivative attribution:** finite-difference plateau, reference refinement error, uncompressed modal error, compression-only error, and total compressed-to-reference error. Do not combine these into a single unexplained number.

**Cost:** nodal/native assembly, projection, split extraction, directional-reference construction, mask discovery, protected-part construction/application, remainder storage/application, factorization, RHS solves, receiver evaluation, derivative contractions, validation, and peak memory. Record each factorization and RHS batch; finite-difference primal reassemblies count as work.

Use fixed block/unknown scaling throughout a paired comparison. If scaling depends on geometry, either differentiate it or freeze it explicitly. Canonical `q` should remove the obvious length-unit mismatch between Dirichlet and unweighted Neumann traces; any further equilibration must be documented.

### Provisional numerical gates

| Quantity | Gate |
|---|---|
| Total receiver error against qualified refined Kress | `<= 1e-6` relative on each non-negligible frequency/RHS group. |
| Data directional-derivative error | `<= 1e-3` relative, target `1e-4`; report every non-negligible held-out direction. |
| Objective directional-derivative error | `<= 1e-3` relative, target `1e-4`, with the cancellation-aware absolute allowance below. |
| Lifted residual in the qualified, fixed scaled full nodal system | `<= 1e-6`; also report the uncompressed modal residual. |
| Research retention target | Approximately `<= 0.30` of candidate remainder couplings, including the derivative-support union. |
| Refinement stability | Accuracy remains qualified when trace dimension is approximately doubled; retained fraction must not rapidly approach one. |

The field/gradient/retention targets are from the report; the explicit residual check carries forward BIE-002's warning about apparently accurate receiver fields. The additional safety margins and practical rules here are proposed experiment details, not universal physical tolerances. [R1, p. 14; P5]

For an objective derivative close to zero, do not divide by an arbitrary machine epsilon. Save absolute error and use

$$
|\widetilde g_v-g_v|\le 10^{-3}|g_v|+10^{-6}s_v,
\qquad s_v=\|r_{\rm ref}\|_2\,\|W D_vY_{\rm ref}\|_2.
$$

Report whether the relative or cancellation-aware term controlled the decision, along with the derivative sign when significant. For near-zero fields/data derivatives, declare an analogous absolute scale based on the fixed experiment's signal/reference accuracy before inspecting masks.

The oracle's uncertainty must be well below the intended approximation tolerance. Do not use a poorly resolved oracle to create an apparently small error, and do not require the approximation error to be smaller than roundoff-level oracle differences. Keep reference uncertainty, allowed numerical approximation, and inversion/noise budget distinct.

### Verdict vocabulary

**`GO_HYBRID_FEASIBILITY`** — adaptive common masks meet receiver, derivative, residual, and refinement gates on both noncircular fixtures at the intended intermediate/moderate electrical sizes, with roughly 30% or lower remainder retention. Identify whether a verified singular split was used. This authorizes a recommendation for a separate hybrid-assembler prototype, not a speed or inverse-method claim.

**`STRUCTURE_ONLY`** — oracle/training masks look promising but held-outs, protected-part cost, mask-discovery cost, or full-system residuals prevent a practical conclusion. State the one missing mechanism. Do not hide dense preprocessing behind an “online” number.

**`STOP_TESTED_COMPRESSION`** — the tested adaptive representation needs more than roughly half the candidate interactions at relevant moderate electrical size, derivatives destroy the saving, or retention deteriorates sharply with refinement. Preserve that negative result and its scope. Failure without a verified singular split does not refute every desingularized/modal method. [R1, p. 14]

**`INCONCLUSIVE_REFERENCE_OR_BUDGET`** — reference, derivative, trace, decomposition, or compute qualification failed. Do not convert missing evidence into a scientific no-go or a success.

Compare `FORWARD` and `DERIVATIVE_AWARE` directly. If forward-only selection already meets all derivative gates at the same or lower cost, report that the tested cases do **not** demonstrate an advantage from derivative-aware selection.

## 11. Runtime interpretation — do not optimize the wrong baseline

For the diagnostic, conventional dense factorization is acceptable. It isolates approximation quality; zeroing entries does not reduce dense LU complexity. [R1, pp. 5, 7]

Measure two separate questions:

1. **Does the representation preserve the required quantities with fewer couplings?**
2. **Can obtaining and using those couplings beat the current qualified implementation?**

Constructing all dense entries and all directional derivatives before selecting a mask addresses the first question. It does not establish a faster assembler. Include its actual preparation cost and label any later sparse-assembly benefit as unimplemented.

If a protected singular part stays dense, count it. If it is stored/applied through coefficients, report that representation's measured storage, convolution bandwidth, and action time. Do not quote only the remainder's retained fraction as the total algorithmic reduction.

Benchmark against accuracy-matched **current nodal Kress with its qualified reciprocal/compiled derivative path**, and optionally against uncompressed native modal. A comparison against nodal operator derivatives is a historical control only. The current reciprocal path can avoid assembling `D_vA` for every shape direction, so compressed derivative-matrix construction must earn its cost rather than assume that bottleneck still exists. [P6, P8]

Use one worker and single-thread BLAS/OpenMP for controlled timing, fixed warm-up policy, three paired repeats in alternating order, and report ranges. Record compilation/JIT both cold and amortized where applicable. Do not call a sequential run “isolated” unless host-wide isolation was actually checked.

No speed criterion is required to report a positive **structure** result. But a speed claim requires measured end-to-end savings at matched field and derivative quality, including mask discovery and validation. A break-even estimate may be reported only with measured preparation and per-use costs; it is not an observed acceleration.

## 12. Bounded execution and suggested commands

Start with a pilot: circle algebra/analytic checks, then the ellipse and mixed curve at the intermediate electrical size. Establish reference and derivative validity before the full three-size sweep. Reuse matrices across all masks and both trace cutoffs.

**Proposed numerical budget for this screen:** 45 minutes numerical wall time, 8 GiB peak RSS, at most 500 new full physical assemblies (including derivative primal rebuilds), 1,200 factorizations, and 2,500 RHS batches. Record RHS columns as well as batches. Source-audit and implementation time are separate; never use that distinction to hide numerical runs. These caps are engineering proposals, not numbers in the report.

Reserve work before dispatch so a batch cannot silently overshoot. Stop early on broken equivalence, inconsistent derivatives, source drift, or numerical instability. On a cap, checkpoint and issue `INCONCLUSIVE_REFERENCE_OR_BUDGET`; do not silently discard difficult cases, change tolerances, or launch a larger campaign.

Existing environment guidance is documented in iteration 05. A setup/check sequence is:

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
git status --short
git branch --show-current
git rev-parse HEAD

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
# Activate the project's existing environment; do not install/upgrade packages blindly.
```

The following is the **requested interface to implement**, not an existing command claimed to work now:

```bash
python -m pytest -q experiments/modal_derivative_compression/test_algebra.py \
  experiments/modal_derivative_compression/test_derivatives.py

python -m experiments.modal_derivative_compression.run_screen \
  --config <frozen-config.json> --stage pilot --output <fresh-pilot-directory>

python -m experiments.modal_derivative_compression.run_screen \
  --config <same-frozen-config.json> --stage campaign --resume <pilot-manifest> \
  --output <fresh-campaign-directory>
```

The runner must print actual resolved parameters, expose a dry-run/work estimate, checkpoint safely, and refuse incompatible resumes. Include a source-hash check before/after numerical work. If imported solver files drift, stop and keep prior results tagged with their original snapshot rather than blending them.

## 13. Required artifacts and independent review

Use a fresh directory under:

```text
results/validation/boundary_bie/<registered-id>-<timestamp>-modal-derivative-compression/
```

Required outputs:

```text
README.md                 # decision, decisive evidence, limitations, next decision
manifest.json             # source hashes, environment, geometry, acquisition, seeds
config.json               # frozen tolerances, directions, masks, grids, budgets
audit.md                  # API/scaling/sign mapping and difference from BIE-002
reference_convergence.csv # N, K_u, oracle/trace qualification
fd_convergence.csv        # steps, refinements, tangent and objective checks
compression.csv           # all arms, all masks, all failures; no best-only reporting
heldout.csv               # unused directions/illuminations and local-offset checks
timings.csv               # full ledger, controlled repeats, preparation included
summary.json              # machine-readable per-case gates and overall verdict
commands.md               # exact commands actually executed
review.md                 # independent review, or explicit 'self-review only'
```

Save masks, coefficient directions, and sufficient numeric arrays to reproduce checks locally; follow the repository's tracked-binary policy rather than forcing large dumps into Git. Produce a small number of plots: blockwise forward/derivative magnitudes, error versus retention, and retention versus trace resolution. Label every axis with modes, units, and block identity. Keep failures and invalid probes visible.

The reviewer must answer:

- Was this genuinely adaptive/derivative-aware, rather than BIE-002's band experiment repeated?
- Were `q`, Fourier normalization, RHS, receivers, signs, and all geometry dependencies handled consistently?
- Did derivatives differentiate the same frozen-mask model, and was the continuous reciprocal check labeled separately?
- Were noncircular, held-out, and refined-resolution cases qualified without changing gates after results?
- Was the protected singular part actually verified, or merely the identity, and were all costs counted?
- Does any speed claim survive comparison with the current nodal reciprocal/compiled baseline?

End the report with one recommendation: proceed to a separately scoped hybrid prototype, stop the tested rule, or run one precisely named unresolved diagnostic. Do not produce another unconstrained menu or automatically dispatch a successor.

## 14. Conditional later work — document, do not execute here

After a positive screen, the report's proposed order is a true hybrid Fourier–Galerkin `V` block, then `K/K'`, then regularized `T`, followed by the full Müller system, derivative checks, and one modest matched inverse. Independently refine the hybrid and Kress discretizations; the projected Nyström matrix remains a control. [R1, pp. 14–16]

That later inverse should use refined independent synthetic data, unchanged optimizer/data access, a small active geometry set, several illuminations, and roughly 8–16 frequencies, with geometry error, residuals, accepted steps, gradient checks, memory, and total cost. It must compare against the current qualified baseline, not simply the slowest historical derivative arm. [R1, pp. 15–16; P6]

Frequency–geometry surrogates and reduced bases remain separate later experiments. The report's figure on page 17 places the modal/derivative structure diagnostic before a new hybrid assembler, and conditions further coefficient-only investment on the measured cost of physical-space remainder processing. Existing Laurent work is preserved; this plan neither erases it nor treats it as an unbuilt dependency.

## Sources and provenance

**[R1] Supplied research report.** *Research Directions for Modal Boundary-Integral Inverse Scattering*, 20-page PDF supplied to this conversation. Main mechanism: pp. 5–7. Decisive modal diagnostic and provisional gates: pp. 13–14. Inverse validation and staged path: pp. 15–17. Its novelty assessments remain the report's qualified literature-search inferences, not independently verified priority claims in this handoff.

**[P1] Repository workflow preferences.** `AGENTS.md`, read from `feature/ordered-boundary-nystrom` on 17 September 2026. Retrieved file blob: `f49313fbdaa96dcd90553a9b720d60c82e55dbc5`.

**[P2] Iteration workflow.** `docs/iterations/README.md`, same branch/date. Retrieved file blob: `70a7b66a9098ef131cb1fb749987ef0ca3ef1007`. Also read `docs/iterations/implementation_principles.md` locally before execution; its contents were not separately inspected for this handoff.

**[P3] Current Boundary–BIE handoff.** `docs/iterations/boundary_bie/README.md`, same branch/date. Retrieved file blob: `5349f88014ea87e26f8f2e5221a6cd7c6b71bfff`. Its 16–17 September updates distinguish later exploration from older BIE-006 holds.

**[P4] BIE-002 closeout.** `docs/iterations/boundary_bie/iteration_02/01_results.md`. Retrieved file blob: `7a98ed8cc851be998a5f88b2890e4d597219c375`.

**[P5] BIE-002 numerical report.** `results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md`. Retrieved file blob: `965733b83390b5c3aae960915744d8abf4ffc7eb`. This report links reusable configurations, coefficients, commands, and the original numerical ledger.

**[P6] Native modal/reciprocal baseline.** `docs/iterations/boundary_bie/iteration_05/01_exploration.md`. Retrieved file blob: `e7b911fe4c1ff539b9ed7071fc7f3ed75c6f9a39`. Its later linked coupled/library/deformable-scattering records should be checked locally if relevant; no new performance assertions from those unread follow-ups are assumed here.

**[P7] Negative first-order reuse evidence.** `docs/iterations/boundary_bie/iteration_04/01_results.md`. Retrieved file blob: `87e6b60aa5769f54ef33e8af4f1f48ef9994edc5`.

**[P8] Current production runtime description.** Repository root `README.md`, lines 1–180 inspected on the same branch/date. Retrieved file blob: `69b2f78d9f32f30f8325c0ea65845350c717404b`. This identifies the compiled Kress/guarded reciprocal/training-readiness profile and its reference-mode fallback; qualify the applicable single-interface path locally rather than assuming every compiled fast path applies.

**Source boundary:** report-derived priorities/gates, repository-recorded evidence, and this handoff's proposed engineering details are intentionally distinguished. No diagnostic was executed and no solver change or GitHub write was made while preparing this file.
