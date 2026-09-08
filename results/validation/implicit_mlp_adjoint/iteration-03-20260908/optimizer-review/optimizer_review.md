# Long-run optimizer evidence for the iteration-3 results report

The long paired arm changes the early optimizer finding: **actual Adam becomes less geometrically useful than total-gradient descent at the selected intermediate states, and has the wrong signed correction at state 40.** The multistatic arm does not show the same Adam distortion. Both runs ultimately stop at geometry admissibility barriers that also reject fallback directions after moment resets. These are distinct findings; neither supports attributing both stops to Adam.

This is a read-only review of `iteration-02-final/long-acquisition-20260908T174300326691Z`. It loads all 75 actual optimizer checkpoints and existing trial/geometry reports. No model, extraction, BEM, inverse, or fresh perturbation was run. [optimizer_review.json](optimizer_review.json) contains the source hashes and numerical checks; [optimizer_review.py](optimizer_review.py) reproduces the saved-array calculations in approximately 0.5 seconds after imports.

## Actual accepted methods, resets and stops

| Measurement | E0: paired-8 | E1: multistatic-8 |
|---|---:|---:|
| Accepted updates | 42 | 31 |
| Adam / fallback accepted updates | 41 / 1 | 29 / 2 |
| Attempted candidates | 349 | 312 |
| Fallback attempted at optimizer states | 41, 42 | 29, 30, 31 |
| Actual fallback resets | 41 | 29, 30 |
| Accepted moves below the 0.1 mm reporting floor | 3 | 5 |
| Final accepted move | 6.019 µm | 1.917 µm |
| Stop | `no_decreasing_neural_step` | `no_decreasing_neural_step` |

An optimizer-state index denotes the state from which the next step is proposed. For example E0 fallback at state 41 produces accepted state 42 and clears Adam moments.

Every saved Adam and fallback proposal is a descent direction for both the saved data gradient and total gradient; none fails the non-descent precheck. The fallback attempts follow unsuccessful Adam searches, rather than an observed non-descent skip. The small accepted fallback moves are not evidence of renewed recovery.

## Signed geometry: intermediate paired states degrade under Adam

All directions below have the same **20 µm predicted RMS raw normal motion**. The score is the signed inner product with the saved nearest-target correction projected onto arc-length modes 0–20, with positive values reducing this error. It is not a radial mode-amplitude difference or a proof of recovery.

| Arm / optimizer state | Total-gradient score, 10⁻⁸ m² | Actual Adam score, 10⁻⁸ m² | Total/Adam normal-motion cosine | Existing finite 20 µm probe |
|---|---:|---:|---:|---|
| E0 / 0 | 5.763 | 10.671 | 0.964 | Both agree with prediction |
| E0 / 10 | **11.447** | **3.456** | 0.767 | Actual scores 11.446 / 3.455 |
| E0 / 20 | **10.440** | **6.137** | 0.876 | Actual scores 10.453 / 6.154 |
| E0 / 30 | **8.418** | **2.480** | 0.875 | Actual scores 8.486 / 2.534 |
| E0 / 40 | **+2.545** | **−2.946** | **0.577** | All directions fail with two raw components |
| E0 / 42, after reset | +2.538 | +2.265 | 0.997 | All directions fail with two raw components |
| E1 / 0 | 29.161 | 30.824 | 0.961 | Both agree with prediction |
| E1 / 10 | 18.474 | 18.911 | 0.976 | Actual scores 18.478 / 18.912 |
| E1 / 20 | 8.950 | 9.008 | 0.996 | Actual scores 8.948 / 9.004 |
| E1 / 30, after reset | 5.999 | 6.185 | 0.994 | All directions fail conversion-distance limit |
| E1 / 31, after reset | 5.999 | 6.184 | 0.994 | All directions fail conversion-distance limit |

E0's modes 2–20 distinguish the directions even before its total score changes sign. At states 20 and 30, the total-gradient scores restricted to these modes are positive (`+2.156e-8`, `+3.866e-8 m²`), whereas Adam's are negative (`−2.356e-8`, `−1.406e-8`). At state 30 the arc-length-mode-5 signed effect is `+2.129e-9` for total gradient and `−1.510e-8 m²` for Adam. These are coordinated normal-motion scores, not a claim that changing one Fourier mode in isolation would improve the inverse.

The available finite raw-motion checks confirm the E0 ranking at states 10, 20 and 30. At state 30 the raw IFT prediction error is approximately 0.865% of RMS motion for total gradient and 0.609% for Adam. However there is only one common finite scale; no alpha convergence window is established. At state 40 the sign contrast remains **prediction-only** because the finite candidates fail topology. State 42's reset changes the predicted Adam direction back to positive, but neither Adam nor fallback obtains an admissible next step.

E1 keeps positive, similar total-gradient and Adam corrections at all selected states. Late E1 snapshots at 30 and 31 already use reset moments, and the remaining failure therefore cannot be explained solely by stale Adam history. Geometry was sampled only at E0 states 0, 10, 20, 30, 40, 42 and E1 states 0, 10, 20, 30, 31; other states have weight-space records but no comparable saved motion probe.

## Regularizer and field conditioning

The weighted Eikonal/data gradient-norm ratio reaches only 1.81% in E0 and 2.11% in E1; the terminal ratios are 1.12% and 2.11%. At all selected states, data-only and total-gradient normal motions have cosine at least `0.9999905` in E0 and `0.9999954` in E1. The existing regularizer changes the immediate interface direction very little while field conditioning deteriorates.

The on-contour gradient spread grows from about 1.50 initially to **21.09** in E0 and **6.67** in E1. Terminal ranges are E0 `0.176–3.721` and E1 `0.490–3.267`. This is descriptive evidence, not a causal repair experiment.

The numerator and denominator cannot be collapsed into a single explanation. At E0 state 30, matching the RMS scale of `−N` alone gives an Adam signed score of `−3.377e-8 m²`, while `−N/G` gives `+2.480e-8`; the variable denominator substantially changes the geometric score. At state 40 Adam is adverse in both (`−7.161e-8` for the normalized numerator, `−2.946e-8` for velocity), while the total-gradient numerator is nearly neutral (`−6.35e-10`) and its velocity is positive (`+2.545e-8`). Thus the late distortion involves the neural direction and its interaction with G; division by G is not uniformly harmful or uniformly corrective.

## Terminal admissibility barriers

E0's binding reason for the next-larger rejected step is motion at 31 accepted transitions, conversion distance at 5, refinement change at 1, and topology at 5. The final state generates 15 Adam and 15 fallback trials. At their smallest tested factors (`1/16384`) the independent conversion audit still detects **two raw zero-set components**. The accepted state's saved conversion distance is 0.190273 mm, so the terminal report must retain the topology/audit distinction rather than describe every failure as a 0.2 mm distance limit.

E1's next-larger rejected steps bind motion at 22 transitions and conversion distance at 9, with refinement also failing at 2 of those transitions. Its final accepted conversion distance is **0.1999554 mm**, only about **44.6 nm below** the 0.2 mm limit. All 15 final fallback trials fail conversion distance. Even the smallest candidate reports **0.2001447 mm**, while refinement change is just **0.0023349 mm**, comfortably below the separate 0.01 mm refinement limit. This is a conversion-distance stop. The last five accepted moves shrink to approximately 51.8, 25.9, 12.9, 3.83 and 1.92 µm.

Consequently, a positive infinitesimal signed score or a moment reset does not demonstrate an admissible useful finite step at either terminal state. Neither run exhausted its declared 60-update, 1,440-candidate or one-hour cap.

## Optimizer integrity and interpretation limits

All 75 bound-projected Adam proposals equal their raw proposals exactly. Adam first/second-moment recurrence errors are at most `2.23e-16` / `3.47e-18`; raw update equations agree to `5.53e-17`. Accepted increments match their saved backtrack factors to `5.56e-17`. Saved weight/moment continuity is exact. Successful fallback steps clear moments as specified, and terminal failed searches restore the preceding moments exactly. Nested trial records match `trials.jsonl` throughout. There is no demonstrated implementation bug in these checks.

For documenting what the measurements support: the paired-arm evidence now supports investigating the effect of the actual optimizer metric at admissible intermediate states, whereas multistatic's terminal evidence chiefly concerns conversion fidelity and field conditioning. Existing frozen field-repair and independent conversion-resolution diagnostics address unresolved causal questions. These records do not establish a production optimizer fix, an admissible terminal alternative, or the outcome of any further experiment. No new experiment plan or production change is made by this review.
