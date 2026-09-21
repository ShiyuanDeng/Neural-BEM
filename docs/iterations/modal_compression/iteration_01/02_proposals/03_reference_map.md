# Reference map and theoretical claims

Reviewed 2026-09-21. The new 34-page
[theoretical report](<../../Theoretical Foundations of Geometry-Spectrum–Adaptive Modal Müller Compression.pdf>)
is a secondary research synthesis. This map distinguishes checked primary
results, repository evidence, and proposed extensions. It is not a complete
priority search or verification of every citation in the PDF.

## Short reading sequence

| Source | Checked support | What it does not establish for this project |
|---|---|---|
| [Boubendir–Domínguez–Turc, 2016](https://doi.org/10.1093/imanum/drv010), [author preprint](https://arxiv.org/pdf/1404.1331) | Theorem 2.1 and Eq. (2.10) support the smoothing differences and the nu=1 second-kind transmission system. The regularized hypersingular formula agrees with the report's Maue convention | Explicit entrywise tail constants uniform over a changing shape family, an adaptive mask, or a speedup |
| [Boriskina et al., 2004](https://doi.org/10.1364/JOSAA.21.000393) | Direct dielectric trigonometric Galerkin precedent with analytic singularity extraction | Novelty of Fourier–Galerkin Müller alone, or sparse derivative families |
| [Cai–Xu, 2008](https://doi.org/10.1137/070703478) | Publisher abstract: smooth-kernel compact-part compression with O(n log n) entries, a structured fast solve and convergence | Automatic transfer to the four weighted transmission blocks |
| [Jiang–Wang–Yu, 2021](https://link.springer.com/article/10.1007/s11075-021-01082-0) | Publisher abstract confirms convolution/compact splitting, O(n) retained entries and conditional exponential convergence for its Helmholtz equations | A frequency-uniform small-matrix guarantee, transmission derivative preservation, or an available fast implementation here |
| [Fang–Jiang–Su, 2025](https://doi.org/10.1016/j.apnum.2025.07.013), [2024 preprint](https://arxiv.org/html/2408.02199v1) | Publisher confirms journal version. Preprint treats Laplace on toroidal surfaces; directional Fourier decay and stable truncation. Theorem 4.2 includes `q*b >= p/2` and sufficiently large resolution | Direct theorem for 2D Helmholtz Müller; an arbitrary fixed `q=2` guarantee; our sampled root search as a certified strip |
| [Costabel–Le Louër, Part I](https://doi.org/10.1007/s00020-012-1954-z), [preprint](https://arxiv.org/abs/1105.2474) | Primary preprint identity checked; shape-calculus framework for operator/pullback differentiation | Uniform compression of all directions. Full theorem hypotheses were not independently re-audited in this review |
| [Ryan–Damle, 2021](https://arxiv.org/abs/2001.11619) | Primary abstract explicitly describes efficient factorization updates under local geometric perturbations and shape optimization | Performance on our Helmholtz inverse, but enough to refute “monolithic factorization cannot reuse changes” |
| [Goal-oriented, model-constrained optimization for reduction of large-scale systems](https://www.sciencedirect.com/science/article/pii/S0021999106005535) | Publisher search excerpt supports output-targeted basis selection as prior art; full page was unavailable on subsequent open | A Müller-specific estimator or novelty merely from targeting an objective |

## The useful theoretical bridge

Use fixed material physics and the exact state convention `(u, q=J*u_N)`.
The published mapping result gives three-order regularization for the
single-layer difference and one order for the hypersingular difference;
the double-layer operators gain three orders on smooth planar curves.
The smooth weight/pullback preserves these order statements on a fixed
nondegenerate curve. It does not make their constants uniform as the geometry
degenerates. [Boubendir–Domínguez–Turc](https://arxiv.org/pdf/1404.1331).

The proposed entry envelope then needs extra quantitative work. For a periodic
symbol `a(t,n)`, the matrix entry is its coordinate Fourier coefficient at
`m-n`. Smoothness in `t` can control separation from the diagonal while symbol
order controls dependence on `n`. A fully smooth bivariate remainder instead
has two-index Fourier decay. These are different structures; one uniform
diagonal band need not be the right compression pattern for both.

The new report is careful to label its geometry-explicit envelope as a theorem
target. This review agrees. Mapping properties alone do not establish that
specific envelope, usable constants or uniform stability. Additional controls
must cover speed/Jacobian lower bounds, nonlocal chord separation, physical
frequency, coordinate regularity and the inverse norm in the selected scaling.

## Do not rediscover completed work

The repository already has the weighted state, exact logarithmic Fourier
coefficients, bivariate log amplitudes, Maue assembly, and an explicit principal
log extraction. See
[transmission.py](../../../../../experiments/laurent_literature/transmission.py).
LAU-002 compared identity, full-log and principal-log protection. None of the
extra protected variants lowered the smallest successful count.

The new report's warning against calling “everything except a diagonal
singularity” smooth is correct. It is not evidence that the existing native
split made that mistake: the native and hybrid assemblers convolve the full
bivariate log amplitude with the known symbol. Block-dependent allocation,
coordinate effects and physical output control remain distinct questions.

## Further corrections and limits

1. **The 2021 paper was already investigated more deeply here than in the new
   report.** The report explicitly relies on its abstract. LAU-002 records
   full-PDF provenance and the actual index convention, stretched-exponential
   bound and unresolved printed-table discrepancies. Preserve that evidence;
   do not replace it with the looser phrase “exponential convergence.” This
   review verified the publisher record but did not redownload and independently
   recheck all of those theorem/table pages.
2. **The FJS preprint's width is not our numerical width.** Its theorem uses
   sufficient analytic/geometric bounds. The later repository routine seeks
   a nearest complex root by finite sampling and local minimization. A found
   root suggests an obstruction; failure to find one does not certify a strip.
   Nor does a finite fitted decay slope have to equal a theorem's admissible
   exponential rate. Its fixed-q sweep is a numerical adaptation.
3. **Circle selection rules need physical directions.** At the circle,
   `delta z = d_q exp(i*q*t)` has normal component
   `Re(d_q exp(i*(q-1)*t))`. A pulled-back matrix also responds to coordinate
   transport. Use physical normal harmonics when testing a sideband theorem;
   record Cartesian indices separately.
4. **An adjoint estimate changes the target, not the mathematics of differentiation.**
   A good physical gradient from approximate traces can coexist with a bad
   derivative of the approximate forward model. MC-001 explicitly measures
   both; an eventual optimization method must control that discrepancy.
5. **The report has a conjugation inconsistency.** Its p. 3 inner product and
   pp. 3–4 matrix-coefficient formulas cannot both hold as written. With the
   stated first-argument-linear inner product, use `<B e_n,e_m>` for the
   usual matrix. This is a repair to notation, not a disproof of its main claim.

## What would be a useful research contribution

Three independent outcomes could justify work:

- a quantitative, validated error bound that chooses resolution/retention
  before computing the dense matrix;
- a derivative/output-preserving approximation that changes the time, memory
  or reliability of a named inverse workload;
- a clear limit law identifying when frequency, regularity or parametrization
  destroys useful compression, with untouched validation cases.

Each needs evidence beyond a sparse image, a fitted line or a novelty score.
Theoretical error control can be valuable without an inverse speedup, provided
that is the stated contribution. Neither the report nor this review establishes
priority or guarantees publishability.
