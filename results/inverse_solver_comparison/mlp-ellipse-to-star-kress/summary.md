# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

The accepted state is a full tanh MLP. Modal fields are transient black-box
finite-difference probes; every accepted modal contour is re-distanced with
signed polygon-distance supervision plus Eikonal loss and then re-solved.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.191e+00 -> 9.249e-01 | 1.053e+00 -> 1.024e+00 | 4.222e-02 -> 4.214e-02 m | 6 | `maximum_iterations` |
