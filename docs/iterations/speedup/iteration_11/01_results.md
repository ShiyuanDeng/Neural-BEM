# Iteration 11 results: SPD-014 exact geometry acceleration

2026-09-27. **COMPLETE / PASS; qualified opt-in** under the
[approved contract](../iteration_10/03_spd014_plan.md). The user replied
"you have my approval" to the remaining geometry follow-up. Owner: Codex;
self-review only. Implementation began after SPD-012/013 completed at clean
commit `e3bc5e5d`, with no competing numerical workers.

Exact spatial pruning and independent diagnostic-batch caching reduce the
remaining CPU geometry cost on the CUDA path. They keep all polygon samples,
resolved tolerances, crossing/touching rules and integer counts. Dense candidate
sets and unsuitable tree coordinates fall back to the unchanged dense checker.
The normal backend remains `reference`.

## Measured benefit and unchanged quality

| Measurement | Matched reference | Combined geometry | Result |
|---|---:|---:|---|
| 96 diagnostic batches, four arms | 132.61 s | 52.08 s | 60.7% less time; every complete output hash identical |
| Six SC-043 continuation workers | 302.82 s | 281.38 s | 7.1% less time; all 54 paired JSON files identical except timing |
| Six fresh video preparations | 638.61 s | 296.05 s | 53.6% less time (2.16x); every non-timing field identical |

The continuation workers start from saved intermediate shapes and run the
complete SC-043 suffix. They exclude the original circle-start prefix and
earlier releases; these are not full circle-to-target reconstruction times.

The standalone geometry screen gives 209.2x median
speedup over 36 saved start/end samples, with exact count agreement. Dense checks
consume 60.5% of reference diagnostic time; caching reduces 38 computations per
batch to one. Cache-only and spatial-only times are 54.13
and 52.57 seconds. Their savings overlap.

All independent inverse audits and original renderer assertions pass. Each arm
uses 4180 inverse physical units (including audits) and
3800 video units. Video checks fall from
3800 dense computations to 100
spatial computations, with no dense fallback on these saved trajectories.
The 369-test broad regression suite, one replay-harness test, a 110-test CPU
subset, and 54 additional extreme-scale comparisons pass.

## Scope and decision

These are sequential, shared-host measurements on an RTX 5090, with explicit
CUDA, four frequency threads for inverse objectives, and one BLAS thread. The
renderer remains serial across frequencies. There is one complete pair per
scene and two diagnostic repeats. Worker totals above exclude harness startup
and repeated hashing of roughly 21.5 GB of frozen inputs; full campaign elapsed
times and per-scene rows are retained in the evidence.

Fits already share geometry checks, which explains the smaller inverse gain.
Fresh video output/cache folders reuse the same saved upstream field shots.
No reconstruction policy, physics, pair-clearance rule or video content changed.
The result supports an opt-in execution optimization for these six development
cases; it adds no noisy-data, multicomponent-performance or all-topology claim.

The [evidence and provenance](../../../../results/validation/speedup/SPD-014-20260927-geometry/README.md)
record every arm, work count, source/input hash and the pre-dispatch harness-only
manifest-staging amendment. The [usage guide](../../../../experiments/spd014_geometry/README.md)
shows the scoped backend and diagnostic-cache APIs. All approved stages passed
their gates and stayed within budget. No default promotion or successor
numerical run is scheduled.
