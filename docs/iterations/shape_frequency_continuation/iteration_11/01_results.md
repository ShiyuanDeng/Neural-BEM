# Iteration 11 — distinguish the dense atlas from the inverse's update space

2026-09-24. Owner: Codex. SC-028's
[plan](../iteration_10/03_plan.md) was implemented and its targeted suite
passed 33 tests. The preflight then stopped the expensive campaign as
intended: [six of twelve full P=48 Jacobian comparisons failed](../../../../results/validation/shape_continuation/SC-028-atlas-strategies/README.md).
All fields passed. No recovery arm was dispatched and no strategy benefit
or failure can be inferred from this numerical gate.

The [separately declared active-band diagnostic](../../../../results/validation/shape_continuation/SC-028-active-band-diagnostic/README.md)
recomputed the same twelve cells. At the proposed inverse's maximum band
M=19, every cell passes the **unchanged** 1e-6 column-relative tolerance.
The maximum is 5.37e-7 (kite); the C is <=1.75e-7 and peanut <=2.41e-7.
The full-atlas maxima occur at harmonics 45–48. See the
[complete per-band numbers](../../../../results/validation/shape_continuation/SC-028-active-band-diagnostic/diagnostic.json).

## Decision and scope

- SC-028 is **complete at its failed qualification gate**; the recovery
  campaign was not released. Preserve the original negative evidence.
- P=48 atlas refinement is not uniformly established at these rough
  SC-025 endpoints. Do not generalize SC-023's small qualification sample
  to every SC-026 state or frequency.
- The same evidence supports a narrower, explicitly declared inverse
  test at M<=19. Open **SC-029**, using exactly SC-028's frozen recovery
  strategies, tolerances, cases, resolutions and budgets. Only the
  qualification claim changes: all columns of the maximum space actually
  used by the inverse, rather than all 97 atlas coordinates.
- This qualification is post hoc to the preflight failure, but **precedes
  every recovery outcome**. No threshold was tuned to recovery scores.

The user's instruction to analyse, propose strategies, test them and
document results authorizes this bounded continuation. It requires no new
branch, worktree or default change. The [SC-029 plan](03_plan.md) records
the restricted claim and the unchanged comparison before dispatch.
