# TOP-011 — how much geometry hides inside the data tolerance

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Owner:** unassigned. **Reviewer:** unassigned.
- **Baseline:** `3c2fd13`; the TOP-009 stage-4 endpoint and the TOP-010 restart
  plateau, their data, chart and `K = 9`.

## Why this and not another optimizer fix

Four defects have been found and fixed — the frozen-column derivative
(TOP-008), missing shape capacity (TOP-009), a truncated mode ladder (TOP-009
stage 4) and premature stopping (TOP-010). **Every one improved the training
objective. Not one improved the reconstruction.** The benchmark still passes
5/12.

The sharpest form of the puzzle is a single pair of numbers. The final `K = 9`
state satisfies the frozen controller's **0.003** relative-error data tolerance
at **8.7878e-05** — thirty-four times inside it — while sitting **11.849 mm**
from the truth with union IoU 0.7088 and worst holdout error 1.4154. Meanwhile
the true geometry reaches **3.23e-07**. The question is no longer which defect
to fix; it is why a data fit that good coexists with geometry that bad.

## Question

At the saved states, **which geometric directions does this acquisition actually
constrain, and how far can the boundary move while the data fit stays inside the
frozen 0.003 tolerance?**

## Falsifiable hypothesis

A large boundary displacement is available at negligible data cost, concentrated
in the weakly-constrained right-singular directions of the Jacobian. If instead
every direction that moves the boundary appreciably also moves the residual
appreciably, the decoupling is *not* explained by conditioning and the
explanation lies elsewhere — a real and reportable negative.

## What is already measured, and what is missing

At the plateau the reduced Jacobian is full rank 34/34 with singular values
spanning **2.085e-04 to 28.83**, a condition number of **1.205e+05**. Rank alone
says a descent direction exists; it says nothing about how much *geometry* the
weak directions buy per unit of data. That conversion — data cost to millimetres
of boundary — has never been measured, and it is the whole question.

Note the shape of the problem: **34 gauge directions against 48 real residual
entries.** Formally over-determined, and that is exactly why a conditioning
answer cannot be assumed from counting.

## Intervention

**Diagnostic only. No source change, no controller default, no new arm, and no
state advanced or saved as a reconstruction.**

At each saved state, assemble the Jacobian with the feasible-side stencil at the
three declared FD steps, take its SVD, and for each right-singular direction
`v_i` with singular value `σ_i`:

1. Compute the step length `t_i` at which the predicted relative L2 error
   reaches the frozen **0.003** tolerance — the boundary of what the controller
   would still call a fit.
2. Take that step, verify it against the **actual** objective rather than the
   linear prediction, and record where the prediction breaks down.
3. Measure the resulting **boundary displacement in millimetres** — matched
   Hausdorff against the state it started from, not against the truth.
4. Score against the truth **only afterwards**, so the answer to "is this
   direction data-blind" never consults it.

The headline product is one table: **millimetres of boundary movement permitted
per singular direction, inside the data tolerance.**

## Controls

Same production and refined resolutions, observations, radius floor, gauge,
trust bounds and feasibility guards. Truth and holdout may score and must never
select. Directions refused by the floor or by either resolution are recorded as
refused, not silently skipped — the feasible set is part of the answer.

## Budget, to be declared before execution

At most **1200 forward frequency solves** and **600 seconds**, counted by
category at solver-call boundaries, stopping and retaining partial evidence on
either limit. The Jacobians are roughly 204 solves per state per FD step; the
step probes are one to two solves per direction.

## Decision criteria

- **Large displacement inside tolerance**, concentrated in small-`σ` directions:
  the decoupling is a conditioning and information problem, and the successor is
  acquisition or a geometric prior — chosen against a measured spectrum rather
  than a guess.
- **Small displacement in every direction**: conditioning does not explain it.
  The objective, the gate definitions or the forward model become the suspects,
  and this line stops rather than proposing a fix it has not motivated.
- **The linear prediction failing early** would itself be the finding: it would
  mean the local model does not describe the tolerance neighbourhood at all.

Any later performance claim requires all twelve frozen scenes. Nothing here
changes the benchmark, its gates or its data.

## Artifacts

Fresh `results/validation/topology/TOP-011-<run-id>/` with source and config
hashes, the per-direction table, the linear-versus-actual comparison, complete
work counts, failure records and a summary.
