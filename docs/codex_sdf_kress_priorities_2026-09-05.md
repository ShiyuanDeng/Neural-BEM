# SDF → Fourier boundary → Kress: repairs and selected experiments

**Date:** 2026-09-05  
**Purpose:** Codex implementation brief, revised after the inverse-pipeline review.  
**Evidence status:** Based on the uploaded project reports, not an independent inspection or execution of the repository. Verify the actual working tree before changing it. Proposed experiments below have not been run.

## 1. Decision and execution scope

Keep the validated explicit-curve inverse as the control. Do not add machinery merely to justify keeping an SDF. First remove avoidable coupling between reconstruction and representation, then test whether a better parameterization makes the implicit-to-Fourier conversion more efficient.

**First implementation batch:** implement Tasks A and B, and run the bounded parameterization experiment in Task C. Preserve existing defaults and historical results; expose the new behavior through an explicit experiment profile. Do not simultaneously replace the optimizer, extraction algorithm, and quadrature.

**Next milestones:** Task D is the small material-inversion extension; Task E is the numerical foundation for genuine neural shape updates. They are separate work packages, not requirements for completing the first batch. Tasks F–H are gated research branches, not authorization to implement everything now.

| Priority | Work | Question it answers |
|---|---|---|
| A — first | Separate reconstruction from SDF distillation/export | What does the neural representation cost, and when should it be allowed to block a result? |
| B — first | Supervise distance to the smooth canonical curve | Are we training the network to represent the wrong, polygonal geometry? |
| C — first experiment | Parameterization-aware Fourier fitting | Are we spending modes on parameter labels rather than geometry? |
| D — next, practical | Recover one interior `epsr` | Can the inverse distinguish material changes from shape changes? |
| E — next, enabling | Verify the complete discrete Kress geometry derivative | Can a proposed geometry update be differentiated through the actual solved objective? |
| F — gated | Neural-induced normal updates against explicit-curve controls | Does a neural update rule add anything beyond a smooth boundary optimizer? |
| G — gated | Fourier singularity swapping for close evaluation | Can analytical harmonic integration extend the supported separation regime? |
| H — later | Tangency-aware extraction; data-driven topology | Can an implicit representation provide a measurable extraction or search advantage? |

Adapt implementation details to existing modules. Reuse the continuous/sample geometry contracts and solver adapters rather than creating parallel class hierarchies.

## 2. Evidence and corrections to the previous advice

### What the project sources establish

The latest review reports an authoritative, single-component, star-shaped radial Fourier inverse with eleven geometric controls at radial bandwidth `K=5`. The MLP is fitted to accepted curves; its weights do not independently supply the next production geometry Jacobian. However, its representation checks **can veto updates or prevent convergence**, so it is not merely a passive audit. [S1]

For the saved ellipse-to-star run, canonical training/held-out-frequency relative field errors were `1.068e-8` and `1.339e-8`; errors through the extracted MLP were `0.005085` and `0.004327`. MLP/canonical curve-set drift was `0.329 mm`, above the `0.2 mm` representation gate. Re-distancing plus geometry audits used approximately 66% of the recorded inverse time. These are reported measurements, not newly reproduced results and not a measured curve-only speedup. [S1]

The multi-component forward adapter already accepts an `OrderedBoundary2D` directly. It discovers/fits independent loops from an implicit field, but its current inverse counterpart is not a topology-changing optimizer. Its supported components are disjoint, non-nested, sufficiently separated, and share one lossless nonmagnetic interior material. [S2]

The earlier A/B/C study supports Method B as the current economical baseline. The isolated logarithmic Kress proxy can converge to roundoff on a Fourier curve while that curve still has appreciable geometry error. That proxy is not a validation of all Müller blocks or an inverse gradient. [S3, S4]

### How this changes the recommendations

1. **Fix representation ownership before pursuing new extraction.** Increasing MLP capacity will not enlarge the authoritative radial chart. Changing that ownership by simply feeding its approximate contour back into the optimizer would undo the canonical-state repair. [S1]
2. **Move singularity swapping below the immediate representation work.** It remains the closest practical relative of the harmonic-integration idea, but close evaluation is a currently excluded regime, not an established cause of the saved reconstruction/representation discrepancy. [S1, S2]
3. **Do not claim that off-boundary distances add measured physics.** Tangent-circle constraints can make better use of sampled distance data. When those data were distilled from the same canonical curve, they are not independent geometric observations. [S1; proposed interpretation]
4. **Do not mistake a parameter gradient for a normal shape-gradient density.** Eleven coefficient derivatives do not uniquely determine an arbitrary function on the boundary. Any recovery of such a function needs an explicitly declared basis/metric. See Task E.
5. **Non-star-shaped and multi-component geometry are not exclusive SDF capabilities.** General Cartesian Fourier loops and explicit component proposals are necessary controls for a fair SDF comparison. A prescribed split is not data-driven object-count recovery. [S1, S2; proposed comparison]

### Repairs already reported as done

Do not blindly reimplement these: valid one-sided FD probes, missing-column/stationarity handling, projected-bound convergence, negative-inside orientation checks, initialization audits, radial-to-Cartesian bandwidth accounting (`K+1` for the current finite radial series), and expanded observation/material provenance. Inspect the working tree and retain/add regression coverage. Preserve uncommitted changes. [S1]

## 3. Task A — make distillation policy explicit

### Required behavior

Keep one authoritative reconstruction state and add explicit policies with the following semantics; the names are suggestions, not mandated APIs.

| Policy | During reconstruction | At completion |
|---|---|---|
| `legacy_strict` | Preserve current distillation, representation vetoes, and stop semantics | Preserve current behavior |
| `curve_only` | No neural training or neural representation veto | Return the canonical reconstruction; SDF export is not requested |
| `export_only` | Optimize exactly the canonical curve objective | Train and audit an SDF against the final accepted continuous curve |

An optional diagnostic-audit policy may be added later. Do not introduce an asynchronous training system or an elaborate scheduler for this task.

When initialization actually comes from an SDF, still extract and validate it. A supplied canonical curve alone must not be described as a verified MLP contour. In curve-only mode, an absent neural audit is **not applicable**, not zero drift. In strict mode, preserve the initialization repair in the review. [S1]

Store reconstruction and representation results separately: reconstruction status/reason, export status/reason, whether a representation was evaluated, canonical field errors, extracted-representation field errors, and drift. Retain backward compatibility through an explicit schema/version or documented mapping. Never reinterpret old `converged=false` artifacts retroactively.

An export failure must preserve the valid reconstructed curve. The overall requested delivery may still be incomplete when an SDF was required; report that without calling the reconstruction a failure or the export a success.

### Ablation and acceptance gates

Use identical immutable observations, initial canonical coefficients, material values, solver tolerances, parameter scaling, and random seeds where applicable.

First use a short deterministic run. Instrument neural training, SDF value/gradient calls, extraction, audits, forward solves, and optimizer evaluations. Then compare the saved benchmark configuration in a fresh result directory.

`curve_only` and the reconstruction phase of `export_only` should follow the same accepted canonical trajectory within declared deterministic tolerances. Export must not mutate it. Neither mode should train an MLP during reconstruction. A strict run may diverge because its vetoes differ; log those divergences rather than assuming identical paths.

Measure reconstruction time, export time, and end-to-end time separately. Include any changed line-search work. Do not convert the reported 66% cost share into a claimed speedup without running the ablation. Do not disable canonical geometry validity, physical admissibility, or solver-readiness checks to save time.

## 4. Task B — train against the smooth curve, not the solver polygon

### Target definition

For a regular simple continuous canonical curve `gamma(t)`, define

\[
d_\Gamma(x)=s_\Gamma(x)\min_{t\in[0,2\pi)}\|x-\gamma(t)\|,
\]

where `s_Gamma` is negative inside and positive outside. Solver node count, distance-target accuracy, extraction resolution, and representation-audit resolution must be independently configurable.

The review reports that current re-distancing targets the polygon through solver nodes. For a circle, chord error at edge midpoints is

\[
r\,[1-\cos(\pi/N)].
\]

At `r=65 mm`, this is about `0.313 mm` for `N=32`, but only about `0.0196 mm` for `N=128`. The latter is a scale illustration, not an explanation of the reported star-run drift: shape, spacing, fit error, training error, and audit error all differ. [S1; circle calculation]

### Implementation choices

Prefer an existing continuous closest-point routine if one is reliable. Otherwise use dense periodic candidate localization followed by safeguarded closest-point refinement, considering multiple candidates on concave curves. A stationary point satisfies

\[
(\gamma(t)-x)\cdot\gamma'(t)=0,
\]

but stationarity alone does not establish the global minimum. Sign determination and completeness of the search need their own tests. Report numerical refinement agreement rather than claiming a certificate that the algorithm does not provide.

An adaptively refined polygon is an acceptable intermediate implementation only when its continuous-curve error is controlled independently of BEM nodes. Nearest-vertex distance is not point-to-segment or smooth-curve distance. Changing BEM `N` must not silently change the supervised shape.

**A useful low-cost variant to try:** generate near-boundary targets from smooth normal offsets,

\[
x=\gamma(t)+s\,n(t),\qquad d_\Gamma(x)=s.
\]

This identity requires the offset point to retain `gamma(t)` as its unique closest boundary point. Restrict offsets to a validated tubular neighborhood and check them with the distance routine. A curvature bound alone does not exclude another nearby branch. Retain global/sign coverage so correct local supervision does not conceal extra zero-set components. This is a proposed supervision strategy, not new measurement information.

### Diagnostic experiment

Freeze one canonical circle and one noncircular canonical curve before comparing target policies. Keep network architecture, sample locations, initialization, optimization budget, and extraction/audit settings fixed. Compare the existing polygon targets with continuous-curve targets; test normal-offset sampling separately so sampling and target accuracy are not confounded.

Report separately:

- target-distance approximation error before any network training;
- trained field error on independent distance/sign samples;
- extracted zero-set drift and topology against the canonical curve;
- extraction/Fourier-fitting refinement error for the frozen trained field;
- canonical and re-extracted field predictions at converged solver resolution.

Use independent, converged set-distance comparisons rather than a phase-dependent nearest-sample floor. Audit inside/outside sign and all detected components, not just the main contour.

Declare the target-distance tolerance before the experiment; for example, make it at most one tenth of the requested representation tolerance, then tighten it to verify stability. This is an accuracy budget, not a guarantee that the network will attain that tolerance. A negative result—targets improve but neural drift does not—is useful evidence against attributing the floor to polygonization.

## 5. Task C — the first research experiment: parameterization-aware fitting

### Hypothesis

Some Fourier bandwidth is spent representing the chosen parameterization rather than the geometric set. Test this before implementing a new global extractor or another general Method-C loss.

For an ellipse,

\[
\gamma(t)=(a\cos t,b\sin t)
\]

has Cartesian bandwidth one. Its speed is generally nonconstant, so constant-speed reparameterization changes the coordinate spectrum. This does **not** prove that the nonuniform-speed version needs fewer BEM nodes: density and kernel resolution also matter. The current Method-B arc-length refit is a sensible default, not a correctness error. [S3; direct mathematical observation]

Zhao–Serkh provide relevant intuition by jointly treating speed and tangent-angle representations in bandlimited fitting. Our initial experiment is a simpler ablation, not an implementation or claimed reproduction of their algorithm. [R1]

### Two comparisons, kept separate

**C1 — pure parameterization control.** Use the same analytic ellipse in native-angle and accurately evaluated arc-length parameters, without a finite-bandwidth refit changing the geometric set. Both satisfy the continuous geometry contract. Compare frozen-geometry Kress convergence and spectra. This isolates parameterization from fitting error.

**C2 — actual implicit-to-Fourier conversion.** Freeze the same projected ordered points for all arms:

- existing Method B with its arc-length refit;
- the same initial Fourier fit without the final arc-length refit;
- an experimental fit that adjusts ordered sample parameters as well as Fourier coefficients.

The second arm still inherits chord-length parameter labels; merely skipping the refit does not discover the native ellipse angle. Do not label it an optimal-parameter method.

A minimal third-arm objective is

\[
\min_{c,\{t_i\}}
\sum_i\omega_i\|\gamma_c(t_i)-p_i\|^2
+\lambda\sum_{k=1}^{K}k^{2q}\|c_k\|^2,
\]

with cyclic order, a phase gauge, and nondegeneracy constraints. Here `p_i` are the frozen projected points, `c` contains Cartesian Fourier coefficients, `omega_i` are fixed fitting weights, and `q` specifies a declared spectral penalty. Use unregularized controls and disclose parameter-dependent regularization; do not present different penalties as the same shape prior.

One possible parameterization uses positive cyclic increments whose sum is `2*pi`. That prevents reordered labels but does not by itself guarantee a simple curve or positive continuous speed. Retain independent topology, speed, setwise-fidelity, and conditioning checks. Closest-point updates must not silently jump to the wrong branch.

Use a new experimental label; do not change the historical meaning of Methods A/B/C. Preserve a valid baseline fallback and report its use.

### Cases, metrics, and decision

Start with a circle, a moderately eccentric rotated ellipse, and the existing smooth star. Then add a known simple non-star-shaped analytic reference. The latter tests general Cartesian curves; do not force it through the radial inverse chart. Use the same extraction data for fitting comparisons.

Sweep geometry bandwidth separately from BEM node count. For every accepted continuous curve, freeze it while refining even `N`. Record geometry/set error, normals and derivative accuracy, minimum speed and speed ratio, coordinate and derivative-weighted spectral tails, fit time, conditioning, and forward field error. Compare densities only after transferring them to a common physical parameter; raw nodal vectors from different parameterizations are not directly comparable.

Use circle analytics where applicable and a separately converged existing oracle otherwise. The old scalar log proxy is a useful unit test but is not the only performance target.

**Decision gate:** retain the experimental fit only when it attains the same declared geometry and field accuracy with less total work, or a demonstrably lower usable bandwidth without unacceptable quadrature/conditioning cost. A compact coordinate spectrum alone is not a win. An exact ellipse parameterization is an intuition control, not evidence of broad superiority.

Do not yet optimize an expensive solver-aware parameterization objective. First determine whether this inexpensive geometry-level experiment produces a meaningful tradeoff.

## 6. Task D — one unknown material parameter

This is a practical inverse extension recommended by the review, not a novelty claim. It can use the existing validated parameter-FD path and need not wait for a shape adjoint. [S1]

Start with fixed geometry and estimate one interior relative permittivity, `epsr_in`, with fixed exterior, known sources, and current lossless nonmagnetic physics. Use explicit physical bounds and scaled real parameters. Then test joint radial shape plus material inversion in a separate experiment.

Changing candidate material must rebuild all affected predictions, including the interior wavenumber, operator differences, and analytic diagonal terms. Include candidate material, geometry, acquisition/frequency identity, numerical configuration, and source calibration in appropriate cache keys. Never regenerate observations from the candidate parameters.

Validate fixed-circle material predictions and sensitivities against independent Mie data. Test fixed-shape recovery from several material starts, then joint shape/material starts. Add reproducible complex noise and unseen acquisition angles. Inspect singular values and column correlations of the **scaled, weighted real-stacked residual Jacobian**; report material and geometry errors as well as field error.

No automatic claim of identifiability is warranted. Joint shape/material compensation may remain even with small field error. Conductivity, separate materials per component, nested interfaces, and full 3-D are outside this task.

## 7. Task E — verify the derivative of the actual Kress objective

### Scope and mathematical contract

Implement and test a directional derivative/JVP before building a new neural optimizer. Use fixed topology, fixed even node counts, fixed correspondence, fixed paired acquisition selection, and a declared real parameter vector `p`. Recompute all geometry-dependent arrays on a perturbed curve; do not freeze normals or arc weights as in the legacy surrogate. [S1]

The following is algebraic bookkeeping, not a replacement for the repository's Green-function or Müller sign conventions. For one frequency, write

\[
A(p)U(p)=B(p),\qquad
z(p)=P\,\operatorname{vec}(C(p)U(p)+D(p)).
\]

`U` stacks the existing Dirichlet/Neumann boundary unknowns, with columns for right-hand sides; `B` contains incident traces; `C` is the receiver evaluation map; `D` is any direct contribution in the selected observable; and `P` implements the actual paired observation selection. For a direction `dot p`,

\[
\dot U=A^{-1}(\dot B-\dot A U),\qquad
\dot z=P\,\operatorname{vec}(\dot C U+C\dot U+\dot D).
\]

Include every dependence actually present: point positions, derivative jets, speeds, outward normals, curvature where used, target and source derivatives, singular-split factors, analytic diagonals, source weights, RHS, receiver map, and material dependence for material directions. Do not differentiate an unused idealized formula while production uses another stabilized implementation.

**Useful distinction:** at fixed `N` and uniform computational parameters, universal Kress logarithmic product weights are geometry-independent. Their geometry derivative is zero. Arc factors and geometry-dependent smooth/singular factors are not constant. Likewise, fixed observation selection has `dot P=0`, but `P` and its adjoint must still be applied correctly.

For the real objective

\[
J=\tfrac12\|L_r(z-y)\|_2^2+\mathcal R(p),
\]

`L_r` is a fixed residual-weighting/whitening map and `y` is immutable measured data. Define

\[
Q=\operatorname{unvec}\big(P^*L_r^*L_r(z-y)\big),
\qquad A^H\Lambda=C^H Q.
\]

Then

\[
\dot J=\operatorname{Re}\left[
\langle Q,\dot C U+\dot D\rangle_F+
\langle\Lambda,\dot B-\dot A U\rangle_F
\right]+\dot{\mathcal R},
\]

where `H`/`*` denote conjugate adjoints and `⟨X,Y⟩_F = tr(X^H Y)`. Sum contributions over frequencies. This is a direct derivation from the discrete system; choose AD, analytic derivatives, or a combination to match existing code.

Do not accidentally double arc factors, use a transpose instead of a conjugate transpose, drop complex source phases, discard the imaginary residual, or replace paired measurements with the full receiver/source Cartesian product. Repeated selections must accumulate under `P*`, not overwrite.

### Validation ladder

First test coherent finite-bandwidth coefficient directions: translations, radius/scale, and nontrivial shape modes. Add material directions and multiple complex-strength sources. Test the raw complex prediction derivative as well as the real objective derivative; objective-only checks near a perfect fit are uninformative.

Sweep central-FD steps in scaled real parameters over several decades, and repeat at `N`, `2N`, and `4N` on each frozen continuous curve. Seek the expected central-difference convergence region before cancellation/solve error dominates. Use declared absolute-plus-relative tolerances for nearly zero derivatives. Standard complex-step differentiation is not an independent oracle for a nonholomorphic squared complex residual.

Add adjoint/JVP dot-product tests. Keep discrete correctness at fixed `N` separate from convergence toward a continuous shape derivative. Include bound/invalid-probe tests preserving the repairs already reported. A derivative that differentiates only `A` is insufficient when `B` or `C` also vary.

During one check, do not adapt `N`, refit/rephase the curve, reorder components, or cross a topology/clearance threshold. Such operations can be tested separately as accepted-update transformations. Tangential reparameterization may have a nonzero finite-discretization effect; verify its decay with refinement rather than forcing it to zero by construction.

### Normal density versus coefficient gradient

The continuous normal density is defined by

\[
\delta J=\int_\Gamma g_n h\,ds,\qquad h=\delta x\cdot n.
\]

A discrete derivative might instead be an already weighted covector with respect to nodal normal displacements, or a covector with respect to Fourier coefficients. Document which object is returned. A coefficient gradient cannot simply be divided by nodal arc weights and called `g_n`.

For a declared normal-displacement basis `b_l`, coefficient derivatives satisfy

\[
\frac{\partial J}{\partial a_l}=\int_\Gamma g_n b_l\,ds.
\]

Recovering a projected `g_n` requires a stated mass-matrix/Riesz map in that basis. Alternatively, retain the covector and apply the appropriate update Jacobian directly. Do not infer an arbitrary boundary function uniquely from the eleven current controls.

## 8. Task F — a genuine neural-update experiment, only after E

For a regular negative-inside implicit field `phi_theta`, the first-order normal displacement is

\[
h=-\frac{\partial_\theta\phi\,\delta\theta}{\|\nabla\phi\|}.
\]

Thus a verified normal density would induce

\[
\frac{dJ}{d\theta}
=-\int_\Gamma g_n\frac{\partial_\theta\phi}{\|\nabla\phi\|}\,ds.
\]

Use arc weights exactly once, in accordance with the gradient contract in E. This identity assumes a regular zero set. It neither differentiates a discrete topology event nor proves that the finite-bandwidth extracted curve follows that displacement. [S1; R2 motivates the flow/parameter-update distinction]

A safe first experiment is to use the neural parameter-to-normal map as an update metric on the authoritative smooth curve. With

\[
B_\theta(x)=-\frac{\partial_\theta\phi(x)}{\|\nabla\phi(x)\|},
\]

Euclidean parameter descent induces the formal normal velocity

\[
V_n(x)=-\int_\Gamma B_\theta(x)B_\theta(y)^T g_n(y)\,ds_y.
\]

This follows by the chain rule. It suggests a test of the neural **update coupling**, not evidence that off-interface distances contain extra physics. Label this branch accurately: a neural-metric curve update is not yet end-to-end optimization of a re-extracted neural zero set.

Compare it with direct normal/Fourier updates and an explicit smooth boundary metric, using comparable regularization and accepted forward-objective checks. Otherwise a gain could be caused simply by smoothing or parameter scaling.

A later direct-SDF branch must test actual weight perturbation → extraction → fit → prediction against the proposed derivative. Quantify normal-motion transfer error, field drift, and refinement dependence. Keep fixed topology and small valid steps initially. The canonical-state branch remains the control; do not silently substitute an approximate MLP curve into it.

## 9. Task G — analytical Fourier integration for close targets

**Keep this idea, but stage it as a separate forward experiment.** Periodic singularity swapping moves a target singularity into complex parameter space and integrates the difficult factor against Fourier modes. This is a concrete relative of the user's harmonic-integration idea, not a formula that analytically diagonalizes the complete Helmholtz operator. [R3]

The current adapter rejects near-touching components. Do not weaken that safety gate globally to run this experiment. Use an explicit experimental backend with its own supported domain and failure states. [S2]

Start with manufactured log/Cauchy-type potential evaluations on a frozen circle and ellipse, with targets on both sides approaching the boundary. Then address the actual Helmholtz receiver operators and exterior cross-component blocks. Validate every affected layer and normal-derivative operator before claiming the multi-component solver supports close boundaries. Correcting only a self `T_ii` entry is not this task.

Important integration checks:

- Handle complex densities without copying a real-density `Re(...)` formula that discards their imaginary contribution.
- Reconcile the reference's Fourier indexing with the repository's even-node Kress/Nyquist convention. Never silently change the solver grid.
- Verify the correct nearby complex preimage, residual, branch/orientation conventions, and a safe far-target fallback.
- Preserve linearity in the source density so corrected evaluations can consistently form matrix rows or operator actions.
- Distinguish accurate quadrature from resolving sharply varying solved densities and from physical/numerical conditioning as gaps narrow.

For two circles, sweep positive gap and source resolution independently, and compare complete fields with the independent multiple-cylinder oracle. Include a plain oversampling control and count its cost. Where possible, vary the gap relative to local source spacing, not merely in arbitrary physical units.

The useful outcome is improved close-target accuracy at a matched error budget. Do not promise cheaper generic assembly: a target-dependent correction is not automatically an FFT-diagonal global operator. Keep exact contact, self-intersection, and pinch configurations invalid.

## 10. Task H — extraction and topology ideas worth retaining

### H1. Tangency-aware smooth fitting

Reach For the Arcs reconstructs from discrete SDF samples using a geometric tangent-point interpretation. A proposed 2-D adaptation could fit a smooth Fourier curve to distance/tangency constraints instead of only projected contour points. The cited method does not already provide our Fourier-to-Kress decoder. [R4]

Test first on independently specified exact distance samples, then a frozen approximate neural SDF with measured off-surface distance error. Do not treat generic ellipse/radial level-set values as Euclidean distances. Neither Eikonal regularization alone nor the existence of a zero set certifies valid tangent-circle radii.

Use equal or explicitly counted query budgets; distinguish continuous field/gradient access from sparse distance samples. Compare zero-set projection plus Method B against the new fit on the same frozen geometry. Evaluate topology, set fidelity, derivative accuracy, query cost, and downstream field error. Test sign/inside consistency and genuine closest contacts, not tangency stationarity alone.

Do not sell this as a reconstruction breakthrough when the SDF was generated from the same canonical curve. Its first possible contribution is improved conversion accuracy or lower query cost. Likewise, predictor–corrector contour tracking is worth reconsidering if measured extraction cost dominates; it needs component seeds and independent topology checks.

### H2. Data-driven component proposals

The most decisive topology experiment starts with the wrong object count and accepts a new, valid separated geometry because it improves a declared data objective with complexity control. A boundary-local shape gradient alone cannot create an object in empty space. The existing Cassini trajectory tests extraction/forwarding, not that inverse task. [S1, S2]

First establish a fixed-count explicit multi-loop inverse control. Then add a small proposal/search mechanism for birth/death or split/merge candidates. Candidate placement must come from data sensitivity or a declared spatial search, not target coordinates. Use training data for proposals/acceptance and untouched acquisitions for final testing.

A topology event may be a discrete jump between valid geometries. It need not numerically pass through a pinch, and a well-separated candidate does not require waiting for Task G. Preserve clearance checks, material conventions, and the true forward acceptance test. Include persistent component identity and event ancestry; spatial sorting alone is not identity.

Compare SDF-based proposals with explicit-loop proposals. Penalize unnecessary complexity, include false-positive controls, and report failures as well as successful count recovery. Distinct per-component materials are a later extension requiring independent unequal-cylinder validation and material state attached to persistent identities. Nested objects require a different region/interface model. [S1, S2]

## 11. What not to implement in this batch

Do not replace Kress with implicit local quadrature/density interpolation, build a Faber/conformal operator solver, introduce a spectral implicit field, add a learned generative shape prior, or port to 3-D. These remain reading/prototype directions, not diagnosed fixes for the reported run. A full 3-D EM target changes traces and quadrature rather than adding a coordinate to scalar TMz. [S1]

Do not grow the network as the first response to its drift. Do not retune Method C until another unlabelled objective happens to pass. Do not bypass geometry failure states, use held-out truth to tune acceptance, or treat a tiny linear-system residual as field accuracy.

The missing air/ground interface and acquisition modeling remain separate limitations for physical GPR. The present benchmarks should continue to be described as homogeneous full-space tests. [S1]

## 12. Deliverables and stop conditions

For the first batch, deliver policy separation, smooth-curve target construction, focused regression tests, and the C1/C2 comparison driver plus one bounded artifact set. Keep all research functionality opt-in and the old baseline reproducible.

Every new result bundle should record the working-tree/commit identity and relevant dirty-state provenance; full immutable observation/acquisition/material configuration; canonical geometry representation and coefficients; separate extraction, fitting, distance-target, audit, and BEM resolutions; status and explicit failure reasons; call counts and separated timings; reference identity/convergence; and exact commands/environment.

Reuse the repository's strict JSON/CSV/non-pickled geometry artifacts. Write to new directories. Do not overwrite the saved September results or introduce notebook-only generation logic.

The Codex completion note must distinguish:

1. existing behavior confirmed, new code implemented, and designs still deferred;
2. tests actually run and their outcomes;
3. measured changes in geometry, field accuracy, runtime, and export status;
4. experiments that failed or did not show an advantage.

Stop the first batch after producing that evidence. Do not automatically progress into topology, new singular quadrature, or a neural optimizer because their designs appear later in this document.

## Sources and reading entry points

### Project evidence

**[S1]** `inverse_pipeline_review_2026-09-05.md`. Primary current assessment. In particular: “Verdict,” “What the saved evidence actually says,” “How the SDF could earn its place,” and “Correctness fixes in this review.” Repository links inside it are navigation hints; inspect the actual tree.

**[S2]** Uploaded `README.md`, titled **Automatic multi-component SDF/Kress seam**. Use “Supported contract,” the direct boundary-forward adapter, and “Integration boundary after the MLP repair.” This is the sibling package README, not evidence that its inverse integration has already happened.

**[S3]** `sdf_boundary_parameterization_implementation.md`, dated 2026-09-02. Read the continuous/sample contracts, Method B and arc-length behavior, and the full convergence study. Its earlier isolation statements describe that experiment's stage, not a reversal of the later integration reported by S1/S2.

**[S4]** Uploaded `summary.md`, titled **Frozen SDF boundary: isolated Kress proxy**. Use its explicit validation scope and geometry-versus-quadrature distinction.

### Primary literature, checked for this brief

**[R1]** Mohan Zhao and Kirill Serkh, *A Continuation Method for Fitting a Bandlimited Curve to Points in the Plane* (2024 journal publication; 2023 preprint). Read the speed/tangent-angle filtering idea before considering a full implementation.  
Preprint: `https://arxiv.org/abs/2301.04241`  
Journal DOI: `10.1007/s10444-024-10144-5`

**[R2]** Ishit Mehta, Manmohan Chandraker, and Ravi Ramamoorthi, *A Level Set Theory for Neural Implicit Evolution under Explicit Flows* (2022). Read for the distinction between desired geometric flow and actual neural parameter updates.  
`https://arxiv.org/html/2204.07159v2`

**[R3]** Ludvig af Klinteberg, *Singularity swap quadrature for nearly singular line integrals on closed curves in two dimensions*, BIT Numerical Mathematics 64, article 11 (2024). Read the Cauchy/log constructions and target-preimage step; the preprint also identifies the author's baseline Julia implementation. Verify indexing and source-version details rather than transcribing rendered formulas unchecked.  
`https://arxiv.org/html/2304.11865v1`  
Journal DOI: `10.1007/s10543-024-01013-0`

**[R4]** Silvia Sellán, Yingying Ren, Christopher Batty, and Oded Stein, *Reach For the Arcs: Reconstructing Surfaces from SDFs via Tangent Points* (SIGGRAPH 2024). Read the geometric interpretation of distance samples; a Fourier-boundary adaptation would be our experiment.  
Author project page: `https://odedstein.com/projects/reach-for-the-arcs/`

**Bottom line:** first make the explicit reconstruction and SDF export honest, independently accurate products. Test parameterization-aware fitting as the smallest interesting new idea. Preserve analytical harmonic close evaluation and neural shape coupling as separate, testable next milestones rather than combining them into one untraceable rewrite.
