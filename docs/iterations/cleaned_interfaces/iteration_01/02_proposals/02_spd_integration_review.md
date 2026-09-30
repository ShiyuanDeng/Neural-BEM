# SPD integration requirements for CI-001

2026-09-30. Requested by the user: check the latest SPD work and integrate it
when writing the cleaned implementation. Owner: Codex. This is an integration
assessment of saved evidence and current code, not a new numerical experiment
or an independent review of the original SPD work.

## Decision

The cleaned inverse must preserve the qualified SC runtime improvements from
SPD-010 through SPD-015 and integrate SPD-016's selected Mie-grid plus damped
assembly acceleration through maintained interfaces. Performance retention
includes this accelerated execution baseline, not only reconstruction accuracy.

SPD-016 is the latest completed result in the
[speed-up handoff](../../../speedup/README.md). It is a qualified experimental
bundle and is not yet integrated into ordinary solver calls. SPD-015 remains
the native geometry default. Both states must remain clear in CI-001 records.

## What belongs in the cleaned implementation

| Work | Current evidence/state | Integration responsibility |
|---|---|---|
| SPD-010: independent-frequency threading | Integrated; ordered results and serial-order ledger behavior, with caller context propagated to worker threads | Shared execution service; preserve deterministic ordering, scoped caches and configurable concurrency |
| SPD-011/012: real-frequency CUDA assembly and LU, automatic dispatch | Integrated; `auto` uses CUDA when available, CPU otherwise; recorded CPU retry for device out-of-memory; explicit CPU reference remains available | Nodal physics backend and execution configuration; preserve float64/complex128, residual checks, factor reuse and bounded device memory |
| SPD-013: multicomponent real-frequency CUDA | Qualified and integrated for the separate coupled extension | Preserve compatibility in shared solver code; the coupled scenes do not enlarge CI-001's 36-case benchmark |
| SPD-014/015: exact spatial geometry checks and bounded validation caches | Integrated native default, with dense/pathological-case fallback and reference mode | Geometry validation plus fit/objective/diagnostic scopes, reusable by future physics backends |
| SPD-016: Mie Hankel-order recurrence and GPU grid contraction | Qualified experimental implementation; same finite mask, selected starts and localization objective | Localization evaluator service; keep the grid, radial coefficients, clearance rules and coordinate refinement unchanged |
| SPD-016: complex-frequency CUDA assembly and existing device LU | Qualified on the fixed damping ray `1 + 0.25i`; experimental bundle only | Nodal backend kernel implementation, with explicit support checks and unchanged near-pair series, Kress weights and diagonal terms |
| SPD-016 optional source/receiver-field tables | Correct on the tested screen, but no consistent incremental end-to-end saving | Preserve the evidence; do not select this extension for the cleaned default |

Earlier SPD topology-specific readiness shortcuts and compiled scattering
policies are not automatically part of the SC/MA algorithm. Their existence
does not justify changing the continuation policy during this integration.

Sources: [SPD-010/011](../../../speedup/iteration_09/01_results.md),
[SPD-012/013](../../../speedup/iteration_10/01_results.md),
[SPD-015](../../../speedup/iteration_12/01_results.md), and
[SPD-016](../../../speedup/iteration_13/01_results.md).

## Latest measured result: SPD-016

The [evidence bundle](../../../../../results/validation/speedup/SPD-016-20260930-damped-gpu/README.md)
contains two fresh matched complete MA-004 D attempts:

| Configuration | Reference | Grid + assembly | Speedup | Work units in either arm |
|---|---:|---:|---:|---:|
| Shifted star, contrast 0.5 | 245.45 s | 101.11 s | 2.43x | 1,536 |
| New asymmetric, contrast 13.3 | 396.52 s | 143.95 s | 2.75x | 2,321 |

Recovery, configurations, localization starts, stage counts, accepted-step
counts, trial/acceptance decisions and work match. The largest relative
accepted-curve difference is 1.83e-11. The primary qualification has 27 passing
records; the optional field arm adds 24 passing records and five fallback
checks. The field extension changes the two accelerated attempt times to
107.81 and 143.44 s, so it supplies no consistent additional benefit.

These are two noiseless single-object cases, with one run per arm/scene on a
shared RTX 5090, four frequency threads and one BLAS thread. The timings cover
localization, fitting and audits from the original circles but exclude the
MA-005 DF tail. Including process startup, the primary speedups are 2.40x and
2.74x. Neither an all-36 speedup nor noisy-case or general-complex-frequency
qualification follows from these measurements.

SPD-010 through SPD-015's SC-043 inverse timings cover saved continuation
suffixes. They must not be multiplied by SPD-016's speedup or presented as
full-reconstruction speedups on all 36 cases.

## Interface and integration constraints

1. **Keep solver selection distinct from execution settings.** Selecting nodal
   Kress or modal Müller chooses a numerical backend; CPU/GPU and frequency
   concurrency configure execution. The policy supplies frequencies, shape
   bands and decisions without knowing which kernel or device implements them.
2. **Replace prototype overrides with explicit dependencies.** SPD-016's
   `runtime.install()` overrides the Mie landscape and damped solve, and
   `gpu_matrix()` temporarily replaces a CUDA kernel function. Extract their
   numerical implementations into maintained services; do not carry those
   process-global mutations or imports from result directories into the clean
   execution path. Pass localization and physics implementations explicitly.
3. **Preserve support checks and define reference execution.** The damped table
   uses 111 degree-24 Chebyshev panels over real arguments `[0.01, 100]` on
   `1 + 0.25i`. The prototype checks the ray and rejects out-of-range arguments.
   Preserve those checks. Define recorded CPU/reference execution for supported
   physics outside the accelerated envelope and for unavailable devices, under
   an explicit automatic-execution setting; explicit GPU requests must have
   clear failure semantics. Do not extrapolate the table or silently substitute
   real-frequency data. Existing real-frequency OOM behavior is a baseline to
   preserve; equivalent damped behavior needs integration validation.
4. **Keep cache and factor lifetimes bounded.** Preserve SPD-015's exact cache
   keys, thread safety, context precedence and cleanup on exit/exception. Keep
   device assembly synchronization and host retention of reusable LU factors;
   do not restore the unbounded device retention that caused earlier OOMs.
5. **Retain the unchanged algorithm.** Localization recurrence and GPU
   contraction must preserve the objective, finite mask, selected starts and
   coordinate refinement. Kernel acceleration must preserve the matrix model,
   derivative coordinates, geometry checks, acceptance rules, budgets and
   stopping decisions. Algorithmic changes needed for all-36 retention must
   be measured separately from execution equivalence.
6. **Carry the portable improvements into future solver integrations.** Scoped
   geometry reuse, ordered frequency execution, localization acceleration and
   accounting should remain available when a modal backend is selected. The
   nodal Kress assembly kernels remain internal to that backend; a modal backend
   supplies its own implementation and cannot inherit their timing claims.

## Verification to include in CI-001

- First reproduce the two SPD-016 pairs through the clean interfaces, retaining
  the original quality/work gates and reporting matched current timings. The
  original cost gate was at least 20% saving per pair, not an obligation to
  reproduce an exact shared-host wall time.
- Preserve focused threading, real-frequency CPU/CUDA, factor reuse,
  geometry-predicate/cache and failure-path checks from the earlier SPD work.
  Keep the serial CPU reference usable for diagnosis.
- Extend checks to the actual cumulative policy, noisy inputs, additional
  contrasts, transient geometries and complete DF paths used by the 36-case
  campaign. Saved two-case D results do not substitute for this validation.
- Measure the cleaned accelerated pipeline against an explicitly documented
  current accelerated baseline, as well as the reference execution where
  needed to isolate correctness. Report localization, damped/undamped fitting,
  diagnostics, audits and setup/transfer costs. Keep worker/thread counts and
  host load visible, and retain source snapshots before extracting code.

For this documentation review, all 163 SPD-016 reference source/input hashes
and both script manifests (6 and 12 entries) were rechecked successfully.
The saved primary comparison receipts pass every quality/work and cost gate.
No numerical workers were launched and no SPD artifacts were changed.
