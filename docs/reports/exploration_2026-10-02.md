# Ranked exploration, 2 October 2026

The [new research document](../iterations/cleaned_interfaces/compass_artifact_wf-82366c2c-4c07-5e25-8f50-db8aa83ba80c_text_markdown.md)
was pulled at commit `15611d94` on the already active
`feature/shape-frequency-continuation` branch. No branch or worktree was
created. The first campaign produced experiments for all ten priorities, using
CPU runs and existing solver/geometry implementations where they applied.
That coverage did **not** complete every requested comparison or resolve every
research question. The new numerical interfaces are opt-in.

## Closure and value for the cleaned interface

The user closed the broad campaign because the plan came from an outdated
branch, allowing demonstrated improvements for the cleaned interface to be
retained. New campaign scheduling stopped. Unfinished trajectories are preserved
as **scope-change stops**, not numerical failures or completed comparisons.
No branch was created, switched, or merged.

The initial handoff overstated completion: the original M=5 SC arm was not the
maintained cumulative policy. The follow-up executes the actual policy through
explicit coupled-geometry and frequency-catalog adapters, but its interrupted
campaign does not establish a replacement strategy. The
[maintained-policy closure](../../results/exploratory_continuation/maintained_policy/README.md)
records finished cases, partial checkpoints, and the information differences.

The useful results retained are:

- **Cleaned-interface numerical audit:** stream independent frequencies to
  release dense systems promptly, and reuse an unchanged failed initial audit
  when no fitting occurred. Direct equivalence tests and an isolated memory
  comparison qualify this change. It changes neither the policy nor its
  numerical acceptance tolerances. The five-frequency N512/1024 check reduces
  peak process memory by 74.4%, with bitwise-identical outputs and work counts.
  Commit `8e619088` isolates this fix from the experimental adapters.
- **Measured illumination:** incident-only multipole calibration, withheld-angle
  checks, and a fixed-illumination shape derivative support a controlled 1–4 GHz
  Fresnel comparison. At the final geometry, the 4 GHz residual improves from
  24.77% to 16.49%. These are reusable experimental source primitives; they are
  not installed as cleaned-interface defaults. See the
  [source qualification](../../results/fresnel/source_qualification/README.md).
- **Initializer evidence:** all 24 additional LSM/full-matrix TD controller jobs
  completed. Each initializer passes 5/12, matching the original-start count;
  neither result supports a new initialization default. The
  [full comparison](../../results/initialization-full-matrix-resolved-20261002/README.md)
  explicitly accounts for the additional 552 complex samples per scene.
- **Stopping-floor evidence:** continued resolved decreases below historical
  floors show that the old stopping point was premature. The run was closed
  while descending, so eventual shape recovery and a final numerical floor
  remain unestablished. The
  [continuation audit](../../results/stopping-floor-20261002/README.md)
  gives residual/gradient error bounds and preserved checkpoints. No optimizer
  default is changed from this partial experiment.

The [follow-up validation bundle](../../results/exploration-followup-20261002/README.md)
records the exact tests, closure status, source hashes, and artifact inventory.
The first campaign's provenance remains unchanged and refers to its earlier
snapshot, not these follow-up edits.

## Initial campaign results and scope

| Priority | Executed work | Evidence and limits |
|---|---|---|
| 1. Shape sensitivity | 108 combinations, 216 spectra; normal harmonics through 40; extra M80 saturation check; independent Mie, analytic derivative and FD checks | [Atlas](../../results/atlas/README.md). Rank grows with frequency but depends on shape, contrast and acquisition. TOP-009's finite error is not mostly near-null and is far outside its local linear model. |
| 2. Fresnel measurements | Both complete 2001 dielectric data files imported, calibrated and inverted through 1–8 GHz | [Measured data](../../results/fresnel/README.md). Single-cylinder radius 15.54 mm; substantial antenna mismatch. Coordinate assumptions in the supplied prompt were corrected and explicitly audited. Twin result uses fixed two-circle topology. |
| 3. TE solver/derivative | Weighted transmission, derived PDE jump derivative, circle series and 20 random circle/ellipse FD directions | [TE derivation](../reference/te_shape_derivative.md), [validation](../../results/polarization/README.md). Circle agreement≤5.13e-14; FD≤1.71e-7. One smooth interface. |
| 4. Passive loss | Correct conductivity sign for exp(−iωt), lossy circle/derivative checks, 80 TE/TM atlas cases | [Lossy atlas](../../results/polarization/README.md). At 1 GHz the fixed-floor count falls TM 59→49 and TE 61→49 with 50 mS/m background conductivity. Relative normalization hides much of the loss. |
| 5. Initializers | All 12 frozen scenes; existing topological derivative; separate eligible full-matrix LSM control; 24 matched runs with original numerical budgets | [Initializer comparison](../../results/exploratory_continuation/README.md). Original and topological starts both pass 5/12 under policy H; each arm has one 600-second timeout. Frozen data contain 24 paired values, not a 24×24 matrix, so an LSM frozen-data arm is unavailable. |
| 6. Frequency paths | All 12 scenes, 144 primary runs: SC fixed-band control, three RLA factors, eight SCIF seeds; 16 longer retries | [Continuation](../../results/exploratory_continuation/README.md). Explicit added training frequencies; original holdouts remain held out. RLA c=1.5 passes 4/12; best-of-eight SCIF 3/12 at both work caps; fixed-band control 0/12. This is not an evaluation of the complete cleaned SC/MA policy. |
| 7. Time domain | 512 BIE frequencies, 20 receivers, three independently run gprMax grids | [Transient comparison](../../results/time_domain/README.md). Finest relative scattered error 0.506%, minimum zero-lag correlation 0.999978, maximum peak discrepancy 5.20 ps. Matched temporal windows and absolute source normalization; no fitted calibration. |
| 8. Half-space | Existing Sommerfeld representation extended to a buried-interface Müller/Kress solver; Fresnel, spectral-quadrature and independent volume checks | [Half-space](../../results/halfspace/README.md). Uses the document's alternative layered-Green-function route, not WGF; no window-size convergence claim. Single buried object, forward only. |
| 9. 3-D scalar IBIM | Sphere SDF narrow-band quadrature, scalar transmission, independent 3-D Mie, grid/band/memory study | [Sphere feasibility](../../results/ibim3d/README.md). Finite-grid errors about 1e-4–5e-4; sphere-specific singular correction and almost 1 GB matrix at largest run. No arbitrary-surface or Maxwell claim. |
| 10. Algoim | Pinned upstream C++ quadrature directly on an 8,577-parameter saved SIREN; Method B and continuum weight-gradient comparisons | [Quadrature](../../results/algoim/README.md). Method B perimeter difference falls to 3.83e-10 at band 64; selected weight gradients agree with recomputed-quadrature FD. This does not differentiate the adaptive discrete quadrature algorithm. |

## Findings that change the original proposal

The strongest new result is a correction to the proposed explanation of
TOP-009. With a smooth physical-angle correspondence, only 24.9% of the M40
error energy at the reconstruction lies below 0.001 σ₁ at the training frequency.
Its projected local linearization misses the finite field change by a factor
of 670. The untruncated path tangent differs from the M40 tangent by only
0.0254%, confirming that basis truncation does not explain this remainder.
A smooth path toward the truth raises residual 8.82e-5→1.52e-2 at its
midpoint, then returns to the truth. This is evidence of nonlinear separation
along one path, not proof of a local minimum or nonuniqueness. The previous
TOP-010 premature-stopping evidence remains valid.

The original literature summary also conflates two scaling laws.
[Kow, Salo and Zou](https://arxiv.org/html/2404.18482) distinguish a boundary
Herglotz-density problem from a linearized volume-potential problem; neither
proves a shape-Jacobian cutoff for this dielectric transmission solver.
The atlas supports increasing measured rank, with no universal exterior- or
interior-wavenumber rule established by the tested geometries.

Other concrete contract corrections were necessary. The frozen topology suite
has only one training frequency, making a nontrivial frequency-path comparison
impossible without declaring extra observations. Its sparse paired data also
cannot supply a full matrix for LSM. The [experiment contract](../../experiments/exploratory_continuation/README.md)
derives both restrictions and records the extensions. In Fresnel data, primary
source indexing and the actual file rows replace the proposal's simplified
receiver layout and unverified nominal coordinate orientation.

## Boundaries supported by evidence

These are research outputs, with the following reasons for retaining opt-in
status rather than changing production defaults:

- The local SVD does not explain the large finite TOP-009 deformation. The
  finite-path audit shows a barrier on one path but cannot certify all paths
  or justify a new optimizer policy.
- Fresnel incident measurements differ from the calibrated isotropic source
  over the full receiver aperture by 0.92–2.41 relative error. Higher spatial
  resolution changes fitted predictions by only about 1e-14. Antenna modeling,
  reference coordinates and uncertainty require further physical qualification.
- Sampling and continuation results retain failed scenes, incomplete paths,
  and numerical/work stops. The improved initial overlap does not increase
  full-budget passes, and longer SCIF paths do not improve its pass count.
  A frozen rejected proposal meets the numerical gate at N512/1024, but
  fixed-count smooth updates cannot merge its three components into the
  one-component target. These results do not establish superiority of a
  replacement for the complete cleaned SC/MA policy.
- [Bruno and Pérez-Arancibia's WGF construction](https://arxiv.org/html/1703.01034v1)
  has a specific infinite-interface correction. The implemented Sommerfeld BIE
  takes the other route explicitly allowed in the proposal and requires
  spectral-quadrature convergence instead; it must not be renamed WGF.
- The 3-D sphere correction uses exact spherical row integrals. The coarea
  foundation in [Kublik, Tanushev and Tsai](https://www.oden.utexas.edu/media/reports/2012/1217.pdf)
  does not supply a ready-made arbitrary-surface Helmholtz singular quadrature
  or Maxwell derivative. The measured dense cost and nonmonotone refinement
  further limit generalization.
- Algoim's continuum shape derivative and the derivative of its adaptive
  numerical node/weight construction are different objects. The former is
  checked here; the latter is not asserted.

Each linked report includes reproduction commands, raw measurements, primary
literature or a derivation, and the limits of its comparison. Reviewed figures
and numerical arrays are retained as named exceptions to the normal generated
artifact exclusions. No paper PDF or third-party source tree is vendored.

## Initial campaign validation and provenance

The combined CPU test run passes **60 tests** across all new experiment
modules and the existing Kress API/forward regression checks. The 14 warnings
are matplotlib/pyparsing deprecations. The [validation bundle](../../results/exploration-20261002/README.md)
records the exact command, test log, reviewed source hashes and artifact
inventory. Independent reviews checked the TE and half-space signs, atlas
normal metric and real SVD, sphere coarea correction, acquisition contracts,
and continuation accounting. Earlier failed checks and superseded processing
results are preserved and labeled in the individual reports.
