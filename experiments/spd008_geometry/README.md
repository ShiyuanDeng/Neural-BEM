# SPD-008: exact geometry validation acceleration

User-approved [contract](../../docs/iterations/speedup/iteration_07/03_plan.md).
The experiment changes execution of geometry checks, keeping the compiled
runtime, readiness, FD-compatible analytic policy, grids and optimizer fixed.

**Completed:** [SPD-008 results](../../results/validation/speedup/SPD-008-20260917-geometry/README.md).
All 16 full workers recover with exact paired trajectories, endpoints and work.
Hard-scene median time reductions are 50.5% and 54.5%; the implementation remains
qualified opt-in. The final source/input/artifact audit passes.
The reported wall times are shared-host observations: a separate LAU-001 screen
appears to overlap the final worker. The closeout preserves this timing caveat;
all measured sources and exact numerical/work comparisons still pass.

The geometry mode is deliberately separate from `--inverse-runtime`:

```python
from ordered_boundary.validation_cache import geometry_validation

with geometry_validation('certified', on_fit=fit_diagnostics.append):
    # Call the existing inverse or complete TOP-025 worker.
    # Each fixed-topology fit gets its own bounded cache.
    ...
```

`reference` collects matching diagnostics without reuse; `cache` reuses exact
component reports and sampled self-intersection counts; `certified` additionally
uses conservative sampled-polygon separation in boolean admissibility. There is
no process-global cache, environment override, new optimizer or default change.
Outside each fit, readiness and independent endpoint validation retain the
ordinary path. Direct geometry-only checks can use `validation_cache(...)`.
Detailed pair-clearance reports remain exact reports on the original path.

Use the EMNerf interpreter with `PYTHONPATH=solvers` and one BLAS thread. The
following modes are sequential, with fresh output directories and frozen
source/input hashes:

```bash
python -m experiments.spd008_geometry.run tests --bundle RESULTS
python -m experiments.spd008_geometry.run qualify --bundle RESULTS
python -m experiments.spd008_geometry.run campaign --bundle RESULTS
python -m experiments.spd008_geometry.run report --bundle RESULTS
```

`RESULTS/preparation/fixtures.json` supplies the prepared 19 saved records.
`qualify` checks every record at 64/128/256/512 nodes in both resolution orders,
then replays central/two-star updates twice per mode and one coarse merge update
per mode. Profiling follows all unprofiled update timings. Full workers are
released only if exact decision/state agreement and the two-fold hard-case
stencil speed gate pass. They run two repeats of four scenes, sequentially with
alternating/reversed arm order. Both full arms use the compiled inverse runtime;
the `reference` geometry label does **not** select the old FD inverse runtime.

The driver refuses source/input drift and existing output folders, reserves the
original physical/Jacobian work, and stops on the first paired regression. Cache
diagnostics are separate from physical work accounting. Geometry timers are
nested and must not be added. The current candidate's estimated retained
key/value/entry memory is bounded to 16 MiB per fit; peak usage and evictions are
reported. Exceptions, timeouts and partial runs remain in the evidence bundle.

SPD-009's true-analytic policy, all-scene default promotion, GPU execution and
lazy compiled Jacobians are outside this experiment.
