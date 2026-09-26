# SC-042 — matched state treatment

Rebuilt by `analyse.py` from JSON. 5/24 terminal paths; 0 exceptions; 19 pending.

| Case | Arm | RMS mm | Hausdorff mm | Radius mm | Loss | Work | Outcome | Audit |
|---|---|---:|---:|---:|---:|---:|---|---|
| circle_to_star | boundary | 0.017756 | 0.045633 | 6.0674 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | cap | 0.017772 | 0.045831 | 6.0751 | 3.502e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | none | 0.017758 | 0.045576 | 6.0653 | 3.497e-12 | 1159 | COMPLETED_SCHEDULE | True |
| circle_to_star | once | 0.017755 | 0.045578 | 6.0651 | 3.496e-12 | 1159 | COMPLETED_SCHEDULE | True |
| kite | none | 0.047617 | 0.31584 | 0.09326 | 4.817e-10 | 760 | NUMERICAL_FAILURE | True |

Evidence checks: 25/25.

The four interventions have the same allowance; actual work can differ. Cleanup can
increase the loss at a stage boundary. Last returned states are scored, not best-truth iterates.
Common-work checkpoints and floored comparisons are in `analysis.json`.

Exceptions remain in the 24-path denominator and prevent an arm from passing its six-case gate.
Geometric means describe available scored pairs; they are provisional until the full denominator is resolved.
