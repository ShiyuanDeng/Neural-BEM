# SPD-001 — combined analytic Jacobian and CPU/CUDA results

Executed 2026-09-15/16 under the user's instruction to proceed and produce
concrete runtimes. [Approved plan](../iteration_01/03_plan.md).
Owner/reviewer: Codex `/root`, self-review; no independent review claimed.

**Execution COMPLETE. Verdict: `MATCHED_ONE_UPDATE_SPEEDUP`.**
Recommend the opt-in **analytic Jacobian + fast CPU kernels** for this qualified
workload. It delivers almost all of the measured saving; CUDA linear algebra
adds little after these two changes. Production defaults remain FD/reference CPU.

[Measured report](../../../../results/validation/speedup/SPD-001-20260915-233833-combined/README.md)
· [CSV](../../../../results/validation/speedup/SPD-001-20260915-233833-combined/comparison.csv)
· [Numerical qualification](../../../../results/validation/speedup/SPD-001-20260915-233833-combined/qualification.json)
· [Verification](../../../../results/validation/speedup/SPD-001-20260915-233833-combined/verification.json).

## Actual times

One saved TOP-023 terminal two-star geometry, 24 paired sources, 34 gauge
directions, N=256/component with N=512 refined feasibility/acceptance,
double precision. Core Ultra 9 285K, RTX 5090, single-thread CPU BLAS.
All arms ran sequentially after TOP-025 and its renderer exited; source and
worker checks passed at every arm boundary. Imports and CUDA context startup
precede timing; per-arm transfers, factorization and synchronization are charged.

| Configuration | One-frequency Jacobian median | Four-frequency optimizer update | Update speedup |
|---|---:|---:|---:|
| Current FD/reference CPU | 42.10 s | 261.20 s | 1.00x |
| Analytic/reference CPU | 26.77 s | 208.73 s | 1.25x |
| FD/fast CPU kernels | 27.09 s | 151.73 s | 1.72x |
| Analytic/fast CPU kernels | 13.54 s | 100.42 s | **2.60x** |
| FD/fast kernels + CUDA | 25.09 s | 134.71 s | 1.94x |
| Analytic/fast kernels + CUDA | 13.44 s | 98.20 s | **2.66x** |

Jacobian rows are medians of three alternating-order repetitions at 1.25 GHz,
including objective setup and refined feasibility. Optimizer rows are one
complete measurement per arm: initial and terminal Jacobians, candidate search
and production/refined acceptance at 0.5/0.75/1.0/1.25 GHz. The optimizer uses
the stored production settings with one update opportunity. These are measured
update times, not full-reconstruction runtimes or multiplied microbenchmark estimates.

## Accuracy and interpretation

- All six arms accepted one update and reduced the objective from
  `2.19073145e-5` to about `2.129959e-5`. The largest final coefficient
  difference from FD was `2.176e-8 m` (0.022 micrometres), below the declared
  `1e-6 m` tolerance. Within the same Jacobian mode, changing the backend
  agreed to at most `3.259e-13 m` in coefficient infinity norm.
- The full 192x34 analytic Jacobian differed from the archived production-step
  FD matrix by `1.252e-5` relatively, with worst-column error `2.932e-5`,
  below `1e-4`. Analytic backend parity was better than `1e-12`; selected
  256/512 sensitivities agreed to `4.112e-12` worst-column relative error.
  Finite-step FD and an analytic derivative are not expected to be identical.
- Analytic differentiation cuts full assembled/factored systems from **560
  to 24**, but also performs **272 derivative assemblies**. Those assemblies
  take **185.4 s**, or **88.8%** of the reference analytic update. Thus a
  95.7% reduction in full-system counts gives only a 1.25x update speedup.
  The proposal's solve-count shares cannot be treated as runtime shares.
- Real-argument special-function routines cut derivative assembly to
  **85.7 s**. This is the main additional benefit. CUDA linear algebra then
  saves just **2.2 s (2.2%)** of the complete update and less than 1% of the
  repeated one-frequency Jacobian time. The single update timings do not
  establish a statistically reliable small CUDA advantage.

## Implementation and validation

Three new production modules (419 lines) and 69 added/11 removed lines across
six existing numerical files: about **490 added production lines**, plus tests,
documentation and experiment/reporting code. The coupled derivative largely
promotes BIE-004's existing implementation. No custom CUDA kernel was required.

- Retain one LU factorization per geometry/frequency and reuse it for tangent
  RHSs. Differentiate self/cross interactions, incident traces and receiver maps.
- Add an explicit `jacobian_mode="analytic"` to the existing optimizer and a
  scoped execution context for fast kernels and optional CUDA. The residual,
  LM update, quadrature, feasibility and acceptance formulas stay the same.
- Keep a true analytic policy and an optional FD-compatible constrained-stencil
  policy. Only the true policy is used in these timings; all measured columns
  had feasible FD stencils. Non-Cartesian coefficient bridges remain unsupported.
- **116 tests passed** before dispatch, covering existing Kress behavior,
  promoted derivative algebra, weighted one-/three-component directions,
  CPU/CUDA parity, factor reuse and constrained FD fallback. The import-isolation
  test permits only the two optional modules' Torch use and still checks that
  CPU import/factorization does not load Torch.
- **29 additional regression tests passed** after measurement for optimizer
  hooks, passive work accounting and recovery handoffs: **145 passed in total**.
- Both numerical stages finished within their 3,600 s ceilings: **645.0 s**
  for qualification/Jacobian repetitions and **955.3 s** for optimizer arms.
  Charged totals: **3,945 assembly equivalents**, **1,538 derivative assemblies**,
  **2,407 factorizations**, within all caps. No numerical arm failed.

[API and usage](../../../../solvers/gpr_bem_kress/README.md#optional-coupled-jacobians-and-execution-settings-spd-001)
· [Experiment runner](../../../../experiments/spd001_analytic_jacobian/README.md).
Original and measured source snapshots, inputs, every Jacobian/trajectory,
acceptance checks, process state and work counts are retained in the bundle.

## What this resolves and what remains

The bounded integration and combined runtime question are resolved: about
**2.6x per measured complete update**, with matched endpoints. The requested
successor to BIE-004 was filed under the new **SPD-001 speed-up track**, rather
than BIE-007.

Full recovery across scenes, larger bandwidths, lossy materials, topology
controller integration and a default change are not established by this run.
The next useful validation would be matched full recoveries with the fast CPU
analytic mode. Further kernel-value reuse across directions is a plausible
optimization, but was not implemented or assigned an estimated speedup here.
