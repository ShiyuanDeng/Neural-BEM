# Run BRG on TG-002 shapes with plane-wave data

## Status and authority

Baseline half authorized by the coordinator on 17 November 2026, after
acceptance of activities 02 and 03. No BEM run or solver edit is authorized
here. The separate BEM coordinator owns frozen plane-wave TG-002 data and
all BEM work. The two BEM sections below are not executed in this activity.

The 37-frequency sweep, floor(10k) radius-10 layout, geometry wrapper,
public settings and frozen scoring are approved. Frozen BEM-side data do
not yet exist: tonight uses BRG-generated data, labelled **provisional**.
When frozen data arrive, compare fields using the threshold below and rerun
only cases exceeding it. The request is one machine-readable JSON file,
including coefficients and hashes, rather than a second data specification.

Pilot: asymmetric eta=4, BRG data and BRG inversion only. If total case time
is at most 15 minutes, continue the other 19 without another question.
Caps: one hour per case and four hours elapsed for the whole campaign,
including data, scoring and retries. At most three BRG MATLAB processes;
keep at least 14 GB available and reduce concurrency when needed. CSI has
three concurrent fits; record overlap. Commit and push each completed batch.
No k=30 paper resume is authorized during CSI's overnight campaign.

Pilot completed in 771.81 seconds on 17 November, so the other 19 cases
started under the approved automatic continuation rule. A Python 3.10 hash
writer error occurred after MATLAB and scoring; its log and receipt repair
are retained. No numerical pilot rerun was needed.

The user chose this as the main BRG table on 17 November: “for brg i think
we should compare it on my tb 002 scenes, its more variety?”, then “yeah”.
The six paper cases remain a check of BRG on its own examples. Activity 03's
explicit CPU plane-wave/table adapter supplies the BEM path for this table.

## Question and cases

How do BRG and our default modal Müller + slider inverse compare on the
same broader set of shapes, start, contrast and plane-wave observations?
Save raw area error, field residual, contrast error and separate times;
do not introduce a new success cutoff or exclude failed shapes.

Use all ten frozen TG-002 shapes at eta=0.5 and 4: **20 cases**. Exclude
13.3 as for the other baselines. Shapes are circle, kite, peanut, star,
asymmetric, c_shape, hook, cross, cog and aphex_twin. Preserve each frozen
translation, rotation, Fourier band and historical smoothing. Use the
benchmark's saved truth coefficients, checked against its scene definitions.
Do not rebuild an unsmoothed polygon or recenter each target.

Sources: [benchmark README](../../../../experiments/benchmark/README.md),
[scene definitions](../../../../experiments/benchmark/scenes.py),
[frozen scoring](../../../../experiments/comparison/scoring.py), and
[activity 03 result](../03_adapt_bem_to_brg_data/results.md).

This is **TG-002 shapes with BRG-style data**, not the sealed TG-002 data.
BRG's released inverse accepts plane waves. Sealed TG-002 uses 24 paired
point sources/receivers. The new observations must therefore be generated;
no result in this table should be described as running BRG on sealed data.

## Scaling and the one start

Subtract the fixed scene centre (0.5,0.5) m and divide every length by
0.065 m. The centred 65 mm start becomes BRG's unit disk at the origin.
Target offsets remain present. The original benchmark coefficients use a
0.05 m length unit, so multiply them by 0.05/0.065; do not shift their
constant coefficient again. Receivers use the same new unit.

Eta is the squared interior/exterior wavenumber ratio, directly 0.5 or 4.
BRG gets q=sqrt(eta), transk=[q*k,k], and equal-density a=b=[1,1].
The data are unit-amplitude exp(+ik d.x) incident waves, finite-range
**scattered** fields, outgoing Hankel first kind, negative time convention.
No fitted phase, gain or far-field normalization enters the handoff.

## Frequency choice

Use the benchmark's actual background constants: mu=4*pi*1e-7,
epsilon=6*8.854187817e-12. Dimensionless k is physical exterior wavenumber
times 0.065 m. The 19 sealed frequency labels map as follows; this reads
only their frequency definition, not their measured fields.

| GHz | k | GHz | k |
|---:|---:|---:|---:|
| 0.250 | 0.834234519 | 1.500 | 5.005407111 |
| 0.375 | 1.251351778 | 1.625 | 5.422524371 |
| 0.500 | 1.668469037 | 1.750 | 5.839641630 |
| 0.625 | 2.085586296 | 1.875 | 6.256758889 |
| 0.750 | 2.502703556 | 2.000 | 6.673876149 |
| 0.875 | 2.919820815 | 2.125 | 7.090993408 |
| 1.000 | 3.336938074 | 2.250 | 7.508110667 |
| 1.125 | 3.754055334 | 2.375 | 7.925227926 |
| 1.250 | 4.171172593 | 2.500 | 8.342345186 |
| 1.375 | 4.588289852 | | |

The original spacing is 0.417117259 in k, larger than BRG's published 0.25.
**Approved single sweep:** insert one midpoint in each original interval.
This gives **37 frequencies**, k=0.834234519 to 8.342345186 with spacing
0.208558630, preserving all 19 TG-002 labels and the exact physical range.
Compute values from the constants, not the rounded numbers printed here.

This gives BRG continuation steps no coarser than its own published rule,
without extending the measured bandwidth or running a second sweep. It is
an adapted TG-002-shape experiment, not a reproduction of a paper example.
No frequency-grid tuning or alternate sweep is planned.

## BRG data, geometry and inversion

At each k use floor(10k) equally spaced incident directions and the same
number of equally spaced receivers on the radius-10 ring, following BRG's
full-aperture rule. This ranges from 8-by-8 to 83-by-83. The receiver radius
corresponds to 0.65 m after scaling; it is not TG-002's sealed 0.30 m ring.
Generate noiseless fields with BRG's pinned forward solver and the true eta.
Data use 100 exterior points per wavelength, minimum 300 nodes, rounded
even. Save the actual counts, directions, receiver coordinates and layout.

Feed each scaled Cartesian Fourier curve through an owned geometry wrapper:
evaluate its complex Fourier series and first two derivatives at uniform
parameters; fill xs, ys, dxs, dys, ds, H, h, paramL and L, plus the public
spectral differentiation matrices Der_param and Der. Apply the same public
zero-step arclength resampling used for data in activity 02. This is input
construction, with **no change to BRG's geometry or inverse code**. Preserve
the original coefficients as the cross-solver truth and record any resampling
error. Test orientation, closure and the scaled start before generating data.

Use the activity 02 frozen public settings: min(gn,sd), Gaussian filtering,
50 iterations per frequency, 1e-5 residual/update thresholds, 70 exterior
inverse points per wavelength, band floor(3*max(k,sqrt(eta)*k)), no length
scaling, eps_curv=0.1 and minimum curvature band 20. Keep public start-of-
frequency resolution, filter sequence and zero-gradient behavior unchanged.
Use only approved upstream patches 03/04 as needed and the seven-argument
call. Save after every frequency and resume without repeating completed work.

## Cross-solver forward checks — BEM side, not executed here

For every shape and contrast, feed the **same saved BRG observations** into
our CPU table forward on the exact scaled true coefficients. Check all
frequencies that either BEM fit will use. Save the source SHA-256, row/column
errors, maximum absolute difference, full relative complex error, solve
residual and modal/cancellation diagnostics. Verify rectangular/masked layout
machinery by the retained activity 03 tests; this campaign itself uses all pairs.

Raise BEM trace/workspace resolution once at each checked frequency. Require
refinement difference <=1e-6 and BRG agreement <=max(1e-5, ten times the
measured BRG refinement error). Check BRG data on a finer grid at the largest
k for each true shape/eta, and at a failed comparison if needed. A BRG
refinement error above 1e-4 returns to the coordinator; do not silently relax
thresholds. The circle also has the independent disk-series check.

Keep series_loss=1e-9 and every current numerical check. Qualification uses
the largest passing prefix. Activity 03 showed that a fitted curve can have
a larger coefficient-based wave radius than truth: record a later fit
refusal separately from the true-shape cap. No redesign, tolerance loosening
or altered truth is proposed. A failed qualification remains a table result;
it does not justify dropping that case.

## Our BEM on exactly the same data — BEM side, not executed here

Main table: known contrast, modal Müller + slider, real frequencies only,
no localization, no warm-up, one centred unit-circle start. Extra row:
recovered contrast on the same 20 cases, using the existing weak-scatterer
initial contrast rule and MaterialUnknown, never a truth-based initial value.
The weak-start solve uses the new plane-wave table context; its scalar
formula is unchanged. Record its time separately.

CPU table mode is explicit. The paired TG-002/CUDA defaults stay unchanged.
Declare length_unit_m=0.065 and origin_m=0.5+0.5j for physical slider bounds;
geometry coordinates remain centred BRG units. Reuse the benchmark's fixed
physical fitting box, converted by Problem, rather than inferring a box from
truth. The paper adaptation's 1 m reference unit is not used here.

**Proposed BEM schedule:** use the 19 original frequency labels within the
37-frequency catalog, growing a cumulative prefix from the lowest label.
This is BEM's own schedule, requiring no interpolation. Give each active
frequency equal relative weight. Use the activity 03 explicit ragged policy,
default slider/LM controls, floor(3k) update bands, compact 2M+2 storage,
22 iterations per stage and the existing quotas; retain the 13,412-unit cap.
Trim to the largest true-shape-qualified prefix for that case. Record the
actually reached frequencies and any subsequent refusal. No tuning reruns.

Both BEM rows read exactly the saved entries available to BRG. Their use of
a declared subset is reported, as for the other comparison tables. Forward
qualification is shared by known/recovered rows; recovery at other contrasts
can still fail a numerical check and must preserve that failure.

## Frozen scoring and reporting

Import `experiments.comparison.scoring`, without editing it. Convert each
returned curve back to the benchmark's 0.05 m coefficient units before
calling its frozen score path: BRG/BEM unit-disk coefficients times
0.065/0.05. Preserve every component and apply no fitted alignment. BRG's
uniform-parameter nodes define its periodic Fourier interpolant; converting
them for the curve scorer adds no smoothing or retained-mode tuning.

Use the same 16,384 curve samples, symmetric-difference area divided by true
area, boundary distances, centroid, 201-by-201 material grid and signed
susceptibility image as table A. Use its exported functions and protocol
version. Known eta has zero contrast error by construction; recovered eta
uses the returned estimate. Keep raw metrics, failed/empty outputs and times.

The scorer's residual helper indexes only the original 19 frequency labels.
Call its geometry/material scoring with the residual fields absent, then
report plane-wave per-frequency residuals and the unchanged clean limit
0.003 separately, using the exported protocol. Never invent matching sealed
frequencies for the 18 added midpoints. This keeps table A's geometry and
material metrics exact without changing the shared module.

Report BRG data generation, BRG inversion, BEM qualification, BEM known fit,
BEM recovered fit, contrast initialization and scoring separately. Report
adapted timings separately from each solver's native benchmark timings.
These are different data from table A, so matching scoring does not make the
tables interchangeable measurements of the same inverse problem.

## Budget and execution order

**Time one case first:** asymmetric at eta=4, chosen before results because
it has several harmonics, an offset start and the higher included contrast.
Run its BRG data generation, BRG fit and frozen scoring once. Retain the
pilot in the final table. Report phase times and the 20-case projection.
If elapsed case time exceeds 900 seconds, stop and report. Otherwise continue
with the other 19 under the one-hour case and four-hour campaign caps.
No BEM qualification or inverse is performed in this baseline campaign.

Memory is checked before launch and while running. Reserve headroom for
active BRG workers rather than relying only on instantaneous free memory.
A resource stop preserves all completed frequency checkpoints; it is recorded
and counts against both limits. There is no tuning rerun. Bulk observations
remain provisional until compared with the BEM-side frozen observations.

## Commands and evidence locations

Owned commands, implemented before the pilot:

- `python experiments/baselines/brg/prepare_tg002.py`: build the single JSON
  data request, geometry inputs and geometry checks from frozen truths.
- `python experiments/baselines/brg/run_tg002.py --case asymmetric__c4`:
  generate provisional BRG data, invert, save each frequency and score.
- `python experiments/baselines/brg/run_tg002.py --campaign --detach`:
  enforce the pilot rule, budgets and memory/concurrency limits for 20 cases.

Evidence: `results/brg/tg002_shapes/2026-11-17/`; the request is
`data_request.json` there. Compact case outputs retain curves, residuals,
exit reasons, source hashes, overlap and phase times. Bulk fields, exact
states and full logs stay ignored in `local/` with command and SHA-256.
Keep at most about 5 MB per case; figures go in this activity's `figures/`.
Commit and push each batch by explicit owned paths on `organised`.

The report separates provisional BRG data, inverse and scoring times.
Cross-solver checks and both BEM rows belong to the BEM coordinator and stay
unexecuted here. No shared solver or comparison file is edited.
