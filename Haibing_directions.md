# Review of the Proposed Upgrades to the Fourier–Galerkin Müller Inverse Shape Solver: What Is Backed by Literature and What Appears New

Most of the review's new parts are standard tools (Maue's identity, Neumann series, Schur complements, dual-weighted residuals, interpolatory model reduction, Cayley/ItI transforms) correctly transferred into the coefficient-space Fourier–Galerkin setting. Three pieces had no direct prior work in my search: the coefficient-space step certificate, the incremental Chebyshev recurrence for matrix updates, and the Riccati/ItI shape flow written in Fourier–Galerkin form. All the mathematical identities I checked are correct. The main overclaims concern the practical benefit (speed, bandedness) rather than correctness.

## TL;DR

- **Correct and mostly standard:** items 1, 5, 6 and 8 are textbook results restated in Fourier-coefficient form. Items 2, 7, 9 and 10 are known results newly applied here. The general closed form for the singular-weight Fourier coefficients (item 2) and the exact bandwidth bound are correct by my own derivation; only the j = 0 and j = 1 cases appear in the sources I read.
- **No prior work found:** the Wiener-type certified step region for Fourier curves (item 3), the difference recurrence ΔT_j used to update BIE matrices (item 4), and the Hamiltonian/ItI Riccati flow for the weighted DtN in coefficient form (item 11). The closest prior work is coefficient conditions for harmonic univalence, Nicholls–Reitich perturbation recursions, and Grieser / Henry–Louro DtN shape derivatives.
- **Overstated or unsupported:** item 4 gives no reduction in operation count. The bandedness in item 2 helps little at the final K = 64. Items 5–7 speed up linear solves, which are probably not the bottleneck for a dense system of a few hundred unknowns. The Hamiltonian form in item 11 needs a conjugate (or index-reversed) transpose. References R1, R10 and R11 only loosely support the claims attributed to them.

## How to read this report

Tags used below:
- **[S]** means read directly from a source I opened or whose abstract or snippet I retrieved.
- **[I]** means my own derivation or inference.
- **[M]** means bibliographic detail from memory that I did not re-verify in this session.

Notation follows the review. Symbols:
- z(θ) is the curve and v = |z'| its speed.
- D = diag(im) is the Fourier derivative and C_g is the Toeplitz convolution matrix of g.
- V, K, K', T are the single-layer, double-layer, adjoint double-layer and hypersingular operators.
- N is the trace band, K the storage band and M the update band.

## Key Findings by Item

### 1. Weighted-trace Maue reduction and K' as index-reversed transpose

**Verdict: standard (a).** The truncation remark is correct and practically important.

The identity is Maue's integration by parts. Kress (1995) writes it as follows **[S]**:\[1\]

$$T\varphi = \tfrac{d}{ds} S \tfrac{d\varphi}{ds} + k^2\, \nu\cdot S(\nu\varphi)$$

(J. Comput. Appl. Math. 61, 345–360; PDF: https://webhome.auburn.edu/~jzl0097/teaching/math_8970/Kress.pdf).

Domínguez–Turc give the parametrized form [H_k g] = [D V_k D g] − ik²[V_k((x'(s)·x'(·))g)] and state that K and K^T "are transpose to each other" **[S]** (https://arxiv.org/abs/1510.06682). \[2\] The printed "−ik²" looks like a typo or a convention artefact **[I]**.

Writing x'(s)·x'(t) = Σ_j x_j'(s)x_j'(t) turns the second term into Σ_j C_{x_j'} V C_{x_j'} in coefficient form. So the review's T_k is this identity under the weighted-flux convention **[I]**.

The index-reversed transpose (K')_{mn} = K_{−n,−m} follows from swapping the kernel arguments in the Galerkin integral with basis e^{imθ} **[I]**. It is a plain transpose, not a conjugate transpose, because Helmholtz kernels are complex-symmetric.

The truncation claim is correct **[I]**. C_{x'} maps modes |n| ≤ N to |n| ≤ N+K, so the Galerkin matrix of C V C needs V on N+K modes before cropping. Using V_N on both sides gives a product of Galerkin matrices, not the Galerkin matrix of the product. Because x' has only K harmonics, the expansion is finite and exact.

Reference check: R1 (Boubendir–Domínguez–Levadoux–Turc, https://arxiv.org/abs/1312.6598, https://doi.org/10.1137/140964230) is about regularized combined-source formulations built from approximations of admittance/DtN operators **[S]**.\[3\] Its abstract says nothing about Maue's identity in Fourier coefficients. Kress (1995) and Domínguez–Turc (2016) are the better citations for this item.

### 2. Müller cancellation and the analytic singular weights Ψ_j

**Verdict: known but newly applied (b).** The j = 0 and j = 1 coefficients are in the literature. The general-j closed form and the exact bandwidth bound are correct; I found no paper stating them in this form.

Bessel series **[I]**: J0(x) = Σ(−1)^j (x/2)^{2j}/(j!)². With R the squared distance, this gives the stated a_j = (−1)^j(k_e^{2j} − k_i^{2j})/(4^j (j!)²). The j = 0 term cancels.

The Müller cancellation of the leading singularities is known. The Domínguez–Turc discretization of the Kress–Roach/Müller system replaces H_− − H_+ by T_− − T_+, because the principal part DΛD does not depend on the wavenumber **[S]** (https://arxiv.org/abs/1510.06682). \[2\]

Fourier coefficients, with g(t) = 4 sin²(t/2):
- **j = 0:** the classical series log(4 sin²(t/2)) = −2Σ_{n≥1} cos(nt)/n gives Ψ̂_0(0) = 0 and Ψ̂_0(n) = −1/|n| **[I]**.
- **Recurrence:** g = 2 − e^{it} − e^{−it} gives the review's recurrence exactly **[I]**.
- **j = 1:** the recurrence gives 2, −3/2 and 2/(|n|(n²−1)) **[I]**. Domínguez–Turc list coefficients 1/2, −3/8 and (1/4)[1/|n+1| + 1/|n−1| − 2/|n|] for sin²(t/2) log sin²(t/2) **[S]**.\[2\] These equal Ψ̂_1/4, so their table matches the review up to the factor 4 in g **[I]**.
- **Their j = 0 entry:** they print −2 log 4 and −2/|n| for log sin²(t/2).\[2\] This differs from the standard values by a normalization factor **[I]**, so do not copy constants between the two documents without rechecking.

General closed form, verified by induction **[I]**:

$$\widehat{\Psi}_j(n) = \frac{(-1)^{j+1}(2j)!}{\prod_{l=-j}^{j}(n-l)},\qquad |n|>j$$

The step uses the fact that the second difference of 1/[(n−j)⋯(n+j)] equals (2j+1)(2j+2)/[(n−j−1)⋯(n+j+1)]. That gives c_{j+1} = −(2j+1)(2j+2)c_j with c_0 = −1, which reproduces the review's formula, since n Π_{l=1}^{j}(n² − l²) = Π_{l=−j}^{j}(n−l). The coefficients decay like |n|^{−(2j+1)}, consistent with the extra smoothing of the j = 1 weight reported by Domínguez–Turc.\[2\]

Bandedness is correct **[I]**. The weight depends only on θ−φ, so it is Toeplitz in Fourier space. The smooth factor q^j has total frequency r+s within [−2jK, 2jK]. The Galerkin index condition forces m−n = r+s, so (B_j)_{mn} = 0 for |m−n| > 2jK exactly. Matrix multiplication by a trigonometric polynomial of degree d giving a banded Toeplitz structure is standard. Applying it to the singular part of the Müller matrix is the new step here.

Overclaim **[I]**: the bandwidth 2jK is at least 128 already at j = 1 and K = 64. If N is of order 64–128, B_1 is effectively full at the final stage. Bandedness only helps in the early continuation stages, where K is small relative to N.

A second numerical caveat **[I]**: at high contrast the subtracted polynomial Σ a_j R^j has the same growth-and-cancellation issue as the original power series. So P_s must stay small, and E(R) must itself be evaluated stably over the whole range of R.

Reference check: R4 (Slevinsky–Olver, https://arxiv.org/abs/1507.00596) treats "univariate singular integral equations over unions of intervals" using Chebyshev and ultraspherical polynomials to obtain "almost-banded" systems, "utilizing low rank approximations for sparse representations of the bivariate kernels" **[S]**.\[4\] It supports the general "banded + low rank" idea (A ≈ B_band + UCU^H). It does not cover closed periodic curves, and its bandedness comes from the ultraspherical basis, not from a total-frequency bound.

The closest periodic prior work is the fast Fourier–Galerkin line (Cai–Xu, "A Fast Fourier–Galerkin Method for Solving Singular Boundary Integral Equations," SIAM J. Numer. Anal. 46 (2008) 1965–1984, https://doi.org/10.1137/070703478; Jiang–Wang–Yu, https://doi.org/10.1007/s11075-021-01082-0). Jiang–Wang–Yu split the operator "into a convolution operator and a compact operator" and compress the matrix to O(n) nonzeros **[S]**.\[5\]\[6\] That gives compression by truncation, not exact bands.

### 3. Coefficient-based geometry safe region

**Verdict: elementary ingredients are standard; using them as a certified step region for Fourier-curve shape updates had no prior found (c).**

The inequality chain is correct **[I]**:

$$|W_{z+\Delta z}| \ge |W_z| - |W_{\Delta z}|,\qquad |W_{\Delta z}| \le \textstyle\sum_m |m|\,|d_m|$$

The second bound holds because (e^{imθ} − e^{imφ})/(e^{iθ} − e^{iφ}) is a sum of |m| unimodular terms. On the diagonal, W(θ,θ) = z'(θ)/(ie^{iθ}). So |W| ≥ μ bounds the speed from below and the chord from below by μ|e^{iθ} − e^{iφ}|, which gives injectivity and a bi-Lipschitz bound.

The q_min bound is correct because q = |W|² is real and nonnegative **[I]**. However, the off-diagonal coefficient sum is small only for near-circles. For elongated or strongly non-convex shapes, expect INCONCLUSIVE often, with frequent fallback to the sampled test.

To freeze the Chebyshev interval, the safe region also needs the matching upper bound |W_{z+Δz}| ≤ |W_z| + η_g μ, which follows the same way **[I]**.

Prior work (from the subagent search, which found no direct match):
- Coefficient conditions for harmonic univalence such as Σ_{n≥2} n(|a_n| + |b_n|) ≤ 1 (H. Silverman, "Harmonic univalent functions with negative coefficients," J. Math. Anal. Appl. 220 (1998) 283–289, https://doi.org/10.1006/jmaa.1997.5882, a DOI that matches citing papers' reference lists; Clunie–Sheil-Small 1984). These are the nearest ℓ¹-type injectivity conditions, but for maps of the disc, not certificates for a given trigonometric curve.
- Sharp counts of self-intersections of trigonometric curves (Kalmykov–Kovalev, https://arxiv.org/abs/2407.12572). \[7\]
- A 2026 resultant-based self-intersection barrier for Fourier-coefficient curves in shape optimisation (Kakhsaz Malayeri, https://optimization-online.org/2026/09/rooting-out-self-intersection-an-algebraic-shape-optimization-barrier/). \[8\] This is a non-refereed preprint.
- Energy penalties against self-intersection in inverse obstacle scattering (Eckhardt et al., https://arxiv.org/abs/1903.05074, which uses "penalization with the Möbius energy").\[9\]

### 4. Incremental geometry and incremental Chebyshev recurrence (top-priority idea)

**Verdict: the algebra is standard and correct; applying it to update BIE matrices had no prior found (c). The efficiency claim is unsupported, and the precision claim holds only in a narrow case.**

The recurrence follows from T_{j+1}(X) = 2X T_j(X) − T_{j−1}(X), by subtracting the values at X_1 and X_0 **[I]**:

$$\Delta T_{j+1} = 2X_1\,\Delta T_j + 2\,\Delta X\,T_j(X_0) - \Delta T_{j-1}$$

The directional-derivative version and the ΔR, Δq formulas are also correct **[I]**.

Your operation-count observation is right **[I]**. Each degree needs two bivariate coefficient convolutions (X_1·ΔT_j and ΔX·T_j(X_0)) against one for direct recomputation, plus storage of T_j(X_0) for every j. So "reduce repeated computation" does not hold for the update itself.

The precision gain is real only for quantities that use ΔA as a separate object **[I]**. Examples are finite-difference Jacobian checks, the Schur derivative δS, or a low-rank update of a factorisation. If the solver only needs A_1, computing it directly already has error at machine-precision level relative to ‖A_1‖, and the incremental route adds nothing.

The log1p step also needs care **[I]**. log(q_1) − log(q_0) = log(1 + Δq/q_0) requires the quotient Δq/q_0 in coefficient space, which means a division or reciprocal expansion. This is not one of the pure multiplication operations the node-free pipeline relies on.

Prior work: Nicholls–Reitich show that boundary-perturbation recursions suffer "significant cancellations … in the recurrence relations satisfied by successive terms in a perturbation series" **[S]** (https://doi.org/10.1364/JOSAA.21.000590). \[10\]\[11\] Incremental recursions are therefore not automatically stable, and stability should be tested at large ΔX. Other prior work:
- Bruno–Reitich's "method of variation of boundaries" (https://doi.org/10.1364/JOSAA.10.001168) is the classical perturbation-in-shape approach.\[12\]\[13\]
- Potthast gives Fréchet derivatives of boundary integral operators (https://doi.org/10.1088/0266-5611/10/2/016). \[14\]
- Factorisation updates under geometry change exist only for local perturbations. Ryan–Damle call efficient updating under global changes open (https://arxiv.org/abs/2001.11619; Minden et al., https://arxiv.org/abs/1411.5706) **[S]**.\[15\]\[16\]

### 5. Anchor preconditioning and controlled residual correction

**Verdict: standard (a).**

The bound is the geometric-series tail **[I]**:

$$x - x_q = \sum_{j>q} E^j g,\qquad \|x - x_q\| \le \frac{\rho^{q+1}}{1-\rho}\,\|g\|$$

The production choice is standard practice: GMRES right-preconditioned by the fixed old LU, with flexible GMRES only if the inner solve varies. Krylov recycling for slowly changing sequences is established (Parks, de Sturler, Mackey, Johnson, Maiti, "Recycling Krylov subspaces for sequences of linear systems," SIAM J. Sci. Comput. 28(5) 1651–1674 (2006), https://doi.org/10.1137/040607277; Kilmer–de Sturler, "Recycling subspace information for diffuse optical tomography," SIAM J. Sci. Comput. 27(6) 2140–2166 (2006) **[S]**, surveyed in https://arxiv.org/abs/2001.10347). Computing the residual with the trusted current operator is good practice.

Caveats **[I]**:
- ‖E‖ ≤ ρ < 1 is not guaranteed after an LM step at high frequency or high contrast, and ‖E‖ itself costs extra to estimate.
- In the review's own GPU-assembly / CPU-LU design, the dense system has roughly 2(2N+1) unknowns, i.e. a few hundred. LU at that size takes milliseconds, so assembly, not solving, is the likely bottleneck. This reduces the speed value of items 5–7.

### 6. Schur elimination of high trace modes with feedback

**Verdict: standard (a).** The formulas are correct.

Expanding the review's product form gives **[I]**:

$$\delta S = \delta A_{LL} - \delta A_{LH} Z A_{HL} - A_{LH} Z\, \delta A_{HL} + A_{LH} Z\, \delta A_{HH} Z A_{HL}$$

The bound ‖S − S_q‖ ≤ ‖A_LH‖‖Z − Z_q‖‖A_HL‖ is immediate. Eliminating the observation consistently (ℓ_eff, d_eff) is the usual static-condensation bookkeeping.

The approach is justified in this setting **[I]**. Domínguez–Turc note that the leading part of the Costabel–Stephan operator "is diagonal in the complex exponential bases" **[S]**.\[2\] So A_HH is close to diagonal plus a compact remainder, and a Neumann series for Z_q should converge on the high modes. Elimination saves time only if H is large; otherwise its value is the feedback consistency, not cost.

### 7. Forward–adjoint local reduced model with directional enrichment

**Verdict: known but newly applied (b).** The O(α²)/O(α⁴) orders are the expected ones.

Two-sided projection with forward solutions in V and adjoint solutions in W matching the output and its first parameter derivatives is the interpolatory-MOR result of Baur–Beattie–Benner–Gugercin (SISC 33(5) 2489–2518, https://doi.org/10.1137/090776925) **[S]**.\[17\] It is used for nonlinear inversion in diffuse optical tomography by de Sturler et al., who follow "well-known results regarding interpolatory parametric model reduction in [6, Theorem 4.1-4.2]" **[S]** (https://arxiv.org/abs/1311.0922). \[18\]\[19\]

Adding one directional derivative on each side matches the output through third order along the path **[I]**. The output error is the product of the primal and dual residuals, which gives O(α²)·O(α²) = O(α⁴). Without enrichment, O(α)·O(α) = O(α²). The reported slopes 1.990 and 4.006 agree.

Reduced-basis BIE scattering is also established (Fares–Hesthaven–Maday–Stamm, J. Comput. Phys. 230 (2011) 5532–5555 **[S]**; Ganesh–Hesthaven–Stamm, https://doi.org/10.1016/j.jcp.2012.07.008). \[20\]\[21\]\[22\]

Caveat **[I]**: shape enters A(a) non-affinely. A_r(a) = W^H A(a) V still requires the full A(a), so assembly cost is unchanged. Matching all first derivatives also needs V and W to span all 24 source and receiver solutions at each frequency.

### 8. Error control for the LM step

**Verdict: standard components (a); combining them for inverse obstacle scattering is newly applied (b).**

DWR identity **[I]**: with r_p = b − Ax̂ and r_d = ℓ − A^H λ̂, the error F − F_corr = r_d^H A^{−1} r_p is exact. The resolvent bound follows from A^{−1} = (I − E)^{−1}P_0.

LM bound **[I]**: H ⪰ λΓ gives ‖Γ^{1/2}H^{−1}Γ^{1/2}‖ ≤ 1/λ, hence ‖d̂ − d‖_Γ ≤ λ^{−1}‖Γ^{−1/2}ζ‖. This requires symmetric positive definite Γ and real symmetric H.

This bound only covers the inexact linear solve of the LM system. It does not cover errors in J or g from an approximate forward model, because those change H and g themselves. Also, 1/λ is loose when λ is small.

Objective bound **[I]**: with residual error ‖e‖ ≤ ε_r,

$$|\Phi - \hat\Phi| \le \varepsilon_r\|\hat r\| + \tfrac12\varepsilon_r^2$$

So the acceptance rule guarantees a true decrease, provided ε_r is a rigorous bound on the full data-residual vector. A bound on one output functional is not enough.

Reference check:
- R6 (Qian–Grepl–Veroy–Willcox, SISC 39(5) S434–S460, https://doi.org/10.1137/16M1081981) uses the reduced-basis method "in conjunction with a trust region optimization framework" with certified error bounds **[S]**. It supports the acceptance logic, but for affinely parametrized PDEs with quadratic costs.\[23\]
- R7 (Dembo–Eisenstat–Steihaug, "Inexact Newton methods", SIAM J. Numer. Anal. 19(2) (1982) 400–408, https://doi.org/10.1137/0719025) supports forcing-term inexact solves, not certified bounds.
- Yue–Meerbergen use interpolatory reduced models as optimisation surrogates with a "relaxed first-order condition" **[S]** (https://doi.org/10.1137/120869171). \[24\]

### 9. Separate management of M, K, N and frequencies; shape-metric identifiability

**Verdict: known but newly applied (b).**

Frequency continuation is recursive linearization (Borges–Gillman–Greengard, SIAM J. Imaging Sci. 10(2) 641–664, https://doi.org/10.1137/16M1093562) **[S]**.\[25\]\[26\]\[27\] That paper is an inverse-medium method that reconstructs "an unknown sound speed" by "seeking a suitably band-limited approximation of the sound speed profile" at increasing frequency, so the closer obstacle-boundary analogue is Borges–Greengard, "Inverse Obstacle Scattering in Two Dimensions with Multiple Frequency Data and Multiple Angles of Incidence," SIAM J. Imaging Sci. 8(1) 280–298 (2015). Separating the update, storage and trace bands is a sensible refinement, with no specific prior found.

Whitening the Jacobian by G^{−1/2} and then taking an SVD is a metric-weighted SVD, standard in regularized inversion **[I]**. One caveat: G is singular if some direction has zero normal displacement, for example pure reparametrization. In that case use a pseudo-inverse or remove those directions first.

### 10. Circle closed forms and first-order single-layer perturbation

**Verdict: standard (a).** The formulas are correct under the weighted-trace convention.

Graf's theorem with |x| = |y| = a gives H_0 = Σ J_m H_m e^{im(θ−φ)}. This yields σ_m = (iπ/2)J_mH_m when the weighted flux absorbs |z'| = a. With a test-side factor a, τ_m = (iπt²/2)J_m'H_m' **[I]**.

The κ_m formula takes the average of the one-sided limits **[I]**. Sanity checks:
- small t, m ≠ 0: κ_m → 0, as for the Laplace double layer on a circle;
- m = 0: κ_0 → −1/2.

Perturbation **[I]**: δV = a^{−1}(M_h K' + K M_h), with M_h the multiplication by h. With K and K' both diagonal with entries κ, this gives (δV)_mn = (κ_m + κ_n)ĥ_{m−n}/a, banded by the bandwidth of h. Perturbation around a circle is classical (Nicholls–Reitich operator expansions; Bruno–Reitich).\[13\]\[28\] Use the circle mainly as a unit test.

### 11. Riccati evolution of the weighted interior DtN; ItI form

**Verdict: known for Laplace / homothetic families (b); the Fourier–Galerkin Helmholtz ItI Riccati with transport term had no prior found (c).** One notational error.

Circle check, using Bessel's equation **[I]**:

$$\frac{dP_m}{da} = \frac{m^2 - P_m^2}{a} - k^2 a$$

The general Riccati with h = 1, β = 0, v = a reproduces this, since −D C_{1/a} D = m²/a.

Grieser derives the shape derivative of the Laplace DtN, Ṅ = −div_∂ a∇ + 2aH𝒩 − 𝒩a𝒩 (Theorem 13), and says the exterior case is the same **[S]** (https://arxiv.org/abs/1208.3120). \[29\] R8 therefore supports the structure, for Laplace and without weighting or k.

Henry–Louro–Soares factorize star-shaped problems "using the technique of invariant embedding", with "the family of domains … defined by a homothety", which leads to a Riccati equation for the DtN **[S]** (https://doi.org/10.1007/978-3-642-04802-9_15). \[30\]\[31\]\[32\]\[33\]

Hamiltonian lifting **[I]**: P = YX^{−1} gives P' = Q − B̃P − PB − PMP. Matching terms requires B = C_β D and B̃ = −D C_β. The review's "−B^T" is correct only if T means the conjugate transpose (C_β is Hermitian for real β, and D^H = −D) or the index-reversed transpose. With a plain transpose it fails.

ItI: Gillman–Barnett–Martinsson write "Since ItI maps are unitary, this formulation is inherently numerically stable, and is immune to problems of artificial internal resonances" **[S]** (https://arxiv.org/abs/1308.5998). \[34\] Unitarity holds for the lossless case **[I]**: the weighted P is Hermitian in the plain coefficient inner product, because P = M_v𝒩 and 𝒩 is self-adjoint in L²(ds). For the damped copy k(1+0.25i), the ItI map is not unitary.

Reference check: R10 (Bruno–Pandey, https://arxiv.org/abs/1907.05914) uses ItI maps to couple volume and boundary discretizations and proves unique solvability **[S]**.\[35\] R11 (Beck–Canzani–Marzuola, https://arxiv.org/abs/2103.14700) proves norm bounds for impedance operators "on convex, polygonal domains" and invertibility of merge operators **[S]**.\[36\] Neither addresses shape evolution, so citing them for the Riccati/ItI flow is overreach.

### 12. Overall novelty framing

**Verdict: the combination as stated had no prior found; several sub-combinations exist.**

Existing sub-combinations **[S]**:
- reduced-order models inside nonlinear inversion (de Sturler et al.);\[18\]
- Krylov recycling in tomographic inversion (Kilmer–de Sturler);\[37\]
- reduced-basis BIE scattering (Fares et al.; Ganesh et al.);\[20\]\[22\]
- certified trust-region reduced-basis optimisation (Qian et al.);\[23\]
- factorisation updating under local geometry change (Minden et al.; Ryan–Damle).\[15\]\[16\]

Fast Fourier–Galerkin BIEs on smooth curves are established (Cai–Xu; Jiang–Wang–Yu), but they use quadrature for the kernel coefficients. I found no prior work combining, for inverse transmission obstacle scattering, (i) coefficient-only assembly, (ii) certified geometry steps, (iii) incremental matrix updates and (iv) certified LM acceptance **[I]**. The review's narrow framing of novelty is accurate.

## Secondary: Closest Prior Work to the Original Method

- **Node-free Müller assembly:** the closest is the Kress / Martensen–Kussmaul log splitting plus product integration of Domínguez–Turc (https://arxiv.org/abs/1510.06682), and the fast Fourier–Galerkin methods.\[2\] No source I found expands the smooth remainder in Chebyshev polynomials of R and the divided difference W **[I]**. The reported drop from 1e6 to 3e-14 fits the known cancellation of power series when k_i R is large **[I]**.
- **Non-self-intersection certificate:** see item 3; no direct prior found.
- **Band and frequency continuation:** see item 9; it is a variant of Borges–Gillman–Greengard recursive linearization.\[25\]

## Recommendations

1. Keep items 1, 2, 3 and 10 as core infrastructure. They are correct and cheap.
2. Make the weighted-trace and transpose conventions explicit in the note. Items 1, 10 and 11 depend on them.
3. Downgrade item 4 from "top priority". Implement it only where ΔA is used directly (δS, finite-difference checks), and benchmark both accuracy and time against direct recomputation at small and large ΔX.
4. Before investing in items 5–7, profile assembly time against LU time at the final N. If LU is a small fraction, treat these items as certification tools, not speed-ups.
5. Fix the Hamiltonian transpose in item 11, and drop R10 and R11 as support for the shape flow.
6. Replace R1 with Kress (1995) and Domínguez–Turc (2016) as the Maue citations.

## Caveats

- My searches were limited. "No prior found" means I found none in about 18 searches plus one subagent pass; it does not prove that none exists. Items 3, 4 and 11 most need a targeted literature check before any novelty claim is published.
- Some bibliographic details were checked only against citing papers' reference lists rather than publisher pages: Silverman's DOI and the Cai–Xu page range.
- The circle and Maue formulas were checked only up to sign conventions for T and for the normal direction.

## Overall Assessment

- **Appears new:** the coefficient-space certified step region (item 3), the ΔT recurrence for incremental BIE matrix updates (item 4), the general-j closed form for Ψ_j together with the exact 2jK band structure (item 2, as a stated and used result), and the coefficient-form Helmholtz Riccati/ItI shape flow (item 11).
- **Standard tools applied here:** Maue reduction, index-reversed transpose, Neumann/GMRES anchor solves, Schur condensation, interpolatory forward–adjoint reduced models, DWR and inexact-LM acceptance, circle closed forms, and frequency continuation.
- **Overstated or unsupported:**
  - the computational savings of item 4;
  - bandedness as a benefit at K = 64;
  - the speed value of items 5–7 for a dense system of a few hundred unknowns;
  - the LM step bound treated as covering forward-model error;
  - ItI unitarity for the damped copy;
  - the plain transpose in the Hamiltonian form;
  - R1, R10 and R11 as support for the claims attributed to them. R4, R5, R6, R8 and R9 support their claims, but only in more restricted settings (intervals, affine parameters, Laplace, lossless).

## Sources

1. [Kress.pdf](https://webhome.auburn.edu/~jzl0097/teaching/math_8970/Kress.pdf)
2. [High order Nystr\\"om methods for transmission problems for Helmholtz equation](https://arxiv.org/pdf/1510.06682)
3. <https://arxiv.org/abs/1312.6598>
4. [\[1507.00596\] A fast and well-conditioned spectral method for singular integral equations](https://arxiv.org/abs/1507.00596)
5. [A fast Fourier-Galerkin method solving boundary integral equations for the Helmholtz equation with exponential convergence](https://dl.acm.org/doi/10.1007/s11075-021-01082-0)
6. [A fast Fourier-Galerkin method solving boundary integral equations for the Helmholtz equation with exponential convergence](https://link.springer.com/article/10.1007/s11075-021-01082-0)
7. [A sharp bound on the number of self-intersections of a trigonometric curve](https://arxiv.org/pdf/2407.12572)
8. [Rooting Out Self-Intersection: An Algebraic Shape-Optimization Barrier – Optimization Online](https://optimization-online.org/2026/09/rooting-out-self-intersection-an-algebraic-shape-optimization-barrier/)
9. [Elastic energy regularization for inverse obstacle scattering problems](https://arxiv.org/pdf/1903.05074)
10. [Shape deformations in rough-surface scattering: cancellations, conditioning, and convergence](https://www.osapublishing.org/abstract.cfm?uri=josaa-21-4-590)
11. [SIAM J. MATH. ANAL. c ⃝2005 Society for Industrial and Applied Mathematics](http://homepages.math.uic.edu/~nicholls/papers/Final/dnolip.sima.pdf)
12. [Numerical solution of diffraction problems: a method of variation of boundaries](https://opg.optica.org/josaa/abstract.cfm?uri=josaa-10-6-1168)
13. [Copyright © by SIAM. Unauthorized reproduction of this article is prohibited.](https://www.math.purdue.edu/~shen7/pub/NS_SINUM.pdf)
14. [Frechet differentiability of boundary integral operators in ...](https://people.math.ethz.ch/~hiptmair/Seminars/SHAPECALC/Papers/POT94.pdf)
15. [Parallel Skeletonization for Integral Equations in Evolving Multiply-Connected Domains](https://arxiv.org/pdf/2001.11619)
16. [A technique for updating hierarchical skeletonization-based factorizations of integral operators](https://arxiv.org/pdf/1411.5706)
17. [Interpolatory projection methods for parameterized model reduction](https://vtechworks.lib.vt.edu/handle/10919/48155)
18. [\[PDF\] Nonlinear Parametric Inversion Using Interpolatory Model Reduction](https://www.semanticscholar.org/paper/Nonlinear-Parametric-Inversion-Using-Interpolatory-Sturler-Gugercin/f04f1cf95e410294db88d6c0211e03eb353a260c)
19. [Randomization for the Efficient Computation of Parametric Reduced Order Models for Inversion](https://arxiv.org/html/2007.06027)
20. [The reduced basis method for the electric field integral equation (Journal Article)](https://www.osti.gov/etdeweb/biblio/21499753)
21. [ArbiLoMod: Local Solution Spaces by Random Training in Electrodynamics](https://link.springer.com/chapter/10.1007/978-3-319-58786-8_9)
22. [A reduced basis method for electromagnetic scattering by multiple particles in three dimensions](https://infoscience.epfl.ch/entities/publication/40f32d65-6218-4c79-9afe-f6102d5efe7c)
23. [(PDF) A Certified Trust Region Reduced Basis Approach to PDE-Constrained Optimization](https://www.researchgate.net/publication/305160735_A_Certified_Trust_Region_Reduced_Basis_Approach_to_PDE-Constrained_Optimization)
24. [Accelerating Optimization of Parametric Linear Systems by Model Order Reduction](https://dx.doi.org/10.1137/120869171)
25. [High resolution inverse scattering in two dimensions using recursive linearization - NYU Scholars](https://nyuscholars.nyu.edu/en/publications/high-resolution-inverse-scattering-in-two-dimensions-using-recurs)
26. [Research](https://sciences.ucf.edu/math/borges/research/)
27. [Mathematical analysis and numerical methods for inverse scattering problems](https://ems.press/content/book-chapter-files/33328)
28. [(PDF) Analytic continuation of Dirichlet-Neumann operators](https://www.researchgate.net/publication/226311027_Analytic_continuation_of_Dirichlet-Neumann_operators)
29. <https://arxiv.org/pdf/1208.3120>
30. [Factorization by Invariant Embedding of a Boundary Value Problem for the Laplace Operator](https://link.springer.com/chapter/10.1007/978-3-642-04802-9_15)
31. [Maria do C´eu Cerqueira Soares FACTORIZATION BY INVARIANT EMBEDDING OF](https://run.unl.pt/bitstream/10362/2708/1/Soares_2006.pdf)
32. [Factorization of Boundary Value Problems Using the Invariant Embedding Method](https://www.sciencedirect.com/book/monograph/9781785481437/factorization-of-boundary-value-problems-using-the-invariant-embedding-method)
33. [The star-shaped domain](https://www.researchgate.net/figure/The-star-shaped-domain_fig1_221463310)
34. <https://arxiv.org/abs/1308.5998>
35. <https://arxiv.org/abs/1907.05914>
36. <https://arxiv.org/abs/2103.14700>
37. [(PDF) Recycling Subspace Information for Diffuse Optical Tomography](https://www.researchgate.net/publication/220411606_Recycling_Subspace_Information_for_Diffuse_Optical_Tomography)
