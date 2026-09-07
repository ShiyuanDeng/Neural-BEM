# Reconstruction / representation policy ablation

Profile: `short`.

Each policy uses identical immutable observations and initial canonical coefficients.
Strict initialization and every optional phase are timed explicitly; no historical result is rewritten.

| Policy | Reconstruction status | Representation | Holdout error | Reconstruction s | Export s | End-to-end s |
|---|---|---|---:|---:|---:|---:|
| legacy_strict | maximum_iterations | failed | 9.6041e-01 | 8.02 | 0.00 | 10.59 |
| curve_only | maximum_iterations | not_requested | 9.6041e-01 | 1.87 | 0.00 | 1.93 |
| export_only | maximum_iterations | failed | 9.6041e-01 | 1.88 | 2.59 | 4.51 |

Policy contract passed: `True`.
Reconstruction convergence, field accuracy, and successful SDF delivery are separate outcomes.
