# CI-SPD evidence index

This bundle documents the already completed GGB-001 experiment and related
runtime/design notes grounded in existing evidence. Its creation aggregates
existing JSON and copies the existing comparison image; no field solver,
inverse fit, geometry replay, or new timing experiment runs.

The [detailed explanation](../../../../docs/iterations/CI-SPD/01_results.md)
distinguishes measured timings from mechanisms identified in the source.

| Artifact | Contents |
|---|---|
| [comparison_summary.json](comparison_summary.json) | Per-case metrics, timing boundaries, physics counts, exact trial-status/refusal totals, stages and source-manifest digest |
| [comparison.png](comparison.png) | Byte-identical copy of the original truth/GauGal/BEM image panel |
| [GPU_SPLINE_FAIR_BASELINE.md](../../../../docs/iterations/CI-SPD/GPU_SPLINE_FAIR_BASELINE.md) | Existing geometry evidence, a proposed GPU spline baseline and unmeasured predictions |
| [MODAL_RUNTIME_GEOMETRY_CHECK.md](../../../../docs/iterations/CI-SPD/MODAL_RUNTIME_GEOMETRY_CHECK.md) | Verified PC-001/PC-002 runtime accounting, corrected audit timing boundaries and proposed certificate-cost fixes |

Canonical evidence is retained in
[Gau-Gal at commit 3ec2627](https://github.com/HaibingWu657/Gau-Gal/tree/3ec2627d3ff7329453ec7b76469a0761d6f6e3de/docs/iterations/GGB-001/evidence).
The local checkout is `/home/drdeng/Gau-Gal`; original raw outputs remain
under its `outputs/GGB-001/pilot`. This bundle does not replace or reseal the
original experiment. Full per-case arrays and unsuccessful-case histories
remain in the canonical archive.

Aggregation formulas:

```text
accepted_steps = sum(stage.accepted_steps)
trial_proposals = sum(len(stage.trials))
refusal_reasons = Counter(trial.reason for refused trials)
physics_seconds = successful/failed evaluations + successful/failed derivatives
other_wall_seconds = fit_seconds + audit_seconds − physics_seconds
```

LU factorization and the native stage timers are subsets of physics time,
not additional disjoint categories. GauGal's `linear_solves` and
`linear_iterations` in the final result describe its last outer iteration,
because the counters reset every iteration; they are not totals over 300
iterations. No cumulative Krylov-work claim is derived from those columns.

SHA256 digests of the local artifacts:

```text
7a334c9fa065834806aa655c992d99c777b11db4333c582df9a310cedf0df7ac  comparison_summary.json
3b62890b7b1d13b27c353cee3e9d2453c5c78dd673cce1a95436fc2cdd4ebc04  comparison.png
```
