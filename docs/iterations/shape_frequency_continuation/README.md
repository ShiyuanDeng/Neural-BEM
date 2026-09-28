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

**SC-049 COMPLETE / NOT RECOVERED, 2026-09-27:** the user-requested
[far-circle-to-C trial](iteration_29/01_results.md) stops in stage 1 after
seven accepted steps. Boundary RMS worsens from 168.76 to 188.37 mm despite
lower fitting loss; a subsequent candidate fails field refinement. The main
attempt takes 21.43 s including audits and initial/final atlases. CPU controls
reproduce the endpoint discrepancies. This is a new initialization of the
existing C target, not an unseen shape. No restart or retuning followed.

**2026-09-27 coupled follow-through:** Claude's final review and
[multi-object/topology roadmap](../../GPR_next_steps_multi_object_topology.md)
were pulled after the requested one-hour wait. [SC-047 / iteration 27](iteration_27/01_results.md)
qualifies the coupled non-star-shaped forward and complete derivative. All 12
local reconstruction endpoints pass numerical audits; worst-object RMS falls
from 3.81 mm to 0.74–1.03 mm. Conditional selection fails all four superiority
gates. The current-scene topological derivative passes finite-insertion checks,
but false births and a misplaced missing-object minimum withhold topology
actions. [SC-048 / iteration 28](iteration_28/01_results.md) adds intrinsic
shape perturbations: compact M5 reaches 0.705 mm, M9 2.72 mm, and exact global
enrichment 3.58 mm. All three endpoints qualify; enrichment fails its primary
gate, withholding transfers. No default changes. The autonomous run closes
at these evidence gates. [Briefing](../../reports/overnight_2026-09-27.md).

**2026-09-26 strategy campaign:** the user authorized successive controlled
experiments after review of Claude's `b946d57`. **SC-042/043/044 are complete:
60 comparison paths plus six shared fresh-case prefixes.** All returned
endpoints have passing original or separate numerical qualifications. No
production default, branch or worktree has changed.
The [campaign accounting](../../../results/validation/shape_continuation/STRATEGY_CAMPAIGN.md)
retains all original stops, timeouts and separately charged qualifications.

| Item | State |
|---|---|
| Latest completed cycle | [Iteration 29 / SC-049](iteration_29/01_results.md): distant-circle initialization fails in stage 1; numerical failure and wrong location retained. No successor run scheduled. |
| Prior coupled enrichment | [Iteration 28 / SC-048](iteration_28/01_results.md): compact M5 wins the one clean local screen; exact global enrichment fails the frozen gate. Transfers withheld, no retuning. |
| Coupled and topology qualification | [Iteration 27 / SC-047](iteration_27/01_results.md): coupled physics PASS, 12/12 local endpoint audits; conditional selector not superior; topological derivative qualified but action gate fails. |
| Prior strategy decision | [Iteration 26 / SC-043](iteration_26/01_results.md): COMPLETE, 18/18 policy paths and audits. Atlas RMS geometric-mean ratios 1.11301 versus fixed and 1.00512 versus stagnation; both superiority gates fail. Kite RMS is 88%/68% worse despite qualified diagnostics. |
| State treatment | [Iteration 24 / SC-042](iteration_24/01_results.md): 24/24 development suffixes. One-off cleanup repairs the kite artifact and passes its development gate; recurrent cleanup and a cap give essentially tied geometry. Common-work aggregate improvement is much smaller than terminal improvement. |
| Fresh shapes and noise | [Iteration 25 / SC-044](iteration_25/01_results.md): six common prefixes and 18 suffix paths on two fixed new shapes. Cleanup/cap avoid one noisy-C numerical stop and suppress some local artifacts; most RMS comparisons tie. Original transfer gates retain two audit timeouts. |
| Endpoint follow-ups | All five originally timed-out endpoints have separately passing unchanged audits in [SC-045](../../../results/validation/shape_continuation/SC-045-timeout-qualification/README.md) and [SC-046](../../../results/validation/shape_continuation/SC-046-lost-audit-recovery/README.md). The first SC-045 result was lost to an output error; its failed record and uncertain cost remain. |
| Claims and next decision | [Reviewer constraints](iteration_24/02_claims_review.md) and [conditions for another useful iteration](iteration_24/03_next_decisions.md). Filtering, normal-band restriction, curvature control and constrained least squares have close prior art. The tested prospective rule fails; a replacement must predict accepted finite progress at charged cost. No threshold retuning or production promotion follows from this result. |
| Working implementation | Existing V2 hybrid and fixed M=3/5/7/9 prefix remain the reference; SPD-L is the comparison reference where star-shaped geometry applies. SC-035's centred projected update is reused unchanged in the isolated studies. SC-036's alternate finite path is not adopted. Müller/Kress and production defaults are unchanged. |
| Figure 1 | Still provisional from iteration 03; strategy comparisons do not resolve the profile and plotting-provenance differences. |
| Checkout | Existing `feature/shape-frequency-continuation`; no new branch or worktree. |
| Review | Current campaign owner: Codex. Independent reviewer unassigned. The campaign is an owner assessment of the prior work, not an independent review of its own implementation. |

The [SC-041 closeout](iteration_23/01_results.md) is the preceding comparison.
Its complete-update forecasts nominate useful star releases, while kite
shows that a nominal physical radius does not ensure finite validity. The
historical capped QR display remains a heuristic. Current feature checks
also clarify that the star's 5.11 mm truth minimum is at a concave valley,
not a convex tip; its convex-tip radius is 10.42 mm.

The user authorized autonomous development of this isolated pipeline and
commit/push checkpoints. On 2026-09-25 the user explicitly extended execution
through successive bounded iterations until substantive results or research
blockers, requesting a morning briefing. Branch/worktree restrictions remain.
Iteration 04 adds a measured characterization of how
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

- **Fresh distant initialization:** [SC-049 results](iteration_29/01_results.md),
  [geometry, atlases and raw evidence](../../../results/validation/shape_continuation/SC-049-far-circle-to-c/README.md).

- **Coupled follow-through:** [SC-047 results](iteration_27/01_results.md),
  [evidence and figures](../../../results/validation/shape_continuation/SC-047-coupled-continuation/README.md),
  [SC-048 results](iteration_28/01_results.md), and
  [27 September briefing](../../reports/overnight_2026-09-27.md).

- **Current campaign:** [SC-042 state treatments](iteration_24/01_results.md),
  [SC-044 fresh shapes and noise](iteration_25/01_results.md),
  [SC-043 prospective policies](iteration_26/01_results.md),
  and [combined accounting](../../../results/validation/shape_continuation/STRATEGY_CAMPAIGN.md).


- **SC-041 complete (2026-09-26):** [iteration 23 results](iteration_23/01_results.md),
  [contract](iteration_22/03_plan.md), [evidence and comparison figure](../../../results/validation/shape_continuation/SC-041-atlas-decisions/README.md);
  complete-update physical-metric diagnostic in `experiments/shape_continuation/action_atlas.py`.
- **SC-040 complete (2026-09-25):** [iteration 22 results](iteration_22/01_results.md),
  [plan](iteration_21/03_plan.md), [evidence](../../../results/validation/shape_continuation/SC-040-six-scene-pipeline/README.md)
  and the [six-scene atlas videos](../../../results/validation/shape_continuation/videos/README.md).
- **SC-039 complete (2026-09-25):** [iteration 21 results](iteration_21/01_results.md),
  [plan](iteration_20/03_plan.md) and [data bundle](../../../results/validation/shape_continuation/SC-039-trajectory-atlas-data/README.md);
  collector and later-atlas helpers in `experiments/shape_continuation/trajectory_atlas.py`.
- **SC-038 complete (2026-09-25), directly requested by the user:**
  [Iteration 20 results](iteration_20/01_results.md),
  [small M-release ladder on all frequencies](iteration_19/03_plan.md),
  with [C/kite matched controls and evidence](../../../results/validation/shape_continuation/SC-038-update-band-release/README.md).
- [Iteration 19 results](iteration_19/01_results.md): SC-037, one wider later
  state ladder; [SC-037 evidence](../../../results/validation/shape_continuation/SC-037-later-state-release/README.md) and [plan](iteration_18/03_plan.md).
- [Iteration 18 results](iteration_18/01_results.md): SC-035, the centred
  state-band restriction; [SC-035 evidence](../../../results/validation/shape_continuation/SC-035-state-band/README.md),
  [plan](iteration_17/03_plan.md) and [derivative/speed review](iteration_16/02_proposals/04_state_band_qualification.md).
- [Iteration 17 results](iteration_17/01_results.md): SC-036, matched normal
  and ray finite paths; [SC-036 evidence](../../../results/validation/shape_continuation/SC-036-matched-finite-paths/README.md),
  [coordinate review](../../../results/validation/shape_continuation/SC-036-coordinate-review/README.md) and [plan](iteration_16/03_plan.md).
- [Atlas/geometry research brief](../../atlas_geometry_high_level_next_steps.md): the
  user's 2026-09-25 brief that set iterations 17–19, and the
  [overnight briefing](../../reports/overnight_2026-09-25.md) that reports them.
- [Iteration 16 results](iteration_16/01_results.md): SC-034, the SPD comparison fitter with
  the legacy controls and the ladder; [SC-034 evidence](../../../results/validation/shape_continuation/SC-034-spd-legacy-controls/README.md),
  [assessment](iteration_15/02_proposals/01_spd_legacy_controls.md) and [plan](iteration_15/03_plan.md).
- [Iteration 15 results](iteration_15/01_results.md): SC-032, the four-stage
  continuation; [SC-032 evidence](../../../results/validation/shape_continuation/SC-032-regularizing-metric-prefix/README.md).
- [Iteration 14 results](iteration_14/01_results.md): SC-031 falsifies
  step-metric avoidance of the stage-1 collapse; [SC-031 evidence](../../../results/validation/shape_continuation/SC-031-regularizing-metric/README.md).
- [Iteration 13 proposals](iteration_13/02_proposals/): the user's
  [atlas-to-inverse research brief](iteration_13/02_proposals/01_atlas_to_inverse_research_brief.md)
  and its [review, baseline lock and SC-031 proposal](iteration_13/02_proposals/02_state_reconciliation_and_SC-031.md),
  with the [RD-1 saved-history audit](iteration_13/02_proposals/rd1_saved_history_audit/audit.py).
- [Iteration 13 closeout](iteration_13/01_results.md): SPD-008 versus the clean hybrid on all six common starts; [SC-030 evidence](../../../results/validation/shape_continuation/SC-030-spd008-comparison/README.md).
- [Iteration 12 closeout](iteration_12/01_results.md): all 36 strategy endpoints,
  decisions and next questions; [SC-029 evidence](../../../results/validation/shape_continuation/SC-029-atlas-strategies/README.md).
- [Independent consolidated-atlas audit](iteration_10/01_results.md),
  [strategy proposals](iteration_10/02_proposals/01_atlas_strategies.md), and
  [SC-029 frozen contract](iteration_11/03_plan.md).
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
  SC-001 through SC-041, with raw measurements, scripts, checkpoints and failures.
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
| [12](iteration_12/01_results.md) | SC-029 complete: 36 endpoints, five hard stops. Neither first-band protection nor added frequencies passes the robustness criteria. Extra work on old data improves all six baseline cases; local frequency benefits depend on the prefix. |
| [13](iteration_13/01_results.md) | SC-030 complete: 36 runs. Exact reuse cuts hybrid inversion time 12.62% with identical trajectories; the fixed ladder has lower RMS error on all six common starts. SPD hard-stops on three cases and completes the other three with large errors. Native geometry/guards differ; this is not a full topology comparison. The [research brief review](iteration_13/02_proposals/02_state_reconciliation_and_SC-031.md) finds that the hard cases collapse in stage 1 and proposes SC-031 (not approved). |
| [14](iteration_14/01_results.md) | SC-031: Hanke regularizing LM with an L² or curvature-change metric does not avoid the stage-1 collapse (C/peanut ≈ 2 mm), although the metric is active and ρ ≈ 1. The gate withheld stages 2–4. R2 fits stage-1 data much better; SC-032 (withheld stage B) is proposed. |
| [15](iteration_15/01_results.md) | SC-032: the curvature metric (R2) improves kite/peanut/C with no case worse (GM 0.832), but misses the ≤ 0.8 bar; Hanke + L² is worse than R0; the collapse remains. R0 stays the baseline. SC-033 (Borges eq. 13 admissibility filter) is proposed. |
| [16](iteration_16/01_results.md) | SC-034 (user-directed): restoring the legacy controls fixes SC-030's SPD baseline. The ladder is the operative control: SPD-L recovers circle, star and peanut to ≤ 3.3e-5 mm and kite to 1.25 mm; the step controls do not help. The hybrid's peanut collapse is not a property of the 0.5 GHz data. SC-035 (band-limited hybrid state) is proposed. |
| [17](iteration_17/01_results.md) | SC-036: a ray path with the same first-order normal velocity allows larger useful steps at early peanut/kite corners (3.15x decrease at peanut state 3), yet both paths fail at the terminal peanut corner. Full inverses are mixed: peanut and star improve, kite and C worsen. Coordinate controls separate changes of basis from different physical subspaces. The ray path is not adopted. |
| [18](iteration_18/01_results.md) | SC-035: a centred state band K 8/12/16/20 with the complete-construction derivative cuts peanut/C/kite RMS to 0.14/0.47/0.57 mm (original hybrid 2.94/3.20/2.98); star regresses 16%. The matched K=192 controls hard-stop on three cases. A final K=192 release adds almost nothing. |
| [19](iteration_19/01_results.md) | SC-037: the wider ladder K 8/16/32/64/192 restores star (0.53 mm) but C worsens 27.65% against SC-035, failing the frozen 25% gate. The timing of the release is a case-dependent prior. The autonomous run stops; the next step is the user's decision. |
| [20](iteration_20/01_results.md) | SC-038: all-frequency M=11/15/19 release reduces C RMS 0.4895 → 0.0241 and kite 0.5518 → 0.1096 mm against matched M=9 controls. Kite needs a denser-grid replay, is time-limited, and retains a sharp feature (0.0908 mm radius versus truth 2.138). All audits pass; no default promoted. |
| [21](iteration_21/01_results.md) | SC-039: raw boundary data (traces, geometry, full predictions; 19 frequencies, 512/1024 nodes) at all 867 accepted states of 34 trajectories plus 6 truths. Stored traces reproduce `shape_jacobian` to 1e-15 in any basis; 1,114 saved losses rebuilt bitwise. Data only. |
| [22](iteration_22/01_results.md) | SC-040: current pipeline on all six scenes with atlas videos. Star ends at 0.142 mm RMS; all four new endpoint audits pass. The historical QR display is subsequently qualified as heuristic in SC-041. |
| [23](iteration_23/01_results.md) | SC-041: complete-update forecasts nominate useful star M=22/25 releases; M=25 reaches 0.0476 mm RMS. Kite M=22 reaches 0.0730 mm but sharpens its point and stops at numerical qualification. Nominal RMS radius does not ensure finite validity; five endpoint audits pass, no controller promoted. |
| [24](iteration_24/01_results.md) | SC-042: 24 matched state-treatment suffixes. Initial cleanup repairs the kite artifact; recurrent cleanup/cap give essentially tied geometry. One-off development gate passes, with common-work RMS ratio 0.9846; three original timeouts retain separate later qualifications. |
| [25](iteration_25/01_results.md) | SC-044: six prefixes and 18 fresh-shape/noise suffixes. Cleanup/cap avoid one noisy-C numerical stop, with common-work RMS ratios 0.909/0.908; most datasets tie. Local curvature artifacts remain. Original transfer gates retain two separately qualified audit timeouts. |
| [26](iteration_26/01_results.md) | SC-043: all 18 prospective policy paths and audits complete. Atlas RMS GM ratios 1.11301 versus fixed and 1.00512 versus stagnation, with 1,368 diagnostic units; both superiority gates fail. Kite stays at M22 and is 88%/68% worse in RMS. All radius constraints are inactive. The full campaign closes at 49,120 recorded units plus up to 130 unrecorded from the retained lost audit. |
| [27](iteration_27/01_results.md) | SC-047: coupled non-star-shaped physics and complete derivative qualify; 12 local endpoints pass, with worst RMS 0.74–1.03 mm from 3.81 mm. Conditional object selection loses its cost/accuracy gate. Current-scene topological response qualifies, but false births and failed localization withhold actions. |
| [28](iteration_28/01_results.md) | SC-048: one intrinsically perturbed close pair, three qualified endpoints. M5 / M9 / global enrichment RMS 0.705 / 2.72 / 3.58 mm from 3.90 mm. Global enrichment fails its primary gate; transfer cases are withheld without retuning. |
| [29](iteration_29/01_results.md) | SC-049: one full far-circle-to-C attempt. Seven accepted updates worsen geometric error; the next candidate fails field refinement. CPU controls reproduce the endpoint discrepancy. Initial atlas qualifies; returned atlas does not. No recovery or restart. |
