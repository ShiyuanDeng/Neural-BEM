# Nyström Reference Solver — Convergence Study

2026-08-25

## What this is

A standalone explicit-boundary Nyström solver for the 2D TMz transmission
problem, living in `solvers/nystrom_ref/`. It is an **oracle**, not a production
solver: forward only, no SDF, no adjoint, no inverse, not differentiable.

It exists to answer one question — *how accurate should this BIE be on a smooth
shape when geometry and quadrature are not the limiting factors?* — and thereby
to bound whether the corrected volumetric IBIM redesign (issue 2) is worth
attempting.

It is a **sibling** of `gpr_bem_ref` / `gpr_bem_mod`, not a module inside either.
Two reasons. An oracle that imports the machinery it judges shares its bugs. And
the shared `pytest/` suite resolves the bare name `gpr_bem` to one package at a
time, so a reference buried in `gpr_bem_mod` would vanish under `--solver=ref`.
It shares only the *definition of the problem* — `config/simulation_config.py`,
`EPS0`/`MU0`, the `Material` wavenumber convention, and the
`0.25j * H_0^(1)(k r)` line-source normalisation. All numerics are written from
scratch.

## The design decision that made this cheap

The plan for this solver budgeted a two-phase quadrature effort, with Phase 2
adding "Kress/Alpert-style corrections, especially for S, D, K', and the weakly
singular W_out - W_in difference", and rated high-order hypersingular quadrature
as the medium-confidence risk.

**No hypersingular quadrature is needed anywhere, and the singularity ranking is
the other way round.**

For TMz with non-magnetic media both traces are continuous, so the Müller blocks
are *pure* exterior-minus-interior differences with no material weighting. Take
those differences analytically, at the kernel level, and the leading singularity
of every block cancels, because in each case that leading term is
**k-independent**:

| block | kernel | leading term | after the difference |
|---|---|---|---|
| `dS` | `(i/4)[H0(ke r) - H0(ki r)]` | `ln r`, coeff `-1/2pi` | **bounded** (`const + O(r^2 ln r)`) |
| `dD` | `(i/4) d[k H1(k r)] (r.ny)/r` | `1/r`, coeff `-2i/pi` | **bounded** |
| `dK'` | same with `(r.nx)/r` | `1/r` | **bounded** |
| `dT` | `(i/4)[nx.ny d(kH1)/r - (r.nx)(r.ny)/r^2 d(k^2 H2)]` | `1/r^2` | **`O(ln r)`** |

So the hypersingular block is the only one with any singularity left, and it is
merely logarithmic. One Kress/Kussmaul-Martensen log rule handles the entire
system. No Maue/Günter regularisation, no finite-part integrals.

This is variant (D) of `ibim_error_mitigation_literature_codex.md` §4b.4, which
was scoped and never built. The differences must be formed **symbolically** —
subtracting two assembled `O(1/r^2)` matrices is exactly the cancellation §4.3
warns against.

The log split needs the coefficient of `ln r` in each kernel. It is free: the
coefficient of `ln r` in `H_n^(1)(k r)` is `i (2/pi) J_n(k r)`, so `M1` is the
same expression as the kernel with every Hankel replaced by the corresponding
Bessel and the prefactor `i/4` replaced by `-1/(2 pi)`.

## Circle against the Fourier–Bessel series

Analytic circle R = 0.05 m, 12 bistatic pairs on a 0.27 m ring, float64.
`pts/lam` counts exterior wavelengths.

| f (GHz) | N | pts/lam | abs err | rel err | cond(A) | residual | leak |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 128 | 99.7 | 1.39e-14 | 6.58e-13 | 1.19e+02 | 5.3e-16 | 1.0e-15 |
| 0.5 | 1024 | 797.9 | 1.52e-15 | 7.21e-14 | 1.19e+02 | 7.6e-16 | 2.4e-15 |
| 1.5 | 128 | 33.2 | 1.14e-13 | 8.27e-12 | 4.39e+03 | 4.7e-15 | 1.0e-15 |
| 1.5 | 1024 | 266.0 | 1.96e-14 | 1.43e-12 | 4.39e+03 | 1.0e-15 | 6.1e-16 |
| 2.0 | 128 | 24.9 | 4.43e-13 | 1.92e-10 | 9.90e+03 | 4.0e-15 | 1.3e-15 |
| 2.0 | 1024 | 199.5 | 8.00e-14 | 3.47e-11 | 9.90e+03 | 2.1e-15 | 5.0e-16 |
| 2.5 | 128 | 19.9 | 6.01e-13 | 5.45e-11 | 1.21e+04 | 3.4e-15 | 1.5e-15 |
| 2.5 | 1024 | 159.6 | 1.09e-13 | 9.87e-12 | 1.21e+04 | 5.0e-15 | 7.8e-16 |
| 4.0 | 128 | 12.5 | 1.49e-12 | 1.89e-10 | 3.52e+04 | 4.6e-15 | 7.2e-15 |
| 4.0 | 1024 | 99.7 | 2.71e-13 | 3.44e-11 | 3.52e+04 | 5.3e-15 | 2.2e-15 |
| 8.0 | 128 | 6.2 | 6.57e-11 | 3.15e-08 | 5.06e+05 | 8.6e-15 | 1.4e-14 |
| 8.0 | 1024 | 49.9 | 1.27e-11 | 6.09e-09 | 5.06e+05 | 3.3e-14 | 3.4e-15 |

`leak` is the convention check: `D_e u_inc - S_e q_inc` must vanish identically
outside the scatterer, and does, to machine precision. It fails loudly on a
flipped normal or a wrong jump-relation sign, which is the failure mode a
convergence study is blind to.

**The solver is converged at N = 128 at every frequency in the band.** Refining
further buys nothing: the residual decay is `O(1/N)`, not spectral, because the
remaining error is dominated by the `epsilon`-limit used for the diagonal
quadrature entries (see below), and one diagonal entry enters the operator with
weight `h = 2 pi / N`. That floor sits at `~1e-11` absolute worst case, five to
eight orders of magnitude below anything in this project.

### The diagonal limit, and why it is not the §4b mistake

`M2 = M - M1 log(4 sin^2(...))` is continuous across the diagonal but has no
convenient closed form. It is recovered by evaluating slightly off-diagonal at
`t +- eps` and `t +- 2 eps` and Richardson-extrapolating, with `eps = 1e-3`.

This is deliberately *not* the pattern criticised in §4b. Nothing is differenced
and nothing is divided by `eps`: it is the limit of a continuous function at a
removable singularity, not a derivative. Shrinking `eps` costs accuracy only
through the cancellation inside `M - M1 log(...)`, never through `1/eps`
amplification. Two-sided averaging removes the linear term; Richardson removes
most of the `eps^2 log eps` term. The measured cost is the `1e-11` floor above.

## Identities and non-circular shapes

| check | result |
|---|---|
| zero contrast (`k_int = k_ext`), max abs scattered | 2.35e-17 (incident scale 3.97e-03) |
| ellipse path with `a = b` vs circle oracle | 4.66e-12 |
| star path with `amplitude = 0` vs circle oracle | 4.66e-12 |
| reciprocity on the star, `max|S - S^T| / max|S|` | 1.29e-11 |

The two degenerate-path checks matter more than they look. Self-convergence
(N → 2N → 4N) proves the *scheme* converges, not that it converges to the right
answer, and it is blind to a normal pointing the wrong way on a general curve.
Degenerating the general parameterisations back to a circle tests them against
the oracle. Both reproduce the circle result to the same digit, which is what a
shared correct code path looks like.

Self-convergence at 2.5 GHz, against the N = 1024 solution:

| shape | N=128 | N=256 | N=512 |
|---|---:|---:|---:|
| ellipse, 1.96:1 axis ratio | 1.86e-10 | 8.95e-11 | 3.27e-11 |
| star, `r0(1 + 0.25 cos 5t)` | 9.42e-10 | 4.59e-10 | 1.69e-10 |

## What this settles

**Issue 6 (8 GHz non-convergence) is not the formulation and not the physics.**
This is the single most informative row in the table. At 8 GHz the Nyström
solver reaches 3.15e-08 relative at **N = 128**, which is only 6.2 points per
exterior wavelength, and `cond(A) = 5.06e+05` — larger than at 0.5 GHz but
entirely workable. Müller is also resonance-free for transmission problems, so
there are no spurious interior resonances to confuse the diagnosis. Whatever
breaks at 8 GHz in the IBIM path is in the IBIM discretisation, not in the
integral equation being discretised.

**The 2 GHz spike is a metric artifact, as issue 5 argued.** The Nyström
relative error at 2.0 GHz (1.9e-10) is in line with its neighbours. There is no
structural difficulty at that frequency; the physical scattering null makes a
pure relative error misleading when the solver error is large, and that is all.

**The reference is qualified.** `gpr_bem_mod` currently sits at
`1.0e-4 / 2.6e-3 / 5.5e-3` at 0.5 / 1.5 / 2.5 GHz on 272 nodes. The Nyström
solver is five to eight orders of magnitude better at half that node count, so
it can serve as truth for any IBIM experiment without its own error entering the
comparison.

## What this does *not* settle

It shares the Müller formulation with `gpr_bem_mod`, so **it cannot
independently validate that formulation**. That question is already answered by
the conditioning collapse and the three-scheme control in
`validation_change_log.md`; this solver isolates quadrature and geometry only.

It also does not yet answer the question that actually decides issue 2. "Nyström
beats IBIM by five orders of magnitude" was close to a foregone conclusion —
spectral quadrature on an exact parameterisation against a low-order stand-off
approximation. The informative question is how much of the IBIM's residual error
is *bad quadrature* versus *bad node distribution*, since the IBIM's nodes come
from a compressed level-set band with irregular spacing and no amount of
singular-quadrature work fixes irregularity. The cheap experiment is to jitter
the uniform-`t` nodes here to match the IBIM's measured spacing statistics and
see how much accuracy survives. That is not done.

## Files

- `solvers/nystrom_ref/nystrom_tmz.py` — geometry, kernels, quadrature, assembly,
  evaluation.
- `solvers/nystrom_ref/__init__.py` — public surface.
- `pytest/test_nystrom_reference.py` — 11 tests, 14 s. Thresholds are loose by
  five or more orders of magnitude; this study is not rerun in the suite.
