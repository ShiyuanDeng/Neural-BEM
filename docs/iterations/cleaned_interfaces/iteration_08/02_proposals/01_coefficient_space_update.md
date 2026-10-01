# Replacing the node-based geometry update of a Laurent curve with coefficient-space operations: literature, feasibility and a bounded experiment

**Answer first:** The shape directions and validity checks can be moved into coefficient space exactly and for less cost now. The arclength gauge cannot be reproduced exactly with band-limited operations, because the only simple curve with a Laurent-polynomial arclength parameterisation is a circle (Lemma 2). It can be emulated to spectral tolerance, though. For Monday, the one bounded experiment should be the untested "N-update" (with its coordinates rescaled to metres), run on the six core configurations with drift logging. The full arclength emulation should be deferred.

## TL;DR

- **Exact and cheap now [derived]:** With the N-update, z_new = Π_K(z + g_a N), the trial map is affine in a. The shape directions δz_q = Π_K(φ_q N) are index shifts costing O(K) each, which removes the 2(2M+1) sampled projections. A new scalar test costing O(K) per trial (Lemmas 3–4) can certify most small trials as simple and regular before the full |W|² certificate is run. Rescaling g_a = h_a/σ_0 with σ_0 = L/(2π) keeps the step coordinates in metres to within the speed ratio σ/σ_0.
- **Arclength gauge: emulable, not exact [derived + read]:** An arclength curve of finite band exists only for the circle (Lemma 2). The arclength Fourier coefficients can still be computed spectrally, without splines or inversion, from z̃_k = (ik)⁻¹⟨z′e^{−ikα(θ)}⟩₀ (eq. 9; this is a change of variables also used by Koga 2021 with a non-uniform FFT). The cost is O((K + M + d) B log B), which is below the current 8192-node spline refit at K = 192. Accuracy is set by the drift ratio r_σ = max|z′|/min|z′| through a Chebyshev rate ((r_σ+1)/(r_σ−1))^{−d} (eq. 6).
- **Decision:** Put one experiment in the plan: N-update versus the existing nodal baseline on the six core configurations, with and without an explicit band-limited tangential term (eq. 11, a coefficient version of Hou–Lowengrub–Shelley). Log r_σ, β_W, Λ_W/β_W, log-series degree, K_tr and refusals by cause, with decision rules fixed in advance. Defer full arclength emulation, the Gram–Cholesky frontier, sum-of-squares certificates and conformal-map gauges.

## Scope and evidence levels

The repository files could **not** be read. The fetch tool refused the branch and raw-file URLs, and searches returned only the repository root page. That page shows the default branch `feature/ordered-boundary-nystrom` and an `experiments/` folder whose contents are not listed [read].\[1\] Everything about the current code below comes from the task description, not from code; no claim is tagged [code].

Tags used throughout:
- [read]: full or substantial text.
- [abstract]: abstract only.
- [snippet]: search-result excerpt.
- [derived]: derived here.
- [inferred]: reasoning not stated in a source.

"No precedent found" means not found in the roughly 20 searches done.

## Symbols and acronyms

| Symbol | Meaning |
|---|---|
| w = e^{iθ}, θ | curve parameter on the unit circle |
| z(w) = Σ_{\|j\|≤K} z_j w^j | Cartesian Laurent curve (complex form); K = storage band |
| M | update band; a ∈ ℝ^{2M+1} step coordinates |
| z′ = dz/dθ = Σ i j z_j w^j | parameter derivative |
| N = −i z′ = Σ j z_j w^j | unnormalised outward normal |
| σ = \|z′\|, S = σ² = z′ conj(z′) | speed; squared speed (Laurent polynomial of band 2K) |
| L, σ_0 = L/(2π) | perimeter; mean speed (σ_0 = zeroth coefficient of σ) |
| r_σ = max σ / min σ | drift ratio (1 for arclength) |
| α(θ) = (2π/L)∫_0^θ σ, η = α − θ | normalised arclength; its periodic part |
| H_k(θ) = e^{ikα(θ)} | arclength harmonics expressed in θ |
| n̂ = N/σ, κ | unit normal; curvature |
| h_a(α), g_a(θ) | normal-displacement series in arclength (current) and in θ (N-update) |
| φ_q | q-th basis function (1, cos mθ, sin mθ) |
| Π_K | crop to \|j\| ≤ K; A = spline arclength resampler; T_z = trial map |
| δz_q, ω_q = Re(δz_q conj N) | shape direction; its Hadamard weight |
| ψ(θ) | real tangential coefficient: tangential move ψ z′ |
| W, R, Y, ρ_c, β_W, Λ_W, K_tr | as defined in the task (divided difference, chord², reciprocal series, certificate residual, certified bounds on \|W\|², trace cutoff) |
| ‖f‖_1 = Σ\|f_j\| | Wiener (ℓ¹ coefficient) norm; it bounds sup\|f\| and is submultiplicative |
| ν(f) = Σ \|j\|\|f_j\| | Wiener norm of the derivative coefficients |
| ⟨f⟩_0 | zeroth Fourier coefficient (mean over θ) |
| d, λ_E | Chebyshev degree; Bernstein-ellipse parameter |
| B, N_s | working band for non-polynomial series; number of exact evaluation points |
| Ξ | certificate residual 1 − \|W_new\|² Y |

Acronyms:
- LM: Levenberg–Marquardt
- BIE: boundary integral equation
- FFT: fast Fourier transform
- NUFFT: non-uniform FFT
- IRGNM: iteratively regularised Gauss–Newton method
- HLS: Hou–Lowengrub–Shelley
- MSC: modal speed control
- BRG: Borges–Rachh–Greengard
- BGN: Barrett–Garcke–Nürnberg
- IGA: isogeometric analysis
- SOS: sum of squares
- SDP: semidefinite programming

## Key Findings

1. **The closest precedent resamples in arclength too.** Borges–Rachh–Greengard 2023 update by a normal perturbation h_j(t)ν(t) written in arclength harmonics of the previous curve, cos(2πnt/L_{j−1}). They then "reparametrize the curve as a Fourier series in arclength" after every step, with update band ⌈ck⌉, c = 2 recommended in [1,3] [read].\[2\] The current code's gauge is that published design. Moving away from it has no direct precedent in inverse scattering.
2. **The classical regularised Newton literature uses radial or Cartesian trigonometric parameterisations and handles the tangential gauge by penalties, not reparameterisation.**
   - Kress uses a star-shaped radial r(t) with L² Tikhonov on the update [read].\[3\]
   - Hohage–Werner use a radial q with an H^{1.6} penalty ‖q − q_0‖² in the IRGNM [read].\[4\]
   - The paper "Corrosion shape reconstruction of the mixed boundary in electrostatic imaging" (Adv. Differ. Equ. 2020, art. 405), which uses the Kress–Rundell method, states that "the parameterization of the update ζ obtained from (20) and (21) is not unique" and chooses "the H^2 penalty term to the reconstructed boundary ζ" [snippet].
   - "A second degree Newton method for an inverse obstacle scattering problem" (J. Comput. Phys. 230(20), 2011), building on Hettlich & Rundell (SIAM J. Numer. Anal. 37(2), 1999), uses Cartesian trigonometric polynomials T_m [snippet; the T_m detail was not re-checked].
3. **Tangential moves are in the first-order null space of the Jacobian (Lemma 1, [derived]).** Penalising the tangential gauge inside LM is therefore equivalent to a separate tangential least-squares step. That step is the modal speed control idea, and it needs no physics.
4. **Exact arclength is impossible in band-limited form (Lemma 2, [derived]).** Spectral emulation is possible. Everything reduces to one family H_k = e^{ikα(θ)}, |k| ≤ max(K, M), which serves both h∘α and the reparameterisation (eqs. 8–9).
5. **Drift sets the cost of every non-polynomial series.** The Chebyshev degree for √S, 1/√S and log S is set by r_σ (eq. 6). Λ_W/β_W ≥ r_σ² (Lemma 5), so drift directly raises the log|W|² degree [derived].
6. **Refused trials need not cost a full certificate.** A bound costing O(K) per trial (Lemmas 3–4), then one Newton–Schulz step, then a full rebuild gives a tiered test [derived]. A rigorous box test follows from exact FFT evaluation plus a Bernstein correction (eq. 13) [derived].
7. **The N-update's own frontier is natural in θ-harmonics weighted by S.** Before the crop, ω_q = φ_q S exactly (eq. 4). A diagonal L²(ds) normalisation with a polynomial proxy for S^{3/2} keeps per-harmonic meaning (eq. 14) [derived].

## Details

### 1. Literature (Q1)

**Inverse obstacle scattering.**
- BRG 2023 (penetrable obstacle, recursive linearisation) [read]:
  - initial update h_1 = α_0 + α_1 cos t + β_1 sin t in the normal direction;
  - then the update (10) in arclength harmonics with band ⌈ck⌉, and a curve band N_γ = max(N_γ,prev, pL_j k/2π);
  - a trust region on curvature "elastic energy", E_κ^{⌈ck⌉} ≥ (1 − ε_f)E_κ, inside a Powell dogleg choice between the Gauss–Newton and steepest-descent steps;
  - if neither step passes, a Gaussian filter γ_n → γ_n exp(−n²/(σ²N²)) is applied up to 10 times;
  - in the numerics, N_γ = ⌊3 max(k, k_i)⌋ update modes and 70 points per wavelength.\[2\]
- BRG also conclude that "the geometry of the set of non-intersecting curves is complicated to parametrize" [read]. BRG state they extend the Borges–Greengard method (SIAM J. Imaging Sci. 8(1), 2015, 280–298, arXiv:1408.5436) [read]. That paper was not read in full. Its abstract says "we do not assume the boundary is star-shaped. Instead, we assume it is bandlimited as a function of arclength", and "instead of Tikhonov regularization, we simply enforce a bandlimit" [abstract].
- Kress (ANZIAM J. 2000): the boundary is {r(z)z}, with the update r̃ = r + h, "αh + [F′(r)]*F′(r)h = [F′(r)]*(u∞ − F(r))", and trigonometric or periodic-Gaussian bases [read via subagent].\[3\]
- Hohage–Werner: radial q, R(q) = ‖q − q_0‖²_{H^s} with s = 1.6; replacing q_0 by q_n gives LM [read via subagent].\[4\]
- Hohage–Schormann 1998 applies the IRGNM to the transmission problem [snippet].\[5\]\[6\] Its exact parameterisation could not be checked.
- Harbrecht–Hohage 2007 note that parameterisations "are not uniquely determined by the obstacle" [snippet].\[7\]
- Eckhardt, Hiptmair, Hohage, Schumacher & Wardetzky, "Elastic energy regularization for inverse obstacle scattering problems" (Inverse Problems 35(10), 2019, arXiv:1903.05074), state that "the assumption of star-shaped obstacles is severely restrictive" [snippet].

**Interface dynamics.**
- HLS 1994 introduced the equal-arclength frame, with the tangential velocity found by antiderivatives [snippet; formula read in Koga].\[8\]\[9\]
- Koga 2021 gives the evolution s_{α,t} = V_α − θ_α U (U normal, V tangential velocity, θ_α = κ s_α). It obtains the Fourier coefficients of the arclength parameterisation "directly … through a simple change of variables", evaluated with a type-1 NUFFT [read].\[9\]
- Seol–Lai (SIAM J. Sci. Comput. 2020) find "the discrete inverse of the arclength(-like) function in the framework of the Fourier spectral method" [abstract].\[10\]
- Mikula–Ševčovič (asymptotically uniform redistribution) and Ševčovič–Yazaki 2011 (curvature-adjusted) choose the tangential velocity to control point spacing [snippet/abstract].\[11\]\[12\]
- BGN schemes get equidistribution from an implicit tangential motion [snippet]. Practical BGN variants apply "a mesh regularization procedure … when the mesh ratio exceeds a given threshold value" [snippet], which is a precedent for threshold-triggered reparameterisation.\[13\]

**Coefficient-updating shape optimisation.**
- IGA adds a Winslow regularisation "to penalize configurations of control points that result in poor parametrizations" [snippet].\[14\]
- IGA certifies validity by positivity of the Jacobian's Bézier/B-spline control coefficients [snippet].\[15\]\[16\] This is a coefficient-space validity certificate that parallels the |W|² test.
- Fourier-knot gradient flows redistribute by resampling an inscribed polygon and refitting the Fourier coefficients [snippet].\[17\] That is a nodal precedent.
- For elliptic Fourier descriptors, arclength parameterisation is standard [snippet].\[18\] No precedent was found for controlling parameterisation degradation during descriptor-based optimisation.

**Conformal and Laurent dynamics.**
- Polubarinova–Galin dynamics are ODEs for the Laurent coefficients of the conformal map [snippet].\[19\]
- Fornberg and Wegmann compute the boundary correspondence by Newton iteration on Fourier coefficients [snippet].\[20\]\[21\]
- Beceanu, Hong, Kwon & Lim, "The Eigenvalue Problem for the Laplacian via Conformal Mapping and the Gohberg–Sigal Theory" (arXiv:2112.11026, Springer), use exterior conformal-map coefficients and give eigenvalue asymptotics "from the changes in the conformal mapping coefficients" [abstract].
- The conformal gauge is canonical, but like arclength it is not band-limited in a Cartesian Laurent curve [inferred].

**Algebra.**
- Brent–Kung: composition and reversion are equivalent in cost; "special left-compositions, including … reciprocals, square roots, and elementary transcendental functions … can be done in merely O(M(n)) operations" [snippet].\[22\]\[23\]
- Johansson's fast Lagrange inversion is a practical alternative [snippet].\[24\]
- Newton–Schulz squares the residual, F_{k+1} = F_k² [snippet].\[25\]
- Dumitrescu: a nonnegative univariate trigonometric polynomial is an SOS, if and only if it has a positive-semidefinite Gram matrix, giving an SDP test [abstract/snippet].\[26\]\[27\]

**Precedent classes.**

| Idea | Class |
|---|---|
| Normal update in arclength harmonics + arclength refit | Published (BRG) |
| Sobolev/Tikhonov penalty on coefficients to fix the gauge | Published (Kress, Hohage) |
| Normal-only update in parameter harmonics (N-update) | Adaptation (Kress radial updates; HLS Lagrangian normal motion) |
| Spectral arclength reparameterisation by change of variables | Published (Koga, NUFFT); coefficient-recurrence form is an adaptation |
| Band-limited tangential term (MSC/HLS form, eq. 11) | Adaptation (HLS, Mikula–Ševčovič) |
| Incremental ℓ¹ certificate (Lemmas 3–4) | No precedent found |
| Bernstein-corrected box bound | Adaptation (classical Bernstein inequality) |
| Möbius/Blaschke reparameterisation of Laurent curves | No precedent found |

**Literature map ranked by relevance (plain URLs).**

| Rank | Source | Level | URL |
|---|---|---|---|
| 1 | Borges, Rachh, Greengard, Inverse Problems 39 (2023) 035004 | [read] | https://arxiv.org/abs/2210.11607 \[28\] |
| 2 | Koga, Numerical reparametrization of periodic planar curves via curvature interpolation | [read] | https://arxiv.org/abs/2110.12432 |
| 3 | Kress, Integral equation methods in inverse obstacle scattering, ANZIAM J. 42 (2000) | [read via subagent] | https://www.cambridge.org/core/services/aop-cambridge-core/content/view/D4F49AB00C9D89921CBBE374C67A9AD1/S1446181100011603a.pdf/integral_equation_methods_in_inverse_obstacle_scattering.pdf \[3\] |
| 4 | Hohage, Werner, Iteratively regularized Newton-type methods … | [read via subagent] | https://arxiv.org/abs/1105.2690 \[4\] |
| 5 | Hohage, Schormann, Inverse Problems 14 (1998) 1207 | [snippet] | https://doi.org/10.1088/0266-5611/14/5/008 \[5\] |
| 6 | Hou, Lowengrub, Shelley, J. Comput. Phys. 114 (1994) | [snippet] | https://users.cms.caltech.edu/~hou/papers/SSD_jcp94.pdf |
| 7 | Seol, Lai, Spectrally accurate points redistribution, SISC 42 (2020) | [abstract] | https://epubs.siam.org/doi/10.1137/20M1314690 |
| 8 | Ševčovič, Yazaki, curvature adjusted tangential velocity | [abstract] | https://arxiv.org/abs/1009.2588 |
| 9 | Second-degree Newton method, Cartesian T_m (J. Comput. Phys. 2011) | [snippet] | https://www.sciencedirect.com/science/article/abs/pii/S0021999111003846 |
| 10 | Huygens' principle and iterative methods (H^s penalties on parameterisation update) | [snippet] | https://link.springer.com/content/pdf/10.1007/s10444-009-9135-6.pdf |
| 11 | Corrosion shape reconstruction (non-unique update parameterisation, H² penalty) | [snippet] | https://link.springer.com/article/10.1186/s13662-020-02864-x |
| 12 | Harbrecht, Hohage, Fast methods for 3D inverse obstacle scattering | [snippet] | http://num.math.uni-goettingen.de/hohage/obstacle3D.pdf |
| 13 | Brent, Kung, Fast algorithms for manipulating formal power series | [snippet] | https://www.eecs.harvard.edu/~htk/publication/1978-jacm-brent-kung.pdf |
| 14 | Johansson, A fast algorithm for reversion of power series | [snippet] | https://fredrikj.net/math/reversion.pdf |
| 15 | Practical isogeometric shape optimization: parametrization by regularization | [snippet] | https://academic.oup.com/jcde/article/8/2/547/6097073 |
| 16 | Isogeometric shape optimisation via Coons patches (Jacobian control-point positivity) | [snippet] | https://cdm.me.wisc.edu/pub/ShapeOptCoonsRev1.pdf |
| 17 | BGN second-order scheme with threshold mesh regularisation | [snippet] | https://arxiv.org/abs/2309.12875 |
| 18 | Transport-type BGN convergence (deformation-rate minimiser) | [snippet] | https://link.springer.com/article/10.1007/s00211-025-01521-3 |
| 19 | Newton–Schulz review | [snippet] | https://arxiv.org/abs/2208.04068 |
| 20 | Dumitrescu, Positive Trigonometric Polynomials and Signal Processing Applications | [abstract] | https://link.springer.com/book/10.1007/978-3-319-53688-0 |
| 21 | Bazant, Conformal mapping methods for interfacial dynamics | [snippet] | https://math.mit.edu/~bazant/papers/4.10_Bazant.pdf |
| 22 | DeLillo, Fourier series methods for numerical conformal mapping | [snippet] | https://www.math.wichita.edu/~delillo/TD_tutorial.pdf |
| 23 | Laplacian eigenvalues via exterior conformal map coefficients | [abstract] | https://arxiv.org/abs/2112.11026 |
| 24 | Menger-curvature flow, Fourier-knot redistribution | [snippet] | https://arxiv.org/abs/1408.6517 |
| 25 | Elliptic Fourier features notes (arclength parameterisation) | [snippet] | https://www.sci.utah.edu/~gerig/CS7960-S2010/project3/Kelemen_EllipticHarmonicsOnly.pdf |
| 26 | Neural-BEM repository root (README only) | [read] | https://github.com/ShiyuanDeng/Neural-BEM \[1\] |

### 2. Supporting lemmas

**N-update and its normal motion.** The update is

$$ z_{\rm new} = \Pi_K\big(z + g_a N\big),\qquad g_a = \sum_q a_q\varphi_q . \tag{1} $$

The unit normal is n̂ = N/σ and |N| = σ, so before the crop the move is purely normal, with displacement

$$ (g_a N)\cdot\hat n = g_a\,\sigma . \tag{2} $$

Here g_a N has band K + M; the crop is exact whenever z has band ≤ K − M, and otherwise its error is computable exactly from the discarded modes [derived].

**Lemma 1 (tangential null space, first order).** For real ψ, the tangential move δz = ψz′ gives ω = Re(ψz′ conj N) = 0.

*Proof.* Write conj N = conj(−iz′) = i conj(z′). Then ψz′·i conj(z′) = iψS, whose real part is 0 because ψ and S are real. ∎

Because the Hadamard formula weights only ω, tangential moves leave the Jacobian unchanged to first order [derived].

**Consequence for the N-update.** Before the crop,

$$ \omega_q = \mathrm{Re}(\varphi_q N\,\overline N)=\varphi_q S . \tag{3} $$

This holds since φ_q is real and N conj(N) = S. It follows that

$$ \frac{\partial F_s}{\partial a_q} = 2\pi(k_i^2-k_e^2)\sum_j(\varphi_q S)_j\,(u\tilde u)_{-j}. \tag{4} $$

This is exact and coefficient-only. The crop adds a correction Re((Π_K − I)(φ_q N) conj N), which is also exact [derived].

**Lemma 2 (no band-limited arclength curve except the circle).** Suppose a simple counterclockwise Laurent-polynomial curve has σ ≡ c > 0. Then z = z_0 + z_1 w.

*Proof.*
1. Let D(w) = z′ = Σ i j z_j w^j and D*(w) = Σ conj(i j z_j) w^{−j}. On |w| = 1, D* = conj(D). So D D* − c² is a Laurent polynomial vanishing on the whole circle, hence identically zero.
2. Write D = w^p Q(w), where Q is a polynomial of degree q with Q(0) ≠ 0. Then D* = w^{−p−q} Q^#(w), where Q^#(w) = w^q conj(Q(1/conj w)) and Q^#(0) ≠ 0.
3. Hence Q Q^# = c² w^q. The left side has a nonzero constant term, so q = 0 and D = d w^p.
4. A periodic z needs p ≠ 0, so z = z_0 + (d/(ip)) w^p, a circle traversed |p| times. Simple and counterclockwise forces p = 1. ∎ [derived]

### 3. Emulating the arclength gauge to tolerance (Q2)

**Speed, unit normal and α.** S is an exact Laurent polynomial of band 2K. σ = √S and 1/σ are not polynomials. On a certified interval [a, b] containing the range of S, map x ∈ [a, b] to t ∈ [−1, 1]. The singularity x = 0 then sits at t_0 = −(a+b)/(b−a).

The Bernstein ellipse parameter is λ_E = |t_0| + √(t_0² − 1). With √(b/a) = r_σ this simplifies (using t_0² − 1 = 4ab/(b−a)²) to

$$ \lambda_E=\frac{\sqrt b+\sqrt a}{\sqrt b-\sqrt a}=\frac{r_\sigma+1}{r_\sigma-1},\qquad \text{error}\sim\lambda_E^{-d}. \tag{5} $$

So the degree for a tolerance ε is

$$ d\approx\frac{\ln(1/\varepsilon)}{\ln\big((r_\sigma+1)/(r_\sigma-1)\big)}\;\approx\;\tfrac{r_\sigma}{2}\ln(1/\varepsilon)\ \ (r_\sigma\gg1). \tag{6} $$

The same rate holds for 1/√x and log x, which share the singularity at 0 [derived]. For ε = 10⁻¹², d ≈ 8, 12, 25 and 54 at r_σ = 1.05, 1.2, 2 and 4.

**Normalised arclength.** With σ = Σσ_jw^j and σ_0 = L/(2π),

$$ \alpha(\theta)=\theta+\eta(\theta),\qquad \eta_j=\frac{\sigma_j}{i\,j\,\sigma_0}\ (j\neq0),\ \ \eta_0\ \text{free (origin)}. \tag{7} $$

This is exact given σ, since α′ = σ/σ_0 [derived].

**Arclength harmonics and h∘α.** Since

$$ H_k=e^{ik\alpha(\theta)}=w^k\,e^{ik\eta(\theta)},\qquad \cos m\alpha=\mathrm{Re}\,H_m, \tag{8} $$

the current update h_a(α(θ)) is a linear combination of the H_m. Build H_1 = w e^{iη} by scaling and squaring (e^{iη} = (e^{iη/2^s})^{2^s}), with each multiplication an FFT convolution cropped to band B. Then H_k = H_{k−1}H_1. The instantaneous frequency of H_k is kσ/σ_0, so B ≈ max(K, M)·max σ/σ_0 plus a decay margin [derived].

**Reparameterisation without inversion.** For the arclength curve z̃(α) = z(θ(α)), substitute α = α(θ) and integrate by parts. The boundary term vanishes because z and e^{−ikα} are 2π-periodic in θ. This gives

$$ \tilde z_k=\frac{1}{ik}\big\langle z'\,H_{-k}\big\rangle_0=\frac1{ik}\sum_j (z')_j\,(H_{-k})_{-j}\ \ (k\neq0),\qquad \tilde z_0=\sum_j z_j\,\frac{\sigma_{-j}}{\sigma_0}. \tag{9} $$

This is the coefficient form of Koga's change of variables (3.6), which Koga evaluates with a type-1 NUFFT [read].\[9\] Neither θ(α) (Lagrange or Newton inversion) nor a composition z∘θ is needed [derived].

**Cost and comparison.** The full emulated trial, z + h_a(α)n̂ followed by eq. (9) on the new curve, needs about d + M + K products of length about 2B. At K = 192 and B ≈ 1024 that is roughly 400 FFTs of 2048 points.

The current resampler A uses 2^⌈log₂ max(1024, 16(2·192+1))⌉ = 8192 points with cubic splines, whose error is O(h⁴). It is repeated 2(2M+1) + 1 = 383 times per prepare step, plus the grid-doubling check [derived from description; timings not measured].

The spectral route converges geometrically, but it is **approximate**: Π_K truncation and the √ series both leave tails. Certification in ℓ¹ through Wiener submultiplicativity is pessimistic for large k. A practical control is to transplant the existing criterion: compute at bands B and 2B and require a difference below 10⁻⁵ L/2π [inferred].

**The hybrid option keeps the meaning of a.** By Lemma 1, the current arclength-gauge columns satisfy ω_q ≈ Re(cos(mα) n̂ σ conj(n̂)) = cos(mα)σ before the crop. These can be computed from eq. (8) and the √ series alone, with no projections, while T_z stays nodal for the trial itself. This changes the Jacobian only by the finite-difference error (ε = 10⁻⁷ m) and the tangential and crop terms [derived].

**Pseudo-spectral equivalence.** Evaluating √S or e^{ikα} pointwise on an oversampled FFT grid gives the same coefficients up to aliasing, which decays at the same rate. "Node-free" is therefore best defined as *no interpolation and no unbounded non-polynomial step*, with grids used only as exact convolution engines [inferred].

### 4. Band-limited gauge alternatives (Q3)

**Speed change under a step [derived].** For δz = gN + ψz′,

$$ \delta S=2g\,\mathrm{Im}(\overline{z'}z'')+2\psi' S+\psi S' . \tag{10} $$

Two facts give this: Re(g′N conj(z′)) = 0, and Re(g conj(z′)(−iz″)) = g Im(conj(z′)z″). Normal-only steps change S by 2gκσ³, so the drift per step is d ln σ ≈ −κ·(normal displacement). This agrees with Koga's s_{α,t} = V_α − θ_α U [read].\[9\] Drift is therefore largest where large deformations meet high curvature [inferred].

**MSC in HLS form (adaptation).** Setting δS = 0 when S ≈ S_0 = σ_0² gives

$$ \psi_a=-\frac1{S_0}\,\partial_\theta^{-1}\!\Big(g_a\,\mathrm{Im}(\overline{z'}z'')-\big\langle g_a\,\mathrm{Im}(\overline{z'}z'')\big\rangle_0\Big). \tag{11} $$

This is an exact Laurent polynomial of band 2K + M, linear in a, so T_z(a) = z + Π_K Σ a_q(φ_qN + ψ_qz′) stays affine and T_z(0) = z. By Lemma 1 the tangential part leaves ω_q unchanged before the crop.

To remove existing non-uniformity, add a relaxation term ψ′_rel = −ω_rel(S − S_0)/(2S_0), after Mikula–Ševčovič. Apply it only on accepted steps, because it breaks T_z(0) = z. Expected behaviour: it holds r_σ near its starting value, with second-order error O(|δz|²) and crop error [inferred].

**Variance penalty inside LM.** With N-update coordinates there is no tangential freedom, so a penalty on Var S = Σ_{j≠0}|S_j|² would distort the *shape* (eq. 10 with ψ = 0) [derived]. Adding tangential coordinates fixes this. By Lemma 1 their physics columns vanish, so the normal equations decouple into data + normal block and penalty + tangential block. The result is MSC computed as a separate least-squares step. The IGA Winslow approach is the analogue [snippet].\[14\]

**Direct Cartesian coefficient updates (a = Δz_j).** These have precedent in Cartesian T_m (Hettlich–Rundell type) [snippet].\[29\] They fix M = K, which conflicts with the empirical finding that M needs its own frequency-tied schedule. The tangential null space then has to be damped or penalised [inferred]. Low priority.

**Möbius/Blaschke reparameterisation.** z∘B with B(w) = (w − b)/(1 − b̄w) is rational with a pole at 1/b̄, so its band is infinite. That breaks the band-limited Laurent arrays that the modal Müller service relies on. Reject [derived]. No precedent was found.

**Reparameterising only at stage boundaries.** Apply eq. (9) when r_σ exceeds a threshold or at stage changes, where LM state and frontier are reset anyway. The BGN threshold regularisation is the precedent [snippet].\[13\] It is a low-risk companion to the N-update [inferred].

### 5. Validity checks (Q4)

**Lemma 3 (incremental certificate).** Let Δ = |W_new|² − |W|². If ρ_c + ‖Δ‖_1‖Y‖_1 < 1, then

$$ |W_{\rm new}|^2\ \ge\ \frac{1-\rho_c-\|\Delta\|_1\|Y\|_1}{\|Y\|_1}>0\ \ \text{on the torus}. \tag{12} $$

*Proof.*
1. Let Ξ = 1 − |W_new|²Y. Then Ξ = (1 − |W|²Y) − ΔY, so ‖Ξ‖_1 ≤ ρ_c + ‖Δ‖_1‖Y‖_1.
2. Pointwise, |W_new|²|Y| = |1 − Ξ| ≥ 1 − ‖Ξ‖_1, and |Y| ≤ ‖Y‖_1. Dividing gives (12). ∎

One Newton–Schulz step Y_new = Y(1 + Ξ) gives the residual 1 − |W_new|²Y_new = Ξ² exactly, because the arrays commute. So ρ_new ≤ ‖Ξ‖_1² [derived].

**Lemma 4 (divided-difference norm).** ‖(f(w) − f(v))/(w − v)‖_1 ≤ ν(f).

*Proof.*
1. For j > 0, (w^j − v^j)/(w − v) = Σ_{k=0}^{j−1} w^k v^{j−1−k}, which has j unit coefficients.
2. For j = −n < 0, (w^{−n} − v^{−n})/(w − v) = −w^{−n}v^{−n}(w^n − v^n)/(w − v), which has n unit coefficients.
3. Sum over j. ∎

With ΔW the divided difference of Δz, ‖Δ‖_1 ≤ 2ν(z)ν(Δz) + ν(Δz)². So (12) becomes a **scalar O(K) pre-check per trial** [derived]. How conservative it is must be measured.

**Tiered validity test [derived].** Run these in order and stop at the first decisive result:
1. Exact orientation and area, π Σ j|z_j|² > 0, at cost O(K).
2. Lemma 3 with Lemma 4, at cost O(K).
3. A 1-D regularity bound min S ≥ min_{N_s} S − ½(π/N_s)²(2K)²‖S − S_0‖_1, using the Bernstein argument below. This is necessary, not sufficient.
4. One Newton–Schulz step: one 2-D product plus an ℓ¹ norm.
5. A full rebuild of Y.

Global simplicity always needs the 2-D test: local regularity does not exclude distant self-intersection [inferred].

**Box containment.** Let x = Re z, of degree K, and let s be the nearest of N_s exact FFT evaluation points to the maximiser. At an interior maximum x′ = 0, so the Bernstein inequality applied twice to x − x_0 gives

$$ \max_\theta x\ \le\ \max_{N_s}x+\tfrac12\Big(\tfrac{\pi K}{N_s}\Big)^2\sum_{j\ne0}|x_j| . \tag{13} $$

The same holds for −x, ±y. With N_s = 16K the correction is 0.019Σ|x_j|, against the full disk bound Σ|z_j| [derived]. SOS/SDP certificates (Dumitrescu Gram matrix [abstract]) are exact\[26\] but cost at least O(K³) per trial. Defer them.

### 6. Frontier redefinition (Q5)

**Option F1 (recommended for the experiment).** Use the N-update columns ω_q = φ_qS (eq. 3) with a diagonal L²(ds) normalisation of the metre-scaled normal displacement φ_qσ/σ_0. Its squared norm is ∫φ_q²σ³dθ/σ_0².

Replace σ³ = S^{3/2} by the polynomial proxy P(S) = S_0^{3/2}(1 + (3/2)u + (3/8)u²), with u = S/S_0 − 1 and error O(u³). For cos mθ this gives

$$ G_{qq}=\frac{1}{\sigma_0^2}\int\cos^2(m\theta)P\,d\theta=\frac{\pi}{\sigma_0^2}\big(P_0+\mathrm{Re}\,P_{2m}\big), \tag{14} $$

and the analogous expression with −Re P_{2m} for sin. At r_σ = 1 this equals L/2, the current normalisation of arclength harmonics [derived].

**Option F2.** Use arclength-harmonic columns cos(mα)σ via eq. (8). This preserves the current meaning exactly, to tolerance.

**Option F3.** Use the Toeplitz Gram matrix G_{pq} = 2πP_{p−q} with Cholesky orthonormalisation. This mixes harmonics, so p_m loses its per-harmonic meaning when r_σ is far from 1. Defer it.

The bases coincide to O(r_σ − 1). A θ-band M corresponds to a local arclength band of about M·σ_0/min σ, so frontier values m* are comparable across gauges only while r_σ stays near 1 [derived].

### 7. Comparability and drift experiments (Q6)

**Step coordinates.** With g_a = h_a/σ_0, a_q is in metres and the normal displacement is h_aσ/σ_0. The clips (12 mm, 18 mm, 6 mm) then transfer with a distortion factor in [1/r_σ, r_σ]. A diagonal or Sobolev damping matrix diag((1 + m²)^s) transfers unchanged in form, and the M schedule transfers up to the factor σ_0/min σ [derived].

**Lemma 5.** Λ_W/β_W ≥ r_σ².

*Proof.* W(w, w) = dz/dw and |z′(θ)| = |dz/dw| on |w| = 1. So β_W ≤ min σ² and Λ_W ≥ max σ². ∎

By eq. (6), the log|W|² series degree is then at least ln(1/ε)/ln((r_σ+1)/(r_σ−1)) [derived].

**What to log at every accepted step:**
- r_σ, β_W, Λ_W/β_W, the log-series degree, ‖Y‖_1 and ρ_c;
- K_tr, and the crop tail ‖(Π_K − I)(g_aN)‖_1/‖g_aN‖_1;
- the energy fraction of z above K/2;
- m*, LM iterations per stage, and refused trials by cause and by tier;
- wall time split into geometry and physics.

**Pre-registered drift indicator.** Drift matters if, on any core configuration, r_σ exceeds 1.5, or the log-series degree or K_tr rises by more than 30% over the nodal baseline at the same stage [inferred thresholds; adjust before running].

### 8. Ranked replacement options per node-using step

**Trial update**

| Rank | Option | Inputs → outputs | Exact? | Cost | Meaning change | Precedent | Risk |
|---|---|---|---|---|---|---|---|
| 1 | N-update (1), g = h/σ_0 | z, a → z_new | Exact except crop (computable) | O(MK) | θ-harmonics; metres only up to σ/σ_0 | Adaptation | Drift |
| 2 | N-update + HLS tangential term (11) | z, a → z_new | Exact polynomial, linearised gauge | O((2K+M)log) | Same as 1, drift held | Adaptation (HLS, Mikula–Ševčovič) | Second-order drift; crop |
| 3 | Nodal T_z kept (hybrid) | z, a → z_new | Spline O(h⁴), checked | 1 resample per trial | None | Published (BRG) | None new |
| 4 | Full spectral emulation (8)+(9) | z, a → arclength z_new | To tolerance (λ_E^{−d}, tails) | O((d+K+M)B log B) | None | Adaptation (Koga NUFFT) | Implementation; certification |
| 5 | Cartesian Δz_j + tangential penalty | z, Δz → z_new | Exact | O(K) per step, larger LM | M = K | Published (Cartesian T_m; Winslow) | Conflicts with M schedule |
| 6 | Möbius/conformal gauge | n/a | Not band-limited | n/a | Canonical | Conformal-map literature | Reject or defer |

**Shape directions**

| Rank | Option | Exact? | Cost | Meaning change | Precedent | Risk |
|---|---|---|---|---|---|---|
| 1 | δz_q = Π_K(φ_qN) by index shifts; ω_q from (3) plus crop term | Exact | O(K) each, O(MK) total | With N-update | Adaptation | Low |
| 2 | Hybrid ω_q = cos(mα)σ via (8) and the √ series | To tolerance | O((d+M)B log B) | None | No precedent found | Low |
| 3 | Current central differences | O(ε²) plus spline error | 2(2M+1) resamples | None | n/a | Cost |

**Validity checks:** tiered test 1→5 (§5), rank 1, exact bounds [derived]. Box test eq. (13), rank 1 [derived]. SOS/SDP deferred.

**Frontier:** F1 rank 1 for the N-update; F2 for the hybrid; F3 deferred.

**Reparameterisation**

| Rank | Option | Notes |
|---|---|---|
| 1 | None, with monitoring (N-update) | Decide from data |
| 2 | Continuous MSC (11) | Cheap; keeps the trial affine |
| 3 | Spectral reparameterisation (9) at stage boundaries or an r_σ threshold | Precedent: BGN thresholds |
| 4 | Current spline at every step | Status quo |

## Recommendations

**Into Monday's plan (one bounded experiment).** "N-update drift audit."
- **Arms:** six core configurations × two arms, run against the existing nodal results:
  - arm A: N-update (eq. 1), g = h/σ_0, unchanged clips, damping and M schedule, F1 frontier, tiered validity tests;
  - arm B: arm A plus the tangential term (11).
- **Built-in control:** before the runs, check on saved nodal states that the coefficient columns (eq. 3, and the hybrid cos(mα)σ) match the current finite-difference columns to about 10⁻⁶ relative. This validates the Jacobian path independently of drift.
- **Decision rules, fixed in advance:**
  - If arm A keeps r_σ < 1.5 and matches nodal pass/recovery on at least 5/6 configurations, adopt the N-update.
  - If arm A drifts but arm B does not, adopt arm B.
  - If both drift or lose cases, keep the nodal trial map and adopt only the hybrid columns.
- **Effort and payoff [inferred]:** about 1–2 days of implementation and 12 runs. It answers the central open question (whether drift matters) and delivers the projection-free Jacobian in every outcome.

**Defer:**
- full arclength emulation (eqs. 8–9) as the trial map;
- the Gram–Cholesky frontier (F3);
- SOS/SDP positivity certificates;
- conformal-map or Möbius gauges;
- direct Cartesian coefficient updates;
- re-running the 36-configuration campaign. Do this only after the six-configuration result, and report it in the new coordinates alongside 28/36 and 34/36.

## Caveats

- No repository code was read. File names, function behaviour and constants come from the task description. The default branch README describes other pipelines.
- Lemmas 3–5 and eqs. (10)–(14) are derived here and untested. In particular, the conservativeness of the O(K) pre-check is unknown.
- Cost figures are operation counts, not timings. Python overhead may dominate both the nodal and spectral paths.
- Hohage–Schormann 1998, HLS 1994 and Borges–Greengard 2015 were not read in full. The statements about them rest on snippets or on citing papers.
- The thresholds in §7 are suggestions, to be fixed before running.

## Remarks

- **Pi_K and accumulation.** Each N-update adds band M. The high-K accumulation seen when only M is restricted is consistent with g_aN filling K − M < |j| ≤ K. The exact crop-tail diagnostic in §7 measures this directly [inferred].
- **Hadamard form in θ.** Eq. (4) is the user's Jacobian formula with ω_q made explicit. The physics service needs no change for the N-update.
- **Brent–Kung relevance.** Only the "special left-compositions" (√, reciprocal, exp) are needed.\[23\] General composition and reversion are avoided by eq. (9), so the O(n^{1/2}) Brent–Kung and Johansson algorithms are not on the critical path.
- **Conformal gauge as a later extension.** The exterior conformal map's Laurent coefficients are a canonical shape coordinate with a known perturbation theory (arXiv:2112.11026).\[30\] Using them would require a Fornberg/Wegmann Newton solve per update, which is beyond the current scope.
- **README side note.** The default-branch README records that the Cartesian chart "under its polar-angle gauge" is star-shaped, "an open concern recorded 2026-09-15" [read].\[1\] Confirm that the shape-continuation branch's arclength gauge does not share that restriction.

## Sources

1. [GitHub - ShiyuanDeng/Neural-BEM](https://github.com/ShiyuanDeng/Neural-BEM)
2. <https://arxiv.org/pdf/2210.11607>
3. <https://www.cambridge.org/core/services/aop-cambridge-core/content/view/D4F49AB00C9D89921CBBE374C67A9AD1/S1446181100011603a.pdf/integral_equation_methods_in_inverse_obstacle_scattering.pdf>
4. [Iteratively regularized Newton-type methods for general data misfit functionals and applications to Poisson data](https://arxiv.org/pdf/1105.2690)
5. [A Newton-type method for a transmission problem in inverse scattering - IOPscience](https://iopscience.iop.org/article/10.1088/0266-5611/14/5/008)
6. [On the convergence of a new Newton-type method in inverse scattering](https://www.semanticscholar.org/paper/On-the-convergence-of-a-new-Newton-type-method-in-Potthast/6c8f83695b8445887efded97f26eda1922cf749a)
7. [FAST METHODS FOR THREE–DIMENSIONAL INVERSE OBSTACLE SCATTERING PROBLEMS](http://num.math.uni-goettingen.de/hohage/obstacle3D.pdf)
8. [Removing the Stiffness from Interfacial Flows with Surface ...](https://users.cms.caltech.edu/~hou/papers/SSD_jcp94.pdf)
9. <https://arxiv.org/pdf/2110.12432>
10. [Spectrally Accurate Algorithm for Points Redistribution on Closed Curves](https://epubs.siam.org/doi/10.1137/20M1314690)
11. [Evolution of curves on a surface driven by the geodesic curvature and external force](https://www.researchgate.net/publication/242494925_Evolution_of_curves_on_a_surface_driven_by_the_geodesic_curvature_and_external_force)
12. [Search](https://arxiv.org/search/math?searchtype=author&query=Sevcovic,+D)
13. [A second-order in time, BGN-based parametric finite element method for geometric flows of curves](https://arxiv.org/html/2309.12875)
14. [Practical isogeometric shape optimization: parametrization by means of regularization](https://academic.oup.com/jcde/article/8/2/547/6097073)
15. [Isogeometric shape optimization of photonic crystals via Coons patches](https://www.researchgate.net/publication/222646966_Isogeometric_shape_optimization_of_photonic_crystals_via_Coons_patches)
16. [To appear in Computer Methods in Applied Mechanics and Engineering](https://cdm.me.wisc.edu/pub/ShapeOptCoonsRev1.pdf)
17. [Analysis of the first variation and a numerical gradient flow for integral Menger curvature](https://arxiv.org/pdf/1408.6517)
18. [4 Parametrization of closed curves and surfaces](https://www.sci.utah.edu/~gerig/CS7960-S2010/project3/Kelemen_EllipticHarmonicsOnly.pdf)
19. [1Analytic functions and conformal maps](https://arxiv.org/html/cond-mat/0409439v1)
20. [Fourier Series Methods for Numerical Conformal Mapping of Smooth Domains](https://www.math.wichita.edu/~delillo/TD_tutorial.pdf)
21. [A Fornberg-like method for the numerical conformal mapping of bounded multiply connected domains](https://www.researchgate.net/publication/277069535_A_Fornberg-like_method_for_the_numerical_conformal_mapping_of_bounded_multiply_connected_domains)
22. [Fast Algorithms for Manipulating Formal Power Series R P. BRENT](https://www.eecs.harvard.edu/~htk/publication/1978-jacm-brent-kung.pdf)
23. [\[1108.4772\] A fast algorithm for reversion of power series](https://ar5iv.labs.arxiv.org/html/1108.4772)
24. [A FAST ALGORITHM FOR REVERSION OF POWER SERIES FREDRIK JOHANSSON](https://fredrikj.net/math/reversion.pdf)
25. [Newton–Schulz Iterations](https://www.emergentmind.com/topics/newton-schulz-iterations)
26. [Gram Matrix Representation](https://link.springer.com/chapter/10.1007/978-3-319-53688-0_2)
27. [Truss topology design under harmonic loads: Peak power minimization with semidefinite programming](https://arxiv.org/pdf/2401.16175)
28. <https://arxiv.org/abs/2210.11607>
29. [A second degree Newton method for an inverse obstacle scattering problem - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0021999111003846)
30. <https://arxiv.org/abs/2112.11026>
