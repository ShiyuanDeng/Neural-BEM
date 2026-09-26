# SC-044 — fresh shapes and measurement noise

16/18 terminal suffix paths; 0 prefix/suffix exceptions; 2 pending.

| Shape | Data | State strategy | RMS mm | Hausdorff mm | Complete path work | Outcome | Audit |
|---|---|---|---:|---:|---:|---|---|
| asymmetric_lobes | clean | boundary | 0.010827 | 0.03357 | 863 | COMPLETED_SCHEDULE | True |
| asymmetric_lobes | clean | cap | 0.010827 | 0.033569 | 863 | COMPLETED_SCHEDULE | False |
| asymmetric_lobes | clean | none | 0.010827 | 0.033574 | 863 | COMPLETED_SCHEDULE | True |
| asymmetric_lobes | noise_seed_0 | boundary | 0.067808 | 0.20125 | 451 | DISCREPANCY_REACHED | False |
| asymmetric_lobes | noise_seed_0 | cap | 0.067808 | 0.20126 | 451 | DISCREPANCY_REACHED | True |
| asymmetric_lobes | noise_seed_0 | none | 0.067808 | 0.20125 | 451 | DISCREPANCY_REACHED | True |
| asymmetric_lobes | noise_seed_1 | boundary | 0.11338 | 0.33304 | 384 | DISCREPANCY_REACHED | True |
| asymmetric_lobes | noise_seed_1 | cap | 0.11338 | 0.33306 | 384 | DISCREPANCY_REACHED | True |
| asymmetric_lobes | noise_seed_1 | none | 0.11338 | 0.33304 | 384 | DISCREPANCY_REACHED | True |
| deep_c | clean | boundary | 0.07327 | 0.38461 | 1343 | COMPLETED_SCHEDULE | True |
| deep_c | clean | cap | 0.073293 | 0.38774 | 1343 | COMPLETED_SCHEDULE | True |
| deep_c | clean | none | 0.073616 | 0.48202 | 1343 | COMPLETED_SCHEDULE | True |
| deep_c | noise_seed_0 | boundary | 0.15805 | 0.59938 | 905 | DISCREPANCY_REACHED | True |
| deep_c | noise_seed_0 | cap | 0.15768 | 0.59823 | 905 | DISCREPANCY_REACHED | True |
| deep_c | noise_seed_0 | none | 0.35351 | 1.6091 | 829 | NUMERICAL_FAILURE | True |
| deep_c | noise_seed_1 | none | 0.10769 | 0.70304 | 898 | DISCREPANCY_REACHED | True |

Unique prefix work: 1766; suffix work: 8246.
Saved-evidence checks: 95/95.
Each complete path is charged its shared prefix. Two noise draws are repeated measurements of the same two shapes, not additional independent targets.

The JSON also reports the last accepted states within a common work allowance for each paired comparison. This post-fit analysis does not select the best truth iterate or change the original endpoint gate. Intermediate common-work states have the original fitting acceptance checks, not a new endpoint audit.

Post-fit observation check: the two realized noise losses are 1.0584× expected (0.8747× the discrepancy threshold), 1.0388× expected (0.8585× the discrepancy threshold). These ratios match across shapes because standardized draws are shared. Both truths lie inside the declared discrepancy; these truth residuals never choose the fitting stop.
