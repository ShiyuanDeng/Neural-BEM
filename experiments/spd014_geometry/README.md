# SPD-014: exact sampled-geometry acceleration

**COMPLETE / PASS; qualified opt-in.** Six matched SC-043 suffix runs use 7.1% less time;
video preparation uses 53.6% less time, with exact non-timing results.
See the [results and limits](../../results/validation/speedup/SPD-014-20260927-geometry/README.md).

The matched worker timings begin at saved intermediate shapes, not at the
original circles. They measure complete SC-043 continuation suffixes.

**Native integration, 2026-09-28:** [SPD-015](../spd015_default_geometry/README.md)
adds this acceleration to shape-continuation's ordinary fit, objective and
diagnostic calls, controlled by `SC_GEOMETRY_RUNTIME` (default `both`). Its
reference setting retains the pre-integration execution path. SPD-014's original
qualification and timing receipts remain historical; use SPD-015's fresh evidence
for the native default. The shared ordered-boundary API still defaults to dense
checks outside the shape-continuation scopes.

Approved follow-up to SPD-011's remaining geometry cost. The candidate retains
all polygon nodes, orientation/touching tolerances and intersection counts. It
uses the existing shape-continuation KD-tree idea in the shared Kress validation
path, with a bounded candidate set and the original dense fallback.

The four arms isolate execution changes: `reference`, `cache`, `spatial`, and
`both`. The normal ordered-boundary backend stays `reference`; no optimizer or
forward-physics default changes. Select pruning in Python:

```python
from ordered_boundary.validation_cache import intersection_validation

with intersection_validation('spatial'):
    # Existing Kress or inverse calls; frequency threads inherit this context.
    ...
```

For diagnostic batches, cache across all frequencies and their Jacobians with
an explicit `validation_cache('cache')` context. `geometry_validation('cache')`
only selects caching for decorated fits; it does not activate a cache for direct
objective/solver calls. Use a new cache for each independent endpoint audit.

The experiment wrappers combine the controls without changing archived scripts:

```python
from experiments.spd014_geometry.runtime import cache_diagnostic, geometry_acceleration

diagnostic = cache_diagnostic(existing_diagnostic)
with geometry_acceleration('both'):
    diagnostic(...)  # fresh exact cache, cleared even when the call raises
```

An already active cache is reused without changing its mode. Selection is
context-local, so copied frequency contexts share the chosen backend and cache.
Backend-specific cache keys ensure switching reference/spatial cannot hide a
comparison behind a previous cache hit.

Reproduce in a new evidence folder, with the same explicit backend
and thread counts throughout. The driver freezes and checks source/input hashes,
requires fresh output folders, and gates full runs on the geometry and four-arm
screens. Failed/partial folders remain intact.

```bash
export SC_FORWARD_BACKEND=cuda SC_FREQUENCY_THREADS=4
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:.
PYTHON=/home/drdeng/miniconda3/envs/EMNerf/bin/python
BUNDLE=results/validation/speedup/SPD-014-reproduction
$PYTHON -m experiments.spd014_geometry.run freeze "$BUNDLE"
$PYTHON -m experiments.spd014_geometry.run geometry "$BUNDLE"
$PYTHON -m experiments.spd014_geometry.run batches "$BUNDLE"
$PYTHON -m experiments.spd014_geometry.run inverse "$BUNDLE"
$PYTHON -m experiments.spd014_geometry.run video "$BUNDLE"
```

`inverse` loads the frozen SC-043 worker and supplies an independently scoped
audit wrapper; `video` loads the unchanged `latest_vs_hybrid` renderer and wraps
its diagnostic function. Neither historical evidence nor display caches are
overwritten. The comparator includes all non-timing fields, not only endpoints.
Source and observation hashes, work counters and geometry computation counts
accompany timing. Threaded/nested geometry timers cannot be summed as wall time.

Post-review: [sub-roundoff fallback amendment](../../results/validation/speedup/SPD-014-amendment-20260928/README.md). Below the orientation roundoff guard the implementation uses the dense checker to preserve its floating-point counts. Original timings predate this amendment.
