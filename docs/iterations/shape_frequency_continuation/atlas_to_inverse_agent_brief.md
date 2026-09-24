# Agent brief: from the atlas to predictive adaptive inverse scattering

**Prepared:** 24 September 2026  
**Repository:** `ShiyuanDeng/Neural-BEM`  
**Research branch:** `feature/shape-frequency-continuation`  
**Latest inspected commit:** `c23bb5972a6360b4da32d432eb5738b26edb4e31`  
**Historical atlas/strategy review snapshot:** `f90191fffa59538f84915cc6c83f78071dd961a0`  
**Document role:** research direction and agent handoff, not an executed experiment or a frozen numerical specification.  
**New experiment approval:** `PROPOSED — NOT APPROVED FOR EXECUTION`. Existing approvals retain their original scope.  
**New experiment execution:** `NOT STARTED`. Owner and independent reviewer: `unassigned`.

> **Mission:** Establish whether a geometry-dependent atlas can predict when to continue optimizing existing data, change the shape-update space, or introduce another frequency—and whether acting on those predictions improves complete nonlinear reconstructions.
>
> Do not optimize for a larger atlas, another heuristic, or more passing tests. Optimize for a defensible chain: **mechanism → prediction → controlled intervention → full-inverse benefit**.

## 1. Start here: scope, authority, and repository state

Read `AGENTS.md`, `docs/iterations/README.md`, `docs/iterations/implementation_principles.md`, and the shape/frequency track handoff before proposing edits. Their current execution, collaboration, and approval rules govern implementation. This brief supplies the scientific direction, not a replacement workflow. [E1–E3]

Use the existing checkout and the already-authorized `feature/shape-frequency-continuation` branch for this track. The repository-wide default branch instruction is older and more general; do not switch a running continuation checkout back to that default. Inspect the actual branch, HEAD, dirty files, and active jobs. Never discard or overwrite another agent's work, change a checkout being benchmarked, or create a new branch/worktree without separate explicit permission.

The user has requested this instruction document and agreed with its research direction. That does **not**, by itself, authorize every future campaign below. Read the live handoff for any broader, explicit user authorization already in force. Otherwise, first produce a reviewed, bounded experiment contract and obtain the approval required by the repository. Do not invent experiment IDs already in use, compute budgets, reviewers, completed tests, or authorization.

**Immediate task:** reconcile this snapshot with current local/remote evidence, preserve or finish the already-approved SC-030 work as applicable, and propose the smallest next diagnostic contract. Do not launch the entire roadmap, regenerate the entire atlas, or start tuning policies immediately.

### Placement and lifecycle

At the inspected snapshot, place this file as:

```text
docs/iterations/shape_frequency_continuation/iteration_13/02_proposals/01_atlas_to_inverse_research_brief.md
```

That proposal slot was empty at the inspected commit. If another proposal has arrived, use the next available proposal number without overwriting it. If the live handoff has advanced, place the proposal in its actual current cycle and link this dated snapshot. Do not infer the active cycle solely from the highest directory number.

The eventual `03_plan.md` owns exact settings and approval status. Executed results open the next iteration. Result bundles own measurements; do not copy large historical tables into multiple handoffs. [E1–E3]

## 2. Big picture: what we are trying to contribute

### 2.1 The original idea

At the current reconstructed boundary, characterize how each available physical frequency acts on shape-deformation harmonics. Preserve more than magnitude: retain signed residual gradients, off-diagonal coupling, jointly constrained directions, and information about where the local model stops predicting a useful finite update. Combine frequency-specific information to inform continuation in data space and shape-update space.

The long-term idea may also use incident/output or boundary-trace modes as extra axes. **That is not a prerequisite for this study.** First demonstrate that frequency/shape diagnostics improve decisions with the qualified nodal forward solver. A lossless change of forward coordinates alone does not create measurement information.

The current pipeline is:

```text
Cartesian Fourier boundary
    → normal Fourier displacement in current normalized arclength
    → finite normal move and arclength refit
    → nodal Müller/Kress transmission forward solve and shape Jacobian
    → shared LM backend
    → continuation policy choosing data, update space, and work allocation
```

The current campaign is a single-component, fixed-topology, known-contrast, lossless/equal-permeability, homogeneous full-space 2-D TMz transmission benchmark. It is relevant to the intended GPR research, but is **not** yet a validated layered-ground, finite-antenna, lossy, or 3-D GPR method. It is also not the native Fourier–Galerkin/Laurent forward pipeline. [E4–E5]

### 2.2 The literature gap must remain specific

| Established ingredient | Candidate gap worth investigating | Evidence needed here |
|---|---|---|
| Frequency continuation with band-limited normal boundary updates. [R1] | An iterate-dependent rule for deciding which data and shape directions are useful now, rather than prescribing a bandwidth from frequency alone. | Predictive advantage over fixed and simple adaptive rules. |
| Scattering-coefficient sensitivity/resolution analysis, including near-circle linearized settings. [R2] | A useful characterization at evolving, noncircular transmission interfaces and through finite nonlinear updates. | Numerical qualification, theory or a quantitative model, and validation outside calibration trajectories. |
| Regularized Newton/LM and Sobolev curve metrics. [R3–R5] | Distinguishing information, optimization, and geometric-validity limitations well enough to choose the correct intervention. | Controlled ablations; the atlas must add value beyond a repaired optimizer. |
| Information-based experimental design and adaptive scattering acquisition. [R6–R7] | Joint continuation using geometry-dependent information **and** finite-update validity in this boundary inverse. | A sharply differentiated mechanism and full-inverse tests accounting for diagnostic cost. |

This table defines a **candidate contribution**, not a verified priority claim. Literature reviews are reading maps, not proof that nobody has done the proposed combination. Any eventual manuscript must compare against the closest primary papers and their assumptions.

The central scientific distinction is:

```text
A mode changes data
    ≠ its coefficient is jointly identifiable
    ≠ a useful finite step exists in that direction
    ≠ the optimizer will find and accept that step
    ≠ repeated choices will recover the true boundary.
```

### 2.3 Intended publication outcome

The preferred paper combines a new diagnostic/mechanism with an algorithmic consequence:

> A geometry-dependent spectral diagnostic distinguishes data-supported deformations from directions that cannot yet be exploited reliably in finite updates. A continuation policy informed by that diagnostic improves reconstruction robustness, accuracy at matched work, or total cost at matched accuracy over competent controls.

A second possible outcome is a strong analysis paper: a new, quantitatively predictive explanation of transmission-inversion failures, supported by controlled interventions, even if it does not yield the best controller. A descriptive atlas or a successful collection of standard optimizer repairs is not automatically that result.

Do not promise publication, global convergence, a universal bandwidth law, or an advantage on every case. Define the actual contribution from the results.

## 3. What has already been done—and what it does not establish

The entries below summarize repository records, not independently repeated experiments conducted while preparing this brief. Refresh current status before execution. [E3–E10]

| Evidence | Recorded result | Interpretation to retain |
|---|---|---|
| SC-001–014: isolated inverse and Borges study | Qualified forward/derivative and continuation infrastructure; glider recovery obtained; Figure 1 reproduction remains provisional. | Useful reference implementation, not a fully settled paper reproduction. |
| SC-015–017: early atlas/horizon/controller study | Circle selection structure, frequency-dependent sensitivity and finite-linearization measurements; adaptive outcomes include clear failures and regime dependence. | These laws are conditional on tested geometries, contrast, acquisition, metric, and directions—not universal facts. |
| SC-020/021: clean hybrid qualification | Borges-style normal/refit updates combined with SPD-style LM; local comparison against SPD on a near-truth handoff. | Backend qualification, not general recovery or an atlas-policy win. |
| SC-022–025: trajectory atlases and band policies | Conditional-step interpretation repaired; roughening/refit obstructions identified; no band policy reliably supersedes the ladder on the tested cases. | Separate actual restricted solves from slices of a larger solve. All six cases are now development data. |
| SC-026: consolidated atlas | 1,286 unique curves, 2,066 state occurrences, 24,434 frequency/state cells, from 49 trajectories. | Substantial reusable evidence, but trajectory-conditioned rather than independent sampling of shape space. |
| Independent SC-026 audit | Algebra/hash checks; 1,875 recorded step occurrences reduce to 1,280 distinct transitions; 24 satisfy the original pathological-roughening definition, all in stage 1. | The event uses truth curvature and misses some difficult cases. It is not an online failure detector. |
| SC-028 qualification | Full `P=48` atlas refinement fails on some rough states. | Preserve this failure. Narrower qualification does not certify the whole atlas. |
| SC-029 controlled strategies | 36 endpoints: 31 completed schedules, three numerical stops, two time stops. Neither smaller first band nor frequency extension passes the frozen robustness criteria. | Meaningful negative intervention evidence; completion does not imply convergence or recovery. |
| SC-030 at `c23bb59` | First pass of six cases × three arms recorded; repeat pending. Cached/uncached hybrid trajectories match; first-pass time reductions 11.2–14.6%. | Baseline/performance work, not an adaptive-atlas result. Do not present pending repeated timings as complete. |
| SC-027 | Regularity/Sobolev-metric proposal exists but is unexecuted at this snapshot. | Review and amend it if selected; do not mark it approved or already tested. |

### Findings that should guide the next experiments

**Extra work on old data matters.** SC-029's original-prefix old-data continuation improves all six RMS errors. Its reported floored geometric-mean ratio is 0.545, at 3.19× total path work. Extra iterations, band opening, and stage resets changed together. This rules out treating the attained noiseless endpoints as solely limited by the maximum data frequency; it does not identify which of those three changes helped. [E8]

**A smaller first band is not a general regularity control.** In SC-029, `M=2` initially helps C/peanut but hurts kite/hook. Peanut's initial-band comparison changes RMS from about 2.94 to 0.129 mm, while hook changes from about 0.525 to 4.99 mm. The smaller first band can lead to either smoother or rougher trajectories. [E8]

**Higher frequencies have different benefits in different states.** After the `M=2` prefix, peanut improves from about 0.0420 to 0.0105 mm versus its old-data continuation; C attains similar error at fewer work units. Other paths fail or retain local defects. This supports testing state-dependent decisions, not automatic extension or its automatic rejection. [E8]

**The atlas has important scope limits.** There are 24 complex paired responses per frequency, giving 48 real rows for 97 `P=48` shape coordinates. Normal-ray coverage is below 99% on 967/1,286 curves. The filtered reanalysis retains only one kite state. The recorded noise threshold is an assumed component-noise model, not measured channel-relative noise. [E6–E7]

**Numerical qualifications are different.** The SC-029 representative active-space diagnostic passes through `M=19` at the declared tolerance; the report records 1,330 accepted-step field cross-resolution checks. Neither fact certifies arbitrary `P=48` Jacobian spectra at rough trial shapes. [E8]

### Do not reopen unrelated work by accident

The shared track record says Laurent and modal-compression tracks were closed by user direction. This brief does not reopen them. Do not add topology changes, neural SDFs, a new BIE assembler, a volumetric inverse, learned controllers, or multi-material physics merely to make the novelty sound broader. Any later extension needs its own scientific question and authorization. [E1]

## 4. Mathematical and data conventions

### 4.1 Separate the four resolutions

Keep physical frequency `f`, normal-update band `M`, Cartesian curve-storage band `K`, and quadrature count `N` independent. Use `P` for a diagnostic atlas band that may exceed `M`.

The current V2 baseline uses cumulative training frequencies `(0.5, 0.75, 1.0, 1.25) GHz`, bands `(3,5,7,9)`, `K=192`, `N=512/1024`, coefficient step clipping, and refit tolerance `1e-5`. SC-029 suffixes use bands through `M=19`. These are **historical comparison settings**, not requirements to preserve forever in a newly approved experiment. [E8–E9]

The material ratio is `chi = k_i^2/k_e^2`; in the present lossless equal-permeability setting it equals the permittivity ratio. Do not confuse it with the volume-potential contrast `chi - 1`. Never insert physical GHz directly into a dimensionless wavenumber rule.

### 4.2 Shape coordinates and physical norms

For physical arclength `s` on a boundary of perimeter `L`, use

$$
h(s)=a_0+\sum_{m=1}^{P}\left[a_m\cos(2\pi ms/L)+b_m\sin(2\pi ms/L)\right].
$$

The displacement coefficient vector `c=(a0,a1,...,aP,b1,...,bP)` has units of metres. It is not the vector of Cartesian geometry-storage coefficients. In exact arclength,

$$
\|h\|_{\rm RMS}^2=c^TWc,\qquad W=\operatorname{diag}(1,1/2,\ldots,1/2).
$$

Check the actual discretized mass when arclength refitting is approximate. Gradients are covectors: compare them with `W^{-1}`; compare physical displacement vectors with `W`. The physical tangential wavenumber of mode `m` is `2*pi*m/L`, so a mode number alone is not a perimeter-independent length scale. [E5–E6]

### 4.3 Residual normalization is not automatically noise whitening

Keep the existing normalized residual and Jacobian available for exact baseline replay:

$$
r_f=\mathcal N_f(F_f(\Gamma)-y_f),\qquad J_f=D_h\left[\mathcal N_f F_f\right],
\qquad g_f=J_f^Tr_f,\qquad G_f=J_f^TJ_f.
$$

For the optimizer's stated objective weights, `g = sum_f w_f g_f` and `G = sum_f w_f G_f`. Do not sum independent LM steps and call that the joint LM solve.

For statistical information, separately declare the covariance `C_f` of the normalized **real** measurement noise and form `C_f^{-1/2} J_f`. If frequency errors are correlated, whiten the full stacked covariance, not independent blocks. Keep noise covariance, objective weights, physical mass, prior precision, and numerical damping distinct.

Independent measurement information adds. Reprocessing the same measurements during old-data continuation does **not** create additional independent information. Repeated independent noise realizations used as genuinely new measurements do; use that distinction in calibration tests.

Every physical frequency still has its own forward transmission solve. Adding `G_f` or Fisher information is legitimate; adding the different forward Müller matrices to replace those solves is not the method.

### 4.4 Evaluate joint information, not just sensitive columns

Use a numerically stable SVD of the mass-scaled Jacobian `J W^{-1/2}`—and its noise-whitened counterpart when appropriate. Avoid interpreting small eigenvalues of explicitly formed normal equations without a refinement/roundoff assessment.

The dimensional bound `rank(J_f) <= 48` is immediate for the present `48 x 97` single-frequency atlas. A wide sensitive-column frontier does not defeat that bound.

For an active group `A` and candidate group `B`, conditional data information is equivalently obtained by projecting `J_B` off the range of `J_A`. In matching coordinates,

$$
G_{B\mid A}=G_{BB}-G_{BA}G_{AA}^{\dagger}G_{AB}.
$$

Declare the nuisance/active space, SVD cutoff, covariance, and any prior. Prefer stable projector computations over subtracting ill-conditioned Gram matrices. This is conditional linearized information, not a global identifiability theorem. Restricting an LM solve to chosen coordinates is also different from taking a slice of a full-space solution. [E5, R2, R6]

## 5. Research sequence and decision gates

These are work packages, **not reserved SC IDs and not blanket execution approval**. A plan may combine small checks when justified, but preserve their distinct questions. Assign only the next needed work and put numerical thresholds, sample counts, ownership, and hard budgets into its reviewed contract before running.

### WP0 — Close the baseline question without changing it

**Question:** What is the reproducible current baseline, and which code/configuration can be shared by later arms?

Refresh SC-030 status. Finish only outstanding work already covered by its authorization; do not duplicate completed runs or mutate its measured checkout. Distinguish the exact cache optimization from SPD/hybrid algorithm differences. The latter use different charts, update spaces, and feasible sets.

**Deliverable:** a short baseline lock identifying commit, observations, acquisition, update implementation, backend configuration, numerical gates, noise convention, available frequencies, timing protocol, and known unresolved failures.

**Gate:** a reproducible and interpretable reference, not perfect recovery on every development case. Do not let baseline repair become an indefinite prerequisite campaign.

### WP1 — Qualify only the atlas information needed for decisions

**Question:** Are proposed decision quantities numerically reliable, physically comparable, and statistically interpretable?

Select a bounded, case-balanced subset of existing smooth, rough, progressing, and stalled states. The plan should freeze selection before inspecting new diagnostic outcomes. Existing failure labels may be used for stratified development analysis, but must not enter the online rule.

Required checks:

1. **Refinement and subspace stability.** Recompute relevant active/candidate Jacobian blocks at increased resolution. Compare singular values and subspace projectors, not raw singular vectors in nearly repeated clusters. Report a discretization-error estimate and mark directions comparable to it as unresolved. A passed field check or tiny linear-system residual is insufficient.
2. **Noise calibration.** Reproduce the historical whole-noise-norm threshold, correctly labelled, then test directional predictions under an explicit noise model. For a unit data singular vector and i.i.d. normalized real noise of standard deviation `eta`, projected noise has standard deviation `eta`, not `eta*sqrt(number of rows)`. For a nonzero singular value `s_j`, unregularized local coefficient uncertainty is `eta/s_j`; regularization changes variance and bias. Null directions are not assigned finite likelihood-only uncertainty.
3. **Noise-scale sanity.** With 48 normalized real components per frequency, `eta=0.001` means expected squared noise norm `48*eta^2`, or RMS vector norm about `0.00693`. It is not 0.1% relative vector noise. Check covariance after normalization, including whether normalization is frozen or depends on noisy observations. Independent repeats should reduce directional uncertainty; re-solving identical data should not.
4. **Arclength-origin covariance.** Change only the parameterization origin of the same boundary, with fixed physical acquisition. Transform harmonic pairs consistently, compare physical proposals, and separate quadrature error from optimizer-coordinate dependence. Test complete sine/cosine pairs. Compare physical subspaces rather than individual eigenvectors across multiplicities.
5. **Truth-projection limits.** Recompute any error-alignment conclusions only on explicitly qualified normal-ray states; retain coverage and misalignment information. Use actual symmetric boundary distances for general nonlocal errors rather than forcing every state into a normal graph.

**Derived diagnostic, not an observed failure:** if an arclength-origin change induces `c = T c'`, then `G' = T^T G T` and `g' = T^T g`. Diagonal Marquardt scaling and componentwise box clipping generally do not commute with those pair rotations. Test whether this matters; do not assume it explains the recorded failures or change the optimizer before measuring it.

**Deliverable:** one compact qualification report, reproducible arrays/scripts, and a list of quantities that are usable, unresolved, or misleading.

**Gate:** release only diagnostics whose accuracy and scaling support their intended decisions. A failed high-order diagnostic may be narrowed to a qualified space, but preserve the failure and its implications. Do not regenerate all SC-026 data merely to increase coverage.

### WP2 — Separate insufficient optimization from insufficient update space

**Question:** Why does additional work on the original data improve SC-029 endpoints?

From identical saved endpoints, isolate three factors: additional iterations, opening `M`, and resetting optimizer state. A small design can compare continued work at `M=9` versus a declared wider space, crossed with preserved versus reset damping; the unchanged endpoint is the no-extra-work reference.

Preserve the relevant optimizer state, not merely the geometry. If the current API cannot resume it, propose and qualify the smallest opt-in resume hook. A supposedly continuous arm that silently reinitializes damping is not the intended control. Report how damping/regularization is transported when the shape space changes.

Keep data, weights, geometry representation, tolerances, and total added work ceilings matched. Record outcomes at prespecified work checkpoints. Log gradient/stationarity indicators, predicted decrease, accepted physical motion, damping, and refusal categories. Do not compare losses from different objectives as though they were one monotone sequence.

**Interpretation:** improvement at unchanged `M` indicates optimization/stopping effects; improvement requiring a wider space implicates restricted update capacity; a reset-specific effect implicates optimizer state. Persistent feasible-step or numerical refusals suggest another limitation. These mechanisms can coexist; do not force every endpoint into one exclusive class.

**Deliverable:** an identifiable control comparison and a bounded decision about baseline changes, not a general new restart algorithm.

**Gate:** later policy comparisons share any adopted backend repair. An atlas arm must not receive fixes that its baseline lacks.

### WP3 — Test finite-step regularity as a separate mechanism

**Question:** Does a physically calibrated regularity-aware update avoid bad trajectories while retaining the ability to recover legitimate detail?

Review the existing SC-027 proposal before implementing a competing version. Compare a small set: the current rule, an appropriate physical mass-metric control, and one regularity-metric candidate. A maximum-displacement cap was already explored; do not present it as an untested cure. [E9]

A candidate subproblem is

$$
\min_d \tfrac12\|r+Jd\|^2\quad\text{subject to}\quad d^TR_\Gamma d\le\Delta^2,
$$

with corresponding multiplier form `(G + lambda R_Gamma)d = -g`. A Sobolev or curvature-variation metric is a candidate, not a predetermined winner. [R3, R5]

Two required amendments to a naive metric substitution:

- Calibrate the metric scale and damping/trust radius. Replacing `diag(G)` by a dimensionless Fourier metric while retaining the same numerical `lambda` changes effective regularization as well as its shape.
- Specify a physical smoothing length and how it varies. The proposed factor `(1+(m/p0)^2)^2` ranges only from 1 to 4 over the active band when `p0=M`; it is not automatically strong high-mode suppression. Changing `M` also changes that choice's physical scale.

**Derived geometry check:** with outward normal convention `t_s=-kappa n`, `n_s=kappa t`, a normal move satisfies

$$
(\gamma+hn)_s=(1+\kappa h)t+h_s n,\qquad
\delta\kappa=-(\partial_s^2+\kappa^2)h.
$$

For a circle of radius `R`, `h=a*cos(m*theta)` gives `delta kappa = a*(m^2-1)*cos(m*theta)/R^2`. Verify signs and units against the code. This motivates controlling derivatives of motion as well as amplitude. It does not by itself guarantee injectivity or protect nearby nonlocal branches. Preserve self-intersection, clearance, representation, and field-accuracy gates.

Measure the model ratio on the actual finite trial, including refit:

$$
\rho=\frac{\Phi(\Gamma)-\Phi(\operatorname{Trial}_\Gamma(d))}
{-g^Td-\tfrac12d^TGd}.
$$

Only interpret it when predicted decrease is positive and resolved relative to numerical uncertainty. If the objective includes an explicit prior penalty, use a consistent total-objective model. A step metric is not automatically a shape prior.

A retry after a candidate cross-resolution failure is a **separate** proposed backend change. It may reject the candidate and reduce the step or refine numerics, but must never accept an underresolved candidate or silently relax a tolerance. Do not bundle it into the metric comparison.

**Deliverable:** matched-cost geometry and failure outcomes plus the mechanism measurements: curvature changes, nonlocal separation, refit error/refusals, model ratios, and actual work.

**Gate:** require useful recovery or reliability, not merely smoother curves. If standard regularity control explains all benefit, acknowledge that and test whether the atlas still adds anything. Do not indefinitely tune curvature penalties to rescue the premise.

### WP4 — Make prospective action predictions before building a controller

**Question:** Does the qualified atlas choose useful interventions better than simpler diagnostics?

At a frozen set of states, define a small action menu. The core actions are: continue on existing data and update space; enrich the update space at fixed data; or add a candidate frequency at fixed update space. Include a regularity/step-scale adjustment only if needed and separately qualified. Define each action as an exact, bounded continuation rather than an informal label.

For every action, specify the frequencies, `M`, iteration/work allowance, backend state/reset policy, and terminal rules. Start action rollouts from identical copies of the saved state. Where the questions differ, use both a one-step mechanism comparison and a matched-work short rollout; do not call equal iteration counts equal cost.

Predict action outcomes **before** observing the resulting trial/rollout outcomes. Baseline predictors should include physical frequency/band alone, residual-progress diagnostics, and column sensitivity. Compare them with joint-information diagnostics and with joint information plus finite-update validity. Prefer interpretable low-dimensional rules first. Any fitted predictor must be described as trained, with its training inputs and cost disclosed.

For an implementable proposed displacement `d`, evaluate

$$
\operatorname{pred}_f(d)=-g_f^Td-\tfrac12d^TG_fd.
$$

Positive cosine between raw gradients is not the same as descent of an LM-preconditioned, clipped, and refitted step. Compare predictions with the actual finite changes. Candidate-frequency probing consumes work and accesses those measurements; it must be charged and cannot later be called unseen validation.

A possible information-gain comparator is

$$
\Delta I_f=\tfrac12\log\det\left(I+H_{\rm old}^{-1/2}H_fH_{\rm old}^{-1/2}\right),
$$

where `H_old` is a declared positive prior precision plus existing noise-weighted local information, and `H_f` is genuinely additional independent information. Evaluate all candidates in the same declared parameter space. Correlated data require conditional covariance treatment. This is a local Gaussian-design score, not a new formula or a certificate that nonlinear inversion improves. Do not identify LM damping with prior precision without a model. [R6]

**Outcome evaluation:** use a common, prespecified data objective across action endpoints, actual symmetric RMS and Hausdorff error as evaluation-only geometry measures, hard-failure rates, and work. An action-specific objective alone is not a fair action ranking. An action that fits added frequencies has used them, regardless of when a report evaluates them.

Report ranking accuracy, calibration, harmful-action frequency, and decision regret relative to the best tested action under the same outcome definition. Label the latter an **evaluation-only action oracle**; never use truth to select the action inside the real inverse. Include an abstain/fallback option and account for ties within numerical uncertainty.

Split evaluation by whole shapes/trajectories, not adjacent states from the same run. Deduplicate shared states and transitions and use case/trajectory-level summaries. Examine whether the atlas adds predictive value at similar frequency and residual level; otherwise it may be a complicated proxy for a cheap scalar.

**Gate:** implement an online policy only if a defined mechanism predicts useful actions beyond strong simple rules and its cost is plausible. If not, narrow the analysis claim or stop controller development with a clear result.

### WP5 — Freeze one policy and test full nonlinear inversions

**Question:** Do repeated atlas-informed choices improve complete reconstruction, after paying for the diagnostics?

One-step or short-rollout success is insufficient: decisions alter future geometry and information. Freeze one candidate policy, its thresholds, fallbacks, refresh rule, regularization policy, and stopping conditions on development data before untouched evaluation.

Use the same repaired backend for the main comparison:

| Arm | Purpose |
|---|---|
| Fixed joint frequency/shape ladder | Competent reference using the same infrastructure. |
| Simple residual/progress-based adaptation | Tests whether generic adaptivity explains the benefit. |
| Sensitivity-only adaptation | Tests whether off-diagonal information and validity diagnostics add value. |
| Proposed atlas-informed policy | Tests the full claimed mechanism. |

Add frequency-only and shape-only ablations if the paper explicitly claims a benefit from **joint** adaptation. Keep the ablation set small and tied to named claims; do not run dozens of unrelated policies.

All arms must have the same available measurement bank, material knowledge, starts, observation realizations, and numerical accuracy requirements. If a richer frequency bank is used, give the controls access to it too. Distinguish computational selection of already-recorded data from actual adaptive acquisition; no acquisition-cost claim follows automatically.

Create genuinely new shape families/instances and multiple starts after development choices are frozen. Include noncircular and strongly concave but representable single-component interfaces. Do not require a radial chart. Use independently refined/cross-checked truth data and report shared solver components honestly; identical discretizations should not be the only validation.

Noise-robustness claims need repeated noise realizations, explicit covariance and noise-aware stopping. Contrast-aware claims need changed contrast regimes. Aperture-aware claims need changed acquisition. A limited-aperture full-space example is still not a complete GPR model. Add only the extensions needed for the chosen claim and budget, rather than expanding the entire factorial design.

**Primary measures:** final geometric quality at matched total work and/or work/time to predeclared geometric quality, plus recovery/failure rates across starts. Geometry-based time-to-quality is computed retrospectively by an external evaluator; it is not a truth-based online stopping rule. Keep RMS, approximate/conservative Hausdorff quantities, and their numerical resolution distinct.

Charge atlas/Jacobian probes, refreshes, rejected trials, validation, geometry processing, and fallback work. Report wall time under controlled threading/order/load, alongside categorized work counts. Include offline training/preparation and amortization assumptions separately. Do not claim a speedup from a cheap early failure.

Keep hard stops and incomplete paths in the results with explicit status; report retained endpoints but do not pool them as converged efficacy observations. Do not select the best intermediate iterate using truth. Do not tune after opening the final test set; doing so converts it to development data.

**Gate:** decide whether the result supports a robustness, accuracy/stability, efficiency, or analysis-only claim. There is no universal publication percentage. Predeclare a scientifically meaningful improvement and regression tolerance; do not choose it from the favorable outcomes.

## 6. Theory agenda: support decisions, not decorative mathematics

The theory effort should answer questions the controller needs. Each statement must be labelled as a known result, a derivation under explicit assumptions, a fitted empirical model, or an untested hypothesis.

A useful candidate is a **usable-amplitude interval**. For a dimensionless `W`-unit direction `v`, a physical displacement is `c=alpha*v`, where `alpha` is in metres. Define a noise-detectable amplitude and a safe amplitude:

$$
\alpha_{\rm detect}(v)=\frac{\tau_{\rm noise}}{\|Jv\|},\qquad
\alpha_{\rm safe}(v)=\min(\alpha_{\rm linearization},\alpha_{\rm geometry},\alpha_{\rm numerics}).
$$

The data norm, noise threshold, confidence/detection interpretation, and whitening must be specified. A nonempty interval is only a candidate condition for usable motion; it is not sufficient for descent, recovery, or global identifiability.

For example, if a qualified smooth finite-trial map obeys a local directional remainder bound

$$
\|F(\operatorname{Trial}_\Gamma(\alpha v))-F(\Gamma)-\alpha Jv\|
\le \tfrac12 B_v\alpha^2,
$$

then requiring the remainder to be at most `epsilon` times the linear response gives the sufficient local bound `alpha <= 2*epsilon*||Jv||/B_v`. `B_v` has to be estimated or bounded over the relevant interval, including refit effects—not fitted after observing the desired answer. Weak directions, failed refits, and unresolved response changes need explicit treatment.

The potentially new work is making such quantities predictive and affordable for an evolving transmission interface, not rearranging the Taylor inequality. A conservative certified bound and an empirically measured horizon answer different questions; an empty conservative interval does not prove the absence of any useful step.

Also pursue coordinate-covariant metrics/diagnostics only as far as they improve interpretability or decisions. Arclength does not need replacing by a polar-angle chart. Across different physical boundaries, compare transported physical subspaces with an explicitly defined map; an origin-shift test alone does not solve general inter-iterate transport.

Use the existing circle laws as analytic controls under their acquisition and material assumptions. Do not claim that the observed `0.12/k` horizon or an exterior-wavenumber-only band law transfers to all shapes, high contrast, sparse aperture, noise, or resonances. Local regularized-Newton theory is a useful model, but its assumptions must be checked rather than presumed. [R1–R5]

## 7. Publication evidence contract

| Outcome | Defensible direction | Claim not justified |
|---|---|---|
| Cleaner code and calibrated atlas; no new predictive relationship | Reliable research instrument and reusable evidence. | A superior adaptive inverse method. |
| Standard optimizer/regularity repairs explain all gains | Report the identified mechanism and improved baseline honestly; assess a narrower contribution. | Attribution of those gains to the atlas. |
| A new diagnostic predicts intervention outcomes across unseen cases, but no robust controller win | Potential analysis/methodology paper with a sharp mechanism and controlled evidence. | Better full reconstruction from local tests alone. |
| A frozen atlas policy improves full inverses over repaired and simple-adaptive controls | Candidate adaptive-inversion paper, scoped to tested physics and regimes. | Universal optimality or guaranteed global convergence. |
| A cheap scalar reproduces the full atlas's benefit | Simplify the method and report which information is actually necessary. | Novelty based on the unused complexity of the atlas. |

The intended manuscript should have a clear mechanism figure, a prospective prediction/intervention comparison, an end-to-end quality-versus-cost comparison, and ablations showing what caused the benefit. Maintain negative cases and defined limitations. A strong regime-specific result can be valuable; a post hoc collection of winning cases is not a defined regime.

Novelty may lie in the qualified coupling of information, geometry, and continuation, but assembling established formulas does not automatically make that coupling new. Keep a short primary-literature comparison table and update it once the actual mechanism is known.

## 8. Implementation and evidence requirements

Reuse `experiments/shape_continuation` APIs rather than cloning optimizers. The relevant map is:

| Area | Existing location to inspect |
|---|---|
| Physical forward and shape Jacobian | `forward.py` |
| Geometry/refit and update semantics | `geometry.py`, `updates.py`, `validation.py` |
| Objective, LM, ledger, stage policy | `lm_backend.py` |
| Atlas algebra, metrics, restricted steps | `atlas_survey.py` |
| Dense dataset and source states | `atlas_dataset.py`, SC-026 index/manifest |
| Existing controls and strategies | `ablation_cases.py`, `conditional_study.py`, `conditional_rules.py`, `policy_cases.py`, `atlas_strategy_tests.py` |
| Paper scope and source-code discrepancies | package `PAPER.md` and track iteration 03 |

This map reflects the inspected track documentation; confirm current signatures before edits. Add the smallest opt-in hooks needed. Preserve historical defaults until a separate promotion decision. No new general experiment framework, large registry, or forward solver is required by this brief. [E4–E5]

Every executed contract must retain:

- The question, falsifiable hypothesis, changed mechanism, controls, approval, hard budgets, and numerical/operational gates fixed before dispatch.
- Source/inputs/configuration hashes, environment, exact commands, seeds, parent checkpoint hashes, accepted states, rejected trials, stop categories, and categorized work.
- At each decision: physical frequencies and units, `M/K/N`, weights/covariance/metric identifiers, proposed action, information available at selection time, prediction, uncertainty/qualification flag, actual outcome, and diagnostic cost.
- Separate evaluation-only truth layers and a deterministic report rebuilt from saved evidence. Name missing data or failed qualifications explicitly; a refused derivative is never silently replaced by zero.

SC-026's approximately 1-GB NPZ arrays were local-only at the inspected snapshot. Hashes and source records are tracked. Locate and verify existing files before reuse. If unavailable, record exactly what is missing and propose a minimal reconstruction of the required subset; do not pretend the arrays were audited locally or regenerate the whole archive without a budget. [E6]

Use one implementation owner and a separate reviewer where available; do not invent assignments or let multiple writers share a checkout. Resolve material recommendations as accept, reject, defer, or a named diagnostic, rather than repeatedly rewriting the whole roadmap. Commit/push only under the applicable user instruction or existing authorization, validate first, and verify the result.

At each closeout answer five questions: **What changed? What did the measurement establish? What remains uncertain? Which claim is now supported or rejected? What is the smallest next decision?** A negative or inconclusive result is a valid closeout; another iteration is not mandatory. [E2]

## 9. Reading priorities and limits of precedent

Read the relevant parts before implementing the mechanism they support. Record the PDE, contrast definition, acquisition, update space, and local/global assumptions when translating a paper into this code.

**[R1] Borges, Rachh & Greengard (2023), _On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary_.** DOI: `10.1088/1361-6420/acb2ec`; [author manuscript, arXiv:2210.11607](https://arxiv.org/abs/2210.11607). Start with §§2.1, 4, 5 and the repository's paper/code audit. Establishes the closest penetrable-boundary continuation baseline. Its single-frequency stages and rich plane-wave acquisition differ from the present cumulative paired point-source experiment. Do not assume the unresolved Figure 1 provenance has been settled.

**[R2] Ammari, Chow & Zou (2016), _Phased and Phaseless Domain Reconstructions in the Inverse Scattering Problem via Scattering Coefficients_.** [DOI:10.1137/15M1043959](https://doi.org/10.1137/15M1043959). The user-supplied `Ammari.pdf` contains this paper. Read §§2–4 before borrowing modal sensitivity/SNR arguments; examine the small-contrast, near-circle, far-field assumptions. It supplies a sensitivity/resolution precedent, not a theorem for arbitrary evolving boundaries in this project.

**[R3] Hanke (1997), _A regularizing Levenberg–Marquardt scheme, with applications to inverse groundwater filtration problems_, Inverse Problems 13, 79–95.** [Institutional full-text record](https://publikationen.bibliothek.kit.edu/178097). Read the parameter-choice/stopping framework and its assumptions before treating LM damping as purely an optimizer tuning constant. It is not a convergence certificate for this scattering implementation.

**[R4] Sini & Thành (2015), _Regularized recursive Newton-type methods for inverse scattering problems using multifrequency measurements_, ESAIM: M2AN 49, 459–480.** [DOI:10.1051/m2an/2014040](https://www.numdam.org/articles/10.1051/m2an/2014040/); related preprint [arXiv:1310.5156](https://arxiv.org/abs/1310.5156), titled _Convergence rates of recursive Newton-type methods for multifrequency scattering problems_. Study the relation among observable shape, frequency increment, Newton iterations, and noise. The sound-soft setting is not the present transmission setting.

**[R5] Sundaramoorthi, Yezzi & Mennucci (2007), _Sobolev Active Contours_, IJCV 73.** [Author-hosted record/manuscript](https://cvgmt.sns.it/paper/368/); DOI: `10.1007/s11263-006-0635-2`. Read to distinguish a metric on motion from an explicit curve prior. Favorable regularity in active-contour flows motivates a test here; it does not establish inverse-scattering performance.

**[R6] Alexanderian & Saibaba (2018), _Efficient D-Optimal Design of Experiments for Infinite-Dimensional Bayesian Linear Inverse Problems_, SIAM J. Sci. Comput. 40, A2956–A2985.** [DOI:10.1137/17M115712X](https://epubs.siam.org/doi/10.1137/17M115712X); [arXiv:1711.05878](https://arxiv.org/abs/1711.05878). Read for prior/noise scaling and incremental information criteria. These are established linear-Gaussian design tools; nonlinear shape-continuation usefulness must be demonstrated separately.

**[R7] Jiang, Khoo & Yang (2024), _Reinforced Inverse Scattering_, SIAM J. Sci. Comput. 46, B884–B902.** [DOI:10.1137/22M153207X](https://epubs.siam.org/doi/10.1137/22M153207X); [arXiv:2206.04186](https://arxiv.org/abs/2206.04186). Read as a prior-art boundary for adaptive sensors/frequencies. It is not an instruction to implement reinforcement learning. Distinguish adaptive acquisition from selecting work inside an inverse with a fixed measurement bank.

**Project literature maps:** read the user-supplied _Fourier/Laurent Boundary Models and Joint Harmonic–Frequency Continuation for GPR/FWI and Inverse Scattering_, especially its distinction among representation, numerical resolution, and identifiable bandwidth, and its conditional-information proposal. Also consult the atlas-specific literature review linked by the track handoff. These are secondary research briefs; verify the primary source before making a theorem or priority claim. Their more ambitious physics/topology suggestions are not automatically part of this scoped study.

The older modal-boundary research reports provide context for why Fourier geometry and trace modes were considered. They are not instructions to restart the closed compression/Laurent tracks.

## 10. Repository evidence index

Paths below are repository-relative. Links pin the evidence actually inspected; the live handoff may contain later amendments. The authoritative numerical record is the associated result bundle, not this summary.

- **[E1] Operating rules:** [`AGENTS.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/c23bb5972a6360b4da32d432eb5738b26edb4e31/AGENTS.md) and [`docs/iterations/README.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/c23bb5972a6360b4da32d432eb5738b26edb4e31/docs/iterations/README.md).
- **[E2] Research principles:** [`docs/iterations/implementation_principles.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/c23bb5972a6360b4da32d432eb5738b26edb4e31/docs/iterations/implementation_principles.md).
- **[E3] Track handoff/history:** [`docs/iterations/shape_frequency_continuation/README.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/c23bb5972a6360b4da32d432eb5738b26edb4e31/docs/iterations/shape_frequency_continuation/README.md).
- **[E4] Pipeline scope:** [`docs/pipelines/shape_frequency_continuation.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/docs/pipelines/shape_frequency_continuation.md).
- **[E5] API/conventions:** [`experiments/shape_continuation/README.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/experiments/shape_continuation/README.md) and [`atlas_survey.py`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/experiments/shape_continuation/atlas_survey.py).
- **[E6] Dense atlas and original analysis:** [`results/validation/shape_continuation/SC-026-atlas-dataset/README.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/results/validation/shape_continuation/SC-026-atlas-dataset/README.md) and its `analyze.py`. Preserve `ANALYSIS.md` as historical interpretation, with the later corrections.
- **[E7] Independent interpretation and filtered reanalysis:** [`docs/iterations/shape_frequency_continuation/iteration_10/01_results.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/docs/iterations/shape_frequency_continuation/iteration_10/01_results.md) and [`results/validation/shape_continuation/SC-026-independent-audit/README.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/results/validation/shape_continuation/SC-026-independent-audit/README.md).
- **[E8] Controlled strategy outcomes:** [`docs/iterations/shape_frequency_continuation/iteration_12/01_results.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/docs/iterations/shape_frequency_continuation/iteration_12/01_results.md), with `results/validation/shape_continuation/SC-029-atlas-strategies/README.md`, `case_results.csv`, frozen plan, histories, and audits.
- **[E9] Unexecuted regularity proposal and existing ablations:** [`docs/iterations/shape_frequency_continuation/iteration_09/02_proposals/01_regularity_controlled_steps.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/f90191fffa59538f84915cc6c83f78071dd961a0/docs/iterations/shape_frequency_continuation/iteration_09/02_proposals/01_regularity_controlled_steps.md), `experiments/shape_continuation/ablation_cases.py`, and the SC-024/025 result bundles.
- **[E10] Latest baseline checkpoint:** [`docs/iterations/shape_frequency_continuation/iteration_13/01_results.md`](https://github.com/ShiyuanDeng/Neural-BEM/blob/c23bb5972a6360b4da32d432eb5738b26edb4e31/docs/iterations/shape_frequency_continuation/iteration_13/01_results.md); approved contract at `iteration_12/03_plan.md`; artifacts at `results/validation/shape_continuation/SC-030-spd008-comparison/`.

## 11. What the next agent should return first

Return a brief state reconciliation, identifying any changes since `c23bb59`, which prior proposed checks already exist, and whether SC-030 is complete. Resolve material disagreements with this brief using source evidence or a bounded diagnostic proposal.

Then propose **one** next experiment contract: its scientific question, selected states/cases, minimal API changes if any, controls, numerical and operational gates, actual ownership, explicit compute cap, artifacts, and what each possible result would change. Identify dependencies and defer the rest.

Do not spend the first handoff rewriting all eleven sections or generating a long list of competing algorithms. The next milestone is a trustworthy decision signal. The eventual milestone is an atlas-informed policy that proves its value in complete inversions—or a clear, narrower scientific conclusion when it does not.
