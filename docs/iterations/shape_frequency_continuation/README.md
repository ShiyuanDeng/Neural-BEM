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
| Active cycle | [Iteration 12 — testing the atlas strategies](iteration_12/01_results.md) |
| Stage | SC-029 IN PROGRESS: 12/12 four-stage paths complete, all six baselines replay bitwise. M=2 first stage improves C/peanut and worsens kite/hook; it fails the robustness gate. The 24 frequency/extra-work suffixes are next |
| Working implementation | [Continuation package](../../../experiments/shape_continuation/README.md): clean hybrid (`updates.py`, `lm_backend.py`, with opt-in physical step control), the qualified atlas (`atlas_survey.py`), the SC-023–025 drivers, and isolated legacy/SPD harnesses. Backend variant for new runs: V2 (refit gate 1e-5) |
| Latest runs | [SC-026 atlas dataset and first analysis](../../../results/validation/shape_continuation/SC-026-atlas-dataset/ANALYSIS.md), [SC-025](../../../results/validation/shape_continuation/SC-025-band-policies/README.md), [SC-024](../../../results/validation/shape_continuation/SC-024-backend-ablations/README.md), [SC-023](../../../results/validation/shape_continuation/SC-023-conditional-candidates/README.md) |
| Review / next decision | Execute the remaining frozen [SC-029 comparison](iteration_11/03_plan.md). Keep the original failed P=48 qualification; the inverse-space preflight passes through M=19. No default promotion or fresh-case claim |
| Figure 1 | Unchanged from iteration 03: still provisional. The band-rule measurement bears on it but does not reproduce it |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Reviewer of latest changes | SC-020/021/022: Codex, outsider review. SC-023 to SC-025: none yet |

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints. Iteration 04 adds a measured characterization of how
each frequency acts on each shape harmonic, where that characterization stops
being predictive, and one matched-budget test of driving continuation from it.
Its positive findings are measurements at fixed geometries; its controller
findings are one target family at two contrasts and include a clear negative.
Iteration 05 adds the user-requested regression against the old explicit
Cartesian Fourier pipeline, restricted to single objects. Its baseline wins
on recovery coverage; the new methods stop early on five of the six fixtures.
Iteration 06 isolates a local benefit of step halving and discovers that the
inherited curvature gate excludes the exact star. Its exploratory follow-up
improves recovery substantially but retains a false protrusion.
Iteration 07 builds the drafted clean hybrid and passes its first test
against SPD on SPD's single-object case. The test covers one near-truth
handoff only.

## Where things live

- [Iteration 09 results](iteration_09/01_results.md) and the
  [SC-027 proposal](iteration_09/02_proposals/01_regularity_controlled_steps.md).
- [Review resolution](iteration_08/02_proposals/02_review_resolution.md) and the
  [SC-023–025 plan with amendments A1–A2](iteration_08/03_plan.md).
- [Outsider review, 2026-09-24](iteration_08/02_proposals/01_codex_outsider_review.md):
  verdict on SC-020/021/022, supporting derivations and literature, with a
  reproducible saved-artifact audit.
- [Cleanup purpose](iteration_06/02_proposals/01_clean_adaptive_pipeline_purpose.md):
  the intended solver/policy separation and its role in producing reliable
  adaptive-continuation evidence; purpose and outcomes, not an implementation plan.
- [Pipeline draft](iteration_06/02_proposals/02_clean_pipeline_draft.md): block
  diagram and separate policy/update interfaces; selects Borges' normal move
  and every-trial arclength refit, with SPD-style LM and an SPD-matching first
  policy. After qualification: requalify the existing atlas, test its predictive
  value, then compare simple adaptive strategies. Alternative update strategies
  are separate experiments.
- [SC-020 plan](iteration_06/03_plan.md): the frozen SPD-matched comparison
  contract, declared update-space mapping and pass criteria.
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
  SC-001 through SC-022, with raw measurements, scripts, checkpoints and failures.
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
| [05](iteration_05/01_results.md) | Six existing circle/star recovery fixtures, five arms each. The previous Cartesian inverse passes 6/6; every new policy passes only circle-to-circle. Point-source physics and derivative checks pass. Restore recovery parity before improved-controller claims. |
| [06](iteration_06/01_results.md) | Step halving escapes a specific stall. The inherited 1% curvature gate excludes the exact star; halving plus the existing 10% default reduces training error 94.7%→8.18%, but a false protrusion remains. All four diagnostic arms still fail recovery. |
| [07](iteration_07/01_results.md) | The hybrid passes SPD's near-truth merge case against a hash-identical SPD rerun. M=16 leaves a measured 0.050-mm high-mode error plateau: 0.076 versus 0.048 mm final error, 580 versus 256 units. M=32 reaches 0.0088 mm at 150 units. Review qualifies the plateau as local evidence and the pass as one-case qualification. |
| [08](iteration_08/01_results.md) | Three cases × two band rules. Fixed M=32 fails under the tested settings; Borges' ladder reaches 0.005/1.43/19.4 mm on circle/star/C. Review confirms the atlas records, but full-space harmonic-step alignment is conditional on the other modes and on the signed-distance proxy. |
| [09](iteration_09/01_results.md) | The review is implemented. The atlas numerics pass refinement and directional checks. SC-022's stalls were the refit gate freezing curves roughened by large early steps. No declared band rule beats the ladder. The post hoc A2 rule qualifies on development data but is not reliably better on the held-out cases (1 of 3). Roughening predicts failure; a regularity-controlled step metric is proposed. |
| [10](iteration_10/01_results.md) | Consolidated SC-026 atlas independently audited. Sensitive columns are not jointly determined harmonics; normal-ray coverage is incomplete. SC-028 freezes a controlled initial-band and frequency-extension test on all six development cases. |
| [11](iteration_11/01_results.md) | SC-028 full-atlas preflight fails on rough endpoints; every active inverse column through M=19 passes. SC-029 retains the failed gate and narrows the qualification claim before any recovery outcome. |
| [12](iteration_12/01_results.md) | SC-029: the initial-band comparison is complete and exposes a tradeoff; frequency-extension and matched extra-work controls are pending. |
