# GauGal comparison, iteration 1: material recovery, forward check, GauGal on TG-002

Prepared 2026-11-01 from a design discussion with the user. Execution and
changed priorities are recorded in the dated amendments below.
Experiment IDs: **MR-001** (BEM material recovery), **FW-001** (forward check,
MoM as the classic baseline), **GGB-002** (GauGal on TG-002). GGB-001 is the
earlier three-cylinder comparison kept in `~/Gau-Gal/docs/iterations/GGB-001/`.

## Questions

1. **MR-001.** Can the BEM fit recover the object's contrast together with its
   boundary on TG-002, starting from a contrast that does not use the truth?
2. **FW-001.** On TG-002 shapes, how accurate and how costly are MoM, GauGal's
   forward operator and the BEM forward solve, measured against the sealed
   reference fields? Which GauGal lattice is accurate enough to use?
3. **GGB-002.** On the same TG-002 data, how do GauGal and the BEM fit compare
   in boundary accuracy, image scores, field fit and time?

The report is a fair, two-sided note for Haibing that could later become a
comparison section of a paper. It states what information each method used.

## User decisions (2026-11-01)

- Report reader: Haibing; fair and two-sided. MoM is the forward baseline, not
  a third inverse method.
- Work and results live in this `organised` worktree. GauGal is imported
  read-only from `~/Gau-Gal`; nothing more is pushed to its repository.
- Scenes: TG-002 only for now. The 31 single-disk SingleTX cylinders are not run
  ("if the 31 scenes are just cylinders with different positions i think not
  now, we should stick with tg002 for now"). AU, Fresnel and MNIST are out of
  reach of a single-curve BEM fit; the report quotes GauGal's published numbers.
- Material recovery on TG-002 first, with GauGal run alongside ("if you can run
  them in parallel you could totally just run them together"). MR-001 has no
  pass mark that holds back GGB-002; if it fails, it is fixed until it works.
- Noiseless data for now ("noiseless for now"). Noise is decided later.
- GauGal uses one loss summed over all frequencies (option b), may take
  negative χ, and is tuned once on the three `circle` cases, then frozen.
- Terms follow `GLOSSARY.md`: contrast is ε_r against the background;
  susceptibility χ = ε_r − 1 is what GauGal and MoM call contrast.

## Shared data

TG-002 sealed inputs, unchanged: 10 scenes × contrasts 0.5/4/13.3, 24
source–receiver pairs on a 0.30 m ring (one receiver 0.06 m along the ring from
each source), 19 real frequencies 0.25–2.5 GHz and their damped copies, sand
background ε = 6, noiseless. Interior wavelength at 2.5 GHz: about 69, 25 and
13 mm at contrasts 0.5, 4 and 13.3.

## MR-001: BEM material recovery

**Code.** An optional contrast unknown in `solvers/bem_inverse/`, off by
default so known-contrast fits stay unchanged. The unknown is the log of the
contrast. Its Jacobian column comes from one extra matrix assembly per frequency
per iteration, reusing the existing factorization. It is active in every stage,
including the damped warm-up.

**Start.** Solve the centred 65 mm start circle once at a tiny contrast at the
lowest damped frequency, then scale that response to best fit the data. This is
one solve and one least-squares number, not a search. The estimate is recorded
before fitting.

**Runs.**

| Run | Cases | What | Expected |
|---|---|---|---|
| R1 control | all 30 | Known-contrast fit, current default (`modal_muller` + `spectral`) | About 26/30 recovered, as in PC-001 M1 (which used `certified_spectral`); aphex ×3 and hook 13.3 fail. About 17 min summed. |
| R2 material recovery | all 30 | Same fit plus the contrast unknown, weak-scatterer start | See below |
| R3 near-truth start | R2 failures only | Start at true contrast × 1.2 | Tells a bad start apart from a fit that cannot recover material |

**Expectations for R2.**
- The start estimate should land on the correct side of 1 in every case. Its
  size will be biased by the area mismatch between the start circle and the
  target. At contrast 13.3 the object already resonates at 0.25 GHz (interior
  size about 2.3 radians), so that estimate may be far off.
- Contrast 0.5 and 4: likely to recover the same cases as R1.
- Contrast 13.3: the main risk. Contrast and size can trade against each other,
  and resonances make the loss along the contrast direction bumpy.
- Time: likely 1.2–2× R1 per case, from the extra assembly and any extra
  iterations.

**Analysis.** Per case: recovered under the unchanged TG-002 limits, RMS,
Hausdorff upper bound, final contrast error, time against R1. Start estimate
against truth. The contrast path through the stages: when it settles, and
whether its error follows the area error.

**Checks before R2.** With the option off, `circle__c0.5` reproduces its R1
result. One finite-difference check of the new Jacobian column.

## FW-001: forward check (MoM baseline)

Rasterise each true shape and solve the forward problem with MoM (2D-MOM-ESI) and with GauGal's operator. Compare both with the sealed reference fields at all 19 real frequencies. The sand background is handled by rescaling frequency so the background wavenumber matches.

| Run | What | Expected |
|---|---|---|
| F1 MoM | Cell sizes 4, 2 and 1 mm, 30 cases × 19 frequencies | Error falls roughly in step with cell size; worst at contrast 13.3 and 2.5 GHz. Cost grows with the cube of the cell count; 1 mm is the largest dense size. |
| F2 GauGal operator | Two or three lattice spacings | Similar trend. The default 56 lattice (about 3.6 mm over a 0.2 m box, about 3–4 points per interior wavelength at 13.3) should be clearly too coarse at the top frequency. |
| F3 BEM | Reuse recorded TG-002 qualification and endpoint numbers | No new runs; the BEM solve is near round-off against the reference. |

**Analysis.** Error against unknowns and against time for the three forward
solvers, per contrast. GauGal's lattice: the smallest with at most 1% forward
error at every frequency it uses. If none fits the GPU, the top frequencies are
dropped for GauGal and the report says so.

## GGB-002: GauGal on TG-002

**Code** (in this worktree, GauGal untouched apart from the χ lower limit):
- A TG-002 data builder: positions, the 24-pair mask (`receiver_mask`), the
  background rescaling, and a field-scale check on `circle` against the
  sealed data.
- A multi-frequency loop (about 100–150 lines): it copies GauGal's update loop
  and sums the gradient over the 19 real frequencies, each frequency keeping its
  own field warm starts. Each frequency is weighted by its data energy, so every
  frequency's relative misfit counts equally, as in TG-002's residual limit.
- The χ lower limit moves from 0 to −0.9 at its three clip points.
- GauGal gets no damped data; BEM's damped warm-up is reported as extra
  information BEM used.

**Runs.**

| Run | What | Expected |
|---|---|---|
| G1 tuning | At most 12 settings (smoothing weight, step size, Gaussian width; one common χ upper limit) on `circle__c0.5/c4/c13.3`, one shared setting chosen by mean image RRMSE | A usable setting for 0.5 and 4; 13.3 may have none. |
| G2 all cases | The frozen setting on all 30 cases; the circle cases are marked as tuning cases | See below |

**Expectations for G2.**
- With 24 numbers per frequency (456 in all) against tens of thousands of
  unknowns, the smoothing penalty does most of the work.
- Contrast 0.5 and 4: blurred objects at about the right place and size.
  Thin and sharp features (aphex strokes, cog teeth, cross corners, the
  c-shape cavity) are lost. Boundary RMS of several mm, so TG-002's 1 mm
  limit fails.
- Contrast 13.3: likely to fail. The iterative forward solve may not converge
  within its 100-iteration cap at χ = 12.3, and strong multiple scattering
  makes the loss nonconvex.
- Field residual well above BEM's 0.003. Each iteration costs 19 forward and
  19 adjoint lattice solves, so minutes per case.

**Scores, both methods.** GauGal's image scores (SSIM, RRMSE, PSNR, contrast
SNR) on one shared grid, with the BEM curve filled in; field residual per
frequency; boundary RMS and Hausdorff with GauGal's image traced at half its
peak χ; TG-002 recovery limits; contrast estimate (GauGal: mean ε_r inside
the traced boundary); fit time. Timed runs have the machine to themselves.

## Order

1. Now, no new code: R1.
2. In parallel: the MR-001 contrast unknown; the GauGal TG-002 builder and
   multi-frequency loop; MoM rasterisation and rescaling.
3. F1 and F2, which set GauGal's lattice; then G1 and G2.
4. R2 once its code passes the two checks; R3 only on R2 failures.
5. Report `report.md` in this folder: forward figure, MR-001 table, method
   comparison table, gallery (truth / BEM / GauGal), and what each method used.

## Deferred

- A BEM arm without the damped warm-up, real data only, to match GauGal's data.
- Noise (5% complex Gaussian, seed 1000, was agreed for a noisy stage).
- The 31 single-disk cylinders and GauGal's own datasets.
- Material recovery stays a research option until R2 succeeds; the benchmark
  default is unchanged.

## Amendment 2026-11-02: MR-001 R4, contrast held in the warm-up

**Evidence.** R1 26/30. R2 (weak-scatterer start) 22/30: all 18 control
successes at contrasts 0.5 and 4 recover with contrast within 1.4e-6, but only
4 of 8 at 13.3. In asymmetric, cog, cross and peanut at 13.3, the contrast climbs
from a start of 1.2–1.5 to 157–328 inside `warmup_025_damped`; the fit later
fails numerically. R3 (start 1.2 × truth) recovers all four, and hook 13.3 too.
The warm-up data barely constrain contrast at 13.3: R2's asymmetric warm-up
reached a lower loss at contrast 185 (7.4e-3) than R3's at 9.4 (1.3e-2). In R2,
paths that drifted to about 20 (kite, hook) were pulled back in later stages.

**Hypothesis.** The single 0.25 GHz damped frequency cannot identify a dense
object's contrast, so the warm-up wanders along a flat valley. Holding the
contrast at its weak-scatterer start during the warm-up only, and freeing it
from `stage_1_damped` onwards, where more frequencies constrain it, removes the
runaway.

**Changed condition.** Contrast held during `warmup_025_damped`. Everything else
as R2, including the truth-free start.

**Runs.** R4: all 30 cases, one run (about 10 minutes).

**Stopping.** Adopt R4 as the material-recovery arm if it recovers all 18
contrast-0.5/4 control successes, at least 3 of the 4 contrast-13.3 runaways,
and keeps R2's 4 contrast-13.3 successes. Otherwise record it, report R2 and
R3 as MR-001's answer, and allow at most one more follow-up under a new dated
amendment.

**R4 outcome (2026-11-02).** 20/30; the stopping rule is not met. Contrast 13.3
recovered 3 (circle, c_shape, star; R2 had 4), and `kite__c4` was lost. Holding
the low start contrast in the warm-up leaves it too low for the later stages,
which fail numerically. The hypothesis is rejected. MR-001's answer is R2 with
R3: truth-free material recovery works at contrasts 0.5 and 4; at 13.3 it
needs a start near the truth. R2 is the material-recovery arm for GGB-002.
No further MR-001 follow-up is run under this amendment.

## Amendment 2026-11-02: FW-001 sweeps the Gaussian width

**Evidence.** Smoke tests on `circle__c4`. With the lattice on the pixel grid
(51 on 51), GauGal's operator matches MoM at the same 4 mm cells (9.4e-4 at
0.25 GHz, 12.8% at 1.38 GHz; MoM 9.4e-4, 12.6%), so the adapter is right. On a
lattice coarser than the 1 mm pixel grid, the released width (0.35 × lattice
spacing) leaves gaps between Gaussians: a 51 lattice gives 3.6% at 0.25 GHz and
48% at 1.38 GHz. Width 0.7 gives 6.8e-4 and 3.2%. The released case had lattice
56 on 64 pixels, where the narrow width is harmless. The iterative forward
solve often stops at its 100-iteration cap.

**Changed conditions.** F2 runs lattices 51 and 101 at widths 0.7 and 1.0, and
the pixel-grid lattice 201 at the released 0.35, all on 201 pixels, at five
frequencies (0.25, 0.75, 1.25, 1.75, 2.5 GHz), all 30 cases. The forward check
raises the iteration cap to 2000 so discretisation error is measured on its
own; iteration counts are recorded. The chosen lattice and width then run all
19 frequencies to set GauGal's frequency cutoff (≤ 1% at every frequency used).
F1 (MoM) runs as planned. G1 tunes around the chosen width; the inverse keeps
GauGal's released cap of 100 with warm starts.

**Runs.** F1: 3 cell sizes × 30 × 19. F2: 5 settings × 30 × 5, then 1 × 30 × 19.
F1 runs on the CPU while F2 uses the GPU; their times are reported as measured
under that sharing.

## User decisions 2026-11-02: slider default, forward check paused

The user asked: "thought modal muller plus slider update fixed all tg002
scenes?" The records show the slider ran on five TG-002 cases only (hook c13.3
recovered; aphex c13.3 reached 0.017 mm RMS but failed the final Jacobian
check; no 30-case campaign). The user then said: "change the default update to
slider. then pause forward verification with mom or whatever thats supposed to
do."

- The benchmark CLI default geometry update is now `slider`; `spectral` stays
  available. R1–R4 above used `spectral`.
- FW-001 is paused: F1 (MoM) stopped after 3 cases and F2 (GauGal operator
  sweep) after 7. Their per-case files are complete and the commands resume
  from them. GGB-002 waits.
- The user had expected only BEM material-recovery runs; the forward checks had
  been started on the reading that the two tracks could run together.

## Amendment 2026-11-02: MR-001 with the slider (S1, S2)

**Question.** With the slider default, how many TG-002 cases does a
known-contrast fit recover, and does truth-free material recovery keep them?

**Runs.** S1: known-contrast control, all 30 cases, CLI defaults (`modal_muller`
+ `slider`), one worker, single-threaded BLAS. S2: material recovery with R2's
weak-scatterer start, settings copied from S1. One run each.

**Expected.** S1 recovers hook c13.3 in addition to R1's 26, if the GU-002/PS-003
result carries over; aphex may still fail the final Jacobian check. S2 should
match R2 at contrasts 0.5 and 4; at 13.3 the start problem seen in R2 is not
changed by the geometry update.

**Stopping.** Report S1 and S2 against R1 and R2. Any further fix of the
13.3 start needs a new dated amendment.

**S1 outcome (2026-11-02).** 25/30 (8 / 9 / 8). Against R1 (`spectral`): gains
hook c13.3 (RMS 0.0002 mm); loses hook c0.5 and cog c13.3, both ending in
"production evaluation failed at candidate state". Aphex ×3 still fail (aphex c4
reaches 0.34 mm but fails the final check). Summed time 607 s, median 13.7 s.

**S2 outcome (2026-11-02).** 23/30 (9 / 9 / 5); R2 had 22. Recovered contrasts
are within 8e-5 of truth. Material recovery recovers aphex c0.5 (RMS 0.068 mm),
which no known-contrast fit has recovered, plus hook and peanut at 13.3. Circle
c13.3 fails only the final Jacobian check (0.0026 against 1e-3; shape RMS
7.6e-6 mm, residual 5e-7), as PS-003 saw for slider on circle c4 and aphex
c13.3. Asymmetric and cross at 13.3 run away (to 123 and 74) from starts of
1.45 and 1.21, the start problem seen in R2. Hook c0.5 and cog c13.3 fail as
in S1. Median time 1.28× S1.

## Amendment 2026-11-02: S3, remove the default log-expansion degree cap

**Question.** Does removing the 4,000-term cap let the two S1 cases that hit
it complete and recover under the unchanged TG-002 criteria?

**User request.** "delete that check, try again. is gpu free?" This follows
the discussion of the 4,000-term cap. The separate positive-lower-bound
check and the accuracy target remain unchanged.

**Evidence.** S1 hook c0.5 and aphex c0.5 stop on that cap. Cog c13.3 and
aphex c4/c13.3 instead fail the separate lower-bound check. Replaying hook's
saved trial curve through CPU `ModalGeometry(curve, 128)` reproduced the
4,000-term error with beta/Lambda = 1.52e-5 before editing the code.

**Hypothesis.** The cap may be preventing an otherwise computable forward
solve. If so, allowing more terms should let the fit proceed. Alternatively,
the longer expansion may still fail the lower-bound check or a later fit step.
This tests the user's specified change; no broader diagnosis or repeated
baseline runs are needed.

**Changed condition.** CPU and CUDA modal geometry now have no default degree
cap, including `ModalSettings`. An explicitly supplied cap remains supported
for optional certificate callers. The 1e-16 series target, coefficient window,
lower-bound check, geometry update and numerical-stop handling are unchanged.

**Runs.** S3: hook c0.5 and aphex c0.5, one known-contrast fit each from the
same centred start, `modal_muller` + `slider`, localization none, one worker,
four frequency threads and single-threaded BLAS. Fresh directory
`results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap/`.
Wait for the existing S2 GPU job to finish first. Keep S1 untouched.

**Stopping and comparison.** Record both outcomes, failure details, recovery
scores and runtime against S1. Stop after these two cases: the other three S1
failures did not hit this cap. Use a 15-minute outer time limit for the pair
and preserve partial files if it is reached. These runs are the relevant
code/result validation; commit and push the change and evidence afterward.

**S3 outcome (2026-11-02).** Both runs finished; one recovered. Hook c0.5 now
passes with RMS 0.00419 mm, Hausdorff upper bound 0.0473 mm and maximum field
residual 3.22e-7. It took 18.20 s, versus S1's early stop at 2.42 s. Aphex c0.5
passes the old degree limit but then fails the separate positive-lower-bound
check (coefficient residual 1.98), at the same stage and accepted curve as S1:
RMS 5.975 mm, 11.10 s versus 8.36 s. The GPU was free of compute jobs before
S3 started. The run command exited 0 and retained both result files.

**Validation and conclusion.** The saved hook trial also succeeds in the CPU
implementation at 4,354 terms with the unchanged 1e-16 series target; receipt
in `S3_slider_no_log_cap/cpu_replay.json`. The cap was the obstacle for hook,
but removing it does not resolve aphex's lower-bound failure. Combining S1
with these two replacements gives 26/30; this is not a new full 30-case run.
Cog c13.3 and aphex c4/c13.3 were not rerun because their recorded failures
were lower-bound failures, not degree-cap failures.

## Amendment 2026-11-02: S4, continue with the sampled log interval

**Question.** Do the four remaining known-contrast failures recover when an
inconclusive positive-lower-bound calculation no longer stops the forward solve?

**User request.** "try without thatcheck now", referring to the A1 positive
lower-bound refusal in cog c13.3 and aphex c0.5/c4/c13.3.

**Evidence and hypothesis.** S1/S3 stop these four fits on a trial curve with
coefficient residuals 1.41, 1.98, 2.04 and 2.79 respectively. These bounds are
inconclusive. Continuing with the already-positive sampled interval may let
the optimizer progress. The final field and Jacobian comparisons will still
test the returned fit under the original recovery criteria.

**Changed condition.** On CPU and CUDA, when the coefficient calculation
returns a nonpositive lower bound, retain the interval whose lower endpoint
is half the sampled minimum and use its already-computed logarithm. Do not
substitute a negative endpoint into the square root. Record this interval as
sampled and unverified; retain the failed bound and residual in diagnostics.
Positive coefficient bounds still refine the interval as before. The optional
`certified_spectral` method still requires its own positive certificate.
No degree cap, as in S3; keep the series target, finite-value checks, geometry
checks, trial acceptance, stage policy and final recovery criteria unchanged.

**Runs.** S4: cog c13.3 and aphex c0.5/c4/c13.3, one known-contrast fit each,
from the prescribed centred start, no localization, modal_muller + slider,
one worker, four frequency threads and single-threaded BLAS. Fresh directory
`results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval/`.
The GPU has no compute jobs before preparation. Preserve S1 and S3.

**Validation and stopping.** Reproduce the saved S3 aphex c0.5 trial before
editing; replay it afterward on CPU and CUDA to check both the sampled fallback
and finite logarithm coefficients. Run the four fits with a 15-minute outer
time limit. Report all outcomes, final errors and remaining failure reasons;
stop after these runs and commit and push code, plan and all evidence.

**S4 partial outcome (2026-11-02).** The saved aphex trial returns finite CPU
and CUDA logarithms using the sampled interval; their relative difference is
9.75e-14. Cog c13.3 completes in 72.64 s but is not recovered: RMS 0.481 mm,
Hausdorff upper bound 1.323 mm, maximum data residual 0.246 (limit 0.003), and
the final field/Jacobian comparisons fail. Aphex c0.5 passes its earlier stop
and reaches fixed_M25, but the campaign's 900 s outer limit then expires
(exit 124). Preserve its stage files and last checkpoint; there is no final
recovery result. Aphex c4 and c13.3 were not reached. The GPU was released.

### S4 continuation: finish the two unstarted cases

**Question.** Do aphex c4 and c13.3 recover with the same sampled-interval
fallback? The timed-out c0.5 case cannot answer this for the queued cases.

**Conditions and runs.** No numerical or optimizer changes from S4. Run the
two unstarted cases once each in separate directories under
`MR-001/S4b_slider_sampled_log_interval/`, with a 300 s outer limit per case,
sequentially. This prevents one slow case from consuming the other's time.
Do not repeat cog c13.3 or aphex c0.5. Preserve any timeout evidence, compare
all four attempted cases together, then stop and commit and push the results.

**S4b outcome (2026-11-02).** Aphex c4 completes in 149.46 s but is not
recovered: RMS 0.2078 mm, Hausdorff upper bound 1.0025 mm, maximum data
residual 0.003799 (limit 0.003), and maximum final Jacobian discrepancy
0.00536. Aphex c13.3 reaches fixed_M85 before its 300 s limit (exit 124);
preserve its stage files and checkpoint, with no final recovery claim.
Together S4/S4b give two completed failures and two timeouts, no additional
confirmed recoveries. The positive-bound refusal is removed as requested,
but this experiment does not establish a recovery improvement.

## User priority 2026-11-02: full BEM–GauGal comparison by morning

**Question.** How does the best supported BEM implementation compare with
GauGal across all 30 TG-002 cases, including unsuccessful fits?

**User requirement.** "i expect to see full comparison of bem (the best
version) vs gaugal on all 30 scenes by morning. is hti written in the plan"
The original GGB-002 section included all 30 cases and a report, but no morning
deadline. At 02:11 London time, BEM full campaigns R1/R2/S1/S2 are available;
GauGal has no inverse results yet. S4b's two final BEM retries are running.

**Target.** Deliver `report.md` in this folder by 08:00 London on 2026-11-02
(working interpretation of "morning", subject to the user's correction).
The report must include every case, images, shared image and boundary scores,
field residuals, contrast estimates, runtime, and explicit failures/timeouts.
All-case coverage does not imply all-case recovery. Do not claim a completed
comparison until both methods have an outcome for every case.

**BEM selection.** Finish S4b, then stop further BEM tuning for this delivery.
Use saved full-campaign evidence to select the strongest supported setting,
with a fixed selection rule stated before GauGal results are inspected.
Working proposal: report supplied-contrast BEM and truth-free material recovery
separately, since they use different information; the user has been asked
which should be the main comparison. Do not silently mix per-case winners or
use truth-assisted R3 starts as truth-free material recovery.

**User confirmation.** "Both BEM versions, clearly separated." The report
will contain supplied-contrast BEM, truth-free material recovery and GauGal
for every case. Target time remains 08:00 London.

**GauGal priority.** Proceed to GGB-002 without resuming the broad MoM sweep.
Reuse the seven saved GauGal forward cases to inform a bounded settings and
runtime check. Record the concrete settings, tuning count, frequency choice,
iteration count, selection rule and remaining time budget before starting
the inverse runs. Run a timed circle case first, then freeze one shared
configuration after circle-only tuning and attempt all 30 cases. Report
forward-model limitations and any frequency reduction explicitly. The earlier
"GGB-002 waits" statement is superseded by this delivery priority.

**Feasibility.** The deadline is a target, not a measured runtime guarantee:
no GauGal inverse timing exists yet. Use that first run to choose a bounded
campaign that fits the remaining time. If the measured cost prevents all 30
from finishing, report this immediately and preserve the actual coverage;
do not present missing cases as completed results.

### GGB-002 T0: measure the full-frequency inverse runtime

**Question.** Can a 19-frequency GauGal fit fit the remaining overnight budget,
and does the adapter produce finite updates at its initial shared settings?

**Evidence.** The saved seven-case forward sweep has no tested lattice within
1% at 0.75 GHz and above for every tested case. Its best 0.25 GHz worst-case
errors are 0.727% (51/.7), 0.333% (101/.7), and 0.131% (201/.35). Narrowing
GauGal to 0.25 GHz would discard 18 of the 19 real frequencies. For the
morning comparison, retain all 19 and report this forward-model limitation;
the previous 1%-before-G2 rule is replaced by measured-error disclosure.
No broad forward sweep or MoM continuation is planned.

**Run.** One circle c4 timing fit, lattice 51, Gaussian width .7 times spacing,
201-pixel quadrature, TV lambda scale .5, step 1, susceptibility bounds
[-.9, 15], 10 outer iterations, released 100-iteration inner-solve cap,
all 19 real frequencies. Fresh `GGB-002/T0_timing/`; 600 s outer time limit.
This is a timing and finite-output check, not a final reconstruction.

**Decision afterward.** Record build and iteration costs and the actual
loss trajectory. Then preregister the bounded circle tuning and frozen
all-30 run using the remaining time to 08:00. Do not infer GauGal's final
quality from a ten-iteration timing fit. Preserve and commit this result.

### Frozen BEM report selection, before any GauGal inverse result

Use slider for both BEM arms, following the user's default-method decision.
For supplied contrast, use S1 with the two S3 replacements: removal of the
degree cap changes the path only for the two cases that previously hit it.
Both replacements are included, not just the successful hook case. This gives
26/30 recoveries, tying spectral R1's 26/30. Report the reuse explicitly; do
not describe it as a fresh complete campaign. S4/S4b are diagnostic variants,
not the selected arm: they add no confirmed recoveries and introduce timeouts.

For truth-free material recovery use S2, the strongest completed all-30 arm
(23/30, versus R2's 22 and R4's 20). Keep its recorded settings and outcomes;
do not include R3's truth-assisted starts. The supplied-contrast and material
arms consequently have different numerical versions, which the report must
state. Do not change these selections after seeing GauGal results.

### GGB-002 G1/G2 overnight budget, recorded after T0

**Question.** Which of three common step sizes gives the best circle
reconstructions, and how does that frozen setting perform on all 30 cases
within the morning delivery budget?

**T0 outcome.** Circle c4 with 19 frequencies built in 13.42 s and used
50.12 s for 10 iterations. Its final maximum residual was 1.084 and image
RRMSE 0.3346; it was a timing fit, not converged. CPU/GPU memory fit the
selected 51 lattice. At 5 s per iteration, 300 iterations on 30 cases would
take over 12 hours, excluding tuning. The morning run therefore uses a
smaller declared iteration budget rather than claiming the original 300.

**G1.** Three settings: step sizes 1, 4, 16. Fix lattice 51, sigma scale .7,
lambda scale .5 and all other T0 parameters. Run each on the three circle
contrasts, 30 iterations each, maximum 170 s of optimization and 210 s outer
wall time per fit. Select one shared setting by lowest mean image RRMSE
over all three circles; missing or nonfinite images score infinity. If every
setting is incomplete, prefer the one with most finite scored circles, then
lowest mean RRMSE among those, and disclose that fallback. Maximum nine fits.

**G2.** Freeze the chosen setting. Run all 30 cases with all 19 frequencies,
80 iterations maximum, 400 s optimization allowance and 480 s outer limit
per case, sequentially. Warm starts remain internal to each case. Circle
cases are rerun under the same final budget and marked as tuning cases.
Save finite intermediate images and measured fields every ten iterations,
so an interrupted fit can be reported as partial rather than disappearing.
Record actual iteration counts, stop reasons and failed-solve information.

**Time bound and delivery.** G1 is at most 31.5 min and G2 at most four hours
of subprocess wall time. Start immediately after the T0 result is preserved;
reserve the remaining time before 08:00 for scoring and the report. Do not
add further tuning after G2 starts. A time-limited image is a partial result,
not convergence or TG-002 recovery. Score the saved images and retain missing
or failed cases explicitly in the full 30-row comparison. Commit and push
each completed run's results and the final report automatically.
