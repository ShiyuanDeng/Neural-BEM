# TOP-020 — fresh automatic two-star run does not recover

Completed 2026-09-15 under the [approved plan](../../../../docs/iterations/topology/iteration_13/03_plan.md).
**The full prescribed schedule is numerically qualified but fails recovery.**
The controller chooses two components from the original distant circle; final
boundary, IoU and development-prediction gates fail. Correct count and the
original 0.5-GHz training gate pass.

| Endpoint | Boundary error (mm) | IoU | Worst evaluation error | Numerical gates |
|---|---:|---:|---:|---|
| Automatic endpoint | 7.595101 | 0.7468439 | 1.0031442 | Pass |
| Stage 1 | 10.319802 | 0.8432862 | 0.65039134 | Pass |
| Stage 2 | 11.247027 | 0.8178718 | 0.83725024 | Pass |
| Stage 3 | 11.225181 | 0.8421961 | 0.76152675 | Pass |
| Stage 4 | 9.973540 | 0.8282482 | 0.60114983 | Pass |

[Saved-state figure](endpoints.svg) · [all scores](scorecard.json) ·
[complete result and work](result.json) · [artifact replay](verification.json).

## Interpretation

The five-lobed component ends at 1.625179 mm boundary error and the seven-lobed
component at 9.973540 mm. The final training errors are 0.001748, 0.003006,
0.006176 and 0.010476 at 0.5/0.75/1/1.25 GHz; development errors are 0.094889
and 0.601150 at 1.5/2.5 GHz. Strong production/refined agreement does not imply
accurate reconstruction. The largest final prediction discrepancy is below
2e-13, well inside the unchanged tolerances.

All four stages finish at planned quotas with usable models. None establishes
convergence. Final-stage objective is 1.99973675e-5; its last measured reduced
gradient is 4.90889e-5 at update 13, before the final accepted update 14. The
terminal gradient is unavailable and stationarity is not established. Do not
call this a proved local minimum or infer that another few updates must recover.

TOP-018's successful F result started from a saved COMMON checkpoint. This
fresh run instead executes H and all four new stages from the original circle.
The new stage-1 endpoint differs, and recovery does not carry over. Preserve both
results. The observation, solver, gauge and numerical-tolerance contracts remain
unchanged; the staged fresh entry and allocation need diagnosis.

## Work and verification

Total **9,375 charged calls: 9,308 completed BIE frequency systems and 67 routine
geometry-refused calls**. There are no other failed calls. Topology: 1,615
attempts / 1,548 completed, birth/death/birth, valid margins and monotonicity.
Continuation: 7,760 completed calls, including initial scoring and endpoint
quotas 948 / 1,154 / 1,698 / 3,948. Active time is 3,827.090 seconds (63.785 min),
within the 12,012-call / 7,800-second ceilings. One physical worker, one BLAS
thread; wall time is descriptive.

All 197 measured sources remained unchanged through numerical completion.
**84 pre-dispatch tests** passed; **103 focused closeout tests** pass, including
18 tests of the still-unexecuted conditional suite. Five endpoint records are
independently replayed from saved complex predictions, with no new physical
solves. Source/input/state/gradient/event/acceptance/work checks pass.

A reporting-only counter field was corrected after numerical sealing. The
original measured reporter remains in `measured_sources/`, the corrected copy
is in `closeout_sources/`, and [closeout validation](closeout_validation.json)
records both hashes. No numerical result was repaired or rerun. Review is by
the implementation owner, not an independent reviewer.

## Decision

Close TOP-020 as **FRESH_RECOVERY_NOT_QUALIFIED**. Keep TOP-021's full staged
suite undispatched because its release gate fails. Under the user's approval to
finish the remaining work, scope one fresh direct four-frequency refinement
comparison with the same total cap, original circle, H controller, observations,
K9 chart, 256/512 nodes and optimizer. This tests a different entry protocol;
it does not pre-judge stationarity, uniqueness or the cause of the failure.
