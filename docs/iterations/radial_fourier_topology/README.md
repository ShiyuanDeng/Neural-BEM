# Radial-Fourier-topology iterations: start here

This is the handoff for agents working on the radial-Fourier topology research
cycle. Read the current state below before choosing work. The shared folder
convention is in the [iterations README](../README.md).

## Current handoff

Updated 2026-09-09.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 02](iteration_02/01_results.md) |
| Stage | Results plus user-directed challenge qualifications recorded |
| Latest contribution | [Iteration-02 results](iteration_02/01_results.md), including three post-plan topology challenges |
| Execution status | Full pass: G0–G5 plus large-circle split, far-away replacement, and diagonal ellipse/star split. Five inversion videos and complete metrics are saved in the linked result bundles |
| Next expected research action | **Forward-looking work has moved to the [topology track](../topology/README.md)**, which owns the shared controller's open questions under experiment IDs. Noise, repeated unknown-count births, an explicit event trigger and non-star-shaped targets remain open and are carried there |
| Baseline | [B0 — 2026-09-10](../../baselines/B0_2026-09-10.md). This cycle's bundles are the radial reference B0 §4 pins; none of them records the commit that produced it |
| Downstream use | The [Cartesian-Fourier cycle's iteration 3](../cartesian_fourier/iteration_03/03_results.md) runs this controller under a `--chart` flag and reproduces all eight of these cases. Every radial code path is unchanged and its recorded bundles are untouched; three of that cycle's findings are about this controller and are worth reading here — the candidate-polish rule that decides a split, the feature-radius certificate, and the trust region's dependence on coordinates |

This project's iteration 1 opened from a brief rather than `01_results.md`
because there was no prior cycle. Its agreed plan has now been executed; the
measurements open iteration 2. A results record identifies the next questions
but does not itself authorize another implementation or experiment.

## Relationship to the active tracks

This cycle built the automatic controller that both charts now share. Questions
about that controller — event triggering, candidate construction, refinement
allocation and acceptance — are now organised by question in the
[topology track](../topology/README.md), which cites this cycle's iteration-1
brief, reviews, plan and iteration-2 results as its starting evidence.

Nothing here is moved, renumbered or superseded, and this cycle's approval and
completion history is unchanged. The topology track has **no approved
experiment**; a candidate listed in this cycle's results is not authorisation.

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
