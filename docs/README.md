# Project dashboard

Updated 2026-09-11. This page is the entry point: current baseline, current
research objectives, active tracks and what each one is waiting for. It
**summarises and links**. Measurements live in the
[results catalogue](../results/README.md); implemented capability lives in
[current architecture](current_architecture.md); per-cycle state lives in the
track handoffs. This page does not maintain a second experiment register.

## Current baseline

**[B0 — 2026-09-10](baselines/B0_2026-09-10.md).** Branch
`feature/ordered-boundary-nystrom`, **commit `345038a`**. B0 was recorded
against `e34ed5f` plus an uncommitted working tree; that source was committed on
2026-09-11, so `345038a` is what to check out and `e34ed5f` alone predates the
corrections. Its eight audited source files match the
[September 10 pipeline audit](../results/validation/cartesian_fourier/pipeline-audit-20260910/README.md)
byte-for-byte, so the audit is the reference evidence for the current state.

Limitations that change how the baseline can be used:

- A fresh checkout of `e34ed5f` **does not** reproduce B0 — use `345038a`.
- Most audit rasters and figures are excluded by the `results/` binary policy.
  The death-case video and inspected final frame are tracked exceptions; the
  numerical records are tracked.
- Topology bundles predating TOP-001 do not record their producing commit.
- The single-component Cartesian bundle's recorded commit `4f0fd6d` is not an
  ancestor of HEAD; it was rewritten into `7dae78e` and the trees differ.
- B0's controller driver records no forward-solve counts. TOP-001 now adds
  passive accounting; historical bundles still cannot support cost comparisons.
- Full list: [B0 §8](baselines/B0_2026-09-10.md#8-known-limitations-and-missing-provenance).

## Current research objectives

**A. Topology treatments.** When to propose events, how to construct
candidates, how to allocate candidate-refinement effort, and how to accept or
reject events. 3D-Gaussian-Splatting-inspired adaptive representation
management is on the candidate list, not a prescribed solution.

**B. Boundary representation and the BIE solve.** How Fourier curves — or
smooth parameterised boundaries generally — combine with the BIE solve:
geometry/optimisation coordinates, boundary-trace representations, weak and
Galerkin formulations, derivatives, conditioning, and cost. Replacing Kress is
**not** assumed to be the goal.

## Active tracks

| Track | Question | Stage | Next expected action | Approved IDs |
|---|---|---|---|---|
| [Topology / Track A](iterations/topology/README.md) | How can the inverse choose and execute topology changes more reliably, without a prescribed object count or excessive BIE cost? | TOP-007 complete; guarded runs abort nothing, both arms still pass 5/12. **Implementation held for a literature verdict** | Wait for that verdict before attempting any fix; [iteration 05](iterations/topology/iteration_05/01_results.md) has the diagnosis and the candidate fixes, none approved | **TOP-001, TOP-005, TOP-006, TOP-007** |
| [Boundary–BIE](iterations/boundary_bie/README.md) | Which properties of smooth-boundary representations improve the accuracy, conditioning, differentiation or cost of the BIE inverse? | Brief drafted; no review, no plan | Review [the brief](iterations/boundary_bie/iteration_01/02_proposals/01_boundary_bie_research_brief.md); decide whether `BIE-001` — comparison and selection of one prototype — is the right first deliverable | **None** |

Topology has completed **gate 7 for TOP-001, TOP-005, TOP-006 and TOP-007** under the
user's 2026-09-11 directions to take Track A as far as possible and to continue
from the latest fixes. Those session instructions authorize those plans without
asking again for an exact ID phrase. Boundary–BIE remains at
**gate 2 of 7**, awaiting brief review. TOP-002–TOP-004 remain deferred;
no BIE experiment is approved. See the track handoffs for execution status.

The user's subsequent 2026-09-11 direction authorizes TOP-006: test a distant
large-circle initialization against ellipse/star targets and use a broader
scene matrix for current and future performance comparisons. The numerical
controller stayed frozen during this completed measurement; results opened
iteration 04. The requested distant ellipse/star case fails. All future
performance comparisons must include the [full frozen scene matrix](benchmarks/topology_scenes.md).

**TOP-007 (2026-09-11)** then fixed why four of those runs died: the optimizer
searched the production resolution's feasible set while the controller
evaluated at the refined one. With the opt-in refined feasibility guard no
guarded run aborts, the requested distant ellipse/star case finishes with the
correct object count, and every scene both arms complete returns an identical
state. Pass counts are unchanged at 5/12, which places the remaining failure in
shape rather than feasibility.
[Report](../results/validation/topology/TOP-007-20260911-refined-feasibility/README.md).

### Dependencies and blockers

- `TOP-001` adds solve-count instrumentation in the shared controller driver;
  the [review](iterations/topology/iteration_01/02_proposals/02_codex_review.md)
  declared those changes before implementation.
- Any boundary–BIE prototype will touch shared solver interfaces the topology
  track depends on. Shared-interface changes are declared before implementation.
- The historical radial split failed exact event replay because B0 retains a
  different candidate set. That failure is preserved; fresh unmodified B0 runs
  qualify both charts, and the paired comparison is complete.

## Paused and historical tracks

| Track | State |
|---|---|
| [Radial Fourier topology](iterations/radial_fourier_topology/README.md) | Iteration 2 results recorded, proposals pending. Built the automatic controller both charts now share. Forward-looking topology work moves to the topology track; this history stays where it is |
| [Cartesian Fourier](iterations/cartesian_fourier/README.md) | Iteration 3 executed and measured. Its open iteration-2 questions and iteration-3 candidates feed the two new tracks |
| [Implicit MLP](iterations/implicit_mlp/README.md) | **Paused 2026-09-11 by user direction** — diagnosing the MLP is not the current priority; the explicit Cartesian Fourier implementation comes first. Scientifically open: not closed, not abandoned. Neural recovery remains unresolved. Iteration 3's [plan](iterations/implicit_mlp/iteration_03/03_plan.md) was agreed 2026-09-08 and never executed; it is paused as written |

## Open questions this dashboard cannot answer

- **Whether the paused implicit-MLP iteration-3 plan stands as written.** It was
  consolidated 2026-09-08 from the ChatGPT guide and the first two Claude
  reviews; the
  [gradient diagnosis](iterations/implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md)
  arrived afterwards and removes the gradient hypotheses it budgeted for. The
  2026-09-11 pause deferred the cycle but did **not** settle whether the plan
  stands or must be re-consolidated. That is a question for whoever resumes it.
  Nothing was executed under the plan either way.

## Implemented system

| Start here | Owns |
|---|---|
| [Current architecture](current_architecture.md) | Implemented capabilities, geometry ownership, derivative paths, and demonstrated scope |
| [Baselines](baselines/README.md) | Executable comparison references and their provenance |
| [Iteration workflow](iterations/README.md) | Folder convention, approval rule, experiment-contract template, review and collaboration rules |
| [Results catalogue](../results/README.md) | Actual runs, scenes, dates, outcomes and provenance |
| [Reproduction commands](reproduction.md) | Neural adjoint inverse, gradient checks and separate controls |

### Pipelines

| Pipeline | Owns |
|---|---|
| [Explicit Cartesian Fourier](pipelines/explicit_cartesian_fourier.md) | MLP-free curve and topology drivers, the two optimizer paths, and representation limits |
| [Explicit Radial Fourier](pipelines/explicit_radial_fourier.md) | Explicit curve ownership, fitting/export ablations, and frozen neural metrics |
| [Explicit Radial Fourier shape/material](pipelines/explicit_radial_shape_material.md) | Radial variant with an unknown interior permittivity; analytic derivatives, continuation and restart evidence |
| [Implicit MLP + Method B](pipelines/implicit_mlp.md) | Neural adjoint implementation, geometry ownership, derivative checks, and remaining accuracy gates |
| [Implicit MLP diagnostics](implicit_mlp_diagnostics.md) | Frozen conversion, controlled Eikonal activation, one-update transfer; contract tests run, experiments not yet run |
| [Legacy known-shape-family controls](legacy/known_shape_family_controls.md) | Prescribed-family parameter inverses and why they are distinct from full-MLP recovery |

Active inverse results live under `results/inverse/implicit_mlp/`,
`results/inverse/cartesian_fourier/` and `results/inverse/radial_fourier/`. Both
Fourier pipelines have topology suites; radial additionally has shape/material
and frozen-metric experiments. The old Method-B controls are archived as
[known-shape-family parameter inverses](../results/legacy/known_shape_family_parameter_inverse),
which estimate 3–7 controls in prescribed families, not a full neural field.

## Detailed records

- [Technical references](reference/README.md): mathematics, geometry, solvers
  and validation protocols. Check dated implementation claims against this map.
- [Dated reports](reports/README.md): original numerical conclusions in their
  historical context, including negative results and earlier recommendations.
- [Legacy plans and solver work](legacy/README.md): superseded work orders,
  archived approaches and closed decisions.
- [Validation change log](reports/validation_change_log.md): chronological
  commands and measurements; historical commands retain their original paths.
- [Test layout](../pytest/README.md) and [solver layout](../solvers/README.md).

## Maintenance

Update the architecture page and the relevant pipeline page when implementation
changes; update the track handoff when a stage, next action or execution status
changes; update this dashboard when the baseline, the objectives, or an
approval changes. Use the results catalogue as the entry point for measurements
rather than copying tables into several living documents.

Preserve original run IDs, commands, observations, source hashes and failed
arms; new measurements get fresh output directories. Label inferred dates and
absent audits explicitly. Do not rewrite an executed historical plan to make
later findings look anticipated — record amendments and departures instead.

The [relocation map](../results/relocations.json) maps old paths to organized
locations. One geometry compatibility alias preserves recorded artifact paths
and the existing notebook without modifying its user edits.
