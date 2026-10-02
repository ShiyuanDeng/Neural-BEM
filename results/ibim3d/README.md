# Three-dimensional scalar sphere IBIM feasibility

Implemented and run the ranked document's sphere control: a Cartesian grid
samples the analytic sphere SDF, narrow-band quadrature produces boundary
integrals, and a scalar equal-density Müller transmission solve is compared
with an independent spherical Bessel/Hankel series. Radius is the unit of
length; interior/exterior squared-wavenumber ratio is 4; incident field is
`exp(i k_e z)`; 31 receivers lie at radius 3R on the x-z meridian.
The reported L2 error therefore samples that meridian, not every azimuth of
the Cartesian-grid discretization.

The finest wide-band runs give **1.28e-4** relative field error at kR=1 and **4.95e-4**
at kR=3, using 3,858 surface unknowns (7,716 trace unknowns). This is a
sphere-only feasibility result; neither general 3-D geometry nor Maxwell
transmission has been implemented or validated.

[All measurements](convergence.csv) ·
[Initial convergence plot](sphere-20261002/convergence.png) ·
[Refined grid](sphere-refined-20261002/convergence.json) ·
[Wider band](sphere-wideband-20261002/convergence.json)

| h/R | half-band/R | surface unknowns | stored matrix MB | field error kR=1 | field error kR=3 |
|---:|---:|---:|---:|---:|---:|
| 0.35 | 0.525 | 338 | 7.3 | 0.000873 | 0.0116 |
| 0.28 | 0.420 | 507 | 16.5 | 0.00118 | 0.00471 |
| 0.22 | 0.330 | 805 | 41.5 | 0.000497 | 0.00248 |
| 0.17 | 0.255 | 1,341 | 115.1 | 0.000444 | 0.00236 |
| 0.13 | 0.195 | 2,254 | 325.2 | 0.000298 | 0.000749 |
| 0.10 | 0.150 | 3,801 | 924.6 | 0.000154 | 0.00079 |
| 0.17 | 0.425 | 2,310 | 341.5 | 0.000112 | 0.000685 |
| 0.13 | 0.325 | 3,858 | 952.6 | 0.000128 | 0.000495 |

Memory is **matrix storage only**, not peak RSS; LU and assembly temporaries
require additional memory. The largest run took about 20 seconds on CPU,
including about 17 seconds for dense LU, while other experiments were running.
These are descriptive timings. The kR=3 error is not monotone with grid spacing
at a fixed 1.5h band. Increasing the band to 2.5h improves the measured error;
no asymptotic convergence order is asserted.

## Formulation and evidence

[Kublik, Tanushev and Tsai's implicit-interface formulation](https://www.oden.utexas.edu/media/reports/2012/1217.pdf)
provides the coarea/closest-point foundation. That paper studies Poisson
problems, so the Helmholtz transmission algebra below is explicitly a derived
extension for this sphere experiment.

For `d(x)=|x|-R`, the closest point is `P(x)=R*x/|x|` and its tangential
Jacobian is `(R/|x|)^2`. The quadrature weights are

```text
w_j = h^3 δ_ε(d(x_j)) (R/|x_j|)^2,
δ_ε(s) = (1 + cos(πs/ε))/(2ε), |s|<ε.
```

Coincident projected points are merged by adding weights. A translated grid
avoids systematic alignment; no area renormalization is applied. Four tests
check area/centroid moments, radial derivative formulas, a nonconstant
spherical-harmonic operator action, and refinement against independent 3-D Mie.

The outgoing Green function is `G_k(r)=exp(ikr)/(4πr)` under `exp(-iωt)`.
The same total traces `(u,q)` as in the 2-D equal-density solver obey

```text
[I - (K_e-K_i),    V_e-V_i    ] [u] = [u_inc]
[  -(T_e-T_i), I + (K'_e-K'_i)] [q]   [q_inc].
```

The leading singularity cancels in the difference kernels, leaving a weak
`1/r` term in ΔT. We subtract the local density and restore the exact action
on a constant. **That correction uses the sphere**, with eigenvalues

```text
V_l(k) = i k R² j_l(kR) h_l^(1)(kR),
K_l(k) = i k² R² j'_l(kR) h_l^(1)(kR) - 1/2,
T_l(k) = i k³ R² j'_l(kR) h_l^(1)'(kR).
```

For example `T f = Σ_{j≠i} T_ij w_j (f_j-f_i) + T_0 f_i`.
Only l=0 is used in assembly; the l=1 action and full plane-wave Mie series
are independent checks. A power series evaluates cancelled radial kernels
near zero without subtracting singular floating-point quantities.

The correction cannot be copied to a non-sphere by assuming the same row
integrals. General 3-D SDF transmission needs a qualified local singular
quadrature and its geometry derivatives. Dense memory also scales as the
square of the narrow-band point count, while LU is cubic. These measured and
derived limits are the evidence against promoting this prototype into the
neural inverse pipeline.

## Reproduction

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.ibim3d.sphere --output NEW_COARSE
$PY -m experiments.ibim3d.sphere --output NEW_FINE --spacing .13 .1
$PY -m experiments.ibim3d.sphere --output NEW_WIDE --spacing .17 .13 --width-factor 2.5
$PY -m pytest -q experiments/ibim3d/test_sphere.py
```
