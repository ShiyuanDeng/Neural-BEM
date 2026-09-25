# Iteration 21 — SC-039: raw boundary data along every saved trajectory

2026-09-25. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**SC-039 COMPLETE.** [Plan](../iteration_20/03_plan.md),
[evidence](../../../../results/validation/shape_continuation/SC-039-trajectory-atlas-data/README.md).

The user asked for "all the data on those trajectories" so that any atlas can
be built later, including the M>9 runs. SC-039 stores, at every distinct
accepted state of 34 saved trajectories (original hybrid, SC-035 low and K=192
control, SC-036 ray, SC-037, SC-038 released M and M=9, SPD-L) and at all 19
catalog frequencies, the forward and reciprocal boundary traces, node
geometry and full 24x24 prediction on 512 and 1024 nodes (plus 768/1536 for
the 15 kite shots SC-038 solved there). That is 867 shots and 6 truth
references: 33,744 forward and reciprocal solves, 1 h 48 min, 40.6 GB.

Every first-order shape atlas is a contraction of this kernel,
`J = (ki^2 - k^2) sum_x w u_s v_r h`, with the normal velocity h of any chosen
coordinates: the user's Cartesian coefficients of the stored curve, the
existing arclength normal harmonics, or others. The pilot shows the stored
traces reproduce `shape_jacobian` within 9.6e-16 in all three tested bases.
All 1,114 saved LM-run losses along the trajectories are rebuilt bitwise from
the stored predictions, so every shot is the state the run evaluated. 46 shots
disagree between 512 and 1024 nodes by more than 1e-7 at some frequency; they
are the K=192 control's hard-stopped states and SC-038's dense kite path.

This is data only: no atlas, interpretation or method claim. Next, the user's
choice of which atlas to build first from it; nothing is dispatched.
