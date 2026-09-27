# GPR: next steps for multi-object strategies and topology-aware inversion

**Date:** 27 September 2026  
**Repository baseline:** `ShiyuanDeng/Neural-BEM`, `feature/shape-frequency-continuation`, commit `a122882582cb5d39e4237e40dcff8b97da337491`.  
**Status:** Research roadmap, not an executed experiment. Repository observations, established results, mathematical deductions, and proposed hypotheses are distinguished below.

## 1. Decision: include topology in the programme, but separate diagnostics from actions

**Recommendation:** qualify fixed-count two-object inversion first. Include topological derivatives in a separately budgeted, diagnostic-only study once that forward/derivative foundation works. Enable topology-changing actions only after testing whether those diagnostics distinguish missing objects from ordinary shape error.

| Phase | Topological derivatives | Topology-changing actions |
|---|---|---|
| A. Coupled solver and derivative qualification | Reuse/audit existing implementation; no dependency on it | Off |
| B. Two-object strategy comparison, correct count | Optional saved-state diagnostics, separate cost | Off |
| C. Missing/extra-object diagnostic study | On, with finite-perturbation validation | Proposals evaluated but not committed to the baseline trajectory |
| D. Unknown-count inversion | On, recomputed for the current configuration | Controlled birth and whole-component deletion first |
| E. Connected/disconnected ambiguity | On where appropriate | Split/merge after separate qualification |

This is an experimental sequencing choice, **not** a claim that shape and topology must always be solved separately. Hybrid topological-derivative/regularised Gauss–Newton methods already initialise and update component counts during electromagnetic inversion. That is a direct precedent for the eventual integration, not evidence that our current implementation is ready for it. [^1]

**Central research question:** can the atlas help choose between refining an existing object, repairing its geometry, updating coupled objects together, and proposing a different component configuration—more effectively than simple schedules and existing topology controls?

## 2. What we already have, and what must not be assumed

**Repository evidence.** The older explicit Cartesian/topology pipeline supports disjoint components and birth/death/split/merge. However, its Cartesian topology optimisation path enforces a polar-angle gauge that restricts individual components to a star-shaped family. Its results do not establish general non-star-shaped multi-object inversion. [^P1]

The newer continuation core supports general Cartesian curves and arclength-normal updates, but is documented as single-component and separate from the old topology controller. Transfer the coupled physics and reusable infrastructure—not the restrictive geometry policy—into that core. [^P2]

The trace archive supports reconstruction of different first-order shape-coordinate Jacobians at an already stored configuration. A new multi-object configuration still needs new coupled forward/reciprocal fields. Large trace arrays are currently local rather than committed, so an externally reproducible study needs published, content-addressed arrays or regeneration instructions. [^P3]

SC-043 tested normal-update bandwidth decisions at fixed state bandwidth with all frequencies retained; its tested atlas rule did not beat fixed or stagnation controls. Retain those cheap controls rather than assuming that another information-based score must improve inversion. [^P4]

**Prior-art boundary.** Multiple-dielectric BIE forward solvers and spectral Gauss–Newton multi-object inversion already exist. The potential contribution is the action-selection mechanism and its demonstrated benefits, not adding a second boundary. [^2][^3]

## 3. Mathematical basis: sensitivity is not object-specific identifiability

### 3.1 Keep the three resolution controls separate

For object $j$, store the boundary as

$$
z_j(t)=\sum_{p=-K_j}^{K_j}c_{jp}e^{ipt},\qquad t\in[0,2\pi).
$$

Here $K_j$ is Cartesian **state bandwidth**, $M_j$ is the bandwidth of the scalar **normal update**, and $N_j$ is boundary quadrature resolution. A Fourier curve is not required to be star-shaped, but it must remain regular and non-self-intersecting. Different components must remain disjoint in the first study. Band-limited updates, reparameterisation and shape regularisation have direct boundary-inversion precedents. [^4]

Let $T_z(a)$ be the actual trial construction for the collection of curves, including any intentional projection and reparameterisation, with $a=(a_1,a_2)$ its real update coordinates. Differentiate $F_f\circ T_z$, not an idealised normal move that is subsequently altered by the implementation. This follows from the chain rule; it is consistency, not a novelty claim. [^P4]

### 3.2 All objects belong to one coupled forward problem

Schematically, at physical frequency $f$,

$$
\begin{bmatrix}A_{11}(f)&A_{12}(f)\\A_{21}(f)&A_{22}(f)\end{bmatrix}
\begin{bmatrix}\mathbf t_1\\\mathbf t_2\end{bmatrix}
=
\begin{bmatrix}\mathbf b_1\\\mathbf b_2\end{bmatrix}.
$$

$\mathbf t_j$ denotes the inherited Müller trace unknowns on component $j$; $A_{ij}$ couples source component $j$ to target component $i$; $\mathbf b_j$ contains incident data. Preserve the code's trace signs and normal conventions. This block structure is standard multiple-scattering BIE machinery. [^2][^3]

Moving one object changes the coupled solution on both. Every object-specific Jacobian must therefore use the **full current configuration**. Freezing an object's geometry does not mean removing its scattering interactions.

### 3.3 Construct an object-resolved atlas

Stack real and imaginary data into real residual vectors. For a declared frequency set $\mathcal F$, use

$$
\Phi(z)=\frac12\sum_{f\in\mathcal F}\alpha_f
\left\|W_f^{1/2}\big(F_f(z)-d_f\big)\right\|^2.
$$

Here $d_f$ is measured data, $\alpha_f$ is a fixed frequency weight, and $W_f$ is a declared data metric. Call it noise whitening only when it is actually the inverse noise covariance of the real-stacked measurements.

After the same weighting and stacking, the local model is

$$
r(a)\simeq r+J_1a_1+J_2a_2.
$$

Use the actual normal-velocity basis $B_j(s)$ to define a physical metric, for example

$$
G_j=\frac1{L_j}\int_{\Gamma_j}B_j(s)^TB_j(s)\,ds,
$$

where $L_j$ is perimeter. Remove gauge/null coordinate directions before requiring $G_j$ positive definite. State whether comparisons use per-object RMS displacement or perimeter-weighted global RMS; these are different choices. The normalised block is $\widetilde J_j=J_jG_j^{-1/2}$.

**Linear-algebra deduction.** Write $P_2=\widetilde J_2\widetilde J_2^\dagger$, with $\dagger$ the Moore–Penrose inverse. Then

$$
\min_b\|\widetilde J_1a+\widetilde J_2b\|^2
=a^TS_{1|2}a,
\qquad
S_{1|2}=\widetilde J_1^T(I-P_2)\widetilde J_1.
$$

The minimisation projects object 1's data change against everything object 2 can imitate. Therefore $S_{1|2}$, rather than only $\widetilde J_1^T\widetilde J_1$, measures locally distinguishable object-1 changes when object 2 is also unknown. With full-rank blocks it is the usual Schur complement of the joint Gauss–Newton matrix.

Use rank/noise thresholds consistently and report absolute singular values as well as cross-object correlations. Weak columns must not become important merely because they were normalised. If priors constrain compensation by the other object, use and label the corresponding regularised calculation. Sensitivity-based model/data selection already has substantial FWI precedent; the proposed object-action application remains a hypothesis. [^5][^6]

**Do not conflate:** strong physical multiple scattering, correlated inverse parameters, and low absolute information. They are different properties. Even an additive forward model can have correlated Jacobian blocks.

## 4. First experiment: fixed-count two-object inversion

### A. Qualify the extension before testing policies

Use two circles to compare coupled fields with the existing independent multi-cylinder reference where applicable. Check derivatives for moving object 1, moving object 2, and moving both. Repeat at refined quadrature and over a perturbation-size convergence window. Then qualify a circle/ellipse plus a non-star-shaped component. BIE multiple-dielectric and spectral inverse references provide the relevant numerical context. [^2][^3]

Preserve the one-object regression. Verify component permutations only reorder internal arrays, not predicted physical data. Do not silently reintroduce the legacy polar gauge. Treat inter-object clearance and near evaluation as numerical qualification issues, separately from shape regularisation. [^P1][^2]

**Deliverable:** coupled forward/complete-trial derivative checks and a fixed-count baseline that returns valid endpoints. No controller novelty claimed at this stage.

### B. Choose a small, discriminating benchmark

**Proposed design:** one smooth component and one complicated component, initially with the same known material contrast. Test two predeclared, safely non-touching separations. Report minimum gap relative to wavelength and object size; do not assume distance alone determines information coupling.

Start with the correct count and approximate locations, but incorrect shapes. Preserve the inherited paired acquisition first. Full multistatic data are a separate acquisition experiment—not extra measurements that may be silently read from a stored prediction matrix.

For the same target, compare: target alone; target with a geometrically known neighbour; and target with that neighbour also unknown. The last two isolate the nuisance-shape effect in the **same physical scene**. Algebraically, $S_{1|2}\preceq\widetilde J_1^T\widetilde J_1$ there. No analogous monotonic claim follows when comparing the known-neighbour scene with the target-alone scene, because the fields themselves change.

**Hypothesis:** another object can alter useful illumination while also introducing parameter ambiguity. Whether the net effect helps this acquisition is to be measured, not presumed.

### C. Compare only two strategy changes initially

| Question | Strong simple control | Atlas-informed candidate | Evidence required |
|---|---|---|---|
| Which object needs more freedom? | Shared fixed ladder; cheap object-wise progress/stagnation ladder | Separate $K_j$ or $M_j$ decisions informed by conditional information | Better worst-object accuracy or cost-to-target; no sacrifice of the other object |
| Should objects move together? | Joint LM; round-robin block updates | Selective versus coordinated updates using object coupling and trial outcomes | Advantage over both controls after counting all work |

Change **state bandwidth or update bandwidth**, not both in the first ablation. Keep the frequency schedule fixed initially. Add frequency selection later only if measured ambiguity gives a concrete reason to test it.

Do not repeat SC-043's assumption that extra optimal linearised loss decrease alone measures action value. Its threshold could reject release once the smaller space already predicted almost complete fitting. Use information for nomination; evaluate finite accepted progress, regularity and cost. [^P4]

Freezing one object does not necessarily save a forward factorisation: the coupled system still includes all objects. Any selective-reuse speed claim needs an implementation and measurement, not just a smaller optimiser block. [^2][^3]

## 5. Topological derivatives: diagnostic-only first

### 5.1 What the derivative says

For the present 2D finite-contrast dielectric setting, let $D$ be the current material region and let $B_\epsilon(x)$ be a small disk inserted in the background, separated from existing interfaces. Under the relevant small-inclusion assumptions,

$$
\Phi(D\cup B_\epsilon(x))-\Phi(D)
=\pi\epsilon^2D_T\Phi(x)+o(\epsilon^2).
$$

The coefficient depends on the specified host/inclusion materials and forward/adjoint conventions. A negative value predicts an infinitesimal descent for that insertion. **It is not a finite-object acceptance rule or proof that an object is missing.** The area scaling is for the dielectric problem; do not import it unchanged for a 2D perfectly conducting hole. [^7][^8]

For continuation from an existing scene, use forward and adjoint fields in that scene, including all present scatterers. An empty-background imaging formula is not a substitute. Iterated topological methods and hybrid shape/topology inversion provide precedents for this distinction. [^1][^9]

Use the derivative of the actual weighted objective. Per-frequency image normalisation may be useful for visualisation, but arbitrary renormalisation need not preserve the derivative of that objective. Signed topological derivatives and nonnegative topological-energy indicators also have different interpretations. [^7]

### 5.2 Test what the diagnostic can distinguish

Freeze four diagnostic cases: correct count but wrong boundary; one missing component; one extra component; and a correct-count noisy case. Later add a modest background/source mismatch as a false-trigger control. These are proposed falsification tests, not scenarios already validated by the papers.

At a few declared checkpoints, log topological maps without altering the baseline path. Validate insertion predictions through progressively smaller finite disks, while controlling quadrature and cancellation error. If the production radius floor excludes the asymptotic regime, use a separate reference probe; do not silently relax production feasibility. Record where the predicted sign and area scaling actually hold.

Treat whole-component deletion as a finite counterfactual forward calculation. A derivative for removing a tiny interior material patch does not automatically validate deleting an entire object.

**Key comparison:** do promising topology candidates persist after an equally budgeted shape-only refinement? Otherwise the topology map may simply be compensating for a poorly fitted existing boundary.

**Gate:** enable actions only if the derivative is numerically qualified and its proposals show useful finite predictive value without systematic false births on correct-count controls. Choose tolerances and decision criteria before testing new outcomes. A visually sharp minimum alone is insufficient.

### 5.3 A possible bridge to the atlas, not an immediate requirement

If the small-inclusion **data** perturbation is also available, define its weighted response per unit area $q_x$ by

$$
r(D\cup B_\epsilon(x))=r(D)+\pi\epsilon^2q_x+o(\epsilon^2).
$$

Then $D_T\Phi(x)=r^Tq_x$. To ask what birth adds beyond existing shape changes, let $J$ be the current combined shape Jacobian and form

$$
q_x^{\perp}=(I-JJ^\dagger)q_x.
$$

**Deduction:** $q_x^{\perp}$ is the linearised data response of birth that existing unrestricted shape updates cannot reproduce. The scalar derivative alone does not determine this vector. With bounded/regularised shape steps, replace the unrestricted projection by the corresponding constrained comparison.

**Important limit:** at an unregularised first-order stationary shape fit, $J^Tr=0$, so $r^Tq_x^{\perp}=r^Tq_x$. Projection then does not change the scalar topological derivative; its possible value lies in distinguishing response directions and comparing finite actions, not creating extra first-order descent information.

**Hypothesis:** conditioning birth proposals on the existing shape space could reduce unnecessary object creation. This combines standard small-inclusion and projection mathematics; neither improved decisions nor methodological priority is established. Finite radii, nonnegative inserted area, noise and additional computation must all be tested. [^5][^7][^8]

## 6. Enable topology actions in a separate unknown-count study

Begin with **birth and whole-component deletion**. Defer split/merge until candidate construction and contour fitting work for non-star-shaped components. Thin-neck cuts and bridges are finite geometric events, not automatically certified by a small-disk derivative. Hole creation additionally requires nested-interface handling, outside the current demonstrated topology scope. [^P1]

At a topology decision, compare a finite shortlist against **no topology change plus further shape refinement**. Let all candidates use the coupled solver, declared local-refinement allowances, and unchanged accuracy/admissibility gates. Accept using actual post-refinement evidence; derivative values nominate candidates rather than decide the winner. Do not rank raw topological-derivative values against raw shape sensitivities: their units and perturbation scales differ. Compare finite candidates on a common objective and counted cost.

Specify a noise/discrepancy or explicit model-complexity selection rule before comparing different counts. More flexible models can fit noise; pure residual reduction is not by itself evidence of the correct count. Keep any validation data used for selection separate from untouched final-test data. Bayesian object-count selection is an existing alternative benchmark, not a novelty we can claim. [^10]

Preserve four separate modules: **trigger → construct → refine/allocate budget → accept**. The existing topology track already uses this decomposition; reuse it instead of rewriting all four at once. Its historical successes and failures remain relevant regression evidence. [^P5]

**Required comparisons:** inherited topology policy where its chart is admissible; a simple periodic topology-check baseline with the same candidate generator; and the proposed diagnostic-triggered policy. Test missing, extra and correct-count starts, then split/merge cases. Report false events and final count as well as geometry.

## 7. Other strategy directions to retain—but not bundle into the first extension

These remain alternatives to another global bandwidth rule. Introduce one only when its target obstruction is observed.

| Direction | Proposed action and theory | Minimum comparison / limitation |
|---|---|---|
| **Data-preserving repair — first alternative priority** | Minimise a geometric roughness functional subject to a bounded change in predictions. Weak-data directions can remove existing artefacts rather than merely damp the next update. Constrained/null-space shape optimisation supplies precedent. [^11][^12] | Compare against ordinary low-pass cleanup at equal allowed prediction change. A weak-data direction is not proof of false geometry; finite checks remain necessary. |
| **Localised refinement — strongest geometric alternative** | Keep Fourier storage but selectively activate smooth, local normal deformations. Local sensitivity analysis motivates spatially resolved questions. [^13] | Compare with global release at matched physical limits and work. A complete basis change spanning the same space is not a new action restriction; insufficient storage can erase local corrections. |
| **Curved LM steps — contained optimiser control** | Add geodesic acceleration using a directional second residual derivative, rather than only shortening the first-order step. This is an established nonlinear least-squares method. [^14] | Replay backtracking-heavy states at equal total forward work. Curvature of the data map is not boundary curvature; acceleration does not certify nonintersection. |
| **Small multi-hypothesis continuation — later** | Keep a few geometrically different, data-consistent coarse states instead of committing immediately. Bayesian scattering studies demonstrate multimodal uncertainty in their settings. [^10] | Compare with spending the same total work on one path. A few heuristic branches are not calibrated posterior samples. |

## 8. Evaluation contract and next deliverables

**Freeze before dispatch:** physical setup, geometry families, acquisition, starts, frequency weights, noise draws, baseline schedules, work ceilings, accuracy tolerances, success criteria and permitted interventions. No truth-based selection of iterates, local patches, object count or thresholds.

Report per-object RMS and Hausdorff error, worst-object performance, global material-region error, and local feature/curvature diagnostics. In unknown-count tests, match components only for evaluation and penalise unmatched ones; a small missed object must not disappear in a global average. Track boundary clearance, self-intersections, endpoint qualification, numerical stops, false topology events and discarded work.

Count forward assembly/factorisation, all right-hand sides, reciprocal/adjoint work, refined checks, interior topology-grid evaluation, rejected candidates, and post-birth refinement. Reusing a boundary trace does not make off-boundary topological imaging free. Report controlled wall time as well as declared solve units where possible. [^2][^P3][^P4]

Noise and independent/refined synthetic data are necessary controls, but do not by themselves eliminate shared-model bias. Use new shapes/noise after development, then source/background mismatch. Existing experimental Fresnel work provides a later external benchmark, with a different acquisition and calibration burden—not immediate validation of this GPR pipeline. [^7]

**Immediate deliverables, in order:**

1. Coupled non-star-shaped two-object forward/derivative qualification, preserving single-object regressions.
2. A small object-resolved atlas showing individual versus conditional information at fixed data, geometry and physical scaling.
3. One prospective object-specific strategy comparison against cheap controls.
4. A separately charged, diagnostic-only topological study and a decision on whether birth/deletion actions are justified.

**Defensible novelty target:** a validated, coupling-aware choice between existing-object refinement and topology proposals. Multi-object BIE, topological derivatives, filtering, or combining topology with Newton iteration are established ingredients. The present roadmap proposes a way to test an additional decision mechanism; it does not establish its superiority or priority. [^1][^2][^3][^5][^6]

---

## References and exact project sources

References support the mathematical ingredients or documented precedents, not the untested performance hypotheses above. The literature check is targeted, not an exhaustive priority review. Journal years below are distinguished from later arXiv deposit dates.

[^1]: A. Carpio, T. G. Dimiduk, F. Le Louër and M. L. Rapún (2019), **When topological derivatives met regularized Gauss–Newton iterations in holographic 3D imaging**, *Journal of Computational Physics* 388, 224–251. [DOI](https://doi.org/10.1016/j.jcp.2019.03.027); [author manuscript](https://arxiv.org/abs/1903.12202). Direct precedent for combining topology updates and shape refinement in 3D Maxwell holography; not a matched 2D paired-data benchmark.

[^2]: J. Helsing and A. Karlsson (2019; preprint 2018), **Physical-density integral equation methods for scattering from multi-dielectric cylinders**, *Journal of Computational Physics*. [DOI](https://doi.org/10.1016/j.jcp.2019.02.050); [author manuscript](https://arxiv.org/abs/1808.03122). Two-dimensional multi-dielectric forward and near-evaluation precedent.

[^3]: F. Le Louër (published 2018, volume 59 labelled 2017), **A spectrally accurate method for the direct and inverse scattering problems by multiple 3D dielectric obstacles**, *The Proceedings of ANZIAM*. [DOI and article](https://doi.org/10.21914/anziamj.v59i0.11534). Spectral second-kind BIE and regularised Gauss–Newton multi-object reconstruction.

[^4]: C. Borges, M. Rachh and L. Greengard (2023; preprint 2022), **On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary**, *Inverse Problems* 39, 035004. [DOI](https://doi.org/10.1088/1361-6420/acb2ec); [author manuscript, especially §2.1](https://arxiv.org/abs/2210.11607). Closest transmission boundary-continuation baseline; not evidence that any proposed modification will succeed.

[^5]: A. Mercier, C. Boehm and H. Maurer (2025), **Designing full waveform inverse problems: a combined data and model approach**, *Geophysical Journal International* 241(3), 1479–1494. [DOI](https://doi.org/10.1093/gji/ggaf117). Prior art for joint sensitivity-informed data/model design, in volumetric FWI rather than the present boundary/action setting.

[^6]: L. Xu, V. Winner and H. Maurer (2023; online 2022), **Gradient-constrained model parametrization in 3-D compact full waveform inversion**, *Geophysical Journal International* 232(1), 366–397. [DOI](https://doi.org/10.1093/gji/ggac341). Prior art for adaptive transformed model parametrisation using resolution and gradient information.

[^7]: A. Carpio, M. Pena and M. L. Rapún (2021), **Processing the 2D and 3D Fresnel experimental databases via topological derivative methods**, *Inverse Problems* 37, 105012. [DOI](https://doi.org/10.1088/1361-6420/ac21c8); [full author text, deposited on arXiv in 2025](https://arxiv.org/html/2501.15327v1). §§2–4 specify 2D scalar TM transmission, small-inclusion scaling and experimental imaging. Its empty-background expressions require adaptation for an existing scattering configuration.

[^8]: B. B. Guzina and M. Bonnet (2006), **Small-inclusion asymptotic of misfit functionals for inverse problems in acoustics**, *Inverse Problems* 22(5), 1761–1785. [DOI](https://doi.org/10.1088/0266-5611/22/5/014). Small-inclusion and adjoint-field foundation; its acoustic coefficients are not to be transplanted into TMz without deriving the convention match.

[^9]: F. Le Louër and M. L. Rapún (2017/2018), **Topological Sensitivity for Solving Inverse Multiple Scattering Problems in Three-Dimensional Electromagnetism**, Parts I and II, *SIAM Journal on Imaging Sciences*. [Part I: one-step method](https://doi.org/10.1137/17M1113850); [Part II: iterative method](https://doi.org/10.1137/17M1148359). Detection and iterative multiple-object EM precedents.

[^10]: A. Carpio, S. Iakunin and G. Stadler (2020), **Bayesian approach to inverse scattering with topological priors**, *Inverse Problems* 36, 105001. [DOI](https://doi.org/10.1088/1361-6420/abaa30); [author manuscript](https://arxiv.org/abs/2003.09318). Uncertainty, multimodal posteriors in the studied cases, and stochastic object-count selection.

[^11]: F. Feppon, G. Allaire and C. Dapogny (2020), **Null space gradient flows for constrained optimization with applications to shape optimization**, *ESAIM: COCV* 26, article 90. [DOI and open article](https://doi.org/10.1051/cocv/2020015). Constrained shape optimisation precedent, not a scattering-specific repair result.

[^12]: J. Eckhardt, R. Hiptmair, T. Hohage, H. Schumacher and M. Wardetzky (2019), **Elastic energy regularization for inverse obstacle scattering problems**, *Inverse Problems*. [DOI](https://doi.org/10.1088/1361-6420/ab3034); [author manuscript](https://arxiv.org/abs/1903.05074). General-curve bending-energy regularisation and non-star-shaped reconstruction precedent.

[^13]: H. Ammari, Y. T. Chow and H. Liu (2022), **Localized Sensitivity Analysis at High-Curvature Boundary Points of Reconstructing Inclusions in Transmission Problems**, *SIAM Journal on Mathematical Analysis* 54(2), 1543–1592. [DOI](https://doi.org/10.1137/20M1323576). Local resolution analysis under its assumptions; not a guarantee that an observed curvature spike is a true feature.

[^14]: M. K. Transtrum and J. P. Sethna (2012), **Geodesic acceleration and the small-curvature approximation for nonlinear least squares**, arXiv preprint. [Author manuscript](https://arxiv.org/abs/1207.4999). Directional second-order LM correction and convergence analysis under stated assumptions.

[^P1]: **Repository: existing multi-object geometry and its restrictions.** [Explicit Cartesian Fourier pipeline](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/docs/pipelines/explicit_cartesian_fourier.md), especially “Two optimizer paths” and “Representation limits”.

[^P2]: **Repository: newer continuation scope and conventions.** [Shape/frequency continuation pipeline](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/docs/pipelines/shape_frequency_continuation.md). Single-component core; separate normal-update, state-storage and quadrature controls.

[^P3]: **Repository: reusable trace data and its limits.** [SC-039 trace archive](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/results/validation/shape_continuation/SC-039-trajectory-atlas-data/README.md). Distinguishes paired observations from full predicted matrices and records local-only arrays and refinement exceptions.

[^P4]: **Repository: completed action-policy evidence.** [Iteration 26 / SC-043 closeout](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/docs/iterations/shape_frequency_continuation/iteration_26/01_results.md); [complete-trial action diagnostic](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/experiments/shape_continuation/action_atlas.py). These records support the limitations of the tested rule, not a rejection of all atlas strategies.

[^P5]: **Repository: existing topology work.** [Topology-track handoff](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/docs/iterations/topology/README.md); [controller implementation](https://github.com/ShiyuanDeng/Neural-BEM/blob/a122882582cb5d39e4237e40dcff8b97da337491/solvers/sdf_inverse/topology_controller.py). Reuse the trigger/candidate/refinement/acceptance decomposition; requalify its geometry assumptions for the new core.
