# Iteration 1 — results, problems and possible fixes

September 7–8, 2026. Written retrospectively from the dated audits and reports,
so it records no new experiment; the numbering was assigned after the fact.
Three 12-pair neural inverses failed recovery, targeted repairs were validated
on frozen checkpoints, and the reruns still failed. That is the case put to
ChatGPT in [02_proposals](02_proposals/); the outcome is in [03_plan.md](03_plan.md).

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

## Possible fixes

Retrospective inventory: no separate pre-consultation proposal was saved, so
the dispositions come from the later audits and reviews.

| Candidate | Evidence | Discriminating check | Disposition |
|---|---|---|---|
| Shrinking fallback and deeper diagnostic search | Another halving admits descent at the old circle/star checkpoints | Evaluate unchanged fallback candidates under the original tests | Shrinking fallback retained; deeper search and rejection accounting implemented |
| Star pretraining penalty change | Matched known-target error improves 9.18 → 1.15 mm | Fixed seed, network, sample sequence and training budget; check topology | Zero star penalty retained; inverse Eikonal remains separate |
| Resolved conversion and a guard | Raw and converted contours differ materially | Freeze weights and vary bandwidth, extraction and audit resolution independently | Guard and resolution controls retained; future candidates still require checks |
| Matched eight-versus-twelve-pair control | Historical five-parameter star succeeds at the original frequencies | Fix family, initialization, optimizer and forward resolution | Test before claiming higher frequency is necessary |
| Multistatic readout | Solves compute more entries than the paired experiment retains | Scaled physical/modal Jacobians for paired-8, paired-12 and multistatic-8 | Diagnostic arm followed by a conditional neural experiment |
| Higher frequency and continuation | Lobe sensitivity may depend on band | Combined-frequency spectra, then a matched frequency change | Conditional; no hard mode cutoff or holdout-based selection |
| Neural GN/TSVD/IRGN | Neural updates may remain poorly conditioned | Scaled neural Jacobian after cheaper physical/modal controls | Defer a production optimizer until evidence justifies it |

Broader distance-supervision prototypes and zero-penalty ellipse pretraining
failed topology checks. Enlarging the network, weakening fidelity gates and
returning to a separate curve-to-MLP fitting loop were unsupported.

The consultation had to separate stopping mechanism, information content, shape
prior and nonlinear optimization, with declared scales, disjoint evaluation
frequencies and comparable work budgets.

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

## Supporting reports

These four reports are in the repository, each with its own metrics, scripts
and provenance:

- [Failure audit](../../../../results/validation/implicit_mlp_adjoint/failure-audit-20260907/README.md) — fallback, pretraining and raw/converted geometry
- [Validated repairs](../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/README.md) — adopted changes and rejected prototypes
- [Repair reruns](../../../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md) — circle/star bandwidth comparisons
- [Checkpoint review](../../../../results/validation/implicit_mlp_adjoint/review-20260908/README.md) — the additional acceptable star fallback

The A–E controls and observability study is not in the repository; its bundle
is local at `results/validation/implicit_mlp_adjoint/latest-direction-20260908/`.
Its measured outcomes are tabulated in [03_plan.md](03_plan.md).
