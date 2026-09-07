# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=5` at `ka = 6.91`. The wave and 24-angle limits are respectively `k=9` and `k=11`.

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
| KRESS | 1.193e+00 -> 7.998e-01 | 1.139e+00 -> 1.073e+00 | 4.222e-02 -> 4.692e-02 m | 56 | `representation_limited_stationary` |
