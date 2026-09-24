# SC-030 — SPD-008 versus the clean hybrid

Implementation qualification passed; the six-case comparison is ready for
dispatch under the [frozen contract](../iteration_12/03_plan.md).

The reference is SPD-008 with compiled inverse execution, real-Bessel CPU
kernels and certified exact validation reuse. The clean hybrid now supports
fit-local exact validation reuse through the same opt-in context, including
its own spatially pruned intersection predicate. Global defaults are unchanged.

The pre-dispatch suite passed **76 tests**. At the shared start, SPD and the
package forward agree to at most **1.89e-14** relative error over four training
frequencies at both 512 and 1024 nodes. Physical starting boundaries are equal.
The first-stage cached and reference hybrid trajectories, trial decisions,
stops and work agree exactly: five accepted steps, 18 units, gradient stopping.
Measured inversion times were 17.74 s reference and 16.00 s cached. There were
30 cache hits among 42 shared intersection requests, with peak retained cache
storage 1.48 MB. This small timing pair is qualification evidence, not the
six-case speedup conclusion. Total qualification: 52 units and 58.34 s.

Evidence: [SC-030 bundle](../../../results/validation/shape_continuation/SC-030-spd008-comparison/README.md).
Owner: Codex. Independent reviewer: unassigned. Comparison results pending.
