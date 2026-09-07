# Reconstruction / representation policy ablation

Profile: `short`.

Each policy uses identical immutable observations and initial canonical coefficients.
Strict initialization and every optional phase are timed explicitly; no historical result is rewritten.

| Policy | Reconstruction status | Representation | Holdout error | Reconstruction s | Export s | End-to-end s |
|---|---|---|---:|---:|---:|---:|
| legacy_strict | maximum_iterations | failed | 9.6041e-01 | 5.45 | 0.00 | 7.40 |
| curve_only | maximum_iterations | not_requested | 9.6041e-01 | 1.47 | 0.00 | 1.51 |
| export_only | maximum_iterations | passed | 9.6041e-01 | 1.47 | 2.09 | 3.65 |

Policy contract passed: `True`.
Reconstruction convergence, field accuracy, and successful SDF delivery are separate outcomes.
