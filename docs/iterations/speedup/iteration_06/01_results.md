# SPD-006 — compiled Kress integrates cleanly; full-inverse gains are modest

2026-09-16. **COMPLETE / QUALITY PRESERVED**, following the user-authorized
[compiled integration plan](../iteration_05/03_plan.md).

The BIE-005 nodal scattering compiler is integrated as an opt-in production
backend. It reduces complete runtime by **4.5% on central ellipse/star and 5.6%
on two stars**, beyond reciprocal Kress plus readiness. All 16 fresh workers
recover, with matching topology events and accepted steps. Keep this qualified
option; the next substantial opportunity is geometry/constraint work, which
still occupies 88.5% of one profiled compiled update.

[Result bundle](../../../../results/validation/speedup/SPD-006-20260916-full-inverse/README.md)
and [machine-readable comparison](../../../../results/validation/speedup/SPD-006-20260916-full-inverse/summary.json)
contain timings, original quality gates, work counts and frozen provenance.

## Complete inverse timings

Medians of two fresh workers per arm/scene, rotated/reversed arm order,
sequential CPU workers with one BLAS thread. Both arms use the same training-only
readiness gate, original starts/observations, Cartesian gauge, optimizer,
geometry rules, schedule and inner budgets. Timers include startup, topology,
candidate fitting, continuation, readiness and endpoint checks; existing truth
data generation and video rendering are excluded. Host-wide isolation is
unverified.

| Scene | Reciprocal + readiness | Compiled + readiness | Full runtime reduction |
|---|---:|---:|---:|
| Death | 46.124 s | 46.149 s | Unchanged |
| Merge | 171.724 s | 171.854 s | Unchanged |
| Central ellipse/star | 1098.371 s — 18m18s | 1049.405 s — 17m29s | 4.46% / 1.047x |
| Two stars | 1367.985 s — 22m48s | 1291.664 s — 21m32s | 5.58% / 1.059x |
| Four scenes sequentially, sum of medians | 44m44s | 42m39s | 2m05s saved |

The full validation campaign ran both arms twice: **10486.87 s / 174.78 min**,
within its 10800 s limit. The longest worker took 1374.33 s, below 2400 s.
The small death/merge differences are timing variation: death skips continuation,
and the single-component merge retains reciprocal Kress. Central compiled
repeats take 1048.21/1050.60 s; its controls take 1105.55/1091.19 s. Two-star
compiled repeats take 1300.80/1282.52 s; controls take 1374.33/1361.64 s.
Both difficult-scene pairs improve in both run orders, but two repeats do not
provide a broad statistical or workload claim.

The documented [TOP-025 twelve-scene run](../../topology/iteration_18/01_results.md)
took **90.35 min with up to four workers**, with 7/12 recoveries, using the
historical FD/reference pipeline. No twelve-scene compiled campaign has been
measured. Its runtime cannot be inferred by scaling that concurrent campaign
with these four sequential scene timings. The earlier three-scene operator,
reciprocal and readiness comparison remains in [SPD-005](../iteration_05/01_results.md).

## Quality and numerical qualification

All 16 workers pass every original reconstruction and numerical gate. Every
paired event sequence, component ID and accepted-step count matches:
death skips continuation, merge takes `[16,1,2,3]`, central takes `[22,17,4,3]`,
and two stars takes `[22,22,22,8]`. All continuation stages report zero one-sided
and unresolved columns. Within each arm, repeats reproduce final coefficients
exactly. Across arms, death/merge are exactly equal; the maximum coefficient
difference is `3.137e-14 m` and sampled boundary difference is `1.047e-13 m`.

Central's final truth-boundary Hausdorff error is 0.06234 mm and its maximum
held-out relative field error is 0.12378%. The corresponding two-star values are
0.001721 mm and 0.000252%. Both reciprocal and compiled recover two stars here;
the historical FD run did not. **That recovery improvement is not attributable
to compilation.** The historical FD stage quotas curtailed accepted updates;
the cheaper analytic/reciprocal work allows more progress under the existing
ceilings. This is another reason not to report a controlled ratio against that
historical run.

Pre-dispatch [qualification](../../../../results/validation/speedup/SPD-006-20260916-qualification-01/README.md)
passed **33/33 checks**: 11 saved pre/post-event and difficult handoff states,
256/512 nodes, all four training frequencies, full reachable gauge directions,
plus fresh directional finite differences. Maximum prediction discrepancy is
`5.126e-14`, worst Jacobian column discrepancy `2.838e-13`, and FD discrepancy
`8.422e-9`. It used 352 work units and 103.02 seconds.

The complete workers passed **1340 angular checks**, all at orders 20/24.
Maximum prediction change is `7.875e-13`, worst derivative-column change
`8.455e-10`, and local/reduced system residual `3.290e-15`, below the original
`1e-11`, `1e-7` and `1e-10` gates respectively. Neither difficult scene needed
fallback. Merge records the intended single-component fallback 38 times per
worker. Independent refined candidate and final checks use full Kress.

**114 regression tests pass; one unavailable-CUDA test skips.** Coverage includes
full-gauge derivatives, weighted/complex-source data, translation reuse,
changed-shape invalidation, angular and geometric fallback, accounting and real
continuation integration. The earlier SPD-004/005 sealed bundles remain unchanged.

## Integrated scope and accounting

Use `--inverse-runtime compiled`, `SDF_INVERSE_RUNTIME=compiled`, or
`inverse_runtime("compiled")`. The profile selects the numerical backend;
readiness is separately enabled by this experiment's full-worker wrapper.
At SPD-006 closeout, the `fast` default was unchanged. The subsequent
[SPD-007 promotion](../iteration_07/01_results.md) makes compiled + reciprocal +
readiness the normal full-pipeline default; the timings here remain the original
sealed SPD-006 measurements.

Analytic Cartesian fits at 256 or more nodes use local Kress regular-to-outgoing
maps and a reduced coupled scattering system when there are at least two
components. Full production coefficients and gauge directions remain active.
Reconstructed source and receiver traces supply reciprocal derivatives without
materializing a separate dT for every coefficient. There is no experimental
solver import in production. This is scattering-matrix compilation on CPU,
not a CUDA or machine-code compilation change.

Caches are fit-local and keyed by exact local shape and numerical/material
settings. Pure translations can reuse local maps; changed shape or Cartesian
rotation coefficients recompile. The cylindrical normalization has a fixed
0.1 m scale, independent of the coefficient-sum bounding radius. Angular orders
increase to 24/28 or 28/32 if needed; failed convergence/residual checks,
overlapping bounding circles, unsupported configurations and single objects
retain full Kress. Existing coarse topology, TD, readiness and independent
validation paths remain full Kress. See the [backend documentation](../../../../solvers/gpr_bem_kress/README.md).

Per hard worker, completed physical systems fall from 1140 to 767 (central)
and 1123 to 562 (two stars), with 283 and 387 separately charged compiled
frequency batches. Across the four compiled hard workers, 2680 local
factorizations and 2680 reduced solves are recorded. These batches are not
equivalent-cost physical systems. Failed/refused physical calls are retained;
completed systems reconcile with passive inverse counts plus direct
readiness/endpoint predictions. All original work ceilings hold.

## Remaining cost and next action

After the timed campaign, a [CPU profile](../../../../results/validation/speedup/SPD-006-20260916-full-inverse/remaining_cost_profile/profile.txt)
replayed one compiled stage-one update from the central handoff, limiting only
`max_iterations` from 22 to 1. It reproduced the archived first accepted state
exactly and used five work units: three compiled batches and two refined full
systems. Qualification plus this diagnostic used **357 units / 129.97 s**,
within the predeclared 2000-unit / 1800-second allowance.

| Profiled operation | Calls | Cumulative time |
|---|---:|---:|
| One update, including profiler overhead | 1 | 26.96 s |
| Legacy stencil feasibility (`allowed`) | 136 | 23.86 s — 88.5% |
| Geometry admissibility, nested in the above and other checks | 275 | 23.03 s |
| Compiled evaluator, including its geometry work | 5 | 0.50 s |
| Local Kress compilation, nested in evaluator | 6 | 0.30 s |
| Reduced coupled solve/response, nested in evaluator | 6 | 0.021 s |

Nested times must not be added. This is one profiled update, not an 88.5%
whole-inverse claim. Nevertheless, it directly confirms the same bottleneck on
a difficult multi-object state after compilation: analytic Jacobians still
perform geometry validation for the old plus/minus FD stencils.

The [concrete geometry follow-up](../iteration_05/02_proposals/02_geometry_cost_followup.md)
identifies exact reuse of unchanged component validation and sampled adapters,
and cheap certified separation for boolean admissibility. Separately qualify
the existing true-analytic constraint policy on binding/one-sided cases; it can
remove entire stencil families but changes constrained-direction behavior.
Lazy Jacobian construction for rejected compiled trials is a smaller follow-up.
**These changes come before GPU work.** No geometry/policy change was mixed
into SPD-006, and no speed factor is claimed for the follow-up.

The production change is a qualified opt-in with modest measured benefit.
BIE-005's 2.48x local-fit result does not transfer to this complete inverse.
Retain the larger pipeline opportunities in the [outsider architecture brief](../iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md).

## Provenance and limits

The campaign froze 220 numerical/runner/test sources and 339 input artifacts;
current files and saved source copies match. Reporting/profiling scripts are
archived separately. A file-only monitor read logs every 55 seconds; our
numerical workers ran sequentially. Host-wide process isolation is unverified.
Final artifact hashes and reconciliation checks are in the result bundle.
Four noiseless scenes, two repeats, and one CPU profile do not establish
all-scene, noisy-data or GPU performance. Self-review only; no independent
reviewer claimed. Work remains on `feature/ordered-boundary-nystrom`.
