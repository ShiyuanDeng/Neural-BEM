# Topology track: start here

This is the handoff for agents working on the **topology** research track. Read
the current state below before choosing work. The shared folder convention,
approval rule, experiment-contract template and collaboration rules are in the
[iterations README](../README.md).

## Research question and scope

> **How can the inverse choose and execute topology changes more reliably,
> without a prescribed object count or excessive BIE cost?**

The track is organised around that question, not around one representation. It
inherits the shared automatic controller that the
[radial-Fourier-topology cycle](../radial_fourier_topology/README.md) built and
the [Cartesian-Fourier cycle](../cartesian_fourier/README.md) matched; both
charts are in scope, and so is any future geometry owner.

Four intervention points are treated as **separate** research targets:

| Point | What it decides | Implementation / original B0 location |
|---|---|---|
| **Event triggering** | *When* a topology pass is proposed at all | `topology_controller.py:562` |
| **Candidate construction** | *Which* discrete events are even considered | `generate_topology_candidates`, `topology_controller.py:333` |
| **Candidate refinement / budget allocation** | *Which* candidates get optimizer effort before they are compared | `_refinement_shortlist` in `topology_controller.py` |
| **Event acceptance** | *Whether* the winner is committed | `topology_controller.py:631`–`:654` |

An experiment should move one of these at a time unless it says why not.

Out of scope for this track unless separately raised: nested holes, touching or
intersecting boundaries, multi-material topology, measurement noise, and neural-
owned geometry inside the topology loop. None of these is demonstrated at the
baseline.

## Baseline

[B0 — 2026-09-10](../../baselines/B0_2026-09-10.md). Commit `e34ed5f` on
`feature/ordered-boundary-nystrom`. Recorded as `e34ed5f` plus an uncommitted
working tree; that source was committed on 2026-09-11 as **`345038a`**, which is
what to check out. `e34ed5f` alone predates the corrections. B0 §9 lists exactly
which controller behaviour the baseline pins.

## Current handoff

Updated 2026-09-12.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 08 results](iteration_08/01_results.md) |
| Stage | TOP-010 complete. Four optimizer/representation defects are now found and fixed, **each improving the objective and none improving the reconstruction** |
| Approved experiment IDs | `TOP-001`, `TOP-005`, `TOP-006`, `TOP-007` approved 2026-09-11; `TOP-008` and `TOP-009` approved 2026-09-12 by the user's direction to implement the Codex plan and keep going. `TOP-002`–`TOP-004` remain proposals |
| Execution status | TOP-008 `COMPLETE`, TOP-009 `STOPPED AT STAGE 2` with its reading corrected twice, TOP-010 `COMPLETE`. TOP-010 refutes the local-minimum reading operationally: the terminal gradient is 4013x the optimizer's own tolerance with a full-rank Jacobian, and three restarts of the **unmodified** optimizer recover 1.7x in the objective — while matched error moves 11.849 to 11.991 mm and IoU stays at 0.7088. 581 tests pass; all three mechanisms remain opt-in and off; no controller default changed |
| Next expected action | **Review [TOP-011](iteration_08/02_proposals/01_sensitivity_and_conditioning.md), then decide [TOP-012](iteration_08/02_proposals/02_acquisition_change.md). Neither approved.** The question is no longer which optimizer defect to fix — four have been found and fixed, each worth objective and none worth geometry. It is why the gated geometry is insensitive to four orders of magnitude of training objective: the final K=9 state satisfies the frozen 0.003 data tolerance at 8.7878e-05 while sitting 11.849 mm from the truth. TOP-011 measures how many millimetres of boundary movement hide inside that tolerance, per singular direction, with no source change. TOP-012 is gated behind it and needs a **user decision**, because every acquisition route creates a v2 benchmark — though adding source/receiver pairs at 0.5 GHz would enrich the data without touching the 1.5/2.5 GHz holdout, unlike adding frequencies. Default-policy decisions remain separate |
| Owner / reviewer | TOP-008 and TOP-009 implementation: Claude; literature verdict and independent source/evidence review: Codex. Codex repaired omitted promotion counters; 108 focused regression tests pass |
| Dependencies | Shared controller/driver changes declared in each cycle's review before implementation; no physical solver or geometry-state interface changed |
| Blockers | Four explanations tested, each real and none sufficient: the derivative, capacity, ladder truncation and premature stopping. The benchmark still passes 5/12. What blocks recovery is the decoupling between the training objective and the gated geometry at this scale, which is a sensitivity and conditioning question. Three scenes still time out |

## Reading order

1. This handoff.
2. [Baseline B0](../../baselines/B0_2026-09-10.md) — especially §5 (acceptance
   and stopping rules), §6 (demonstrated scope) and §8 (limitations).
3. [The topology research brief](iteration_01/02_proposals/01_topology_research_brief.md)
   — the question decomposition and the four candidate experiments.
4. Starting evidence, in this order:
   - [Cartesian iteration-3 results](../cartesian_fourier/iteration_03/03_results.md)
     — the eight matched cases and the split discrepancy that motivates `TOP-001`;
   - [its implementation record](../cartesian_fourier/iteration_03/02_implementation.md)
     — written around the five failures that shaped the controller's design;
   - [the September 10 pipeline audit](../../../results/validation/cartesian_fourier/pipeline-audit-20260910/README.md)
     — the freshest numbers, and the only bundle pinned to B0 by source hash;
   - [radial iteration-2 results](../radial_fourier_topology/iteration_02/01_results.md)
     and [its topology-treatment record](../radial_fourier_topology/iteration_02/03_results.md)
     — where birth, death, split and merge came from.
5. `solvers/sdf_inverse/topology_controller.py` and
   `solvers/sdf_inverse/radial_topology.py` for the mechanisms themselves.

## Starting work on this track

All future performance evaluations must include the complete
[frozen topology scene benchmark](../../benchmarks/topology_scenes.md), with
per-scene successes and failures. Preserve v1 scenes, observations and gates;
declare changed budgets/acquisition as a separate comparison.

**TOP-001, TOP-005, TOP-006 and TOP-007 gate 7 closeouts are complete.** TOP-007 was
APPROVED by the user's 2026-09-11 direction to take Track A as far as possible and
to continue from the latest fixes; execution is COMPLETE. Current branch: `feature/ordered-boundary-nystrom`. The per-experiment branches
are removed once merged, at the user's direction: `track/topology-TOP-005` after
that cycle, and `track/topology-TOP-001` (tip `746c9fb`) on 2026-09-11, once its
commits were contained in this branch. The executed plans still name the branch
each cycle used, which is a record of what happened, not a checkout that exists. Preserve completed bundles and the
failed historical qualification. The old brief remains an unedited proposal;
the plan and amendment carry the actual decisions. Boundary–BIE work is separate.

## Relationship to the existing cycles

This track does **not** move, renumber or supersede the radial-Fourier-topology
or Cartesian-Fourier iteration histories. Those cycles stay where they are and
remain the record of what was decided and measured. This track cites them as
starting evidence and carries the forward-looking work.

Findings that are about the *shared controller* rather than about one chart
belong here. Three such findings already exist in the Cartesian iteration-3
record — the candidate-polish rule that decides a split, the feature-radius
certificate, and the trust region's dependence on coordinates.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| 01 | Reliability of topology event triggering, construction, refinement allocation and acceptance | TOP-001 and declared extensions complete; no default change |
| 02 | Selective refinement after raw-shortlist failures | TOP-005 complete; all declared gates pass |
| 03 | Broader automatic-controller scenes | TOP-006 complete; v1 benchmark established, current policies pass 5/12 scenes |
| 04 | Refined feasibility, shape capacity and held-out prediction | TOP-007 proposed, reviewed, planned and executed |
| 05 | Why finished runs still return wrong shapes | Results recorded; guard opt-in; literature verdict ranks corrections and qualifies earlier causal claims; written next steps only |
| 06 | Feasible finite differences and the capacity contract | TOP-008 complete; TOP-009 implemented opt-in |
| 07 | Bandwidth ladder and interpretation review | TOP-009 stage-2 gate failed; stages 3/4 preserved; independent review corrects stationarity/data claims and proposes TOP-010 |
| 08 | Stopping versus stationarity | TOP-010 complete; neither saved state is stationary, restarts recover 1.7x objective and no geometry |
