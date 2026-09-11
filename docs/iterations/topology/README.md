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

| Point | What it decides | Where it currently lives |
|---|---|---|
| **Event triggering** | *When* a topology pass is proposed at all | `topology_controller.py:562` |
| **Candidate construction** | *Which* discrete events are even considered | `generate_topology_candidates`, `topology_controller.py:333` |
| **Candidate refinement / budget allocation** | *Which* candidates get optimizer effort before they are compared | `topology_controller.py:610`–`:617` |
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

Updated 2026-09-11.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 01](iteration_01/02_proposals/01_topology_research_brief.md) |
| Stage | **Proposal drafted; no review, no agreed plan.** The track opens from a brief, not from `01_results.md` — there is no prior cycle in this track to produce one |
| Approved experiment IDs | **None.** `TOP-001` … `TOP-004` are all `PROPOSED — NOT APPROVED FOR EXECUTION` |
| Execution status | `NOT STARTED`. No code changed, no run launched, no instrumentation added |
| Next expected action | A review of the brief that resolves each candidate as accept / reject / defer / named diagnostic, and in particular decides whether `TOP-001` is the right first experiment |
| Owner / reviewer | `unassigned` / `unassigned` |
| Dependencies | `TOP-001` needs solve-count instrumentation in `run_fourier_topology_controller.py`, which currently records none (B0 §8.4). That is part of `TOP-001`'s scope, and it touches a driver the boundary–BIE track also uses |
| Blockers | None. The starting evidence exists and the saved pre-event states needed for replay are present in the committed bundles |

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

**Current gate: 2 of 7 — a review of the brief.** See the shared
[gate sequence](../README.md#from-brief-to-execution) for what each gate means
and what moves it.

Until a named experiment ID is approved by the user, an agent on this track
**may** read the evidence, write a review, propose experiments, and update these
documents. It **may not** change numerical code, alter an experiment
configuration, or launch a run.

When an ID is approved, work on it in its own branch — `track/topology-TOP-001` —
and never in a checkout another track is using. `TOP-001` additionally requires adding solve-count instrumentation to `run_fourier_topology_controller.py`; that driver is shared with the boundary–BIE validation path, so declare the change before implementing it.

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
| 01 | Reliability of topology event triggering, construction, refinement allocation and acceptance | Active; brief drafted, nothing approved, nothing executed |
