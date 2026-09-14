# TOP-013 — the directions the derivative cannot see

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Owner:** unassigned. **Reviewer:** unassigned.
- **Baseline:** the TOP-011 measurement and the TOP-010 restart plateau, their
  data, chart and `K = 9`.

## Why this is now the leading candidate

[TOP-011](../../iteration_08/02_proposals/01_sensitivity_and_conditioning.md)
found two things, and the second is sharper than the first.

The first is that the 0.003 tolerance leaves **6.82 mm** of boundary free, 47 of
68 directions beyond the 1 mm gate, concentrated in the weak half of the
spectrum at a **12×** ratio.

The second is *why the freedom stops there*, and it splits the spectrum at a
sharp edge. For ranks 0–14 the linear model agrees with the measured objective
to within 10% **out to the full permitted step**. For ranks 15–33 it agrees at
**no probed step at all**, down to a quarter of that step, with errors of 0.12
to 16.7. At rank 33 it licenses a step **4975× larger** than the objective
actually permits.

The Jacobian is not wrong — it is stable to 3e-06 across three FD scales with
zero unresolved columns. What fails is its **validity radius**: in the bottom
nineteen directions the neighbourhood the linear model describes is smaller than
a quarter of the step the tolerance permits, because their leading response is
quadratic. The objective sees those directions; the derivative barely does.

That is a statement about the optimizer's model, not about the data, and no
previous cycle had it. Gauss–Newton and Levenberg–Marquardt build every step
from `JᵀJ` and `Jᵀr`, so a step honest to that model is confined to a region
containing a fraction of the millimetres those directions actually hold. This is
a candidate explanation for the thing four cycles of fixes could not move — and
unlike acquisition, it costs no new data.

## Question

At the saved states, do the directions where the linear model fails carry
**usable descent** that a curvature-aware step finds and the LM step does not?

## Falsifiable hypothesis

A step built from a second-order model of the objective along the weak
directions produces a decrease the LM step at the same trust radius does not
find. If a curvature-aware step finds no more descent than LM, the model's
blindness is not costing anything and this line stops — a real and reportable
negative.

## Intervention

**Diagnostic only in stage 1. No source change, no controller default, no new
arm, and no state saved as a reconstruction.**

1. Along each weak right-singular direction, measure the **actual** objective on
   a symmetric ladder of step lengths and fit the local quadratic in the true
   objective. Record where it predicts a minimum, and whether that minimum is
   downhill at all.
2. Compare, at the same trust radius and the same feasible set, the decrease
   available from: the LM step the optimizer would take; the negative gradient;
   and the step the fitted curvature model proposes.
3. Report the decrease each finds, and whether either crosses the acceptance
   margin the controller would apply.

A stage 2 that changes the optimizer is **gated** behind a separate review of
stage 1, and is not authorised by this contract.

## Controls

Same production and refined resolutions, observations, radius floor, gauge,
trust bounds, damping ladder, backtracking scales and feasibility guards. Truth
and holdout may score and must never select. Directions refused by the floor or
by either resolution are recorded as refused.

## Budget, to be declared before execution

At most **900 forward frequency solves** and **600 seconds**, counted by
category at solver-call boundaries, stopping and retaining partial evidence on
either limit.

## Decision criteria

- **Curvature finds descent LM does not, above the acceptance margin:** the
  optimizer's model is the limit, and a gated second-order stage follows.
- **No extra descent:** blindness costs nothing here; stop and say so.
- **Descent found but below the margin:** that is TOP-010's acceptance floor
  again, and it is the acceptance rule that becomes the subject, not curvature.

Any later performance claim requires all twelve frozen scenes.

## Artifacts

Fresh `results/validation/topology/TOP-013-<run-id>/` with source and config
hashes, the per-direction ladders and fits, the three-way step comparison,
complete work counts, failure records and a summary.
