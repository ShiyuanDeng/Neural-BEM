# GGB-002 stage one actions and source checks

Questions: What changes with real-only data, modal versus nodal BEM, and the bandwidth and frequency schedules?
How accurately are all reconstructed components and their material field recovered, with and without noise?
What must be ready for the first comparison on sealed TG-002 without waiting for plane-wave support or every ablation?

Checked 17 November 2026 against `organised` at `af68817f7917cfa927355862dad4e3929c098321`.
Revised on 17 November after the user's stage-one decisions, recorded in [D12](../../../../cleanup/user_decisions.md#d12-stage-one-baseline-comparison-scope-2026-11-17).
The action scope below is decided; implementation and new experiments have not started.
The source checks used code and saved results; no forward or inverse solver was run.

**[read]** identifies source evidence; **[calculated]** identifies arithmetic on saved records;
**[decision]** identifies the user's requirements; **[proposal]** identifies details still to fix; **[inference]** identifies interpretation.
The supplied report's effort labels and proposed settings are not measured results.

## Revised stage one actions

| Step | Action and output | What the source check changes |
|---|---|---|
| 1.1 | **[decision]** Write a settings sheet: known object count/material, unknown curve or curve plus contrast, background 6, lossless model, start, observations, bands, stopping, hardware and timing scope. | **[read]** The benchmark and saved settings supply most fields. Identify historical S1/S3/S2/B1 records separately from the current default. [Benchmark](../../../../../experiments/benchmark/README.md), [B1 amendment](../03_plan.md#L603). |
| 1.2 | **[decision]** Correct the existing report, its recovery count and contrast terminology; distinguish the two experiments called GGB-002. | **[calculated]** Both BEM arms recover 26/30. Fix current narrative and its renderer; preserve dated historical statements. Use branch-qualified descriptive names instead of moving old results. [CSV](../comparison.csv), [renderer](../../../../../experiments/gaugal_comparison/report.py#L387). |
| 1.3 | **[decision]** Make unaligned symmetric-difference area divided by true area the primary region metric. Count and score all reconstructed components; include material-field error. Retain boundary, centroid, Chamfer and image scores, work counts and comparable timing. | **[read]** Extend the existing scoring and counters, replacing the longest-contour-only rule for the new protocol. Fix thresholds, connectivity, holes, empty outputs and sensitivity rules before results. [Scoring](../../../../../experiments/gaugal_comparison/ggb_scoring.py), [ledger](../../../../../solvers/bem_inverse/work.py). |
| 1.4 | **[decision]** Run clean and 5% complex-Gaussian noisy cases, with multiple predetermined noise seeds and the same draws for every compared method. Report results by contrast. | **[read]** Noise metadata, noise-aware stopping and residual limits already exist. Fix the seed count and expected-versus-realized, per-frequency noise convention in the protocol. [Policy](../../../../../solvers/bem_inverse/policy.py#L104), [residual limits](../../../../../experiments/cleaned_interface/benchmark.py#L337). |
| 1.5 | **[decision]** Change `Problem` to represent genuinely real-only input. Remove damped observations from the entire inversion, including initial localisation, material initialization, warm-up and all optimization stages. Keep supplied-contrast and recovered-contrast arms distinct. | **[read]** The current contract requires matched catalogs and the default schedule consumes damped data. Keep TG-002's centred 65 mm start and localization `none`; no initializer may obtain information from a damped catalog. [Input contract](../../../../../solvers/bem_inverse/problem.py#L56), [schedule](../../../../../solvers/bem_inverse/policy.py#L143). |
| 1.6 | **[decision]** Prioritise real-only versus real+damped data; modal versus nodal BEM; adaptive versus fixed-bandwidth continuation; and frequency continuation versus simultaneous inversion. | **[decision]** Gradient descent and top-frequency-only are removed from mandatory experiments. Separate data, backend, shape-band and frequency-schedule effects; reuse matching runs from 1.4–1.5. Remaining ablations need not finish before external baselines start. [Policy](../../../../../solvers/bem_inverse/policy.py). |
| 1.7 | **[decision]** Compare one unchanged TG-002 case with an independent forward implementation, matching physical conventions and recording field differences. | **[read]** RegPy and chunkIE contain suitable components, but neither bridge is verified by execution. This independent forward check stays in Stage 1. Sources and remaining checks are below. |
| 1.9 | **[decision]** Freeze the evaluation protocol before running external inverse baselines. Record the core BEM reference results and failure explanations; append the remaining ablations as they finish. | **[decision]** Completion of every ablation is not a prerequisite for the first baseline comparison. Fix thresholds, components, material metrics, seeds, arms and budgets before their runs, with later changes recorded prospectively. |

**[decision]** Former step 1.8, TG-002-F and production plane-wave/full-matrix support, moves to Stage 2.
The first baseline comparison uses sealed TG-002 and must not wait for this extension.
The numbering above preserves the original step references.

## Real-only input and ablation controls

**[decision]** The real-only `Problem` must accept an absent damped catalog explicitly.
All initialization, localisation hooks, material estimates, warm-up, continuation and fitting must use real observations only.
TG-002 retains localization `none` and the same centred 65 mm start; no new localization search is introduced.

**[proposal]** Compare each pair with the same cases, prior, real observations, noise draws, start, scoring and declared budget.
For real-only versus real+damped, record the extra catalog explicitly; it changes both available information and the usable schedule.
Reuse the corresponding 1.4–1.5 results rather than repeat identical fits.

**[proposal]** For modal versus nodal, change the fitting backend while keeping the observations and geometry update fixed.
For adaptive versus fixed bandwidth, specify the normal-update and stored-curve bands separately from physics resolution.
For frequency continuation versus simultaneous inversion, retain the same frequency set and define the shape-band schedule independently.

**[decision]** The four comparisons above replace the earlier mandatory top-frequency and gradient-descent comparisons.
Their completion is part of the study, but unfinished ablations do not delay external baselines once the fixed comparison setup is ready.

## Confirmed benchmark facts

**[read]** TG-002 has ten single-object shapes at ratios 0.5, 4 and 13.3, a centred 65 mm start,
24 line-source/receiver pairs on a 0.30 m ring, and 19 frequencies from 0.25 to 2.5 GHz.
The receiver offset is 0.2 radians. [Scenes](../../../../../experiments/benchmark/scenes.py#L24), [acquisition and frequencies](../../../../../experiments/cleaned_interface/benchmark.py#L125).

**[read]** Background relative permittivity 6 enters the wavenumber calculation; the contrast is a permittivity ratio.
**[calculated]** Ratios 0.5 / 4 / 13.3 correspond to susceptibilities −0.5 / 3 / 12.3 and object permittivities 3 / 24 / 79.8.
[Wavenumbers](../../../../../experiments/cleaned_interface/benchmark.py#L146), [ratio and susceptibility](../../../../../experiments/gaugal_comparison/tg002_data.py#L26).

**[read]** CPU `nodal_kress` generated noiseless real and damped catalogs; damping multiplies the wavenumber by `1 + 0.25i`.
**[calculated]** All 60 saved qualification records pass N1024/N2048 agreement at the stated 1e-8 tolerance.
This is a self-refinement check, not independent proof of absolute field accuracy. [Generator](../../../../../experiments/benchmark/campaign.py#L88), [saved inputs](../../../../../results/validation/cleaned_interfaces/TG-002/inputs/).

**[read]** New runs use `modal_muller` + `slider`, with localization `none`.
The historical comparison also uses damped continuation data; GauGal uses only the real observations.
[Benchmark default](../../../../../experiments/benchmark/README.md#L42), [comparison](../report.md#L7).

**[calculated]** Recomputed from the 90 rows of [comparison.csv](../comparison.csv):

| Arm | Shared limits met | Median boundary RMS mm | Median recorded seconds |
|---|---:|---:|---:|
| BEM supplied contrast | 26/30 | 0.00335864 | 14.1088 |
| BEM recovered contrast | 26/30 | 0.00721246 | 20.9497 |
| GauGal | 0/30 | 25.1609 | 340.2881 |

**[read]** GauGal has 30 iteration-limit exits at 80 iterations; one case has no finite boundary score.
Boundary medians exclude missing values. Timing includes different components between methods and old/new BEM records.
These medians therefore do not establish a controlled speed ratio. [CSV](../comparison.csv), [timing explanation](../../../../../experiments/gaugal_comparison/report.py#L424).

**[read]** On three original SingleTX cylinder scenes (8, 13, 14), GauGal optimization took 0.814, 1.265 and 0.865 seconds.
Totals excluding load were 1.184, 1.386 and 0.990 seconds; loading added 0.601, 0.558 and 0.539 seconds.
These were 300-iteration, single-frequency 0.4 GHz runs on the RTX 5090. [Saved native-scene results](/home/drdeng/Gau-Gal/docs/iterations/GGB-001/results.md).

**[decision]** Preserve this seconds-per-scene result whenever discussing GauGal cost (user reminder, 17 November).
The 340-second median describes the 19-frequency, 80-iteration TG-002 adaptation; it is not a general GauGal runtime.
**[inference]** The differing settings identify separate measurements, but do not establish the cause of the full timing gap.

## Corrections to the record

- **[read]** The stale 23/30 statement occurs in the [report](../report.md#L394),
  [report generator](../../../../../experiments/gaugal_comparison/report.py#L391) and current summary of the [handoff](../04_handoff.md#L17).
  The [B1 amendment](../03_plan.md#L603) and CSV establish 26/30. Historical pre-B1 counts remain valid for their date.
- **[read]** B1 also changed numerical implementation for nine refits, including removal of a degree cap and a sampled-log fallback.
  The table combines saved runs from different revisions; it is not one fresh campaign using a single current implementation.
  [B1 provenance](../03_plan.md#L619).
- **[read]** The report's claim that all four supplied-contrast failures stop at the lower-bound calculation is stale.
  Cog c13.3 and aphex c4/c13.3 completed their schedules; aphex c0.5 has a numerical failure.
  Their actual residual and shape failures are in the [CSV](../comparison.csv).
- **[read]** The recovered-contrast failures are asymmetric c13.3, hook c0.5, cross c13.3 and cog c13.3.
  All three aphex cases now meet the recovery limits. Avoid describing both BEM arms as having the same failures.
  [CSV](../comparison.csv).
- **[read]** On `feature/shape-frequency-continuation`, GGB-002 means SingleTX case 8 with four real frequencies.
  Use names such as “GGB-002 organised TG-002 comparison” and “GGB-002 continuation SingleTX case 8”.
  [Other experiment at inspected revision](https://github.com/ShiyuanDeng/Neural-BEM/blob/5cc25845e51b5cec4e16b4e1b3602555a023b832/docs/iterations/CI-SPD/GGB-002_plan.md).

## Scoring and noise details to settle

**[read]** Existing rasterization uses area fractions; contour extraction uses half the largest absolute susceptibility,
retains that extreme's sign, chooses the longest closed contour, then fits a band-48 Fourier curve.
That is more specific than “half the recovered range”. [Rasterizer](../../../../../experiments/gaugal_comparison/tg002_data.py#L70), [tracer](../../../../../experiments/gaugal_comparison/ggb_scoring.py#L40).

**[read]** eispy2d thresholds contrast magnitudes. Its shape score removes translation using magnitude-weighted centroids;
its position score uses unweighted support centroids on normalized image axes, multiplied by 100.
Neither is simply the proposed raw physical-coordinate metric. [Metric implementations](https://github.com/andre-batista/eispy2d/blob/a72831db93d64c7b80282579f48de4c110627eeb/eispy2d/core/result.py#L3070).

**[decision]** Use unaligned symmetric-difference area divided by true area as the primary region metric.
Compute it on the union of all reconstructed support components, preserving holes; report the component count explicitly.
Retain centroid distance in mm and give any centred eispy2d score a separate, secondary column.

**[decision]** Do not discard smaller components before region, material or boundary scoring.
The new protocol must retain all component boundaries for RMS, Hausdorff and Chamfer calculations and define empty-output behavior.
Fix the support threshold, sign handling, grid connectivity, hole treatment and any contour smoothing before running comparisons.

**[proposal]** Report material-field relative L2 error on the full common grid using signed susceptibility, normalized by the true field norm.
This includes false components, missing material, wrong sign and wrong amplitude without alignment or per-image rescaling.
Keep existing RRMSE, SSIM and PSNR as additional image scores; freeze the precise material-error definition in 1.9.

**[inference]** Pixel spacing alone does not force failure of a 1 mm boundary test: interpolated contours can have subpixel positions.

**[read]** Borges–Rachh–Greengard describes normalized polygon set-difference area, without specifying symmetric difference or centring.
**[proposal]** Define symmetric difference explicitly in our protocol rather than claim an exact reproduction of that metric.
[Paper section 4](https://arxiv.org/html/2210.11607#S4).

**[read]** The benchmark pass rule uses RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm and a per-frequency residual limit.
The latter is the larger of 0.003 and three times the saved realized noise fraction; it need not equal exactly 0.15 for a 5% expected-noise draw.
[D11](../../../../cleanup/user_decisions.md#L223), [implementation](../../../../../experiments/cleaned_interface/benchmark.py#L337).

**[read]** Five-percent noise has precedent, but “every comparable paper adds noise” is unsupported.
One cited paper uses Gaussian draws rescaled to 5% norm; another uses 2% pointwise random-phase noise; the penetrable-object paper specifies no noise level.
[5% example](https://arxiv.org/pdf/1408.5436#page=10), [2% example](https://arxiv.org/html/2104.13489#S5.SS1), [penetrable example](https://arxiv.org/html/2210.11607#S4).

**[proposal]** Save each noisy array, seed, expected component variance and realized per-frequency noise norm.
Use the same real-frequency noisy data across methods. Any arm receiving additional damped observations remains separately labelled.
Set the seed count and work budget before execution; “several seeds” is not a run count.

**[read]** `fit_work.solves` and `fit_work.reciprocal_batches` already record charged forward and derivative batches.
**[proposal]** Export them separately, define a batch versus source RHS, and separate final scoring from fit time.
Record whether “CPU time” means CPU-only wall time or process CPU consumption. [Ledger](../../../../../solvers/bem_inverse/work.py#L103).

## Independent forward check in Stage 1

**[read]** RegPy `TransmissionOp` has finite-source and near-field branches and accepts density ratio 1; its default is 2.
Its finite-source normalization and explicit receiver-array orientation need checking before use as a reference.
[Transmission source](https://github.com/regpy/regpy-examples/blob/573affa2e7c2e9f00d9fff39e0590f46bff4d933/obstacles2d/transmission_op.py#L38).

**[read]** chunkIE has transmission kernels, finite-target evaluation and the same outgoing point-source Green-function convention.
Its point-source helper constructs regional jumps; physical incident scattering still needs the matching jump signs and scattered-field output.
[Helper](https://github.com/fastalgorithms/chunkie/blob/9deac776188bbf5279f68308d6434290f66ff058/chunkie/+chnk/+helm2d/transmission_helper.m), [demo](https://github.com/fastalgorithms/chunkie/blob/9deac776188bbf5279f68308d6434290f66ff058/chunkie/demo/demo_concentric_transmission.m#L90).

**[proposal]** For one independent check, match the same saved curve, physical length scale, wavenumbers, equal-density interface,
source amplitude, receiver coordinates and scattered-field convention. Record a field-error criterion before calculating the comparison.
Agreement for one case would not establish accuracy or inverse convergence for every case.

## Full aperture support moved to Stage 2

**[decision]** TG-002-F is Stage 2 work because it requires changes to the production modal solver.
It is not a prerequisite for the first comparison on the sealed source–receiver pairs.

**[read]** The nodal forward helper supports plane waves, but production `modal_muller` rejects them and full-matrix point sources.
[Forward helper](../../../../../solvers/bem_inverse/continuation/forward.py#L224), [modal restriction](../../../../../solvers/bem_inverse/forward_solvers/modal_muller.py#L130).

**[read]** In the A1–C12 chain, plane-wave/full-matrix support reaches A3 illumination, A4 receiver evaluation and B7 derivatives.
The existing A4 evaluates a paired diagonal; B7 contracts paired columns. Changing the acquisition class alone is insufficient.
[Code map](../../../../reference/inverse_information_chain.md), [A4](../../../../../solvers/bem_inverse/a4_fields.py#L26), [B7](../../../../../solvers/bem_inverse/b7_data_jacobian.py#L30).

**[read]** The other branch already has a point-source full-matrix research adapter and a real-frequency fitting driver.
**[inference]** Review those for reuse, but they use the older solver interface and do not supply plane-wave support.
[Adapter](https://github.com/ShiyuanDeng/Neural-BEM/blob/5cc25845e51b5cec4e16b4e1b3602555a023b832/experiments/benchmark/ggb002_adapter.py), [driver](https://github.com/ShiyuanDeng/Neural-BEM/blob/5cc25845e51b5cec4e16b4e1b3602555a023b832/experiments/benchmark/ggb002.py).

**[proposal]** In Stage 2, TG-002-F keeps all 30 targets and their placements in a separate sealed input directory.
The report's 24 directions × 24 receivers would provide 576 complex samples per frequency; that acquisition is still a proposed choice.
Establish production support and the real-frequency recipe before generating and fitting a full new catalog.

**[read]** Borges–Rachh–Greengard reports boundary-solver failure on one trapping cavity.
**[inference]** That is a relevant comparison, not proof that wave trapping caused the saved TG-002 failures.
The failure discussion should start from the actual run records. [Cavity example](https://arxiv.org/html/2210.11607#S4.SS3).

## Order and first baseline comparison

**[decision]** Keep report corrections, all-component and material scoring, clean and 5% multi-seed runs,
the entirely real-only arm, independent forward validation and protocol freezing in Stage 1.
Move TG-002-F to Stage 2 and remove gradient descent and top-frequency-only from the mandatory experiments.

**[proposal]** First complete 1.1–1.3 and specify the real-only interface, run matrix and evaluation rules.
Prepare the core BEM reference results under 1.4–1.5 and the independent forward check under 1.7.
Reuse these runs in 1.6 and record any remaining ablation work separately.

**[decision]** Freeze the protocol before any external inverse baseline runs.
Once the comparison setup and core reference results are ready, begin the first sealed TG-002 baseline without waiting for every ablation.
Append later ablation results under the same rules; record any necessary protocol change before the affected runs.

**[inference]** The report's “low effort” labels understate the real-only and ablation work;
the production plane-wave/full-matrix extension belongs to Stage 2. No measured runtime estimate exists for these new arms.
The universal literature requirement, external-code compatibility and cavity diagnosis should not appear as established facts.
