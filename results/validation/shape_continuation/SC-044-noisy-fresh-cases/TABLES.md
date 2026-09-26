# SC-044 — fresh shapes and measurement noise

9/18 terminal suffix paths; 0 prefix/suffix exceptions; 9 pending.

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

Unique prefix work: 1766; suffix work: 3876.
Each complete path is charged its shared prefix. Two noise draws are repeated measurements of the same two shapes, not additional independent targets.
