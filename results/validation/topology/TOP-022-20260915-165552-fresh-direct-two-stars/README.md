# TOP-022 — direct four-frequency entry does not recover the fresh two-star case

**COMPLETED_SCHEDULE; FRESH_RECOVERY_NOT_QUALIFIED.** Completed 2026-09-15
under the [approved plan](approved_plan.md) and the user's remaining-work
instruction after TOP-019 was committed/pushed as `fa2666f`.

H starts at the original distant circle, chooses two components automatically,
and exactly reproduces TOP-020's topology endpoint. Exact K9 padding qualifies
at 256/512 nodes. The sole refinement stage uses all four training frequencies
immediately, with TOP-020's total solve/time ceilings and the unchanged optimizer.
No archived optimized state or supplied count initializes the inverse.

| Prescribed final result | TOP-020 staged | TOP-022 direct |
|---|---:|---:|
| Maximum matched boundary error (mm) | 9.973540 | 9.755053 |
| Material IoU | 0.8282482 | 0.8301304 |
| Original 0.5-GHz training error | 0.00174799 | 0.00192875 |
| Worst development error | 0.6011498 | 0.6191849 |
| Four-frequency objective at 512 nodes | 1.99973675e-5 | 2.19073145e-5 |
| Charged frequency calls | 9,375 | 8,247 |
| Recovery gates | Fail | Fail |
| Numerical qualification | Pass | Pass |

TOP-022 passes count and original training gates; boundary, IoU and development
prediction fail. The five-star boundary error is 1.620646 mm; the seven-star
error is 9.755053 mm. Development errors are 0.0916234 at 1.5 GHz and 0.619185
at 2.5 GHz. Both saved endpoints pass numerical checks; the final maximum
prediction discrepancy across resolutions is 1.36e-13.

The optimizer accepts 22 updates and stops at **maximum_iterations**, with
convergence **UNCONFIRMED**. Its terminal reduced gradient is **0.0142759872**
at the exact final state, above the configured 1e-7 tolerance. All 23 Jacobian
models complete with zero unresolved or one-sided columns. Small objective
changes do not establish stationarity or a local minimum. One candidate is
refused by the radius-floor check before any physical solve.

## Work, verification and decision

H: 1,615 charged calls, 1,548 completed systems, 67 charged geometry refusals,
131.808058 seconds. Continuation: 6,632 charged/completed calls, zero physical
failures, 3,073.327221 seconds. Total: **8,247 charged = 8,180 completed + 67
geometry refusals**, **3,205.137761 active seconds**. All ceilings hold. Timing
is descriptive; see [runtime environment](runtime_environment.json).

112 pre-dispatch tests pass, with seven test files and 199 source files pinned.
All measured sources/inputs remain unchanged. Saved complex predictions,
objective normalization, state/gradient identities, topology events, acceptance,
comparison provenance and per-frequency work replay successfully with zero new
physical solves. The [figure](endpoints.png) was visually checked; the seven-star
lobe mismatch remains visible. See [scorecard](scorecard.json),
[verification](verification.json) and [owner review](closeout_review.md).

Direct entry uses 12.0% fewer charged calls but does not fix fresh recovery.
Keep both negative protocols and the successful, differently initialized TOP-018
comparison. Neither fresh result releases a full-suite candidate. TOP-021 remains
undispatched. Next: a bounded frozen-terminal derivative/step diagnosis, using
training data only to distinguish a model problem from insufficient optimization
progress. No budget extension, restart or production promotion is part of TOP-022.

Scope remains noiseless, separated, same-material, star-shaped polar-gauge
Cartesian components. The twelve-scene topology roadmap is still open.
