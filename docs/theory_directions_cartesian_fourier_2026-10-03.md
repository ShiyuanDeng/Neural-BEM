# Theory-backed directions for Cartesian Fourier shape inversion

2026-10-03. This is a filtered version of the research report on theory-heavy ideas. That report assumed a neural SDF and 3-D Maxwell, which is wrong for this branch. Neural-only ideas are removed here, the rest are restated for the code on `feature/shape-frequency-continuation`, and the two seed ideas are assessed against the same setting.

**Goal.** List directions that give provable guarantees (convexity, convergence radius, path existence) for the current inverse problem, and say how well each fits the code.

## 0. Summary

From the earlier list, six directions remain, with three of the old ideas merged into one. Three others were already tried or implemented in the repo, and two were neural-only. The most direct route is a computable convergence radius in the normal Fourier chart (T1), chained across the existing frequency ladder (T2). Complex-geometry path following (S2) is the natural tool for the stages where that chain breaks, and part of its infrastructure already exists. Convexification (S1) gives the strongest guarantee, but it needs full-matrix data and a Carleman estimate across an unknown interface, which is an open problem.

## 1. Setting

Read from `README.md`, `docs/current_architecture.md` and `docs/pipelines/shape_frequency_continuation.md` on 2026-10-03.

| Item | Current code |
|---|---|
| Physics | 2-D TMz dielectric transmission: the field E_z solves a scalar Helmholtz transmission problem. Lossless, known contrast, homogeneous full space |
| Forward | Ordered periodic Kress/Nyström Müller solver with nodal densities |
| Shape | Cartesian Fourier curve with storage band K, re-parameterised by arclength after each accepted update |
| Update | Scalar normal displacement with 2M+1 real Fourier coefficients (update band M) |
| Frequencies | 19 real frequencies, 0.25–2.5 GHz; MA-005 DF prefix stages at k(1 + 0.25i) |
| Data | 24 paired values per frequency; the full 24×24 matrix only as a control (FM-001) |
| Hard case | The C at contrast 13.3 fails from paired data and recovers from full data (FM-001) |
| Not in the inverse | Half-space (a Sommerfeld forward solver exists), 3-D, noise-aware tail |

Abbreviations: TMz is transverse magnetic with the electric field along z. BIE is boundary integral equation. TCC is tangential cone condition. LSM is linear sampling method. OT is optimal transport. SDP is semidefinite programming. The factorization method is written in full because FM-001 is a repo experiment ID.

## 2. Notation

Each symbol keeps this meaning throughout.

| Symbol | Meaning |
|---|---|
| k | Exterior wavenumber; real in production, complex in damped stages |
| ε_r | Relative permittivity of the object (known) |
| Γ†, ℓ | True boundary curve and its length |
| s | Arclength on Γ†, s ∈ [0, ℓ) |
| x†(s), n†(s) | Point of Γ† and outward unit normal there |
| M | Update band; the unknown has 2M+1 entries |
| h(s) | Normal displacement of the boundary from Γ† |
| c ∈ ℝ^{2M+1} | Fourier coefficients of h; c = 0 is the truth |
| P | Number of data values per frequency (24 paired, 576 full) |
| G(c, k) ∈ ℂ^P | Predicted data |
| d(k) ∈ ℂ^P | Measured data |
| δ | Noise level |
| 𝒦 | Set of frequencies in use |
| Φ(c) | Least-squares misfit over 𝒦 |
| J(c, k) | Jacobian ∂G/∂c, size P × (2M+1) |
| σ_0 | Smallest singular value of J at the truth (frequencies stacked) |
| L | Lipschitz constant of J in c |
| B_r | Ball ‖c‖ ≤ r around the truth |
| C_s | Stability constant |
| η | Tangential-cone constant |
| ρ | Convergence radius |
| F(c, k) | Square system whose solutions a continuation method tracks (S2) |

Norms are Euclidean, and the matrix norm is the operator norm. For real c, the singular values of J are those of the real matrix [Re J; Im J].

## 3. The chart used by all theorems

Fix the true boundary Γ†. A nearby curve is described by its normal displacement h, expanded in M Fourier modes:

$$\Gamma(c)=\{\,x^\dagger(s)+h(s)\,n^\dagger(s)\ :\ s\in[0,\ell)\,\}\qquad(1)$$

$$h(s)=c_0+\sum_{j=1}^{M}\Big(c_j\cos\frac{2\pi js}{\ell}+c_{M+j}\sin\frac{2\pi js}{\ell}\Big)\qquad(2)$$

The misfit over the frequencies in use is

$$\Phi(c)=\tfrac12\sum_{k\in\mathcal K}\big\|G(c,k)-d(k)\big\|^2\qquad(3)$$

The chart describes every nearby curve by how far it sits from the true one, measured along the normal. Sliding points along a curve changes nothing physical, and the chart has no such directions, so each of the unknowns changes the shape. This removes the null-space problem the neural parametrisation had, and it matches the repo's normal updates.

## 4. Seed ideas

### S1. Convexification adapted to shapes (seed 1)

**What is known (taken as given).** Klibanov and coauthors build the method in four steps.

1. Transform the field so the unknown coefficient drops out, by differentiating with respect to frequency or source position.
2. This gives a nonlinear differential system for a new unknown v, with data on the measurement boundary.
3. Minimise a Carleman-weighted Tikhonov functional:

$$Q_\lambda(v)=\int_\Omega e^{2\lambda\psi(x)}\,\big|\mathcal L(v)(x)\big|^2\,dx+\alpha\,\|v\|^2_{H^q(\Omega)}\qquad(4)$$

Here Ω is the imaging region and 𝓛 the operator from step 2. ψ is a fixed weight function, λ > 0 the weight strength, α > 0 a regularisation weight, and H^q a Sobolev space.

4. A Carleman estimate (a weighted inequality for 𝓛 that holds for large λ) then proves the following. For every R > 0 there is λ(R) such that Q_λ is strictly convex on the ball ‖v‖ ≤ R, and gradient methods converge from any start in that ball.

Sources:
- Klibanov, Kolesov and Nguyen, arXiv:1805.07618: 3-D, one incident plane wave, multi-frequency backscatter data, experimental buried targets.
- Khoa, Klibanov and Nguyen, arXiv:1911.10289: 3-D, moving point source.
- Thành and Klibanov, arXiv:1901.03183: 1-D, multi-frequency.
- Klibanov and Li, *Inverse Problems and Carleman Estimates* (De Gruyter, 2021).

**Fit with the code.**

- What is proven convex is (4), not the misfit (3). The least-squares landscape is unchanged; the method replaces it.
- The radius R is arbitrary. The price is that λ grows with R, so the weight spans many orders of magnitude, which is a known numerical difficulty.
- The formulation uses one incident field measured on a curve at many frequencies, or many sources each measured on a curve. One column of the full 24×24 matrix over the 19 frequencies matches this. The paired data (one value per source) do not.
- Here the coefficient equals ε_r inside Γ and 1 outside, so it jumps at the boundary. The existing theory assumes a smooth coefficient.

**What would be new.** There are two routes.

- Smooth the jump, run convexification, and read the shape from a level set. This loses the chart (1)–(2) and the known-contrast information.
- Work with the transmission problem directly. Carleman estimates across a jump interface exist when the interface is known (Le Rousseau and Robbiano, Arch. Ration. Mech. Anal. 195, 2010). Here the interface is the unknown, which is open.

**Verdict.** It has the strongest guarantee in this document and the lowest feasibility. It is best used as a global start on full-matrix data, not as the main loop.

### S2. Complex path following through turning points (seed 2)

**Setup.** A continuation method tracks a solution c(k) of a square system F(c, k) = 0 as k moves. F has 2M+1 equations, for example the stationarity equation of the misfit. At a turning point ∂_c F is singular, and the real branch ends or folds back.

**Lemma 1 (turning points are isolated when F is holomorphic).** Let F: ℂ^{2M+1} × ℂ → ℂ^{2M+1} be holomorphic, and let c(k) be a branch with ∂_c F invertible at the start. Along any path where the branch can be continued, the turning points met are isolated values of k, unless every point of the branch is one.

Proof.

$$\partial_cF\,\frac{dc}{dk}+\partial_kF=0\quad\text{(differentiate }F(c(k),k)=0\text{ by the chain rule)}$$

$$\frac{dc}{dk}=-(\partial_cF)^{-1}\partial_kF\quad\text{(where }\partial_cF\text{ is invertible)}$$

The right side is holomorphic, so c(k) is holomorphic in k.

$$\Delta(k):=\det\partial_cF\big(c(k),k\big)\ \text{is holomorphic}\quad\text{(composition of holomorphic maps)}$$

The zeros of a holomorphic function of one variable that is not identically zero are isolated (identity theorem). Turning points are exactly the zeros of Δ. ∎

So a path in the k-plane can be bent around each turning point. A randomly chosen path avoids them with probability one.

**Real geometry, complex frequency (counting argument, generic case).** If c stays real and only k is complex, the stationarity equation is 2M+1 real equations in 2M+3 real unknowns (c, Re k, Im k), so its solutions form a real surface. The condition det = 0 adds one more real equation, so the turning points form curves in the k-plane, not points. A path avoids such a curve only by going around its end (a cusp point), if it has one. This counting is the generic case by a transversality argument, not proven here. It describes the current damped stages, which use real geometry at k(1 + 0.25i). So "complexified boundary solver" has to mean complex geometry c, not only complex k.

**Making the misfit holomorphic.** The misfit (3) uses complex conjugation, which is not holomorphic. Define mirror versions:

$$\tilde G(c,k)=\overline{G(\bar c,\bar k)},\qquad \tilde d(k)=\overline{d(\bar k)}\qquad(5)$$

$$\Phi^{\mathbb C}(c,k)=\tfrac12\big(\tilde G(c,k)-\tilde d(k)\big)^{\!\top}\big(G(c,k)-d(k)\big)\qquad(6)$$

For real c and real k, G̃ = conj(G) and d̃ = conj(d), so (6) equals the one-frequency term of (3). Both factors in (6) are holomorphic in (c, k), so F = ∇_c Φ^ℂ = 0 is the holomorphic square system Lemma 1 needs.

**Consequences.**

- Evaluating (6) needs the forward solve at the mirror point (c̄, k̄). With the repo's exp(−iωt) convention, a damped frequency (Im k > 0) has its mirror at Im k < 0, the side where scattering resonances lie.
- Data at k̄ require a growing time weight, which amplifies late-time noise.
- An alternative keeps k real and puts a complex homotopy parameter t in the data, with d_t = (1 − t) G(c₀, k) + t d(k) and t moving from 0 to 1 through the complex plane. Then only the geometry is complex, and no complex-frequency data are needed.

**Toy check (one unknown).** Take F(h, k) = h³ − 3h − k. Then ∂_h F = 3h² − 3 vanishes at (h, k) = (−1, 2) and (1, −2). Start at k = 0 on the root h = −√3 ≈ −1.7321.

- Real path: k = 1.9, 1.99, 1.999 gives h = −1.1774, −1.0572, −1.0182 and ∂_h F = 1.1588, 0.3530, 0.1102. The branch ends at k = 2.
- At k = 3 the roots are 2.1038 and −1.0519 ± 0.5652i.
- A path passing above k = 2 ends at −1.0519 + 0.5652i, and a path passing below ends at −1.0519 − 0.5652i. Neither is the real root.
- A path that first loops once around k = 2 takes h from −1.7321 to 0, still at k = 0. A loop around k = −2 then takes it to 1.7321. Running along the real axis to k = 3 then ends at 2.1038.

Complex paths always get past turning points, but which solution they reach depends on how the path winds around the turning points.

**Fit with the code.**

- A complex-frequency forward solver exists (`experiments/modal_atlas/damped.py`), and damped data exist for the 20 MA-005 cases.
- Complex geometry is missing from the Kress quadrature. The kernel's |x − y| must become the non-conjugated root √((x − y)·(x − y)) with a continuous branch. That root can vanish for complex x − y ≠ 0, so the imaginary part of h must stay small.
- Mirror evaluations and a rule for choosing the winding are also missing.

**What would be new.**

- A winding rule, using turning points located as zeros of Δ(k) along the path.
- A comparison with the current real-geometry damped stages, which by the counting argument have fold curves rather than points.

The probability-one path result for polynomial systems (the "gamma trick") is in Sommese and Wampler, *The Numerical Solution of Systems of Polynomials Arising in Engineering and Science* (World Scientific, 2005). Lemma 1 is the analytic version used here.

## 5. Remaining ideas

### T1. Finite-dimensional stability and a computable convergence radius (old 1, 2, 5)

**Assumptions.** Data are noise-free, d = G(0, ·), and frequencies are stacked into one vector.

$$\sigma_0=\sigma_{\min}\big(J(0)\big)>0\qquad(7)$$

$$\|J(x)-J(y)\|\le L\,\|x-y\|\quad\text{for }x,y\in B_r\qquad(8)$$

**Lemma 2 (stability from the Jacobian).** For x, y ∈ B_r with r < σ_0/(2L):

$$\|G(x)-G(y)\|\ \ge\ (\sigma_0-2Lr)\,\|x-y\|\qquad(9)$$

Proof.

$$\|G(x)-G(y)\|\ \ge\ \|J(y)(x-y)\|-\|G(x)-G(y)-J(y)(x-y)\|\quad\text{(triangle inequality)}$$

$$\sigma_{\min}\big(J(y)\big)\ \ge\ \sigma_0-\|J(y)-J(0)\|\ \ge\ \sigma_0-Lr\quad\text{(Weyl's inequality for singular values, then (8))}$$

$$\|J(y)(x-y)\|\ \ge\ (\sigma_0-Lr)\,\|x-y\|\quad\text{(previous line)}$$

$$\|G(x)-G(y)-J(y)(x-y)\|=\Big\|\int_0^1\big(J(y+\tau(x-y))-J(y)\big)(x-y)\,d\tau\Big\|\ \le\ \tfrac L2\|x-y\|^2\quad\text{(fundamental theorem of calculus, then (8))}$$

$$\tfrac L2\|x-y\|^2\ \le\ Lr\,\|x-y\|\quad(\|x-y\|\le 2r)$$

Substituting the last three lines into the first gives (9). ∎

Weyl's inequality, |σ_i(A) − σ_i(B)| ≤ ‖A − B‖, is taken as given (Horn and Johnson, *Matrix Analysis*).

**Lemma 3 (tangential cone condition and radius).** Under the same assumptions:

$$\|G(x)-G(y)-J(y)(x-y)\|\ \le\ \eta\,\|G(x)-G(y)\|,\qquad \eta=\frac{Lr}{\sigma_0-2Lr}\qquad(10)$$

$$\eta=\tfrac12\iff r=\rho:=\frac{\sigma_0}{4L}\qquad(11)$$

Proof.

$$\|G(x)-G(y)-J(y)(x-y)\|\ \le\ Lr\,\|x-y\|\quad\text{(last two lines of Lemma 2's proof)}$$

$$\le\ \frac{Lr}{\sigma_0-2Lr}\,\|G(x)-G(y)\|\quad\text{(by (9))}$$

$$\frac{Lr}{\sigma_0-2Lr}=\frac12\iff 2Lr=\sigma_0-2Lr\iff r=\frac{\sigma_0}{4L}\quad\text{(rearrange)}$$

∎

Taken as given: with η < 1/2 on a suitable ball, Landweber iteration with discrepancy stopping converges and is a regularisation method. The source is Hanke, Neubauer and Scherzer, Numer. Math. 72 (1995) 21–37; the exact ball and stopping constant are in the paper. Similar conditions are used for Levenberg–Marquardt and iteratively regularised Gauss–Newton.

**Toy check.** Take G(c) = sin c with truth c = 0, so σ_0 = cos 0 = 1 and L = sup|sin| ≤ 1, giving ρ = 0.25. On a 2001-point grid of B_0.25:

- The worst ratio in (10) is 0.0235, against the bound 0.5.
- The smallest |G(x) − G(y)|/|x − y| is 0.9689, against the bound 0.5 from (9).

Both bounds hold with margin, as expected for worst-case constants.

σ_0 says how firmly the data hold the shape at the truth. L says how fast that hold can weaken as the shape moves. Their ratio is how far away a start can be and still be pulled in.

**Fit with the code.**

- The Jacobian atlas already computes σ_0, as singular spectra by frequency, contrast and acquisition.
- L is not measured. Finite differences of J along random directions give an estimate of L, not a bound.
- (11) gives a rule for the update band. σ_0 falls as M grows, so M at each frequency should stay where ρ exceeds the expected error. This is a principled version of the repo's 1% column-norm frontier.

**What would be new.**

- For a circle, rotational symmetry makes the linearised map couple mode j of h only to scattering-matrix entries T_{μ,ν} with |μ − ν| = j. So σ_0 has a closed form in Bessel and Hankel functions for full data. Paired data mix these blocks, but σ_0 can still be computed.
- Bounds on L for the transmission problem, which needs the second shape derivative.
- TCC-type conditions are reported as unverified for obstacle scattering (arXiv:2512.10260, 2025). A finite-dimensional, computed version for the transmission problem would be new.

### T2. Frequency continuation with a proven basin (old 4)

**What is known (taken as given).** Sini and Thành (Inverse Probl. Imaging 6 (2012) 749–773) treat a 2-D sound-soft obstacle with one incident direction. They give a quantitative region in which the lowest-frequency misfit has one minimum, and convergence of recursive linearisation with noisy data. The transmission problem and paired data are not covered.

**Chained with T1.** Let ĉ_j be the fit after stage j, assumed to lie in that stage's ball. Let C_s(j) = 1/(σ_0(j) − 2L_j r) be the constant from (9). A sufficient condition for stage j+1 to start inside its radius is

$$C_s(j)\,\big(\|G(\hat c_j,\cdot)-d\|_j+\delta\big)\ <\ \rho(j+1)\qquad(12)$$

The left side bounds ‖ĉ_j‖ by (9), using the triangle inequality on the residual and the noise. The right side is (11) at stage j+1. If the truth is not representable in band M_j, the truncation error adds to the left side.

**Fit and novelty.** The ladder exists (the SC policy and the RLA, recursive linearisation, arm). (12) would turn the band and frequency schedule into a checkable rule. New work would be a transmission, paired-data version of Sini–Thành, and (12) itself.

### T3. Monotonicity tests (old 3), full-matrix data only

**What is known (taken as given).** For a contrast of known sign (here ε_r > 1), whether a test region lies inside the object is decided by the number of negative eigenvalues of a data-difference operator. Griesmaier and Harrach prove this for Helmholtz, and Albicker and Griesmaier (Inverse Probl. Imaging 17 (2023)) for Maxwell. The method needs the full source × receiver matrix; the 24 paired values do not form an operator.

**Use.** The tests give inner and outer sets with D_in ⊆ D† ⊆ D_out, where D† is the true object. If both are normal graphs over the same reference curve, they become h_in(s_i) ≤ h(s_i) ≤ h_out(s_i) at sample points s_i. These are linear inequalities in c by (2).

**Status.** Harrach's convex SDP equivalence is proven only for elliptic problems; a scattering version is open. Here monotonicity would reduce R for S1 and give T2 a start.

### T4. Optimal-transport misfit (old 11)

**What is known (taken as given).** The quadratic Wasserstein distance is convex in time shifts and dilations of a signal (Engquist, Froese and Yang, Commun. Math. Sci. 14 (2016) 2309–2330). For a buried object these correspond roughly to position and size.

**Fit.** The repo can make time traces from the 512-frequency BIE runs, validated against gprMax. Exact convexity breaks when signed traces are normalised. The Mie localisation already handles far starts, so the gain is smaller. New work would be a convexity statement in a circle's centre and radius for paired data.

### T5. Inverse Born series (old 9)

**What is known (taken as given).** Moskow and Schotland (Inverse Problems 24 (2008) 065005) show that the inverse Born series converges, with an explicit radius and error bound, when contrast and data are small enough.

**Fit.** A penetrable object with known contrast fits the method. The output is a contrast map, which is then fitted with chart (2). The contrast-0.5 cases may meet the condition; contrast 13.3 will not. Low priority.

### T6. Bayesian posterior (old 13)

In chart (2) with σ_0 > 0, the shape is locally identifiable. The finite-dimensional Bernstein–von Mises theorem then gives an approximately Gaussian posterior, with covariance proportional to (Re(J^H Σ⁻¹ J))⁻¹, where Σ is the noise covariance. This is computable from the same Jacobian. The guarantee is statistical, not about optimisation. Low priority.

## 6. Already tried or implemented in the repo

| Old # | Idea | Repo evidence | Remaining theory question |
|---|---|---|---|
| 6 | LSM and factorization-method initialisers | 2026-10-02 exploration: the LSM start passes 5/12, the same as the original start. The factorization method needs the full matrix | Exact characterisation from paired data; no known result |
| 7 | Relaxed or extended BIE | RB-001: 0/4 added recoveries | A basin-enlargement theorem; current evidence is negative |
| 8 | Topological derivative | Used for births in the topology controller and as an initialiser | None new |

## 7. Dropped as neural-only

| Old # | Idea | Reason |
|---|---|---|
| 10 | Over-parameterisation and PL* inequality | Needs a neural network |
| 12 | ReLU-SDF polyhedral uniqueness | Its premise is that ReLU zero sets are polygons; Fourier curves are smooth |

Also removed from the kept ideas: the weight-space null-space discussion (there are no weights) and the Maxwell and half-space adaptation notes (the code is 2-D scalar in full space).

## 8. Ranking

| Idea | Guarantee | Fit with current code | Feasibility | Open part |
|---|---|---|---|---|
| T1: radius ρ = σ_0/(4L) | Local, explicit, computable | High: Jacobian atlas, Mie solutions | High | Bounds on L; closed form for circles |
| T2: chained continuation (12) | Local per stage, chained | High: existing ladder | Medium | Transmission and paired-data version of Sini–Thành |
| S2: complex path following | Path exists; endpoint depends on winding | Medium: damped solver exists, complex geometry missing | Medium | Winding rule; complex Kress kernels |
| S1: convexification | Global on any ball, for functional (4) | Low: one full-matrix column only | Low | Carleman estimate across an unknown interface |
| T3: monotonicity | Certified inner and outer sets | Low: full matrix only | Medium | Scattering version of the convex SDP |
| T4: OT misfit | Convex in position and size | Medium | High | Statement for paired data |
| T5: inverse Born | Explicit radius, small contrast only | Low | Medium | Excludes contrast 13.3 |
| T6: Bayesian | Statistical | Low | Medium | Not an optimisation guarantee |

**Combinations.**

1. T1 with T2: compute σ_0 and an estimate of L at each stage of the existing ladder, and test (12). Where (12) holds, the hand-off is justified. Where it fails, the schedule needs a smaller step or a lower band.
2. S2 at the stages where (12) fails or the real branch reaches a turning point, with the winding chosen from the located turning points.
3. S1 or T3 on full-matrix data as a global start for combination 1, if the acquisition allows it.

## 9. Remarks

1. **Paired data.** Most stability and uniqueness theorems assume full far-field or full multistatic data, and FM-001 shows the paired/full gap matters for the contrast-13.3 C. In T1 the effect of the acquisition is entirely in σ_0, which can be computed for both. That gives a direct measure of the information paired data lose.
2. **High contrast and resonances.** Popov and Vodev ("Resonances near the real axis for transparent obstacles", Commun. Math. Phys., 1999) study strictly convex smooth obstacles in which waves travel slower inside than outside, which is the case ε_r > 1. They show an infinite sequence of resonances tending rapidly to the real axis. They use the opposite sign convention; with the repo's exp(−iωt), resonances lie in Im k < 0. The C is not convex, so this is only suggestive. Near-real resonances make G and J change quickly along real k, which raises L and shrinks ρ. This fits why damping (Im k > 0) helps, and it warns that the mirror evaluations in S2 move toward the resonances.
3. **Current damped stages.** By the counting argument in S2, real geometry at complex k has fold curves in the k-plane. The current approach can pass some folds by going around their ends, but it has no guarantee of doing so.
4. **Moving chart.** The repo re-centres the chart on the current curve after each accepted step, while T1 is stated around the truth. For small h the two agree to first order. A careful version expresses the truth as a normal graph over the current curve, which exists when the two curves are close in C¹.
5. **Corrections to the earlier report.** The Maxwell and half-space gaps it listed are not the current bottleneck. Its claim that monotonicity "supplies seed 1's bounded set" was overstated, because Klibanov's radius R is arbitrary; monotonicity bounds can only reduce R. The convex functional in S1 is (4), not the misfit (3).

## Result

In the normal Fourier chart the convergence radius is ρ = σ_0/(4L). Chaining it across frequencies with (12), and using complex-geometry path following where the chain breaks, is the most direct theory-backed route for this code.

The smallest singular value says how firmly the data hold the shape, the Lipschitz constant says how fast that hold changes, and their ratio is how far a start can be.
