# From the atlas to reliable finite shape updates
## High-level research direction for agents

**Repository snapshot:** `ShiyuanDeng/Neural-BEM`, branch `feature/shape-frequency-continuation`, commit `dda61147ba53aa4d31e845262468c674f2d1cf3c` (checked 2026-09-25).

**Purpose:** Set the scientific questions, priorities, and decision criteria. Agents should choose the implementation, numerical settings, and bounded experiment design. This is a research brief, not an executed plan or new experiment authorization; retain the repository’s existing approval and collaboration rules. Reconcile with the live handoff before acting. [R0]

## 1. The big picture

The intended contribution remains **adaptive shape/frequency continuation for penetrable inverse scattering**, supported by a diagnostic that predicts useful reconstruction decisions.

The immediate gap is more specific:

> How should an inverse solver combine data-supported infinitesimal deformations with a controlled family of finite shapes and reliable ways of moving between them?

Do not make “find the correct gauge” or “justify our existing atlas” the objective. Keep the arclength atlas as a qualified local information map, but test its limitations. A different representation should be adopted only for a demonstrated benefit.

Keep four objects distinct:

| Object | Question it answers |
|---|---|
| Shape representation | How do we describe the current outline, and how much approximation freedom does it have? |
| Local update space | Which infinitesimal physical deformations are currently available? |
| Finite update construction | Which candidate boundary does a proposed displacement actually produce? |
| Data sensitivity | Which of those deformations can the available measurements distinguish? |

These objects need not share a basis. A useful architecture may retain arclength normal coordinates for sensitivity while using another representation for the state or another construction for finite updates.

## 2. Starting evidence—not conclusions to rediscover

The following summarizes the recorded branch evidence. Proposed mechanisms below remain hypotheses.

**The atlas exists; a superior atlas-driven inverse is not established.** SC-026 contains trajectory-dependent information, while its audit limits high-order numerical and truth-error interpretations. SC-029 found that smaller initial bands and added frequencies have case-dependent effects. Extra work on the original data improved every original-prefix case, so the original endpoints were not solely frequency-limited. [R0, R1]

**Step regularization has already been tested.** SC-031’s curvature-aware metric did not prevent the stage-1 collapse under the tested settings, despite an active regularization term and accurate local decrease predictions. SC-032 completed the subsequent four-stage comparison. Do not restart the same proposal without a new discriminating question. These results do not rule out a constraint or prior on the resulting shape. [R2, R3]

**The comparison baseline has changed.** SPD-L, with its state-band ladder, is the adopted SPD reference. It recovers several star-shaped cases that the earlier SPD configuration failed. Its radial chart cannot represent all the non-star-shaped targets. Use it where appropriate, and retain a matched hybrid control for claims about a change within the hybrid. [R4]

**Update bandwidth is not state regularity.** RD-2 measures substantial curvature-spectrum content beyond the active update band. RD-3 withdraws its earlier “correction outside the step span” interpretation and points toward finite-update obstructions. Those observations motivate a controlled test; they do not yet prove that changing the finite update alone fixes recovery. [R5, R6]

**A storage-band intervention is proposed, not validated.** RD-4 motivates SC-035 from saved-state approximations. Successful paths also sometimes pass through high-band states. A low-band cap may help, bias, or obstruct the inverse; saved-state fits cannot decide which. [R7]

## 3. Priority A: isolate finite-update geometry from local information

### Question

Can two finite update constructions with the **same first-order normal velocity at the same current boundary** have materially different usable step ranges and reconstruction value?

### Direction

Start with a matched comparison of radial/coefficient motion and normal-graph motion where both are valid. Separate a different physical finite path from merely relabeling the same path. Do not inadvertently change the tangent direction through a second bandwidth truncation.

The scientific comparison is not “SPD versus hybrid again.” It is whether the same infinitesimal information can be used more effectively through a different finite deformation.

### Decision

If an alternative path permits useful finite progress where the matched normal path fails, finite-update geometry is a justified intervention. If both behave similarly, do not attribute that failure to the normal construction alone. If the useful direction cannot be represented in the active arclength space, investigate the update subspace separately.

**Required outcome:** a causal assessment of the finite-update mechanism, including where it does and does not matter—not merely fewer geometry refusals.

## 4. Priority B: a small coordinate and subspace study

### Question

Which apparent differences between arclength, polar-angle, and alternative shape modes are coordinate effects, and which reflect genuinely different allowed deformations?

### Direction

Separate two comparisons:

- Represent the **same physical motion** in different coordinates. This tests consistency and approximation.
- Retain comparably sized low-order spaces in different representations. This tests different geometric priors and deformation capabilities.

Use simple global motions as diagnostic controls, alongside deformations that introduce local detail. A broad spectrum for a rigid translation must not be interpreted as increased shape complexity. Include non-star-shaped geometry rather than making polar coordinates the universal reference.

Reuse the qualified atlas wherever possible. If alternative parameter increments map to arclength normal coefficients through a matrix `B`, the chain rule gives `J_alternative = J_normal B` when those directions are resolved. Transform the physical displacement metric consistently; raw coefficient norms and singular values are not comparable across arbitrary scalings.

### Decision

Prefer an explicit explanation of the subspace differences to a large empirical correlation catalogue. Change or enrich the update space only if it captures useful physical directions more economically or reliably. Coordinate conversion alone cannot create new measurement information.

**Required outcome:** a recommendation about the local deformation space and the atlas’s interpretation—not a universal ranking of gauges.

## 5. Priority C: test regularity of the state, not only regularity of the step

### Question

Can controlling the intermediate boundary itself prevent harmful geometry without excluding legitimate detail or useful recovery paths?

### Direction

Review SC-035 alongside the separate candidate-curve regularization in Borges’ equation (13). An intentional state-band projection, a curvature-tail constraint, a curvature-magnitude constraint, and a clearance constraint regulate different properties. Choose the smallest intervention that tests the proposed mechanism; do not combine them into an unexplained bundle. [R7, P1]

Two theoretical qualifications are essential. First, a curvature guarantee derived from storage band must account for the actual parametrization speed: a Fourier-truncated arclength fit is not automatically exactly constant speed. Second, once projection changes the candidate shape deliberately, the inverse must use the sensitivity of that complete trial construction. Treat this as an alteration of the method, not just a storage optimization.

Do not infer a universal minimum feature size from an empirical detectability frontier. Protect examples with legitimate sharp or concave structure, and distinguish temporary coarse-stage bias from unrecoverable final bias.

### Decision

Keep a state restriction only if it improves reconstruction or reliability at comparable total cost, not merely because curves become smoother. Compare against the same backend without it. Failure should narrow the hypothesis rather than automatically trigger a more elaborate prior.

**Required outcome:** evidence for or against a specific state-level regularization mechanism, separately from finite-path effects.

## 6. Conditional side study: canonical conformal shape coordinates

### Question

Would a normalized exterior conformal map provide a more compact, stable, or useful finite shape family for this inverse problem?

### Direction

Study representation and induced deformation spaces before implementing a conformal inverse. Distinguish exterior conformal-map coefficients from both an arbitrary Laurent boundary and conformal-welding descriptors. Use the primary literature to establish the assumptions of each construction. [P2, P3]

Canonical coordinates do not automatically measure geometric regularity. The one-term exterior map `Psi(w) = a w + b/w`, with `0 < b < a`, describes ellipses that become arbitrarily sharp as `b` approaches `a`. Thus coefficient count alone cannot bound curvature. Assess representation error, parametrization distortion, admissibility, and useful finite motions separately.

Conductivity/Laplace results are precedents, not evidence that the same benefit holds for finite-frequency transmission scattering. A conformal change of variables does not remove Helmholtz geometry dependence for free.

### Decision

Proceed to a conformal-coordinate inverse only if the small study shows a concrete advantage relevant to the failures above. Otherwise retain it as a theoretical comparison. Do not replace the Müller/Kress forward solver or revive node-free assembly merely to test a shape representation.

## 7. Return to adaptive continuation and publication evidence

Once the dominant mechanism is identified, select **one** coherent candidate method. A larger atlas is not the next milestone by default.

The desired evidence chain is:

**Physical distinction → predictive diagnostic → informed decision → improved complete inverse.**

Test whether the diagnostic can distinguish continuing on existing data, changing the deformation space, changing the finite update/state restriction, and adding frequencies. Do not require one diagnostic to choose every action if the evidence supports a narrower contribution.

Then freeze the method and evaluate full nonlinear inversions against the repaired baseline and simpler adaptive controls. Keep data access comparable, charge diagnostic and rejected-trial costs, and reserve genuinely new shapes, starts, and noise realizations for claims about generalization. The present six cases are development data.

If state regularization alone produces the benefit, attribute it accordingly. If a cheap rule matches the atlas, simplify. If the atlas explains a new mechanism but does not improve full inversions, consider an analysis contribution rather than claiming a superior reconstruction algorithm.

## 8. Agent handoff

First reconcile this snapshot with current results and recommend one bounded next experiment, normally Priority A with the small parts of Priority B needed to interpret it. Explain any change of order from new evidence. Review SC-035 in parallel; keep conformal mapping conditional.

Choose the implementation, case selection, tolerances, budgets, and tests locally under the existing workflow. Return a short decision record: the question, decisive comparison, theoretical justification, and what each possible outcome would change. Avoid another framework, a sprawling benchmark, or repeated whole-roadmap rewrites.

**End goal:** connect trustworthy local information to useful finite shape evolution—not defend a particular gauge.

## Evidence and reading anchors

Repository sources below are pinned to the reviewed snapshot. The live handoff governs later execution; newer results can supersede this brief.

- **R0:** [Track handoff](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/README.md).
- **R1:** [SC-029 closeout](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_12/01_results.md).
- **R2:** [SC-031 closeout](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_14/01_results.md).
- **R3:** [SC-032 closeout](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_15/01_results.md).
- **R4:** [SC-034 and SPD-L](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_16/01_results.md). Read together with the subsequent RD-3 correction.
- **R5:** [RD-2: update band and bending spectrum](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_16/02_proposals/01_band_energy_audit.md).
- **R6:** [RD-3: expressibility and finite-step validity](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_16/02_proposals/02_step_span_audit.md). Its interpretation remains subject to the matched-path test proposed here.
- **R7:** [RD-4: storage-band proposal](https://github.com/ShiyuanDeng/Neural-BEM/blob/dda61147ba53aa4d31e845262468c674f2d1cf3c/docs/iterations/shape_frequency_continuation/iteration_16/02_proposals/03_storage_band_audit.md). The parametrization qualification in Priority C is an additional theoretical caution, not an executed correction.
- **P1:** Borges, Rachh and Greengard, *On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary*. Read equations (10)–(13), Theorem 2.1, and the conclusion’s discussion of admissible curve families. [Author manuscript](https://arxiv.org/abs/2210.11607).
- **P2:** Jung and Lim, *Series Expansions of the Layer Potential Operators Using the Faber Polynomials and Their Applications to the Transmission Problem*. Reading target: normalized conformal geometry and its operator basis; verify the governing PDE before transferring any result. [DOI](https://doi.org/10.1137/20M1348698).
- **P3:** Choi, Helsing, Kang and Lim, *Inverse Problem for a Planar Conductivity Inclusion*. Reading target: conformal coefficients as inverse shape variables, and the limits of transfer from conductivity to finite-frequency scattering. [DOI](https://doi.org/10.1137/22M1522395).
