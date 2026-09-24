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
| Active cycle | [Iteration 08 — the atlas along real trajectories](iteration_08/01_results.md) |
| Stage | SC-022 records the full atlas (sensitivity, gradient, GN block, LM/GN steps, evaluation-only true error) at every accepted state of fixed-schedule trajectories on three cases: 159 states, 2,679 cells. Fixed M=32 stalls from far starts; Borges' band ladder recovers the wrong circle (0.005 mm) and the star to 1.43 mm, and fails on the C (19.4 mm). Descriptive only. No independent review yet |
| Working implementation | [Continuation package](../../../experiments/shape_continuation/README.md): clean hybrid (`updates.py`, `lm_backend.py`), the earlier single-frequency GN/SD path, and isolated legacy/SPD comparison harnesses |
| Latest runs | [SC-022](../../../results/validation/shape_continuation/SC-022-atlas-survey/README.md), after the backend qualification in SC-020/021 |
| Review / next decision | Analyse the stored atlas with no new solves. The user chooses the questions; candidates are in [iteration 08](iteration_08/01_results.md) |
| Figure 1 | Unchanged from iteration 03: still provisional. The band-rule measurement bears on it but does not reproduce it |
| Checkout | Existing `feature/shape-frequency-continuation` branch; no new branch or worktree |
| Implementation owner / reviewer of latest changes | Codex / unassigned |

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
| [07](iteration_07/01_results.md) | The draft pipeline is built. Under SPD's policy it passes SPD's merge case against a fresh, hash-identical SPD rerun. It is less accurate (0.076 against 0.048 mm) and costlier (580 against 256 units) because M=16 arclength updates cannot reach 0.050 mm of out-of-band error that SPD's polar directions partly correct. With M=32 (SC-021) the hybrid reaches 0.0088 mm at 150 units. |
| [08](iteration_08/01_results.md) | The atlas along real trajectories, three cases × two band rules. Fixed M=32 stalls from far starts on geometric refusals; Borges' ladder recovers the wrong circle, gets the star to 1.43 mm and fails on the C. At the star's end, frequencies ≥0.75 GHz point at the missing harmonic 15 but mis-point harmonic 20. |
