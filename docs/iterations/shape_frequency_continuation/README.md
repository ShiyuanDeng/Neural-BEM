# Shape and frequency continuation

**Research question:** How should the inverse adapt the shape-harmonic band and
frequency steps to recover complicated boundaries reliably at reasonable cost?

The first prerequisite is a qualified, straightforward inverse using Cartesian
Fourier geometry, scalar Fourier normal updates and nodal Müller/Kress. This
track starts from the implementation and evidence already collected; it does
not renumber or move those records. The working inverse and continuation
interfaces are qualified on the recorded cases. **Figure 1 reproduction remains
provisional**, with two profile differences and plotting provenance unresolved.

## Current handoff

| Item | State |
|---|---|
| Active cycle | [Iteration 04 — measuring the frequency/shape interaction, and what it buys](iteration_04/01_results.md) |
| Stage | Measurements complete and recorded; the controller comparison identifies one mechanism and one blocker. No review yet |
| Working implementation | [Isolated continuation package](../../../experiments/shape_continuation/README.md); the inverse is unchanged, `atlas.py`/`horizon.py`/`policy.py` are additive |
| Latest runs | [SC-015](../../../results/validation/shape_continuation/SC-015-atlas-structure/README.md) atlas structure, [SC-016](../../../results/validation/shape_continuation/SC-016-validity-horizon/README.md) validity horizon, [SC-017](../../../results/validation/shape_continuation/SC-017-atlas-controller/README.md) matched-budget controller arms |
| Review / next decision | Settle harmonic transport before any non-circular frequency-by-harmonic figure is read as physics; that is also what blocks the measured band rule |
| Figure 1 | Unchanged from iteration 03: still provisional. The band-rule measurement bears on it but does not reproduce it |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Implementation owner / reviewer of latest changes | Claude / unassigned |

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints. Iteration 04 adds a measured characterization of how
each frequency acts on each shape harmonic, where that characterization stops
being predictive, and one matched-budget test of driving continuation from it.
Its positive findings are measurements at fixed geometries; its controller
findings are one target family at two contrasts and include a clear negative.

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
  used to audit the numerical conventions. Figure 1's exact provenance is open.
- [Qualification index](../../../results/validation/shape_continuation/README.md):
  SC-001 through SC-017, with raw measurements, scripts, checkpoints and failures.
- [Literature review and reading map](Atlas-Driven%20Adaptive%20Continuation%20in%20Inverse%20Scattering_%20Literature%20Review%20and%20Pre-Coding%20Reading%20M.pdf):
  the user-supplied survey that set iteration 04's experiment design, with its
  own stated search cutoff and verification limits.

This directory owns the research interpretation and decisions. Follow the
[shared iteration convention](../README.md): results open a cycle, proposals
and a plan appear when they exist, and results of the next executed change open
the next cycle. Code and run artifacts retain their current locations.

## Cycle history

| Cycle | Question / state |
|---|---|
| Pre-track work | SC-001–SC-012 built and qualified the inverse/controller, prepared the paper profiles and recorded the first actual-contrast ladder. Original evidence remains under `results/validation/shape_continuation/`. |
| [01](iteration_01/01_results.md) | Why does the resolved paper-profile inverse stop accepting updates, and what should be fixed or measured before adaptive continuation comparisons? Results recorded; its proposed step-halving diagnostic was never run. |
| [02](iteration_02/01_results.md) | The trust-region band excluded the update's own highest harmonic. Four settings were corrected against inspected code; SC-013 recovers the glider at both contrasts. Its 2.5x–26x comparison assumes the printed normalized area interpretation. Its [review](iteration_02/02_proposals/01_codex_review_resolution.md) identified candidate-search and chunk-counter defects. |
| [03](iteration_03/01_results.md) | SC-014 shows partial low-contrast agreement under a raw-area hypothesis; high contrast remains unmatched. The [review](iteration_03/02_proposals/01_codex_review.md) accepts both optimizer fixes, identifies stopping/resolution differences, and withdraws claims that the axis, band rule or paper-matched baseline are settled. |
| [04](iteration_04/01_results.md) | The circle's exact rank-one selection rule; a detectability frontier of 2.5k set by the exterior wavenumber, not `3 max(k,ki)`; a linearization horizon of `0.12/k` whose per-harmonic form the free atlas diagonal predicts to 0.04 dex; frequency gradients that oppose each other, measurably and without truth, from `k=1.25` at contrast 10. Driving continuation from these measurements needs harmonic transport settled first. |
