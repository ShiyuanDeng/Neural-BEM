# TOP-022 results — direct entry also fails fresh recovery

Completed 2026-09-15 under the [iteration-14 plan](../iteration_14/03_plan.md),
within the user's remaining-work authorization. Owner/reviewer: Codex `/root`;
no independent review claimed.

The freshly recomputed H controller exactly reproduces TOP-020's two-component
endpoint. Immediate four-frequency K9 refinement at 256/512 nodes completes
22 updates but fails the same boundary/IoU/development gates: **9.755053 mm**,
**0.830130 IoU**, **0.619185 worst development error**. Count and original
training pass; all numerical gates pass. The five-star error is 1.620646 mm,
and the seven-star lobe mismatch dominates the boundary failure.

The final objective is 2.19073145e-5, versus TOP-020's 1.99973675e-5. TOP-022
uses **8,247 charged calls** rather than 9,375: 8,180 completed systems plus
67 geometry refusals, in 3,205.137761 active seconds. All budgets hold. The
lower call count and modest boundary improvement do not qualify recovery.

Unlike TOP-020's quota-final state, TOP-022 has a measured terminal gradient:
reduced infinity norm **0.0142759872**, above the 1e-7 configured tolerance.
The optimizer stops at **maximum_iterations**, with convergence unconfirmed.
All 23 Jacobian models are complete, with no unresolved or one-sided columns.
This is not evidence of a stationary local minimum or of the benefit from
simply extending the run. Derivative accuracy and step quality at this terminal
state remain questions for a bounded diagnosis.

112 pre-dispatch tests pass; all 199 measured sources/inputs remain unchanged.
Both saved endpoint predictions, events, state/gradient identities and complete
work counters replay successfully without new physical solves. The final figure
was visually verified. [Authoritative bundle and comparison](../../../../results/validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars/README.md)
and [owner review](../../../../results/validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars/closeout_review.md).

## Decision

Close TOP-022 as **FRESH_RECOVERY_NOT_QUALIFIED**. Preserve both failed fresh
protocols and TOP-018's successful different saved-COMMON entry. TOP-021 stays
NOT STARTED; no full-suite candidate is released. Next, declare a small frozen
terminal training-model diagnosis before further optimization, under the user's
remaining-work approval. Keep truth/development data outside candidate selection.
The twelve-scene roadmap and production qualification remain open.
