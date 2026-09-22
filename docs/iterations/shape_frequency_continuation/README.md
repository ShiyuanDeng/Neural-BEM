# Shape and frequency continuation

**Research question:** How should the inverse adapt the shape-harmonic band and
frequency steps to recover complicated boundaries reliably at reasonable cost?

The first prerequisite is a qualified, straightforward inverse using Cartesian
Fourier geometry, scalar Fourier normal updates and nodal Müller/Kress. This
track starts from the implementation and evidence already collected; it does
not renumber or move those records.

## Current handoff

| Item | State |
|---|---|
| Active cycle | [Iteration 01 — baseline and the paper-profile stall](iteration_01/01_results.md) |
| Stage | Results available; no successor experiment executed |
| Working implementation | [Isolated continuation package](../../../experiments/shape_continuation/README.md) |
| Latest run | [SC-012](../../../results/validation/shape_continuation/SC-012-paper-glider-k2/README.md): contrast .33 through k=2; resolution passes, recovery stalls |
| Next research decision | Determine whether the stalled checkpoint admits a useful step with a smaller step length before changing continuation rules |
| Current constraint | The user requested no expensive inverse runs; the latest bounded run was performed by the user |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Owner / independent reviewer | Codex / unassigned |

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints, then limited the current preparation to inexpensive
work. Opening this documentation track adds no numerical experiment or broader
campaign. A proposed next diagnostic is not an executed result.

## Where things live

- [Pipeline guide](../../pipelines/shape_frequency_continuation.md): architecture
  and interfaces.
- [Package README](../../../experiments/shape_continuation/README.md): commands,
  optimizer/controller contract and numerical choices.
- [Paper audit](../../../experiments/shape_continuation/PAPER.md): replication
  settings, assumptions and differences from the manuscript.
- [Paper PDF](../../reference/papers/borges_rachh_greengard_2210.11607v1.pdf): the
  author manuscript used for that audit.
- [Qualification index](../../../results/validation/shape_continuation/README.md):
  SC-001 through SC-012, with raw measurements, scripts, checkpoints and failures.

This directory owns the research interpretation and decisions. Follow the
[shared iteration convention](../README.md): results open a cycle, proposals
and a plan appear when they exist, and results of the next executed change open
the next cycle. Code and run artifacts retain their current locations.

## Cycle history

| Cycle | Question / state |
|---|---|
| Pre-track work | SC-001–SC-012 built and qualified the inverse/controller, prepared the paper profiles and recorded the first actual-contrast ladder. Original evidence remains under `results/validation/shape_continuation/`. |
| [01](iteration_01/01_results.md) | Why does the resolved paper-profile inverse stop accepting updates, and what should be fixed or measured before adaptive continuation comparisons? Results recorded; next diagnostic not run. |
