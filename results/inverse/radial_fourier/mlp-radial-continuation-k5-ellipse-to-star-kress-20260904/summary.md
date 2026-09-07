# Alternating MLP-SDF inverse

Target: `star`; initialization contour: wrong `ellipse`.

Update basis: modes through `k=5` at `ka = 6.54`. The wave and 24-angle limits are respectively `k=9` and `k=11`.

The accepted optimization state is a gauge-fixed star-shaped radial Fourier
curve. Its center, mean radius, and modes 2..K are authoritative, so repeated
finite-difference steps cannot create geometry above K. Every accepted contour
is re-distanced into the tanh MLP and audited, but representation error is not
recycled into the next geometry Jacobian.
Training uses cumulative low-to-high frequency stages (the safe default);
each trajectory row records its objective because stage losses are local.
The driver exit check demonstrates strict training progress only; it is not a
convergence or reconstruction-accuracy certificate.

| Solver | Train rel. L2 initial -> final | Holdout rel. L2 initial -> final | Max boundary error initial -> final | Accepted updates | Stop |
|---|---:|---:|---:|---:|---|
| KRESS | 1.202e+00 -> 1.068e-08 | 1.133e+00 -> 1.339e-08 | 4.181e-02 -> 2.570e-10 m | 44 | `representation_limited_stationary` |
