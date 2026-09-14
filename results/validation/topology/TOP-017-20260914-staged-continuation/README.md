# TOP-017 — remaining principal frequency exposure

**INCOMPLETE_EXPOSURE_OR_NUMERICAL_OBSTRUCTION.** Promising principal predicate: **False**. Production promotion: **False**.

**central-ellipse-star F recovered within the original gates:** boundary 8.81539 → 0.0623345 mm, IoU 0.999426, worst evaluation error 0.521397 → 0.00123772. This is fixed-count recovery on this development case, not a new benchmark-suite pass.

[Approved contract](../../../../docs/iterations/topology/iteration_10/03_plan.md) · [Implementation review](preflight.md) · [Independent closeout](closeout_review.md) · [Full scorecard](scorecard.json) · [Frozen configuration](contract.json) · [Saved merge audit](merge_stage_audit.md)

## Principal endpoints

Comparisons start from the same reused stage-1 coefficients. Original TOP-016 starts provide context only. Stage 1 was not replayed. Every new stage resets optimizer state identically for both arms; S trains only 0.5 GHz, F follows the cumulative schedule. All reported scores belong to predetermined retained endpoints.

| Case/arm/endpoint | Boundary mm | IoU | Refined 0.5-GHz error | Worst 1.5/2.5-GHz error | Original gates | Numerically qualified | New stage solves | Optimizer-stage outcome |
|---|---:|---:|---:|---:|---|---|---:|---|
| far-two-stars S original TOP-016 start | 11.9911 | 0.7088 | 6.77027e-05 | 1.42174 | False | True | — | — |
| far-two-stars S reused start | 12.0328 | 0.714194 | 6.4259e-05 | 1.41375 | False | True | — | — |
| far-two-stars S stage 2 | 11.997 | 0.718387 | 5.80657e-05 | 1.39282 | False | True | 1249 | STAGE_QUOTA_REACHED |
| far-two-stars S stage 3 | 11.8958 | 0.725275 | 5.3542e-05 | 1.3525 | False | False | 1744 | STAGE_QUOTA_REACHED |
| far-two-stars F original TOP-016 start | 11.9911 | 0.7088 | 6.77027e-05 | 1.42174 | False | True | — | — |
| far-two-stars F reused start | 12.0328 | 0.714194 | 6.4259e-05 | 1.41375 | False | True | — | — |
| far-two-stars F stage 2 | unavailable | — | — | — | — | — | 872 | NUMERICAL_FAILURE |
| central-ellipse-star S original TOP-016 start | 9.22257 | 0.777493 | 0.0156703 | 0.892165 | False | True | — | — |
| central-ellipse-star S reused start | 8.81539 | 0.909688 | 0.000535202 | 0.521397 | False | True | — | — |
| central-ellipse-star S stage 2 | 8.04913 | 0.92259 | 3.23582e-05 | 0.442474 | False | True | 1243 | STAGE_QUOTA_REACHED |
| central-ellipse-star S stage 3 | 7.00142 | 0.928552 | 1.72004e-05 | 0.378267 | False | True | 1733 | STAGE_QUOTA_REACHED |
| central-ellipse-star S stage 4 | 6.12516 | 0.93029 | 1.43157e-05 | 0.321496 | False | True | 1796 | NORMAL_OPTIMIZER_RETURN |
| central-ellipse-star F original TOP-016 start | 9.22257 | 0.777493 | 0.0156703 | 0.892165 | False | True | — | — |
| central-ellipse-star F reused start | 8.81539 | 0.909688 | 0.000535202 | 0.521397 | False | True | — | — |
| central-ellipse-star F stage 2 | 0.745146 | 0.992011 | 4.82689e-05 | 0.0418952 | True | True | 1146 | STAGE_QUOTA_REACHED |
| central-ellipse-star F stage 3 | 0.0464422 | 0.999713 | 3.05039e-07 | 0.000964216 | True | True | 1572 | NORMAL_OPTIMIZER_RETURN |
| central-ellipse-star F stage 4 | 0.0623345 | 0.999426 | 6.72932e-07 | 0.00123772 | True | True | 1132 | NORMAL_OPTIMIZER_RETURN |

[Endpoint quality figure](endpoint_quality.png) · [SVG](endpoint_quality.svg). The final predetermined stage 4 is the headline endpoint, even though central F stage 3 had slightly smaller boundary/evaluation errors. No best-stage selection was performed.

## Training exposure and stopping

Schedule exposure, bounded completion, numerical qualification, configured convergence and reconstruction quality are separate fields in the scorecard. Completed quota-limited stages do not establish stationarity. Scoring frequencies are excluded from training exposure.

| Case/arm/stage | Active GHz | Complete Jacobians | Candidate attempts | Accepted steps | Actual optimizer stop | Convergence | Unused quota |
|---|---|---:|---:|---:|---|---|---:|
| far-two-stars S 2 | 0.5 | 16 | 138 | 15 | None | UNCONFIRMED | 1 |
| far-two-stars S 3 | 0.5 | 22 | 213 | 22 | None | UNCONFIRMED | 6 |
| far-two-stars F 2 | 0.5,0.75 | 6 | 20 | 5 | None | UNCONFIRMED | 378 |
| central-ellipse-star S 2 | 0.5 | 16 | 125 | 16 | None | UNCONFIRMED | 7 |
| central-ellipse-star S 3 | 0.5 | 22 | 201 | 22 | None | UNCONFIRMED | 17 |
| central-ellipse-star S 4 | 0.5 | 23 | 195 | 22 | maximum_iterations | UNCONFIRMED | 2204 |
| central-ellipse-star F 2 | 0.5,0.75 | 8 | 13 | 8 | None | UNCONFIRMED | 104 |
| central-ellipse-star F 3 | 0.5,0.75,1 | 7 | 21 | 6 | no_decreasing_step | UNCONFIRMED | 178 |
| central-ellipse-star F 4 | 0.5,0.75,1,1.25 | 4 | 3 | 3 | gradient_tolerance | CONFIRMED_BY_CONFIGURED_TEST | 2868 |

## Merge representation audit

Fixed evaluation-only projections use the inherited truth-to-polar-angle-gauged Cartesian fitter at K9 and K17. The 16,384-sample procedure is predetermined; 32,768 samples check projection/distance stability, never select a better fit. These states never enter an inverse. A poor projection is not an approximation lower bound; a good projection is not recovery evidence.

| K | Benchmark boundary mm | Dense 16,384 mm | Dense 32,768 mm | Worst evaluation error | 128/256 qualified |
|---|---:|---:|---:|---:|---|
| 9 | 0.7154238 | 0.7138888 | 0.7137704 | 0.08986506404287982 | True |
| 17 | 0.01712342 | 0.02284441 | 0.01717472 | 0.0023445742573378597 | True |

The [saved merge stages](merge_stage_audit.md) retain the measured adverse inverse result: prediction deterioration at shared stage 1, geometric deterioration beginning at F stage 2. Audit capacity does not resolve that regression.

## Work and limits

New attempted/completed/failed frequency solves: **12535/12535/0**. Phase A: **48/256** attempted. Each trial cap 7000 and each stage quota include endpoint scoring; unused quota is not transferred. Historical common-prefix costs are separate in the scorecard. At most two numerical workers, single-thread BLAS; summed worker time is not campaign elapsed time. See [campaign](campaign.json) and [environment](environment.json).

Last gradients carry exact state/objective/resolution associations. Interrupted derivative diagnostics may be partial; no terminal Jacobian was run solely for reporting. Exact frequency solves are counted; factorization/RHS counts are unavailable. Development evaluation frequencies never fit updates and do not establish generalization.

## Recorded obstructions

- far-two-stars S, stage 3: retained endpoint numerical qualification failed.
- far-two-stars F, stage 2: candidate leaves frozen numerical-resolution regime.

The scorecard retains exact failed discrepancies and associations with rejected candidates and retained states. The two-star pair did not complete effective exposure to the whole schedule; these stops do not decide its frequency-recovery benefit. The measured central recovery is retained separately.

## Next decision

Decide whether a separately scoped numerical-resolution check of the saved two-star states is justified before any further continuation experiment. No successor, merge inverse, local control or suite was executed or authorized by this closeout.
