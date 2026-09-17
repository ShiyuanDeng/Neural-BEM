# SPD-008 — exact geometry acceleration

**COMPLETE / PASS — retain the qualified opt-in.** All 16 full inverse workers
recover. All eight pairs have identical topology and continuation trajectories,
accepted states, gradients, candidate decisions, refusal reasons, endpoints and
work counts. Both hard-scene median reductions exceed the predeclared 20% gate;
both easy scenes improve in the recorded shared-host timings. Defaults and the FD-compatible constraint policy are
unchanged. Four noiseless scenes do not establish all-scene qualification.

The [approved plan](../../../../docs/iterations/speedup/iteration_07/03_plan.md)
governs scope and budgets. The [implementation review](../../../../experiments/spd008_geometry/implementation_review.md)
is an owner self-review; no independent reviewer is claimed.

## Matched complete inverse times

Both arms use compiled + reciprocal + readiness, original observations and
starts, the same topology controller, grids, tolerances and stopping rules.
Only geometry-validation execution changes. Times include worker startup,
topology, candidate fits, continuation and independent endpoint checks.

Each cell gives the **median**, followed by both samples in seconds.

| Scene | Reference geometry (s) | Exact cache + certificate (s) | Median time reduction |
|---|---:|---:|---:|
| Death | **46.32** (46.49, 46.14) | **30.56** (30.35, 30.77) | **34.0%** |
| Merge | **176.18** (178.30, 174.06) | **136.65** (135.40, 137.90) | **22.4%** |
| Central ellipse/star | **1069.98** (1071.86, 1068.09) | **529.95** (527.32, 532.57) | **50.5% / 2.02x** |
| Two stars | **1314.84** (1305.21, 1324.48) | **597.65** (597.56, 597.73) | **54.5% / 2.20x** |

The sum of these four medians is 43m27s versus 21m35s. This describes one
reconstruction per selected scene, not all twelve scenes or the repeated
validation campaign. Full precision and every comparison are in
[campaign/summary.json](campaign/summary.json); commands and per-worker machine
load are in [campaign/timings.json](campaign/timings.json). The timing caveat below
applies to these measurements; numerical equivalence is independently verified.

Workers ran sequentially on an Intel Core Ultra 9 285K, CPU execution, one BLAS
thread, with alternating/reversed arm order. Both arms collect matching fit
diagnostics. A file-only monitor read saved logs every 55 seconds, and small
file-only audits checked completed results. **The final workspace audit found
contemporaneous LAU-001 numerical work:** its artifact timestamps and recorded
31.30 s duration indicate overlap with the last SPD-008 two-star worker. Its
tests/pilot may also have overlapped; absolute times for those are unavailable.
The observed wall times are shared-host measurements, not an isolated benchmark.
[timing_context.json](timing_context.json) preserves the evidence and inference;
the other task's work was left untouched. All 240 measured source hashes still
match. Two repeats provide limited timing evidence. No noisy-data or GPU claim
is made, and no samples were discarded or extra runs launched to hide this limit.

## What changed and what remains exact

- A fresh opt-in context for each fit caches component validation reports and
  sampled self-intersection counts using full array contents and resolved
  settings/tolerances. No coefficient rounding or cross-fit cache is used.
- Boolean pair admissibility can accept a conservative sampled-polygon axis-gap
  certificate. Ambiguous, overlapping, nested, near-threshold or unsupported
  scales use the original exact path. Detailed pair-clearance reports still
  compute actual clearances.
- Requested-grid guards, bounds, adapter ownership, radius floor, retraction,
  refined checks and independent endpoint scoring remain in place. The existing
  FD-compatible stencil policy is retained in both arms.

The retained key/value/entry estimate is capped at 16 MiB per fit. The measured
maximum was **16,777,204 bytes**, below 16,777,216; evictions occur in longer
fits. This is a cache accounting bound, not a process-RSS measurement.
See [experiment usage](../../../../experiments/spd008_geometry/README.md) for
`geometry_validation('reference' | 'cache' | 'certified')`.

## Qualification and work

The final-source regression selection passes **144 tests**, with one
unavailable-CUDA skip, in 22.68 s ([test record](tests.json), [log](tests.log)).
Geometry-only replay agrees on all 19 saved records across the three arms and
64/128/256/512-node grids in both orders: 57 rows / 456 decisions, including the
saved coarse-accept/refined-refuse case, with zero physical solves.

Two unprofiled full-update replays per arm on each hard handoff reproduce the
archived first accepted state exactly. Median stencil times are:

| Handoff | Reference | Cache only | Cache + certificate | Complete stencil speedup |
|---|---:|---:|---:|---:|
| Central ellipse/star | 23.079 s | 13.930 s | 6.324 s | 3.649x |
| Two stars | 22.630 s | 13.620 s | 6.351 s | 3.563x |

The coarse merge update also preserves states, candidate decisions and stopping:
1.463 / 0.810 / 0.729 s for reference / cache / certified. These diagnostics
released the full campaign; they are not substituted for its measured timings.
See [geometry qualification](geometry/qualification.json) and
[update qualification](updates/qualification.json).

Full-worker work is identical across arms and repetitions:

| Scene | Physical attempts, including refusals | Operator directions | Reciprocal batches | Compiled batches | Total work units |
|---|---:|---:|---:|---:|---:|
| Death | 89 | 130 | 0 | 0 | 219 |
| Merge | 316 | 250 | 46 | 0 | 612 |
| Central ellipse/star | 805 | 1136 | 0 | 283 | 2224 |
| Two stars | 629 | 661 | 0 | 387 | 1677 |

These categories are the existing budget units, not interchangeable elapsed
costs. Attempted/completed/refused counts reconcile, including per-frequency
records. Maximum paired coefficient difference is zero. All saved endpoint
prediction arrays, readiness decisions and final recovery metrics agree exactly.

## Preserved attempt and cumulative budgets

The first dispatch stopped before numerical work because a progress edit to the
live plan tripped the input hash guard. [The incident](dispatch_incident.json)
and [failed launch](campaign_attempt_01/) are retained. The runner now freezes
its archived plan copy; two added harness regressions cover that boundary and
charging prior attempts against the original budgets. No numerical solver,
cache or certificate code changed in this repair. Qualification was repeated on
the final runner. Initial tests and both diagnostic attempts remain archived.

| Phase, all attempts included | Consumed | Original ceiling |
|---|---:|---:|
| Geometry replay | 26.63 s, zero solves | 300 s |
| Update qualification and separate profiles | 429.25 s, 226 work units | 1800 s, 2000 units |
| Full campaign, including failed pre-dispatch attempt | 7805.49 s (2h10m05s) | 10800 s; 2400 s per worker |

[verification.json](verification.json), rebuilt by the file-only [audit.py](audit.py),
passes 240 current source hashes, 1648 archived source hashes, 251 current input
hashes and 111 archived-attempt input hashes. All **618** hashes in the completed
TOP-025 compiled campaign still match, and its verification record is unchanged.
Its 8/12 outcome and failed scenes are preserved. The audit performs no solves.
[artifact_manifest.json](artifact_manifest.json) seals this bundle's artifacts.

## Remaining cost and decision

A separate accelerated central update profile takes 8.945 s, including 6.431 s
in stencil checks, 5.060 s in sampled self-intersections, 1.136 s in component
reports and 0.123 s in exact pair checks. These are **nested** timings and must
not be added. The profile applies to one update. In the first complete central
pair, fit stencil time falls from 697.88 to 199.75 s, while total worker time
falls from 1071.86 to 527.32 s. Unchanged physical work and independent scoring
limit the transfer from the local 3.65x stencil gain to the full 2.02x gain.

Retain this implementation as a numerically qualified opt-in with the observed
timing gains and shared-host caveat. An isolated confirmation of wall-clock gains,
default promotion and a fresh
all-twelve-scene geometry comparison require a separately recorded scope.
SPD-009's true-analytic constraint policy remains unexecuted. No additional
numerical campaign is scheduled by this closeout.
