# TOP-016 — isolate fixed-topology recovery before changing the controller

Prepared 2026-09-14. Consolidates [the recovery-reset review](02_proposals/04_recovery_reset_review.md).

## Status and authority

- **Approval status:** APPROVED
- **Execution status:** COMPLETE
- **Owner:** Codex `/root`. **Reviewer:** independent Codex `/root/top016_review` (preflight/implementation) and `/root/top016_closeout_review` (read-only closeout).
- **Reviewed source:** `feature/ordered-boundary-nystrom`, commit `9acae6bac060e84704d938e9a1e63407971841e7`.
- **Working branch after approval:** `track/topology-TOP-016`, in its own worktree.
- **Scope of approval when granted:** documentation reconciliation, implementation preflight, numerical/sensitivity screening, the paired fixed-topology pilot, the explicitly bounded local control, and closeout. It does **not** include a new topology policy, optimizer redesign, or a twelve-scene qualification run.

A file named `03_plan.md` does not grant approval. Record the actual user's approval of TOP-016 in this block and the track handoff before numerical implementation or execution. The accompanying handoff prompt provides a way for the user to approve this exact scope once. Passed scientific gates within this scope do not require repeated approval.

If the local branch has advanced, inspect the intervening changes first. Retain this review revision as provenance, pin the actual execution revision, and verify that TOP-016 and the proposed file paths have not already been used. Do not overwrite a concurrent agent's plan or run.

Approval recorded 2026-09-14: the user instructed “a zip is in place. git pull, then put it in its places. then do as it sayd”. This adopts the archive’s copy-paste TOP-016 approval and shared principles as equivalent execution instructions. Scope and conditional budgets remain exactly as packaged. Execution base: `d3bbdae`; the only change after reviewed `9acae6b` is the handoff archive. Local commit is authorized by the adopted handoff; push and merge are not.

Execution closed 2026-09-14: information screens passed; principal/local arms stopped at stage-1 budgets; completed F-merge introduced a geometric failure. **No promotion.** [Iteration-10 results](../iteration_10/01_results.md) and [bundle](../../../../results/validation/topology/TOP-016-20260914-fixed-topology/README.md) retain the measured answer and diagnostic limits.

## 1. Question, hypothesis and limits

**Question:** With component count fixed, does a bounded frequency-continuation protocol improve difficult Fourier-boundary reconstructions relative to a matched single-frequency continuation?

**Hypothesis:** The added frequencies constrain relevant shape directions more strongly and improve reconstruction, rather than merely reducing a different training objective.

A negative, mixed or inconclusive answer is a valid closeout. This experiment does not establish global identifiability, globally optimal inversion, automatic component-count recovery, or generalization. It tests a particular acquisition/continuation package, not the isolated effect of frequency diversity independently of continuation.

The motivation and primary references are in the review, especially [L1]–[L4]. The frequencies, thresholds and budgets below are predeclared project choices, not literature guarantees.

## 2. Fixed scope

Retain the homogeneous full-space 2D TMz transmission model, materials, paired acquisition geometry, Cartesian Fourier chart with its current gauge, Müller/Kress forward, existing finite-difference LM algorithm, and qualified feasibility checks.

Use the refined-feasibility treatment and feasible-side finite differences already available. Inspect their actual configuration fields rather than inventing new flag names. Hold their enabled state fixed across both arms.

No MLP, new TD formula, birth/death/split/merge rule, candidate selector, curvature optimizer, new shape prior, adaptive bandwidth algorithm, BIE formulation, adjoint implementation, or generic experiment framework is included.

The main pilot runs the **fixed-topology refinement path**, not a controller call that immediately exits on `recovered`. Component IDs and counts remain unchanged throughout each trial. Counts supplied by saved states are part of this diagnostic and are not advertised as newly inferred counts.

## 3. Inputs and common representation

Use these inputs, selected in advance rather than after inspecting trial outcomes:

| Role | Scene and initial state |
|---|---|
| Principal shape case A | `far-two-stars`: the last **retained** restart plateau in TOP-010, not a rejected final restart trial |
| Principal shape case B | `central-ellipse-star`: the completed final arm-H state from TOP-008 |
| Prediction control | `merge`: the completed final arm-H state from TOP-008 |

TOP-008's per-scene table documents correct counts for these selected cases. TOP-010's plateau is the saved high-bandwidth two-star diagnostic. Record exact JSON paths, field names, component IDs, coefficient arrays and file hashes in the new manifest. Prefer portable saved JSON to untracked binary files. A missing or non-reproducible input is a preflight obstruction; do not silently substitute a more successful state or rerun an entire historical experiment.

Set a common **Cartesian maximum mode K = 9 per component**. Zero-pad lower-bandwidth saved curves without changing their physical boundaries, IDs, gauge or parameterization. Do not truncate a higher-bandwidth input to force compliance. Verify boundary preservation to 1e-10 m or tighter on a dense independent parameter grid and verify predictions agree at the numerical comparison accuracy.

Perform a separate, evaluation-only representation audit: can this fixed chart/cap approximate each principal truth within **0.1 mm matched boundary error** while respecting the same feasible set? This is not an inversion or an admissible truth-assisted initialization for the main trials. If this audit fails, stop with a representation obstruction; do not increase K during this experiment.

Reuse the original **24-pair, 0.5 GHz** observations byte-for-byte. New training data use the same physical model and source/receiver positions. Do not use the 48-pair v2 configuration.

Create a fresh experiment-only specification, for example `config/topology_TOP016_fixed_topology_pilot.json`, and a frozen copy in the result bundle. Do not edit either frozen topology benchmark specification.

## 4. The two arms

| Stage | S: single-frequency control | F: cumulative frequency continuation | Forward-frequency solve cap per arm |
|---|---|---|---:|
| 1 | 0.5 GHz | 0.5 GHz | 1,000 |
| 2 | 0.5 GHz | 0.5, 0.75 GHz | 1,250 |
| 3 | 0.5 GHz | 0.5, 0.75, 1.0 GHz | 1,750 |
| 4 | 0.5 GHz | 0.5, 0.75, 1.0, 1.25 GHz | 4,000 |

Both arms have four predetermined stages, the same initial coefficients, coefficient cap, optimizer settings, reset/warm-start convention and total work ceiling. Warm-start geometry from the previous accepted stage. Reset optimizer internal state identically at each stage; do not add opportunistic restarts. An early convergence leaves budget unused; unused stage allocations do not automatically expand later stages.

F uses cumulative data so earlier fitted information remains in its objective. This is a declared variant inspired by recursive linearization, not an exact reproduction of the single-frequency-at-each-step algorithms in the cited papers.

**1.5 and 2.5 GHz remain evaluation-only.** Neither their observations nor truth geometry may be passed to the optimizer. Evaluate the predetermined accepted endpoint of each stage; never select the best iterate, direction, step, frequency or restart using those scores.

For an active frequency set A, use the dimensionless residual convention

\[
r_A(c)=\frac{1}{\sqrt{|A|}}\operatorname{stack}_{f\in A}
\left[\operatorname{Re}\frac{F_f(c)-d_f}{\|d_f\|_2},\;
\operatorname{Im}\frac{F_f(c)-d_f}{\|d_f\|_2}\right],
\qquad \Phi_A(c)=\tfrac12\|r_A(c)\|_2^2.
\]

Here `c` contains the real Fourier coefficients in the retained reduced coordinates; `F_f(c)` is the complex predicted 24-pair scattered-data vector at frequency `f`; `d_f` is its observed counterpart; `|A|` is the number of active frequencies; and `stack` concatenates real vectors. Each frequency receives equal weight in mean squared relative error. A zero or numerically unusable observation norm is an explicit failure, not an invitation to choose a favourable normalization.

Verify the existing residual builder's ordering and scaling. Adapt the experiment wrapper consistently if needed; differentiate the same scaled residual that is actually minimized. Record per-frequency errors in addition to the aggregate. The S objective is the same at all four stages; F's aggregate objective changes when A changes. Do not assert aggregate-loss monotonicity across those transitions.

## 5. Common stopping and acceptance configuration

TOP-010 already found scale-dependent early stopping. A comparison that leaves the single-frequency control unable to move for that reason would not isolate the proposed intervention.

Use one **opt-in diagnostic configuration** in both arms. With the objective convention above, request:

- absolute objective target: **1e-14**;
- absolute loss-change stopping: **disabled**, not reported as stationarity;
- absolute acceptance margin: **1e-14**;
- relative acceptance margin: **1e-8**;
- gradient, step, damping, backtracking and geometric trust-region settings: inherited unchanged from the selected fixed-topology reference configuration and recorded explicitly;
- no outer `relative_error_tolerance = 0.003` early return in the pilot.

These values are diagnostic settings, not proposed controller defaults. Map them to the real source interface during preflight; do not guess that assigning zero disables an option. A small backwards-compatible option to separate loss-target and loss-change stopping is in scope if the existing API couples them. No replacement optimizer is in scope.

Check that the requested precision is meaningful for the selected discretization, repeated evaluations and derivative probes. Accept a candidate only through the existing geometric validity and cross-resolution checks, with the corresponding scaled margin applied consistently at both resolutions. Assess the numerical reliability of the **loss decrease** at both resolutions, not merely the absolute offset between their losses at one geometry. When disagreement in the measured decreases dominates a proposed gain, reject/report it as unresolved instead of calling it progress. Do not tune these constants against truth or evaluation scores.

If a stable, equivalent configuration cannot be expressed without changing the optimizer algorithm, close preflight with that obstruction. Do not spend this ID on a stopping-rule research programme. At every endpoint record gradient diagnostics, actual stop reason, smallest accepted/rejected gain and which limit bound the run. A margin-limited stop is not stationarity.

## 6. Phase 0 — reconcile, map and validate

Before inverse runs:

1. Read the root `AGENTS.md`, shared iteration workflow, implementation principles, this review/plan, current architecture and the relevant result bundles. Write a compact implementation map and record actual owner/reviewer assignments.
2. Update the dashboard and topology handoff to acknowledge completed TOP-011/012 and active iteration 09. Link the new review instead of rewriting historical measurements. After adoption, add a dated supersession note to TOP-015; leave TOP-013/014 unexecuted.
3. Recover and validate the three input states and their observations, the K=9 zero-padding, physical restrictions, residual normalization and supported stopping options.
4. Generate only the necessary new pilot observations. Check oracle convergence at the added frequencies. Reuse existing evaluation observations unchanged; verify evaluation accuracy rather than assuming a 0.5-GHz discretization suffices at 2.5 GHz.
5. Choose a common training production/refined node pair for S and F from **(64,128), (128,256), (256,512)** per component. Use the smallest pair that passes the existing oracle/resolution checks and yields at most **1e-7 relative prediction discrepancy** at all added training frequencies on the saved pilot states. This selection uses numerical accuracy only, never reconstruction scores. Freeze the pair before the comparison. If none qualifies within budget, stop; do not add another resolution ladder.
6. Verify several reduced Jacobian directions at the new frequencies using the existing feasible-side estimator and two FD scales. Record refused and unresolved probes; never replace them by zero. Run the focused tests for the affected interfaces and default invariance.

Retain run-time refined checks: a start-state convergence check is not a guarantee for every later candidate. If candidates leave the qualified numerical regime, stop/report the numerical obstruction; do not silently change discretization in only one arm.

The reviewer resolves material implementation risks once. Mechanical API mapping, logging and correctness repairs within this scope do not require a new research plan. Any scientifically material amendment must be documented **before** looking at the trial outcomes; any scope expansion requires separate user approval.

## 7. Phase 1 — a cheap, binding information screen

At each principal saved state, compare 0.5 GHz against the complete proposed F training set before running the expensive pilot.

Use the existing reduced-Jacobian SVD at 0.5 GHz. Fix the **eight weakest physically nontrivial directions** in their original order. Do not choose directions against truth or recompute a more favourable list separately for F. If fewer than eight directions exist, use all and record the count.

Normalize each direction to approximately **1 mm RMS normal boundary displacement**, integrated with arclength weights over the current boundaries. This is a diagnostic physical scaling, not an optimizer change. Probe both signs at 0.5 mm and 1 mm with both resolutions. Record actual boundary displacement, feasibility, and nonlinear data change relative to the unperturbed prediction. A direction that changes only parameterization is not a physical shape direction; identify it explicitly rather than dividing by nearly zero displacement.

For each direction compute D_S and D_F: the RMS normalized data change across the active frequencies for that physical perturbation, using the same normalization as the objective but subtracting the **base prediction**, not truth data. Report both signs and amplitudes; for the screening summary use their median. Form G = D_F / D_S only when D_S is above the measured numerical floor. Otherwise report a floor-limited bound, not infinity.

**Release Phase 2 only if both principal cases satisfy all of the following:**

- the median G across the usable weak directions is at least **1.5**;
- at least half the usable directions individually have G at least **1.5**, with at least four usable directions;
- the relevant data changes exceed the measured numerical uncertainty by at least a factor of **5**;
- the conclusions are not reversed by the refined discretization or smaller physical probe.

These are operational screening rules, not identifiability theorems. Save the complete spectra, coordinate conventions and per-direction data. Similar singular-value lists alone are not enough. Do not interpret a failed screen as proof that no other acquisition could help.

**A failed or inconclusive screen stops this pilot. No full suite and no extra frequency/angle search follows automatically.** Close out with the measured result.

## 8. Phase 2 — paired recovery pilot

If Phase 1 passes, run S and F on both principal shape cases and the merge prediction control, using the fixed four-stage protocol. Every arm gets the same declared ceilings. Count derivative, refinement, rejected-trial and evaluation work, not just accepted steps.

Save accepted coefficients and terminal diagnostics at each stage. After the training endpoint is fixed, score it with the existing matching, IoU and evaluation-frequency metrics. Keep every stage, including any geometric deterioration; do not select a favourable rung as the final answer.

### A bounded local control, only if needed

If neither main arm produces a qualifying principal-case reconstruction, run at most **two** additional diagnostic trials, S and F, on `far-two-stars` initialized from its representable truth translated by **(+2 mm, -1 mm)** for every component. Leave all other coefficients unchanged. Check feasibility without searching for a better perturbation.

This is explicitly a **truth-assisted local-recovery control** and never counts as an automatic reconstruction. It tests local recoverability using the same model; it is not evidence of robustness to poor initialization. Each trial has a separate **2,000-frequency-solve / 600-second** ceiling, with stage allocation **250, 350, 500, 900**. No other near-truth seeds or restart search are authorized.

### Scorecard

Report initial and final values, stage histories and arm differences for:

- fixed component count and all feasibility/resolution failures;
- matched boundary error in mm and material-union IoU;
- original 0.5-GHz relative error, every newly fitted frequency error, and the aggregate;
- 1.5- and 2.5-GHz evaluation errors separately and their maximum;
- original gate predicates, without changing their thresholds;
- attempted/completed frequency solves by category, wall time, accepted steps and stop reasons.

For reference, the v1 geometric/prediction gates are **at most 1 mm matched boundary error**, **at least 0.90 IoU**, **at most 0.003 refined original-training error**, and **at most 0.05 worst evaluation-frequency error**. Report new-frequency fit additionally; do not label the pilot as a v1 benchmark pass.

## 9. Budgets and termination

| Work | Attempted forward-frequency solve ceiling | Wall-clock ceiling |
|---|---:|---:|
| Phases 0 and 1 combined, including new oracle/validation work | 5,000 total | 1,200 seconds total |
| Phase 2, each principal or merge arm | 8,000, partitioned as in Section 4 | 1,800 seconds per trial |
| Optional local control, each arm | 2,000 | 600 seconds per trial |

The maximum authorized solve total is **57,000**: 5,000 + six main trials × 8,000 + two local trials × 2,000. This is a ceiling, not a target. Tests that call the physical forward also count. Ordinary non-forward unit tests do not consume the forward-solve allowance.

Use single-thread numerical workers for interpretable per-trial timing. Independent trials may use separate processes/worktrees, but declare concurrency; do not call concurrent elapsed times a controlled speed comparison. A per-trial ceiling applies regardless of concurrency.

Before a Jacobian or validation batch, reserve its known maximum work. Save the latest accepted state before an expensive batch. On any cap, retain partial evidence, write the actual binding limit, and stop that trial. Do not borrow from the other arm or increase a later stage's cap. Never repeat completed runs because a summary was missing; rebuild the summary from artifacts.

## 10. Decisions and the next iteration

Use these predeclared decisions, not “the loss improved, so keep going”:

**Candidate continuation merits a future twelve-scene qualification** only if:

- F reduces matched boundary error by at least **30%** from the common initial state on both principal cases;
- F is at least **20%** better than S in final boundary error on at least one principal case and not worse on the other;
- F does not worsen IoU or worst evaluation error relative to the initial state on either principal case, improves worst evaluation error by at least **20%** on each, and the merge control does not acquire a new geometric failure;
- at least one previously failing principal case satisfies the original geometric and prediction thresholds listed above;
- the improvement survives the numerical checks and is not based on a timeout, an unretained iterate, a truth-selected step, or unequal undeclared work.

These are promotion criteria, not claims that a smaller improvement has no scientific value. Report mixed improvements even when promotion fails.

**If S also reaches the same recovery standard without an appreciable F advantage:** prefer the simpler acquisition as the next qualification candidate. The need for richer data has not been established.

**If the data screen improves but neither arm recovers:** use the numerical, terminal and local-control evidence to propose the next continuous-inverse diagnostic. Do not assert a unique cause or automatically run TOP-013.

**If the screen fails or a budget/numerical obstruction intervenes:** close this particular protocol with its limitation. Do not widen the acquisition or restart search within TOP-016.

Any outcome opens `iteration_10/01_results.md`. A successful pilot may justify a separately reviewed twelve-scene comparison from the original unknown-count initializations. That suite must compare matched configurations, report every original scene, charge all extra acquisition/optimization work, and distinguish a topology failure from a shape-polishing failure. **It is not authorized by TOP-016.** Do not pre-create a fictitious successful result or reserve an unrelated successor ID now.

## 11. Implementation seams and tests

Inspect and reuse, rather than duplicate:

- `solvers/sdf_inverse/radial_topology.py`: explicit multicomponent state, objective and fixed-topology LM;
- `solvers/sdf_inverse/optimization.py`: finite-difference settings and residual normalization;
- `solvers/sdf_inverse/topology_controller.py`: read to understand inherited policies; no event-policy edits;
- `run_fourier_topology_controller.py` and `run_topology_scene_benchmark.py`: acquisition, scene and portable artifact helpers;
- `solvers/gpr_bem_kress/` and the ordered-boundary interfaces: keep the physical implementation unchanged.

Exact file/API mapping is the implementation owner's task. Prefer one small TOP-016 runner plus focused tests. A limited opt-in configuration extension is allowed; a duplicate optimizer or forward solver is not.

Tests must cover zero-padding invariance, common initial states, fixed IDs/counts, frozen original observations, frequency ordering/normalization, truth/evaluation-data exclusion, correct stopping-option semantics, both-resolution acceptance, stage budget prechecks, exception/timeout artifact retention, and unchanged default behavior. Do not edit hashed numerical sources while trials run.

## 12. Artifacts and closeout

Use a fresh bundle `results/validation/topology/TOP-016-<run-id>/` with, at minimum:

```text
README.md                 question, measured answer, limitations and decision
manifest.json             execution revision, source/input hashes and environment
contract.json             frozen configurations, thresholds, frequencies and budgets
preflight.md              source/API map, review, input and numerical checks
sensitivity.json          physical-direction screen, all signs/amplitudes and failures
runs/                     accepted states, stage metrics and terminal diagnostics
pilot_metrics.json        all main/control outcomes, including missing/failed arms
execution.log             commands, chronology and work counters
```

Include the experiment driver with a clear reproducible command, either alongside the bundle or linked to its committed source. Save enough numeric inputs to reproduce the summary without untracked binary dependencies. Preserve all old bundles byte-for-byte.

On closeout, write iteration 10's results, update the topology handoff and dashboard with one measured decision, and link the bundle from the results catalogue. Keep reusable principles linked from `docs/iterations/README.md`. Do not duplicate the full scorecard in multiple dashboards.

Commit validation and documentation changes on the experiment branch according to the user's actual git instruction. This plan does not authorize a push, merge, deletion of other work, or silent promotion of experimental options to defaults.

**Definition of done:** the bounded comparison has a reproducible result or precisely documented obstruction, an honest scope-qualified conclusion, and one justified next decision. Do not continue automatically into another research cycle.
