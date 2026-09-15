# BIE-006 result — first-order operator reuse does not earn its cost

2026-09-15. **COMPLETE — STOP_FIRST_ORDER_OPERATOR_REUSE.**

[Authoritative result bundle](../../../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md)
and [executed contract](../iteration_03/03_plan.md).

## Measurement

One saved noncircular single interface, three chronological update directions,
two frequencies and four scaled displacements: 24/24 resolution-qualified cases.
The operator surrogate is less accurate than tangent data in 22/24 cases and
extends the primary 0.1%-error region in **0/6** direction-frequency paths.
Both models pass through 1 mm at 0.5 GHz and 0.1 mm at 1.25 GHz on the frozen
ladder. Their error slopes are 1.995–2.000, consistent with quadratic error.

Worst exact N=128/256 discrepancy is 4.512e-14; worst analytic tangent refinement
discrepancy is 3.216e-14. Public production parity is exact to reported precision.
The approximate-system residual can be 1e-15 while the residual against the
actual changed system reaches 4.456e-2: model error remains even when its own
linear solve is accurate.

Fresh-direction cost, with base already available and all directional/geometry
work charged, is approximately 249 ms for T and 250 ms for O versus 168 ms for E.
These values sum three-repeat component medians; the fixed 1.25 GHz/1 mm timing
point fails the primary accuracy gate and is a cost probe only. On the actual
qualified prefixes, O's best setup-plus-one-validation speedup over E is 0.772x,
or approximately 1.30x slower. There is no qualifying saving over T.

Executed work: 60 exact assemblies, 15 analytic assemblies with 15 primal kernel
recomputations, 87 LU factorizations, 102 RHS batches and 27 updated O solves.
20.469 seconds, 0.161 GiB peak RSS. Four tests, refinement/parity gates, 48 saved
prediction replays and source/input hash checks pass. No failed physical work.

## Interpretation and limits

Solving first-order approximated operators does not improve their truncation
order. Here it supplies neither a wider accurate region nor a finite-reuse cost
advantage sufficient to justify a new controller path. Derivative construction
costs more than fresh assembly for one direction; its earlier full-Jacobian
benefit in BIE-004 is a different workload and remains valid evidence.

The directions have pairwise cosines 0.993–0.999. They are real chronological
directions but not broad independent coverage. Their original 19.99–25.01 mm
steps exceed the tested region; zero of six later same-cycle states lies within
5 mm. The campaign uses local scaled rays, not a demonstrated usable inverse
sequence. No claim rejects all operator surrogates, preconditioning, higher-order
models or other scenes. The reference is refined production BIE, not a new
independent physical oracle.

## Decision

Stop this first-order operator-reuse line at the bounded diagnostic. Do not
integrate it or automatically expand to higher orders. No successor executed.
The existing positive result remains BIE-004's coupled analytic Jacobian; its
future integration/scene coverage is separate from this negative reuse result.

All work is in the new BIE experiment and BIE-only records. Shared solver and
topology files were left unchanged; unrelated ongoing topology work is preserved.
Owner/reviewer: Codex/self-review; no independent review claimed.
