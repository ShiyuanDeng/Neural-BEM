# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=5` at `ka = 6.91`. The wave and 24-angle limits are respectively `k=9` and `k=11`.

The accepted optimization state is a canonical ordered boundary. Modal
finite-difference probes act directly on that boundary; every accepted
contour is re-distanced into the tanh MLP and audited, but representation
error is not recycled into the next geometry Jacobian.
Training uses cumulative low-to-high frequency stages; each trajectory
row names its active stage because loss values are objective-local.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.194e+00 -> 1.031e+00 | 1.003e+00 -> 9.430e-01 | 4.203e-02 -> 2.783e-02 m | 15 | `no_acceptable_mlp_distillation` |
