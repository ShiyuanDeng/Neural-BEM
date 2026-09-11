# Boundary–BIE track: start here

This is the handoff for agents working on the **boundary representation and BIE
solve** research track. Read the current state below before choosing work. The
shared folder convention, approval rule, experiment-contract template and
collaboration rules are in the [iterations README](../README.md).

## Research question and scope

> **Which properties of smooth-boundary representations can improve the
> accuracy, conditioning, differentiation, or cost of the BIE inverse?**

The track is organised around that question, not around one representation.
Fourier curves are the case in hand, but the question is about smooth
parameterised boundaries generally: how the geometry unknowns, the boundary
trace, the formulation and the derivative path fit together.

**Replacing the Kress/Nyström discretisation is not assumed to be the goal.**
It is one candidate outcome among several, and the track's first deliverable is
to decide which mechanism is worth prototyping — not to prototype all of them.

Three families of candidate direction, kept separate:

1. **Geometry and optimisation coordinates** — parameterisation freedom, the
   current gauge restrictions, and what the gauge costs.
2. **Boundary-field representation and formulation** — modal traces, weak and
   Galerkin formulations, against the current nodal Nyström collocation.
3. **Derivatives, preconditioning, and physically meaningful optimisation
   metrics** — including the analytic discrete derivative that exists for a
   single interface but is not wired to the multi-component explicit path.

Three resolutions must be kept distinct throughout and **must not be assumed
equal or coupled**:

| Symbol | Meaning | At the baseline |
|---|---|---|
| `K_gamma` | geometry Fourier bandwidth, per component | 1–9 depending on case and continuation stage |
| `K_u` | boundary-**trace** bandwidth | **does not exist** — traces are nodal, not modal |
| `N` | Nyström quadrature resolution | 64 production, 128 refined, per component |

A weak/Galerkin BIE **discretisation** and a soft physics-residual **penalty in
an optimisation loss** are different research interventions with different
failure modes. Do not conflate them.

## Baseline

[B0 — 2026-09-10](../../baselines/B0_2026-09-10.md). Commit `e34ed5f` on
`feature/ordered-boundary-nystrom`. Recorded as `e34ed5f` plus an uncommitted
working tree; that source was committed on 2026-09-11 as **`345038a`**, which is
what to check out. B0 §9 lists what it pins for this track; §7 records the
representation-scope distinction this track must not blur.

## Current handoff

Updated 2026-09-11.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 01](iteration_01/02_proposals/01_boundary_bie_research_brief.md) |
| Stage | **Proposal drafted; no review, no agreed plan.** The track opens from a brief; there is no prior cycle in this track to produce `01_results.md` |
| Approved experiment IDs | **None.** `BIE-001`, `BIE-003`–`BIE-005` are `PROPOSED — NOT APPROVED FOR EXECUTION`; `BIE-002` is a reserved ID with no contract yet — `BIE-001` is meant to write it |
| Execution status | `NOT STARTED`. No code changed, no prototype written, no run launched |
| Next expected action | A review of the brief that resolves each candidate direction as accept / reject / defer / named diagnostic, and decides whether `BIE-001` — a comparison and *selection* of one discriminating prototype — is the right first deliverable |
| Owner / reviewer | `unassigned` / `unassigned` |
| Dependencies | None blocking. `BIE-001` is a desk study over existing code and bundles. Any prototype selected by it will touch shared solver interfaces and must be declared before implementation |
| Blockers | None |
| Open question the review must not skip | Whether a modal-trace prototype is the right first prototype. It is a candidate, deliberately **not** pre-selected |

## Reading order

1. This handoff.
2. [Baseline B0](../../baselines/B0_2026-09-10.md) — §2 (drivers and
   configuration), §5 (acceptance and stopping rules), §6 (what the two
   optimizer paths actually are), §7 (gauge policy versus representation), §8
   (limitations).
3. [The boundary–BIE research brief](iteration_01/02_proposals/01_boundary_bie_research_brief.md).
4. Mechanism sources, in this order:
   - `solvers/gpr_bem_kress/README.md` — the forward's deliberately narrow
     geometry boundary and its adjoint contract;
   - `solvers/gpr_bem_kress/system.py` and `operators.py` — the Müller system as
     actually assembled;
   - `solvers/gpr_bem_kress/shape_derivative.py` — the analytic **single-
     interface** discrete derivative, and who consumes it;
   - `solvers/sdf_inverse/radial_topology.py:897` — `run_multiradial_fd_inverse`,
     the finite-difference optimizer the explicit multi-component path uses;
   - `solvers/sdf_inverse/curve_updates.py:1399` — the gauge-fixed subspace and
     its dimension.
5. [Cartesian pipeline guide](../../pipelines/explicit_cartesian_fourier.md) for
   the two optimizer paths and the representation limits, and
   [Cartesian iteration-1 plan](../cartesian_fourier/iteration_01/03_plan.md)
   for why the parameterisation, not the bandwidth, set the accuracy ceiling.

## Proposed validation order for any prototype

Whatever mechanism `BIE-001` selects, the prototype is validated in this order,
and does not advance to the next step until the previous one passes:

1. **Fixed geometry**, against the current forward reference — same curves, same
   acquisition, agreement to a declared tolerance.
2. **Derivative checks**, if and only if the derivative path changes.
3. **Saved difficult geometries around topology events** — the pre-event and
   post-event states stored in the controller bundles' `trajectory.json`, where
   quadrature and conditioning are most stressed.
4. **Integration into automatic topology search**, only after 1–3 pass.

## Starting work on this track

**Current gate: 2 of 7 — a review of the brief.** See the shared
[gate sequence](../README.md#from-brief-to-execution) for what each gate means
and what moves it.

Until a named experiment ID is approved by the user, an agent on this track
**may** read the evidence, write a review, propose experiments, and update these
documents. It **may not** change numerical code, alter an experiment
configuration, or launch a run.

When an ID is approved, work on it in its own branch — `track/boundary-bie-BIE-001` —
and never in a checkout another track is using. `BIE-001` is a desk study over existing code and bundles — no runs, no production edits — so it needs no branch of its own until it selects a prototype.

## Relationship to the existing cycles

This track does not move, renumber or supersede the Cartesian-Fourier or
radial-Fourier-topology histories. It cites them as starting evidence. The
Cartesian-Fourier cycle's iteration-2 open question about the re-gauge accuracy
floor belongs to this track's §1 direction, and the cycle's own record of it
stays where it is.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| 01 | Which boundary-representation mechanism is worth prototyping for the BIE inverse | Active; brief drafted, nothing approved, nothing executed |
