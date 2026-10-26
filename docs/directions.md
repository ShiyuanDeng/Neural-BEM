# Research directions: what would change, and why

**Questions this document answers:** Where could computation be reduced? Which
changes could avoid the current recovery failures? What is the next experiment
that would tell us whether each idea helps?

Updated 2026-10-25 against code and results at `670524839` on `organised`.
The scope is the 13 families in the [October 11 backlog][backlog], with their
earlier evidence and subsequent work. This is not every idea ever proposed.

## How to read this document

Start with the ranking, then open the direction that interests you. Each entry
explains the change in ordinary language before giving an implementation brief.
The IDs D01–D13 preserve the original backlog numbering; ranks can change.

The ranking is a **provisional estimate of interest**, not a measured benefit
or an execution order. Computation comes first. Recovery can outweigh speed
when the change addresses a demonstrated failure of the current solver.

This format and ranking rule were agreed with the user on 2026-10-25. Optimistic
benefits are hypotheses. A closed experiment stays visible even when its wider
direction remains worth considering. Effort describes change size, not a time quote.

The briefs specify the next useful research step. Their unresolved mathematics
is part of that step. Detailed run budgets and numerical criteria belong in a
pre-registered plan under `docs/iterations/` when a direction is selected.

### Current selection: presentation experiments, 2026-10-26

The user excludes further compact modal / reduced trace-model work from the
current experiments because that direction was already tested. Haibing's
item 7 is therefore removed from the shortlist; the evidence remains below.

Anchoring is a separate idea. Haibing's item 5 keeps the full current trace
system and reuses a reference factorization to help solve it. The proposed
combination is anchoring plus item 8 error measurements, without trace reduction.
The user accepted the remaining scope on 2026-10-26: item 3 is a diagnostic
on unchanged moves; the result is measured accuracy/cost with exact fallback.

The finalized [AN-001 plan](iterations/anchoring/iteration_01/03_plan.md) fixes
the component comparison and presentation outputs. No new inverse campaign
is part of this first experiment.

LAU-003/004 are the closest earlier reduced-model experiments. Their
forward/adjoint and tangent-enriched spaces overlap strongly with item 7's
aim, although its two-sided projection is not the identical construction.

Rule for the current work: do not add reduced trace spaces or modal compression
to anchoring under another name. The technical briefs below preserve possible
research questions; they do not override this selection or request new runs.

## Where a direction changes the solver

Use the [canonical A1–C12 map][chain] and [glossary][glossary] for exact terms.

```text
Stored curve
  A1 geometry arrays → A2 physical interaction matrix
                      + A3 source and receiver waves
                      → A4 boundary fields and predicted measurements
  B5 compare with observations
  B6 geometry directions → B7 measurement sensitivities → B8 gradient/curvature
  C9 propose a step → Geometry update: construct the trial curve
  C11 evaluate and accept/reject → C12 continue from the accepted curve
```

| Part being changed | Directions |
|---|---|
| Repeated physics construction or solution, A1–A4 | D01, D02, D03, D04, D05, D09 |
| Meaning or calculation of sensitivities, B6–B8 | D02, D03, D04, D06, D07, D08 |
| Shape representation and finite geometry update | D07, D08 |
| Route through the inverse problem | D06, D10, D12, D13 |
| Both shape representation and forward physics | D11 |

These overlap: changing A4 can require a different B7 derivative. A fast
prediction with the wrong derivative can make the whole fit slower or fail.

## What the current code is struggling with

- **Repeated work on changed curves.** Exact-curve geometry caching already
  exists. Reuse across different curves is a new approximation problem.
  A2 assembly, A3 waves and A4 factorization still matter after geometry reuse.
- **A finite move can produce a difficult curve.** [NR-001][nr001] recovered
  26/30 cases. The remaining four reached A1 distance-function lower-bound
  failures on nearly self-touching trials; this does not prove non-identifiability.
- **The update map can change that outcome.** [GU-001][gu001] recovered
  `hook__c13.3` with the slider. Its spectral, uncentred and N-update arms failed.
  This is one scene; retention of the other 26 recoveries was not tested.
- **Cost shares depend on the workload.** Historical [AC-002 profiling][cost]
  measured 48.35 ms for a new-curve solve versus 11.98 ms with reused geometry.
  Those CUDA timings are evidence of an opportunity, not a current CPU speed forecast.

The TG-002 default remains `modal_muller` + `spectral`, `CumulativePolicy`,
with no localization. The fit evaluates at working resolution; the benchmark
checks its endpoint afterward. Research variants and historical defaults differ.

## Provisional interest ranking

The benefit column describes an optimistic mechanism, not a promised speedup.
Ranking favors a connection to the limitations above; uncertainty is retained.
Updated 2026-10-26: full-trace anchoring is first. Excluded compact-model
directions remain documented but have no active interest rank.

| Rank | Direction | Where | Optimistic intended benefit | Effort | Evidence status |
|---:|---|---|---|---|---|
| 1 | [D04 Full-trace anchoring](#d04-solve-through-matrix-actions-and-reuse-previous-solves) | A4, B7 | Reuse a reference LU while solving the full changed system | Medium for AN-001 | Selected: Haibing 5+8; no trace reduction |
| 2 | [D01 Anchoring the operator construction](#d01-anchoring-physics-for-nearby-shapes) | A1–A4 | Avoid rebuilding expensive physics for every trial | Medium–high | Earlier first-order construction failed; deferred beyond AN-001 |
| 3 | [D08 Make useful shape moves easier](#d08-make-useful-shape-moves-easier) | B6, geometry update; sometimes A1 | Avoid wasted or obstructed moves; recover hard shapes | Medium–high | GU-002 slider success and preparation speedup; other charts untested |
| 4 | [D07 Construct and check curves directly from coefficients](#d07-construct-and-check-curves-directly-from-coefficients) | B6, geometry update | Cheaper preparation or reusable validity bounds | High for full engine | Only existing step-bound diagnostic selected for AN-001 |
| 5 | [D05 Separate object response from illumination](#d05-separate-object-response-from-illumination) | A3–A4 | Reuse a response for many sources or object configurations | Medium–high | Positive multi-object components; current workload differs |
| 6 | [D06 Let fields and shape improve together](#d06-let-fields-and-shape-improve-together) | A4, B5–B8 | Avoid difficult optimization paths caused by strict elimination | High | Earlier relaxation added no recoveries |
| 7 | [D09 Share geometry work across the interaction calculation](#d09-share-geometry-work-across-the-interaction-calculation) | A1–A2 | Reduce repeated kernel construction across frequencies/media | High | Tested Ewald constructions failed |
| 8 | [D10 Find a rough volume image before fitting its boundary](#d10-find-a-rough-volume-image-before-fitting-its-boundary) | Before A1–C12 | Enter a useful shape region without relying on boundary moves alone | High | Adapter failed; successful full handoff untested |
| 9 | [D11 Represent the object implicitly and change the physics solver](#d11-represent-the-object-implicitly-and-change-the-physics-solver) | A1–A4, B6–B7 | Handle shapes that strain an explicit boundary representation | Very high | Related forward studies; proposed inverse unestablished |
| 10 | [D12 Travel through complex shapes to bypass a turning point](#d12-travel-through-complex-shapes-to-bypass-a-turning-point) | Geometry/physics, C9–C12 | Reach a useful real solution along a different continuation route | Very high | Local mechanism works; tested routes did not return usefully |
| 11 | [D13 Reconstruct an auxiliary field with a better-shaped loss](#d13-reconstruct-an-auxiliary-field-with-a-better-shaped-loss) | New inverse outside A1–C12 | Stronger convergence behavior, then recover the interface | Very high | Formulation and prototype tested; original-data recovery unestablished |
| — | [D02 Reuse a library of physical responses](#d02-reuse-a-library-of-physical-responses) | A2–A4, B7 | Amortize construction across frequencies and shapes | High | Compact trace models excluded; operator interpolation remains separate and unselected |
| — | [D03 Keep fewer physics modes](#d03-keep-fewer-physics-modes-without-losing-shape-information) | A2, A4, B7 | Reduce assembly, solve and derivative cost together | Medium–high | Not pursuing; preserve prior compression failures |

D04's anchoring variant is first because it gives a bounded, interpretable
test of reuse without introducing a reduced model. Its complete-cost benefit
is uncertain: it still builds the changed matrix and source/receiver waves.

D01 has greater potential to avoid construction but needs a different mechanism
from the failed BIE-006 model. D12 and D13 still lack a demonstrated connection
from their mechanisms to the current recovery failures.

### Haibing items: order for the presentation work

| Priority | Items | Decision and reason |
|---:|---|---|
| 1 | 5 + measured parts of 8 | AN-001: full-trace anchoring versus fresh LU, with current-operator residuals and exact fallback |
| 2 | 3 | AN-001: measure step-bound coverage on the same moves; no clipping or altered trajectory |
| 3 | 4 | Deferred: incremental differences only if a later method needs accurate matrix differences; no assumed assembly saving |
| 4 | New part of 2 | Deferred: explicit singular-weight extraction needs a separate assembly-cost question |
| 5 | 11 | Longer-term: meaningful shape-flow evidence needs more than a circle identity |
| — | 6, 7 | Excluded from this plan: no Schur reduction or compact trace model bundled into anchoring |
| — | 1, existing parts of 2/3/9/10 | Reuse established infrastructure and controls; do not present them as newly implemented ideas |

Only the first two rows are scheduled by the AN-001 plan. The remaining ranks
record possible interest, not conditional extra experiments after a failure.

## Shared instructions for the next experiment

1. Read the chosen entry, its evidence, and the current linked implementation.
   State the new question and how it differs from the earlier experiment.
2. Put the smallest comparison that answers it in a dated iteration plan.
   Specify inputs, accuracy targets, total work limit and stopping criteria
   before measuring. Do not silently expand a component study into an inverse run.
3. For a code change, retain the current method as a control. Reuse saved
   TG-002 states when they answer the question. Match physical curves, data,
   working resolutions and hardware when interpreting a timing difference.
4. Charge setup, derivatives, rebuilds, failed attempts and validation work.
   Report first-use cost and the reuse count needed to recover setup cost.
   A smaller matrix or fewer iterations alone does not establish a saving.
5. A new inverse comparison follows the [TG-002 contract][benchmark]: ten
   scenes × three contrasts, one centred start, unchanged scoring. Follow the
   approved run scope; no far starts, grid search or extra cases by implication.
6. Keep mathematical implementations in `solvers/bem_inverse/` independent
   of campaigns and results. Put truth-based scoring and campaign work in
   `experiments/`. Use the [package API][package] and established checks.

For each approximation, distinguish prediction error, derivative error and the
effect on a finite step. Record the implemented tolerances and the independent
reference used; an accurate solution of an approximate equation is insufficient.

An experiment closes with its measured outcome and limits. Update this page's
evidence/status and next question, preserving earlier failures. User approval
of experiment work governs execution; this directions document is not a run request.

## D01 Anchoring physics for nearby shapes

**Technical name:** Shape-Taylor / reference-operator models.
**Location:** A1–A4, with consistency requirements at B7 and C11.

**Naming agreed 2026-10-26:** anchoring means reusing calculations from a
reference shape. This direction approximates the changed operator; Haibing's
item 5 instead uses the anchor's LU to solve the full current operator (D04).

**Today → change.** A changed trial curve needs its own physical interaction
calculation. Build a local approximation around an accepted curve and reuse
it while the trial stays sufficiently close; rebuild when it no longer applies.

**Intended effect.** Reduce the cost of damping retries and backtracking.
The potential saving comes from avoided construction, not from assuming LU
is the dominant cost. Approximation setup can consume the entire benefit.

**Evidence and status.** [BIE-006][bie006] tested first-order operator reuse:
it was less accurate than tangent-data prediction in 22/24 cases and extended
the 0.1%-error region in 0/6 paths. Its best qualified speed ratio was 0.772×.

That construction was stopped. No later test of a replacement was found in
the reviewed history. The wider question remains open, but repeating its
first-order construction without a different cost or error mechanism is unjustified.

**Remaining question.** Can a model tailored to the current modal construction
stay accurate over enough actual trial displacements to repay its setup?

**Agent brief — next experiment**

- **Entry points:** [`ModalMuller._solve`, `prepare_geometry`, `assemble_matrix`][modal],
  [`a2_muller.muller_matrix`][a2] and [`a4_fields.factorize`][a4]. The existing
  geometry cache matches identical coefficients; it is not changed-curve reuse.
- **Construction to derive:** choose one local directional model along a
  fixed B6 velocity, initially a quadratic shape expansion. State how its
  coefficients are obtained and charge that work before claiming amortization.
- **Mathematical requirement:** approximate A2, the A3 source RHS and receiver
  readout consistently. Track coordinate changes and truncation. A small
  residual against the approximated matrix does not bound the physical error.
- **Smallest comparison:** use a saved TG-002 accepted state and its next
  direction; replay the recorded backtracking lengths. Compare exact solves,
  tangent-data prediction and the chosen local model at identical trial curves.
- **Decision:** require a useful accuracy range and lower total work after
  setup and exact checks. Count how many real trials fit within that range.
  If the model expires before breaking even, close this construction.
- **Integration limit:** first measure offline. Any later trial-screening
  policy needs an error rule for loss decisions and exact accepted-state
  derivatives; a forward approximation alone is not a new inverse method.

## D02 Reuse a library of physical responses

**Technical name:** Operator atlas, reduced basis and empirical interpolation.
**Location:** A2–A4 and B7.

**User decision, 2026-10-26:** do not continue compact trace-model experiments
for the presentation. In particular, Haibing item 7 is not an anchoring arm.
The following evidence and research brief are retained for reference.

**Today → change.** Each new shape/frequency combination is handled directly.
Build a small library of representative operators or fields, then interpolate
or combine them for combinations the library has not seen.

**Intended effect.** Amortize expensive construction over a long trajectory
or repeated problems. Unlike D01's local expansion about one curve, this
direction seeks reuse over a collection of shapes or frequencies.

**Evidence and status.** [LAU-003][lau003] found that compact accuracy at one
shape did not reliably transfer to nearby shapes or new illumination.
[LAU-004][lau004] delivered 42/42 accurate results with 24 rebuilds.

The [September 18 study][laurentstudy] found operator frequency rank near 11,
while accurate solution/derivative bases needed roughly 80 dimensions.
Neither result establishes useful current-pipeline reuse across shapes.

MA-007's saved response atlas studied continuation controls; it was not an
operator surrogate. It is not a later success for this direction.

**Remaining question.** Is there a restricted reuse domain where prediction
and derivative accuracy survive long enough to repay library construction?

**Agent brief — next experiment**

- **Entry points:** [`ModalState` and the modal forward solve][modal],
  [`solve_and_predict`][a4], and the [reciprocal derivative][b7]. A separate
  physics context can enter through [`runner.fit`][runner].
- **Choose one target:** start with frequency interpolation at one saved
  TG-002 curve. Operator interpolation and a reduced solution basis are
  separate experiments; do not combine their error or cost claims.
- **Mathematical requirement:** define the basis, projection, interpolation
  weights and residual/error indicator. An operator fit must account for
  conditioning; a solution basis must also cover reciprocal responses.
- **Smallest comparison:** train on declared frequencies, predict held-out
  catalog frequencies, and compare fields, B7 derivatives and total cost with
  exact solves. Keep the held-out data out of basis selection.
- **Decision:** retain only if setup plus all uses and rebuilds beats exact
  work at the required accuracy. Shape transfer is a subsequent, separately
  bounded question; frequency success does not answer it.

## D03 Keep fewer physics modes without losing shape information

**Technical name:** Derivative-preserving modal compression.
**Location:** A2 matrix construction, A4 trace solves and B7 sensitivities.

**Current selection, 2026-10-26:** excluded from the presentation experiments.
Preserve the closed MC-001 result and the user's decision to pursue anchoring
separately from compact modal reduction.

**Today → change.** Physics retains a full window of boundary Fourier modes.
Keep a smaller, carefully chosen space while protecting the modes needed
to predict how measurements change when the shape moves.

A mode is one oscillating pattern around the boundary. A field can look
accurate with some patterns missing while its response to a shape change is wrong.

**Intended effect.** Smaller operators, traces and contractions could reduce
several costs together. A mode that barely changes today's field may still
matter strongly to tomorrow's shape direction.

**Evidence and status.** [LAU-002][lau002] reduced represented forward slots
by 19.6–25.8% in four noncircular cases, but still performed dense computation;
it established no runtime saving.

[MC-001][mc001] found no noncircular case meeting the common forward/derivative
target at 50% represented slots. Its next stage was not run, and that track
was closed. A sensitivity-aware construction would need a distinct argument.

**Remaining question.** Can a compact space preserve useful finite inverse
steps, rather than only the current forward field?

**Agent brief — next experiment**

- **Entry points:** [`kernel_matrix`, `muller_matrix`][a2],
  [`solve_and_predict`][a4] and [`hadamard`][b7]. Keep the two trace roles,
  Dirichlet field and speed-weighted flux, distinct.
- **Construction to derive:** form a trial reduced space from forward and
  reciprocal traces plus selected shape responses at one saved TG-002 state.
  Define how projection, scaling and omitted-mode error are measured.
- **Smallest comparison:** compare the reduced and full calculation on
  held-out directions at that state: predicted measurements, residual
  Jacobian, C9 proposal and the exact loss of the resulting finite trial.
- **Decision:** first establish a nontrivial reduction at common accuracy.
  Then measure a genuinely reduced implementation, charging basis work.
  Masking an already assembled dense matrix is an accuracy study only.
- **Limit:** reuse after changing the curve belongs to D02 unless explicitly
  included in this experiment. Raising/lowering `K_trace` through a policy
  is not by itself derivative-preserving compression.

## D04 Solve through matrix actions and reuse previous solves

**Technical name:** Matrix-free and recycled linear algebra.
**Location:** A2–A4; a separate variant changes B7–C9.

**Selected variant, 2026-10-26:** [AN-001](iterations/anchoring/iteration_01/03_plan.md)
tests full-trace anchor-LU reuse. It still assembles the current dense matrix;
it is neither matrix-free nor reduced-order. The broader brief below is deferred.

**Today → change.** Assemble a dense interaction matrix and factor it.
Instead, supply a routine that applies the interaction to a vector, solve
iteratively, and reuse useful solve information from nearby problems.

**Intended effect.** Reduce memory and factorization cost when systems become
large. It helps little if assembly still dominates or many iterative steps
cost more than the existing batched dense solve.

**Evidence and status.** The [September 18 study][laurentstudy] tested recycled
and approximate preconditioners and reduced GMRES iterations, but still
assembled the true dense matrix. This was not a matrix-free inverse result.

Historical [AC-002][cost] put LU at only 5.6% of a new-curve solve, versus
25.1% with reused geometry. Those workload-specific numbers keep this below
changes that can remove construction itself.

**Remaining question.** At what relevant size and reuse count does an iterative
method beat the complete current calculation?

**Agent brief — next experiment**

- **Entry points:** [`factorize`, `solve_and_predict`][a4] and
  [`reciprocal_jacobian`][b7]. The separate Jacobian-action variant touches
  [`curvature`][b8] and [`solve_proposal`][c9].
- **Construction to derive:** one block operator action and a preconditioner.
  Specify the actual action cost; multiplying a retained dense matrix tests
  iterative solving, not avoided assembly. Include all source/receiver RHS.
- **Smallest comparison:** use saved TG-002 states at their observed working
  resolutions, comparing cold and reused solves with dense LU. Start by
  checking whether the measured size regime can repay preconditioning.
- **Decision:** require field and derivative accuracy plus lower complete
  cost or a relevant memory advantage. Stop the current-workload claim if
  the crossover lies outside the sizes used by the fit.
- **Separate question:** replacing explicit `J` by `Jv`/transpose actions
  requires its own adjoint consistency and LM comparison; do not infer that
  benefit from a faster boundary-system solve.

## D05 Separate object response from illumination

**Technical name:** T-matrix / local scattering-response factorization.
**Location:** A3–A4.

**Today → change.** Solve the boundary problem for the actual source columns.
First calculate how the object responds to a reusable set of incoming waves;
express different sources in that basis and read out the resulting fields.

**Intended effect.** Reuse one response for many illuminations, receiver
arrangements or repeated object configurations. The response still changes
when the object's boundary changes.

**Evidence and status.** The [September 18 study][laurentstudy] tested local
responses and Graf translations against monolithic controls. Rebuilding only
the moved object agreed bitwise with rebuilding all objects.

That study reported substantial savings in multi-object reuse workloads.
Today's TG-002 problem is a single changing boundary with 24 paired sources
and receivers; the same amortization is not established here.

**Remaining question.** Does the actual acquisition supply enough repeated
work to repay a reusable response basis?

**Agent brief — next experiment**

- **Entry points:** [`WaveArrays`][a1], [`point_kernels`][a3] and
  [`solve_and_predict`][a4]. Existing Graf expansions provide ingredients,
  not an already selected T-matrix inverse.
- **Construction to derive:** incoming/outgoing modal normalization, basis
  truncation, translations and the mapping back to the measured paired data.
  Count basis RHS separately from the existing source RHS.
- **Smallest comparison:** on one saved TG-002 curve and frequency, compare
  the 24-pair calculation using a response basis versus the current batched
  solve. Include response construction and reciprocal-response requirements.
- **Decision:** report the reuse count needed to break even and whether the
  current fit provides it before the curve changes. A larger-acquisition
  component study can be valuable, but is a different workload claim.

## D06 Let fields and shape improve together

**Technical name:** Relaxed-BIE inverse formulation.
**Location:** Changes the reduced inverse around A4 and B5–B8.

**Today → change.** Every shape trial first satisfies the boundary equation,
then compares its predicted measurements with observations. Introduce field
unknowns and permit a controlled equation mismatch during optimization.

**Intended effect.** Fields and shape might move together through regions
where strict elimination gives an unhelpful optimization path. Additional
unknowns, penalty terms and inner solves can also increase cost substantially.

**Evidence and status.** The [relaxed-BIE record][relaxed] distinguishes an
initial incomplete gradient (FM-001) from its repair (FM-002). With damping,
both relaxed and unrelaxed arms recovered 3/3; the real prefix recovered 1/3.

RB-001 removed four immediate numerical stops but added 0/4 recoveries.
Those results did not establish a recovery advantage. Augmented-Lagrangian
updates or a different reduced curvature remain separate proposed mechanisms.

**Remaining question.** Can a well-defined relaxation improve useful shape
progress, rather than merely hide an equation error or delay a numerical stop?

**Agent brief — next experiment**

- **Entry points:** the `evaluate`/`linearize` functions in [`fit_stage`][fitstage],
  [`b5_residual.evaluate`][b5] and [B8][b8]. Current code has no auxiliary-field
  optimizer. The speed-unevenness penalty is not relaxed BIE.
- **Construction to derive:** choose an augmented-Lagrangian formulation
  with explicit field variables, boundary-equation residual and observation
  residual. Define weights, multiplier updates and all shape derivatives.
- **First decision:** establish how the formulation handles the current
  A1 refusal. If it still requires the same unavailable matrix on the same
  curve, it does not directly remove that obstruction.
- **Smallest numerical comparison:** at a saved state before that refusal,
  compare one relaxed proposal with the ordinary LM proposal. Evaluate both
  returned trial curves with exact physics and record complete cost.
- **Decision:** require useful exact-data progress and decreasing equation
  mismatch. An improved relaxed loss alone is not evidence of recovery.

## D07 Construct and check curves directly from coefficients

**Technical name:** Coefficient-space geometry and validity bounds.
**Location:** B6 and the geometry update; potentially shared A1 quantities.

**Today → change.** The spectral update samples a curve for its arclength
refit and checks final speed/intersections on nodes. Construct the update
and establish validity through coefficient operations and reusable bounds.

**Intended effect.** Reduce repeated preparation or checking and make error
control explicit. Eliminating samples is not itself a speed benefit: proving
whole-curve statements can cost much more than the present checks.

**Evidence and status.** [NG-001][ng001] completed 279 fixed moves; its full
prototype accepted 57 versus the control's 277. [NG-002][ng002] improved
construction and base proofs. [NG-003][ng003] constructed 243 qualified pairs.

[NG-004][ng004] then accepted 123/279 with complete validity checking, versus
277/279 for the frozen control. It made no physics calls. Construction success
and full acceptance are different results; no inverse improvement was shown.

Historical [GC-001][gc001] attributed 19.1% of the old fit's runtime to geometry
updates. That share is not a current universal upper bound, especially after
NR-001 removed finer re-evaluations and changed the work performed.

**Remaining question.** Can reusable bounds make the successful constructor
operational at acceptable cost without refusing many usable moves?

**Agent brief — next experiment**

- **Entry points:** [`SpectralProjectedUpdate.prepare`, `batched_projection`,
  `geometry_update`][spectral], [final-curve checks][checks] and optional
  [certificate mathematics][certificates]. NG's research engine is archived.
- **First task:** analyze NG-004's retained refusal reasons and times. It
  records 120 proof-unresolved refusals and 36 construction failures. Pick
  one cause for which a changed bound can plausibly improve cost or coverage.
- **Mathematical requirement:** bound all discarded modes and identify the
  exact curve to which each reused result applies. Distinguish a proof that
  failed to finish from evidence of an actual crossing.
- **Smallest comparison:** replay only the predeclared affected saved moves
  with unchanged constructed curves and a changed proof. Compare accuracy,
  decisions and total work against the retained NG-004 records.
- **Decision:** require a real acceptance/cost improvement before proposing
  a full geometry replacement. Current default checks inspect the final
  trial curve; historical multi-role checking is not the live baseline.

## D08 Make useful shape moves easier

**Technical name:** Alternative boundary coordinates and finite update maps.
**Location:** B6 and the geometry update; a new stored chart also changes A1.

**Today → change.** A normal step is refitted and cropped to stored Fourier
coefficients. Change how that step becomes a finite curve, or change the
coordinates used to describe the boundary itself.

**Intended effect.** Reach useful shapes with fewer obstructed or distorted
moves. Two methods can agree on an infinitesimal normal velocity yet produce
different finite trial curves, hence different inverse trajectories.

**Evidence and status.** The [geometry strategy brief][geometrybrief] separates
state representation, update space and finite path. [GU-001][gu001] is a
related test: the slider recovered hook c13.3; the other three arms failed.

GU-001 did not test a tangent-angle chart or an exterior conformal chart.
Its single-scene success does not establish retention of the other recoveries,
nor show that every failure was caused by speed unevenness.

**Remaining question.** Can a change in finite motion avoid the observed
near-touch obstruction while retaining the existing successful recoveries?

**Agent brief — next experiment**

- **Entry points:** [`FourierCurve`][curve], [`make_update`][selection],
  the [spectral method][spectral], [slider][slider] and
  [`runner.fit(geometry_adapter=...)`][runner].
- **Nearest next step:** use GU-001's saved paths to identify where the slider
  avoids the spectral obstruction. Before inventing another chart, register
  a TG-002 comparison of the existing slider with the default at matched settings.
- **Mathematical requirement:** separate the same physical normal velocity
  from a different span of allowed velocities. B6 must differentiate the
  actual finite map, including any normalization, centring or crop.
- **Alternative chart branch:** for positive-speed/tangent-angle coordinates,
  derive closure and the map to stored curves; for exterior conformal
  coordinates, derive normalization and admissibility. Test these separately.
- **Chart component test:** represent a saved concave TG-002 curve and a
  controlled move, checking geometry error and its complete derivative before
  any fit. A convenient parameterization must not exclude the target shape.
- **Decision:** retain a method for useful recovery or lower total work at
  preserved accuracy. More even speed or fewer geometric refusals alone
  does not establish a better inverse.

## D09 Share geometry work across the interaction calculation

**Technical name:** Ewald / shared-geometry factorization of Müller physics.
**Location:** A1–A2, with A3–A4 and B7 compatibility retained.

**Today → change.** Construct geometry-dependent interaction coefficients
for each medium and frequency. Split short-range and long-range interactions
and reuse common geometric maps in the resulting calculation.

**Intended effect.** Reduce repeated construction across frequencies and
media. The decomposition can instead create large intermediate terms,
expensive contractions or difficult cancellation near the interface.

**Evidence and status.** [ON-003][on003] failed circle accuracy/resource
requirements before full fields and derivatives were tested. [EW-001][ew001]
tested smaller splitting parameters and remained unfavorable.

Those constructions closed. A new test needs a different factorization or
a justified operating regime, not another unexplained parameter sweep.

**Remaining question.** Can a complete transmission factorization preserve
the necessary near-field cancellations at less total construction cost?

**Agent brief — next experiment**

- **Entry points:** [`ModalGeometry`, `ChebyshevArrays`][a1],
  [`muller_matrix`][a2] and its [CUDA assembly counterpart][cuda].
- **First task:** derive the proposed full near/far split, including jumps,
  diagonal limits and both media. Estimate contraction cost and cancellation
  before allocating a new implementation campaign.
- **Smallest comparison:** on the TG-002 circle, compare complete Müller
  blocks and predicted fields with the existing solver at a declared
  frequency/contrast where the cost estimate predicts a benefit.
- **Decision:** stop if the complete matrix cannot meet the matched error
  target or its cost estimate already exceeds the current method. Passing
  one scalar kernel does not release a full inverse comparison.
- **Next prerequisite:** shape derivatives and close-interaction behavior
  must be established before claiming usefulness along difficult trajectories.

## D10 Find a rough volume image before fitting its boundary

**Technical name:** Volume-to-boundary hybrid inversion.
**Location:** A new stage before `runner.fit()`, followed by ordinary A1–C12.

**Today → change.** Begin from a circle and move its boundary. First estimate
material over an area, extract a contour from that image, then pass the contour
to the boundary solver for accurate refinement.

**Intended effect.** Reach a useful starting shape that boundary-only updates
miss. The volume solve, contour extraction and handoff must all be charged;
a visually plausible image may still be a poor scattering shape.

**Evidence and status.** [ON-002][on002] passed 0/25 required adapter solve
checks; its hybrid inverse remained unrun. [GS-001][gs001] improved a volume
fit to 0.461% single-frequency residual but retained 28.088 mm contour RMS error.

That is evidence about a volume stage, not a successful complete handoff.
The proposed GP-001 hybrid was not a completed result in the reviewed history.

**Remaining question.** Can a volume stage using the same observations produce
a physically useful boundary quickly enough to improve the total inverse?

**Agent brief — next experiment**

- **Entry points:** campaign code in `experiments/`, [`Problem.initial`][problem],
  [`FourierCurve.from_samples`][curve] and [`runner.fit`][runner]. There is no
  current volume inverse to enable by changing a pipeline name.
- **First task:** resolve the recorded forward-adapter mismatch. Match units,
  source normalization, contrast, receiver convention and scattered/total field
  definitions on the same TG-002 circle before optimizing anything.
- **Handoff to derive:** a deterministic contour extraction and Fourier fit
  with declared handling of multiple components and thin gaps. Use data and
  geometry checks, never truth geometry, to select the handoff.
- **Smallest next comparison:** adapter field agreement first. If that passes,
  plan the volume-plus-boundary comparison against boundary-only fitting
  with all work and the same measurement catalog charged.
- **Decision:** a lower volume loss is insufficient. Judge the final boundary
  with unchanged TG-002 scoring; additional data make a separate feasibility
  study rather than a benchmark improvement.

## D11 Represent the object implicitly and change the physics solver

**Technical name:** Implicit geometry with IBIM/KFBI-type physics.
**Location:** Replaces A1–A4 and much of B6–B7.

**Today → change.** Store an explicit curve and solve interactions on its
boundary. Store a level-set or signed-distance field instead, and evaluate
sharp-interface physics through an embedded-grid or implicit-boundary method.

**Intended effect.** Make complicated geometric evolution easier to represent.
This could remove some explicit-chart restrictions, but introduces extraction,
normal estimation, singular treatment and derivative errors of its own.

**Evidence and status.** The [research freeze][freeze] records earlier
IBIM/MOD/QBX/kernel-difference forward studies and the closure of compressed-cloud
work without a demonstrated robustness/cost advantage.

Related scalar and implicit-quadrature studies do not establish this proposed
transmission inverse. Changing the representation alone does not solve the
current field-calculation or recovery failures.

**Remaining question.** Can an implicit sharp-interface forward method supply
accurate, affordable fields and shape sensitivities for this transmission problem?

**Agent brief — next experiment**

- **Entry seams:** [`physics.make_backend`][physics] and [`runner.fit`][runner]
  accept alternative physics/update components. They are integration seams,
  not existing IBIM/KFBI implementations.
- **Construction to derive:** select one method and derive transmission jumps,
  singular corrections, geometry normals and the complete shape derivative.
  Declare the smoothing width and grid-refinement relationship if applicable.
- **Smallest comparison:** qualify fields on the TG-002 circle, then a
  saved smooth noncircular TG-002 boundary at matched accuracy against the
  nodal reference. Compare derivatives only after the forward result holds.
- **Decision:** require a credible accuracy/cost regime before an inverse.
  If performance needs new physics, measurements or a multi-component task,
  identify that as a separate research scope.
- **Difference from D10:** D10 hands a volume image to existing boundary
  physics. This direction changes the physics used throughout reconstruction.

## D12 Travel through complex shapes to bypass a turning point

**Technical name:** Complex-geometry continuation.
**Location:** A separate geometry/physics extension and C9–C12 path following.

**Today → change.** Follow real shapes as the continuation settings change.
Allow intermediate shape parameters to be complex, travel around a branch
point, then try to return to a useful real solution.

**Intended effect.** Reach a solution branch that a real continuation route
cannot follow directly. A branch exchange can also lead to a maximum or leave
the path at a nonreal endpoint, which is not a recovered physical object.

**Evidence and status.** [CG-001–003][complex] demonstrated local branch
exchange in a fixed-centre radius family. Real pseudo-arclength also crossed
the fold. None of three fixed detours returned a real endpoint at the target.

CG-003 tested 92 directed loops with zero real returns; the tested actions
stayed within a complex pair. Those route families closed. General complex
Fourier shapes and full benchmark recovery remain unrun.

**Remaining question.** Is there a demonstrably different route connecting
the observed branch to a useful real endpoint?

**Agent brief — next experiment**

- **Historical starting point:** the archived [complex-geometry track][complex]
  and its derivation. Reuse its saved endpoint/branch evidence before adding
  another continuation sweep.
- **First task:** identify a new critical value or attachment route and derive
  why it could escape the observed two-root action. If the same generators
  cannot leave that pair, composing more of them does not answer a new question.
- **Smallest comparison:** only after identifying such a route, compare it
  with the existing real pseudo-arclength control in the same radius problem;
  check real return, stationarity and whether the endpoint is a useful minimum.
- **Implementation limit:** [`ModalGeometry`][a1] contains conjugations and
  real products. Complex Fourier coefficients already encode ordinary real
  planar curves; accepting complex arrays is not holomorphic shape continuation.
- **Decision:** a full complexified boundary engine needs a separate derivation.
  Neither complex-frequency damping nor a local branch swap establishes the
  required real-shape recovery advantage.

## D13 Reconstruct an auxiliary field with a better-shaped loss

**Technical name:** Carleman-style convexification / auxiliary-field reconstruction.
**Location:** A new inverse outside the present A1–C12 fit.

**Today → change.** Minimize measurement mismatch over boundary coordinates.
Transform the field equations into a weighted auxiliary-field problem, solve
that problem, then infer the material interface from its solution.

**Intended effect.** Obtain better convergence behavior, potentially with
stronger guarantees under suitable assumptions. A theorem for another
observation model does not guarantee recovery from our paired measurements.

**Evidence and status.** [CVX-001][convex] completed formulation checks and
identified a smoother differentiated log-field quantity. Tail closure and
boundary observability remained unresolved under the original information model.

CVX-002 used augmented Cauchy data. Low-contrast images improved overlap but
failed the original paired-data physical check; six stronger-contrast arms
stopped at log-field checks. Grid refinement did not establish convergence.

**Remaining question.** Can the auxiliary-field formulation be closed and
observed from admissible data without an unknown interior field supplied as truth?

**Agent brief — next experiment**

- **Historical starting point:** [CVX-001/002 and their derivations][convex].
  No current auxiliary-field implementation belongs inside `fit_stage`;
  a prototype would be isolated under `experiments/` initially.
- **First task:** write the observation operator and all unknown tail/reference
  fields explicitly. Determine what the paired TG-002 observations actually
  constrain and which proposed boundary quantities would require extra data.
- **Mathematical requirement:** establish closure and the applicable weighted
  estimate for the selected formulation. Record assumptions about interfaces,
  nonzero fields and regularity; mark unsupported steps as open questions.
- **Smallest comparison:** test the identified closure or observability claim
  using retained CVX evidence or a declared component problem. A new weighted
  optimization run is premature while the required inputs remain unavailable.
- **Decision:** separate success with additional Cauchy data from success on
  the unchanged inverse. A useful formulation result can stand alone without
  being presented as a TG-002 recovery improvement.

## Evidence coverage and maintenance

The history search covered the 71 commits from backlog creation `e09be5267`
through `670524839`, including changed-file lists and relevant result reports.
Earlier evidence was read at preserved revision `a64de2eed`.

Direct later families were NG-001–004, CG-001–003 and CVX-001–002. GU-001 is
related finite-update evidence for D08. MA-007 studied continuation controls;
NR-001 changed in-fit numerical checks. Neither establishes an operator surrogate.

No new post-backlog experiment answering D01–D06 or D09–D11 was found in
that available history. This describes recorded work, not a proof that no
uncommitted or external experiment exists. Numerical results were not rerun.

Archived links below are pinned to the last preserved research snapshot.
Current implementation links point into this checkout. The historical evidence
page contains older defaults; use the current chain map and source for behavior.

When adding an experiment, record its date, ID, exact intervention, outcome,
limits and source link in the relevant direction. Change the direction's next
question explicitly; do not replace a failed experiment with a fresh proposal.

[backlog]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/reports/architectural_experiment_backlog_2026-10-11.md
[chain]: reference/inverse_information_chain.md
[glossary]: ../GLOSSARY.md
[benchmark]: ../experiments/benchmark/README.md
[package]: ../solvers/bem_inverse/README.md
[nr001]: ../results/validation/cleaned_interfaces/NR-001/README.md
[gu001]: ../results/validation/cleaned_interfaces/GU-001/README.md
[cost]: evidence.md
[gc001]: ../results/validation/cleaned_interfaces/GC-001/README.md
[bie006]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/boundary_bie/iteration_04/01_results.md
[lau002]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/laurent/iteration_04/01_results.md
[lau003]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/laurent/iteration_05/01_results.md
[lau004]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/laurent/iteration_06/01_results.md
[laurentstudy]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/results/experiments/laurent_fgm_20260918/README.md
[mc001]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/modal_compression/CLOSEOUT.md
[relaxed]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/relaxed_bie/README.md
[geometrybrief]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/atlas_geometry_high_level_next_steps.md
[ng001]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/node_free_geometry/NG-001_results.md
[ng002]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/node_free_geometry/NG-002_results.md
[ng003]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/node_free_geometry/NG-003_results.md
[ng004]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/results/validation/node_free_geometry/NG-004/run-01/report.json
[on003]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/CI-SPD/iteration_01/05_ON003_results.md
[ew001]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/results/validation/cleaned_interfaces/EW-001/summary.json
[on002]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/results/validation/cleaned_interfaces/ON-002/resume128_double/summary.json
[gs001]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/CI-SPD/GS-001_results.md
[freeze]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/reports/research_freeze_2026-10-05.md
[complex]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/complex_geometry/README.md
[convex]: https://github.com/ShiyuanDeng/Neural-BEM/blob/a64de2eed/docs/iterations/convexification/README.md
[modal]: ../solvers/bem_inverse/forward_solvers/modal_muller.py
[a1]: ../solvers/bem_inverse/a1_geometry.py
[a2]: ../solvers/bem_inverse/a2_muller.py
[a3]: ../solvers/bem_inverse/a3_waves.py
[a4]: ../solvers/bem_inverse/a4_fields.py
[b5]: ../solvers/bem_inverse/b5_residual.py
[b7]: ../solvers/bem_inverse/b7_data_jacobian.py
[b8]: ../solvers/bem_inverse/b8_gauss_newton.py
[c9]: ../solvers/bem_inverse/c9_lm.py
[fitstage]: ../solvers/bem_inverse/fit_stage.py
[runner]: ../solvers/bem_inverse/runner.py
[problem]: ../solvers/bem_inverse/problem.py
[physics]: ../solvers/bem_inverse/physics.py
[curve]: ../solvers/bem_inverse/continuation/geometry.py
[selection]: ../solvers/bem_inverse/geometry_selection.py
[spectral]: ../solvers/bem_inverse/geometry_update_methods/spectral.py
[slider]: ../solvers/bem_inverse/geometry_update_methods/slider.py
[checks]: ../solvers/bem_inverse/checks.py
[certificates]: ../solvers/bem_inverse/geometry_update_methods/certificates.py
[cuda]: ../solvers/bem_inverse/modal_cuda.py
