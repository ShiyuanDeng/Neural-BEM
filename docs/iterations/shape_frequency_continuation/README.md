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
| Active cycle | [Iteration 03 — partial Figure 1 agreement and unresolved fidelity](iteration_03/01_results.md) |
| Stage | Results reviewed; documentation corrected at the user's request. Numerical follow-ups remain recommendations |
| Working implementation | [Isolated continuation package](../../../experiments/shape_continuation/README.md) |
| Latest run | [SC-014](../../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md): five arms; partial contrast-0.33 agreement over k∈[1,5] under the raw-area hypothesis, contrast 10 unmatched. The `driver` profile does not exactly follow upstream resolution/stopping |
| Review / next decision | [Codex review](iteration_03/02_proposals/01_codex_review.md): optimizer fixes accepted; resolve stopping/resolution choices before freezing an adaptive control. Axis convention and author band rule remain unverified |
| Current scope | User requested write-up corrections and recorded verdicts first. No numerical settings or inverse runs changed in this amendment |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Implementation owner / reviewer of latest changes | Claude / Codex |

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints. The optimizer fixes are accepted and the saved runs
are auditable. Partial agreement with Figure 1 does not recover its exact
settings or plotting convention. The paper's harder cases, higher frequencies
and any adaptive-policy benefit remain untested. Recommendations are not
executed results.

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
  SC-001 through SC-014, with raw measurements, scripts, checkpoints and failures.

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
