# Alternating MLP-SDF inverse

Target: `circle`; initialization contour: wrong `circle`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 9.740e-01 -> 4.017e-04 | 1.416e+00 -> 4.253e-02 | 4.327e-02 -> 6.335e-04 m | 28 | `no_decreasing_redistanced_step` |
| MOD | 9.735e-01 -> 2.718e-03 | 1.383e+00 -> 8.394e-02 | 4.327e-02 -> 6.403e-04 m | 28 | `no_decreasing_redistanced_step` |
