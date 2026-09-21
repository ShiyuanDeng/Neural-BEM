# Testing the 2026-09-18 Laurent report's decisive experiments

**Run 2026-09-18.** Code: [`experiments/laurent_fgm/`](../../../experiments/laurent_fgm/README.md).
Source: the report *Explicit-Boundary BIE/FWI for Scattering: Literature Review,
Novelty Assessment, and Research Roadmap*, filed in
[`docs/iterations/laurent/`](../../../docs/iterations/laurent/).

The report proposes **geometry-spectrum–adaptive Fourier-Galerkin Müller
operators with coefficient-space shape derivatives** as the main direction, a
**differentiable multi-object local-response calculus** as the strongest
alternative, and names four decisive experiments with explicit success and kill
criteria. All four were run, against the literature it cites rather than against
this repository's existing conventions.

The report's first experiment is specified on the projected-Nyström diagnostic
`Ã_M = P* A_N P`, and says explicitly to use that "only as a diagnostic, not as
the final claimed Galerkin discretisation". Since stage 2 builds the true
Fourier-Galerkin operator, the compressibility question is answered here on that
operator directly, which removes projected-Nyström aliasing from the study
rather than having to argue around it.

No production default was changed. `solvers/` and
`experiments/modal_muller_research/` were imported read-only; the 30 tests of the
latter still pass, and the only symbol taken from it is the exact log-symbol
contraction `kernel_matrix`.

---

## 0. The assembler the report asks for, and the frequency ceiling

The report's stage 2 is a hybrid analytic/spectral assembly: treat the universal
log symbol analytically through its exact coefficients `L_ℓ = -1/|ℓ|`, sample the
smooth two-variable amplitudes on an oversampled tensor grid, and FFT. That was
built. The amplitudes are **closed-form Hankel/Bessel expressions**, which is the
one substantive departure from the existing node-free assembler.

It matters more than it sounds. The Laurent track records a hard frequency
ceiling — good at 2.5 GHz, broken at 5 GHz with 28 terms, still poor at 8 GHz.
That ceiling is a property of the **Bessel power series in `R²`**, which cancels
catastrophically at large argument. It is not a property of the Fourier-Galerkin
Müller formulation:

| Check | Result |
|---|---|
| FFT Galerkin vs `CoefficientGeometry.assemble`, ko = 64 | `2.6e-15` – `4.6e-14` |
| Same, ko = 160 (where the power series is near its limit) | `5.4e-12` – `1.0e-11` |
| Circle receiver field vs analytic Mie, **kD = 2 / 10 / 30 / 60** | `1.7e-15` / `3.7e-15` / **`1.6e-14`** / **`2.8e-14`** |

Every kD = 30 number below rests on this. **The electrical-size limit recorded
against the Laurent path was a series artefact and is now gone.**

---

## 1. The decay law is real, and `b*` predicts it

Fang-Jiang-Su 2024 ([arXiv:2408.02199](https://arxiv.org/abs/2408.02199),
Corollary 3.1) prove `|K_kl| ≤ (M/2π) exp(-b‖l-k‖₁)` for every `b < b*`, with
`b*` the analyticity strip half-width of the boundary and **no wavenumber in the
exponent**. For a Laurent curve `b*` is computable from `{z_j}` alone as the
largest strip free of complexified self-intersection; the implementation
reproduces the closed form `b* = ½log|A/B|` for an ellipse to machine precision.

Measured on the Müller `V` block, peak envelope per diagonal offset:

| curve | max mode | `b*` | rate kD=2 | kD=10 | kD=30 | `r²` | rate/`b*` at kD=30 |
|---|---|---|---|---|---|---|---|
| circle | 1 | ∞ | — exactly diagonal to `3e-16` — | | | | |
| ellipse | 1 | 0.310 | 0.437 | 0.442 | 0.379 | 0.98 | 1.22 |
| kite | 2 | 0.167 | 0.355 | 0.304 | 0.254 | 0.98 | 1.51 |
| crescent | 2 | 0.091 | 0.275 | 0.223 | 0.156 | 0.98 | 1.72 |
| corrugated | 9 | 0.108 | 0.211 | 0.182 | 0.171 | 0.99 | 1.59 |

**The law holds** (`r² = 0.93`–`0.99` across all 12 fitted cells; the circle needs
no fit, being diagonal) and **`b*` is a valid bound in every cell**
(rate/`b*` ∈ [1.2, 3.0], always ≥ 1, as the theorem requires).

**`b*`, not geometry bandwidth, is the predictor.** The crescent and the
corrugated boundary were built as a discriminating pair: modes `|j| ≤ 2` versus
`|j| ≤ 9`, a 4.5× difference in Fourier content, but close `b*` — and their
measured rates are 0.156 vs 0.171. A rule keyed to "how many modes the geometry
has" would have separated them by 4.5×. It would have been wrong.

**The structure the rates hide is a plateau.** The entries sit at full amplitude
across a band of width **≈ kD** before any decay begins: the first tenfold drop
of the monotone envelope is at `d/kD` = 0.77, 0.80, 1.10, 0.57 (ellipse, kite,
crescent, corrugated) at kD = 30, and 0.90, 1.10, 1.30, 0.90 at kD = 10. The
theorem is asymptotic in `d`; its constant `M(k)` grows with frequency, and the
plateau is where that growth lives.

**A correction to a claim this study initially made.** Fitting one exponential
across both the plateau and the decay returns a blend of the two, and that blend
drifts with kD for a reason that is not physical. Refitting on the decaying
region alone ([`penalty/post_knee_rates.csv`](penalty/post_knee_rates.csv)):

| curve | `b*` | whole-range kD=10 → 30 | **post-knee kD=10 → 30** |
|---|---|---|---|
| ellipse | 0.310 | 0.442 → 0.379 | **0.429 → 0.416** |
| kite | 0.167 | 0.304 → 0.254 | **0.284 → 0.255** |
| crescent | 0.091 | 0.223 → 0.156 | **0.198 → 0.149** |

So the exponent is essentially **k-independent for the ellipse**, as FJS's
theorem says it should be, and most of the apparent decline there was the fit.
A residual decline survives for the more distorted curves (kite −10%, crescent
−25%), but it is window-sensitive and this study does not claim a quantitative
wavenumber dependence of the exponent. **Nothing downstream rests on it**: the
band requirements below come from a direct search over every band, with no
fitting anywhere, and they are set by the plateau and the amplitude rather than
by the exponent.

---

## 2. What that costs: the band grows linearly in kD, so retention does not improve

Smallest band `|m-n| ≤ Q` that holds each target, searched over every `Q`, with
the report's four errors. `Q_field` is what the receiver data needs; `Q_grad` is
what the shape gradient needs.

| curve | kD | K | `Q_grad` @1e-6 | retained | `Q/kD` | `q = Q/lnN` |
|---|---|---|---|---|---|---|
| ellipse | 2 / 10 / 30 | 24 / 24 / 54 | 10 / 18 / 38 | 0.38 / 0.61 / 0.58 | 5.0 / 1.8 / 1.27 | 2.57 / 4.63 / **8.10** |
| kite | 2 / 10 / 30 | 24 / 36 / 81 | 12 / 25 / 50 | 0.45 / 0.58 / 0.52 | 6.0 / 2.5 / 1.67 | 3.08 / 5.83 / **9.82** |
| crescent | 2 / 10 / 30 | 24 / 36 / 81 | 13 / 28 / 59 | 0.48 / 0.63 / 0.60 | 6.5 / 2.8 / 1.97 | 3.34 / 6.53 / **11.58** |
| corrugated | 2 / 10 / 30 | 54 / 81 / 121 | 24 / 36 / 64 | 0.40 / 0.40 / 0.46 | 12.0 / 3.6 / 2.13 | 5.12 / 7.07 / **11.65** |

Two things follow, and they are the answer to the report's first question.

**There is a stable rule tying bandwidth to geometry spectrum and kD.** Fitting
over all non-circle cells:

```
Q  ≈  1.20 kD  +  0.162 ln(1/tol) / b*  −  2.3         R² = 0.935, mean error 3.2 modes
```

The geometry enters **only through `b*`**. Alternatives fit worse: dropping `b*`
gives R² = 0.863, and the published form `Q = q ln N` gives R² = 0.729 while
requiring `q` to grow from 2.6 to 11.6 across the sweep.

**But the payoff is a constant factor, not a complexity reduction.** Retention at
`1e-6` gradient accuracy is 0.38–0.63 and is **flat to rising in kD**. The report's
success criterion asked for "materially fewer than `O(M²)` significant modal
interactions". Half the matrix, not improving with electrical size, is not that.
This is the report's own kill criterion for pure modal compression — reached for
a specific, diagnosable reason (the `≈ kD` plateau), not because the structure is
unpredictable. It is entirely predictable.

![decay findings](decay_findings.png)

---

## 3. In the compression papers' own regime, the published methods work

Before scoring published rules against an electrical-size sweep they deserve
their own regime: kernel fixed, `N` refined. That is what their theorems claim.
Fixed kD = 10, `N` pushed from 33 to 257 (the untruncated solve is already
converged to `~2e-15` at `N = 33`):

| curve | rule | N=33 | 65 | 129 | 257 | retention 33 → 257 |
|---|---|---|---|---|---|---|
| ellipse | **JWY μ=1.2** | 1.2e-1 | 1.7e-2 | 8.3e-5 | **1.6e-7** | 0.363 → 0.065 |
| ellipse | FJS `q=2` | 1.2e-1 | 1.8e-2 | 1.8e-2 | 1.5e-3 | 0.355 → 0.087 |
| kite | **JWY μ=1.2** | 1.7e-1 | 4.0e-2 | 5.9e-3 | **9.8e-5** | 0.363 → 0.065 |
| kite | FJS `q=2` | 2.4e-1 | 8.8e-2 | 5.1e-2 | 1.5e-2 | 0.355 → 0.087 |
| crescent | **JWY μ=1.2** | 3.0e-1 | 8.2e-2 | 1.2e-2 | **3.7e-4** | 0.363 → 0.065 |
| crescent | FJS `q=2` | 3.9e-1 | 2.2e-1 | 1.0e-1 | 5.4e-2 | 0.355 → 0.087 |

**Jiang-Wang-Yu's mask transfers to the Müller transmission operator and behaves
exactly as its theorem promises**: error down three orders while retention falls
5.6×. **Fang-Jiang-Su's band rule does not**, and the reason is structural rather
than a defect — their rule is a *pure* `ℓ¹` band, uniform in `(m,n)`, whereas JWY's
`(1+(m-n)²)^μ min(1+m², 1+n²) ≤ N²` is hyperbolic-cross shaped: wide near low
`|m|,|n|`, narrow in the corners. For this operator the shape is what matters; the
maximum half-band JWY keeps grows 16 → 101 while FJS's grows only 6 → 11.

**The reconciliation, and it is the load-bearing sentence of this study:** that
compression is compressing *over-resolution*. At `N = 33` the physics is already
resolved to `2e-15`; every row below it is refinement the problem did not need.
Inverse scattering does not over-resolve — `N` is set by `kD`. At the `N` the
physics actually requires, the same masks deliver one to two digits. The papers
are right and the method does not transfer, and those are not in conflict.

---

## 4. Gradients need a wider band than fields — everywhere, and by a predictable amount

The report states that gradient fidelity, not field error, is the binding metric
for inversion. That is now measured, and it holds in every experiment here.

The clean case is the circle, whose Müller matrix is *exactly diagonal*:

| band `Q` | 0 | 1 | 2 | **3** | 4 |
|---|---|---|---|---|---|
| field error, kD=30 | `2.4e-15` | `2.1e-15` | `2.0e-15` | `2.0e-15` | `1.9e-15` |
| gradient error, kD=2 | `1.7` | `7.0e-1` | `2.6e-1` | **`9.4e-11`** | `3.5e-11` |
| gradient error, kD=10 | `3.7` | `2.9` | `2.0` | **`1.3e-8`** | `8.4e-9` |
| gradient error, kD=30 | `5.1` | `4.0` | `2.6` | **`1.2e-7`** | `8.1e-8` |

The field is correct to machine precision at `Q = 0` at every frequency. The
gradient is 170–510% wrong there and falls by eight to ten orders of magnitude
at exactly `Q = 3` — the largest Laurent mode among the four shape directions
differentiated (modes 1, 2, 3, −2). Perturbing by mode `p` opens the `|m-n| = p`
bands.

**A second correction.** That single family gave one value of the shape mode
content, and the rule first read off it — `Q_grad ≥ max(Q_field, p_max)` — is
wrong. Varying the differentiated modes over `p_max` = 2, 3, 6, 10, 15 shows the
penalty is **additive, not a maximum** ([`penalty/penalty.csv`](penalty/penalty.csv)):

| curve | kD | `Q_field` | `p_max`=2 | 3 | 6 | 10 | 15 |
|---|---|---|---|---|---|---|---|
| ellipse | 10 | 16 | 0 | 2 | 4 | 6 | **10** |
| ellipse | 30 | 36 | 0 | 2 | 2 | 4 | 6 |
| kite | 10 | 23 | 1 | 2 | 5 | 7 | **11** |
| kite | 30 | 48 | 2 | 2 | 4 | 6 | 8 |
| crescent | 10 | 26 | 2 | 2 | 5 | 8 | **13** |
| crescent | 30 | 55 | 2 | 4 | 5 | 9 | 12 |

At `Q_field = 16` and `p_max = 15`, `max(Q_field, p_max)` predicts 16 and the
truth is 26. The penalty runs at 0–1.33 × `p_max`, median ≈ 0.67, and is damped
at larger kD where the field band is already wide. The bound that held in all 30
cells is:

```
Q_field  ≤  Q_grad  ≤  Q_field + p_max + 1
```

This is a design rule, not a failure: **a truncation set chosen from the base
geometry is not valid for the derivative; it must be chosen for the family.**
It also sharpens the retention verdict in the wrong direction — a realistic
inversion carries 15–30 shape modes, so the gradient band is the field band plus
another 10–20, on a matrix whose half-order is only 1.8–2.7 × kD. The same gradient-trails-field pattern reappears independently
in the reduced-basis experiment below, and far more severely: at rank 80 the
field error is `1e-12` while the gradient error is `5e-7`, a five-order gap in
the same solve.

---

## 5. Multi-object local response: exact, 3–7× smaller, and the reuse is the prize

`S_j = R_j A_j⁻¹ B_j`, Graf translation, `(I − SU)b = Sa^inc`, all on the same
assembler. Validation:

| Check | Result |
|---|---|
| `S` vs analytic Mie coefficients (circle) | `9.6e-16` (kD=10), `4.5e-15` (kD=30); off-diagonal `1.3e-16` |
| Graf translation vs direct field re-expansion | `7.4e-12` |
| Two-object local solve vs monolithic Müller | `4.0e-15` – `1.4e-14` |
| Rebuild-one vs rebuild-all after moving one object | **bitwise identical** |

Separation sweep, coupling dimension against the monolithic trace dimension:

| pair | kD | gap 3λ | 1λ | 0.25λ | 0.06λ |
|---|---|---|---|---|---|
| two circles | 10 | 6.8× smaller | 6.8× | 6.8× | 6.8× |
| two circles | 30 | 5.1× | 5.1× | 4.7× | 4.7× |
| ellipse + crescent | 10 | 5.0× | 5.0× | 4.4× | 3.2× |
| ellipse + crescent | 30 | 4.2× | 4.2× | 3.3× | 2.7× |

The report's kill criterion — "useful accuracy requires a local multipole order
comparable to the full boundary discretisation over ordinary target separations"
— **is not met**. The order grows toward contact but stays 2.7–4.7× below the
trace dimension even at a 0.06 λ gap. (Below 0.06 λ the FFT-quadrature monolithic
*reference* is itself unconverged at the stated grid; those rows carry a
`monolithic_grid_control` column and are inconclusive, not negative.)

The scaling, on a ring of `J` ellipses at kD = 10:

| J | monolithic dim | coupling dim | full solve | one-object step |
|---|---|---|---|---|
| 2 | 284 | 58 | 1.23× | 2.4× |
| 4 | 568 | 116 | 1.66× | 6.6× |
| 8 | 1136 | 232 | 2.32× | 17.7× |
| 16 | 2272 | 464 | 3.66× | **49.2×** |

**The optimisation-step number is the real result** and it grows linearly in `J`
with no sign of saturating. One honest qualification on the full-solve column:
at `J = 16` the monolithic cost is 26.9 s of assembly against 0.43 s of
factorisation, so what the local route avoids is assembling `J²` dense cross
blocks, not linear algebra. A production monolithic code would use an FMM or
`H`-matrix for the far field and close much of that gap. The step speedup does
not depend on that, because it comes from *reuse*, which a monolithic
factorisation cannot offer at all.

---

## 6. Broadband low rank: the solution manifold is not low rank, but the operator is

Three ranks measured separately over kD ∈ [4, 24] (a 6:1 band), 21 training
frequencies, 20 held out, dimension 226.

| curve | **operator** rank 1e-3 / 1e-6 / 1e-9 | **solution** rank | **joint (k,c)** rank |
|---|---|---|---|
| ellipse | 7 / **11** / 14 | 44 / **62** / 78 | 46 / 70 / 88 |
| kite | 8 / **11** / 14 | 59 / **84** / 107 | 63 / 95 / 121 |
| crescent | 8 / **11** / 14 | 59 / **88** / 112 | 67 / 101 / 130 |

The report warned that "a solution family can be low dimensional even when the
operator family is not". **The measurement says the reverse, and emphatically.**
The operator family is rank **11 at 1e-6 for all three geometries** — a 20×
reduction, and strikingly insensitive to the boundary. The solution manifold is
rank 62–88, five to eight times larger, and it *is* geometry-sensitive. That
ordering has a clean cause: `A(k)` is analytic in `k` through its Hankel
amplitudes, so the operator family has tiny Kolmogorov width, while
`x(k) = A(k)⁻¹b(k)` inherits every near-resonance of the inverse.

The singular values make it unambiguous, and show the operator rank is a real
measurement rather than an artefact of sampling only 21 frequencies — the
operator spectrum falls by a factor of ~8 per mode and reaches `1e-11` by index
15, while the solution spectrum is nearly flat:

```
kite, operator :  1.0  7.6e-1  4.4e-1  2.7e-1  1.3e-1  4.3e-2  1.0e-2  2.0e-3
                       3.5e-4  5.4e-5  7.3e-6  8.7e-7  9.0e-8  7.9e-9  6.0e-10
kite, solution :  1.0  9.4e-1  9.1e-1  8.3e-1  8.2e-1  7.2e-1  6.9e-1  6.5e-1
                       5.9e-1  5.9e-1  5.0e-1  4.9e-1  4.3e-1  4.2e-1  3.8e-1
```

A reduced basis built from solution snapshots, Galerkin-projected on held-out
frequencies, confirms it from the other side:

| rank | field error | gradient error |
|---|---|---|
| 5 | `1.0` – `2.0` | `1.0` – `2.1` |
| 10 | `9.6e-1` – `2.0` | `1.1` – `2.1` |
| 20 | `2.6e-1` – `2.7` | `4.5e-1` – `7.0` |
| 40 | `4.2e-4` – `1.7e-1` | `5.0e-3` – `6.4e-1` |
| 80 | `3.9e-13` – `4.2e-6` | `4.9e-7` – `5.8e-3` |

The report's success criterion was "a rank of perhaps 5–10 reproduces held-out
frequencies at forward **and derivative** tolerances over a genuinely useful
band". A solution-space basis needs **rank ≈ 80 out of 226** for `1e-6` gradients
— a 2.8× reduction — and rank 5–10 is not merely inaccurate but useless (error
≥ 1). Note again the gradient trailing the field by three to five orders at
every rank.

**But the operator measurement points somewhere specific.** Rank 11 at `1e-6`
means an affine decomposition `A(k) ≈ Σ_r θ_r(k) A_r` over `r ≈ 11` is available
on this band, uniformly in geometry. The report listed exactly that form as its
third candidate and deprioritised it as crowded prior art with "weak standalone
novelty". On these numbers it is the broadband reduction worth building — as an
operator decomposition, not a reduced basis.

One qualification, because this is the most quotable number here: a rank is a
statement about a set of snapshots, and an affine model needs the coefficients
`θ_r(k)` to be recoverable at a frequency that was never assembled. A small
singular-value spectrum does not say they are — it is computed *from* the
snapshots it is asked to represent, and is perfectly compatible with
coefficients that oscillate too fast to interpolate from any affordable set of
them. §6c runs that experiment.

---


## 6b. Preconditioner reuse is the cheapest result here, and it is a clear win

GMRES to `rtol = 1e-10` using the LU at an anchor `(k_n, c_n)`, against plain
GMRES on the same system. Anchor kD = 14, dimension 226.

| curve | plain | `ΔkD`=0.25 | 0.5 | 1 | 2 | 4 | `‖ΔA‖/‖A‖`=0.03 (geom) | 0.08 | 0.16 | 0.33 |
|---|---|---|---|---|---|---|---|---|---|---|
| ellipse | 18 | 7 | 9 | 11 | 14 | 18 | 7 | 9 | 12 | 14 |
| kite | 21 | 8 | 10 | 15 | 16 | 27 | 6 | 8 | 11 | 12 |
| crescent | 28 | 8 | 10 | 13 | 22 | 33 | 7 | 10 | 12 | 16 |

The asymmetry is the point. A unit step in `kD` moves the operator about four
times as far as the geometry perturbations tested, so **the anchor factorisation
survives a geometry step of any size tried here** (6–16 iterations, always better
than plain) while it stops paying for frequency beyond `ΔkD ≈ 2`. A Gauss-Newton
inversion changes geometry every step and moves frequency slowly under
continuation — which is exactly the regime where this works. Recording it costs
nothing and it needs no new operator theory.

One bound on this, from testing it outside the range measured here: `ΔkD` was
swept only to 4. Across the full 6:1 band of §6d the anchor factorisation takes
**20 / 26 / 35** iterations against 18 / 21 / 28 plain — applied far enough away
in frequency it is not weak but actively harmful. The geometry column is the
durable half of this table.

---

## 6c. The affine decomposition, run: the rank is real, and the spacing is the price

`run_affine.py` tests §6's rank as an actual affine model. Held-out frequencies
sit at fine-grid midpoints — never a training node of any stride, and the
furthest a target can be from the densest training set. Two error sources are
separated:

```
projection      ||(I - P_r) vec A(k)|| / ||vec A(k)||    what the rank promises
interpolation   ||A_hat(k) - A(k)||_F / ||A(k)||_F       basis + cubic spline in k
```

**The rank survives everything.** Trained on 11, 21, 41, 81 and 161 frequencies
across kD ∈ [4, 24], the rank at `1e-6` is **11 for every curve at every
density** (kite touches 12 once). §6's number was not an artefact of sampling 21
points.

**And the coefficients interpolate.** Median over 8 held-out frequencies, rank
fixed by the `1e-6` criterion, as `projection / interpolation` with the receiver
field error beside it:

| Δk | n | ellipse | kite | crescent |
|---|---|---|---|---|
| 2.0 | 11 | 2.4e-6 / 3.4e-3 · `1.6e-2` | — | — |
| 1.0 | 21 | 3.3e-7 / 8.6e-5 · `3.7e-4` | 7.1e-7 / 4.8e-4 · `7.8e-4` | 6.2e-7 / 3.7e-4 · `5.4e-4` |
| 0.5 | 41 | 3.4e-7 / 3.2e-6 · `1.5e-5` | 1.0e-7 / 1.9e-5 · `3.1e-5` | 6.4e-7 / 1.5e-5 · `2.3e-5` |
| 0.25 | 81 | 2.9e-7 / **4.1e-7** · `2.8e-6` | 6.7e-7 / 1.4e-6 · `7.7e-6` | 6.0e-7 / 1.2e-6 · `6.4e-6` |
| 0.125 | 161 | 2.7e-7 / **2.7e-7** · `2.1e-6` | 6.3e-7 / **6.4e-7** · `5.8e-6` | 5.6e-7 / **5.7e-7** · `4.7e-6` |

The interpolation column converges at measured order **4.65 – 5.29** while it is
away from the floor — the cubic spline's own rate — then rolls off to order ≈ 1
as it lands on the projection error. That roll-off is the signature of reaching
a floor, not of failing. By Δk = 0.125 the two columns agree to within 2%: the
rank-11 basis is then **fully exploited, and nothing but the rank limits the
result**. At 11 snapshots the spectrum does not reach `1e-6` at all for the kite
or the crescent, so that row is ellipse-only and its model is rank 10.

So §6's open question answers yes. What it costs is the sampling:

| target on `‖Â−A‖/‖A‖` | ellipse | kite | crescent |
|---|---|---|---|
| `1e-3` | Δk = 1.0, **21** | 1.0, **21** | 1.0, **21** |
| `1e-5` | 0.5, **41** | 0.25, **81** | 0.25, **81** |
| `1e-6` | 0.25, **81** | 0.125, **161** | 0.125, **161** |

**and that is the entire economics.** Per held-out frequency, reconstruction
costs `0.0008 s` against `0.457 s` to assemble — **599× cheaper**, exactly the
win §6 promised. But the offline cost is `n` assemblies of the same operator, so

```
break-even = (n * 0.457 + t_svd) / (0.457 - 0.0008)  =  21 / 41 / 82 / 164
                                                        online frequencies
```

one for one with the training set. The affine model is free after you have paid
for it, and you pay in the same currency: **it saves nothing until the band is
sampled more finely for solving than it was for training.** For one boundary
swept finely in frequency that is easy to clear. For inversion it is not — the
basis is built from snapshots of one boundary, the geometry moves every
Gauss-Newton step, and the assemblies are spent again. §6's joint `(k, c)`
measurement is the one that governs there, and it is **70–130, not 11**.

**The field pays a further factor.** Operator error reaches the receiver data
amplified by a median **5.5×**: a `1e-6` operator does not buy `1e-6` data.

### Sharpening §6 — the conclusion stands, the reason given for it does not

I wrote that a low-rank operator family buys cheap assembly and **not** cheap
solves, *because each `A(k)` still has to be factorised*. In a dense
implementation the conclusion survives, but that reason is not the right one.
Factorisation was never the obstacle — `0.0006 s` against `0.457 s` to assemble —
and it need not be done on `A(k)` at all: the LU of the reconstructed `Â(k)`
drives GMRES on the *true* `A(k)` to `rtol = 1e-10` in **2 iterations against 21
plain**, and still in 4 when `Â` is only `1e-4`-accurate, so the preconditioning
is not fragile and the reconstruction never has to be accurate enough to use
directly:

| `‖Â−A‖/‖A‖` | preconditioned | plain | rows |
|---|---|---|---|
| `1e-5` – `1e-1` | **4** | 21 | 194 |
| `1e-6` – `1e-5` | **2** | 23 | 55 |
| below `1e-6` | **2** | 19 | 71 |

The obstacle is the **application**, not the factorisation. GMRES needs `A(k)`
applied, and here that means having assembled it — so in a dense implementation
nothing is saved and §6's conclusion holds. It becomes a saving with a
matrix-free or banded application of `A(k)`, which §1 says exists at
half-bandwidth `Q ≈ 1.2 kD`, though no banded assembler was built here. Naming
the right obstacle matters, because it is the one piece of implementation that
would cash this in, and §6 pointed at the wrong one.

---
## 6d. One basis, any frequency — and exactly as far in geometry as §6b allows

`run_transfer.py` asks the question §6c's break-even leaves open. That
break-even was one for one in *frequencies at a fixed boundary*, which a
Gauss-Newton inversion never reaches: it solves a few tens of frequencies and
then moves the boundary. But 6c also showed the reconstruction never has to be
accurate enough to solve with — it only has to precondition. So: build the basis
once at `c₀` (81 assemblies, rank 11), then use `LU(Â(k, c₀))` on the true
`A(k, c)` as the boundary moves. Six held-out frequencies spread across
kD ∈ [4, 24]; GMRES to `rtol = 1e-10`; two controls.

| curve | `‖ΔA‖/‖A‖` | **affine** | anchor LU (§6b) | plain | §6b, geometry only, matched distance |
|---|---|---|---|---|---|
| ellipse | 0 | **2** | 20 | 18 | — |
| | 0.084 | 10 | 20 | 18 | 0.083 → 9 |
| | 0.167 | 13 | 20 | 18 | 0.165 → 12 |
| | 0.334 | 14 | 18 | 18 | 0.330 → **14** |
| | 0.657 | 18 | 20 | 18 | beyond §6b's range |
| kite | 0 | **2** | 26 | 21 | — |
| | 0.080 | 8 | 26 | 21 | 0.080 → **8** |
| | 0.155 | 10 | 27 | 21 | 0.157 → 11 |
| | 0.300 | 12 | 27 | 21 | 0.303 → **12** |
| | 0.550 | 18 | 26 | 22 | beyond §6b's range |
| crescent | 0 | **2** | 34 | 28 | — |
| | 0.109 | 10 | 35 | 28 | 0.109 → **10** |
| | 0.211 | 12 | 36 | 28 | 0.211 → **12** |
| | 0.393 | 17 | 35 | 28 | 0.394 → 16 |
| | 0.666 | 24 | 35 | 26 | beyond §6b's range |

Three things, in order of how much they change the picture.

**The single anchor is not merely weak across a band — it is harmful.** §6b
measured frequency reuse only to `ΔkD = 4` and found it stopped paying around
`ΔkD ≈ 2`. Across the full 6:1 band the anchor LU takes **20 / 26 / 35**
iterations against **18 / 21 / 28** plain. A factorisation from kD = 14 applied
at kD = 5 or 23 is worse than no preconditioner at all. That is a limit on §6b,
found by testing it outside the range it was measured in.

**The affine reconstruction absorbs the frequency axis completely.** At the
training geometry it is 2 iterations (max 3 over all 18 cells) at every held-out
frequency, from a reconstruction that is only `1.9e-6` accurate.

**And what is left is exactly the geometry mismatch — nothing more.** Compare
the last two columns: at every matched `‖ΔA‖/‖A‖`, preconditioning with the
*reconstructed* operator at the right frequency costs **within one iteration** of
preconditioning with the *exactly assembled* operator at the same geometry
distance. The affine model gives up nothing relative to having assembled the
true operator there. Eleven vectors carry the entire 6:1 frequency dependence.

So the operating rule is concrete: **one 81-assembly basis at `c₀` serves every
frequency in the band, and tolerates the boundary moving to `‖ΔA‖/‖A‖ ≈ 0.33` at
12–17 iterations.** Past `0.55` it is back to plain and the basis must be rebuilt.

### What this is and is not worth

Two uses, with different accounting, and they should not be conflated.

*Reconstruct and solve directly.* Unconditional: 599× cheaper per frequency than
assembly, at the `2.8e-6` – `7.7e-6` field error of §6c. But it works **only at
the training geometry** — at `‖ΔA‖/‖A‖ = 0.08` the reconstruction is already
wrong by 8%, so this path does not survive the boundary moving at all.

*Reconstruct and precondition.* This is the path that transfers, and it is the
one with a caveat: GMRES needs `A(k, c)` to be **applied**, and in this dense
implementation applying it means having assembled it — at which point LU costs
`0.0006 s` against the `0.457 s` already spent, and the preconditioner has saved
nothing. It converts to a real saving only with a matrix-free or banded
application of `A(k, c)`, which §1 says exists at half-bandwidth `Q ≈ 1.2 kD`
but which was not built here. Until it is, the iteration counts above are a
sharp *measure of closeness* and a design argument, not a measured speedup.

---

## 7. Verdict against the report's own criteria

| Direction | Report's criterion | Outcome |
|---|---|---|
| Geometry-adaptive modal compression | stable bandwidth rule **and** `≪ O(M²)` retention | **half**: the rule exists and is `b*`-keyed with R² = 0.935; retention is 0.38–0.63 and does not improve with kD |
| Multi-object local response | local order ≪ trace dimension, compelling reuse speedup | **pass**: 2.7–6.8× smaller through near-touching, exact reuse, 49× per optimisation step at J = 16 |
| Broadband ROM | rank 5–10 at forward **and** derivative tolerance | **fail as posed** (solution basis needs rank ≈ 80), but the **operator** family is rank 11 at `1e-6` uniformly in geometry, the coefficients interpolate to the projection floor, and 11 vectors absorb the whole 6:1 frequency axis |
| Preconditioner reuse | GMRES iterations vs `Δk`, `‖Δc‖` | **pass, cheaply**: anchor LU survives any geometry step tested (6–16 its vs 18–28 plain); frequency reuse pays to `ΔkD ≈ 2` |

The report recommended compression as the main direction, local-response reuse as
the strongest alternative, and frequency reduction as crowded prior art to defer.
**The measurements reverse that ordering end to end.**

The compression thesis survives as a theorem — `b*` really does predict the
coupling spectrum, which is the mathematically interesting half — but the plateau
of width `≈ kD` caps the payoff at a constant factor exactly where the
application needs it most. The local-response calculus delivers on its numbers,
49× per optimisation step at J = 16 and still growing. And the direction the
report deferred turns out to hold the single largest clean reduction measured
anywhere in this study: a rank-11 operator decomposition over a 6:1 band,
insensitive to the geometry, whose coefficients interpolate at cubic-spline
order onto the projection floor (§6c) and which preconditions the true operator
**as well as the exactly assembled one would** (§6d).

Its price is honest and worth stating with it. The basis costs 81 assemblies and
its break-even is one for one in frequencies at a fixed boundary, so the direct
reconstruct-and-solve path pays only for a boundary swept finely in frequency —
not for inversion, where the geometry moves. The preconditioned path does survive
the boundary moving, as far as `‖ΔA‖/‖A‖ ≈ 0.33`, but converts to a *speedup*
only once `A(k, c)` can be applied without being assembled. §1 says that is
available at half-bandwidth `Q ≈ 1.2 kD`; building it is the one piece of
implementation that would turn this study's two strongest measurements into a
solver.

**Recommended order on this evidence: local-response reuse first, operator-space
frequency decomposition second, modal truncation not at all as a speed
mechanism.** Preconditioner reuse across geometry steps should just be turned on;
it is free.

The publishable statement that survives all of this is narrower and firmer than
either: **the geometry's analyticity strip `b*`, computable from the Laurent
coefficients alone, predicts the modal coupling bandwidth of the Müller operator
and of its shape derivative, with the derivative needing the field's band widened
by the shape parameterisation's own mode content.** That is a geometry-spectrum
result about the derivative operator, it is what the literature does not state,
and it does not depend on compression paying off.

## Limits

Lossless, equal permeability, scalar TMz, one interface per component, disjoint
bounding circles, external sources and receivers, contrast `ε_r 6 → 3`. Curves
normalised to unit diameter so `k = kD`. Shape gradients are central differences
through the full pipeline; each run records a step-size consistency number.
The step-consistency check (step vs 4× step) gives `6e-9` at kD = 2 rising to
`4e-7` at kD = 30; for central differences that bounds the fine-step error at
roughly a fifteenth of it, so the `1e-6` gradient targets sit above the
finite-difference floor and the `1.2e-7` circle entry above is floor-limited.
Four shape directions (Laurent modes 1, 2, 3, −2), 16 sources × 16 receivers,
one acquisition geometry. The broadband ranks of §6 come from 21 sampled
frequencies; §6c re-measured them at 11, 21, 41, 81 and 161 and the operator rank
at `1e-6` is 11 at every density, so that number is not sample-limited. A rank
claim above ~15 still would be at 21 samples, and the flat solution spectrum is a
lower bound rather than a measurement of where it ends. The geometry axis of §6d
is one Laurent direction (mode 2) at four amplitudes, matched to §6b's so the two
are comparable; it is a line through shape space, not a survey of it. Single-threaded timings on one machine, dense LAPACK
throughout — no fast direct or `H`-matrix comparison was made. Five boundaries,
three electrical sizes: this is a screen, not a statistical study.
