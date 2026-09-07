# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=5` at `ka = 6.91`. The wave and 24-angle limits are respectively `k=9` and `k=11`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.194e+00 -> 1.039e+00 | 1.003e+00 -> 1.043e+00 | 4.203e-02 -> 4.667e-02 m | 25 | `spectral_tail_growth_limit` |
