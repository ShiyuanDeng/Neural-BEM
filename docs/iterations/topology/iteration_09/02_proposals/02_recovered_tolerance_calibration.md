# TOP-014 — calibrate `recovered` against the geometry it certifies

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION. Changing the value
  would be a **controller default change**, which this track keeps as a separate
  decision from any measurement.
- **Execution status:** NOT STARTED
- **Owner:** unassigned. **Reviewer:** unassigned.
- **Baseline:** the TOP-011 measurement; `topology_controller.py:795`.

## The mismatch, stated precisely

`relative_error_tolerance = 0.003` is not only a pass gate. It is the
controller's own **stopping criterion**: at `topology_controller.py:795` a cycle
that reaches it sets `stop = 'recovered'` and the run ends.

[TOP-011](../../iteration_08/02_proposals/01_sensitivity_and_conditioning.md)
measured what that criterion certifies about shape: at 0.003 the boundary is
free to move up to **6.82 mm**, with 47 of 68 singular directions permitting
more than the **1 mm** `maximum_matched_hausdorff_m` gate the same run is then
judged by.

So the controller stops on a criterion that is about **seven times looser** than
the criterion it is scored against. That is not a tuning opinion; it is a
measured relationship between one number and the other.

## Question

What value of `relative_error_tolerance` certifies at most 1 mm of boundary
freedom, measured the way TOP-011 measured 0.003 — and does stopping there
change any of the twelve frozen scenes?

## Falsifiable hypothesis

Scenes that currently stop on `recovered` while still failing a geometric gate
do so because the criterion fires early. If tightening it changes no scene's
outcome, the criterion was not what was binding, and the finding is that this
mismatch is real but inert.

Note the expected reach honestly: of the v1 arm-H runs, only **`merge`** stops
`recovered` anywhere near a tightened threshold, at 7.88e-05 with a 0.55 mm
boundary and a failing holdout gate. The rest stop at 6e-07 or below, far past
any tightening, and the failing ellipse/star scenes never reach 0.003 at all —
their problem is not the stopping criterion. **At most one gate is available
here**, and the contract should not pretend otherwise.

## Intervention

1. **Calibration, from saved artifacts first.** TOP-011's walks already record
   the measured relative L2 at several step lengths per direction. Combined with
   the displacement measured at the accepted step, they give a millimetres-
   versus-relative-error curve per direction, under an explicitly stated and
   spot-checked local-linearity assumption on displacement. Invert it for the
   tolerance whose permitted movement is 1 mm.
2. **Verification, with solves.** Re-run the TOP-011 walk at that candidate
   tolerance and confirm the permitted movement directly rather than by
   extrapolation.
3. **Twelve frozen scenes**, arm H, tolerance as the only difference, reported
   per gate against the recorded v1 arm-H bundle.

## Controls

Everything except `relative_error_tolerance` is identical, including the pass
gates. **The gate is not moved to meet the criterion; the criterion is moved to
meet the gate.** The v1 bundles are not re-run or re-scored.

## Budget, to be declared before execution

Stage 1 costs no solves. Stage 2 at most **700 forward frequency solves** and
**400 seconds**. Stage 3 is the v1 per-scene wall-clock ceiling and suite
ceiling, unchanged, with timeouts reported apart from gate failures.

## Decision criteria

A pass-count change on the twelve scenes is the headline. A tightened criterion
that gains nothing and costs solves is a rejection, and should be recorded as
one rather than adopted for tidiness.

## Artifacts

Fresh `results/validation/topology/TOP-014-<run-id>/`, with the calibration
curve, its verification, and the full twelve-scene comparison.
