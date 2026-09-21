# Proposed next tests: decide what compression is for

2026-09-21. **PROPOSED — NOT APPROVED FOR EXECUTION.**
This is a concrete next-step recommendation following the requested review,
not an agreed `03_plan.md`. No numerical experiment ran during that review.

The first question should be whether the negative derivative evidence is
binding for the physical inverse calculation. Do not start with a sparse
assembler, a general ROM framework, or a proof covering every admissible
geometry. A useful theorem can be a separate research product, but a broad
proof-first programme is a large commitment before identifying which bound
or approximation actually matters.

## MC-001 — compress traces while preserving physical inverse sensitivities

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION.
- **Execution status:** NOT STARTED.
- **Question:** at a fixed absolute representation budget, can compressed
  forward/receiver-adjoint traces give accurate physical data derivatives where
  the derivative of the masked discrete system fails?
- **Falsifiable hypothesis:** the LAU-001-R1 circle separation extends to at
  least two noncircular geometries and small off-anchor motion, with at least
  25% fewer total represented forward slots than the smallest independently
  qualified dense modal reference. This is an initial structure/quality gate,
  not a speed claim.
- **Baseline:** freeze the existing checkout revision at execution (review
  HEAD `db291c3ca6e5297cea0334f2808b6928f2b86c40`) and all imported file hashes.
  Use refined Kress with reciprocal/operator reference derivatives and an
  uncompressed hybrid Galerkin control. Cite LAU-001-R1 and LAU-002 for the
  historical counterexample; do not compare different tolerance regimes as
  matched results. Record production compiler/reciprocal settings for later
  economic comparisons.
- **Intervention:** keep identical compressed primal and receiver solutions,
  geometry and mask; compare (a) differentiating the frozen-mask discrete
  system and (b) evaluating the continuous reciprocal/Hadamard data derivative
  from those traces. This isolates the derivative target. Do not add a new
  basis or optimizer in this experiment.
- **Controls:** fixed physical exterior/interior wavenumbers during geometry
  changes; identical source/receiver coordinates, material contrast, normalized
  physical directions and base solves. Qualify trace cutoff, coefficient grid
  and finite-difference step independently. Mask must stay fixed across each
  differentiation check. Inspect every physical direction separately.
- **Scope and interfaces:** a new isolated experiment driver and audit only;
  read-only imports from `solvers/`, `modal_muller_research/`,
  `laurent_compression/`, `laurent_literature/` and the hybrid assembler.
  Do not repair the September 18 archived sources in place. Recover their
  provenance if using their exact historical fixtures; otherwise freeze a
  fresh fixture and label it new.
- **Fixture budget:** circle sanity control plus ellipse, asymmetric star and
  crescent; two physical frequencies chosen at each anchor to give exterior
  kD=2 and 10. Six normalized physical normal directions (sine/cosine at
  orders 1, 3, 6) and one held-out mixed direction. Two held-out 0.5%-diameter
  normal offsets per noncircle. A translated/rotated equivalent configuration
  checks coordinate consistency. If physical-normal directions are represented
  approximately in Laurent coordinates, record and qualify that projection.
- **Compression budget:** one predeclared derivative-aware reference pattern
  from existing machinery, at absolute budgets 25%, 50%, 75% of the smaller
  qualified full representation. Count protected identity/log terms and any
  auxiliary stored coefficients. Full dense construction is allowed in this
  diagnostic but must be charged and prevents an efficiency claim. Do not
  enlarge the reference dimension to improve a retained fraction.
- **Quality metrics:** receiver error, individually scaled Dirichlet/flux trace
  errors, independent lifted residual, every directional data derivative,
  objective directional derivatives on declared residual vectors, and
  `Jv`/`J* w` consistency where available. Report errors of both derivative
  arms against the physical reference and the finite-difference derivative of
  the actual approximate forward separately. Use absolute floors for tiny
  sensitivities and list them. Include a weak-sensitivity direction; aggregate
  Frobenius error alone is insufficient.
- **Initial gates:** independently refined reference data error ≤1e-8 and
  derivative error ≤1e-6; candidate data error ≤1e-6 and worst normalized
  non-negligible directional derivative error ≤1e-3. These screening gates
  precede any noise-aware relaxation. Reference uncertainty should be below
  one tenth of the candidate gate. A lifted residual above 1e-6 is reported
  explicitly; such a model can qualify only as output-specific, never as a
  replacement for the old full-state qualification.
- **Decision-level check:** for models passing the physical gates, compare one
  regularized local Gauss–Newton direction and its predicted data change with
  the full reference, using the same damping and starting state. Evaluate
  actual trial reduction with the full forward. A good scalar gradient alone
  is insufficient for the repository's least-squares method. These are local
  checks, not a completed nonlinear inverse campaign.
- **Compute budget and stops:** at most 30 minutes, 1,000 full frequency-system
  assemblies, 4,000 factorizations and 8 GiB RSS, one CPU worker with fixed
  single-thread BLAS. Stop the affected fixture if independent controls fail;
  do not spend the rest of the budget repairing the physics or increasing
  scope. Stop for an overall numerical obstruction after two such fixture
  failures. Ceilings are not targets.
- **Artifacts:** a fresh `results/validation/modal_compression/MC-001-<stamp>/`
  containing exact config/commands, sources and input hashes, all passing and
  failing arms, physical direction definitions, errors, absolute counts,
  work/timing/RSS and a read-back audit. Never overwrite prior bundles.
- **Decision criteria:** if compact physical sensitivities survive noncircular
  and offset tests, pursue the cheapest economic realization and a subsequent
  controlled inverse pilot. If success is circle-only or requires nearly full
  representation, reject this mechanism as a practical route for these
  fixtures. If derivatives improve but trial directions fail, investigate
  consistency/weak directions before any speed work. No criterion promotes a
  production default.
- **Owner / reviewer:** unassigned / unassigned for execution.

This experiment tests the physical-derivative route, not the general modal
compression hypothesis. A negative should close that route at its stated
scope; it should not be relabeled proof of global incompressibility.

## Conditional directions after the first decision

### 1. Blockwise and coordinate-aware structure

If MC-001 identifies usable compressed states but the count is borderline,
test *one* further mechanism at a time:

- Allocate different patterns/tolerances to the four blocks in a declared
  physical/Sobolev scaling. Compare centered band, adapted hyperbolic mask and
  a block-specific envelope at the **same absolute total count**. Include
  identity/protected terms and factor fill. LAU-002 already tested principal-
  log extraction with a common mask and found no smaller winner; another test
  must isolate a different allocation, not repeat that experiment under a new
  name. Derive the constants needed for that allocation as part of the work.
- Test the same physical circle/ellipse under a controlled nonuniform
  reparametrization and an arclength-like solver coordinate. Keep shape design
  variables fixed and transport traces, flux weights and derivatives correctly.
  Include the interpolation cost and geometry approximation. This tests
  whether the chosen coordinates are causing avoidable coupling. It must not
  change the physical shape or silently erase design directions.

A full matrix may be built for a bounded oracle screen, but that is only an
upper estimate of how much structure can be exploited. Success must then earn
a construction that avoids dense work. A matrix-vector action through the
nodal solver is another valid competitor; “modal” need not mean building a
modal matrix.

### 2. Noise-aware inverse quality, with safeguards against hidden bias

If compact physical sensitivities survive, compare an adaptive error budget
with a uniform high-accuracy budget. Tie approximation to the current residual
and step acceptance, tightening near convergence. Test both 0% and 1% noise,
held-out data and several paired seeds; keep initializations, regularization,
data access and stopping rules fixed. A noise fraction alone is insufficient:
weak shape directions can be damaged by coherent model error below that level.

Compare explicit regularization on the full model. Otherwise an apparent
denoising benefit could simply be unacknowledged model bias. Report shape
error, held-out prediction, failed/rejected steps and total work, not just
training residual. If final certification uses the full model, charge it.

### 3. Economics only for a surviving construction

Require a cost breakdown against the current accuracy-matched Kress/compiled
reciprocal path: selection, geometry, assembly, factors/preconditioners,
forward/adjoint RHS, derivatives/actions, validation and refreshes. Measure
memory including peak construction storage and factor fill. A 25% entry saving
need not yield any wall-time saving. A memory improvement can stand on its own
if its intended workload is named and measured.

For a dense training phase of cost `C_off`, baseline per-query cost `C_full`,
and reduced per-query cost `C_red`, amortization requires

`queries > C_off / (C_full - C_red)`, with a positive denominator.

Every geometry refresh resets some or all of that cost. Report the number of
queries before refresh actually achieved in the intended workload. For
preconditioning, count true operator applications, check GMRES return status
and residuals, and compare full wall time across all RHS. A correct complete
matrix-free application has not been supplied by a fitted bandwidth law.

## Resolution of the reports' recommendations

| Recommendation | Review decision |
|---|---|
| General compression is the main speed project | Reject as established priority; no current whole-inverse bottleneck or saving demonstrated |
| Study quantitative weighted Müller block structure | Accept as a research question; reuse existing split/principal-symbol code and distinguish norms |
| Preserve every derivative matrix | Reject as the only admissible target; resolve physical trace-product alternative through MC-001 |
| Treat Fourier bandwidth alone as a geometry predictor | Reject; include regularity, nonlocal clearance, coordinate choice, frequency and stability |
| Prove a broad theorem before further diagnostics | Defer; first establish the useful approximation target with MC-001, then prove the bound that target needs |
| Enable preconditioning immediately | Reject; counts alone, discarded convergence flags and dense assembly do not establish savings |
| Reuse local scattering responses | Preserve as a separate useful mechanism; not an answer to whether entrywise compression is valuable |
| Claim uniqueness/novelty from a literature search gap | Reject; a geometry-uniform derivative/output bound is a candidate contribution, not established priority |

No successor implementation or numerical campaign is authorized by this
proposal. The requested organization, audit and next-step brief are complete
without executing these proposed tests.
