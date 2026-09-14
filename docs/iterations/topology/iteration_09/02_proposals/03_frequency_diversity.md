# TOP-015 — frequency diversity, and the holdout it destroys

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION. **Requires a user
  decision**, because it destroys the frozen evaluation contract.
- **Execution status:** NOT STARTED
- **Owner:** unassigned. **Reviewer:** unassigned.
- **Baseline:** the TOP-012 route-A result and the TOP-011 measurement.

## Why it is now the only acquisition route left

[TOP-012](../../iteration_08/02_proposals/02_acquisition_change.md) route A
doubled the ring to 48 source/receiver pairs at 0.5 GHz and changed **nothing**:
the permitted boundary movement moved by one part in ten thousand, the same 47
of 68 directions still exceeded the 1 mm gate, and the condition number got
1.7% *worse*.

It also said why, at zero solve cost. The added positions carry the same
response energy as the original ones — observed-norm ratio **1.41421376**
against √2 = 1.41421356 — and produce the same singular values to seven digits.
The new rows of the Jacobian **add no direction and reweight nothing**. At
0.5 GHz the scattered field around a 0.30 m ring is angularly band-limited to a
handful of harmonics and 24 positions already sample it well above that band.

So spatial sampling at the training frequency is exhausted. **Frequency is the
only acquisition axis left**, which is what the
[literature verdict](../../iteration_05/02_proposals/03_literature_verdict.md)
ranked and deferred, and what Borges–Greengard continuation actually rests on.

## The cost, stated before anything runs

Frozen v1 trains at 0.5 GHz and reserves **1.5 and 2.5 GHz** for evaluation
only. Training on additional frequencies **destroys that holdout**: once
1.5 GHz is fitted, no result at 1.5 GHz is held out, and every holdout number in
TOP-006 through TOP-012 becomes incomparable. A new, never-fitted evaluation set
must be generated and then left alone.

That is why this needs a user decision and cannot be inferred from the fact that
route A failed.

## Question

Does the boundary displacement permitted inside the 0.003 tolerance shrink, and
does matched error improve on the failing scenes, when the training acquisition
spans frequencies rather than angles?

## Falsifiable hypothesis

If the shortage is bandwidth, added frequencies lift the small singular values
and shrink the permitted movement. If the spectrum is unchanged the way route A
left it unchanged, the limit is not acquisition at all, and the objective, the
representation or the optimizer's model — see
[TOP-013](01_curvature_blind_directions.md) — carry the explanation.

## Order

**Run [TOP-013](01_curvature_blind_directions.md) first.** It is cheaper, it
needs no new data, it destroys no evaluation contract, and it addresses the
sharper of TOP-011's two findings. Buying data that costs the holdout, before
testing a hypothesis that costs nothing, would repeat the mistake TOP-012's own
contract was written to avoid.

## Intervention, if approved

A `v3` specification with additional training frequencies and a **fresh,
never-fitted** holdout set, its oracle convergence re-checked rather than
assumed. The cheap TOP-011-style sensitivity measurement runs first, before the
twelve-scene suite, exactly as TOP-012 ordered its stages. v1 and v2 stay
byte-identical.

## Controls

Identical scenes, truths, materials, resolutions, budgets, gates and controller
policy. Acquisition is the only difference. The 0.003 tolerance is not loosened
and no gate is re-tuned.

## Budget, to be declared before execution

Oracle generation for the v3 acquisition and holdout, the sensitivity stage, and
a twelve-scene comparison under the v1 ceilings — each declared with explicit
solve and wall-clock caps before any run.

## Decision criteria

Per gate, on all twelve scenes, against the same policy on v1 data, with the
enriched arm reporting what it cost in solves. No result transfers back to v1 or
v2.

## Artifacts

`config/topology_scenes_v3.json` and
`results/validation/topology/TOP-015-<run-id>/`.


## Status amendment — 2026-09-14

**SUPERSEDED by TOP-016.** The user adopted the bounded [fixed-topology pilot](../03_plan.md) and [recovery-reset review](04_recovery_reset_review.md). TOP-015 was not executed. Its original proposal remains above as historical context.
