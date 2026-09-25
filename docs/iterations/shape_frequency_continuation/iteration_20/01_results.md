# Iteration 20 — SC-038: release the update band with all frequencies

2026-09-25. Owner: Codex. Independent reviewer: unassigned.
**COMPLETE. Both cases improve; kite remains time-limited and too sharp locally.**
[Contract](../iteration_19/03_plan.md),
[resolution follow-up](../iteration_19/04_resolution_followup.md),
[conditional final stage](../iteration_19/05_remaining_m19.md),
[evidence and figures](../../../../results/validation/shape_continuation/SC-038-update-band-release/README.md).

The user identified an untested limitation of SC-035/037's final release:
K increased to 192 while M remained 9. SC-038 compares M=11/15/19 with
M=9/9/9, using identical saved SC-035 stage-four starts and all 19 frequencies
(0.25–2.5 GHz) at every new stage. K=192, the projected update and complete
Jacobian, weights, solver and optimizer are shared. The full catalog is now
fitting data, not held-out validation.

| Case | Start RMS (mm) | All frequencies, M=9 | Released M | Reduction vs M=9 |
|---|---:|---:|---:|---:|
| C | 0.471739 | 0.489494 | **0.024100** | **95.1%** |
| Kite | 0.574158 | 0.551755 | **0.109571** | **80.1%** |

C progresses 0.471739 → 0.307814 → 0.147683 → 0.024100 mm. All stages return
normally at 512/1024 nodes; the last accepts two steps and ends on
`no_decreasing_step`. Its Hausdorff error is 0.11460 mm, versus 1.77449 in the
control; mean catalog field residual is 0.0226%, versus 5.48%. The same-data
M=9 control takes no further step after its first new stage. Thus the benefit
is not explained by additional frequencies and repeat opportunities alone.

Kite reaches 0.421182 at M=11 and 0.278808 after one M=15 step, then the next
candidate fails the 512/1024-node field gate (4.0567e-7 versus 1e-7). The
returned endpoint passes its audit; the stopped attempt is retained.
A 768/1536-node replay keeps the same tolerances. Its M=9 control is exactly
unchanged; M=15 takes 11 steps to 0.172712 mm, then hits the 30-minute limit.
The prospectively recorded conditional M=19 completion uses only the unspent
solve budget, takes four steps to 0.109571 mm, then hits its 900-second limit.
The dense M=15 and M=19 segments together use 1,190 units, below the original
3,000-unit ceiling. No band or tolerance sweep; no truth-selected rollback.

**Kite is not fully fixed.** Its Hausdorff error is 0.44486 mm and its minimum
sampled curvature radius is 0.09078 mm, versus 2.13789 mm for truth and
1.76049 mm at the common start. The localized sharp feature remains despite
the better RMS and field residual. Curvature sampling at 8,192/16,384 points
agrees; this is not a continuous certificate. C's minimum radius is 8.55 mm
versus 14.55 mm for truth. Neither result establishes exact geometry recovery.

All field/derivative audits pass. Final kite field refinement is at most
1.22e-8 across all 19 frequencies; its 2.5 GHz M=19 Jacobian and full-trial FD
errors are 7.90e-9 and 3.30e-10. Source/input hashes, matched configurations,
exact prefix reuse and accounting checks pass. Actual new work including all
attempts is 3,052 inverse + 822 audit + 133 scoring = 4,007 units. Selected
complete-path totals including old prefixes are C 521 / 844 and kite
985 / 2,156 for M=9 / released M. These are equal-ceiling, not equal-work,
comparisons; the M=9 repeats stop without further progress.

The original final-release conclusion must be scoped to M=9 on four
frequencies. Raising M with the full catalog is effective on these saved
states. Kite still exposes a state-regularity and incomplete-convergence
issue, so the experiment does not establish a universal cure. No solver or
production default changed, no new-shape/noise generalization is claimed,
and no further run is dispatched. Standing autonomous authorization remains
valid; ending this bounded test does not create a new approval requirement.
