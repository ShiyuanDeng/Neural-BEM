# SPD-002 — fast default in the current topology pipeline

**PASS.** Analytic Cartesian Jacobians and faster CPU kernels are now the default. The reference profile restores FD/reference CPU; CUDA is optional.

The actual TOP-025 `run_scene` pipeline ran from original death/split starts and saved observations, through automatic topology and all four frequency-continuation stages. No optimizer settings, resolutions, acceptance formulas or acquisition changed. N=64/128 for topology and 256/512 for continuation; 24 pairs, four training frequencies. Runs were sequential with one CPU BLAS thread. Single complete timing per profile, including worker startup and endpoint checks; no rendering.

| Case | FD/reference CPU | New default | Speedup | Maximum boundary difference | Recovery |
|---|---:|---:|---:|---:|---|
| death | 434.65 s | 233.73 s | 1.86x | 0.000024 um | Both pass |
| split | 418.01 s | 221.53 s | 1.89x | 0.000069 um | Both pass |

## Work and correctness

| Case | Reference full systems | Fast full systems | Fast derivative assemblies/tangents |
|---|---:|---:|---:|
| death | 1063 | 157 | 470 |
| split | 1037 | 193 | 451 |

Both physical-system and derivative attempt/completion/failure counts reconcile. Budgets charge one unit per full frequency system or analytic directional assembly/tangent. Existing `total_attempted` values remain physical-system counts; `budget_work_units` includes derivatives. Feasible-stencil fallback, damping, geometry gates and endpoint checks remain active.

SPD-001 measured a single update with the true analytic constraint policy. The promoted default uses the FD-compatible policy, which checks perturbation feasibility before retaining analytic columns. These full runs also include topology and endpoint validation, so their speedup should be read directly from this table rather than inferred from the earlier 2.60x update.

261 tests passed, including real continuation/default selection, constrained derivatives, CPU/CUDA numerical parity, topology controls, worker inheritance and budget-failure handling. Historical tests prescribing FD or synthetic residuals explicitly select FD/reference mode. The archived TOP-017 source-lock test verifies rejection of later solver changes.

## Use

Existing Cartesian topology commands use the fast mode without changes. Add `--inverse-runtime reference` to the controller, benchmark, challenge or current TOP-025 runner to restore FD/reference CPU. `SDF_INVERSE_RUNTIME=reference` works for other callers and spawned workers. In Python use `with sdf_inverse.runtime.inverse_runtime("reference"):`. Radial coefficient states retain FD under automatic selection. Explicit execution contexts are respected.

## Provenance and limits

`manifest.json` and `measured_sources/` freeze this implementation. Profile subfolders retain identical input copies, their hashes, every topology event/iterate, continuation state, acceptance check, work ledger and recovery gate. `timings.json` includes process checks and load averages. The approved plan, test logs, summary CSV/JSON and artifact hashes are saved. Reporting can be rebuilt with `python -m experiments.spd002_default_runtime.summarize BUNDLE`.

These two full-case controls support the default change and measured saving. They are not a rerun of all twelve scenes, and do not establish that every scene speeds up equally.
