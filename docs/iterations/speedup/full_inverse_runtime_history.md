# Full-inverse runtime history: original FD, current default and geometry opt-in

Updated 2026-09-17 from the sealed results. This page consolidates recorded
campaigns. Each full-inverse time
includes worker startup, original-start topology, candidate fits, any
continuation, and final checks. Truth-data preparation and video rendering are
excluded. The speedup comparisons used sequential workers with one BLAS thread.

## What each change actually saved

| Change | Matched full-inverse before → after | Measured effect | Evidence |
|---|---|---|---|
| Analytic operator Jacobian + fast CPU kernels | Death 434.65 → 233.73 s; split 418.01 → 221.53 s | 1.86x / 1.89x faster than original FD/reference CPU | [SPD-002](iteration_03/01_results.md), one worker per arm/scene |
| Training-only readiness before mandatory continuation | Death 236.26 → 46.12 s; split 222.32 → 33.10 s; merge 406.34 → 403.52 s | Additional 5.12x / 6.72x for death/split; merge effectively unchanged | [SPD-004](iteration_04/01_results.md), two workers per arm for death/split, one for merge |
| Reciprocal derivatives, measured without readiness in either arm | Death 234.83 → 133.03 s; split 223.03 → 123.52 s; merge 409.85 → 172.00 s | Additional 1.77x / 1.81x / 2.38x over operator derivatives | [SPD-005](iteration_05/01_results.md), two workers per arm/scene |
| Readiness combined with reciprocal derivatives | Death 133.03 → 46.02 s; split 123.52 → 33.57 s; merge 172.00 → 175.92 s | Skip unnecessary fitting on death/split; about 2.3% screening overhead on merge in this campaign | [SPD-005](iteration_05/01_results.md), same matched campaign |
| Compiled scattering added to reciprocal + readiness | Central ellipse/star 1098.37 → 1049.41 s; two stars 1367.98 → 1291.66 s | Additional 4.46% / 5.58% less time; death/merge unchanged | [SPD-006](iteration_06/01_results.md), two workers per arm/scene |
| Promote the combined setup to the default | Fresh death 46.27 s; merge 173.32 s | Dispatch/quality confirmation; no additional algorithmic speedup | [SPD-007](iteration_07/01_results.md), one fresh default worker per scene |
| Exact geometry report/audit reuse and boolean pair certification, opt-in | Death 46.32 → 30.56 s; merge 176.18 → 136.65 s; central ellipse/star 1069.98 → 529.95 s; two stars 1314.84 → 597.65 s | Additional 34.0% / 22.4% / 50.5% / 54.5% less time with exactly matched trajectories, endpoints and work | [SPD-008](iteration_08/01_results.md), two workers per arm/scene |

All timed workers in these speedup campaigns passed their original recovery
checks. Repeated rows use medians. Small variations between campaigns are not
new speedups: for example, merge's 175.92 s in SPD-005 and 171.85 s in SPD-006
do not establish a compiled benefit; SPD-006's paired reciprocal control was
171.72 s.

Readiness and reciprocal derivatives overlap. On death/split, readiness skips
the continuation that would benefit from reciprocal derivatives, while coarse
topology retains operator derivatives. Their separately measured gains must
not be multiplied. The combined runtime was measured directly.

## Complete-runtime configurations at a glance

Times below come from the campaign identified in the first column. This is a
history of measurements, not one simultaneous benchmark across every row.
A dash means that full configuration/scene was not measured in these campaigns.

| Configuration / measurement | Death | Split | Merge | Central ellipse/star | Two stars |
|---|---:|---:|---:|---:|---:|
| Original FD/reference CPU, SPD-002 control | 7m15s | 6m58s | — | — | — |
| Analytic operator + fast CPU, SPD-005 control | 3m55s | 3m43s | 6m50s | — | — |
| Operator + readiness, SPD-004 | 46s | 33s | 6m44s | — | — |
| Reciprocal, without readiness, SPD-005 | 2m13s | 2m04s | 2m52s | — | — |
| Reciprocal + readiness, SPD-005 | 46s | 34s | 2m56s | — | — |
| Reciprocal + readiness, SPD-006 control | 46s | — | 2m52s | 18m18s | 22m48s |
| Compiled + reciprocal + readiness, SPD-006 | 46s | — | 2m52s | **17m29s** | **21m32s** |
| Same setup via default CLI, SPD-007 | 46s | — | 2m53s | — | — |
| Same compiled setup, SPD-008 matched control | 46s | — | 2m56s | 17m50s | 21m55s |
| Compiled + readiness + exact geometry acceleration, SPD-008 opt-in | 31s | — | 2m17s | **8m50s** | **9m58s** |

The latest directly measured split time is 33.57 s under reciprocal + readiness.
It was not rerun in SPD-006/007/008. Its measured ready route skips continuation,
so compiled continuation has no work to accelerate on that route.

For the four SPD-006 scenes, the sum of per-scene medians fell from **44m44s
to 42m39s**, saving 2m05s. That is one sequential reconstruction per scene,
not the duration of the 16-worker repeated validation campaign.

For SPD-008's matched four-scene comparison, that sum falls from **43m27s to
21m35s**. Both arms use compiled + reciprocal + readiness; the only intervention
is geometry-validation execution. The implementation remains opt-in, so these
are not the current default's timings. The SPD-006 and SPD-008 control samples
belong to different campaigns and must not be used to manufacture another gain.

SPD-008's wall times are **shared-host observations**: a final workspace audit
found separate LAU-001 artifacts whose timestamps and 31.30 s recorded duration
indicate overlap with the last worker. Its pilot/test absolute timings are
unavailable. The measured sources, trajectories, endpoints and work still match
exactly; an isolated timing benchmark is not claimed. See the
[preserved timing context](../../../results/validation/speedup/SPD-008-20260917-geometry/timing_context.json).

## Original all-scene record: useful context, different timing conditions

Before the speedups, [TOP-025](../topology/iteration_18/01_results.md) ran all
twelve scenes with FD/reference CPU and up to **four concurrent workers**.
The total was **90.35 minutes**, with **7/12 recoveries**, including failed and
stopped cases. Its individual elapsed times are from the original
[campaign record](../../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/campaign.json):

| Original scene | Original full-worker elapsed | Recovery |
|---|---:|---|
| Repeated birth | 20m22s | Pass |
| Death | 7m44s | Pass |
| Split | 7m23s | Pass |
| Merge | 17m53s | Pass |
| Mixed | 24m34s | Pass |
| Far two circles | 13m39s | Pass |
| Central ellipse/star | 45m56s | Pass |
| Far two stars | 65m03s | Failed recovery |
| Far ellipse/star | 4m40s | Stopped: finer-grid handoff infeasible |
| Empty ellipse/star | 1m24s | Stopped: finer-grid handoff infeasible |
| Enclosing ellipse/star | 10m01s | Stopped: topology wall limit |
| Far three shapes | 10m01s | Stopped: topology wall limit |

These original concurrent timings are historical context, not matched controls
for the newer sequential timings. Two stars also changes from failed recovery
to successful recovery, so a ratio would not compare equal outcomes. The old
FD quotas curtailed its optimization progress; both reciprocal and compiled
SPD-006 arms recover, so compilation did not create that recovery improvement.

The later [completed compiled-default TOP-025 campaign](../../../results/validation/topology/TOP-025-compiled-20260917-115641/campaign.json)
measures **30m16s elapsed, with 8/12 recoveries**, up to four concurrent workers
and one BLAS thread per worker. Its [scorecard](../../../results/validation/topology/TOP-025-compiled-20260917-115641/scorecard.json)
and failures are preserved: far/empty ellipse-star fail finer-grid handoff,
enclosing ellipse-star reaches the event limit, and far three shapes reaches
the topology wall limit. Verification passes. It finished before SPD-008
implementation began; all 618 recorded artifact hashes still verify.

The original and compiled all-scene records have different successful subsets
and are historical campaigns, not a new matched all-scene speedup comparison.
**No all-twelve-scene runtime with SPD-008 geometry acceleration has been
measured.** Its four-scene reductions cannot be extrapolated into such a time.
The [all-scene command](../../../experiments/spd007_default_promotion/README.md#run-all-twelve-scenes-with-the-promoted-default)
continues to select the promoted default.

## Changes without a separate full-inverse timing claim

- **Analytic differentiation alone versus CPU kernels alone:** SPD-002 measured
  their combination in full inverses. [SPD-001](iteration_02/01_results.md)
  separates them only for a single four-frequency optimizer update:
  FD/reference 261.20 s, analytic/reference 208.73 s, FD/fast kernels 151.73 s,
  and analytic/fast kernels 100.42 s. The 2.60x figure describes that update,
  which also used a different constraint policy, not a complete reconstruction.
- **CUDA linear algebra:** the SPD-001 analytic/fast update fell from 100.42 s
  to 98.20 s (2.2% less time), with only one measured update per arm. No matched
  full-inverse CUDA timing was established; the current default is CPU.
- **SPD-003 continuation reuse, true-analytic constraint
  policy and other pipeline proposals:** no full-inverse speedup has been
  established. SPD-006's 88.5% geometry-check share is one profiled update,
  not the fraction of a whole inverse that can automatically be removed.

The deployed combination is recorded in [SPD-007](iteration_07/01_results.md).
The qualified geometry opt-in is recorded in [SPD-008](iteration_08/01_results.md).
Its default promotion and the separate true-analytic policy comparison remain
future decisions; no successor campaign is scheduled.

## Why the current CUDA switch has little work to accelerate

This is a limitation of the current implementation and workload, not evidence
that a redesigned GPU pipeline could never help.

1. **Geometry dominates the measured default update.** Even with an analytic Jacobian,
   the default `fd_compatible` policy in
   [the optimizer](../../../solvers/sdf_inverse/radial_topology.py) calls
   `allowed(+step)` and `allowed(-step)` for every gauge direction. Each call
   retracts the perturbed geometry and validates the production and refined
   boundaries. The NumPy self-intersection and component-clearance calculations
   do not use the CUDA execution context. In the SPD-006 central-case update,
   136 stencil checks took **23.864 s of 26.957 s (88.5%)**.
2. **CUDA currently offloads a limited set of operations.**
   [Execution](../../../solvers/gpr_bem_kress/execution.py) dispatches dense LU
   factorization and RHS solves to Torch/CUDA; the older operator derivative
   also offloads some tangent matrix products. Matrix construction and special
   functions remain NumPy/SciPy CPU work. Reciprocal products and compiled
   trace reconstruction remain NumPy operations. The compiled backend does
   call the CUDA-aware `Factorization`, so it supports this limited offload.
3. **The implementation transfers and synchronizes repeatedly.** `to_cuda`
   copies host arrays to device and immediately calls `torch.cuda.synchronize()`;
   LU factorization and RHS solves also synchronize. `Factorization.solve`
   returns `.cpu().numpy()`. Factors can be retained, but the full calculation
   does not remain on the GPU. Transfer and synchronization overhead is charged
   before any net speedup can be obtained.
4. **Compilation has already reduced the linear algebra substantially.** At
   angular order 24, two objects give a 98-by-98 coupled system, alongside the
   larger local Kress solves. The matched compiled profile spent only **0.759 s
   (2.8%)** in all instrumented dense factorization/solve operations combined:
   0.712 s in full validation solves, 0.036 s in factorizations, and 0.011 s in
   RHS solves. Making these operations free would improve this one profiled
   update by only **about 1.03x**, even before accounting for transfers.

The operation timings come from the
[recorded profile summary](../../../results/validation/speedup/SPD-006-20260916-full-inverse/remaining_cost_profile/summary.json).
They include profiler overhead and describe one update, not an entire inverse
or a new CUDA benchmark. The older actual CUDA experiment improved one analytic
fast-CPU update from 100.42 s to 98.20 s; the current compiled full inverse has
not received a matched CUDA timing campaign.

SPD-008 subsequently qualified exact geometry reuse on CPU. Its separate
accelerated central update takes 8.95 s, with 6.43 s in stencil checks including
5.06 s in sampled self-intersections; these nested timings are not additive.
The full hard-scene gains were measured separately as 2.02x and 2.20x. The
true-analytic constraint policy remains a separate unexecuted study. If GPU work is
pursued, it should target the measured geometry/assembly bottlenecks, retain
arrays on device, and batch enough independent work to offset transfers.
Simply selecting `device="cuda"` does not make those architectural changes.
