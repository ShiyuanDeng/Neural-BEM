# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `star`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.194e+00 -> 4.409e-02 | 9.996e-01 -> 2.419e-01 | 4.311e-02 -> 4.855e-03 m | 58 | `no_decreasing_redistanced_step` |
| MOD | 1.198e+00 -> 5.054e-02 | 9.971e-01 -> 2.577e-01 | 4.311e-02 -> 4.757e-03 m | 56 | `no_decreasing_redistanced_step` |
