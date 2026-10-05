# GGB-005 — One frequency is sufficient for this initial circle fit

Completed 2026-10-05. The translation-and-radius stage fitted to **0.5 GHz
alone reaches its noise target in 1.322 seconds and 30 full accepted updates**.
No ordinary shape stage was run. The original centred 0.35 m circle, frozen
observations, known material, step limits and numerical checks are unchanged.
This uses the lowest member of the GGB-002 panel; the archived 0.4 GHz
measurement is checked afterward as a holdout.

| Measurement | GGB-004: four frequencies | GGB-005: 0.5 GHz only |
|---|---:|---:|
| Fit seconds | 3.702 | **1.322** |
| Accepted updates | 43 | **30** |
| Forward evaluations | 352 | **62** |
| Derivative batches | 176 | **31** |
| Centre error | 0.198 mm | **0.103 mm** |
| Radius | 172.546 mm | 172.512 mm |
| Original pixel-grid SSIM / RRMSE | 1.0 / 0.0 | **1.0 / 0.0** |
| Stop | No decreasing step | **Fitted noise target reached** |

Both geometries reproduce the original pixel mask exactly. This does not
mean equality with the continuous pixel-cell boundary. The single-frequency
run has no geometry refusal, backtracking or failed field evaluation.
All 31 stored states remain exact circles. These are single timing
observations with different stopping criteria, not a general speedup claim.

## What “two resolutions” means

The physical measurement frequency is still just **0.5 GHz**. The BEM field
solver uses modal cutoffs **64 and 96**: 129 and 193 Fourier modes per trace,
or transmission matrices of size 258 and 386. The higher cutoff checks that
the predicted fields and objective improvement are numerically reliable.
These are field-solver accuracies; the geometry still has only three
parameters. The frozen field/decrease checks remain active.

There are 31 states × one frequency × two resolutions = **62 forward
evaluations**, plus 31 Jacobian batches. At four frequencies the analogous
count was 44 × four × two = 352. Single-frequency fit timings include
0.384 s assembly, 0.379 s physics geometry preparation, 0.134 s source/receiver
waves, 0.122 s factorization, 0.038 s field readout and 0.113 s Jacobian work.
Circle-update preparation/construction takes 0.037 s. Physics geometry is
shared across frequencies in the four-frequency run, so its cost does not
fall proportionally with the frequency count. Initialization and remaining
overhead also remain. The separate post-fit audit takes 0.089 s.

## Stopping and held-out measurements

| Frequency | Role | Residual | Noise target | Pass |
|---|---|---:|---:|---|
| 0.40 GHz | Archived holdout | 5.015% | 5.498% | Yes |
| **0.50 GHz** | **Only fitted frequency** | **5.204%** | **5.498%** | **Yes** |
| 0.75 GHz | Holdout | 5.625% | 5.499% | No |
| 1.00 GHz | Holdout | 6.014% | 5.492% | No |
| 1.25 GHz | Holdout | 6.601% | 5.490% | No |

Every field-refinement check passes at approximately 1e-15. Only 0.5 GHz
enters the fitted objective, discrepancy threshold, acceptance decisions and
restricted-stationarity audit. The higher-frequency failures are reported
as holdout evidence, not silently counted as fitted failures or successes.

The final one-frequency loss is 0.00135433. The solver returns
`NORMAL_OPTIMIZER_RETURN / loss_tolerance`: the noise target was reached,
not gradient stationarity. An endpoint audit finds an available Gauss–Newton
move of 0.134 mm and predicted gain 1.03e-6, above the 1.36e-11 acceptance
margin. We did not continue optimizing after the prescribed noise stop.

This supports **single-frequency translation-and-size initialization on this
case**. It does not establish that one frequency suffices for general shape
recovery or explain all remaining high-frequency model discrepancy.

## Evidence and validation

- [Preregistered plan](GGB-005_plan.md) and [authorization](../../../results/validation/cleaned_interfaces/GGB-005/authorization.json).
- [Convergence figure, SVG](../../../results/validation/cleaned_interfaces/GGB-005/convergence.svg).
- [Direct-boundary video](../../../results/validation/cleaned_interfaces/GGB-005/W/video/case8_translation_scaling_boundary.mp4), with all 31 saved states and the established encoder.
- [Full saved endpoint diagnostics](../../../results/validation/cleaned_interfaces/GGB-005/report.md).

116 tests pass, including explicit holdout exclusion and four-frequency
scoring tests. Unchanged numerical-source/input hashes allow reuse of the
passed CPU/CUDA 0.5 GHz derivative qualification; its receipt is linked and
hashed, rather than represented as a new physics test. Saved predictions,
metrics, circle invariants, coordinate caps, accepted steps, objective and
active-frequency flags were independently verified. The earlier four-frequency
receipt also passed the generalized verifier without modifying its artifacts.
