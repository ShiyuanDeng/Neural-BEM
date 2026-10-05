# GGB-004 — The restricted circle stage settles in 3.70 seconds

Completed 2026-10-05 under the user's instruction to run immediately, then
their explicit choice: **"Inspect the initial stage first."** No ordinary
shape stage was run. The saved endpoint is available for later continuation.

Allowing only exact translation and uniform scaling avoids the deformation
failure observed in GGB-003. The original centred radius-350 mm circle reaches
the target location and size in **43 accepted updates / 3.702 seconds**.
Every step is accepted at full length; there is no backtracking, geometry
refusal or failed physics candidate. All 44 saved states remain exact circles.

| Measurement | Restricted-stage endpoint |
|---|---:|
| Centre | (−0.330108, −0.527287) m |
| Centre error | **0.198 mm** |
| Radius | **172.546 mm** |
| Target area-equivalent radius | 172.725 mm |
| Radius difference | 0.179 mm |
| Original pixel-grid SSIM / RRMSE | **1.0 / 0.0** |
| Joint loss, initial → final | 2.87310 → **0.00172962** |
| Fit / endpoint-audit time | 3.702 / 0.140 s |
| Fit work | 528 of 2600 stage units |
| Geometry trial construction | **0.0141 s** |
| Optimizer stop | NORMAL_OPTIMIZER_RETURN / no_decreasing_step |

The radius initially shrinks to 66.3 mm while the centre moves, then grows
back toward 172.5 mm as the circle arrives. These are ordinary data-driven
updates, not a prescribed path. The shape remains circular throughout, so
the temporary shrinking does not create the persistent protrusions seen when
normal shape updates were interleaved with translation.

## Did this stage converge?

It **settled within the existing step/acceptance precision of the restricted
circle model**. The formal gradient criterion was not reached: the terminal
gradient infinity norm is 4.20e-7 versus tolerance 1e-7. However, an independent
endpoint Jacobian audit gives an undamped Gauss–Newton move of just
6.562e-9 m (6.6 nm), below the existing 1e-7 m step threshold for this stage.
Its predicted objective reduction is 1.233e-15, approximately 14,000 times
smaller than the existing 1.731e-11 acceptance margin. Trace cutoffs 64 and
96 agree on these diagnostics. Thus `no_decreasing_step` here is consistent
with negligible remaining local improvement, not invalid-shape stagnation.
This is a local restricted-model conclusion, not a proof of global optimality.

## Remaining data mismatch

| Frequency | Role | Relative residual | Noise target |
|---|---|---:|---:|
| 0.40 GHz | Archived holdout | **5.018%** | 5.498% |
| 0.50 GHz | Fitted | **5.205%** | 5.498% |
| 0.75 GHz | Fitted | 5.629% | 5.499% |
| 1.00 GHz | Fitted | 6.006% | 5.492% |
| 1.25 GHz | Fitted | 6.594% | 5.490% |

The three higher frequencies and the joint discrepancy still miss their
thresholds (joint target 0.00150961). All field-refinement checks pass at
approximately 1e-15 relative error. We therefore do **not** label this full
noise-discrepancy recovery. Exact image metrics refer to the original pixel
grid: a smooth circle and the supplied pixel-cell boundary need not be the
same continuous geometry. Discretization/model mismatch is a plausible
contributor to the remaining frequency-dependent residual, not established
by this experiment.

## What this changes

For this case, a distinct position-and-size stage is much more effective than
interleaving shape deformation from the start. GGB-003's interleaved fit took
297.68 s and ended at loss 0.0112442 with thin protrusions; this restricted
stage reaches a lower loss and better image match in 3.70 s. The endpoints
and stages differ, so this is an observed case comparison rather than a
general speedup claim. The dominant geometry cost disappears because exact
positive similarity transformations preserve the circle's validity.

The next continuation, if requested, can start from this saved circle. Its
purpose would be to assess the remaining residual without undoing the good
initialization. No further experiment, shape stage, or tuning was performed.

## Evidence

- [Preregistered plan](GGB-004_plan.md) and [authorization/scope record](../../../results/validation/cleaned_interfaces/GGB-004/authorization.json).
- [Convergence figure, SVG](../../../results/validation/cleaned_interfaces/GGB-004/convergence.svg).
- [Direct-boundary video](../../../results/validation/cleaned_interfaces/GGB-004/W/video/case8_translation_scaling_boundary.mp4), using the established video generator and all saved states.
- [Full endpoint diagnostics and generated report](../../../results/validation/cleaned_interfaces/GGB-004/report.md).
- [Saved endpoint](../../../results/validation/cleaned_interfaces/GGB-004/W/endpoint.npz).

110 package/adapter/controller tests passed. Three-coordinate field derivatives
at all four frequencies on CPU/CUDA pass with maximum relative error
1.118e-9. Independent review verified every circular state, coordinate cap,
full accepted step, endpoint archive, loss and convergence diagnostic. Saved
residuals and image metrics were recomputed. Code, data hashes, histories,
qualification and timing receipts are retained with this run.
