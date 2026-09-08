# Radial-Fourier-topology iterations: start here

This is the handoff for agents working on the radial-Fourier topology research
cycle. Read the current state below before choosing work. The shared folder
convention is in the [iterations README](../README.md).

## Current handoff

Updated 2026-09-08.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 01](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md) |
| Stage | Implementation brief and first review recorded; agreed plan pending |
| Latest contribution | [Codex review](iteration_01/02_proposals/02_codex_review.md) of the initial brief, at head `34864ab` |
| Execution status | No topology implementation or experiment exists. Review-only regression checks passed; topology recovery remains unimplemented and unvalidated |
| Next expected research action | Consolidate the [initial brief](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md) and [Codex review](iteration_01/02_proposals/02_codex_review.md) into `iteration_01/03_plan.md`, recording accepted amendments, fixed configurations, gates and deferrals; no implementation or experiment is authorized |

This project's iteration 1 opens from a brief rather than `01_results.md`
because there is no prior cycle. The latest numbered document is the latest
contribution, not an adopted plan. A request to review or update documentation
does not authorize implementing the brief or launching an inverse.

## Read in this order

1. [Initial implementation brief](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md):
   objective (component birth only), why this is the first topology experiment
   for this repository, literature practice to preserve, and the intended
   fixed-topology-refinement ↔ topological-derivative-birth architecture.
2. The existing radial inverse and `solvers/gpr_bem_kress/multicomponent.py`
   for the multi-component forward the brief builds on.
3. [Codex review](iteration_01/02_proposals/02_codex_review.md): agreements,
   required objective/oracle/seam/optimizer corrections, numerical gates and
   confidence levels.
4. Iteration 1's `03_plan.md` once it exists.

## What to do at each stage

See the [shared stage table](../README.md) and the fuller description in the
[implicit-MLP handoff](../implicit_mlp/README.md#what-to-do-at-each-stage); the
same rules apply here. In short: results establish what was measured; proposals
and reviews contribute recommendations and may disagree; the agreed
`03_plan.md` governs execution, and its existence alone does not mean its
experiments have run.

Update this handoff whenever the stage, next action or execution status
changes. Do not infer the active cycle from the highest folder number.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| [01](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md) | Topology-aware Explicit Radial Fourier inverse: current-domain topological derivative for component birth | Active; brief and one review recorded, agreed plan pending. Nothing implemented |
