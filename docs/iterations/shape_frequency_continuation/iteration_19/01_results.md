# Iteration 19 — SC-037: earlier release reduces one bias, but keeps the tradeoff

2026-09-25. Owner: Codex. Independent reviewer: unassigned.
**SC-037 COMPLETE, adoption gate FAIL.** All four schedules complete.
[Contract](../iteration_18/03_plan.md),
[evidence and raw gate](../../../../results/validation/shape_continuation/SC-037-later-state-release/README.md).

The single wider state ladder K=8/16/32/64/192 restores star to 0.5305 mm
(1.6% above the matched high-K control) and reaches peanut 0.1491, C 0.6021,
kite 0.5537 mm. It retains the substantial hard-case gains of SC-035, but C is
27.65% worse than SC-035 low K, beyond the frozen 25% limit. No threshold
changes; no new schedule sweep. Total work 1,429 inverse units including the
reused stage-one prefixes, plus 76 evaluation fields.

This qualifies the state-family conclusion: restricting early intermediate
geometry can preserve useful evolution at later frequencies, but the timing
of relaxing that restriction is a prior with case-dependent bias. Restoring
K only at the end cannot be assumed to erase that bias. No evidence here
supports a superior atlas-driven policy, a conformal replacement, or a
universal gauge ranking.

The autonomous run stops after its substantive controlled inverse gains and
bounded follow-up. SC-036 is complete, and all four SC-035 final endpoint
field/derivative audits pass. No dispatched work remains running. The solver, production defaults and SPD-L reference
remain unchanged. Next scientific work, if resumed, should freeze one
explicit state-family policy and use genuinely new shapes/starts/noise to
test a narrower claim; do not enlarge the atlas or tune these four cases by
default. No next experiment has been dispatched.
