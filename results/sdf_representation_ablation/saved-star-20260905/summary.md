# Reconstruction / representation policy ablation

Profile: `saved-star`.

Each policy uses identical immutable observations and initial canonical coefficients.
Strict initialization and every optional phase are timed explicitly; no historical result is rewritten.

| Policy | Reconstruction status | Representation | Holdout error | Reconstruction s | Export s | End-to-end s |
|---|---|---|---:|---:|---:|---:|
| legacy_strict | stable_data_and_geometry | failed | 1.3393e-08 | 229.74 | 0.00 | 240.07 |
| curve_only | stable_data_and_geometry | not_requested | 1.3393e-08 | 81.61 | 0.00 | 82.98 |
| export_only | stable_data_and_geometry | failed | 1.3393e-08 | 81.62 | 8.41 | 91.40 |

Policy contract passed: `True`.
Reconstruction convergence, field accuracy, and successful SDF delivery are separate outcomes.
