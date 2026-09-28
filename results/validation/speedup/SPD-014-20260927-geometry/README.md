# SPD-014: exact geometry acceleration

**COMPLETE / PASS; qualified opt-in.** The user approved this bounded follow-up
with "you have my approval". Owner: Codex; no independent reviewer claimed.
The [contract](approved_plan.md) preserves geometry sampling, tolerances,
physics, optimizer decisions, work accounting and independent endpoint audits.

Against the completed SPD-012/013 CUDA baseline, the six SC-043 continuation workers take
**7.1% less time** and video preparation takes
**53.6% less time (2.16x faster)**.
Every paired non-timing inverse and video field agrees exactly. The broad
regression suite passed 369 tests; a subsequent replay-harness test also passed.

## What changed

- The shared sampled-polygon check can use a KD tree to select candidate
  segment pairs, followed by the original crossing, touching and adjacency
  rules. This extends the mechanism already present in the hybrid geometry
  code to Kress validation. It retains all polygon samples and resolved tolerances.
- Candidate pairs are counted before allocation. A candidate budget of
  `min(262144, max(4096, 16*N))`, extreme-coordinate guards and dense fallback
  bound the new allocation. The dense predicate's body is unchanged.
- Backend selection is context-local and copied to frequency workers. Cache
  keys include the backend as well as full points and resolved tolerances, so
  switching arms cannot mask a comparison with an old cache hit.
- Direct audit and complete renderer diagnostic calls use an independent,
  active exact cache. `geometry_validation('cache')` only selects future fits;
  it does not activate caching for direct objective calls. Existing fit caches
  and an explicitly active reference cache keep their original policies.
- Historical SC-042/043 drivers and `latest_vs_hybrid/render.py` are unchanged.
  The replay harness wraps their audit/diagnostic callables and writes fresh
  outputs. Source signatures and all original renderer assertions are preserved.

The normal intersection backend remains `reference`. See
[usage](../../../../experiments/spd014_geometry/README.md) for
`intersection_validation('spatial')`, or `geometry_acceleration('both')` with
`cache_diagnostic` for combined diagnostic acceleration.

## Qualification and attribution

The [geometry screen](geometry/result.json) compares all six SC-043 start/end
curves at 512, 1024 and 2048 nodes: **36 exact count matches**, with a median
**209.2x** uncached-check speedup. The 256-node grid is
not valid for their K192 storage and is skipped explicitly. Unit tests add
crossings, tolerated touches, collinearity, repeated/zero-length segments,
translations/scales, nonuniform samples, invalid inputs, dense fallback,
cache lifetime, thread sharing and unchanged multicomponent clearance refusals.

The [four-arm screen](batches/result.json) uses six endpoint curves, actual
production/refined grids (512/1024, or 768/1536 for kite), all 19 frequencies,
and two repeats in reversed arm order. All **96 complete diagnostic outputs**
have identical hashes, including Jacobian blocks and frontiers. Each timed
batch performs 19 forwards and 19 reciprocal solves. The 24 warmup units are
recorded separately; total screen work is 3672 units.

| Arm | Summed diagnostic time | Time reduction | Executed intersection checks |
|---|---:|---:|---:|
| reference | 132.605 s | 0.0% | 912 |
| cache | 54.129 s | 59.2% | 24 |
| spatial | 52.572 s | 60.4% | 912 |
| both | 52.083 s | 60.7% | 24 |

The dense check consumes 80.282 of 132.605 s
(60.5%) in these serial reference batches.
Caching reduces 38 computations per batch to one; spatial pruning makes each
computation much cheaper. Their gains overlap and must not be multiplied.
The combined screen exceeds the declared 20% diagnostic-saving gate.

## Complete SC-043 continuation workers

These workers begin at saved intermediate shapes and execute the complete
SC-043 suffix. They exclude the original circle-start prefix and earlier
releases; their times are not full circle-to-target reconstruction times.

Six SC-043 fixed-policy controls and six combined workers run sequentially,
alternating arm order by scene, with four frequency threads and one BLAS thread.
All 54 paired JSON files match after removing only fields named `seconds`:
decisions, accepted states, three blocks, checkpoints, audits, results and progress.
All endpoint audits pass. Physical units include each worker's 114-unit audit.
These preserve baseline reconstruction quality; they are not a new recovery or
optimizer-policy claim.

| Scene | CUDA reference | Combined geometry | Time reduction | Physical units per arm |
|---|---:|---:|---:|---:|
| Circle | 14.73 s | 13.23 s | 10.2% | 228 |
| Star | 54.97 s | 51.87 s | 5.6% | 855 |
| C | 55.92 s | 52.56 s | 6.0% | 893 |
| Kite | 95.31 s | 87.45 s | 8.2% | 912 |
| Peanut | 32.64 s | 30.29 s | 7.2% | 532 |
| Hook | 49.24 s | 45.98 s | 6.6% | 760 |
| **Sum** | **302.82 s** | **281.38 s** | **7.1%** | **4180** |

[Inverse receipt](inverse/result.json). Fits already share geometry checks,
so their marginal gain is smaller than for uncached diagnostics. Reference
workers execute 819 dense checks; combined workers
execute 159 spatial checks, including independent
audit cache scopes, with 0 dense fallbacks on
these six trajectories.

## Fresh video preparation

Both arms run the unchanged renderer with new output/display-cache folders and
the same saved upstream raw field shots. Every non-timing prepared field,
source/cache signature, work counter, curve/RMS and frontier is identical.
Original saved-loss and refinement assertions pass in both arms. No inverse is
rerun here, and the identical displayed content does not need video re-encoding.

| Scene | CUDA reference | Combined geometry | Time reduction | Physical units per arm |
|---|---:|---:|---:|---:|
| Circle | 13.42 s | 7.95 s | 40.8% | 76 |
| Star | 127.95 s | 56.67 s | 55.7% | 988 |
| C | 118.46 s | 58.61 s | 50.5% | 836 |
| Kite | 218.48 s | 94.11 s | 56.9% | 760 |
| Peanut | 59.33 s | 32.19 s | 45.7% | 380 |
| Hook | 100.98 s | 46.51 s | 53.9% | 760 |
| **Sum** | **638.61 s** | **296.05 s** | **53.6%** | **3800** |

[Video receipt](video/result.json). Executed intersection checks fall from
**3800 dense computations to 100
spatial computations**, with 0 dense fallbacks.
Field and reciprocal work is unchanged.

## Timing scope and provenance

- Same RTX 5090 host; explicit `SC_FORWARD_BACKEND=cuda`, four frequency threads
  for inverse objectives, one BLAS/OpenMP thread, and one process worker at a
  time. The renderer's frequency loop stays serial. No other numerical campaign
  was running. Process/load/GPU observations accompany the saved commands.
- One full pair per scene, two diagnostic repeats. Reported ratios are observed
  shared-host timings, not statistically established population speedups.
  Tables use worker time, including inverse endpoint/scoring or video preparation;
  they exclude harness imports and repeated provenance hashing. The harness
  verifies roughly 21.5 GB of frozen inputs. Its full stage elapsed times are
  971.9 s for inverse and 1321.5 s for video,
  which include that extra verification/startup overhead.
- Earlier SPD-011/013 timings used different concurrency and are not the matched
  timing controls here. The measured baseline is completed commit `e3bc5e5d`
  plus the reference-preserving SPD-014 dispatch, pinned by source hashes.
- [Current manifest](manifest.json), [source archive](sources.tar.gz),
  [preflight source receipt](preflight_source_record/manifest.json), and
  [harness amendment](source_amendment.json) preserve exact provenance. Pre-dispatch
  review found a missing SC-043 output-manifest staging step; that harness-only
  fix and its test were recorded before any inverse run. Numerical sources,
  inputs, thresholds and schedules did not change after the successful screens.
- Geometry validation stays a sampled-polygon guard, not a continuous-curve
  simplicity proof. Dense/pathological shapes can fall back and need not gain
  speed. No multicomponent performance, noisy-data or all-topology-scene claim
  follows from these six single-object development cases.

Tests: [geometry/CPU](geometry-tests.log), [broad regression](regression-tests.log),
[replay harness](harness-tests.log). Post-timing validation adds
[54 exact extreme-scale count/error comparisons](extreme_scale_check.json),
including norm-underflow scales. The [final integrity check](final_integrity.json)
verifies all frozen sources, inputs, the approval snapshot and source archive.
Machine-readable closeout: [summary](summary.json).
Reproduction commands and scoped APIs are in the
[experiment README](../../../../experiments/spd014_geometry/README.md).
