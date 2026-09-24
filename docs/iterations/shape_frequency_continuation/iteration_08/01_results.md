# Iteration 08 — the atlas along real trajectories (SC-022)

2026-09-24. Executed from the [iteration 07 plan](../iteration_07/03_plan.md)
after the user moved the focus to the atlas. The user chose the cases:
wrong circle, circle to star, and a new non-star C. Records are in
[SC-022](../../../../results/validation/shape_continuation/SC-022-atlas-survey/README.md).
No independent review was claimed at execution.

## Outsider review added 2026-09-24

The [Codex review](02_proposals/01_codex_outsider_review.md) accepts the
descriptive atlas and confirms its counts, local artifact hashes and step
replay. It qualifies the interpretations below:

- The recorded LM steps are damped but unclipped; they are not unregularized.
  Per-frequency inversion has 48 real data rows for 97 real coefficients.
- A component of the full-band step is conditional on the other allowed
  directions. At the final star and 0.75 GHz, p=15's alignment with the error
  proxy changes from +0.952 to −0.998 when solving only for the existing M=9
  space plus that pair. This is an offline model check, not a recovery trial.
- The “true error” layer is a signed closest-distance proxy. It is not
  generally the displacement needed along the current normal. Whole-vector
  norms and cosines also need the physical Fourier mass metric.
- The M=32 failures concern the tested clipping, damping, starts and retry
  limits; they do not establish that this band cannot work from distant starts.

The audit additionally finds positive model decrease for all 135 accepted
steps, with actual/predicted ratios 0.926–1.767. This supports local models
on accepted steps, not unexecuted atlas recommendations. The review gives
derivations, literature, reproducible checks and the resulting next questions.
Original observations below remain the execution record, read with these
qualifications.

## What exists now

For three cases, every accepted state of every trajectory has the full
first-order picture over 19 frequencies (0.25–2.5 GHz) and 48 normal
harmonics:
- sensitivity;
- the signed gradient;
- the complete Gauss–Newton block and its spectrum;
- the LM step at the live damping;
- a truncated GN step;
- evaluation-only, the true error on the same harmonics.

This covers 159 states and 2,679 cells, all in the backend's own
coordinates. The atlas reproduces the backend's recorded steps to ≤1.5e-13.
Because the blocks and gradients are stored, other step variants can be
derived offline with no solves.

## What happened on the way

**Fixed M=32 cannot start far from the answer.** From the legacy circle all
three cases stall in stage 1, at 26, 34 and 48 mm. Every rejection is
geometric. Unregularized weak harmonics receive steps clipped at SPD's 6 mm
bound, and those steps produce self-intersecting or unrefittable curves.
SC-021's M=32 result holds only near the truth.

**Borges' published band ladder works as a trajectory generator.** It uses
M = floor(3·max(k, kᵢ)), which here is 3, 5, 7 and 9. Results:
- wrong circle: 43 → 0.005 mm;
- star: 49 → 1.43 mm;
- C: 60 → 19.4 mm (fails).

This was a declared amendment, adding a second arm; the M=32 runs are kept.

## Descriptive observations (not yet interpreted)

1. **Raw steps are dominated by weak directions.** A frequency's raw LM step
   in the full 48-harmonic space is dominated by the weak directions along
   that frequency's sensitivity edge. At the starts, its median size is
   600–2,300 mm against a 25 mm true error. It needs regularization before
   it can serve as a signal.
2. **Off the circle, sensitivity spreads to high arclength harmonics at all
   frequencies,** as SC-015 saw on the glider.
3. **The star shows what a band rule needs to decide.** At its final state
   the remaining error is at harmonics 15, 20, 25 and 10, beyond M=9.
   - At p=15 (0.66 mm), every frequency from 0.75 GHz up points its own step
     at the truth (cosine ≥0.85), at 40–90% of the needed size. These
     frequencies are inside the schedule's training set.
   - At p=20 (0.21 mm), the same frequencies point the wrong way and
     overshoot.

   So "open the band" is not one decision: which harmonics to open depends
   on which frequencies are in hand.
4. **The full-band stage step stops pointing at the truth near the end:**
   cosine 0.08 for the star and 0.01 for the C at the final states.

## Next decision

The recording phase is complete. The next step is analysis of the stored
atlas, with no new solves. Candidate questions:
- Which training-only quantity, computable without truth, predicts the
  harmonics whose step points at the truth? Examples: sensitivity against
  the residual, agreement across frequencies, predicted against realized
  decrease.
- How should the per-frequency step be regularized so that it becomes a
  usable signal?
- Why does the C stall at 19 mm while the data still carry 0.1–1 relative
  residual?

These are user decisions. No successor experiment is scheduled.
