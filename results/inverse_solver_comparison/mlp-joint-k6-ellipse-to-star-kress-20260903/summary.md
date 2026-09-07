# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=6` at `ka = 4.14`. The wave and 12-angle limits are respectively `k=6` and `k=5` (the requested basis exceeds a limit).

The accepted optimization state is a canonical ordered boundary. Modal
finite-difference probes act directly on that boundary; every accepted
contour is re-distanced into the tanh MLP and audited, but representation
error is not recycled into the next geometry Jacobian.
Training uses the default joint objective: one complete-band stage
with the full modal basis and the entire accepted-update budget.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.192e+00 -> 7.388e-01 | 1.053e+00 -> 9.353e-01 | 4.203e-02 -> 3.511e-02 m | 14 | `representation_limited_stationary` |
