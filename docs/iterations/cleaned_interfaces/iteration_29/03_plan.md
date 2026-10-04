# GC-001 — spline versus spectral geometry: cost, precision and attribution

Pre-registered 2026-10-04. Cleaned-interface iteration 29.

**Approval:** APPROVED, user: "run", 2026-10-05, in response to the GC-001
registration and its pending ID approval. **Execution:** implementation and
focused validation, before dispatch. No branch or worktree will be created.
Use the existing `feature/shape-frequency-continuation` checkout that contains
PC-002; do not switch branches or modify the numerical implementation for this
measurement. Results will open iteration 30; this plan will be preserved.

## Question and output

Compare today's spline and spectral geometry on identical TG-002 curves and
identical physical normal moves. Identify which differences arise from inverse
arclength interpolation, position interpolation, quadrature resolution, retained
band, finite-difference cancellation, batching, device arithmetic, transfer,
discarded diagnostics, or validity checks. No physics, data loss, inverse fitting,
new scene generation or recovery claim is part of this experiment.

Deliver a table here and a retained report containing:

1. Paired preparation and trial times, with startup, projection, derivative,
   validity, certificate and fallback work separated.
2. Curve differences in metres and normalized units, derivative-column
   differences, cross-resolution convergence and validity decisions.
3. A ranked explanation of measured runtime and precision differences, with
   evidence from controlled ablations and explicit unresolved interactions.

**User scope clarification, 2026-10-04:** keep this quick and interpret the
results relative to complete inverse runtime. Reuse saved TG-002/PC-002 curves;
do not launch fresh fits. Target minutes rather than a campaign-length run;
implementation/validation and the six deeper interpolation diagnostics are
reported separately from headline measurement time. The timing panel stays
bounded at 11 states and three repeats; do not broaden or repeat it without
new failures or unresolved concerns. Actual runtime will be recorded, not
promised from historical performance.

## Bigger-picture interpretation

Use the [existing-receipt aggregation](01_results.md#whole-inverse-context-from-existing-receipts)
to anchor significance. Recorded geometry updates take 19.10% of summed M1
total runtime and 19.45% of summed NS total runtime. Their median case shares
are 15.54% and 15.61%. N1 has a median case share of 3.08%, but its long failed
cases raise the weighted share to 15.21%. Distinguish representative-case and
total-campaign summaries, including the four failures separately.

For each claimed component speedup, state its fraction of the corresponding
complete runtime and the conditional Amdahl saving: with affected fraction f
and speedup s, complete speedup is `1 / ((1-f) + f/s)` at unchanged work.
Do not multiply geometry and physics speedups or present a projection-only
speedup as an inverse speedup. At a 19% geometry share, a 2x geometry speedup
saves about 9.5% of complete time; even removing the entire category is only
about 1.24x. Optimizing only preparation or only certificates has a smaller
ceiling. Keep initial/final audit time in the whole-run denominator; exact
fitting-only geometry fractions are unavailable from the saved combined counters.
Separate boundary-update geometry from BEM geometry assembly inside physics.

Also evaluate precision as a possible change in physical work: report whether
native-map resolution gates or validity decisions disagree on identical moves,
especially the hook/aphex failure states and high-M releases. A difference in
geometric convergence is not itself a recovery improvement. Conclude whether
geometry is worth optimizing for direct runtime, numerical consistency, both,
or neither on the measured states. Inverse trajectory/recovery consequences
remain untested by this geometry-only replay.

## Frozen inputs and state selection

Read and verify the sealed TG-002 inputs using `experiments/benchmark/campaign.py`.
Do not regenerate or rewrite them. Freeze all selected file hashes and exact curve
coefficients before calculation. Use:

- The common centred TG-002 start, padded to K64, with M1.
- The **last accepted state** from each of the 30 completed PC-002 NS cases,
  including the four unrecovered cases. Keep its recorded K and M. These are
  replay states, not necessarily the curve after an endpoint cleanup operation.

Total coverage is 31 states; no truth-based selection, omitted failed case,
grid start or legacy fixture. Contrasts have no role in the geometry operators;
keep the 30 states because the fitted curves and retained update spaces differ.
Retain duplicate states as case-weighted rows, and additionally report unique
exact-coefficient/K/M groups so identical curves do not inflate coverage claims.

For repeated timing, use the start and the ten contrast-4 last accepted states
(11 states, fixed before any timings). The remaining 20 endpoints receive full
precision/decision coverage and one reported timing, without statistical claims.
Report K, M, grid size, speed ratio and curvature summaries per state.

## Arms and causal contrasts

| Arm | Preparation | Trial projection | Validity | Purpose |
|---|---|---|---|---|
| S | Current CPU `ProjectedUpdate` | Current spline | Sampled | Maintained spline baseline |
| F | Current CPU `SpectralProjectedUpdate` | Current CPU spectral | Sampled | Same-device, same-validity resampler contrast S/F |
| B | Current CUDA batched preparation | Same CPU spectral as F | Same sampled checks as F | Preparation/batching contrast F/B |
| C | Current `DeviceCertifiedUpdate` on CUDA | Current CPU spectral | GPU certificate tiers plus sampled fallback | Production spectral geometry, validity contrast B/C |

B is an experiment-local adapter using `BatchedCertifiedUpdate.prepare` and the
plain `ProjectedUpdate.trial` with spectral `_project`. It must call maintained
implementations, not duplicate their mathematics. Validate its trial and sampled
decisions against F and its preparation against C before comparing timings.
Do not promote B to a production selector.

F/B does not alone isolate GPU arithmetic: batching, shared geometry and skipped
crop diagnostics also differ. On the fixed start plus contrast-4 circle, kite,
hook and aphex states, add a batched Torch **CPU** preparation control and a
CPU spectral coefficient-only diagnostic that omits only the unused crop-error
reconstruction. Confirm coefficients against the unchanged CPU implementation.
Report those ablations separately; retain preparation refusals or fallbacks.

## Identical moves and precision

At every state draw three unit random coordinate directions, seed 3, in its
recorded M space. Scale each direction to maximum physical **raw normal motion**
of 1e-7 m, 1 mm and 6 mm, using the common normal basis on the same base nodes.
This produces nine common moves per state (279 total). Do not scale with an
arm-specific derivative or metric. The same coefficient vector reaches every
arm. Preserve refusals and reasons; do not shrink a move until it passes.

Separate the following measurements:

- Base projection and moved projection differences, and their centred
  increment `z + projection(moved) - projection(base)`. Report cancellation
  rather than attributing a raw base-gauge difference to physical shape error.
- Retained coefficient difference, parameter-aligned maximum/RMS curve
  difference on a common evaluation grid, and normal/tangential components
  relative to the common reference tangent. Parameter-aligned errors are not
  Hausdorff bounds; tangential differences may represent parameterization.
- Native N/2N refinement for both maps. Compare with CPU spectral 4N/8N
  centred increments on the same input curve/move/band. The latter is a
  reference only when its own 4N/8N difference is <=1e-10 sigma0; otherwise
  mark reference unresolved and avoid accuracy-ranking that trial.
- Native geometry derivative-column differences. On the fixed five-state
  diagnostic panel above, repeat central differences at 1e-6, 1e-7 and 1e-8 m,
  using a refined spectral reference with its own resolution check. Separate
  grid error and step-size/cancellation sensitivity. Do not call this a
  physical field-Jacobian comparison.
- Native full-trial accepted/refused outcomes, projection-refinement gate,
  and certificate tiers/fallbacks. Count disagreements, including when one
  map passes its resolution gate and the other does not. A sampled check and
  a coefficient certificate give different assurance; no equivalence of
  rigorous guarantees is claimed.

sigma0 is base perimeter/(2pi), converted with the fixed 0.05 m package length
unit. Record errors in metres as well as normalized units. Retained K stays
identical in all arms; report intentional band cropping separately from
discretization error. Raw `intentional_projection_mm` values use different
evaluation grids and must not be compared as identical precision metrics.

## Locating interpolation error

Choose the six trials with largest native S/F centred-curve disagreement
(descending value, then stable state/move ID; selection is diagnostic only).
For each use one common, fixed moved Fourier curve and its speed/arclength map
to perform a two-by-two interpolation ablation:

| Inverse arclength | Position evaluation |
|---|---|
| Native cubic inverse | Native periodic cubic position spline |
| Refined/root-solved inverse of the same spectral arclength primitive | Native periodic cubic position spline |
| Native cubic inverse | Direct evaluation of the same moved Fourier series |
| Refined/root-solved inverse of the same spectral arclength primitive | Direct moved-Fourier evaluation |

Keep speed integration, moved curve, target arclength grid and retained K fixed
in this panel. Check inverse residuals and refinement of the inverse reference;
use chunked Fourier evaluation to bound memory. Also refine the speed/arclength
grid separately. Distinguish interpolation effects from errors in the common
arclength map and from the spectral quadrature's aliasing/truncation.

Record changes to **error vectors**, as well as error norms. Contributions can
cancel, and sequential norm reductions are not an additive error budget. A
factorial interaction term must be reported when inverse and position errors
interact. No source is declared dominant solely because its code path differs.

## Runtime conditions and profiling

One process, one arm at a time, one CPU BLAS/OpenMP thread; Torch CPU threads one.
Idle GPU, float64/complex128 throughout. Record hardware, dependency versions,
source commit/hashes and device fallbacks. Enforce CUDA synchronization around
wall-time measurements; include host/device copies and returned host arrays.
Record allocated/reserved CUDA peak memory and process host peak memory, with
the measurement scope stated.

Record process/device startup and a single common-start warm-up per arm
separately, then use three measured preparation repeats on the 11-state timing
panel. Counterbalance arm order deterministically between repeats. Report
paired medians and ranges, not ratios of unrelated campaign totals.

Full decision coverage uses all nine common moves. Repeated full-trial timing
uses the first 1 mm and first 6 mm directions on each timing-panel state.
Use a fresh prepared space at the start of each repeat: report first-trial
(lazy base-certificate build included) and subsequent-trial times separately.
Use the same geometry runtime (`both`) and exact-validation-cache lifecycle
for all arms; state whether a result is cold within the space or reused.

Keep instrumentation outside the timed headline runs. Profile an additional
fixed-panel pass with nested timers/counters: base jets/basis, normal move/FFT,
speed/arclength, spline inverse, spline position evaluation, coefficient FFT,
spectral coefficient quadrature, crop-error reconstruction, FD construction,
host/device transfer, validity and certificate work. Report exclusive times
or explicitly labelled nested times; do not double-count them or mix profiled
and uninstrumented headline totals. Reconcile components with complete wall
time and report overhead/unattributed remainder. Never subtract an estimate
from headline time as though it were measured work.

## Validation, preservation and stopping

**Implementation detail fixed before dispatch (2026-10-05):** precision replay
uses a fresh sampled-validation cache per full trial, with the lazy certificate
retained in its arm's prepared space. Repeated timing/profiling use a fresh cache
per arm/space, shared across its first and subsequent trials. Coefficient-array
errors are evaluated on the common 2N grid. The derivative reference's 4N/8N
column gate is 1e-5 relative; this is a reference-qualification diagnostic, not
the physics derivative acceptance gate. The interpolation reference uses 4N/8N
refined inversion of the **same native** Fourier arclength primitive. Chunked
direct Fourier evaluations omit at most 2e-13 package units in coefficient l1
norm, with the actual bound recorded; that limit is not a fitted tolerance.

Implement the driver under `experiments/benchmark/`, with no imports of campaign
data added to `solvers/bem_inverse/`. Focused validation checks adapter fidelity,
common move units, centred increment construction, error-vector decomposition,
inverse residuals and receipt/provenance integrity. No blanket inverse suite or
new inverse campaign is needed because production numerical code is unchanged.
Validate before committing the driver; run only after GC-001 ID approval.

Write incremental per-state/per-trial receipts under the fresh
`results/validation/cleaned_interfaces/GC-001/` directory. Preserve exceptions,
OOMs, reference failures, disagreements and unfinished coverage. Never overwrite
old reports or numerical sources. If CUDA is unavailable or the adapter fails
equivalence, retain that failure and stop the corresponding causal comparison;
do not silently replace the CUDA arm with CPU. Unresolved reference trials may
still report native disagreement/timing without an accuracy claim.

After execution validate the bundle, prepare the runtime/precision/attribution
table and report here, write iteration-30 results, then commit and push code,
documentation and all result/failure evidence on the existing branch. Verify
the remote commit and final working-tree status. No production change or further
inverse experiment is authorized by this plan.
