# Radial-Fourier-topology iterations: start here

This is the handoff for agents working on the radial-Fourier topology research
cycle. Read the current state below before choosing work. The shared folder
convention is in the [iterations README](../README.md).

## Current handoff

Updated 2026-09-08.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 02](iteration_02/01_results.md) |
| Stage | Results recorded; proposals pending |
| Latest contribution | [Iteration-02 results](iteration_02/01_results.md) from executing the agreed iteration-01 plan |
| Execution status | Full pass: G0–G5. The direct multi-Kress forward, current-domain TD, one finite birth, two-component radial refinement and predeclared wrong-A qualification all passed. Two inversion videos and complete metrics are saved in the linked run bundle |
| Next expected research action | Review the [iteration-02 results](iteration_02/01_results.md), then propose and review the next bounded experiment. Repeated births, an automatic trigger and low-band continuation are candidates, not yet authorized work |

This project's iteration 1 opened from a brief rather than `01_results.md`
because there was no prior cycle. Its agreed plan has now been executed; the
measurements open iteration 2. A results record identifies the next questions
but does not itself authorize another implementation or experiment.

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
5. [Iteration 1's agreed plan](iteration_01/03_plan.md).
6. [Iteration 2's measured results](iteration_02/01_results.md) and the linked
   implementation artifacts/videos.

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
| [01](iteration_01/03_plan.md) | Topology-aware Explicit Radial Fourier inverse: current-domain topological derivative for component birth | Closed with full G0–G5 pass |
| [02](iteration_02/01_results.md) | Results of one-component birth and wrong-A qualification | Active; results recorded, proposals pending |
