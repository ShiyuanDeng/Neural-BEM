# SPD-015: native geometry default — COMPLETE / PASS

2026-09-28. The user requested integration and validation, then explicitly chose
“Enable the geometry speedups in the current shape-continuation pipeline”.
Implementation and validation used the existing `feature/shape-frequency-continuation`
checkout. Owner: Codex; self-reviewed, with no independent review claimed for
this integration. The amended SPD-014 spatial predicate is unchanged.

Shape-continuation now defaults to exact spatial intersection checks and bounded
validation reuse (`SC_GEOMETRY_RUNTIME=both`). Native solves, Jacobians, fit stages,
objectives, atlas builds and trajectory diagnostics select scoped acceleration.
Each ordinary fit/batch releases its cache, including on exceptions; explicit
active cache/intersection selections retain precedence. Independent objective
and endpoint calls create new scopes. Other shared ordered-boundary callers keep
their dense default. No optimizer, physics, sampling or tolerance rule changes.

Use `SC_GEOMETRY_RUNTIME=reference` for pre-integration execution, or `cache` and
`spatial` to isolate the mechanisms. `geometry_runtime(mode)` is a context-local
override; `geometry_batch()` scopes custom diagnostics. The native
`python -m experiments.shape_continuation.latest_video` command adds complete
batch reuse around the historical renderer. See the [API](../../../../experiments/shape_continuation/README.md)
and [reproduction guide](../../../../experiments/spd015_default_geometry/README.md).

## Matched measurements

| Work | Reference | Native default | Time reduction |
|---|---:|---:|---:|
| Diagnostic batches, 24 per arm | 132.82 s | 52.31 s | 60.6% |
| Six complete SC-043 continuation suffixes | 306.49 s | 284.85 s | 7.1% |
| Six video preparations | 640.21 s | 297.99 s | 53.5% (2.15x) |

| Scene | Inverse reference s | Inverse default s | Reduction | Video reference s | Video default s | Reduction |
|---|---:|---:|---:|---:|---:|---:|
| `wrong_circle` | 15.12 | 13.33 | 11.8% | 13.21 | 7.93 | 40.0% |
| `circle_to_star` | 55.90 | 52.38 | 6.3% | 128.43 | 57.10 | 55.5% |
| `circle_to_c` | 56.95 | 53.23 | 6.5% | 118.21 | 59.32 | 49.8% |
| `kite` | 96.28 | 88.93 | 7.6% | 218.71 | 94.64 | 56.7% |
| `peanut` | 32.65 | 30.61 | 6.2% | 59.73 | 32.26 | 46.0% |
| `hook` | 49.59 | 46.36 | 6.5% | 101.92 | 46.73 | 54.2% |

Cache-only diagnostic batches take 54.24 s and spatial-only batches 52.62 s;
their gains overlap. Dense checks consume 60.5% of the reference diagnostic
batch time. Across these batches, the reference executes 912 dense checks;
cache-only executes 24 dense checks, spatial-only 912 spatial checks, and the
native default 24 spatial checks. Each arm performs 912 physical units, plus
24 common warm-up units for the complete screen. The 96 complete diagnostic
hashes agree exactly across all arms/resolutions/repeats.

Inverse checks fall from 819 dense computations to 171 spatial computations;
video checks fall from 3800 dense computations to 100 spatial computations.
No measured default worker invokes the dense fallback. Both inverse arms use
4180 physical units including audits; both video arms use 3800. All accepted
states, trials, decisions, audit results and work counters agree: 54 paired
inverse JSON files and six complete prepared-video JSON pairs. Every independent
endpoint audit and original renderer assertion passes. All 54 fresh reference
files additionally match the earlier SPD-014 reference archive, excluding timing.

## Validation and provenance

- 374 broad regression tests pass in 25.21 s, covering shape continuation,
  ordered-boundary, Kress, SPD-008 and the SPD-014 harness.
- 65 CPU-focused/native-harness tests pass in 9.93 s. These overlap the broad
  suite and add two native-harness tests. Coverage includes exact CPU/CUDA fields
  and Jacobians, multicomponent physics, invalid geometry, reference overrides,
  cache lifetime/cleanup, copied thread contexts, fit trajectories and work.
- All 36 saved-geometry comparisons match; the median uncached speedup at
  N >= 512 is 188.93x. These saved counts are zero; adversarial tests cover
  nonzero crossings/touches and the reviewed zero/sub-roundoff dense fallback.
- All 234 frozen source hashes and 559 input hashes verify. The original
  spatial predicate, SC-043 driver and video renderer are unchanged from the
  starting commit (`b994cdf8`). Numerical code was frozen before measurements.
- Every phase stays within the [frozen contract](approved_plan.md), and all
  commands exit zero. Inverse/video physical totals are 8360/7600. Geometry,
  diagnostic, inverse and video process times are 37.39, 322.75, 995.63 and
  1345.60 s respectively, including startup and repeated integrity checks.

The [verification receipt](verification.json), [summary](summary.json),
[source/input manifest](manifest.json), [commands](commands.json),
[test commands](test_commands.json), [broad test log](regression.log),
[CPU-focused test log](cpu_tests.log), [source archive](sources.tar.gz) and
[preserved-source check](preserved_sources.json) retain the evidence.
`geometry/`, `batches/`, `inverse/` and `video/` contain all detailed receipts,
worker outputs, cache files, commands, environments and comparisons.
`summarize.py` reproduces the summary without numerical work; `campaign.py`
records the exact sequential dispatch used here.

## Scope and decision

Promote this execution optimization as the native shape-continuation default.
These are fresh sequential measurements on a shared RTX 5090 host with explicit
CUDA, four frequency threads for inverse objectives, and one BLAS thread.
Video diagnostics remain serial across frequencies. There is one complete pair
per scene and two diagnostic repeats, with reversed arm ordering. All numerical
workers ran sequentially; tests finished before timing began.

The inverse timings cover saved SC-043 continuation suffixes, not full
reconstructions from the original circles. Worker sums exclude harness startup
and repeated hashing of roughly 21.5 GB of inputs. Nested geometry timers are
not additive. Video output/display-cache folders are fresh; the same archived
raw field shots are reused in both arms. Identical display data requires no
video re-encoding. No noisy-data, multicomponent-performance or topology-default
claim is added. No speedup ratios from earlier CPU/CUDA studies are multiplied.

Historical SPD-014/SC-043/SC-049/SC-050 evidence is preserved. This integration
adds no new reconstruction strategy or claim about solving nonconvex failures.
