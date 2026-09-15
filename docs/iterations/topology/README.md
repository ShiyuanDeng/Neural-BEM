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

Updated 2026-09-15.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 13 results](iteration_13/01_results.md); iteration 12 retains the executed TOP-019 plan |
| Stage | TOP-019 COMPLETE: both K=17 merge arms recover and qualify; F improves precision at higher cost |
| Approval | TOP-019 APPROVED on 2026-09-15 by the user’s “go” response to its explicit audit/conditional-pair request; [plan](iteration_12/03_plan.md). TOP-018 retains its completed [approved contract](iteration_11/03_plan.md) |
| Next expected action | Scope one fresh automatic two-star controller/continuation check, without a supplied count or saved COMMON start. [Decision](iteration_13/01_results.md#decision-and-next-step) and [completion roadmap](#completion-roadmap); no successor ID or execution is approved |
| Owner / reviewer | TOP-019: Codex `/root`, owner implementation/closeout review; no independent review claimed. TOP-018 retains its owner review; TOP-017 retains its historical independent review |
| Deferred / superseded | TOP-013 and TOP-014 not selected for execution; TOP-015 SUPERSEDED by TOP-016; TOP-002–004 remain deferred |
| Evidence interpretation | Fresh central, saved-common-start two-star F, and the new K=17 merge S/F pair pass their contracts. Fresh automatic two-star recovery and twelve-scene qualification remain untested. The old K=9 merge regression is preserved; it does not recur in TOP-019 |
| Git scope | Consolidated by user direction into `/home/drdeng/Neural_SDF_BEM_AD`, branch `feature/ordered-boundary-nystrom`. Ask the user explicitly before any new branch/worktree, even in full-access mode |

TOP-001, TOP-005–012, TOP-016, TOP-017, TOP-018 and TOP-019 have recorded approvals and completed closeouts. TOP-016's [bounded fixed-count results](iteration_10/01_results.md) report passed information screens, incomplete principal comparisons, and an adverse completed merge control. This is not twelve-scene qualification.

The later [engineering result bundle](../../../results/validation/topology/TOP-017-followup-20260914-engineering/README.md)
and [fresh-run video](../../../results/validation/topology/TOP-017-followup-20260914-engineering/fresh_circle_to_ellipse_star.mp4)
record the user-requested implementation follow-up. Existing numerical defaults
and historical measurements are preserved; validated work is committed locally.

TOP-018's supplied review predates that follow-up. Its [completed bundle](../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/README.md)
reuses the verified predictions, qualifies the remaining checks, and completes
the matched pair. The final F boundary error is 0.00167644 mm, versus S's
11.793168 mm. A post-schedule reporting type error and both worker exits are
preserved; metadata was repaired without new physical solves. No new branch or
worktree was created, and no push is authorized by the experiment contract.

TOP-019's [completed merge bundle](../../../results/validation/topology/TOP-019-20260915-144340-qualified-merge/README.md)
records both qualified recoveries: S ends at 0.0860067 mm / 0.0116406 worst
prediction error, F at 0.0214283 mm / 0.00229358. F uses 3.77× the solves for
4.01× boundary and 5.08× prediction accuracy. Total new work is 6,232 solves,
zero failed; 84 pre-dispatch tests and final artifact verification pass. Keep F
as the development candidate for the next integration check and S as a successful
lower-cost merge control. No production promotion or successor is approved.

## Completion roadmap

Recorded 2026-09-15 so a new session can resume from this handoff without chat
history. **The topology work is not complete.** The validated fresh central
pipeline and saved-common-start two-star continuation establish the successes
above; TOP-019 now adds qualified merge-control recovery. The broader automatic
controller still needs qualification. TOP-018 and TOP-019 are complete.

Proceed in this order, with later work conditional on the preceding evidence:

1. **Resolve the merge regression with a capacity-qualified comparison — complete
   for the bounded TOP-019 protocol.** The [iteration-13 closeout](iteration_13/01_results.md)
   records both K=17 S/F recoveries from a coefficient-identical, zero-padded
   original controller start. The truth projection was evaluation-only. F has
   better boundary/prediction accuracy and higher work; both arms pass the
   original gates. Preserve the historical K=9 adverse result and the changed
   resolution/quota conventions. This does not qualify a universal K=17 policy.
2. **Qualify fresh automatic two-star recovery — next scoping decision.** The
   merge result supports further qualification of F; separately scope a run from
   the frozen original distant
   circle through the topology controller and continuation, without a supplied
   object count or the saved COMMON checkpoint. Check topology-event validity,
   final count, geometry, prediction and work. Preserve the fresh central
   success as a regression control. TOP-018's fixed-count result cannot replace
   this integration check.
3. **Qualify the complete frozen twelve-scene comparison.** After focused
   controls pass, compare candidate and reference on every scene in the
   [v1 benchmark](../../benchmarks/topology_scenes.md), retaining all failures
   and attempted/completed work. Preserve v1 inputs and gates; changes to
   acquisition, mode schedules, numerical resolution or budgets must be explicit
   in a separately named comparison. Report each recovery criterion, numerical
   qualification and cost, rather than only optimizer completion or pass count.
4. **Close the topology work against declared acceptance criteria.** A closeout
   must account for the merge regression, fresh two-star integration and all
   twelve scene outcomes, with the required recovery, numerical, cost and
   regression gates satisfied. Unresolved required failures keep the work open;
   any narrower completion claim needs an explicitly agreed scope. Promotion
   requires a measured decision and reproducible artifacts.

**Restart action:** read this handoff, [iteration 13](iteration_13/01_results.md),
the completed [TOP-019 plan](iteration_12/03_plan.md), and the
[shared workflow](../README.md). Prepare the fresh automatic two-star contract;
do not replay the completed merge pair. Steps 2–4 remain conditional, with no
successor IDs, budgets or execution approval assigned. Use the existing checkout
and branch recorded above.

## Reading order

1. This handoff and [the latest iteration-13 results](iteration_13/01_results.md).
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

Controller performance qualifications must include the complete
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
| 09 | Tolerance, acquisition, and recovery reset | TOP-011/012 complete; TOP-013/014 deferred, TOP-015 superseded; TOP-016 approved and executed from the iteration-09 plan |
| 10 | Bounded fixed-topology continuation | TOP-016 results reviewed; TOP-017 approved and executed from saved endpoints |
| 11 | Central recovery and numerical qualification | TOP-017 and engineering follow-up complete. TOP-018 approved and executed under its bounded audit/conditional-pair contract |
| 12 | Qualified two-star paired recovery | TOP-018 complete; TOP-019 approved and executed from the iteration-12 plan |
| 13 | Capacity-qualified merge recovery | TOP-019 complete: both arms recover; F improves precision at higher cost. Fresh automatic two-star integration is the next scoping decision |
