# Fourier-Galerkin Müller operators and the published compression rules

Isolated research code testing the 2026-09-18 report
[*Explicit-Boundary BIE/FWI for Scattering*](../../docs/iterations/laurent/Explicit-Boundary%20BIE_FWI%20for%20Scattering_%20Literature%20Review,%20Novelty%20Assessment,%20and%20Research%20Roadma.pdf).
Measurements live in [`results/experiments/laurent_fgm_20260918/`](../../results/experiments/laurent_fgm_20260918/README.md).

`experiments/modal_muller_research/` and `solvers/` are **read-only imports**.
The only thing imported from the hash-pinned research package is
`coefficient_operator.kernel_matrix`, the exact log-symbol contraction; nothing
here modifies it and no production default is touched.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/fgm-matplotlib
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

$PY -m pytest -q experiments/laurent_fgm
$PY -m experiments.laurent_fgm.run_decay       --output <fresh>/decay
$PY -m experiments.laurent_fgm.run_refinement  --output <fresh>/refinement
$PY -m experiments.laurent_fgm.run_multiobject --output <fresh>/multiobject
$PY -m experiments.laurent_fgm.run_scaling     --output <fresh>/scaling
$PY -m experiments.laurent_fgm.run_broadband   --output <fresh>/broadband
$PY -m experiments.laurent_fgm.run_penalty     --output <fresh>/penalty
$PY -m experiments.laurent_fgm.run_affine      --output <fresh>/affine
$PY -m experiments.laurent_fgm.run_transfer    --output <fresh>/transfer
$PY -m experiments.laurent_fgm.plot_findings   --bundle <fresh>
```

## What the assembler is, and why it was needed

`assembler.py` is the report's **stage 2**: hybrid analytic/spectral
Fourier-Galerkin Müller assembly,

```
A = A_universal_sing + A_smooth
```

with `log(4 sin²((t-s)/2))` handled analytically through its exact coefficients
`L_ℓ = -1/|ℓ|`, and the smooth two-variable amplitudes sampled on an
oversampled tensor grid and transformed by FFT. Amplitudes are **closed-form
Hankel/Bessel expressions**, not power series.

That last point is the whole reason it exists. The existing node-free assembler
reconstructs the same operator through a Bessel power series in `R²`, which
cancels catastrophically at large argument — the Laurent track records it good
at 2.5 GHz and broken at 5 GHz. That ceiling is a property of the *series*, not
of the formulation: with closed-form amplitudes the same Galerkin operator is
exact at `kD = 60`. Every kD = 30 measurement in this package depends on that.

| Module | Owns |
|---|---|
| `assembler.py` | `FourierGalerkinMuller` (blocks `[[I-K, V], [-T, I+K']]`, Maue before truncation), point-source traces, receiver operator |
| `curves.py` | Literature boundaries (circle, ellipse, Kress kite, non-star-shaped crescent, corrugated) and **`analyticity_halfwidth`** — `b*` from the Laurent coefficients alone |
| `decay.py` | Band profiles, exponential-rate fits, the FJS band and the JWY mask, the four report errors |
| `multiobject.py` | Local responses `S_j = R_j A_j⁻¹ B_j`, Graf translation, monolithic control |
| `run_decay.py` | Decisive experiment 1: decay law vs `b*`, smallest band per accuracy target, field **and** gradient |
| `run_refinement.py` | The compression papers' own regime: fixed kD, refined N |
| `run_multiobject.py` · `run_scaling.py` | Decisive experiment 2: separation sweep, selective reuse, and the J crossover |
| `run_broadband.py` | Decisive experiments 3 and 4: the three ranks, held-out ROM, preconditioner reuse |
| `run_penalty.py` | How the gradient's band penalty scales with the shape parameterisation's mode content, and the decay exponent refitted on the decaying region alone |
| `run_affine.py` | Whether the broadband operator rank is an affine model you can use: projection floor vs spline interpolation of `θ_r(k)` at held-out frequencies, and what the sampling costs |
| `run_transfer.py` | Whether one offline basis survives the boundary moving — `LU(Â(k, c₀))` as a preconditioner for `A(k, c)`, against the single-anchor control |

## `b*` is the geometry quantity that matters

Fang-Jiang-Su 2024 ([arXiv:2408.02199](https://arxiv.org/abs/2408.02199),
Corollary 3.1) bound the Fourier-Galerkin representation matrix by
`|K_kl| ≤ (M/2π) exp(-b‖l-k‖₁)` for every `b < b*`, with `b*` the half-width of
the analyticity strip of the boundary parameterisation. For a closed Laurent
curve the obstruction is a **complexified self-intersection**: with `u = e^{it}`,

```
W(u,v) = -u v (z(u)-z(v)) (z̄(u)-z̄(v)) / (u-v)²
```

equals `R²/(4 sin²((t-s)/2))` on the real torus, and `b*` is the largest `β`
with `W ≠ 0` for `|u|,|v| ∈ [e^{-β}, e^{β}]`. `analyticity_halfwidth` finds it by
rooting the divided difference, and reproduces the closed form
`b* = ½ log|A/B|` for an ellipse `z = Au + B/u` to machine precision.

**`b*` is not "geometry bandwidth".** The `crescent` (modes `|j| ≤ 2`) and the
`corrugated` boundary (modes up to `|j| = 9`) were chosen as a discriminating
pair: they have close `b*` (0.091 vs 0.108) and close measured decay rates
(0.156 vs 0.171 at kD = 30) despite a 4.5× difference in mode content.

## Validation, and what it is worth

| Check | Result |
|---|---|
| FFT Galerkin vs `CoefficientGeometry.assemble` (circle/ellipse/star, ko = 64) | `2.6e-15` – `4.6e-14` |
| Same at ko = 160, where the power series is near its limit | `5.4e-12` – `1.0e-11` |
| Circle receiver field vs analytic Mie, kD = 2 / 10 / 30 / 60 | `1.7e-15` / `3.7e-15` / `1.6e-14` / `2.8e-14` |
| Local response `S` vs analytic Mie coefficients | `8.0e-16`; off-diagonal `1.3e-16` |
| Graf translation operator, direct field re-expansion | `7.4e-12` |
| Two-object local solve vs monolithic Müller | `4.0e-15` |
| Selective reuse (rebuild one object) vs rebuild all | bitwise identical |

Shape gradients are central differences through the whole pipeline; every run
records a step-size consistency number (step vs 4× step) so the finite-difference
floor is visible next to the truncation errors it is used to measure.

## Standing limits

Same physics as the rest of the Laurent work: lossless, equal permeability,
scalar TMz, one interface per component, disjoint bounding circles, external
sources and receivers. The contrast is the project's GPR acquisition,
`ε_r 6 → 3`, so `k_i/k_o = 1/√2`.

Curves are normalised to **unit diameter**, so `k = kD` throughout and the
electrical size is read directly. The near-touching rows of the separation sweep
carry a `monolithic_grid_control` column: below a `0.06 λ` gap the FFT-quadrature
monolithic reference is itself not converged at the stated grid, and those
comparisons are inconclusive rather than negative.
