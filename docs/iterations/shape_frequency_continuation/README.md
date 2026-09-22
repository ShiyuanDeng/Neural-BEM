# Shape and frequency continuation

**Research question:** How should the inverse adapt the shape-harmonic band and
frequency steps to recover complicated boundaries reliably at reasonable cost?

The first prerequisite is a qualified, straightforward inverse using Cartesian
Fourier geometry, scalar Fourier normal updates and nodal Müller/Kress. This
track starts from the implementation and evidence already collected; it does
not renumber or move those records. **That prerequisite is met on §4.1 as of
iteration 02**, which replicates the paper's Figure 1 boundary inverse.

## Current handoff

| Item | State |
|---|---|
| Active cycle | [Iteration 02 — the paper profile recovers the glider](iteration_02/01_results.md) |
| Stage | Results available; no successor experiment proposed or approved |
| Working implementation | [Isolated continuation package](../../../experiments/shape_continuation/README.md) |
| Latest run | [SC-013](../../../results/validation/shape_continuation/SC-013-paper-glider-recovery/README.md): both Figure 1 contrasts recover the glider; area error 0.849% at k=5 and 0.297% at k=3, but 2.5x–26x below the published curve rather than matching it |
| Next research decision | Calibrate against the published Figure 1 before anything else: rerun η=10 to k=3 with the drivers' L-scaled `floor(2kL/2π)` update band and see whether the error curve lands on the printed one |
| Current constraint | None active. The user's 2026-09-22 instruction to make the paper's algorithm work authorized the code changes and runs in iteration 02 |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Owner / independent reviewer | Claude / unassigned |

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints. The §4.1 boundary inverse is replicated; the paper's
harder cases, higher frequencies and any adaptive-policy benefit are not.
A proposed next diagnostic is not an executed result.

## Where things live

- [Pipeline guide](../../pipelines/shape_frequency_continuation.md): architecture
  and interfaces.
- [Package README](../../../experiments/shape_continuation/README.md): commands,
  optimizer/controller contract and numerical choices.
- [Paper audit](../../../experiments/shape_continuation/PAPER.md): replication
  settings, assumptions and differences from the manuscript.
- [Paper PDF](../../reference/papers/borges_rachh_greengard_2210.11607v1.pdf): the
  author manuscript used for that audit, and the
  [reference implementation](../../reference/papers/README.md#reference-implementation)
  that settles what the manuscript states loosely.
- [Qualification index](../../../results/validation/shape_continuation/README.md):
  SC-001 through SC-013, with raw measurements, scripts, checkpoints and failures.

This directory owns the research interpretation and decisions. Follow the
[shared iteration convention](../README.md): results open a cycle, proposals
and a plan appear when they exist, and results of the next executed change open
the next cycle. Code and run artifacts retain their current locations.

## Cycle history

| Cycle | Question / state |
|---|---|
| Pre-track work | SC-001–SC-012 built and qualified the inverse/controller, prepared the paper profiles and recorded the first actual-contrast ladder. Original evidence remains under `results/validation/shape_continuation/`. |
| [01](iteration_01/01_results.md) | Why does the resolved paper-profile inverse stop accepting updates, and what should be fixed or measured before adaptive continuation comparisons? Results recorded; its proposed step-halving diagnostic was never run. |
| [02](iteration_02/01_results.md) | Answered: the trust-region band excluded the update's own highest harmonic. Four settings were corrected against the authors' code, and SC-013 recovers the Figure 1 glider at both contrasts. The fixed ladder is now a usable baseline for adaptive comparisons. |
