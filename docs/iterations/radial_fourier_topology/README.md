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
| Latest contribution | [Claude review](iteration_01/02_proposals/03_claude_review.md) of the brief and the Codex review, at head `3835f69` |
| Execution status | No topology implementation or experiment exists. Review-only regression and oracle probes passed; topology recovery remains unimplemented in the repository and unvalidated through the Kress path |
| Next expected research action | Consolidate the [initial brief](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md), the [Codex review](iteration_01/02_proposals/02_codex_review.md) and the [Claude review](iteration_01/02_proposals/03_claude_review.md) into `iteration_01/03_plan.md`, recording accepted amendments, the declared scene and frequency band, fixed configurations, gates and deferrals; no implementation or experiment is authorized |

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
4. [Claude review](iteration_01/02_proposals/03_claude_review.md): the derived
   and validated topological-derivative expression, the measured frequency
   dependence of localization and birth acceptance, the declared inspection
   region, and where the two earlier documents need correcting. Its probes are
   under
   [`results/validation/radial_fourier_topology/iteration-01-20260908/`](../../../results/validation/radial_fourier_topology/iteration-01-20260908/review-diagnostics-topological-derivative/README.md).
5. Iteration 1's `03_plan.md` once it exists.

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
| [01](iteration_01/02_proposals/01_radial_fourier_topology_initial_instructions.md) | Topology-aware Explicit Radial Fourier inverse: current-domain topological derivative for component birth | Active; brief and two reviews recorded, agreed plan pending. Nothing implemented |
