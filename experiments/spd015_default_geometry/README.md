# SPD-015: native geometry default

This validates the geometry integration requested by the user on 2026-09-28.
The [contract](../../docs/iterations/speedup/iteration_12/03_plan.md) fixes the
controls, budgets, evidence and promotion gates. The native runtime is documented
in the [shape-continuation API](../shape_continuation/README.md).

`SC_GEOMETRY_RUNTIME` defaults to `both` (exact spatial pruning plus bounded
validation reuse). Set it to `reference` for the previous execution path, or
`cache`/`spatial` to isolate either mechanism. The CUDA backend and frequency
thread controls are independent. The earlier SPD-014 wrapper delegates its
explicit arm selection to this runtime, preserving reference comparisons after
the native default change.

Use a fresh folder and run the phases sequentially under EMNerf:

```bash
export PYTHONPATH=solvers:. SC_FORWARD_BACKEND=cuda SC_FREQUENCY_THREADS=4
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PYTHON=/home/drdeng/miniconda3/envs/EMNerf/bin/python
BUNDLE=results/validation/speedup/SPD-015-reproduction
$PYTHON -m experiments.spd015_default_geometry.run freeze "$BUNDLE"
$PYTHON -m experiments.spd015_default_geometry.run geometry "$BUNDLE"
$PYTHON -m experiments.spd015_default_geometry.run batches "$BUNDLE"
$PYTHON -m experiments.spd015_default_geometry.run inverse "$BUNDLE"
$PYTHON -m experiments.spd015_default_geometry.run video "$BUNDLE"
$PYTHON -m experiments.spd015_default_geometry.run verify "$BUNDLE"
```

The combined worker leaves `SC_GEOMETRY_RUNTIME` unset. Inverse replays use the
native fit/objective scopes without SPD-014 audit or forecast wrappers. Video
workers use `experiments.shape_continuation.latest_video`, which scopes complete
diagnostics around the unchanged historical renderer. Geometry-screen and
campaign bookkeeping reuse SPD-014's tested harness; each experiment has its own
frozen contract and sources. Existing result folders are never reused by these
campaign commands.

All numerical comparisons exclude timing fields only. Work counters, failed
trials, accepted states, endpoint audits, displayed fields and frontiers remain
part of the exact comparison. These six inverse timings start from saved SC-043
intermediate shapes. They do not measure full original-circle reconstructions,
multicomponent performance or generalization to new/noisy scenes.

The [2026-09-28 evidence](../../results/validation/speedup/SPD-015-20260928-native-geometry/README.md)
contains test logs, frozen source/input manifests, per-worker commands and all
comparison receipts.
