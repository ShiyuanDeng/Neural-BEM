# Further acceleration of the full inverse

2026-09-16. Requested by the user: think beyond the roughly 2x FD-to-analytic
improvement, including GPU/CUDA, and retain the work in the speed-up iterations.
This is a source and saved-artifact audit plus a ranked proposal. No new solver
run or timing was performed. Inspected checkout: `7add2b41ba0adcd5dceb2d2ba7bef369f415ebd3`
on `feature/ordered-boundary-nystrom`; unrelated working changes were preserved.
Author: Codex `/root`; independent reviewer: unassigned.

**Later clarification:** the user asked for an outsider's view of pipeline
architecture. The [subsequent design brief](03_pipeline_redesign_outsider_view.md)
broadens the question and takes precedence for selecting next work. The local
implementation opportunities below remain valid proposals.

**Recommendation: first remove exact repeated work across continuation stages,
then cache the kernel values shared by all directions at a new geometry.**
After that, compare CPU frequency parallelism with GPU derivative assembly.
The current CUDA option accelerates linear algebra while leaving the dominant
derivative assembly on the CPU.

## What the existing speedups actually establish

| Measurement | Earlier implementation | Faster implementation | Interpretation |
|---|---:|---:|---|
| Complete death pipeline | 434.65 s | 233.73 s | 1.86x, both recover |
| Complete split pipeline | 418.01 s | 221.53 s | 1.89x, both recover |
| One four-frequency update, fast analytic CPU versus CUDA | 100.42 s | 98.20 s | Only 2.2% less wall time from CUDA; single measurement |

The full-pipeline comparison changed **both** the Jacobian and CPU kernel
implementation. It does not isolate a 2x benefit from analytic differentiation
alone. See [SPD-002](../01_results.md) and
[SPD-001](../../iteration_02/01_results.md). The CUDA row uses SPD-001's true
analytic constraint policy; the full pipelines use the promoted FD-compatible
policy. Those ratios should not be multiplied together.

The [saved fast-CPU update](../../../../../results/validation/speedup/SPD-001-20260915-233833-combined/arms/optimizer_analytic_fast_cpu_0/result.json)
spent **85.68 / 100.42 s = 85.3%** in derivative assembly. Tangent response,
including its solves, took 2.02 s. These timers are nested: do not add
`rhs_solve` to `tangent_response` as if they were disjoint. The 85.3% share is
an **update** profile, not a measured share of the two complete inverses.

In the full fast runs, the continuation ledger reports 197.19 s for death and
197.97 s for split, about 84% and 89% of their complete worker times. Those
figures include continuation work and checks, not just Jacobians. Sources:
[death metrics](../../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/fast/runs/death/F/metrics.json),
[split metrics](../../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/fast/runs/split/F/metrics.json),
and [worker times](../../../../../results/validation/speedup/SPD-002-20260916-default-pipeline/timings.json).

## Ranked opportunities

The ranking is an engineering judgment from this audit, not a measured ranking.

| Priority | Change | Evidence and expected scope |
|---|---|---|
| 1 | Exact per-frequency prediction/Jacobian reuse across continuation | Both saved full cases repeatedly differentiate the same state; small cache, direct full-pipeline opportunity |
| 2 | Cache kernel values and radial slopes within each analytic base | Removes repeated special functions and primal algebra for every direction; applies when geometry changes too |
| 3 | Parallelize frequencies inside one inverse | Current frequency loop is serial; each frequency has independent assembly, LU and derivative work |
| 4 | GPU assembly and contractions, with arrays retained on device | Targets the expensive part missing from the existing CUDA implementation; more implementation and accuracy work |
| 5 | Classify constrained columns before computing derivatives | Current optimizer computes analytic columns that it subsequently zeros or replaces with one-sided FD |
| 6 | Reuse the accepted objective's exact base factors | Objective results retain predictions but discard the systems needed by the analytic Jacobian |
| 7 | Receiver adjoints or tiled tangent batches | Can reduce solve/dispatch work and dense derivative storage; current tangent time alone limits the benefit |
| 8 | Cache exact geometry checks and endpoint predictions | Potential secondary full-pipeline savings; preserve every validation result and its provenance |

### 1. Reuse identical frequency derivatives across continuation

Reading all four `stage_*/jacobians.jsonl` and `terminal.json` files under the
two metric directories above gives:

| Fast case | Jacobians in stages 1–4 | State across all four stages | Accepted continuation steps | Directions per frequency |
|---|---|---|---:|---:|
| Death | 1, 1, 1, 1 | Same SHA-256 (`e6a4195e…`) | 0 in every stage | 34 |
| Split | 1, 1, 1, 1 | Same SHA-256 (`d1661556…`) | 0 in every stage | 34 |

Both use 256/512 production/refined nodes throughout continuation and have zero
one-sided or unresolved columns. Death stops at loss tolerance; split stops
with no decreasing step. Both pass the full recovery gates. Consequently these
controls exercise substantial repeated terminal work; they do not establish
performance on a long sequence of changing continuation geometries.

The cumulative frequency schedule visits 1 + 2 + 3 + 4 = **10 frequency bases**
at this same state, although only **4 distinct frequencies** are present.
With matching complete cache keys, raw per-frequency reuse would reduce the
continuation derivative assemblies from **340 to 136**, eliminating **204
(60%)**. Relative to the full-run totals of 470 and 451 assemblies, that is
43.4% and 45.2% respectively. These are potential work-count reductions;
they are not wall-time predictions or evidence of an implemented cache.

Cache the raw complex prediction and raw complex response derivatives for each
frequency and direction basis. **Rebuild the normalized residual/Jacobian for
each stage.** The active-frequency set changes the residual weighting; reusing
the previous stage's normalized matrix would be incorrect. Likewise, recompute
stage loss, gradient and stopping checks from the current objective.

Key exact coefficient bytes and component order, parameterization/gauge basis,
node grids and period, frequency, material constants, acquisition points and
source strength, quadrature/branch settings, dtype and backend. Include every
feasibility setting and FD step if caching constrained-column results. Cache
raw analytic columns separately from that policy, and reapply the policy on
each call. Invalidate on topology, geometry, basis, resolution or input changes;
never use approximate geometry matching. Bound cache lifetime to the run and
retain only a small number of exact states.

The cache must live above individual optimizer invocations: the local
`evaluate()` cache in
[radial_topology.py](../../../../../solvers/sdf_inverse/radial_topology.py)
already avoids duplicate objectives within one call but cannot span the
continuation stages. This is exact memoization of an unchanged discrete
problem; it does not reuse an approximate operator at a moved boundary.

### 2. Stop rebuilding kernel values for each direction

[cartesian_residual_jacobian](../../../../../solvers/sdf_inverse/analytic_jacobian.py)
already retains one LU per frequency and computes geometry directions once.
Those savings are implemented. However,
[directional_operators](../../../../../solvers/gpr_bem_kress/coupled_shape_derivative.py)
still reconstructs primal and derivative A/B/C for each direction, and
[_special / _radial / _difference_matrices](../../../../../solvers/gpr_bem_kress/shape_derivative.py)
reevaluate identical Bessel/Hankel values, near-series coefficients, distances,
Kress corrections and primal consistency norms.

Prepare immutable pair geometry and, per frequency, the six radial functions
and their exact radius derivatives. At fixed materials a shape direction needs
`dF = F_r * dr`; it does not need another special-function evaluation. Preserve
the actual truncated near series, its derivative, analytic diagonals and the
base's near/direct branch. Keep source and receiver kernels in the same base
preparation. Cache validity is part of the numerical contract.

Then propagate direction-specific point, normal and weight changes using those
arrays. Build/check the primal once per exact base, with exhaustive old/new
primal and directional checks in qualification. Keep finite-value checks on
every result. Simply deleting consistency checks from the existing path would
not establish that a replacement cache is correct.

For a local illustration only, if derivative assembly alone were made 2x or
4x faster at the *old update's* measured share, Amdahl's formula
`S = 1 / ((1-p) + p/s)`, with `p=0.8532`, gives **1.74x or 2.78x additional
update speedup**. These are conditional calculations, not forecasts for caching
or for the full inverse. Reprofile the full pipeline after each change; reuse
and parallelization savings overlap.

### 3. Use CPU cores for independent frequencies

Parallelize the frequency body of `cartesian_residual_jacobian`, with a
persistent, bounded worker pool and one BLAS thread per worker initially.
Compare 1, 2 and 4 workers with the same complete inverse. Reassemble residual
rows in the original frequency order, propagate runtime settings explicitly,
and aggregate work/failure counters in the parent. Charge pool startup,
serialization, shared-memory preparation and peak memory.

Use one level of parallelism first. Stages with one frequency cannot benefit
from frequency parallelism; after exact caching, a stage may have just one
new frequency even when four are active. Direction tiles are a later option
for that case, using a shared immutable base without refactorizing per worker.
Benchmark those mechanisms separately. Parallel scenes improve campaign
throughput, but are not a speedup of one full inverse.

### 4. Make CUDA execute the expensive assembly

The current [execution backend](../../../../../solvers/gpr_bem_kress/execution.py)
copies each direction's dA/dB/dC to CUDA and synchronizes transfers/solves.
The saved analytic CUDA update records 880 host-to-device transfers, but only
0.64 s in that transfer timer versus 86.23 s in CPU derivative assembly.
Removing transfers alone cannot explain a large improvement on this workload.
Source: [CUDA update ledger](../../../../../results/validation/speedup/SPD-001-20260915-233833-combined/arms/optimizer_analytic_fast_cuda_0/result.json).

The useful GPU design is to prepare exact kernel data, then keep geometry,
kernel tables, LU factors, U and C on the device through derivative assembly,
contraction and solve. Return paired responses or small Jacobian blocks. Test
CPU-prepared kernel tables plus GPU contractions as a separate arm before a
complete GPU kernel implementation. This follows NVIDIA's advice to retain
intermediate arrays on device and include transfer costs in comparisons.
[CUDA best practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/).

For the current positive-real, lossless kernel arguments, CUDA supplies
double-precision `j0`, `j1`, `jn`, `y0`, `y1`, `yn`; these provide ingredients
for `H_n = J_n + i Y_n` and the derivative recurrences already used here.
They do not establish numerical parity with SciPy or supply the Kress near
series. Qualify those branches and diagonals explicitly in float64/complex128.
[CUDA Math API](https://docs.nvidia.com/cuda/cuda-math-api/cuda_math_api/group__CUDA__MATH__DOUBLE.html).
CuPy lists the real Bessel routines but currently lists no `scipy.special.hankel1`
equivalent, so a NumPy-to-CuPy substitution is not a complete port.
[CuPy special functions](https://docs.cupy.dev/en/stable/reference/scipy_special.html),
[comparison table](https://docs.cupy.dev/en/stable/reference/comparison.html).
These documentation checks were made on 2026-09-16; installed-version support
still needs checking at implementation time. Complex lossy arguments need
their own qualified path, not a silent use of real-argument routines.

Tile directions and pair interactions. For two components at 512 nodes each,
one 2048-by-2048 complex128 dA consumes **64 MiB**; 34 directions at four
frequencies would consume **8.5 GiB for dA alone**. Preserve streaming or
contract blocks directly into `dA @ U` instead of materializing every dA.
Compare fused compiled CPU contractions with GPU contractions too: the best
backend after caching is unmeasured. No FP32/Tensor Core speedup is assumed.

### 5–8. Secondary exact-work savings

- **Constrained columns:** in `jacobian()`, run the same retraction and
  production/refined feasibility checks first. Compute analytic columns only
  where both sides are allowed; use the current one-sided FD or zero-column
  behavior elsewhere. Preserve failure handling, diagnostic counts and budget
  reservations explicitly. This cannot save columns in the two recorded
  continuation controls, whose stencils are all feasible; measure its share
  on topology states before prioritizing it.
- **Objective/base reuse:** `MultiRadialObjectiveEvaluation` contains the
  prediction but no reusable A/B/C/LU. Passing an exact accepted base into the
  Jacobian could avoid its independent base solve. Retain a bounded cache and
  preserve primal qualification. The current local residual cache and retained
  tangent LU must not be reported as new improvements.
- **Receiver adjoints:** with `A U = B`, solve `A^H Lambda = C^H` once per
  frequency. Then the paired complex derivative is
  `dY_pp = (dC U)_pp + lambda_p^H (dB_p - dA U_p)`.
  This retains the full residual Jacobian and its LM model while replacing
  direction-by-direction tangent solves with receiver contractions. It still
  needs derivative work; a scalar loss adjoint alone does not supply `J^T J`.
  The 2.02 s tangent-response profile makes solve removal alone a secondary
  target. Reverse accumulation into geometry before the Fourier pullback may
  also reduce repeated directional assembly, but requires separate derivative
  qualification. Tiled multi-RHS tangent solves offer a smaller alternative.
- **Geometry and endpoints:** cache immutable grid/index data and exact
  repeated feasibility or endpoint predictions using complete keys. Retain
  all production/refined and held-out checks, and recompute their scores under
  the relevant data. Endpoint observations must remain outside optimization.

## Ideas to defer or treat as different comparisons

Approximate Jacobian reuse, Broyden updates, skipping terminal gradients,
changing the LM optimizer, fewer frequencies/nodes, lower precision and looser
acceptance tests can alter the trajectory or its qualification. They need
separate controls rather than being bundled into an execution optimization.
The prior [BIE-006 result](../../../boundary_bie/iteration_04/01_results.md)
already rejects the tested first-order operator reuse mechanism. Exact caching
at the identical state does not reopen that negative result.

FMM/iterative solves and mixed-precision factorization should wait for a profile
where matrix solves or memory are material bottlenecks. More BLAS threads or a
faster GPU LU cannot remove the present CPU assembly cost by themselves.

The [FDE accounting observation](../../../field_defined_events/iteration_01/01_results.md)
also belongs here: `jacobian_work_bound` is a conservative reservation unit,
not elapsed-time prediction. It can reserve 25 units for 12 analytic directions
versus 24 for FD despite the analytic calculation using one base factorization.
Record cache hits, actual assemblies/solves, reservations and elapsed time
separately. Changing caps to buy more optimizer progress is a different
comparison from making the same inverse faster.

## Proposed next step and success criterion

[SPD-003](02_SPD003_exact_continuation_reuse_contract.md) isolates exact
per-frequency continuation reuse against the current fast default. Kernel
precomputation is the next general optimization if changing-state profiles
still show assembly dominance. CPU parallelism and CUDA assembly remain
separate candidate experiments, not approved implementations.

For every mechanism, measure from the original initialization through topology,
all continuation stages and endpoint checks. Keep the data, frequencies,
geometry resolution, optimizer settings and stopping rules fixed. Include
preparation, startup, transfers, synchronization and fallback work. Require
matching topology/recovery gates and endpoint boundaries, and report changed
trajectories separately. Use repeated sequential A/B runs with source/input
hashes, declared machine load and memory. Include a case with changing
continuation geometry before making a broad full-inverse claim.
