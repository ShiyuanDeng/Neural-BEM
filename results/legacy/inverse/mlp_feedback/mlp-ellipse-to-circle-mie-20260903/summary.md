# Alternating MLP-SDF inverse

Target: `circle`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=3` at `ka = 1.38`, whose resolution estimate is `k=3`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 9.288e-01 -> 1.457e-02 | 1.518e+00 -> 4.940e-01 | 3.831e-02 -> 6.050e-03 m | 77 | `no_decreasing_redistanced_step` |
| MOD | 9.278e-01 -> 1.444e-02 | 1.523e+00 -> 5.089e-01 | 3.831e-02 -> 6.152e-03 m | 57 | `no_decreasing_redistanced_step` |
