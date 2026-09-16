# SPD-005 — reciprocal Kress in the full inverse

Status: **PASS**. See [summary.json](summary.json) for raw quality, timing and work counts.

| Scene | Operator | Reciprocal | Reciprocal + readiness | Reciprocal gain | Combined gain | Readiness increment |
|---|---:|---:|---:|---:|---:|---:|
| death | 234.826 s | 133.028 s | 46.018 s | 1.77x | 5.10x | 2.89x |
| split | 223.031 s | 123.523 s | 33.572 s | 1.81x | 6.64x | 3.68x |
| merge | 409.848 s | 172.004 s | 175.925 s | 2.38x | 2.33x | 0.98x |

Two workers per arm/scene are planned; table medians use completed workers only.
Includes fresh topology search,
candidate fits, continuation and endpoint scoring; excludes archived truth-data generation.
All arms use identical original starts, observations and controller/feasibility settings.
Only the combined arm applies the predeclared training-only readiness gate.

The reciprocal runtime retains operator derivatives below 128 nodes. Thus these
64-node topology fits are unchanged; the reciprocal gain occurs in continuation.
All original constraints and the FD-compatible stencil policy remain in force.

A separate [remaining-cost profile](remaining_cost_profile/summary.json) diagnoses one
continuation stage after all timed workers. Profiler times are excluded from this table.
See the [iteration 05 closeout](../../../../docs/iterations/speedup/iteration_05/01_results.md)
for the guarded qualification, endpoint comparison and next priority.

Own workers ran sequentially with one BLAS thread. Host-wide process isolation was
not established. These are three noiseless scenes, not an all-scene or noise qualification.

The [manifest](manifest.json), measured_sources, qualification snapshots and per-arm
input manifests preserve the actual source/configuration provenance. The [verification](verification.json)
reconciles physical systems, operator directions and reciprocal RHS batches separately.
Kernel profiling spans may overlap; use phase wall times for additive comparisons.

Rebuild with `PYTHONPATH=solvers:. python -m experiments.spd005_reciprocal.reporting.summarize BUNDLE`.
