# SPD-001 — measured analytic Jacobian and CPU/CUDA speed

**Controlled six-arm comparison complete.** Numerical defaults remain FD/reference CPU.

The current TOP-023 terminal two-star geometry was replayed with current production geometry validation, 24 paired sources, N=256 per component, complex128 and single-thread CPU BLAS. All arms ran sequentially after TOP-025 and its renderer finished; their process checks found no sibling numerical/render worker. CUDA timings include copies, factorization, solves and synchronization. Python imports and one-time CUDA context initialization precede timing; these are warm-process measurements.

## Complete one-frequency Jacobian

At 1.25 GHz, 34 directions. Each row includes the base objective, initial refined feasibility and the complete Jacobian assembled by the actual optimizer. An intentionally large gradient stopping tolerance ends this timing after the initial Jacobian; it is not used for optimizer-update measurements. Three alternating-order repetitions per arm, with setup charged in each.

| Arm | Median [min, max] seconds | Speedup | Relative difference from FD Jacobian |
|---|---:|---:|---:|
| fd_cpu | 42.102 [41.763, 42.105] | 1.00x | 0.000e+00 |
| analytic_cpu | 26.769 [26.731, 26.842] | 1.57x | 1.405e-05 |
| fd_fast_cpu | 27.087 [27.004, 27.087] | 1.55x | 6.981e-12 |
| analytic_fast_cpu | 13.541 [13.471, 13.597] | 3.11x | 1.405e-05 |
| fd_fast_cuda | 25.095 [25.084, 25.096] | 1.68x | 9.862e-12 |
| analytic_fast_cuda | 13.439 [13.435, 13.466] | 3.13x | 1.405e-05 |

## Actual bounded optimizer

Four training frequencies (0.5/0.75/1.0/1.25 GHz), production FD step 1e-4, N=256 production/N=512 feasibility and candidate acceptance. One update opportunity, including the initial and terminal Jacobians, line search and production/refined acceptance. Stored optimizer settings are identical across arms. These are single complete measurements per arm, not repeat medians or full reconstruction times.

| Arm | Seconds | Speedup | Accepted updates | Final objective | Max coefficient difference from FD (m) |
|---|---:|---:|---:|---:|---:|
| fd_cpu | 261.199 | 1.00x | 1 | 2.12995959e-05 | 0.000e+00 |
| analytic_cpu | 208.732 | 1.25x | 1 | 2.12995842e-05 | 2.175e-08 |
| fd_fast_cpu | 151.731 | 1.72x | 1 | 2.12995959e-05 | 3.258e-13 |
| analytic_fast_cpu | 100.423 | 2.60x | 1 | 2.12995842e-05 | 2.175e-08 |
| fd_fast_cuda | 134.714 | 1.94x | 1 | 2.12995959e-05 | 8.686e-14 |
| analytic_fast_cuda | 98.197 | 2.66x | 1 | 2.12995842e-05 | 2.175e-08 |

All six arms accepted one update and their final coefficient differences from FD stayed within the declared 1e-6 m tolerance.

## Where the optimizer time goes

| Arm | Full systems assembled/factored | Derivative assemblies | Derivative assembly seconds (% of wall time) |
|---|---:|---:|---:|
| fd_cpu | 560 | 0 | 0.000 (0.0%) |
| analytic_cpu | 24 | 272 | 185.412 (88.8%) |
| fd_fast_cpu | 560 | 0 | 0.000 (0.0%) |
| analytic_fast_cpu | 24 | 272 | 85.681 (85.3%) |
| fd_fast_cuda | 560 | 0 | 0.000 (0.0%) |
| analytic_fast_cuda | 24 | 272 | 86.230 (87.8%) |

A full system solve and a derivative assembly are different units of work. The analytic path retains one LU per base geometry/frequency and solves tangent RHSs with it, but each direction still assembles dense derivative operators. Those assemblies dominate the analytic runtime. Execution phase timers are nested (for example, tangent response contains RHS solves); do not sum them as disjoint phases.

## Interpretation and limits

Derivative choice and hardware choice are measured separately. Analytic derivatives eliminate perturbed forward solves, while fast real-argument Bessel routines also accelerate derivative assembly. CUDA reuses one LU per geometry/frequency for all tangent columns. Its incremental contribution is the difference between the fast-CPU and fast-CUDA rows within the same Jacobian mode.

Analytic columns need not equal a finite-step FD approximation exactly; trajectory discrepancies are reported above. Backend comparisons within a derivative mode must stay within 1e-6 m in coefficient infinity norm. No claim covers a completed recovery, a changed default, all scenes, or lossless-to-lossy extension. The optional FD-compatible constrained-stencil mode was unit-tested; this terminal state uses the true analytic mode and has no FD-refused columns in the continuation comparison.

## Validation and provenance

- 116 Kress, analytic/backend and FD-constraint tests passed before dispatch. The isolation test explicitly allows function-local Torch use in the optional execution and existing geometry-pullback modules; a clean CPU import/factorization still verifies that Torch is not loaded.
- `accounting_hooks_tests.log`: 29 additional optimizer-hook, work-accounting and recovery-handoff regression tests passed after the timing process exited.
- `qualification.json`: all 192x34 four-frequency columns compared with the archived FD Jacobian; accelerated analytic paths compared directly with analytic CPU; selected refined-grid sensitivities checked.
- `arms/`: every measured trajectory, matrix, acceptance check, phase count, timing and environment.
- `baseline_sources/` and `measured_sources/`: original and measured numerical source snapshots.
- `manifest.json`, `workspace_before.json`, `budget.json`, `approved_plan.md`, `tests.log`, `execution.log`: provenance, setup and all charged work. `comparison.csv` and `summary.json` are generated from the arm records.
- `verification.json` reconciles charged work and verifies original/measured/current source hashes and saved numerical errors. `artifact_manifest.json` hashes every final bundle file except itself.

Rebuild: `PYTHONPATH=solvers:. python -m experiments.spd001_analytic_jacobian.summarize <bundle>`. No BIE solves occur during reporting.
