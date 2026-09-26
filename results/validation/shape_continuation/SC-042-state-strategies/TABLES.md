# SC-042 — matched state treatment

Rebuilt by `analyse.py` from JSON. 24/24 terminal paths; 0 exceptions; 0 pending.

| Case | Arm | RMS mm | Hausdorff mm | Radius mm | Loss | Work | Outcome | Audit |
|---|---|---:|---:|---:|---:|---:|---|---|
| circle_to_c | boundary | 0.0062807 | 0.033387 | 12.003 | 1.168e-13 | 551 | COMPLETED_SCHEDULE | False |
| circle_to_c | cap | 0.006281 | 0.033357 | 12.021 | 1.169e-13 | 551 | COMPLETED_SCHEDULE | True |
| circle_to_c | none | 0.0063427 | 0.040677 | 9.0813 | 1.241e-13 | 551 | COMPLETED_SCHEDULE | True |
| circle_to_c | once | 0.0062803 | 0.033539 | 11.943 | 1.168e-13 | 551 | COMPLETED_SCHEDULE | True |
| circle_to_star | boundary | 0.017756 | 0.045633 | 6.0674 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | cap | 0.017772 | 0.045831 | 6.0751 | 3.502e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | none | 0.017758 | 0.045576 | 6.0653 | 3.497e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | once | 0.017755 | 0.045578 | 6.0651 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |
| hook | boundary | 0.0021025 | 0.0058631 | 11.716 | 3.933e-15 | 893 | COMPLETED_SCHEDULE | True |
| hook | cap | 0.0021025 | 0.0058632 | 11.716 | 3.933e-15 | 893 | COMPLETED_SCHEDULE | True |
| hook | none | 0.0021025 | 0.0058756 | 11.716 | 3.933e-15 | 893 | COMPLETED_SCHEDULE | True |
| hook | once | 0.0021025 | 0.0058626 | 11.716 | 3.933e-15 | 893 | COMPLETED_SCHEDULE | True |
| kite | boundary | 0.027898 | 0.14075 | 1.0909 | 5.27e-11 | 1710 | COMPLETED_SCHEDULE | False |
| kite | cap | 0.02791 | 0.1409 | 1.1009 | 5.076e-11 | 1710 | COMPLETED_SCHEDULE | False |
| kite | none | 0.047617 | 0.31584 | 0.09326 | 4.817e-10 | 760 | NUMERICAL_FAILURE | True |
| kite | once | 0.027887 | 0.1412 | 1.2526 | 5.254e-11 | 1710 | COMPLETED_SCHEDULE | True |
| peanut | boundary | 0.0023358 | 0.0072914 | 14.055 | 4.68e-15 | 779 | COMPLETED_SCHEDULE | True |
| peanut | cap | 0.0023358 | 0.0072914 | 14.055 | 4.68e-15 | 779 | COMPLETED_SCHEDULE | True |
| peanut | none | 0.0023358 | 0.007291 | 14.055 | 4.68e-15 | 779 | COMPLETED_SCHEDULE | True |
| peanut | once | 0.0023358 | 0.0072913 | 14.055 | 4.68e-15 | 779 | COMPLETED_SCHEDULE | True |
| wrong_circle | boundary | 0.00024467 | 0.00036579 | 49.946 | 9.726e-16 | 114 | COMPLETED_SCHEDULE | True |
| wrong_circle | cap | 0.00024467 | 0.00036579 | 49.946 | 9.726e-16 | 114 | COMPLETED_SCHEDULE | True |
| wrong_circle | none | 0.00024467 | 0.00036579 | 49.946 | 9.726e-16 | 114 | COMPLETED_SCHEDULE | True |
| wrong_circle | once | 0.00024467 | 0.00036579 | 49.946 | 9.726e-16 | 114 | COMPLETED_SCHEDULE | True |

Evidence checks: 125/125.

The four interventions have the same allowance; actual work can differ. Cleanup can
increase the loss at a stage boundary. Last returned states are scored, not best-truth iterates.
Common-work checkpoints and floored comparisons are in `analysis.json`.

Exceptions remain in the 24-path denominator and prevent an arm from passing its six-case gate.
Geometric means describe available scored pairs; they are provisional until the full denominator is resolved.
