# SPD-002 — fast CPU default, verified on complete topology pipelines

2026-09-16. **Execution COMPLETE; validation PASS.** The user's request to make
the faster implementation the default is fulfilled under the
[approved plan](../iteration_02/03_plan.md). Owner/reviewer: Codex `/root`,
self-review; no independent review claimed.

**Existing Cartesian topology commands now default to analytic Jacobians and
faster CPU kernels**, including candidate refinement and all continuation
stages. No additional flag is required. CUDA remains optional. Radial
coefficient states use FD until their analytic bridge exists.

[Full measured report](../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/README.md)
· [CSV](../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/comparison.csv)
· [Verification](../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/verification.json).

## Complete-pipeline timings

The actual TOP-025 scene worker ran each original start through automatic
topology and all four frequency-continuation stages. Same prepared observations,
24 pairs, optimizer settings, N=64/128 topology and N=256/512 continuation,
feasibility, acceptance and recovery gates. Four sequential CPU runs, single
BLAS thread, no concurrent numerical workers. Times include worker startup and
endpoint checks, with no video rendering. Each row is one timing per profile.

| Full case | Reference FD/CPU | New default | Speedup | Recovery |
|---|---:|---:|---:|---|
| Death | 434.65 s | 233.73 s | **1.86x** | Both pass |
| Split | 418.01 s | 221.53 s | **1.89x** | Both pass |

Maximum differences between recovered boundaries, on the 4096-point comparison
grid, were `2.432e-11 m` and `6.907e-11 m`, well within the declared 1 micrometre
comparison tolerance. Maximum coefficient differences were `1.130e-11 m` and
`4.048e-11 m`. The complete recovery and resolution gates passed for all four
runs; these are full pipeline measurements, not extrapolated Jacobian ratios.

The earlier SPD-001 2.60x number covered one update with the true analytic
constraint policy. The promoted default preserves FD stencil semantics using
geometry-only feasibility checks and one-sided fallback where required. Full
pipeline timings additionally include topology and endpoint validation. Use
the measured full-case ratios above for these cases.

## Integration and safeguards

- `sdf_inverse.runtime` supplies the default and a reference profile. Existing
  shared inverse/objective/TD calls inherit the execution context; explicit
  caller-supplied kernel/device contexts take precedence.
- The controller, benchmark, challenge driver and current TOP-025 runner expose
  `--inverse-runtime reference`. `SDF_INVERSE_RUNTIME=reference` also covers
  other callers and spawned workers. New manifests record the profile;
  prepared benchmark/campaign runs reject a changed profile.
- The physical-system ledger counts analytic base solves. Separate derivative
  attempt/completion/failure counters prevent unmetered analytic work.
  `budget_work_units` charges a full system or a directional assembly/tangent;
  historical `total_attempted` fields continue to mean full systems.
- Reference/fast death used 1063/157 full systems, with 470 fast derivative
  assemblies. Split used 1037/193 full systems, with 451 fast derivative
  assemblies. Every count reconciled and all caps were respected.
- **261 tests passed**, including real continuation with default selection,
  feasible-stencil handling, numerical/backend parity, worker inheritance,
  context restoration, topology controls and failure/cap accounting. Historical
  FD/synthetic-residual controls explicitly select the reference path. The
  old TOP-017 frozen-source guard still rejects the later solver changes.

No numerical or rendering worker was running before edits. Source snapshots
and inputs remained unchanged during timing. Historical SPD-001 and TOP-025
bundles were preserved. Failed development test logs are retained alongside the
final passing test log; no full-pipeline arm failed.

## Use and scope

Keep using the existing Cartesian topology command: the faster mode is selected
automatically. Add `--inverse-runtime reference` for the previous implementation.
For a Python call, use `with sdf_inverse.runtime.inverse_runtime("reference"):`.
See the [pipeline guide](../../../pipelines/explicit_cartesian_fourier.md) and
[runtime API](../../../../solvers/sdf_inverse/runtime.py).

Default promotion is complete. This validates two full cases; the all-twelve
TOP-025 scorecard remains historical reference-mode evidence. Equal speedup or
unchanged trajectories on every harder scene are not established by these
controls. No additional full campaign was launched.
