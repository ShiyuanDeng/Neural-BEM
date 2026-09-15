# TOP-023 results — damping reset merits a bounded continuation check

Completed 2026-09-15 under the [iteration-15 plan](../iteration_15/03_plan.md)
and the user's remaining-work authorization. Owner/reviewer: Codex `/root`;
no independent review claimed.

The reconstructed full 256-node model matches TOP-022's terminal gradient.
Selected rows 33 and 0 pass two-scale/two-resolution checks, with relative
derivative changes around 1e-5. The dominant gradient is -0.0142759872 at the
original probe scale and -0.0142760990 at 512 nodes/half step. The configured
stationarity criterion is not met; no local-minimum or uniqueness claim follows.
The measured singular-value ratio is 223.20 in the declared coordinates.

At that same frozen state, damping **1e-2** gives a validated production gain
**6.01388e-7**, compared with **1.51177e-7** at the next baseline damping
3.1381e-15. It needs **8 candidate frequency calls versus 24** and a smaller
physical step. Other tested damping values do not meet the predeclared >=2×
gain/no-more-calls gate. Coordinate clipping is inactive in all four proposals.

The diagnostic completes **396 new calls**, all successful, in **274.108536
seconds**, under its 600-call/1200-second limits. Eight historical training
prediction systems are reused. 85 pre-dispatch tests pass; all 202 sources and
frozen inputs remain unchanged. Saved-array algebra, numerical gates and work
replay with no new solves. [Authoritative results and all four rows](../../../../results/validation/topology/TOP-023-20260915-181302-terminal-model/README.md)
· [owner review](../../../../results/validation/topology/TOP-023-20260915-181302-terminal-model/closeout_review.md).

## Decision

The operational gate passes for damping 1e-2 only. Declare a bounded continuation
comparison from the identical failed TOP-022 terminal state, with the existing
optimizer and baseline next damping retained as a control. Test an initial
damping reset to 1e-2. Measure the original reconstruction gates and cost;
another objective decrease is not sufficient to qualify fresh recovery.

No inverse was executed by TOP-023 and no diagnostic candidate replaces its
frozen base. TOP-020/022 failures and TOP-018's different positive entry remain
intact. TOP-021 and any full-suite candidate remain unreleased. The topology
roadmap stays open under the existing user approval.
