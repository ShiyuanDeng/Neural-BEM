# Inverse BEM runtime and recovery audit

2026-10-05. Codex. Review of the maintained package at `9d01de74`, the
archived GGB-001 comparison, and completed TG-002 campaigns.

**The first priority is the optimizer's handling of difficult steps.** Case 8
spent 348 seconds without recovering, while its recorded physics calls cost
29 seconds. Its damping controller repeatedly became more aggressive after
accepting severely shortened steps. Faster LU or a cheaper Jacobian cannot
repair this. For ordinary TG-002 runs, the largest already-demonstrated saving
is the audited accuracy exit: 31.4% less total time with the same 26/30
recoveries. Further opportunities are repeated refinement evaluations, geometry
work on doomed proposals, wave construction, and serial audits.

BEM does have demonstrated quality advantages on GGB cases 13 and 14, but
these are known-material shape controls. There is no evidence that case 8's
extra time buys better accuracy, and no proposed fix below has demonstrated
case 8 parity.

This is a source and saved-receipt audit. No new inverse experiment, forward
solve, geometry replay, or timing benchmark was run. Frequency-information
changes belong to the user's separate investigation. The pre-existing
uncommitted GGB-002 work and iteration-32 draft were left untouched.

## Evidence and timing boundaries

Primary records are the [GGB comparison](01_results.md), its
[summary](../../../results/validation/cleaned_interfaces/CI-SPD/comparison_summary.json),
the [ON-001 comparison](../../../results/validation/cleaned_interfaces/ON-001/final_comparison.json),
and [RG-001 results](../cleaned_interfaces/iteration_31/05_results.md).
The accompanying [receipt analysis](../../../results/validation/cleaned_interfaces/inverse-pipeline-audit-20261005/receipt_analysis.json)
contains recomputed totals, acceptance decisions, case-8 damping histories,
and SHA-256 hashes of the 313 source/evidence files used in that calculation.

Three distinctions matter:

1. GGB-001 used one real frequency, all 512 transmitter/receiver pairs, 5%
   noise, and M3/M7/M11 stages with 100 iterations each. It did not execute the
   TG-002 continuation policy. TG-002 uses 19 frequencies, 24 paired
   measurements per frequency, a centred start and no localization.
2. ON-001 E is an opt-in recipe, not the unchanged default. Its campaign cap
   was 120 seconds; the package's default policy allows 1800 seconds.
3. Geometry counters cover initial, fitting, and endpoint-audit work on one
   update object. Physics timers also include audits, overlap across frequency
   threads, and can include lock waits. Neither is a disjoint fit-time profile.

The existing [iteration-32 draft](../cleaned_interfaces/iteration_32/01_results.md)
subtracts all geometry time from fit time and calls the remainder physics.
That is not a measured partition. Its 82% physics and 18% geometry figures
for successful fits, and its lean-LM speed forecasts, need this qualification.
The earlier [timing review](MODAL_RUNTIME_GEOMETRY_CHECK.md) already documents
the shared-counter issue.

## Where the retained TG recipe spends time

The following aggregates are from ON-001 E. Summed case times are not the
elapsed time of a concurrently executed campaign.

| Disjoint output accounting | 26 recovered cases | Four failures | All 30 |
|---|---:|---:|---:|
| Fitting | 336.23 s | 101.80 s | 438.03 s |
| Numerical audits | 82.22 s | 11.52 s | 93.74 s |
| Remaining setup and output boundary | 16.68 s | 2.54 s | 19.22 s |
| Audited output | **435.14 s** | **115.85 s** | **550.99 s** |

Audits consume 17.0% of total audited-output time. Geometry preparation plus
trial work totals 60.16 seconds on successes and 49.75 seconds on failures:
**14.4% and 43.9% of the respective runner totals**, including audits. The
fit-only shares are not recorded; 17.9% and 48.9% are upper bounds. Geometry
must not be added to the disjoint table above because it occurs inside both
fitting and audits.

| Nested cumulative component | Successes | Failures | Interpretation |
|---|---:|---:|---|
| Geometry preparation | 19.08 s | 2.03 s | Includes audit preparations |
| Complete geometry trials | 41.08 s | 47.72 s | Includes certificate and projection work |
| Certificates | 19.05 s | 46.14 s | A nested timer, not an additional wall component |
| Projection quadrature | 13.33 s | 0.49 s | Inside trial construction |

Across all 30 cases, recorded physics phase durations are assembly 300.39 s,
waves 232.99 s, LU 197.72 s, modal geometry 105.49 s, fields 64.39 s and
Jacobian 19.51 s. These rank useful inspection targets but **are not wall-time
shares**. In particular, assembly timing starts before acquiring the global
GPU lock. Failed phase timings are incomplete because the phase context
manager lacks `finally`; overall failed-call time is recorded separately.
See [modal_muller.py](../../../solvers/bem_inverse/modal_muller.py).

## Case 8 exposes a controller problem

| Archived observation | Value |
|---|---:|
| BEM fit / endpoint audit | 347.935 / 1.095 s |
| GauGal optimization | 0.814 s |
| BEM / GauGal data residual | 87.66% / 5.26% |
| Proposed / accepted steps | 845 / 99 |
| Self-intersection / physics / projection refusals | 669 / 73 / 4 |
| Recorded physics calls, including failures and derivatives | 28.887 s |
| LU / derivatives, already included in physics | 0.371 / 0.262 s |

The unpartitioned remainder is 320.144 seconds, or 91.7% of fit plus audits.
It includes trial geometry, certificates, preparation, bookkeeping and
rasterization. GGB-001 did not save the geometry sub-timers needed to assign
all of that remainder to certificates. Removing LU entirely would save only
about 0.1% of this run.

The important trajectory evidence is more specific than the aggregate:

- M3 accepted 76 steps; 32 required seven halvings, or 1/128 of the proposed
  step. Nevertheless, damping decreased after every acceptance. It reached
  `1.8248e-43`; the last five attempted damping levels reached only
  `1.8248e-39`. At those scales damping effectively no longer changes the
  normal-equation direction.
- M7 accepted all ten steps at seven halvings. It spent 50.80 seconds reducing
  relative residual from 1.12277 to 1.10891, only about 1.2%.
- M11 ended with gradient infinity norm 8.13 and residual 0.87662. All three
  stages stopped with `no_decreasing_step`; this is not evidence of a
  stationary solution or successful convergence.

The current [LM implementation](../../../solvers/bem_inverse/continuation/lm_backend.py#L864)
still multiplies damping by 0.3 after every accepted step, regardless of the
accepted fraction. Actual/predicted gain is optionally logged but does not
control damping. The numerical floor is the smallest positive normal float,
which provides no practical regularization floor here.

**Proposed fix:** update damping using model agreement and the accepted step
fraction; retain or increase it after severe shortening; use a meaningful
floor in the scaled normal equations; detect repeated clipped proposals.
Retain a bounded line search initially. The fact that 98% of successful TG
steps needed no halving does not justify removing the mechanism on case 8,
where progress depended on it. This is a supported inefficiency diagnosis,
not proof that repaired damping will recover the target.

Also check wall/proposal budgets before constructing geometry. Currently,
pure geometry-refusal loops can traverse up to five damping attempts times
eight backtracks without reaching the physics reservation that checks time.
A proposal cap and progress stop prevent long failed runs; **failing faster
must be reported separately from improving recovery**.

Historical provenance limits the diagnosis. GGB's 65 BEM source hashes match
`6f2c1408` and `5cb9bac8`; five files differ at the reviewed current commit.
Commit `f2a3d441` changed failed candidate physics from refusal-and-continue
to an immediate numerical stop. Thus the 73-failure retry sequence is
historical, while the damping defect remains. The archived exceptions were
discarded, so their underlying numerical causes cannot now be identified.
Future receipts should retain exception type, message and candidate identity.

## Component audit and concrete changes

| Component | Assessment | Recommended treatment |
|---|---|---|
| Inputs and localization | Current TG contract uses a centred start and no search. GGB has a different acquisition and initial mismatch. | Preserve the TG contract. No new far-start cases or grid initializer. |
| Continuation and stopping | Default noiseless loss tolerance is 1e-14 and required-accuracy exit is off. Scheduled releases can continue after required quality is reached. | Use the qualified ON-001 E recipe where 0.003 residual is the required endpoint; retain its passed audit. |
| LM direction and globalization | Tiny damping, coordinate clipping and repeated backtracking can combine into almost repeated invalid steps. | Repair the damping feedback described above; log clipping, accepted fraction and gain ratio. |
| Geometry preparation | Batched CUDA preparation and GPU certificates already exist. High storage band 192 gives an 8192-point geometry grid and 16384-point refinement. | Reuse exact base nodes, normals and basis arrays across backtracks; avoid claiming an already-present GPU port as a new saving. |
| Certificates and validity | Coarse moved curve, fine moved curve and projected candidate are checked. Difficult trials can exhaust full certificates before sampled refusal. | Cache exact compatible certificates across accepted states; investigate an early rejection screen with validated refusal behavior. Retain projected-candidate validity. |
| Finite projection | Trial quadrature remains CPU work; coarse/fine agreement protects the discrete update and its derivative. | Cache immutable work first. Qualify any coalescing or device port against candidate coefficients and full-trial derivatives. |
| Modal geometry and field resolution | Trace dimension is chosen from stored geometry band, not measured error, frequency or contrast. Full-catalog storage 192 increases the field system from 258 to 514 unknowns. | Develop an accuracy-selected modal profile with bounded refinement response; avoid arbitrary truncation cuts. |
| Operator assembly | GPU work is serialized; assembled matrices return to the host. Resolution-dependent indices and log symbols are rebuilt repeatedly. | Cache resolution-only arrays and compare bounded frequency batching. Measure GPU execution separately from waiting and transfer. |
| Incident and receiver waves | CPU Graf work is substantial. `WaveArrays.ensure` rebuilds existing cells when either required dimension grows. | Preplan active-catalog bounds or append only missing rows/columns, preserving expansion tolerances. |
| LU and field readout | Factors are already reused for sources and reciprocal solves. Small matrices and host/device transitions complicate GPU benefits. | Compare resident batched solves only after repeated evaluations are reduced. GPU LU is not automatically faster and is irrelevant to most case-8 cost. |
| Shape Jacobian | Reciprocal differentiation reuses factors; it is already cheap compared with full evaluation. | Keep it. Avoid rebuilding the next tangent/Jacobian after a terminal loss or iteration condition when callbacks/checkpoints do not need it. |
| Refined acceptance | Nearly half of successful-fit forward solve counts are acceptance validation. Every improving trial can trigger refinement. | Qualify adaptive refinement checks using an error budget relative to predicted decrease; keep periodic and endpoint validation plus bounded resolution response. |
| Endpoint audits | All frequencies are processed serially despite configured frequency parallelism. Fields, Jacobian columns and full-trial FD are checked. | Stream small parallel frequency batches within memory limits. Reuse raw initial-audit calculations only with an exact key; recompute data-dependent normalization and verdicts. |
| Cleanup, frontier and output | Cleanup is crop/pad; frontier costs one evaluation and derivative. JSON/checkpoint overhead has no exclusive timing. | Low priority. Measure output separately before changing it; preserve failure evidence. |

Relevant implementation: [policy](../../../solvers/bem_inverse/policy.py),
[LM](../../../solvers/bem_inverse/continuation/lm_backend.py),
[certified trials](../../../solvers/bem_inverse/certified.py),
[geometry selection](../../../solvers/bem_inverse/geometry_selection.py),
[wave arrays](../../../solvers/bem_inverse/modal_geometry.py#L241),
[assembly](../../../solvers/bem_inverse/modal_cuda.py#L254),
[physics and resolution](../../../solvers/bem_inverse/modal_muller.py#L138),
and [audit execution](../../../solvers/bem_inverse/runner.py#L63).

The exact cache key must include curve coefficients, resolution/window,
precision, device and tolerances, plus material, frequency and acquisition
where relevant. Equal starting circles alone do not make audit verdicts
interchangeable: normalization uses each scene's observed data.

## Which safeguards earn their cost

The [ON-001 results](../cleaned_interfaces/iteration_31/01_results.md) establish
803.35 to 550.99 seconds across the 30 cases, with 26/30 recoveries in both
arms and median paired speedup 1.546x. This trades unnecessary accuracy for
the declared requirement: median recovered RMS changes from 0.00191 to
0.01498 mm; the largest E recovered RMS is 0.1883 mm against a 1 mm gate.
Recovery retention does not mean identical final accuracy.

For refinement checks, direct reclassification of saved proposals gives:

| Saved E paths | Checks | Actual accepts | Accepts if production gain exceeds recorded margin | Changed decisions |
|---|---:|---:|---:|---:|
| 26 successes | 1660 | 1313 | 1313 | 0 |
| Four failures | 393 | 259 | 263 | 4 |

This supports testing fewer refinement evaluations on resolved paths. It does
not establish a safe universal deletion: every failed case diverges, the
recorded margin itself includes refined information, and changing other
parts of the update changes the proposals being tested.

Likewise, zero fine/candidate geometry refusals on saved successful paths
does not prove the checks redundant. A valid displaced curve can become
invalid after projection. GC-001's 279 fixed moves showed matching sampled
and certified decisions, but that is bounded replay evidence, not a guarantee
on new optimizer paths. Continuous coefficient certificates have a heuristic
floating-point allowance and sampled fallback; they are not interval proofs.

All four ON-001 TG failures hit the frozen resolution gate. Current modal
behavior stops the whole fit on the first improving unresolved candidate;
it has no modal promotion response. **Simply weakening that gate was already
tested:** RG-001 added no recoveries and increased its matched suite from
554.11 to 841.09 seconds. Aphex c4 improved in RMS but still failed overall
recovery and numerical gates. A bounded resolution response is a better
target than allowing unresolved progress indefinitely.

The existing reach-clipping and working-frequency screens were negative,
the Gaussian geometry map failed finite-trial qualification, and the Ewald
replacement remains unqualified. These should not be presented as available
speed fixes. See [ON-001](../cleaned_interfaces/iteration_31/01_results.md)
and [EW-001](iteration_03/05_results.md).

## What is better than GauGal and what is not established

| Case | GauGal / BEM image RRMSE | GauGal / BEM contrast SNR | GauGal optimization / BEM fit |
|---|---:|---:|---:|
| 8 | 0.01891 / 0.06452 | 8.31 / -1.39 dB | 0.814 / 347.935 s |
| 13 | 0.01818 / 0.00960 | 11.35 / 17.57 dB | 1.265 / 1.928 s |
| 14 | 0.02024 / 0.01503 | 11.97 / 14.90 dB | 0.865 / 36.191 s |

BEM produces sharper, more accurate homogeneous shapes on 13 and 14. Case 13
is a defensible quality/time tradeoff; case 14 pays much more for a smaller
quality gain. BEM knows the true material, whereas GauGal estimates material
coefficients. These results do not establish superiority at equal prior
information. The timers also have different boundaries and only one execution
per case, so their ratios are not controlled end-to-end speedups.

BEM's full numerical audit checks fields, normalized Jacobian columns and the
complete finite-trial derivative. That is useful assurance. It normally
compares two resolutions of the same backend, not an independent solver.
GGB used a narrower endpoint field check; case 8 passed it at 5.95e-6 against
1e-4 while remaining unrecovered. Numerical resolution and inverse success
must remain separate claims.

GauGal's fixed-domain representation reuses operators and uses batched FFT
propagation without deforming, projecting or validating a boundary at each
iteration. This structural advantage matters more than parameter count.
Its success on the same single-frequency measurements means lack of frequency
information alone is not yet an explanation of the difference; the separate
investigation must distinguish data information from optimization and priors.

## Recommended order and acceptance criteria

1. **Use the already-qualified accuracy exit and repair the damping
   controller.** Add proposal/deadline checks and useful failure details.
   These directly address observed waste without replacing the formulation.
2. **Reduce repeated work while preserving decisions:** immutable geometry
   caches, incremental wave arrays, resolution-only assembly caches, bounded
   parallel audits, and avoidance of terminal linearization work.
3. **Qualify adaptive numerical effort:** modal resolution selection and
   response, then less frequent refined acceptance. Keep endpoint accuracy
   gates and report failed-run time as well as successful-run speed.
4. **If feasibility still blocks recovery, test explicit rigid translation
   coordinates alongside shape deformation.** Exact translation preserves
   boundary validity, whereas repeated finite normal moves can distort a
   shape while moving it. This is an untested pose hypothesis, requires a
   matching discrete derivative, and does not imply a grid initializer or
   additional observations.

Before a new comparison, record exclusive initial-audit, fit, early-audit and
terminal-audit timings; split GPU queue and execution time; preserve failed
phase durations; count geometry proposals and actual dispatched physics work.
Require unchanged recovery gates, no new failures, and time to a qualified
endpoint. For case-8 competitiveness, a quick failed return is insufficient:
recovery must approach the noisy-data discrepancy with competitive shape
quality under a declared information and timing contract.

No new experiment ID is approved by this report. New inverse experiments
must follow TG-002 and receive explicit ID approval. A future case-8 rerun
would additionally need an explicit exception to the current prohibition on
new far-start experiments. Existing case-8 receipts can support source and
trajectory analysis without reopening that campaign.

Validation for this report: recomputed the ON-001 aggregates and all saved E
acceptance comparisons directly from JSON; checked 26 successes plus four
failures, 845 GGB proposals and 669 self-intersection refusals; cross-checked
the current damping rule against archived histories. No implementation was
changed or speedup newly measured.
