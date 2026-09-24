# SC-030: SPD-008 and the accelerated clean hybrid on the six atlas cases

Approved by the user's 2026-09-24 instruction: set the SPD baseline to 008,
apply the proposed exact speedups to the clean hybrid, and compare the six
cases. This authorizes implementation, conditional execution, documentation,
and commit/push milestones on the existing checkout. No new branch or worktree.
Owner: Codex. Independent reviewer: unassigned.

## Decision and reference

Use **SPD-008**, not the older SC-020/021 SPD timing, as the comparison reference:
compiled inverse runtime, real-Bessel CPU kernels, exact fit-local geometry
cache with certified separation enabled. SPD-008 is the fastest qualified
measured opt-in configuration in the speedup history; its historical timing
evidence covers four topology cases, not these six starts. This choice does
not assert a new twelve-scene qualification or change global solver defaults.

The question is whether the existing clean hybrid fixed ladder improves
reconstruction and/or cost against that reference on the six development
cases. A separate cache-off hybrid control measures the execution improvement.
No atlas policy, additional frequency, restart, regularizer or gate relaxation.

## Implementation map and qualification gate

- `ordered_boundary.validation_cache`: reuse the existing exact, bounded,
  context-local cache; do not change its numerical predicates.
- `shape_continuation/validation.py`: memoize the existing spatially pruned
  intersection count using complete points and tolerance, including invalid
  returned counts. Preserve input checks and exception behavior.
- `shape_continuation/lm_backend.py`: opt-in per-fit cache scope, shared with
  the Kress adapters' repeated self-intersection checks. Keep uncached default.
- A small experiment driver calls the existing SPD and hybrid stage fitters;
  it does not copy either optimizer. Archive hashes, settings, accepted states,
  trials, stops, work and timing. Scoring is outside both fitting interfaces.

Before dispatch: test exact cache keys, invalid geometry, changed coordinates,
changed tolerances/resolutions, bounded storage and scope cleanup; compare a
real first-stage cached/uncached hybrid trajectory, including all accepted
states, trials, stop and work (excluding timing). Check SPD/package forward
agreement at the shared start at all four training frequencies and both
resolutions (relative error <= 1e-8), and the existing refined prediction
thresholds. Failure blocks the comparison. Qualification cap: 1,000 work
units and 900 seconds. Preserve failed attempts with reasons.

## Frozen six-case comparison

Cases: wrong circle, circle to five-lobe star, C, kite, peanut and hook, using
the immutable SC-022/SC-025 observations and oracle qualification. These are
development cases, not untouched generalization data. Start all fits from
the same circle: centre (0.48, 0.52) m, radius 0.065 m. No topology search;
this is a supplied single-component, fixed-topology comparison.

| Setting | Contract |
|---|---|
| Arms | SPD-008; hybrid cache off; hybrid exact cache on |
| Data | Same noiseless 24 complex paired responses per frequency |
| Schedule | Cumulative 0.5, 0.75, 1.0, 1.25 GHz, uniform weights |
| Objective | 0.5 mean of squared per-frequency relative residuals |
| Production / refined nodes | 512 / 1024 for every arm |
| Iteration cap | 22 per stage, existing stopping/damping/acceptance rules |
| Stage work quotas | 1000, 1250, 1750, 4000; existing 12-unit reserve |
| Hard per-run budget | 8012 work units; 3600 inverse seconds |
| SPD geometry | Native K17 Cartesian storage with polar-angle gauge, all 33 reduced directions available at every stage; native feasibility/radius guards |
| Hybrid geometry | V2, K192 arclength storage, normal update M=3,5,7,9; coefficient step clipping; refit tolerance 1e-5 |
| Prediction qualification | Production/refined relative discrepancy <=1e-5 at 0.5 GHz, <=1e-7 above it |
| Repetition | Two fresh processes per arm and case; sequential, alternating order, BLAS threads=1 |
| Campaign cap | 36 fits, 288432 inverse work units, 12 hours including scoring |

The SPD geometry is **not unrestricted Cartesian geometry**. Its polar-angle
chart and native feature-radius guard may limit non-star-shaped recovery.
The hybrid has a different representation and feasible set. These are declared
algorithm differences, not an isolated causal test of harmonic restriction.
Both use the same resolution, rather than comparing SPD's historical 256/512
against the hybrid's 512/1024. Both execute the four-stage fit without the
topology/readiness wrapper; the deliberately inaccurate common start is
qualified in preflight. Retain native per-stage stopping, reset and feasibility.

## Measurements and closeout

Time inversion separately from setup, post-run scoring and process startup.
Record hardware, software, threading, run order and concurrent host load. Two
repeats supply a range, not a statistically strong timing distribution. Report
work categories as well as total units: the categories have unequal cost.
Keep numerical failures, unresolved derivatives and budget stops in the table;
a fast failed run is not a recovery speed win. Save the last accepted state.

Only after fitting, score every retained endpoint with the same independent
package evaluator: symmetric RMS and conservative Hausdorff distance in mm,
19-frequency residuals, and production/refined qualification on training data.
Do not select the best intermediate state or arm using truth. Retain every
accepted-state numerical check. Compare all hybrid cached/off trajectories
exactly after removing timing; also compare against SC-029 baseline endpoints.

The decision is a per-case quality/cost comparison, not a new binary recovery
threshold chosen from results. Quantify cache speedup only for identical work
and trajectories. No automatic successor or extra tuning if SPD or hybrid
fails. Results open iteration 13. Commit/push after (1) this reference/contract,
(2) qualified implementation, and (3) complete measurements and interpretation.
