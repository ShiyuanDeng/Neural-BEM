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

Updated 2026-09-15.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 04 results](iteration_04/01_results.md) |
| Stage | BIE-006 COMPLETE: stop first-order operator reuse; no accuracy-range benefit or qualifying savings |
| Approved experiment IDs | **BIE-002, BIE-004, BIE-006 APPROVED** by explicit user instructions; [BIE-006 plan](iteration_03/03_plan.md) |
| Execution status | **BIE-006 COMPLETE**; [result bundle](../../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md) |
| Next expected action | [SPD-002](../speedup/iteration_03/01_results.md) completed default promotion and two full-case speed/recovery checks; broader recovery coverage remains open |
| Owner / reviewer | Codex / self-review; no independent reviewer claimed |
| Dependencies | Coupled derivative integrated by SPD-001; user-requested analytic/fast-CPU default promotion is tracked by [SPD-002](../speedup/iteration_02/03_plan.md) |
| Blockers | First-order reuse did not meet its benefit gates; SPD-001 qualifies integration and one update, not full inverse recovery |
| BIE-001 disposition | **SUPERSEDED** by the [current review](iteration_01/02_proposals/03_current_checkout_review.md) and BIE-002; no BIE-001 numerical execution |
| Deferred | BIE-003, BIE-005 and broader recovery coverage; integration/default validation is recorded in the speed-up track |

Related discussion: [Are the current failures intrinsic to boundary methods?
What FDTD would change](../topology/iteration_07/02_proposals/02_boundary_methods_and_fdtd.md).
This records the user's solver-alternative question, distinguishes solver and
geometry-representation changes, and suggests a matched forward/derivative
check. It is not the full review of the Boundary–BIE brief, and no FDTD
comparison was run for it.

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

**Current gate: 7 of 7 — BIE-006 closeout complete.** See the
[agreed plan](iteration_03/03_plan.md). Work on the existing
`feature/ordered-boundary-nystrom` branch; no branch or worktree creation.
The user identified active topology fixes: keep the diagnostic in its isolated
experiment directory and leave shared solver/topology files read-only. Stop
measurements on imported numerical source drift. The user authorized Idea 3 with
“then go”; BIE-006 is the concrete bounded contract. No further successor is included.

## Relationship to the existing cycles

This track does not move, renumber or supersede the Cartesian-Fourier or
radial-Fourier-topology histories. It cites them as starting evidence. The
Cartesian-Fourier cycle's iteration-2 open question about the re-gauge accuracy
floor belongs to this track's §1 direction, and the cycle's own record of it
stays where it is.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| 01 | Which boundary-representation mechanism is worth prototyping for the BIE inverse | BIE-002 approved and completed; BIE-001 desk-study superseded |
| 02 | BIE-002 modal/structure evidence | BIE-004 approved and completed under later user instruction |
| 03 | Coupled analytic Jacobian qualification and cost | BIE-006 approved and completed under later user direction |
| 04 | First-order operator reuse accuracy/range/cost | BIE-006 complete; stop this first-order approach; no successor executed |
