# Reconstruction / representation policy ablation

Profile: `saved-star`.

Each policy uses identical immutable observations and initial canonical coefficients.
Strict initialization and every optional phase are timed explicitly; no historical result is rewritten.

| Policy | Reconstruction status | Representation | Holdout error | Reconstruction s | Export s | End-to-end s |
|---|---|---|---:|---:|---:|---:|
| curve_only | stable_data_and_geometry | not_requested | 1.3393e-08 | 70.23 | 0.00 | 71.49 |

Policy contract passed: `True`.
Reconstruction convergence, field accuracy, and successful SDF delivery are separate outcomes.
