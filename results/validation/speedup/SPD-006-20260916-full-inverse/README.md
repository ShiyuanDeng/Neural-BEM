# SPD-006 — compiled Kress continuation in full inverse workers

Status: **COMPLETE_QUALITY_PRESERVED**. Raw evidence: [summary.json](summary.json).

| Scene | Reciprocal + readiness | Compiled + readiness | Ratio |
|---|---:|---:|---:|
| death | 46.124 s | 46.149 s | 0.999x |
| merge | 171.724 s | 171.854 s | 0.999x |
| central-ellipse-star | 1098.371 s | 1049.405 s | 1.047x |
| far-two-stars | 1367.985 s | 1291.664 s | 1.059x |

Medians use completed workers; repeat counts are in summary.json. Failed recovery outcomes are retained.
Ratios are measured full-worker wall times. They are not estimates for all twelve topology scenes.
Both arms use the original data, Cartesian gauge, controller, feasibility rules and training-only readiness.
Compiled frequency batches, local factorizations and reduced solves are distinct from full physical systems.
Physical budget attempts include failures/refusals. Completed physical systems reconcile with passive inverse counts plus direct readiness/endpoint predictions.
Source and input snapshots are in manifest.json and measured_sources. Qualification and regression evidence are included.

## Remaining cost

One compiled central-case update took 26.96 s under CPU profiling; legacy stencil feasibility used 88.5%.
It reproduced the archived first accepted state exactly. Nested profile times must not be added.
This is one update, not a whole-inverse percentage. See [profile.txt](remaining_cost_profile/profile.txt) and [profile summary](remaining_cost_profile/summary.json).

The compiled runtime selects the numerical backend; the benchmark wrapper separately enables readiness.
A file-only monitor read logs every 55 seconds during sequential workers. Host-wide isolation is unverified.
The summary/profiling sources are archived separately from the frozen numerical sources.
