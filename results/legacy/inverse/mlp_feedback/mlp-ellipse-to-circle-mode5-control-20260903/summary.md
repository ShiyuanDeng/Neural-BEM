# Alternating MLP-SDF inverse

Target: `circle`; initialization contour: wrong `ellipse`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 9.288e-01 -> 1.510e-02 | 1.518e+00 -> 6.504e-01 | 3.831e-02 -> 1.515e-02 m | 60 | `maximum_iterations` |
| MOD | 9.278e-01 -> 1.987e-02 | 1.523e+00 -> 7.300e-01 | 3.831e-02 -> 1.853e-02 m | 55 | `no_decreasing_redistanced_step` |
