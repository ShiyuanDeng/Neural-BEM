# Iteration 01 — results and diagnosis before consultation

Retrospective summary from the September 7–8 reports. These measurements
precede implementation of the revised A–H guide. Its later outcomes are in
the local final review; this summary records no new experiment.

## Problem and setup

An 8,577-weight, width-64, two-hidden-layer SIREN owns the accepted geometry.
Its zero contour is extracted, converted by Method B and evaluated by Kress
BEM. Discrete-adjoint sensitivities propagate through the branch-local
conversion reverse; actual candidate networks are re-extracted and checked.
Observations are independent Mie data for circle and Nyström data for star.

Original runs use 12 paired views, seed 0, 6,000 pretraining steps and a
60-update cap. Circle trains at 0.25/0.5 GHz; star at 0.5/1.5 GHz. The inverse
learning rate is 0.001 and Eikonal weight 0.01. Raw run artifacts preserve
the complete materials, acquisition, commands and provenance.

## Original failures

Boundary error is maximum sampled Method-B node-to-target distance, not a
continuous Hausdorff certificate. Training and holdout frequencies differ.

| Original case | Updates | Train relative L2 | Holdout relative L2 | Boundary error | Stop |
|---|---:|---:|---:|---:|---|
| Circle → circle | 43 | 0.001690 | 0.063944 | 1.038 mm | `no_decreasing_neural_step` |
| Ellipse → circle | 60 | 0.008951 | 0.318638 | 6.450 mm | Update budget |
| Star → star | 60 | 0.245624 | 0.783925 | 26.833 mm | Update budget |

All three fail recovery. Falling training loss and good center/radius estimates
do not establish accurate general boundary recovery.

## Demonstrated mechanisms and repairs

1. **Circle minimum-step limitation.** The old fallback normalized every
   gradient to maximum weight displacement 0.001. At the saved final state,
   eight halvings fail data Armijo; nine pass every test and lower loss by
   5.83%. Capping large gradients without amplifying small ones lets a restart
   accept three more updates with the original search budget.
2. **Star pretraining bias.** Changing only the pretraining Eikonal weight from
   0.1 to zero improves a matched exact-target fit from 9.18152 to 1.15088 mm
   boundary error. The teacher `F/||grad F||` approximates distance locally and
   conflicts with a whole-domain unit-gradient penalty. The old fitting error
   is not an intrinsic network capacity bound.
3. **Conversion distortion.** Frozen raw/converted discrepancies are about
   0.267 mm for circle, 1.821 mm for ellipse-to-circle and 0.178 mm for star.
   The new guard requires distance at most 0.2 mm and refinement change at
   most 0.01 mm, rejecting invalid candidates before BEM.

Circle and ellipse retain pretraining weight 0.1. Removing the ellipse penalty
produced five contours; broader star distance-supervision prototypes produced
three or 23 contours and were excluded. Better contour fitting does not certify
signed-distance quality.

Frozen BEM node refinement on the original checkpoints changes circle/ellipse
predictions by roughly machine precision and star by 5.71e-6 followed by
3.60e-10. These checks do not implicate BEM accuracy as the dominant original
failure; new configurations need their own qualification.

## Full reruns after repairs

These runs use eight pairs, so they are not isolated optimizer comparisons
against the original 12-pair experiments.

| Case / bandwidth | Updates | Train relative L2 | Holdout relative L2 | Conversion distance |
|---|---:|---:|---:|---:|
| Circle / 10 | 11 | 0.5653 | 1.172 | 0.199997 mm |
| Circle / 20 | 60 | 0.001795 | 0.07053 | 0.07984 mm |
| Star / 48 | 27 | 0.6526 | 1.023 | 0.199947 mm |
| Star / 96 | 32 | 0.5966 | 1.078 | 0.1061 mm |

Raising bandwidth removes the circle's early guard-limited stop, but it still
ends at 1.122 mm boundary error. Star bandwidth 96 ends at 36.386 mm; fitted
amplitude and rotation errors worsen despite falling training loss. Both fail
recovery gates. Circle takes 2,632 seconds with 479 attempted evaluations;
star takes 2,995 seconds with 233 attempts. These inverse timings include
rejected geometry attempts and are not matched hardware benchmarks.

## Correction discovered during review

The initial guide inferred that a final conversion distance below 0.2 mm
eliminated conversion as the star's stopping constraint. The last permitted
fallback actually fails refinement change: 0.0115825 mm against 0.010 mm.
Backtracks 9, 10 and 12 pass every acceptance condition.

The first extra accepted candidate lowers loss 0.3461879921 → 0.3460535596,
about 0.039%, and moves the boundary 0.07076 mm. This demonstrates a
nonstationary search-budget stop, not a solution to the 36 mm shape error.

## Questions entering the revised guide

- Does the five-parameter star still recover with eight pairs at 0.5/1.5 GHz?
  Its historical 12-pair control reached about 0.039 mm error and 3.14e-5 holdout.
- Which physical and general normal modes are locally observable, using equal
  displacement scales and combined-frequency Jacobians?
- Does multistatic readout improve conditioning? Kress and the independent
  oracle compute full response matrices before selecting the paired diagonal.
- Does a target-fitted MLP have a usable local descent neighborhood?
- Does higher frequency add information after enriching acquisition, and when
  would continuation or a different neural optimizer become justified?

Eight pairs at two frequencies provide 32 real residual entries for 8,577
weights. This rank ceiling does not prove that every unobserved weight direction
moves the boundary or that the desired shape is unrecoverable.

Full reports are included in the local [failure audit](evidence/01_failure_audit.md),
[repairs](evidence/02_validated_repairs.md), [reruns](evidence/03_repair_reruns.md)
and [checkpoint review](evidence/04_checkpoint_review.md). The
[final review](05_final_review.md) distinguishes these hypotheses from later results.
