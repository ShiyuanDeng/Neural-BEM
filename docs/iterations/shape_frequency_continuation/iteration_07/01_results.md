# Iteration 07 — the clean hybrid passes SPD's single-object test

2026-09-23. The user asked for the
[pipeline draft](../iteration_06/02_proposals/02_clean_pipeline_draft.md) to be
built, with a first test using SPD's policy against SPD. The
[frozen plan](../iteration_06/03_plan.md) was executed as
[SC-020](../../../../results/validation/shape_continuation/SC-020-spd-matched-hybrid/README.md)
on the existing branch. No independent review was claimed at execution.

## Outsider review added 2026-09-24

The [Codex review](../iteration_08/02_proposals/01_codex_outsider_review.md)
accepts the frozen near-truth pass and the M=32 improvement. It does not treat
them as general recovery parity with SPD. The out-of-band plateau below is
an observed local effect: finite normal moves and regauging can mix harmonics,
so “cannot reach” is not a global unreachability theorem. Matching coefficient
bounds also does not match physical step bounds across different spaces.
Exact source availability for replay and the remaining far-start comparison
are identified separately. Original measurements below are retained.

## What was built

The draft's modules now exist as code, separate from the earlier
single-frequency GN/SD path. That path and its tests are unchanged.

| Draft module | Code | Notes |
|---|---|---|
| Update strategy (default Borges) | `updates.BorgesUpdate` | Provides `prepare`, `velocities`, `measure`, `trial` and `regauge`. Coordinates are Fourier coefficients of the normal distance h in metres, in normalized arclength. Each trial samples, moves along the unit normal, refits in arclength and reports its projection error. Refusals carry a stable reason label. |
| Backend / LM | `lm_backend.fit_stage` | SPD's LM step rules: Marquardt scaling with floor 1, per-coordinate clip, 5 damping trials × 8 halvings, strict decrease, SPD's refined-margin acceptance, and a numerical-regime hard stop. Work units, stage quotas and reservations follow SPD's rule. |
| Physics | `forward.solve`, `forward.shape_jacobian` | The existing nodal Müller solver and Hadamard derivative. The Jacobian reuses the forward factorization. |
| Policy | `lm_backend.FitStage`, `FixedSchedule`, `run_policy` | A stage fixes the frequency set F, weights, M, K, N, refined N, iterations and quota. A policy returns the next stage from training-only history. Endpoint scoring is an external hook whose return value is ignored. |
| SPD bridge and harness | `spd_cases`, `spd_report` | The only modules that import SPD code. Scoring uses SPD's own scorer and Kress predictor. |

Measured correspondences with SPD:

- Package physics reproduces SPD's saved 256/512-node predictions on the
  handoff to ≤4.1e-13.
- The residual map is bitwise equal to SPD's.
- The acceptance rule equals SPD's.
- The Jacobian matches central differences through the actual trial to
  5.7e-10 in a random direction and 1.3e-8 for harmonic 16.
- SPD's recorded final score is reproduced exactly through the harness.
- The package suite passes, 113 tests including 9 new ones.

## Result

**The test passes.** The fresh SPD rerun reproduces the TOP-025 endpoint
exactly. The hybrid completes the four stages, every endpoint is numerically
qualified, and every original SPD gate passes.

| | SPD | Hybrid |
|---|---:|---:|
| Final matched Hausdorff | 0.048 mm | 0.076 mm |
| IoU | 0.9990 | 0.9974 |
| Final stage loss | 4.65e-13 | 7.00e-12 |
| Worst evaluation error | 3.6e-3 | 6.0e-3 |
| Work units | 256 | 580 |
| Elapsed, single thread | 143 s | 203 s |

The accuracy and cost gap has one measured cause. Normal error beyond
arclength harmonic 16 cannot be reached by an M=16 update. The handoff's
0.0496 mm there persists unchanged through all four hybrid stages, while
in-band error falls to SPD's level (0.015 against 0.013 mm). SPD's 33 polar
radial directions are different arclength functions on this elongated ellipse
and correct part of it (0.018 mm remains). The leftover data misfit makes LM
search weakly determined directions whose Gauss–Newton steps are nonlinear at
millimetre scale. This produced 84 non-decreasing and 50 margin-rejected
trials. The Jacobians themselves cost less than SPD's (55 units against 92).

This is the case the draft anticipated: "equal numeric mode counts in
different coordinates do not establish equivalent update spaces". The plan
predicted the out-of-band floor and its extra trial cost before the frozen
run.

## What this establishes, and what it does not

- **Establishes:** on SPD's single-object case, the clean backend reproduces
  SPD's schedule semantics and meets SPD's recovery gates. Its physics,
  normalization, acceptance and derivative agree with SPD or with finite
  differences at the stated precisions. Policy and update are separate
  objects that can be replaced independently.
- **Does not establish:**
  - recovery from distant starts or on harder targets; the handoff starts
    0.55 mm from truth;
  - any advantage of the Borges update over SPD's polar update;
  - a controlled speed comparison;
  - any adaptive-policy result.

## Next decision

This first test passes, and work stopped here as instructed. Two single
bounded experiments would each change what happens next:

1. **Update-band mapping (cheap, one change).** Repeat SC-020 with M
   covering the handoff's out-of-band content, for example 32. Everything
   else stays frozen.
   - Prediction: the >16 error falls below SPD's 0.018 mm and the rejected
     trials shrink.
   - If it does not, the gap is not the band mapping.
   - Supporting measurement, taken after the run (SC-020
     `development/sensitivity.log`): at the hybrid's final state, 0.05 mm at
     arclength harmonic 18 changes the four-frequency data by 4.4e-5. That is
     about 12× the final residual norm (3.7e-6), so the data can see this
     error. At 0.5 GHz alone the change is 2.2e-6, about the size of the
     stage-1 residual (1.6e-6). That explains why stage 1 stalls instead of
     correcting it.

   This settles how the policy's M should be declared relative to SPD's
   update space before any policy comparison.
2. **Harder single-object starts.** Run both arms on distant circle starts
   for single ellipse and star targets under SPD's acquisition and schedule.
   These need new observations, generated with SPD's checked oracle. This
   provides the regression the purpose note asks for, beyond a near-truth
   handoff.

## Follow-up: update band M=32 (SC-021)

The user asked for the update-band fix to be made with minimal further
effort. [SC-021](../../../../results/validation/shape_continuation/SC-021-hybrid-update-band-32/README.md)
repeats SC-020 with only M changed from 16 to 32, and the prediction above
holds.

| | SPD | Hybrid M=32 |
|---|---:|---:|
| Final matched Hausdorff | 0.048 mm | 0.0088 mm |
| Work units | 256 | 150 |
| Rejected trials | — | 0 |
| Stage stops | — | loss tolerance in all four stages |

The error beyond harmonic 16 falls to 0.002 mm, against SPD's 0.018 mm.

**Decision.** SC-020's accuracy and cost gap came from matching SPD by
direction count. It is not a cost of dropping the star-shaped assumption.
From here the SPD-matching comparison uses M=32
(`spd_cases --update-modes 32`); the harness default remains 16 so that
SC-020 reproduces. This is one near-truth case chosen after SC-020, not a
general rule for M. Choosing M from measured sensitivity is a question for
the atlas.
