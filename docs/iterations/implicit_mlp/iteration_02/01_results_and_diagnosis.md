# Iteration 2 — results and suspected causes

Recorded 2026-09-08 by Codex. **Awaiting ChatGPT's fix proposal and subsequent
review; no next long inverse is authorized by this report.**

## Outcome

The repaired three-case wrong-start suite did not establish full-MLP recovery.
Circle retains approximately the previous accuracy and reaches its update
budget. Star ends with worse geometry than September 7 and stops at a
conversion-refinement/search limit. Ellipse-to-circle fails before saving a
result bundle. Circle and star have valid videos. Treat the missing ellipse arm
as an execution failure, not an inverse accuracy measurement.

The three-step `star-truth` run was a separate local diagnostic, not one of these
wrong-start comparisons. Its results and the prior acquisition findings are
included in this report and the local
[controls/observability evidence](evidence/01_prior_controls_and_observability.md).

## Experiment and comparison limits

The production geometry belongs to an 8,577-weight SIREN. Its zero contour is
extracted, converted by Method B, and evaluated by Kress BEM. Discrete-adjoint
sensitivities propagate through the local extraction/conversion branch to the
network weights. Every actual trial is re-extracted and checked; rejected trials
restore accepted weights. This is not the separate five-parameter star inverse.

All three requested cases preserve 12 paired source/receiver views, Kress/adjoint,
a 60-accepted-update cap, width 64, two hidden layers, omega 10, seed 0, and
6,000 pretraining steps. Learning rate is 0.001 and inverse Eikonal weight 0.01.
Materials and the measurement ring are unchanged. The observation data are
noise-free independent Mie data for the circle and Nystrom data for the star.

| Case | Wrong initial field | Training GHz | Evaluation-only GHz |
|---|---|---|---|
| Circle | `siren_circle` | 0.25, 0.5 | 1, 1.5, 2.5 |
| Ellipse-to-circle | `siren_ellipse` | 0.25, 0.5 | 1, 1.5, 2.5 |
| Star | `siren_star` | 0.5, 1.5 | 0.25, 1, 2.5 |

The following changes are intentionally included in this whole-configuration
comparison. They prevent attributing a difference solely to the line-search fix.

| Setting | September 7 baseline | September 8 suite |
|---|---|---|
| Line search | Earlier fallback; 8 backtracks | Repaired fallback; 14 backtracks |
| Conversion audit | No production conversion-distance guard in original bundle | 0.2 mm distance; 0.01 mm refinement-change limit |
| Circle and ellipse conversion | 64 nodes; bandwidth 10; grid 129; projected samples 64 | 64 nodes; bandwidth 20; grid 257; projected samples 128 |
| Star conversion | 128 nodes; bandwidth 48; grid 257; projected samples 128 | 194 nodes; bandwidth 96; grid 513; projected samples 256 |
| Star pretraining Eikonal weight | 0.1 | 0 |
| Circle/ellipse pretraining Eikonal weight | 0.1 | 0.1 |

The circle resolution had prior circle evidence; applying it to the ellipse
initialization had not been validated. The star's changed supervised fit also
changes the starting contour: initial maximum sampled boundary error is
39.679 mm in the baseline and 42.745 mm in the new run.

Both versions were run from dirty working trees. Metrics record base commits
`659c7e47988826352ec00a4b4b0d9c7ca19dd4bb` (September 7) and
`838bedf4eb37beb3c01ae770958e6c92f2abdf04` (September 8), on
`feature/ordered-boundary-nystrom`. These commit IDs alone do not reproduce the
executed code. Preserve each bundle's commands and provenance.

## Measured comparison

Boundary error below is the recorded maximum distance from sampled Method-B
nodes to the exact target boundary, in millimetres. It is not a certified
continuous Hausdorff distance. Relative L2 values use each case's recorded
frequency sets; training and holdout contain different frequencies.

| Case / run | Accepted updates | Stop / execution status | Train rel. L2 | Holdout rel. L2 | Boundary error, mm |
|---|---:|---|---:|---:|---:|
| Circle, September 7 | 43 | `no_decreasing_neural_step` | 0.001690 | 0.063944 | 1.038 |
| Circle, iteration 2 | 60 | `maximum_iterations` | 0.002061 | 0.061283 | 1.069 |
| Ellipse-to-circle, September 7 | 60 | `maximum_iterations` | 0.008951 | 0.318638 | 6.450 |
| Ellipse-to-circle, iteration 2 | Not recorded | `failed_inverse`, exit 1; empty folder | — | — | — |
| Star, September 7 | 60 | `maximum_iterations` | 0.245624 | 0.783925 | 26.833 |
| Star, iteration 2 | 47 | `no_decreasing_neural_step` | 0.482413 | 0.862650 | 37.368 |

Both new completed inverses fail overall scientific acceptance. The suite uses
`--no-gate` so a recovery FAIL still produces artifacts and a video; it does not
disable optimizer acceptance checks. Ellipse's nonzero exit is therefore an
execution error, not just a final recovery FAIL.

| Iteration 2 case | Attempted training evaluations | Rejected trials | Recorded inverse wall time | Video |
|---|---:|---:|---:|---|
| Circle | 423 | 362 | 2,306.50 s / 38.44 min | Valid H.264, 125 s |
| Ellipse-to-circle | Not recorded | Not recorded | Not recorded | Missing |
| Star | 420 | 372 | 5,353.74 s / 89.23 min | Valid H.264, 99 s |

Evaluation totals include the initial evaluation and attempts rejected during
geometry construction before a BEM solve. Wall times are single-run engineering
measurements; they exclude some setup/control/video work and are not a matched
hardware or isolated solver-cost benchmark. Circle plus star already consumed
127.67 minutes of recorded inverse time.

## Circle: good placement, unresolved boundary accuracy

The final center and radius errors are only 0.0514 mm and 0.0137 mm, while the
maximum sampled boundary error is 1.069 mm. This indicates residual shape error
beyond simple translation and radius. The same network fitted directly to the
exact target achieves 0.2837 mm boundary error and 0.01628 holdout relative L2;
the inverse finishes at 0.06128 holdout and exceeds both representation-relative
acceptance allowances. The target-fit control measures this fitting procedure,
not a proven lower bound on network capacity.

The accepted final conversion distance is 0.08071 mm and its refinement change
is 0.000172 mm, both below their limits. The run reaches all 60 updates, so a
terminal conversion/search stall does not explain this case. Three accepted
trials needed more than eight backtracks, but 25 of 60 accepted motions are below
the reporting-only 0.1 mm meaningful-movement floor.

At accepted state 55 the recorded boundary error is 0.9822 mm. It rises to
1.0692 mm by state 60 while training relative L2 falls from 0.002400 to 0.002061.
Training progress therefore does not guarantee geometric progress. This is a
retrospective diagnostic, not a rule for choosing checkpoints using the truth
or holdout. The training/holdout difference alone does not prove overfitting,
because the frequencies differ.

**Suspected causes:** weakly controlled noncircular boundary directions and the
geometry induced by weight-space updates; interaction with regularization is
also open. At state 59, data-gradient norm is 0.08128 and weighted Eikonal-gradient
norm 0.02051. Norms alone do not show alignment or prove that regularization
caused the error. More iterations may lower training loss, but this run does not
establish that they will close the shape or holdout gap.

## Star: separate why it stops from why it is wrong

Within the new run, training relative L2 falls from 1.19593 to 0.48241, but
maximum sampled boundary error falls only from 42.745 to 37.368 mm. The fitted
center moves toward the target; final center error is 7.234 mm. Fitted mean
radius moves from 60.004 to 61.315 mm against a 50 mm target. Fitted lobe amplitude
collapses from 0.11966 to 0.02072 against a target of 0.25. Fitted rotation error
is 0.01691 rad, but phase alone is not evidence of recovered lobes when amplitude
is so small.

The exact-target neural fit achieves 1.191 mm boundary error in the new
configuration, versus 9.182 mm in the old baseline. Representation fitting has
improved while wrong-start recovery has worsened. Insufficient network capacity
alone does not explain the 37 mm inverse error.

The terminal mechanism is directly visible in saved trial records:

- Final accepted conversion distance: **0.144440 mm**, below the 0.2 mm budget.
- Final accepted refinement change: **0.00998257 mm**, at 99.8257% of the 0.01 mm limit.
- At trial iteration 47, all 30 candidates fail. Twenty-nine fail before any
  data loss is evaluated; the remaining one fails motion and both Armijo tests.
- The deepest Adam candidate, backtrack 14, has refinement change **0.01115574 mm**.
  The deepest fallback has **0.01013135 mm**. Both fail the refinement check.
- The last five accepted movements are 0.196658, 0.052824, 0.006695, 0.003340,
  and 0.000836 mm. The final four are below the 0.1 mm reporting floor. The last
  accepted step lowers data loss by only **0.00301%**.

This is a conversion-refinement/search-budget stop, not a demonstrated
stationary point. The recorded final data-gradient norm is still 16.06. A
deeper search might admit a smaller step, but its existence and usefulness at
this new checkpoint have not been tested. Raising the backtrack limit again
would not, by itself, explain or repair the collapsed lobes.

**Suspected causes of wrong geometry:** the nonlinear basin reached from the
changed warm start, weakly controlled boundary directions outside the tested
modal space, and the geometry induced by neural weight updates. The refinement
limit is a confirmed terminal constraint; why its audit becomes limiting along
this trajectory remains open. A frozen-checkpoint resolution/branch audit can
distinguish numerical audit sensitivity from an increasingly hard-to-represent
contour without repeating the entire inverse or relaxing fidelity limits.

## Ellipse: missing run, with a separate frozen initialization diagnostic

The manifest records `failed_inverse`, exit 1. The case folder is empty: there
are no saved metrics, trials, checkpoint, or video. The runner inherits terminal
stdout/stderr and does not persist a per-case log. No saved traceback was found.
Do not claim to know the exact failed line or the failed run's actual fresh
pretrained weights.

A separate cheap geometry-only replay reconstructs the **September 7 archived
initial ellipse weights** and applies the September 8 geometry settings. It
raises `OrderedSDFGeometryError` with both rejection reasons:

| Frozen initial ellipse check | Measured | Limit |
|---|---:|---:|
| Conversion distance | 3.211626 mm | 0.2 mm |
| Conversion refinement change | 0.073997 mm | 0.01 mm |

This probe requires no pretraining, inverse updates, or BEM solve. Its
[script and saved evidence](evidence/02_ellipse_initialization_audit.md)
are separate from the failed production arm. **Inference:** inadequate conversion
of the ellipse warm start at the reused circle settings is a strong candidate
for the startup failure. The missing fresh weights and traceback prevent
claiming the probe reproduced the original exception exactly. The proposal
should first close this evidence gap and validate the initial contour, rather
than schedule another blind 60-update ellipse run.

## Trial rejection accounting

Counts overlap when one trial violates several tested conditions. Conditions
downstream of a geometry rejection are unevaluated, not successful.

| Rejection reason | Circle | Star |
|---|---:|---:|
| Extraction / topology | 0 | 40 |
| Conversion distance | 4 | 97 |
| Conversion refinement change | 0 | 120 |
| Boundary motion | 204 | 168 |
| Data Armijo | 262 | 7 |
| Regularized Armijo | 240 | 7 |
| Nonfinite / solver failure | 0 | 0 |
| Distinct rejected trials | 362 | 372 |

The star's small Armijo counts do not establish a generally good search
direction: 204 of its 419 total trials have no computed loss because geometry
construction rejected first. The 2 mm motion limit, 0.2 mm conversion-distance
limit, and 0.01 mm refinement-change limit were fixed throughout the September 8
runs.

## Prior measured context included in this iteration

The [completed A–E report](evidence/01_prior_controls_and_observability.md)
constrains the next proposal:

- The five-parameter star recovers at 0.5/1.5 GHz with either eight or twelve
  paired views, to approximately 0.0387 mm sampled boundary error. This is a
  strong shape prior and is not full-MLP recovery.
- Both paired acquisitions have full rank in the tested 21 local normal modes
  (arc-length modes 0–10) at the stacked original band and tested geometries.
  Therefore the claim that these lobes are simply absent from the data is not
  supported. Higher modes and nonlinear neural recovery remain untested.
- Multistatic-8 improves local conditioning. At the target, modal condition
  number is about 10.4 versus 73.6 for paired-8. Absolute and target-relative
  sensitivities have different scalings; not every normalized sensitivity
  improves. A proposal must specify data normalization and its balance with
  the unchanged Eikonal penalty.
- In multistatic diagnostics, switching 0.5/1.5 to 1.5/2.5 GHz raises the smallest
  target-relative modal singular value by about 4.83 times. This motivates a
  separate frequency hypothesis, not a conclusion that higher frequency is
  categorically required.
- Three target-fit MLP updates improve train and 3 GHz evaluation errors while
  sampled boundary error changes from 1.191 to 1.290 mm. That establishes a short
  usable local descent neighborhood, not long-term stability.
- Indexed multistatic forward/adjoint support is implemented and checked, but
  the production neural inverse still uses paired readout. This suite did not
  run the proposed multistatic neural acquisition ablation.

For 12 paired views and two frequencies there are 48 real residual entries
against 8,577 weights. This bounds neural data-Jacobian rank; it does not prove
that every parameter null direction moves the boundary. The A–E study used a
separate validated 3 GHz evaluation set. Do not compare its holdout numbers
directly with this suite's historical frequency sets, or reuse evaluation
frequencies for training while continuing to call them held out.

## Questions for the proposal and review

| Question | Current evidence | What remains to establish cheaply |
|---|---|---|
| Why is the ellipse arm missing? | Exit 1, no bundle; frozen old initialization fails conversion badly | Actual startup exception and whether the intended warm start passes a resolved, unchanged-tolerance conversion audit |
| Why does star stop? | Terminal refinement rejection of both searched directions | Frozen final-state resolution and branch behavior; any valid proposed movement and whether it is meaningful |
| Why do star lobes collapse? | Amplitude moves away from truth despite loss descent and a much better target-fit control | Boundary modes induced by accepted neural updates; distinguish basin, acquisition conditioning, and update geometry |
| Why does circle retain about 1 mm error? | Placement is accurate; sampled shape error and evaluation gap remain | Whether the proposed change controls the remaining boundary directions without degrading resolved conversion |
| Which acquisition should a costly run test? | Existing local diagnostics support multistatic as a candidate | A reviewed integration and scaling plan, bounded validation, fixed initialization, disjoint evaluation set, and comparable work budget |
| Why are the runs expensive? | Hundreds of re-extraction/conversion attempts and about 128 minutes recorded | Profile the relevant path before assigning all cost to BEM or increasing every resolution globally |

The local [possible-fixes note](02_possible_fixes.md) develops these handoff
questions into candidate actions. ChatGPT's guide should rank
a small number of discriminating checks, then state which outcomes justify
implementation and a long inverse. Codex will review that proposal before the
user agrees to iteration 3. Do not enlarge the network, relax the fidelity
contract, switch geometry ownership, or repeatedly extend long-run budgets
without evidence and a reviewed reason.

## Evidence index

- [Suite manifest and executed commands](../../../../results/inverse/implicit_mlp/2026-09-08/wrong_start_suite.json)
- Current circle: [summary](../../../../results/inverse/implicit_mlp/2026-09-08/circle/summary.md),
  [metrics](../../../../results/inverse/implicit_mlp/2026-09-08/circle/metrics.json),
  [accepted states](../../../../results/inverse/implicit_mlp/2026-09-08/circle/kress_accepted_iterates.json),
  [trials](../../../../results/inverse/implicit_mlp/2026-09-08/circle/kress_trials.jsonl),
  [video](../../../../results/inverse/implicit_mlp/2026-09-08/circle/contour_evolution.mp4).
- Current star: [summary](../../../../results/inverse/implicit_mlp/2026-09-08/star/summary.md),
  [metrics](../../../../results/inverse/implicit_mlp/2026-09-08/star/metrics.json),
  [accepted states](../../../../results/inverse/implicit_mlp/2026-09-08/star/kress_accepted_iterates.json),
  [trials](../../../../results/inverse/implicit_mlp/2026-09-08/star/kress_trials.jsonl),
  [video](../../../../results/inverse/implicit_mlp/2026-09-08/star/contour_evolution.mp4).
- September 7 baselines: [circle](../../../../results/inverse/implicit_mlp/2026-09-07/circle/summary.md),
  [ellipse-to-circle](../../../../results/inverse/implicit_mlp/2026-09-07/ellipse-to-circle/summary.md),
  [star](../../../../results/inverse/implicit_mlp/2026-09-07/star/summary.md).
- [Full prior controls and observability report](evidence/01_prior_controls_and_observability.md).

Binary artifacts and some large arrays follow the repository's ignore policy.
Their local existence is verified here; a source-only checkout may not contain
the videos or checkpoints. No production code was changed and no new long
inverse was launched to prepare this report.
