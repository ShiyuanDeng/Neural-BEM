# SPD-015: native shape-continuation geometry default

2026-09-28. **COMPLETE / PASS.** The user requested integration and validation,
then selected the current shape-continuation pipeline. The existing
`feature/shape-frequency-continuation` branch was used. Owner: Codex; self-review.

Exact spatial checks and bounded geometry caches are now enabled automatically
in native solves, Jacobians, fit stages, objective batches, atlas construction
and trajectory diagnostics. `SC_GEOMETRY_RUNTIME=reference` retains the previous
execution path; `cache` and `spatial` isolate the two mechanisms. Explicit cache
and intersection contexts retain precedence, and ordinary independent batches
clear their caches on return or exception. The shared ordered-boundary default
outside these scopes remains dense.

The native `experiments.shape_continuation.latest_video` entry point adds complete
diagnostic-batch reuse around the unchanged historical renderer. The amended
SPD-014 spatial predicate, historical renderer and SC-043 driver are preserved.

| Fresh matched work | Reference | Native default | Time reduction |
|---|---:|---:|---:|
| Diagnostic batches, 24 per arm | 132.82 s | 52.31 s | 60.6% |
| Six SC-043 continuation suffixes | 306.49 s | 284.85 s | 7.1% |
| Six video preparations | 640.21 s | 297.99 s | 53.5% (2.15x) |

All 96 four-arm diagnostic hashes, 54 paired inverse files and six complete video
pairs agree exactly except timing. Work is unchanged: 4180 units per inverse arm
and 3800 per video arm. All endpoint audits and renderer assertions pass. Every
fresh reference inverse file also matches the earlier SPD-014 archive numerically.

The broad regression suite passes 374 tests; a 65-test CPU-focused/native-harness
run also passes (overlapping coverage plus two additional harness tests). All 36
saved-geometry comparisons agree, and all 234 sources and 559 inputs verify.
Adversarial tests retain nonzero crossing/touching and sub-roundoff fallback
coverage; saved geometries have zero intersection counts.

These are sequential shared-host RTX 5090 measurements with four frequency
threads and one BLAS thread. Inverse timings start at saved intermediate shapes,
not original circles. They exclude harness startup and repeated input hashing.
There is one inverse/video pair per scene, with no noisy-data, multicomponent
performance or topology-default claim. The unchanged raw video shots are reused;
identical display data does not require re-encoding videos.

The [complete evidence](../../../../results/validation/speedup/SPD-015-20260928-native-geometry/README.md)
contains per-scene times, computation counts, frozen sources/inputs, commands,
test logs and comparison receipts. The [contract](03_plan.md) and
[usage/reproduction guide](../../../../experiments/spd015_default_geometry/README.md)
record the approved scope and controls. All gates passed within their budgets.
