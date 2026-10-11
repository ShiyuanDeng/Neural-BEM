# Architectural experiments ranked by deviation from the current pipeline

2026-10-11. Research proposal backlog.

The aim is to conduct standalone scientific comparisons that establish where
each architecture works, fails, and becomes worthwhile. Immediate integration
into the maintained solver is not an acceptance criterion. Negative results,
qualified component results, and useful operating limits are valid outcomes.

The scope is architectural changes to geometry, physics, linear algebra or the
inverse formulation. The ranking measures how much of the current **Fourier
curve → dense modal Müller → reciprocal Jacobian → LM** pipeline must change.
It is a rough implementation ranking, not a ranking of expected scientific
value or an execution order. Several families have existing prototypes,
partial tests or negative evidence; each new experiment must identify its
specific unanswered question.

## Ranked architectural ideas

| Rank | Architectural idea | Deviation | What changes and what the experiment should establish |
|---:|---|---|---|
| **1** | **Shape-Taylor / reference-operator models** | Low–medium | Approximate the forward operator around an accepted shape and reuse it for nearby trials. Test the useful displacement range, field/derivative errors, rebuild frequency, and total cost. Previous negative first-order reuse results become controls. |
| **2** | **Operator atlas / reduced basis / empirical interpolation** | Medium | Build a reduced representation across shapes and frequencies, replacing repeated full assembly or solves. Test held-out trajectories and directions, including training and rebuilding costs. Establish whether useful transfer exists beyond the training neighborhood. |
| **3** | **Derivative-preserving modal compression** | Medium | Compress operator blocks or forward/reciprocal traces while protecting the physical sensitivities needed by inversion. Test fields, Jacobians, LM directions and finite-step predictions separately. Include block-specific budgets and Sobolev scaling as distinct variants. |
| **4** | **Matrix-free and recycled linear algebra** | Medium | Replace dense assembly/factorization with operator actions and iterative solves. A separate experiment can replace the explicit inverse Jacobian with `Jv`/`Jᵀv` actions. Measure convergence, preconditioner construction, recycling across changing shapes, memory and the size at which savings begin. |
| **5** | **T-matrix / local scattering-response factorization** | Medium | Separate an object's scattering response from illumination, receiver position and possibly interactions with other objects. Test accuracy and amortization as the number of illuminations, frequencies or repeated configurations grows. Existing isolated implementations provide a starting point. |
| **6** | **Relaxed-BIE inverse formulation** | Medium–high | Replace strict satisfaction of the boundary equation at every inverse step with auxiliary fields and a controlled equation residual. Test augmented-Lagrangian updates and improved reduced curvature separately. Establish whether relaxation changes the optimization landscape usefully, rather than simply reducing inner-solve accuracy. |
| **7** | **Coefficient-space geometry and certification architecture** | Medium–high | Replace sampled geometry construction/checking with coefficient operations, reusable residual certificates and verified intersection/regularity tests. Measure accuracy, decisiveness, cost and failure modes near thin gaps and poor parameterizations. This tests a geometry engine independently of inverse recovery. |
| **8** | **Alternative boundary coordinates** | High | Replace the current Cartesian Fourier chart and finite update map. Candidates include positive-speed/tangent-angle coordinates and exterior conformal coordinates. First compare representation accuracy, closure, distortion, admissibility and derivatives; then compare inverse behavior on the same physical targets. These should be separate arms. |
| **9** | **Ewald / shared geometry factorization of Müller physics** | High | Replace the present kernel assembly with near/far decomposition and geometry maps shared across media and frequencies. Test the complete transmission operator, including close interactions and derivatives. Earlier ON-003/EW-001 failures are the baseline; a new experiment needs an explicitly different construction or regime. |
| **10** | **Volume-to-boundary hybrid inversion** | High | Begin with a volume representation, extract a contour, then continue with the boundary inverse. Test whether the volume phase reaches shapes that boundary-only optimization misses, and whether the gain survives charging the volume solve, contour extraction and handoff. Adapter qualification remains part of the experiment. |
| **11** | **Implicit geometry with IBIM/KFBI-type physics** | Very high | Replace the explicit boundary-centric representation with a level set or SDF and a sharp-interface embedded formulation. Test geometry extraction, singular treatment, transmission accuracy and complete shape derivatives before reconstruction. This is a different forward/inverse architecture from the volume-to-boundary hybrid. |
| **12** | **Complex-geometry continuation** | Very high | Replace real-shape continuation with a predictor–corrector acting on genuinely complexified geometry and a homotopy parameter. Test whether it can traverse a qualified turning-point example and return to a valid real solution. Complex-frequency damping alone does not test this idea. |
| **13** | **Carleman-style convexification / auxiliary-field reconstruction** | Very high; theory prerequisite | Replace the current shape least-squares formulation with a weighted auxiliary-field problem, followed by interface recovery. The first experiment must establish a formulation whose assumptions fit transmission interfaces and available data. Treat it as a formulation study before a benchmark competitor. |

## Common scientific comparison contract

**Track 12 investigation, 2026-10-11:** [CG-001/002](../iterations/complex_geometry/README.md)
qualified complex-radius transport around a physical transmission-data fold:
one loop exchanges a real minimum and maximum, and two restore the start.
Real pseudo-arclength also passes the fold. Three fixed detour heights to the
measured-data endpoint all return the same nonreal root; no inverse advantage
is established. The [literature/theory audit](../iterations/complex_geometry/LITERATURE_THEORY_AUDIT.md)
supports the local fold mechanism; equal endpoints do not establish equal
winding. The next question is whether an accessible real minimum exists at
t=1, then how to select routes to it. General complex Fourier geometry and
benchmark recovery remain unrun.

**Track 13 investigation, 2026-10-11:** [CVX-001](../iterations/convexification/CVX-001_results.md)
completed the formulation/component study. Differentiating the normalized log
field cancels its second-derivative interface jump; the current TMz jump is
zeroth order. Literature assumptions, exact paired-data completion limitations
and tail closure prevent claiming a qualified benchmark competitor. All five
registered component gates passed. The subsequent
[CVX-002 implementation](../iterations/convexification/CVX-002_results.md)
jointly reconstructs the unknown reference field and coefficient from explicitly
augmented Cauchy data. Four low-contrast fits across two grids improve overlap,
but their binary readouts fail the original paired accuracy gates; the weight
does not help. Six stronger-contrast screen arms stop at sampled log-field
qualification. No maintained solver default changed or benchmark recovery is
claimed.

- **Match the physical task and target accuracy.** Each method can use its own
  appropriate discretization and solver. Match numerical accuracy before
  interpreting performance differences.
- **Charge all relevant work:** construction, training, preprocessing,
  rebuilding, failed solves and handoffs. Report both first-use and amortized
  costs, with the workload over which amortization is claimed.
- **Separate component conclusions from inverse conclusions.** A good operator,
  derivative or representation result can be scientifically valuable without
  improving recovery. Component and forward-only studies may isolate the
  mechanism they test.
- **Use TG-002 for every new inverse comparison:** the ten scenes at contrasts
  0.5, 4 and 13.3, one prescribed centered start, no grid search or far starts,
  and unchanged recovery scoring. Follow the
  [benchmark contract](../../experiments/benchmark/README.md). Ideas requiring
  additional measurements or different physics belong to separately described
  feasibility studies; they do not establish an improvement under the unchanged
  TG-002 information contract.
- **Predeclare a falsifiable hypothesis and failure criteria for each
  architecture.** Put each selected experiment's plan in `docs/iterations/`,
  specifying its controls, accuracy checks, work accounting and evidence to
  retain. Successful integration into the maintained solver is not an
  acceptance criterion.

## Instructions for agents starting a track

These instructions apply to every numbered architecture above. When assigned
a track, act as a researcher responsible for answering its scientific question.
Use code as an experimental instrument. A working implementation alone is not
the research result, and immediate production integration is not the goal.

1. **Establish the question and prior evidence.** Read the track's proposal,
   relevant saved successes and failures, and the current implementation at
   the pipeline stage being changed. State the unresolved mechanism in one
   sentence, the intuition behind it, and an observation that would falsify
   it. Identify whether this is a reproduction, a changed construction or a
   new operating regime. Do not treat an old failed implementation as proof
   that the whole architecture cannot work.
2. **Consult literature and theory online as needed.** Read primary papers,
   derivations and authoritative implementation documentation for the central
   mathematical claims. Follow promising references beyond the repository
   when they clarify the mechanism or suggest a discriminating experiment.
   Record links and the relevant equation, theorem or section, together with
   its assumptions. Explain which assumptions hold here and which require
   adaptation. Distinguish established results, your own deductions and
   conjectures; a citation is not evidence that a theorem applies to our
   transmission problem.
3. **Derive the mathematics needed for the actual experiment.** Work out the
   relevant operator, approximation, geometry map, residual and derivative
   before relying on an implementation. Include geometry-dependent bases,
   source/readout terms and coordinate scaling where they matter. Derive
   useful error, conditioning or cost estimates, and predict the regime in
   which the idea should help or fail. Use limiting cases, units and simple
   analytic controls to check the reasoning. A counterexample, bound or
   crossover estimate can itself be a valuable result.
4. **Design the smallest fair experiment that decides the question.** Write
   a compact pre-registered plan under `docs/iterations/`: hypothesis,
   intervention, matched control, independent or refined reference, accuracy
   targets, work budget, tuning allowance and stopping criteria. Use component
   studies and ablations when they isolate the mechanism. Match physical
   information and output quality while allowing each architecture its own
   suitable discretization and algorithm. Preselect evaluation cases and
   separate training/tuning from evaluation; do not select updates or winners
   using truth. Follow the TG-002 contract above for inverse comparisons.
5. **Implement and measure only what the question needs.** Keep prototypes
   isolated from maintained defaults and reuse qualified components where
   appropriate. Check the proposed mathematics against the reference before
   interpreting performance. Record numerical error, useful progress,
   memory and complete cost, including setup, failed attempts and rebuilding.
   Test the predicted useful regime as well as a relevant stress case. A
   different architecture need not reproduce the baseline's iterate sequence.
6. **Explain the outcome scientifically.** Separate implementation defects,
   numerical inaccuracy, representation limits, optimization behavior and
   resource exhaustion. Use a targeted control to test a proposed explanation
   when feasible. Mark an explanation as a hypothesis when it has not been
   isolated. Report support, partial support, refutation or an inconclusive
   result for the stated hypothesis and tested regime. Budget exhaustion or
   an unqualified derivative does not establish that an architectural idea
   is false. Preserve failed evidence and stop when the declared question has
   been answered; further work should have a specific scientific reason.

Keep the derivation and experiment notes as detailed as reproducibility needs,
and make the user-facing closeout brief. Link to the evidence rather than
repeating a run log or a code-change inventory. The
[research implementation principles](../iterations/implementation_principles.md)
provide supporting guidance; current user instructions and
[AGENTS.md](../../AGENTS.md) govern scope and repository operations.

Use one implementation owner and a separate scientific reviewer where
available. Literature reading, derivation and read-only review may proceed
in parallel. Coordinate implementation and measurements so agents do not
concurrently edit the shared checkout or change sources during a measured
comparison. Work in the existing checkout; creating any branch or worktree
requires the user's specific approval. After each new experiment run,
validate, preserve its code and evidence including failures, commit and push,
then verify the push and working-tree status as required by AGENTS.md.

## Brief closeout for every track

Use at most **150 words**, excluding evidence links, with these five points:

- **Question:** What architectural hypothesis did we test?
- **Result:** Supported, partly supported, refuted, or inconclusive in the
  tested regime; give the one to three measurements that decide this.
- **Why:** Give the scientific mechanism and a plain-language intuition in
  one or two sentences. Label an unverified explanation as a hypothesis.
- **Limit:** State the main applicability boundary or unresolved confounder.
- **Decision:** Close this experiment, retain the demonstrated result, or
  name one discriminating next test; give a brief reason. Integration is a
  separate decision.

For example, a reason should explain a measured effect such as rebuilding a
surrogate before its setup cost can be recovered, or preserving field accuracy
while losing a shape-sensitive direction. Avoid unsupported statements such
as "the method is unsuitable" or a closeout consisting only of "implemented
and tests passed." Detailed plots, derivations and failure records belong in
the linked artifacts.

## Proposal sources and prior evidence

- [Seven GauGal-style restructurings](../iterations/cleaned_interfaces/iteration_30/02_proposals/02_gaugal_restructuring_integration.md):
  shape-Taylor models, T-matrix factorization, operator atlases, Krylov,
  Ewald and implicit/volume alternatives.
- [Fully modal Müller atlas vision](fully_modal_muller_atlas_research_vision.md)
  and [modal-compression closeout](../iterations/modal_compression/CLOSEOUT.md):
  modal structure, inverse sensitivities and previous compression evidence.
- [Relaxed-BIE literature and GPU review](../iterations/relaxed_bie/iteration_01/02_proposals/01_literature_and_gpu_review.md):
  auxiliary-field formulation, curvature and augmented-Lagrangian follow-ups.
- [Geometry strategy brief](../atlas_geometry_high_level_next_steps.md),
  [coefficient-space geometry proposal](../iterations/cleaned_interfaces/iteration_08/02_proposals/01_coefficient_space_update.md)
  and [original implicit-geometry report](../reference/deep-research-report.md):
  coordinate choices, geometry operations and certificates.
- [Cartesian Fourier theory directions](../theory_directions_cartesian_fourier_2026-10-03.md):
  genuine complex-geometry continuation and convexification assumptions.
- [Research freeze](research_freeze_2026-10-05.md): completed work, failed
  experiments and the distinction between isolated evidence and maintained
  inverse qualification.
