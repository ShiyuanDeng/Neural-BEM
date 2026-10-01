# NU-001 six-case validation: retain the nodal trial map

2026-10-01. This is the result of the [pre-registered iteration 08 plan](../iteration_08/03_plan.md). The two prepared campaigns ran from the original start on the RTX 5090 with `device=auto`, four frequency threads, `nodal_kress` physics, and one case at a time. The archived CI-001 runs supply the nodal arm. Both campaign source and augmentation seals pass `verify`; all 12 result files exist, all 12 physics receipts include CUDA work, and the run logs contain no `FAILED` line.

## Decision

The [drift audit](../../../../results/validation/cleaned_interfaces/NU-001-drift/drift.json) applies the plan's fixed rules. Arm A matches 2/6 cases and has drift flags on 5/6. Arm B matches 3/6 and has drift flags on 4/6. Neither qualifies (the rule requires no drift flag and at least 5/6 matches), so **keep the nodal `ProjectedUpdate` trial map**. The coefficient normal updates remain experimental.

| Core case | Nodal status / max rσ | A status / max rσ | B status / max rσ | Drift in A / B |
|---|---:|---:|---:|---|
| `wrong_circle` | PASS / 1.000 | REGRESSION / 1.000 | REGRESSION / 1.000 | none / none |
| `peanut` | PASS / 1.012 | PASS / 1.937 | PASS / 1.087 | speed / none |
| `circle_to_c` | PASS / 1.154 | REGRESSION / 21.304 | REGRESSION / 12.103 | speed + log degree / speed + log degree |
| `hook` | PASS / 1.182 | REGRESSION / 288.247 | REGRESSION / 12.869 | speed / speed + log degree |
| `circle_to_star` | REGRESSION / 1.092 | REGRESSION / 1.420 | REGRESSION / 1.206 | speed / speed |
| `kite` | PASS / 1.078 | REGRESSION / 3914.595 | PASS / 1.700 | speed + log degree / speed |

Here “speed” means at least one of the two pre-registered speed-ratio thresholds fired; “log degree” means a stage exceeded 1.3× the nodal stage's log|W|² Chebyshev degree. A and B both recover `circle_to_star`, for which the archived nodal arm also has a frozen comparison regression, so it counts as a match under the plan. The [A](../../../../results/validation/cleaned_interfaces/NU-001-A/comparison.json) and [B](../../../../results/validation/cleaned_interfaces/NU-001-B/comparison.json) reports apply the frozen CI-001 gates; their other regressions are not reclassified here.

Arm B suppresses drift on `peanut` and recovers `kite`, but it still reaches rσ = 1.700 on `kite` and exceeds 12 on `circle_to_c` and `hook`. Arm A reaches rσ = 21, 288, and 3915 on those three cases and stops with numerical failure. The tangential term improves some paths without meeting the generality rule.

## Timing and work

The six-case sums below compare the archived nodal GPU runs with the two new GPU campaigns. Geometry certificate time is **inside** geometry preparation time, so the columns are not additive. Fit units are the policy's work units. Physics timings sum work across four frequency threads and are therefore not wall-time components.

| Arm | Total wall (s) | Fit + localization (s) | Fit units | Geometry preparation (s) | Of which certificate (s) | Geometry trial (s) |
|---|---:|---:|---:|---:|---:|---:|
| Nodal | 572.8 | 488.6 | 9,677 | 64.8 | — | 5.41 |
| A | 396.1 | 315.7 | 5,770 | 28.4 | 25.0 | 0.86 |
| B | 645.7 | 560.8 | 11,420 | 56.8 | 56.4 | 1.43 |

The exact affine updates cut geometry trial time, but certificate computation consumes most of their preparation time on these paths. Arm A's shorter total is driven in part by early numerical failures (`hook`, `kite`, `circle_to_c`); it is not a successful speedup. Arm B takes more work and wall time than nodal in the six-case sum. These are single runs with different decisions, not a matched runtime qualification.

## Separate post-hoc audit of `wrong_circle`

The **frozen** final audit fails for both A and B because a few near-zero Jacobian columns have production/refined relative discrepancies of 4.82% and 4.87% respectively, against the 0.1% per-column gate. Their norms are about 10⁻¹⁴ of the largest column; the largest absolute discrepancy is about 4.8 × 10⁻¹⁶ of that largest column's norm. Both arms reach RMS 7.58 × 10⁻⁶ mm and relative residuals around 10⁻¹⁴. The frozen regression and match counts above remain unchanged.

For diagnosis only, replacing the per-column denominator by `max(column norm, 10⁻¹² × largest column norm)` gives maximum ratios 4.72 × 10⁻⁴ (A) and 4.75 × 10⁻⁴ (B), below 10⁻³. This absolute floor was chosen after the runs and is **not** a campaign gate, a repaired audit, or a change to the pre-registered decision.

The full evidence is in [NU-001-A](../../../../results/validation/cleaned_interfaces/NU-001-A/), [NU-001-B](../../../../results/validation/cleaned_interfaces/NU-001-B/), the [drift report](../../../../results/validation/cleaned_interfaces/NU-001-drift/drift.json), and the [run logs](../../../../results/validation/cleaned_interfaces/NU-001-logs/). These six core cases do not establish all-36 numerical or runtime retention.
