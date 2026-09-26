# SC-042 — matched state treatment

Rebuilt by `analyse.py` from JSON. Partial until all 24 paths return.

| Case | Arm | RMS mm | Hausdorff mm | Radius mm | Loss | Work | Outcome | Audit |
|---|---|---:|---:|---:|---:|---:|---|---|
| circle_to_star | boundary | 0.017756 | 0.045633 | 6.0674 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | cap | 0.017772 | 0.045831 | 6.0751 | 3.502e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | none | 0.017758 | 0.045576 | 6.0653 | 3.497e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | once | 0.017755 | 0.045578 | 6.0651 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |

Evidence checks: 21/21.

The four interventions have the same allowance; actual work can differ. Cleanup can
increase the loss at a stage boundary. Last returned states are scored, not best-truth iterates.
Common-work checkpoints and floored comparisons are in `analysis.json`.
