# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=6` at `ka = 4.15`, whose resolution estimate is `k=6`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.194e+00 -> 1.327e-01 | 1.054e+00 -> 3.400e-01 | 4.227e-02 -> 7.369e-03 m | 109 | `no_decreasing_redistanced_step` |
| MOD | 1.194e+00 -> 1.347e-01 | 1.059e+00 -> 3.411e-01 | 4.227e-02 -> 7.200e-03 m | 122 | `no_decreasing_redistanced_step` |
