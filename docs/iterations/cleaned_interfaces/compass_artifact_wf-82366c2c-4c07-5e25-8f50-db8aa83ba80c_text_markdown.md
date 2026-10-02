# One Codex reset on Neural-BEM: ranked exploratory tasks

The best use of the day is a shape–frequency sensitivity atlas. It is the singular value spectrum of your shape Jacobian, computed across frequency and harmonic index, and it should be aimed directly at the open question in your own README: why does geometry error stop improving after the training objective drops by four orders of magnitude? Run it alongside a first inversion of real Institut Fresnel measured data, which your 2-D TM transmission solver can already model almost unchanged.

## TL;DR
- **Rank 1 (close to code):** build the sensitivity atlas, meaning singular values of the Jacobian from Fourier shape coefficients to scattered-field data, swept over frequency. Test two things: whether your joint K–M truncation rule matches the "stable region grows roughly linearly with wavenumber" result from inverse-scattering theory, and whether your TOP-009/TOP-010 geometry errors sit in the near-null space. It needs CPU only, the result can be checked against theory, and it produces both a figure and a paper argument.
- **Rank 2 (medium distance):** invert the 2001 Fresnel dielectric-cylinder files (dielTM_dec8f, twodielTM_8f; 1–8 GHz, TM). These are real measurements of exactly your forward model: a homogeneous dielectric in free space, 2-D TM. The obstacles are getting the data into the sandbox and calibrating it, not the physics.
- **The rest, in order:** TE polarisation plus its shape derivative (the 2-D step towards Maxwell), lossy ground (complex wavenumber), a sampling or topological-derivative initialiser for your failing distant-start scenes, a frequency-path comparison against Borges et al. recursive linearisation and stochastic continuation, time-domain synthesis against gprMax, half-space Green's functions, a 3-D scalar IBIM, and Algoim quadrature. Cloud Codex tasks should be CPU-only. Keep CUDA work for local runs.

## What I could and could not see in the repo

**Read directly** from https://github.com/ShiyuanDeng/Neural-BEM (public, branch `feature/ordered-boundary-nystrom`, 108 commits):
- The README describes the scope as "homogeneous full-space 2-D TMz dielectric transmission, neural implicit geometry, boundary-element forward modeling, and inversion".\[1\] TM (transverse magnetic) means the electric field is parallel to the cylinder axis, so the problem reduces to scalar Helmholtz.
- There are three inverse pipelines: Implicit MLP + Method B, Explicit Cartesian Fourier, and Explicit Radial Fourier. MLP means multilayer perceptron. For the MLP pipeline the README says the gradient is validated but recovery is "FAIL / unresolved".\[1\]
- The topology benchmark has twelve scenes. TOP-025 reports "7/12 pass all gates"; the earlier TOP-006 to TOP-010 runs passed 5/12, and "the distant ellipse/star case fails".\[1\]
- TOP-009/TOP-010: "the true geometry fits the same training acquisition to 3.23e-07 relative error". The reconstruction is "74,159x above the objective the true geometry attains". Four fixed defects were "each worth objective and none worth geometry". The stated open question: "why the gated geometry is insensitive to four orders of magnitude of training objective."\[1\]
- Some pieces already exist: `audit_star_observability_spectra.py`, `run_star_observability.py`, `run_kress_shape_derivative_validation.py`, the `gpr_bem_kress` module ("ordered Müller/Kress solves and opt-in single-interface discrete geometry/material derivatives"), and an `AGENTS.md` file for Codex.\[1\]
- The README says: "Layered ground and 3-D inversion are outside the current implementation." It also notes that the Cartesian chart is still star-shaped under its polar-angle gauge.\[1\]

**Not visible:** I could not find tracks named "ma" or "sc", or a solver named "node-free", in the README or the top-level file list. They may live on another branch, under different names, or locally. Wherever I refer to "sc" below, I am using your description, not code I read.

## Practical constraints on the Codex day

- **Read from OpenAI docs** (https://developers.openai.com/codex/cloud/environments, https://developers.openai.com/codex/cloud/internet-access): cloud tasks run a setup script that has internet access. The agent phase has internet access off by default ("By default, Codex blocks internet access during the agent phase").\[2\]\[3\] So any dataset has to be fetched in the setup script or committed to the repo. Neither the Fresnel files nor gprMax can be downloaded by the agent mid-task unless you turn agent internet access on.
- **Read from a GitHub issue** (https://github.com/openai/codex/issues/19676): the local CLI's workspace-write sandbox blocks GPU device access ("no /dev/nvidia* in bwrap namespace"). CUDA runs then need a less restricted sandbox mode or have to be launched outside Codex.\[4\]
- **Inferred:** I found no documentation that Codex cloud containers have GPUs, so assume they do not. Every task below is written to run on numpy/CPU at reduced size, with CUDA as an optional local speed-up.
- **Inferred, about budget:** I do not know your exact quota. "One full reset" is planned as roughly 6–10 substantial autonomous tasks, run in parallel where they are independent. Each estimate is given in tasks and in your own hours.

## Ranked ideas

### 1. Shape–frequency sensitivity atlas, used to explain TOP-010 — close to current code

**What it is.** The input is a reference shape (circle, ellipse, five-lobed star), a permittivity, a list of frequencies, and your transmitter/receiver layout. The output is the singular values and right singular vectors of the Jacobian J. J maps Fourier shape coefficients (normal-harmonic index n, up to M) to the complex scattered field at the receivers. The plots are singular value against index, one curve per frequency, plus a heat map of |right singular vector| against harmonic n.

**Why it matters.**
- *Read from the paper.* Kow, Salo & Zou (https://arxiv.org/html/2404.18482) prove that for two linear model problems the singular values "stay roughly constant in the stable region and decay exponentially in the unstable region". The stable region has size about κ^(n−1), where κ is the wavenumber and n the dimension. In 2-D that means roughly κ stable modes, and "the stable features are precisely the first ∼κ^{n−1} Fourier modes".\[5\]
- *My inference.* Their problems are a Herglotz density and a linearised potential, not an obstacle. Transferring the result to a penetrable obstacle in 2-D gives a cutoff near |n| ≈ kR, where k is the wavenumber and R the obstacle radius. Whether that k is the exterior or the interior wavenumber (k√εr) is an open, testable question for transmission problems.
- *Inferred.* This directly tests your rule of truncating K (geometry bandlimit) and M (update harmonics) together and tying both to frequency.
- *Inferred.* It also gives a concrete hypothesis for TOP-010. If the residual geometry error of the saved TOP-009 states projects mostly onto right singular vectors with singular values below the noise or tolerance level, then "objective improves, geometry doesn't" is expected behaviour of the resolution limit, not a bug. That would turn the README's open question into a result.

**Work.** 1–2 Codex tasks. Your time: 1–2 h to specify scenes and read results. The `audit_star_observability_spectra.py` script may already contain part of this. Codex should reuse it rather than rewrite it. It can be checked three ways: a finite-difference Jacobian against your analytic Kress derivative, a circle against the separable Bessel/Hankel case, and the cutoff location against kR.

**Reward.** Atlas figure v0. A table of numerical cutoff index against kR and against k√εr·R. A yes/no answer on whether the TOP-009 geometry error lies in the near-null space. This is plausibly a central figure for a paper and the foundation of your planned atlas.

**Risk.** Low. The only real risk is a muddled result in which the cutoff depends on both wavenumbers; that is still a finding. **GPU:** no.

**First Codex prompt.**
> In Neural-BEM, write `experiments/atlas/run_jacobian_spectrum.py`. For shapes {circle R=30 mm, ellipse 40×25 mm, star 5 lobes} with εr ∈ {2, 4, 9}, frequencies 0.5–8 GHz (12 values), and the existing default transmitter/receiver layout, assemble the Jacobian of scattered field w.r.t. normal-harmonic shape coefficients n = −40..40 using the existing Kress shape derivative in `gpr_bem_kress`. Validate 5 random columns against central finite differences (report relative error). Compute SVD per frequency; save singular values, right singular vectors, and the index where σ_j/σ_1 < 1e-3, plotted against kR and k√εr R. Then load the saved TOP-009 final and true geometries, express their difference in the same harmonic basis, and report the fraction of its norm lying in singular directions below 1e-3·σ_1 at each frequency used. CPU numpy only; add a pytest for the FD check. Write results to `results/atlas/` with a README.

### 2. First inversion of real measured data: 2001 Institut Fresnel dielectric cylinders — medium distance

**What it is.** The input is the measured total and incident electric fields from a lab-controlled experiment on dielectric cylinders, in the same 2-D TM setting as your solver. The output is a recovered boundary, and optionally εr, from real data.

**Facts read from the primary source.** All of these come from Belkebir & Saillard 2001, author copy at https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf.
- File structure: ASCII files with "a 10-line header" and then "7 columns": transmitter index, receiver index, frequency in GHz, real and imaginary total field, real and imaginary incident field.\[6\]
- Geometry: emitter at "720 mm ± 3 mm" and receiver at "760 mm ± 3 mm" from the centre. The target rotates "from 0° to 350° in steps of 10°" (36 transmitters) and the receiver "from 60° to 300° in steps of 5°" (49 receivers).\[6\]
- dielTM_dec8f and twodielTM_8f cover 1–8 GHz in 1 GHz steps.\[7\] The cylinders have radius 15 mm and "εr = 3 ± 0.3".\[6\]\[8\]
- "The time dependence is exp(iωt)."\[6\] If your code uses e^(−iωt), conjugate the data. This conversion is my inference.
- The 2001 paper also warns that the incident field in the target area "has to be estimated, or optimized along the reconstruction process".\[6\]
- Download: Fresnel's page (https://www.fresnel.fr/3Ddatabase/) says the data "are free for scientific use" and points to the IOP article pages, for example http://iopscience.iop.org/article/10.1088/0266-5611/17/6/301/. \[9\]\[10\] I could not confirm whether those IOP supplementary files are downloadable without a login. Check by hand.

**Calibration, read from secondary sources.**
- Geffrin et al. 2005 (snippet via https://www.researchgate.net/publication/231069726): "one single complex coefficient which multiplies the computed fields", taken from "the ratio of the measured incident field and the simulated one at the receiver located at the opposite of the source".\[11\]
- Mojabi & LoVetri ("Comparison of TE and TM Inversions in the Framework of the Gauss-Newton Method", IEEE Trans. Antennas Propag. 58(4), 2010) use "a single calibration factor per transmitter": "the ratio of the simulated incident field to the measured incident field for the receiver point opposite to the transmitter (this factor is used for all receiver points)". They model the sources as an "electric line source for TM illumination and magnetic line source for TE illumination".

**2005 opus.** FoamDielExt, FoamDielInt, FoamTwinDiel and FoamMetExt have source/receiver distance 1.67 m, 2–10 GHz, both TE and TM, and 241 receivers at 1° steps.\[11\]\[12\] I could not confirm the 2005 column layout. These are inhomogeneous targets (foam with a berylon insert), so FoamDielInt would need a nested two-interface boundary integral equation (BIE). I would leave them for later.

**Prior shape-based work on these data, read from abstracts.** Litman 2005, "Reconstruction by level-sets of n-ary scattering obstacles" (Inverse Problems 21 S131), used level sets on Fresnel data.\[13\] Carpio et al. (https://arxiv.org/html/2501.15327v1) also list "level-set based shape identification methods" (Ramananjaona et al. 2001) among the methods already tested on the 2001 set, alongside Bayesian, modified-gradient, contrast-source inversion and distorted-wave Born methods. Carpio, Pena & Rapún say their topological-derivative results "are comparable to the best results obtained in previous studies by other methods, while the computational complexity is very low", but they give no numerical accuracy figure. I did not obtain accuracy numbers from these works, so treat your own boundary error on the 15 mm cylinder as a new number until you find theirs.

**Work.** You download the files once (about 15 min) and commit them under `data/fresnel/`, because the agent phase is offline. After that, 2 Codex tasks: a loader plus calibration plus forward-fit check, then the inversion. It can be checked against known ground truth: centre at (−30 mm, 0) for dielTM_dec8f according to a secondary source (https://www.mdpi.com/2227-7390/12/20/3253), with r = 15 mm.\[8\]

**Reward.** Real-data validation of BIE shape inversion, which most neural-SDF scattering papers do not have. The abstract of the 2022 implicit neural representation paper (https://arxiv.org/abs/2206.02027) reports "high-quality reconstruction results even in noise-corrupted setups" and does not mention measured data. If twodielTM_8f works, it also tests your topology controller on real two-object data. Strong figure candidate.

**Risk.** Medium. Calibration and source modelling can dominate the error, and frequencies above about 6 GHz are where model mismatch usually shows. That last point is my inference. **GPU:** no. This is 49 × 36 data per frequency at small kR.

**First Codex prompt.**
> Add `solvers/io/fresnel2001.py` to parse `data/fresnel/dielTM_dec8f.exp` (10-line header, 7 columns: tx idx, rx idx, f GHz, Re/Im total, Re/Im incident; exp(iωt) convention — convert to the repo's convention). Build tx positions at 0.72 m (0°..350°, 10°) and rx at 0.76 m (60°..300° relative, 5°). Model the source as a 2-D TM line source; compute one complex calibration factor per (frequency, tx) from the opposite-side receiver's measured incident field. Forward-check: simulate a 15 mm, εr=3 circle at (−30 mm, 0) with the Kress solver and report relative misfit per frequency vs measured scattered field (total − incident). Then run the Cartesian Fourier inverse from a 25 mm circle at the origin with frequency continuation 1→8 GHz; report centre error, radius error, IoU, misfit per stage. CPU only. Write `results/fresnel/README.md` with plots.

### 3. TE polarisation solver and its shape derivative: the 2-D step towards Maxwell — medium distance

**What it is.**
- *Background (standard theory).* In TE polarisation the field quantity is H_z, the magnetic field along the axis. The transmission condition changes so that the normal derivative is weighted by 1/ε.
- *Inferred.* This weighting is the 2-D echo of the tangential-field conditions in Maxwell. Concretely: u is continuous across the boundary, and (1/ε)·∂u/∂n is continuous too. Here u = H_z and ∂/∂n is the normal derivative.
- The input is the same geometry. The output is a TE forward solver plus a TE shape derivative, checked against finite differences.

**Why.**
- *Read from the abstract.* Costabel & Le Louër Part II (https://arxiv.org/pdf/1105.2479) give shape derivatives of the Maxwell BIE operators for a dielectric obstacle.\[14\]
- *Inferred, and needing your reading.* The "derivative is another scattering problem" property can be tested in 2-D TE as one extra solve with the same operator and boundary jump data. You would be exercising the hybrid adjoint plan on the polarisation that actually differs from acoustics.
- It also unlocks the Fresnel TE data (rectTE_8f in 2001; all 2005 targets).\[6\]

**Work.** 2 Codex tasks. Your time: 2–3 h deriving the TE jump data, or checking Codex's derivation against Hettlich 1995 or Costabel & Le Louër. It is easy to verify with finite differences and a Mie-type series for the circle.

**Reward.** A validated TE solver and derivative. This is the first concrete piece of the Maxwell path, and a TE row can be added to the atlas, since TE and TM should have different cutoffs (inferred). **Risk:** low to medium; the derivative formula is the error-prone part. **GPU:** no.

**First Codex prompt.**
> Extend the Müller/Kress transmission solver to TE (u=H_z, transmission conditions [u]=0, [(1/ε)∂u/∂n]=0). Validate against the separable series solution for a circle (εr=4, kR∈{1,5,15}); report max relative error vs number of nodes. Then implement the TE shape derivative as a second solve with boundary jump data driven by normal perturbation h·n (derive and document the jump terms in `docs/reference/te_shape_derivative.md`), and validate 10 random harmonic directions against central FD. Add pytests.

### 4. Lossy ground: complex wavenumber — close to current code

**What it is.**
- *Background (standard theory).* Conductivity σ makes the permittivity complex: εc = ε − iσ/ω, where ω is angular frequency. The sign depends on your time convention. The wavenumber then becomes complex and the Hankel kernels decay with distance.
- The input is the atlas setup plus σ for the background and/or the target. The output is how many shape harmonics stay recoverable as σ grows.

**Why.**
- *Inferred.* Real soils are lossy, and loss should shrink the stable region. Quantifying "harmonics lost per S/m at frequency f" is the GPR-specific version of item 1 and does not need a half-space.
- *Read from source.* Lossy-half-space GPR inversion in the literature is mostly linearised or volumetric, for example Meincke, "Linear GPR inversion for lossy soil and a planar air-soil interface" (https://www.researchgate.net/publication/3202784_Linear_GPR_inversion_for_lossy_soil_and_a_planar_air-soil_interface). \[15\]\[16\]

**Work.** 1 Codex task if the solver accepts complex k. scipy's Hankel functions take complex arguments; check that the Kress logarithmic splitting is still valid for complex k. That last check is my inference and needs verifying. **Reward:** an extra atlas axis and a GPR-relevant figure. **Risk:** low. **GPU:** no.

**First Codex prompt.**
> Allow complex exterior and interior wavenumbers in the Kress transmission solver. Validate against the circle series solution with complex k. Rerun `run_jacobian_spectrum.py` for background σ ∈ {0, 1, 10, 50} mS/m, εr_bg=6, at 100 MHz–1 GHz with a 0.2 m target, and plot stable-mode count vs σ and f.

### 5. Sampling or topological-derivative initialiser for the topology controller — close to current code

**What it is.**
- The input is the multi-static data matrix at one or more frequencies. The output is a cheap image of where the scatterers are, which seeds your birth/split decisions or the initial circles.
- Candidate methods: the linear sampling method (LSM), the factorization method, or a closed-form topological derivative.

**Why.**
- *Read from the README.* Your benchmark fails on distant/enclosing starts.\[1\]
- *Read from the abstract.* Carpio et al. (https://arxiv.org/html/2501.15327v1) report that topological fields "admit easy to evaluate closed-form expressions".\[7\]
- *Read from the paper.* Askham, Borges, Hoskins & Rachh (https://arxiv.org/abs/2308.00559) found the problem "is sensitive to the choice of iterative solver used at each frequency and the initial guess at the lowest frequency".\[17\]

**Work.** 1–2 Codex tasks. Verified by rerunning the frozen 12-scene benchmark. **Reward:** a probable direct gain in benchmark passes; it is useful but not novel. **Risk:** low to medium. **GPU:** no.

**First Codex prompt.**
> Implement LSM (Tikhonov-regularised, Morozov parameter) and a topological-derivative indicator from the existing multi-static synthetic data. Add `--init {current,lsm,topo}` to `run_topology_scene_benchmark.py` that thresholds the indicator into initial circles. Run all 12 scenes per arm and report pass counts and solves used, including failures.

### 6. Your sc strategies against recursive linearisation and stochastic continuation in frequency — close to current code

**What it is.** The input is your benchmark scenes. Recursive linearisation (Chen; Borges, Gillman & Greengard 2017, https://doi.org/10.1137/16M1093562) \[18\] inverts at low frequency and then uses each answer as the start for the next frequency, with a band-limited shape. Stochastic continuation in frequency (SCIF, Askham et al.) runs several random frequency trajectories.\[19\] The output is a head-to-head comparison with your sc strategies.

**Why.**
- *Read from source.* Borges & Greengard note that "the same stabilizing effect can be achieved by using a suitably band-limited model for the unknown" (snippet, https://www.researchgate.net/publication/265052531). \[20\] That is essentially your K–M rule.
- *Inferred.* So you need to show what sc adds beyond it.
- *Read from source.* Borges, Rachh & Greengard (https://arxiv.org/abs/2210.11607) compare boundary-only against volumetric inversion for penetrable obstacles.\[21\] That is close to your SDF-versus-continuous-field decision.

**Work.** 1–2 Codex tasks. **Reward:** positions sc against the standard baseline, which you will need for any paper. **Risk:** low. **GPU:** optional.

**First Codex prompt.**
> Add a `recursive_linearization` arm: frequencies ascending, at each frequency M=ceil(c·kR) harmonics with c∈{0.5,1,1.5}, a few damped Gauss-Newton steps, warm start. Add a `scif` arm: 8 random monotone-with-backtracking frequency paths, keep the lowest-misfit result. Run both against the existing sc arms on the 12 scenes; report passes, BIE solves, and wall time.

### 7. Time-domain GPR traces from multi-frequency BIE, compared with gprMax — medium distance

**What it is.** The input is your frequency-domain responses on a dense grid, multiplied by a Ricker wavelet spectrum and inverse-Fourier-transformed. The output is A-scans and B-scans to overlay on gprMax (an FDTD, finite-difference time-domain, simulator) runs of the same 2-D TMz scene.

**Why.**
- *Inferred.* This connects your BIE to the GPR community's reference tool and to your earlier BIE-versus-FDTD slides with a quantitative match.
- *Read from the gprMax docs* (https://docs.gprmax.com/en/latest/comparisons_analytical.html): gprMax has analytical-comparison documentation.\[22\]

**Work.** 2 Codex tasks. gprMax must be installed in the setup script; it compiles Cython, which is a risk. CPU 2-D runs are small. **Reward:** a validation figure; little novelty. **Risk:** medium, mostly from install and source-normalisation details. **GPU:** no for 2-D.

**First Codex prompt.**
> In the setup script install gprMax. Create a 2-D TMz gprMax model: free space, εr=4 circular cylinder r=0.1 m, Hertzian/line source with 1 GHz Ricker, 20 receivers. Compute the same configuration with the BIE at 512 frequencies 0–3 GHz, multiply by the Ricker spectrum, and inverse-FFT. Overlay traces, report normalised cross-correlation and peak-time error, and document the source-normalisation used.

### 8. Half-space Green's function: air–soil interface — far from current code

**What it is.** The input is an interface at z = 0 with soil εr and σ, and an object in the soil. The output is a forward solver whose kernel or formulation accounts for the interface. There are two routes. One is the windowed Green function method (WGF), from Bruno, Lyon, Pérez-Arancibia & Turc, SIAM J. Appl. Math. 76(5):1871–1898 (2016). It keeps the free-space kernel and truncates the infinite interface smoothly (https://arxiv.org/pdf/1703.01034). \[23\]\[24\] The other is a Sommerfeld-integral layered Green's function.

**Why.** Without this, nothing is real GPR geometry; the README lists layered ground as out of scope.\[1\] **Work:** 3–5 Codex tasks, plus your own reading of the WGF paper (about 3 h). One day gets a validated forward solver at most, not an inversion. **Reward:** a necessary building block, low novelty on its own. **Risk:** medium to high, from interface truncation and kernel accuracy. **GPU:** no for validation.

**First Codex prompt.**
> Implement a 2-D TM WGF forward solver: flat interface between air and soil (complex εr) truncated with the smooth window from Bruno et al. 2016, plus one buried dielectric circle using the existing Kress discretisation. Validate the no-object case against the Fresnel plane-wave reflection coefficient and window-size convergence; validate a small buried circle against a reference with a much larger window. Document convergence vs window size.

### 9. Minimal 3-D scalar IBIM on a sphere — far from current code

**What it is.** The input is an analytic SDF of a sphere on a narrow-band grid. The output is the scalar Helmholtz transmission solution computed with the implicit boundary integral method (IBIM), compared with the Mie series.
- *Read from source.* Kublik, Tanushev & Tsai describe how IBIM rewrites boundary integrals as integrals over "a thin tubular neighborhood around the boundary" (https://www.oden.utexas.edu/media/reports/2012/1217.pdf). \[25\]
- *Read from source.* Chen & Tsai treat the exterior Helmholtz case, as cited in https://arxiv.org/html/1709.08070. \[26\]

**Why.** It measures the cost and accuracy you would face before attempting Maxwell IBIM, which is your stated gap. *Inferred:* scalar exterior 3-D IBIM is not new; novelty begins with transmission + neural SDF + shape derivative. **Work:** 2–3 Codex tasks. **Reward:** understanding plus a feasibility table (grid spacing, band width, error, memory). **Risk:** medium; hypersingular handling and dense matrices limit size on CPU. **GPU:** helps, but not needed at small sizes.

### 10. Algoim (Saye) quadrature against Method B for MLP boundaries — far from current code

**What it is.** The input is your MLP SDF. The output is a comparison of boundary quadrature: Saye's high-order method, which recasts the geometry "as the graph of an implicitly defined, multi-valued height function" (https://arxiv.org/pdf/2105.08857), against your Method B extraction.\[27\] The comparison covers accuracy and differentiability with respect to the weights.

**Why.** It is open thread 1 in your notes. **Work:** 2–3 Codex tasks. Algoim is a header-only C++ library (https://algoim.github.io/), so it needs a pybind wrapper; a Julia wrapper exists but not, as far as I found, a maintained Python one.\[28\]\[29\] **Reward:** clarifies the quadrature choice. **Risk:** high for one day, because of the build and because weight-gradients through root-finding need implicit differentiation. **GPU:** no.

## Suggested allocation of the reset

| Slot | Tasks (parallel where independent) | Your time |
|---|---|---|
| Morning | #1 atlas (2 tasks); #2 loader + forward check (after you commit the Fresnel files); #4 complex k (1 task) | 1.5 h spec, data download |
| Midday | #2 inversion; #3 TE solver; #5 initialiser | 1 h review |
| Afternoon | #3 TE derivative; #6 continuation comparison; #1 rerun with TE and lossy axes | 2 h reading results |
| If budget remains | #7 gprMax, or start #8 WGF | — |

**Inferred:** #1, #2 and #3 together produce a coherent story: what is resolvable, does it hold on real data, and does it extend to the Maxwell-like polarisation. #8–#10 are better started after you have read the WGF and IBIM papers, because their specifications depend on choices only you can make.

## Caveats
- I did not see the "ma", "sc" or "node-free" code. Prompts that touch sc assume an existing arm interface in `run_topology_scene_benchmark.py`, which may need renaming.
- Kow–Salo–Zou is proved for linear model problems, not obstacle scattering. Its use as a cutoff prediction for your Jacobian is a hypothesis to test, not a theorem.
- Fresnel download access through IOP was not confirmed; the 2005 file layout and the Litman 2005 accuracy figures were not obtained.
- My literature scan of 2023–2026 neural-SDF + BIE work was limited. The closest prior work I found is the IBIM + SIREN autodiff obstacle paper (https://arxiv.org/abs/2206.02027), \[30\] which is acoustic per its abstract. The other is Chen, Jin & Liu, "Solving Inverse Obstacle Scattering Problem with Latent Surface Representations" (https://arxiv.org/pdf/2311.07187, version of April 2024), a 3-D far-field shape-derivative method that includes "backscattered and phaseless data" and is not a 2-D penetrable-transmission paper. Do a dedicated search before you claim novelty.

## Sources

1. [GitHub - ShiyuanDeng/Neural-BEM](https://github.com/ShiyuanDeng/Neural-BEM)
2. [Codex Cloud (Legacy): internet access](https://developers.openai.com/codex/cloud/internet-access)
3. [Codex Cloud (Legacy)](https://developers.openai.com/codex/cloud/environments)
4. [\[bug\] workspace-write sandbox blocks GPU access (no /dev/nvidia\* in bwrap namespace) · Issue #19676 · openai/codex](https://github.com/openai/codex/issues/19676)
5. <https://arxiv.org/html/2404.18482>
6. <https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf>
7. [Processing the 2D and 3D Fresnel experimental databases via topological derivative methods](https://arxiv.org/html/2501.15327v1)
8. [Application of Kirchhoff Migration from Two-Dimensional Fresnel Dataset by Converting Unavailable Data into a Constant](https://www.mdpi.com/2227-7390/12/20/3253)
9. [(PDF) Continuing with the Fresnel database: Experimental setup and improvements in 3D scattering measurements](https://www.researchgate.net/publication/230990377_Continuing_with_the_Fresnel_database_Experimental_setup_and_improvements_in_3D_scattering_measurements)
10. <https://www.fresnel.fr/3Ddatabase/>
11. [(PDF) Free space experimental scattering database continuation: Experimental set-up and measurement precision](https://www.researchgate.net/publication/231069726_Free_space_experimental_scattering_database_continuation_Experimental_set-up_and_measurement_precision)
12. [Imaging Interiors: An Implicit Solution to Electromagnetic Inverse Scattering Problems](https://arxiv.org/pdf/2407.09352)
13. [Reconstruction by level-sets of n-ary scattering obstacles - Ecole Centrale de Marseille](https://hal-emse.ccsd.cnrs.fr/ECM/hal-00015481v1)
14. [\[PDF\] Shape Derivatives of Boundary Integral Operators in Electromagnetic Scattering. Part II: Application to Scattering by a Homogeneous Dielectric Obstacle](https://www.semanticscholar.org/paper/Shape-Derivatives-of-Boundary-Integral-Operators-in-Costabel-Lou%C3%ABr/4f61d810122bd207c56dd0867deb97546290b562)
15. [Observation Modeling of Reference--Background Residuals in Single-Snapshot FDA-MIMO-GPR](https://arxiv.org/pdf/2605.17728)
16. [Linear GPR inversion for lossy soil and a planar air-soil interface](https://www.researchgate.net/publication/3202784_Linear_GPR_inversion_for_lossy_soil_and_a_planar_air-soil_interface)
17. [\[2308.00559\] Random walks in frequency and the reconstruction of obstacles with cavities from multi-frequency data](https://arxiv.org/abs/2308.00559)
18. [High resolution inverse scattering in two dimensions using recursive linearization - NYU Scholars](https://nyuscholars.nyu.edu/en/publications/high-resolution-inverse-scattering-in-two-dimensions-using-recurs)
19. [Random walks in frequency and the reconstruction of](https://arxiv.org/pdf/2308.00559)
20. [(PDF) Inverse Obstacle Scattering in Two Dimensions with Multiple Frequency Data and Multiple Angles of Incidence](https://www.researchgate.net/publication/265052531_Inverse_Obstacle_Scattering_in_Two_Dimensions_with_Multiple_Frequency_Data_and_Multiple_Angles_of_Incidence)
21. [\[2210.11607\] On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary](https://arxiv.org/abs/2210.11607)
22. [Analytical comparisons — gprMax documentation](https://docs.gprmax.com/en/latest/comparisons_analytical.html)
23. [Perfectly Matched Layer Boundary Integral Equation Method for Wave Scattering in a Layered Medium](https://dx.doi.org/10.1137/17M1112510)
24. [A Windowed Green Function method for elastic scattering problems on a half-space](https://www.researchgate.net/publication/342539385_A_Windowed_Green_Function_method_for_elastic_scattering_problems_on_a_half-space)
25. [ICES REPORT 12-17 April 2012 An implicit interface boundary integral method for](https://www.oden.utexas.edu/media/reports/2012/1217.pdf)
26. [An implicit boundary integral method for computing electric potential of macromolecules in solvent](https://arxiv.org/html/1709.08070)
27. [High-Order Quadrature on Multi-Component Domains Implicitly Defined by Multivariate Polynomials](https://arxiv.org/pdf/2105.08857)
28. [GitHub - ericneiva/Algoim.jl: A Julia wrapper for algoim's algorithms for implicitly defined geometry, level set methods, and Voronoi implicit interface methods · GitHub](https://github.com/ericneiva/Algoim.jl)
29. [Robert Saye](https://math.lbl.gov/~saye/code.html)
30. <https://arxiv.org/abs/2206.02027>
