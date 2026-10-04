# PC-002 — geometry reuse, accuracy-selected nodal resolution and fair timing

Pre-registered 2026-10-04 in cleaned-interface iteration 28.

**Pre-execution amendment, 2026-10-04:** the user's review adds the nodal
512-node floor as the main remaining fairness issue, alongside component
device receipts, common GPU certificates and separate promotion reporting.
The earlier geometry-only draft has not been executed. This amendment replaces
its fixed-floor primary baseline; PC-002 is approved with the narrowed execution below.

- **Approval status:** APPROVED. User: "yes but try speed up validation a bit, im waiting for the fair nodal spline to run on the 10 scenes."
- **Execution status:** implementation and focused validation; fitting pending.
- **Owner:** Codex. **Independent reviewer:** unassigned.
- **Checkout:** existing `feature/shape-frequency-continuation`, planning head
  `b583f29992489e7b14aea3f60c086ec0bc0bc738`. No branch or worktree creation.
- **Starting evidence:** [iteration opening](01_results.md),
  [PC-001](../../../../results/validation/cleaned_interfaces/PC-001/README.md),
  [package contract](../../../../solvers/bem_inverse/README.md), and
  [TG-002](../../../../experiments/benchmark/README.md).

## Approved priority amendment — 2026-10-04, before execution

The latest instruction narrows this execution to **NS**, nodal Kress + spline,
on all ten TG-002 scenes at contrasts 0.5/4/13.3 (30 cases). One centred
start, no localization/grid/restarts, default continuation/LM and unchanged
recovery gates. No other inverse arms or repeated timing panel run now.
The broader comparisons below are deferred, not authorized by this execution.

Focused validation replaces the four-hour blanket qualification: test exact
cache invalidation/concurrency/bounds, compare cached and uncached CUDA real
and damped fields and full-trial Jacobians at identical resolution, exercise
resolution escalation/refusal and run the affected runner/package checks.
Retain the production/refined checks throughout fitting and full endpoint
field/Jacobian/finite-trial audits. Each endpoint audit compares both its native profile and independent
N1024 against N2048 on CUDA, including field/Jacobian gates and full-trial
finite differences. It records all three node counts.
No CPU-reference timing comparison or modal speedup conclusion is drawn.

NS uses explicit CUDA, four frequency threads, one fit at a time on the idle
GPU. Cold process/kernel/table startup is charged and reported; no excluded
warm-up. Cache boundary jets/adapters and CUDA pair geometry/Kress weights;
source/receiver wave evaluation stays on its existing CPU path in this first
implementation (acquisition geometry hoisting is deferred). Retain at most
four geometry entries and 256 MiB of device tensors; record builds, hits,
wall time, retained/peak bytes and evictions. Exact coefficient bytes,
resolution and device are the keys. Forward handles already retain identical
boundary geometry for the Jacobian. Release retained cache at fit exit.

Stage-entry selection starts at the even ceiling of max(2*K_trace+1,
2*K_geometry+1,8), with modal's existing K_trace rule. Try the next +64 nodes
(up to 1024, then 2048), accept only when all active fields meet existing
stage tolerances and every normalized Jacobian column agrees within 1e-3.
Freeze that pair during the stage; unchanged trial cross-resolution gates
still refuse under-resolved candidates. Charge all selection solves and
reciprocal batches to the stage/global ledger and wall cap. Audit endpoints
against fixed N1024/N2048, also checking native-profile fields and Jacobians. There is no N1-style
trial promotion. Report selected node counts and any escalation separately.

Stop and retain evidence if focused equivalence validation fails. Otherwise
commit the implementation before fitting, record that source commit and input
seal in the campaign manifest, run all 30 NS cases, summarize failures as well
as recoveries, validate the result bundle, and commit/push it automatically.
The older broad design below provides rationale; this priority amendment
controls what actually runs.

## Question and hypothesis

After nodal Kress receives geometry reuse and permission to use a smaller,
numerically qualified resolution, does modal physics still reduce complete
inverse time at comparable recovery quality? Separate the effects of geometry
reuse, the 512-node floor, device allocation and the geometry update.

The execution-only hypothesis is that immutable nodal geometry can be prepared
once per candidate curve/resolution/device, reused across real and damped
frequencies, and released without changing fields, derivatives, trial
decisions, or recovery at the same resolution. A fresh uncached nodal control
tests this directly. Lower resolution is a separate numerical intervention:
it need not reproduce every fixed-512 trial decision, but must pass the same
accuracy/acceptance gates and independent audits. Do not conflate resolution
effects with cache-equivalence tests. No minimum modal speedup is assumed.

## Intervention 1: reuse frequency-independent geometry

Separate nodal geometric preparation from frequency-dependent assembly:

| Prepare once for an unchanged curve and resolution | Recompute for each frequency |
|---|---|
| Boundary samples/jets, validated adapter, speeds, normals, curvature and weights | Wavenumbers, material-dependent factors and kernel values |
| Pair separations/distances, normal projections and normal dot products | Near/direct kernel masks, which depend on wavenumber |
| Periodic offsets and geometry-only Kress/logarithmic weight grids | Frequency-dependent diagonal limits and assembled matrices |
| Fixed-source/receiver distances and geometric normal projections | Incident/receiver waves, RHS, LU factors and solved traces |

Reuse the acquisition geometry for reciprocal illumination too. Never cache a
kernel mask as though it were frequency independent. Each coarse/refined
resolution has its own entry; matrices and LU factors remain frequency
specific. The existing per-frequency forward/reciprocal factor reuse remains.

The spline update, reparameterization, tangent definition, metric, filtering,
feasibility, and policy remain fixed. Its preparation is shared across the
frequency batch already; inspect counters and hoist any equivalent repeated
normal-basis evaluation only if it is part of this same geometric reuse.

Use an explicit opt-in `Execution.nodal_geometry_reuse` selector (`off` or
`per_curve`), default `off` during qualification. The nodal backend owns a
fit-local, thread-safe cache; do not use process-global mutable state or round
coefficients. Keys include exact geometry bytes, resolution, precision,
device, and any relevant fixed acquisition/configuration values. Publish one
immutable preparation per concurrent key. Rejected/changed curves, changed
acquisitions, resolution changes and CPU fallback must not reuse stale data.

Bound retained host and device geometry to 256 MiB each per fit; retain at most
four entries in either cache. An oversized entry bypasses retention. Record
in-flight preparation/storage separately from retained cache storage and
release all entries at fit exit. Memory pressure uses the existing declared
fallback or bypasses reuse; it never changes numerical accuracy.

## Intervention 2: remove the fixed floor only behind accuracy gates

The current `Execution` requires an even resolution >=512. Nodal's profile is
`max(512, 2*(K_geometry+1))`, doubled for refinement. Modal starts at
`K_trace=64`, with 129 unknowns per trace (258 total), versus 512 per trace
(1,024 total) for early nodal stages. The cubic dimension estimate is about
61x for LU arithmetic, not an observed LU or inverse-time ratio: actual
devices, kernel/geometry costs, solves and audits must be measured.

Add opt-in `Execution.nodal_resolution_profile='fixed'|'band_matched'`; retain
`fixed`, resolution 512, as the public default. Permit even node counts >=8
only through the experimental profile. Kress requires **even** N, and the
curve sampler/`FitStage` requires N > 2*K_geometry. Thus do not use 129 nodes
literally or lower N by discarding stored shape coefficients.

For each stage, take K_trace from the unchanged modal profile at that stage's
storage band. Set

`n0 = even_ceil(max(8, 2*K_trace+1, 2*K_geometry+1))`.

This gives N130 in an early stage with K_trace64, but at least N386 when
K_geometry192; nodal sampling must still resolve the stored curve. The
production ladder is `n0, n0+64, n0+128, ...`, stopping at 1,024 nodes;
include N1,024 as the final ladder entry if the regular spacing misses it.
The next larger entry is the refinement partner. N1,024 has N2,048 as its
partner. This is a node-count starting rule, not equivalence of discretizations.

At stage entry, select the first pair whose fields and complete-update
Jacobian at the current curve agree across all active frequencies: unchanged
per-frequency field tolerances (1e-5 at <=0.5 GHz, 1e-7 otherwise) and the
existing 1e-3 Jacobian-column gate. Charge every attempted pair, including
discarded lower profiles, to the fitting ledger and wall budget. Retain the
chosen pair for that stage. A pair that fails is not a fitted result; if no
pair qualifies, record a numerical-resolution stop. No truth, residual target
or timing result selects N.

During fitting, keep the existing next-finer field/decrease acceptance check
for every proposed accepted curve. No nodal-only mid-stage resolution response
is enabled; an unresolved trial follows the same hard-stop policy as modal.
Qualify derivatives at the selected profile and audit every returned endpoint.
Rebuild the objective and refined caches when changing a pair; include the
resolved pair in checkpoint/resume identity. Report stage-entry selection as
selection overhead, separately from RB-001-style promotion.

Qualification must check selected adjacent pairs against a separately rebuilt
high-resolution reference, since adjacent agreement can be falsely reassuring.
Use uncached CPU N1,024/N2,048, and preserve unresolved reference rows. A
selected pair must meet the same field/J gates against a qualified reference;
if the reference itself is unresolved, that row cannot pass qualification.
The main comparison does not proceed with an unresolved accuracy claim.

## Component devices and common geometry path

Code inspection at the planning head gives the following **hybrid** execution:

| Component | Nodal with SPD-016/CUDA | Modal with CUDA |
|---|---|---|
| Matrix assembly | GPU | GPU |
| LU factorization | GPU: `DeviceFactors`, `torch.linalg.lu_factor_ex` | CPU: SciPy `lu_factor` |
| Forward/reciprocal linear solves | GPU; host-retained factors uploaded for later solves | CPU: SciPy `lu_solve` |
| Incident/readout and field contraction | CPU | CPU |
| Final Jacobian contraction | CPU | CPU |
| Certified spectral preparation/certificate | Shared GPU update class, absent fallback | Shared GPU update class, absent fallback |

The SciPy import in `physics.py` is not evidence of CPU LU on the CUDA nodal
path. Conversely, modal's `device='cuda'` does not mean GPU LU. Verify actual
calls and transfers with component receipts, not the backend name alone.

Keep the primary optimized native implementations on the same host/GPU.
Add a bounded nodal control with GPU assembly and **CPU LU/solves**, so those
components match modal. An opt-in nodal `factor_device='native'|'cpu'` selector
may route the already assembled matrix to the existing SciPy solve path; no
modal GPU-LU port is bundled here. Verify matrix/field/J equivalence before
timing this control. Native timings support a comparison of the available
hybrid implementations; only the component-matched control supports an
attribution without CPU/GPU LU as a confound. Do not deliberately choose the
slower nodal device route as the headline denominator.

NC and MC must instantiate the same `DeviceCertifiedUpdate` through the
shared selector, with identical configuration and CUDA preparation/certificate
receipts. The read-only [opening assessment](01_results.md) already verifies
all 60 PC-001 N1/M1 geometry receipts: matched CUDA settings and zero recorded
preparation/certificate fallbacks. Repeat this check on PC-002's actual runs;
class selection alone does not prove none occurred.

## Code and API boundary

| Location | Permitted change |
|---|---|
| `solvers/bem_inverse/physics.py` and a small private geometry-preparation module | Opt-in reuse/resolution/factor-device selectors, ownership, lifecycle and component counters |
| `solvers/bem_inverse/continuation/forward.py`, `damped_cuda.py` | Pass prepared geometry into real/damped forward and reciprocal work; retain reference calls |
| `solvers/gpr_bem_kress/` | Internal prepared-geometry assembly/incident/receiver helpers; preserve public builders and their uncached defaults |
| `solvers/bem_inverse/geometry.py` | Only demonstrated equivalent basis reuse, if needed; no new finite update |
| `solvers/bem_inverse/runner.py`, `continuation/lm_backend.py` | Charged stage-entry profile selection, resolved-profile receipts and checkpoint/cache identity; unchanged nonlinear acceptance rules |
| `experiments/benchmark/pc002.py` and focused tests | Frozen arms, qualification, sequential timing, scoring and reports |
| Package and benchmark guides | Document selector and provenance |

Campaigns, input paths and truth scoring remain outside `bem_inverse`. Keep
old compatibility imports working. No reference-solver replacement, nodal
approximation, kernel interpolation change, optimizer change, new registry,
or modal refinement response is bundled into PC-002. Preserve TG-002 and
PC-001 seals, source archives, failed runs and interrupted folders.

## Matched arms

All four comparison arms use the same data, centred start, cumulative policy,
localization `none`, accuracy gates, and **hard stop on unresolved trials**.
This makes backend and geometry-update effects separately identifiable.

| Arm | Physics | Geometry update | Resolution / reuse / LU |
|---|---|---|---|
| NS | `nodal_kress` | `spline` | Accuracy-selected band profile / reuse / native GPU LU |
| NC | `nodal_kress` | `certified_spectral` | Accuracy-selected band profile / reuse / native GPU LU |
| MS | `modal_muller` | `spline` | Unchanged modal profile / existing reuse / CPU LU |
| MC | `modal_muller` | `certified_spectral` | Unchanged modal profile / existing reuse / CPU LU |
| NS0 — cache control | `nodal_kress` | `spline` | Same band profile / reuse off / native GPU LU |
| NS512 — floor control | `nodal_kress` | `spline` | Fixed 512/1024 profile / reuse / native GPU LU |
| NSCPU — device control | `nodal_kress` | `spline` | Same band profile / reuse / CPU LU and solves |

NS is the fair nodal/spline baseline. MS/NS isolates backend cost with spline;
MC/NC isolates it with certified spectral geometry. NC/NS and MC/MS measure
the geometry-update effect within each backend. MC/NS is a complete-pipeline
comparison, not an isolated modal-solver speedup.

NC is deliberately **not** the named `nodal_fixed` recipe, which includes
resolution promotion. Construct these slots through the existing `fit` API;
do not redefine recipes to make their responses appear equal. PC-001 N1's
four promoted failures stay separate from PC-002's speed attribution. Report
their cost separately from PC-001's 26 non-promoted recovered cases. Stage-base
selection in NS/NC is not the historical mid-stage response.

## Shared experiment contract

- Only the sealed 30 TG-002 cases: ten scenes at contrasts 0.5/4/13.3. One
  65 mm circle at the prescribed centre. No localization grid, seed search,
  restart, truth-selected state or new scene/data generation.
- Unchanged real and synthetic damped catalogs, contrast, acquisition,
  normalization, default `CumulativePolicy`, stages, bands and tolerances.
- Nodal profile changes only by the predeclared accuracy-selection rule above;
  modal trace/workspace profiles stay fixed. Match verified accuracy rather than
  forcing equal dimensions. Record N, K_trace, K_geometry, both system dimensions
  and refinement counts per stage/frequency. No cutoff tuning after outcomes.
- Primary execution: explicit CUDA, SPD-016 for nodal, four frequency workers,
  one case worker, one BLAS/OpenMP thread, float64/complex128, same host/GPU.
  Preserve automatic memory fallback behavior in separate qualification checks;
  a fallback in a primary timed fit is retained and flagged, not silently
  included in a CUDA speed claim. Record LU/solve/field/J devices and transfer
  costs separately; primary implementations are hybrid, not device-identical.
- Per-case caps remain 13,412 fitting units, 1,800 fitting seconds and 300 s
  per audit. Recovery: passing final audit, RMS <=1 mm, Hausdorff upper <=2 mm,
  every frequency residual <=0.003. Report every failure and cap separately.
- Truth is read only after fitting for scoring. PC-001 and this suite are
  development evidence, not a new generalization holdout.

## Stages and release gates

### A. Qualify reuse, resolution and component routing before fitting

Use the TG-002 start plus first/last saved accepted M1 states for `circle`,
`kite`, `c_shape`, and `aphex_twin` at contrasts 0.5 and 13.3 (up to 17
distinct curves). Extract by chronological rule, not truth error; retain a
manifest of exact checkpoint files and hashes. Missing or unqualified saved
states are disclosed, not replaced by more favorable ones.

First compare cached/uncached nodal assembly, fields and complete-trial Jacobians
at fixed N512/N1024 across the real and damped catalogs. Check selected directions
against independently rebuilt finite differences. Include CPU reference,
single/four-worker execution, concurrent same-key preparation, acquisition
changes, a one-bit coefficient change, eviction, oversize bypass, OOM/fallback,
and cache cleanup. Existing GPU availability rules apply to regression tests.

Gates: relative matrix difference <=1e-13; prediction difference normalized
by observed data <=1e-12; Jacobian relative difference <=1e-10; existing
refinement and directional gates pass. Recorded sampled trial acceptance and
validity outcomes must match exactly. Record byte identity where achieved;
these tolerances do not assert bit identity. Demonstrate one preparation per
unchanged key across frequencies and bounded cache lifetime/memory.

Then qualify smaller profile pairs and their independent references under
the resolution rule above, including even-node and storage-band checks.
Verify GPU-native versus CPU LU/solve routing and equivalent fields/J, and
confirm common GPU certificate configuration. Preserve all failed pairs.

Benchmark cold geometry plus a 19-frequency forward/Jacobian batch with
three order-balanced repetitions, all preparation/selection/transfers charged.
Keep fixed-floor reuse/off, selected-profile/fixed-floor, and CPU/GPU LU
comparisons separate. Release B only if the numerical, resolution and routing
gates pass with effective reuse. Do not require caching alone to save 5% before
testing the main resolution-floor hypothesis. Require at least one early-stage
fixture to qualify below N512; harder fixtures may select higher pairs by the
frozen rule. If none qualifies below the old floor, stop with that evidence;
do not silently substitute fixed512 for NS/NC.

### B. Fresh TG-002 coverage and paired execution control

Run NS/NC/MS/MC on all 30 cases once (120 fits), sequentially on the same host.
For case index i in the benchmark inventory, rotate `[NS, NC, MS, MC]` by
`i mod 4`. Record the resolved order before launch. No PC-001 timings or
completed results substitute for a PC-002 fit.

The fixed timing/control panel is:

`circle__c0.5`, `kite__c4`, `peanut__c13.3`, `c_shape__c13.3`,
`cog__c4`, `aphex_twin__c13.3`.

Run NS0, NS512 and NSCPU once on these six cases. Compare NS0 to NS's first pass
using the same selected-profile rule. For paths not
limited by wall time, require identical accepted/rejected trial decisions,
stage progression and work counts, with final boundary difference <=1e-6 mm
under a common dense evaluation. Audit/recovery classifications must agree.
Wall-cap-dependent path differences are reported as resource effects and do
not pass trajectory-equivalence qualification. Investigate any other mismatch
before releasing C; do not increase tolerances or substitute panel cases.

NS512 and NSCPU are separate method/device controls, not cache-equivalence
tests. They need not take identical nonlinear trajectories, but must pass the
same independent accuracy and recovery checks. Score/report profile-selection
stops separately from candidate failures and wall/work caps.

For each returned endpoint, add the same uncached CPU N1,024/N2,048 field and
complete-trial-J audit on all real frequencies, after fitting and without truth
feedback. This reference audit is independent of the fitted profile and uses
the unchanged field/J/FD gates. Retain its <=300 s cap and any unresolved result.
Record its time separately and report totals both with and without this common
reference audit; do not charge it selectively or treat it as free computation.
Primary success requires both native and common reference audit qualification.

### C. Repeated timing on the frozen panel

If B's execution-control gate passes, add repetitions 2 and 3 for all seven
arms on the same six cases (84 fits). First-pass panel runs count as repetition
1. In B, insert the three controls next to NS in panel-index rotation order;
the four primary arms retain their prescribed order. In repetitions 2/3 rotate
`[NS0, NS512, NSCPU, NS, NC, MS, MC]` by panel index; reverse it in repetition 2. Save the
whole schedule before fitting. Each fit uses a fresh process/cache.

Warm device/library setup equally outside the primary fit timer; also record
startup-inclusive process time. Include curve-dependent preparation, all
frequency work, spline/spectral preparation, rejected trials, fitting and
initial/final audits in the primary wall metric. Synchronize CUDA at timing
boundaries. Retain setup timings, peak RSS/device memory and host/GPU load;
do not time multiple cases or other numerical jobs concurrently. If load is
present, wait before launching a block; contaminated samples stay labeled.

## Metrics, readings and decisions

Report per case and contrast: recovery, geometry errors, residuals, audits,
stop category, accepted/rejected steps, solves, derivative calls, units,
cache builds/hits/evictions/bypasses, retained/in-flight memory and wall time.
Include chosen/attempted resolutions, total complex system dimension, selection
overhead, actual component devices, transfers, GPU certificate fallback counts,
and native versus common reference audits. Record promoted counts separately;
the four main arms have no mid-stage promotion.
Profile geometry preparation, kernel/matrix assembly, LU, field/reciprocal
solves, geometry updates and audits. Concurrent component timers are not
additive wall time; make that distinction explicit in the report.

1. **Reuse qualification:** NS/NS0 preserves the panel trajectories under the
   rule above. Any changed non-resource decision blocks adoption.
2. **Reuse value:** three-repeat per-case median NS/NS0 time ratio has a
   geometric mean <=0.95, without a >10% case regression, to recommend reuse
   for the measured workload. Report memory cost even when timing improves.
3. **Resolution-floor effect:** NS/NS512 separates accuracy-selected resolution
   from the fixed512 floor with reuse in both. Report changed decisions, cost,
   recovery and selection overhead. Do not turn dimension-cubed estimates into
   observed speedups or claim every stage uses ~130 nodes.
4. **Device effect:** NS/NSCPU measures native GPU versus CPU LU/solves, with
   all transfers charged. MS/NSCPU is the component-matched spline comparison;
   MS/NS is the available-implementation comparison. Publish both scopes.
5. **Backend advantage:** report MS/NS and MC/NC separately. A panel speed
   advantage requires geometric-mean paired median ratio <=0.95 and no lost
   recovered case across the 30-case first pass. Otherwise limit the claim to
   individual matched cases, or report no established general advantage.
6. **Geometry contribution:** report NC/NS and MC/MS without presuming spectral
   geometry is cheaper. Separate changed trajectories from per-step cost.
7. **Complete method:** report MC/NS as pipeline cost/recovery, explicitly
   including both backend and geometry changes.

For quality-matched speed ratios use only cases both compared arms recover in
all three repetitions; disclose every exclusion and require at least three
such panel cases for an aggregate. Also report all-case capped cost, recovery
rates and failure categories so a fast early failure cannot create a success
speedup. Any repeat-dependent recovery or non-resource decision variation
blocks an aggregate claim pending explanation. Report min/max ranges and
per-case median ratios; six selected cases do not establish a repeated all-30
speedup. Full-suite first-pass timings remain descriptive.

Do not multiply historical speedups or use PC-001's interrupted N0 median as
the denominator. Adoption needs the stated numerical and economic gates;
keep the selector opt-in until a user decision on the completed evidence.
Correct negative and inconclusive results are valid closeouts.

## Budget, artifacts and closeout

- A: <=4 h numerical wall, <=12,000 forward frequency solves and <=12,000
  derivative calls, including failed attempts and reference checks.
- B/C: <=24 h sequential numerical wall, <=222 full fits total (120 matched
  coverage + 18 control fits + 84 additional panel repetitions), each with the
  unchanged case caps. The theoretical all-caps maximum exceeds this campaign
  cap; completion is not guaranteed. Stop and report incomplete coverage if
  the campaign cap binds. No retries to erase caps, failures or interruption.
- Check remaining campaign budget before dispatch. A fresh runtime repetition
  has its own directory; an incomplete directory is never reused as a fresh
  timed fit. Infrastructure repairs retain the failed attempt and consume the
  same budget. A change of scientific mechanism requires a new proposal.
- Output: `results/validation/cleaned_interfaces/PC-002/`, with pre-run input/
  source hashes and source archive, resolved arms/policy/order, qualification
  receipts, per-arm/per-repeat runs, timings/memory/load, validation logs,
  machine-readable metrics and a rebuildable side-by-side report/curve gallery.
- Before implementation, freeze the driver schedule and source/input contract;
  seal the implemented sources before numerical execution. Approved staged
  repairs use distinct source snapshots and identify which receipts precede
  them. Never rewrite PC-001 or TG-002 manifests.
- Validation after implementation: the package/cleaned-interface suite,
  benchmark tests, and relevant Kress/ordered-boundary/shared-continuation
  regressions from the package guide; focused independent cache and derivative
  checks above. No numerical tests were run to write this plan.
- After each new experiment run, preserve code, documentation and all results
  (including failures), validate, commit/push to the current configured remote,
  and verify remote HEAD and final working-tree status under AGENTS.md.
- Results open iteration 29. Update the cleaned-interface handoff with actual
  gates passed, unfinished work and claim scope. PC-001 remains a stopped
  historical campaign; PC-002 neither resumes nor silently completes it.
