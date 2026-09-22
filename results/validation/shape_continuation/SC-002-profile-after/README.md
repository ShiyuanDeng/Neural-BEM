# SC-002 — remove geometry-check overhead without changing the inverse

User direction: continue autonomously through cleanup, profiling and necessary
repairs; commit and push validated checkpoints while working. Dedicated branch
`feature/shape-frequency-continuation`, created under the user's subsequent
branch authorization. Reference checkpoint: `964214e`.

The saved SC-001 observations were replayed three times without profiling,
then once with cProfile. Single process, one BLAS thread, same machine and
acquisition. Synthetic-data generation and endpoint scoring are excluded.
Timing is a local workload measurement, not a universal speed claim.

| Measurement | Before | After |
|---|---:|---:|
| Median complete inverse | 19.6641 s | 0.83525 s |
| Forward evaluations | 21 | 21 |
| Jacobians | 8 | 8 |
| Accepted updates | 8 | 8 |

Local speedup: **23.54×**. All **52 accepted/initial state arrays** across the
four replays are bitwise identical, with the same stage residuals and stop
reasons. The profiled reference spent 18.82 of 19.55 seconds in polygon
self-intersection checks; the 21 forward evaluations took 0.73 seconds.

The new spatial check conservatively finds potentially intersecting segment
pairs with a KD tree, then uses the same orientation, touching and adjacency
rules as the all-pairs reference. Geometry sampling, tolerances, forward
assembly, Jacobian, candidate selection and continuation are unchanged.
Initial and update arclength refits now share one implementation. Work counters
include separate numerical and geometry timing buckets.

**Validation:** 34 tests passed in 1.18 seconds. Spatial counts agree with the
all-pairs reference for random, crossing, touching, repeated-point and
near-collinear polygons at multiple scales, offsets and tolerances. The same
2048-point geometry grid is retained in the ellipse replay.

Artifacts: [comparison](comparison.json), [timing and source hashes](timing.json),
[profile](profile.txt), [reference timings](../SC-002-profile-before/timing.json).
`states_0.npz` through `states_3.npz` preserve every state in each replay.

Reproduce either version with its checkout and a fresh output directory:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.shape_continuation.benchmark \
  --pilot results/validation/shape_continuation/SC-001-20260922-ellipse-03 \
  --output /tmp/shape-continuation-profile-new --repeats 3
```

The profiling driver was added after the reference checkpoint; copy only
`benchmark.py` when replaying that checkpoint. The stored manifest records its
hash and those of the exact numerical sources used. The next qualification
extends frequency/shape resolution and tests a more complicated target.
