# TOP-011 and TOP-012 — measure the tolerance, then buy the only data that is free

- **Approval status:** **APPROVED** for `TOP-011` and `TOP-012` under the
  user's 2026-09-12 direction, given after the two contracts were written and
  named: *"keep fixing stuff. top 011 and 012? just go as far as you can. dont
  stop after each fix, keep iterating"*. That names both IDs. It does not widen
  either contract, and this plan does not widen them either.
- **Execution status:** IN PROGRESS. TOP-011 `COMPLETE`; TOP-012 `IN PROGRESS`.
- **Owner:** Claude. **Reviewer:** unassigned.
- **Baseline:** `4d79027` on `feature/ordered-boundary-nystrom`; the TOP-009
  stage-4 ladder endpoint and the TOP-010 restart plateau, their data, chart and
  `K = 9`.
- **Branch:** continue `feature/ordered-boundary-nystrom`; no new branch.

## The user decision TOP-012 required

[TOP-012](02_proposals/02_acquisition_change.md) could not start without a user
choice between three acquisition routes, because each one changes what the
frozen v1 data contract means. The direction above is to go as far as possible,
which selects the route the contract itself recommends and which costs the least
to interpret:

> **Route A — more spatial diversity at 0.5 GHz.** Additional source/receiver
> pairs at the existing *training* frequency. 1.5 and 2.5 GHz are never fitted,
> so the frequency holdout keeps its meaning and every recorded holdout number
> stays comparable.

Routes B and C are **not** taken. B destroys the holdout, C confounds two
effects, and neither is justified before route A has said whether angular
coverage is the shortage. That is a recorded decision, not a deferral by
silence.

## Order, and why it is not negotiable

TOP-011 runs first and TOP-012 reads its answer. TOP-012's own contract gates it
that way — *"this proposal should not run before that one, which would otherwise
buy data to fix a problem not yet shown to be about data"* — and the gate is
kept even though both IDs are approved together.

## TOP-011 — how much geometry hides inside the data tolerance

**Diagnostic only. No source change, no controller default, no new arm, and no
state advanced or saved as a reconstruction.**

At each of the two saved states, assemble the reduced Jacobian with the
feasible-side stencil at FD steps **1.0e-4, 5.0e-5 and 2.5e-5**, take its SVD,
and record the spectrum's stability across those scales. Then, for each
right-singular direction `v_i` and **each sign**:

1. Solve the linear model for the step length `t` at which the predicted
   relative L2 error reaches the frozen **0.003** tolerance. Because the
   training set is a single frequency, `‖residual‖₂` *is* the relative L2 error
   exactly, so this is a quadratic with a closed form rather than an estimate.
2. Find the largest feasible `t` along that ray by bisection against the
   optimizer's own feasible set — radius floor, then both resolutions. Those
   checks build curves rather than solving the BIE, so the feasibility search
   costs no forward solves.
3. Evaluate the **actual** objective there. If the measured relative L2 exceeds
   0.003, bisect downwards on the measurement until it does not, so the reported
   step is certified by the objective and not by the linear model.
4. Measure the resulting **boundary displacement in millimetres**, matched
   Hausdorff against the state the step started from.
5. Score against the truth **only afterwards**.

The headline product is one table: millimetres of boundary movement permitted
per singular direction, inside the data tolerance.

### Controls

Same production and refined resolutions, observations, radius floor, gauge and
feasibility guards. Trust bounds are **recorded**, not imposed: the question is
what the data permits, so the permitted step is reported in units of the
optimizer's trust bound rather than clipped by it. Truth and holdout may score
and must never select. Directions refused by the floor or by either resolution
are recorded as refused with the `t` at which they were refused, not silently
skipped — the feasible set is part of the answer.

### Budget, declared before execution

At most **1200 forward frequency solves** and **600 seconds**, counted by
category at solver-call boundaries, stopping and retaining partial evidence on
either limit. Expected split: ~412 for the six Jacobians and their base states,
the remainder for the per-direction walks.

### Decision criteria

- **Large displacement inside tolerance**, concentrated in small-`σ`
  directions: conditioning and information, and TOP-012 route A follows.
- **Small displacement in every direction**: conditioning does not explain it;
  this line stops and TOP-012 does not run.
- **The linear prediction failing early** is itself a finding.

## TOP-012 — route A, and what it costs the benchmark

Runs **only** if TOP-011 returns the first verdict. Acquisition is the only
difference; scenes, truths, materials, resolutions, budgets, gates and
controller policy are identical to v1.

- A new frozen `config/topology_scenes_v2.json`, identical to v1 except for the
  0.5 GHz source/receiver set, carrying its own version string and its own
  oracle convergence check rather than inheriting v1's.
- The v1 specification and every v1 bundle stay **byte-identical**. Nothing is
  re-run, re-scored or overwritten, and no result transfers back to v1.
- Comparison is per gate on all twelve scenes against the same policy on v1
  data, with the solve cost of the enriched arm reported.
- The 0.003 tolerance is **not** loosened and no gate is re-tuned, whatever
  TOP-011 says about what that tolerance certifies.

### Budget, declared before execution

Oracle generation for the v2 acquisition at the same checked finer
discretisation as v1, then a twelve-scene comparison under the v1 per-scene
wall-clock ceiling. Both declared in the bundle manifest before the run, with a
fresh output directory and partial evidence retained on either limit.

## Artifacts

Fresh `results/validation/topology/TOP-011-<run-id>/` and, if it runs,
`results/validation/topology/TOP-012-<run-id>/`, each with source and config
hashes, complete work counts, failure records and a summary.

## Closeout record

**TOP-011 complete**, inside its declared budget at 1103 of 1200 solves and 194
of 600 seconds:
[bundle](../../../../results/validation/topology/TOP-011-20260912-tolerance-sensitivity/README.md).
It returned the first decision criterion — large displacement inside the
tolerance, concentrated in the small-`σ` directions — so TOP-012 route A is
released to run.
