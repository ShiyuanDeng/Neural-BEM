# Iteration 15 plan — SC-034: SPD comparison fitter with the legacy single-object controls

- **Approval status:** `APPROVED`. This is the user's direction of 2026-09-24,
  quoted in the [assessment](02_proposals/01_spd_legacy_controls.md): "if those
  missing criteria seems convincing to you then add them to our spd here, so at
  least we are not fixing sc toward a solved issue." The assessment finds five
  controls convincing, and this contract adds them and measures the result.
  SC-033 remains `PROPOSED — NOT APPROVED FOR EXECUTION`.
- **Execution status:** `COMPLETE` (2026-09-24). 18/18 fits; qualification replay PASS. H1 **PASS**.
  Results: [SC-034 bundle](../../../../results/validation/shape_continuation/SC-034-spd-legacy-controls/README.md),
  [iteration 16](../iteration_16/01_results.md). The ablation favours arm L over LS; the recommended
  amendment (adopt L) awaits the user's decision.
- **Owner:** Claude. **Reviewer:** unassigned.

## Question and hypotheses

With the legacy single-object controls restored, does the SPD comparison
fitter recover the star-shaped single objects that SC-030's SPD arm failed?
And where does it stand against the hybrid on the six SC cases?

- **H1 (adoption).** Arm LS (ladder + safeguards) completes all four stages
  on circle and star with no hard stop, symmetric RMS ≤ 0.05 mm on both, and a
  qualified endpoint training cross-resolution. 0.05 mm is the legacy level:
  SC-018's conservative bound is 0.031 mm.
- **H2 (attribution, descriptive).** On circle and star, the ladder alone (L)
  recovers, as the diagnostic's 4/6/9/17 schedule did. The controls alone at
  K17 (S) improve on SPD-008 without necessarily recovering.

## Arms (the SPD fitter in all; nothing else varies)

| Arm | Cartesian K by stage (radial orders) | `StepSafeguards` |
|---|---|---|
| SPD-008 (reference, not rerun) | 17/17/17/17 (16) | none — SC-030 results |
| L | 4/6/8/10 (3/5/7/9 = hybrid M) | none |
| S | 17/17/17/17 | m⁴ ridge 1e-4, damping floor 1e-6, 2 mm normal trust region, Armijo 1e-4 |
| LS | 4/6/8/10 | as S |

The stage band grows by zero padding, which keeps the physical curve.
Hybrid reference values are SC-030/SC-029 R0 (bitwise the same) and SC-032 R2.
They are not rerun.

## Controls (identical to SC-030's SPD arm)

Six cases, observations, start circle ((0.48, 0.52) m, 65 mm) and truth files.
Cumulative 0.5/0.75/1.0/1.25 GHz with quotas 1000/1250/1750/4000 units and 22
iterations per stage. 512/1024 nodes. Compiled runtime, real-Bessel kernels,
certified geometry validation. The 8 mm radius certificate, the refined
acceptance and cross-resolution checks, and the SPD per-coefficient clips.
Per fit: 8,012 units and 3,600 s. Scoring is SC-030's worker scoring
(symmetric RMS, Hausdorff upper bound, 19-frequency catalog residual,
training cross-resolution). The optimizer never sees truth.

## Pre-dispatch qualification

1. `pytest/sdf_inverse/test_step_safeguards.py`: gauge directions are unit
   radial harmonics; the normal-move operator is exact; inert safeguards
   reproduce the historical path; accepted steps respect the bound, floor and
   Armijo. Existing SPD suites (`test_top017`, `test_spd001/002/005/006`,
   `test_refined_feasibility_guard`, `test_top016_optimizer_hooks`,
   `test_feasible_finite_differences`, `test_radial_topology`) must pass. The
   TOP-017 interface pin gains `step_safeguards` with default `None`.
2. **Default-path replay:** SC-030's SPD circle, rerun through `spd_fit` on
   the modified code, reproduces its recorded trajectory digest exactly.
3. **Plumbing smoke** (outcome not used): LS on the circle with a stage-1
   quota too small to finish, run in scratch space, to confirm that records
   and `safeguards.jsonl` are written.

## Decision rules (fixed before any outcome)

- **H1 passes:** LS becomes the SC track's SPD comparison reference
  ("SPD-L"), replacing SPD-008 for recovery comparisons. SPD-008 stays the
  timing/execution reference it was qualified as.
- **H1 fails:** SPD-008 remains the reference and the failure is recorded.
  The next step is a per-control ablation, which is proposed, not run.
- **Per case, for the star-shaped hard cases (kite, peanut)** against hybrid
  R0:
  - *solved by the restored baseline*: LS completes, RMS ≤ 0.05 mm and the
    endpoint is qualified;
  - *baseline better, not solved*: LS RMS is below R0's;
  - *open*: otherwise.
  SC work on a case must then be measured against the better of LS and R0.
- **C and hook** are not star-shaped, so SPD's chart cannot represent them.
  Their SPD endpoints are reported as representation-limited, never as
  evidence about the step controls.
- GM ratios (0.01 mm floor) of LS/R0, LS/R2 and LS/SPD-008 over all six cases
  and over the four star-shaped cases are **descriptive**; no adoption bar is
  attached to them.
- Hard stops are outcomes. A budget- or iteration-limited path is reported as
  inconclusive, not as a failure of the controls.

## Metrics

Status and reason; per-stage outcome, accepted steps and units; the endpoint
metrics above. Per safeguarded stage: how often the trust region binds, the
damping range, and Armijo refusals. Descriptive mechanism for circle, star,
kite and peanut: the largest accepted move and the radial RMS above mode 5
along stage 1.

## Budget

18 fits (3 arms × 6 cases), 9 concurrent single-thread workers. At most 3 h
campaign wall, 4,050 s outer limit per worker, ≤ 144,216 inverse units (the
per-fit cap × 18). The qualification replay takes about 3 minutes. The timing
of concurrent workers is an observation, not a cost claim.

## Artifacts

`results/validation/shape_continuation/SC-034-spd-legacy-controls/`: the
manifest (source, input and plan hashes), the approved plan copy, the
qualification, `runs/<arm>/<case>/` (configuration, stage records,
`safeguards.jsonl`, result), campaign logs, and `report.py` with tables and
figures (figures allow-listed in `.gitignore`). Driver:
`experiments/shape_continuation/spd_safeguards.py`.
