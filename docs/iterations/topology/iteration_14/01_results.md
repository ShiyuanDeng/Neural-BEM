# TOP-020 results — fresh staged recovery fails despite qualified numerics

Completed 2026-09-15 under the [iteration-13 plan](../iteration_13/03_plan.md).
The user authorized finishing the remaining topology work after committing and
pushing TOP-019; that checkpoint is `fa2666f`. Owner: Codex `/root`, owner review.

**The fresh automatic two-star run does not recover.** H selects two components
from the original distant circle, but the prescribed stage-4 endpoint has
9.973540 mm boundary error, 0.828248 IoU and 0.601150 worst development error.
Only the count and original 0.5-GHz training recovery gates pass. All initial
and staged endpoints qualify numerically at 256/512 nodes.

| Endpoint | Boundary error (mm) | IoU | Worst evaluation error | Numerical gates |
|---|---:|---:|---:|---|
| Automatic endpoint | 7.595101 | 0.7468439 | 1.0031442 | Pass |
| Stage 1 | 10.319802 | 0.8432862 | 0.65039134 | Pass |
| Stage 2 | 11.247027 | 0.8178718 | 0.83725024 | Pass |
| Stage 3 | 11.225181 | 0.8421961 | 0.76152675 | Pass |
| Stage 4 | 9.973540 | 0.8282482 | 0.60114983 | Pass |

[Bundle, full work and interpretation](../../../../results/validation/topology/TOP-020-20260915-153359-fresh-two-stars/README.md)
· [owner closeout review](../../../../results/validation/topology/TOP-020-20260915-153359-fresh-two-stars/closeout_review.md).

All four stages reach planned quotas. Final objective is 1.99973675e-5. The
last gradient, 4.90889e-5, belongs to update 13; final update 14 has no measured
terminal gradient. Stationarity and a specific local-minimum explanation are
not established. Extra budget is not guaranteed to fix this trajectory.

Total work is 9,375 calls, 9,308 completed systems and 67 geometry refusals,
with no other failures, in 3,827.090 active seconds. Every cap holds. The fresh
H endpoint and events reproduce the historical controller result. 84 original
pre-dispatch tests and 103 closeout tests pass; five saved prediction records,
source/input identities, event margins, gradients, acceptance and work verify.
A reporting-only counter field adaptation after numerical completion is pinned
separately; all 197 measured source files were unchanged during the run.

## Decision and next bounded check

Close TOP-020 as **FRESH_RECOVERY_NOT_QUALIFIED**. TOP-021's prepared full staged
suite remains **NOT STARTED**: its TOP-020 recovery release gate failed. Keep
its code and 18 preparation tests as unexecuted work; do not dispatch the suite
merely because its implementation is ready.

The successful TOP-018 F comparison began at a saved COMMON state. The fresh
staged path reaches a different stage-1 state and fails; retain both records.
The next discriminating protocol test is one fresh H prefix followed directly
by the complete four-frequency objective, with the same total call/time caps,
observations, K9 chart, numerical settings and optimizer. Record this as TOP-022
before dispatch under the user's remaining-work approval. A successful change
would qualify that complete protocol, not prove an isolated basin or derivative
cause. The full suite must then use a separately reviewed candidate contract.

The star-shaped polar-gauge restriction, noiseless same-material setting and
remaining twelve-scene qualification are unchanged. No production promotion.
