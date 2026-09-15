# TOP-018 — one resolution qualification and a matched two-star continuation

Prepared 2026-09-15. Consolidates the
[TOP-017 review](02_proposals/01_TOP017_review_and_resolution_decision.md).

## Status and authority

- **Approval status:** APPROVED
- **Execution status:** COMPLETE — numerical campaign and artifact closeout under
  `results/validation/topology/TOP-018-20260915-resolution-qualified-pair/`
- **Owner:** Codex `/root`. **Reviewer:** owner source/artifact review;
  no independent-agent review assigned or claimed.
- **Approval record:** 2026-09-15, the user replied “yesh” to the explicit request
  to approve TOP-018's audit and conditional two-arm run, capped at 14,256 solves.
  This approves the full conditional contract below and its local commit, with
  no branch/worktree creation or push.
- **Measured source:** `9bde9d1`; 87 pre-dispatch mocked/geometry tests passed.
  [Implementation review](../../../../experiments/top018/implementation_review.md).
- **Closeout:** [iteration 12](../iteration_12/01_results.md). Phase A passed
  (86 new solves); both 256/512 schedules completed and qualified. Final F
  recovers, S fails the recovery gates. Total 8,336 completed solves, zero failed.
  A post-schedule metadata type error was repaired from saved artifacts with
  original worker failures retained; 89 final tests pass. Numerical work was
  not repeated. The result bundle records measured and reporting source hashes.
- **Reviewed source:** `243fe19a7937dd519c4a55bc3e04d464ee04d2a4` on
  `feature/ordered-boundary-nystrom`.
- **Default checkout:** `/home/drdeng/Neural_SDF_BEM_AD`, the existing branch.
- **Scope when approved:** one mechanical preflight/review, Phase A saved-state
  numerical qualification, conditional Phase B consisting of two two-star
  trials, tests, and closeout.
- **Excluded:** central reruns, new observations, oracle generation, new
  sensitivity surveys, new local controls, merge inversions, K changes,
  optimizer/derivative mathematics changes, topology-policy changes, new BIE or
  quadrature methods, adaptive resolution, a twelve-scene suite, and successors.

Record the actual user's approval and actual assignments before numerical work.
An approval of this ID authorizes its conditional phases, not additional Git
branches or worktrees. Root `AGENTS.md` explicitly requires separate direct user
permission for those creations. Use the existing checkout instead. No push or
merge is authorized by this document.

**Installation review, 2026-09-15:** the package is installed and reviewed at
`c2a1f2203e2ed6188b5841027dae8853a3035e0e`. The [current-checkout
review](02_proposals/02_TOP018_current_checkout_review.md) reconciles the later
engineering follow-up: three audit states already have verified 128/256/512
predictions eligible for §A2 reuse, and a separate fresh central recovery is
recorded. COMMON qualification and the prescribed derivative checks remain
pending. Codex `/root` performed the installation/source review; no independent
review or execution was claimed at installation. The later approval above
releases implementation and the conditional numerical contract.

If HEAD has advanced, review the intervening changes, retain the reviewed SHA as
provenance, and pin the actual measured source. Preserve unrelated user edits.
Check that TOP-018 and these destination paths are unused. Do not overwrite a
concurrent plan, change experiment IDs silently, or restore deleted branches.

New documents belong in iteration 11. Executed results, including a negative or
inconclusive closeout, open `iteration_12/01_results.md`. Do not create invented
results or revise TOP-017's executed contract.

## 1. Question and hypothesis

**Question:** With the existing numerical tolerances preserved, does one finer
forward discretization qualify the saved two-star states and allow a matched
S/F continuation to determine the remaining recovery result?

**Hypothesis:** At these geometries the 128/256 obstruction is resolved by
256/512; the existing continuation can then be tested without numerical
under-resolution preventing the prescribed frequency exposure.

Qualification and recovery are separate outcomes. A successful audit does not
predict inversion success. An audit or runtime numerical failure is not a
negative test of the frequency-recovery hypothesis. A completed inverse that
fails the geometry gates is not automatically a solver error.

Central F's existing recovery remains a positive result whatever happens here.
TOP-016's merge regression also remains in the evidence. This ID cannot promote
the production controller or establish automatic count recovery.

## 2. Freeze the model and inputs

Let `B` be:

`results/validation/topology/TOP-017-20260914-staged-continuation/`

### Primary paired start

Use **`B/inputs/far-two-stars/state.json`** for both arms. Verify it equals the
retained TOP-016 common stage-1 endpoint used to initialize both TOP-017 arms.
Check against `B/reuse.json`, both TOP-017 run initial states and, as needed, the
TOP-016 `runs/S-far-two-stars/metrics.json::final_state` and matching F record.
Save source-file and normalized-state hashes, component IDs and coefficients.

Do not instead start S and F from their different TOP-017 stopped endpoints.
Those endpoints have different optimization histories and are diagnostic inputs,
not matched primary starts. Do not replay TOP-016's common low-frequency stage.

Reuse exactly:

- `B/inputs/far-two-stars/training_observations.json` (24 pairs, four frequencies);
- `B/inputs/far-two-stars/observations.json` (original 0.5-GHz and evaluation data);
- `B/inputs/far-two-stars/optimizer.json`, `B/contract.json`, `B/scene_spec.json`,
  material/solve settings and the relevant historical manifests.

Verify acquisition positions, source strengths, materials, frequency ordering,
observation hashes and original-frequency column identity. Do not regenerate
observations to match a changed discretization. Missing/inconsistent primary
inputs stop preflight, rather than releasing a substitute start.

### Unchanged scientific machinery

Keep the homogeneous full-space 2D TMz model, two component IDs, **Cartesian
K=9 per component**, existing polar-angle gauge, finite-difference LM,
feasible-side stencil, material constants, physical clearance/radius floors,
and existing residual normalization. Changing quadrature node count must not
change Fourier coefficients or the intended continuous boundary.

The **only deliberate numerical comparison change from TOP-017** is the common
production/refined pair **256/512 nodes per component**, conditional on Phase A.
Both S and F use it throughout. Discrete feasibility checks are reevaluated at
those resolutions under the same physical rules; report changes in their
outcomes, rather than pretending the discretized feasible sets are identical.

Because denser solves cost more, the per-trial wall ceiling is increased from
1,800 to 7,200 seconds. Solve quotas and optimizer iteration limits are unchanged.
This is declared compute accommodation, not a speed comparison with TOP-017.

## 3. Phase A — saved-state qualification, at most 256 solves

### A0. Mechanical review and tests

Read `AGENTS.md`, the iteration workflow, implementation principles, the
TOP-017 staged-execution amendment, this review/plan and TOP-017 closeout.
Write one short API/file map. Resolve implementation risks in one review,
preferably by a second read-only agent. Do not invent an independent review.

Inspect `run_top017.py`, particularly `fit_stage`, `run_schedule`, `Ledger`,
`observations` and the existing scorer. Prefer reusing tested functions in a
small TOP-018 wrapper. Do not call the TOP-017 campaign entrypoint: it would run
excluded central/control work and use its historical assumptions. Do not
monkey-patch historical node constants and thereby alter an old experiment.

The original input-freezing helper has experiment-specific source assumptions;
reuse only parts that remain valid. New manifests should hash the actual
resolved sources and inputs, not fail merely because a TOP-018 wrapper exists.

Add mocked/geometry tests before physical dispatch:

1. Phase-A failure dispatches no inverse; pass dispatches only the two approved
   two-star arms.
2. Both arms use coefficient-identical common starts and 256/512 throughout.
   No cached 128-node residual, derivative or density is reused at 256 nodes.
3. Quota-limited valid stages can advance; hard trial limits, unresolved
   derivatives and numerical/physical failures cannot.
4. S fits only 0.5 GHz; F fits the prescribed cumulative sets. Evaluation scoring
   is excluded from effective training exposure.
5. Candidate rejection leaves the accepted checkpoint intact, and score and
   gradient records carry exact state, objective and resolution associations.
6. The next complete Jacobian/step batch and endpoint reserve fit before work
   starts; all accounting includes rejected, derivative and scoring work.
7. Historical drivers and numerical defaults remain unchanged.

One writer owns numerical changes. Freeze the measured source before numerical
workers launch. Reviewers use read-only access; workers use separate result
folders, not extra Git worktrees.

### A1. Recover the fixed audit states

Use only this predetermined list:

| Label | Source and purpose |
|---|---|
| COMMON | `B/inputs/far-two-stars/state.json`; primary paired start |
| F_RETAINED | `B/runs/F-far-two-stars/stage_2/terminal.json::final_state`; verify against its accepted checkpoint |
| S_ENDPOINT | `B/runs/S-far-two-stars/stage_3/terminal.json::final_state`; the numerically unqualified scored endpoint |
| F_REJECTED | The candidate flagged `numerical_obstruction` in F stage-2 `acceptance.json`; audit only |

For F_REJECTED, inspect what is actually stored. Where only a candidate hash is
saved, reconstruct through the exact historical state/step/gauge path using
`candidate_attempts.jsonl` and its matched base trajectory. Require its recorded
candidate hash to match. Do not guess from the last array or run an inverse to
recreate it. If exact reconstruction is unavailable, record `NOT_RECOVERABLE`
and audit the other three states. This absence is not license for a substitute
candidate. A recovered rejected candidate is never an inverse initialization.

### A2. Evaluate the same geometry at N=128, 256, 512

For each available audit state, evaluate the six fixed frequencies at each node
count: **0.5, 0.75, 1.0, 1.25, 1.5, 2.5 GHz**. Reuse an existing prediction only
if its complete state, material, acquisition, source and numerical configuration
are known identical; otherwise count the new call. Up to four states require
at most 72 frequency solves for this base table.

Measure per-frequency prediction differences between 128/256 and 256/512 using
the exact existing discrepancy normalization. If written mathematically as
`eta_f(N,2N) = ||P_f,N(c)-P_f,2N(c)||_2 / ||P_f,2N(c)||_2`, verify that this is
indeed the helper's implemented denominator/axis convention. Here `c` is the
unchanged real coefficient vector and `P_f,N` is its complex paired prediction.
Handle zero/nonfinite denominators as explicit numerical obstructions.

Preserve thresholds: **1e-7 at 0.75/1.0/1.25 GHz**, and **1e-5 at 0.5/1.5/2.5
GHz**. Report all six columns, contraction ratios and distance to thresholds;
do not collapse them into a pass flag alone. Verify gauge, physical geometry and
feasibility at the relevant resolutions. When reproducible, compare the old
128/256 discrepancies with the saved obstruction values.

Separate base/candidate objective gains at both resolutions for the exact saved
F base/candidate pair, using its stage-2 training objective and existing
acceptance rule. Report whether the old numerical rejection persists and
whether the candidate would otherwise qualify. This is an audit, not permission
to commit that candidate.

No new truth projection, frequency selection or geometric-accuracy threshold
calibration occurs here. This table measures discretization, not recovery.

### A3. Minimal derivative sanity check

At COMMON, use two predetermined rows of the existing reduced gauge tangent
basis: the first and last rows in its recorded deterministic ordering. Verify
both are physically nontrivial. Check their feasible directional residual
estimates at the inherited FD step and half-step, at both 256 and 512 nodes,
using the complete four-frequency training residual. Reuse the existing
feasible-side estimator and its qualified stability criterion; record refusals
rather than zeroing them. Do not assemble a full spectrum or search for more
favorable directions.

Record residual ordering/scaling, numerical floor and stencil. A floor-limited
or inconsistent check is an obstruction to this release, not evidence of zero
sensitivity. No derivative-method repair is authorized here. Cache only exact
state/configuration matches and count every physical call. For two central
stencils, this probe is roughly 72 additional solves including shared bases;
the 256 cap remains authoritative if feasible-side details cost more.

### A4. Binding release gate

Release Phase B only when all required inputs/tests pass and:

- COMMON, F_RETAINED and S_ENDPOINT qualify at **256/512** at all six frequencies
  under the unchanged tolerances and are feasible under the unchanged rules;
- F_REJECTED, if exactly recoverable and physically admissible, also qualifies
  numerically at 256/512; otherwise preserve the missing/inadmissible status and
  do not claim that particular rejection has been explained;
- the directional derivative check meets the inherited numerical criterion;
- there is no unresolved shared source/data/model inconsistency.

Use a fail if an available, admissible F_REJECTED still fails the finer numerical
check. An unavailable candidate does not alone block release when all retained
states qualify, but narrows the conclusion about the specific rejected trial.

A fail/inconclusive Phase A ends TOP-018 with its audit. **No 512/1024 fallback,
relaxed tolerance, adaptive meshing or main trial is released.** Do not spend the
remaining budget simply because it exists.

## 4. Phase B — one matched higher-resolution pair

Run exactly **two trials**, S and F, on far-two-stars from COMMON. This repeats
only the affected comparison at a deliberately different resolution; it does
not relabel older work as unfinished iterations at the same fidelity.

| Stage | S training GHz | F training GHz | Per-arm frequency-solve quota |
|---|---|---|---:|
| 2 | 0.5 | 0.5, 0.75 | 1,250 |
| 3 | 0.5 | 0.5, 0.75, 1.0 | 1,750 |
| 4 | 0.5 | 0.5, 0.75, 1.0, 1.25 | 4,000 |

Use 256/512 for both arms, including refined feasibility and validation. Retain
identical optimizer reset/warm-start conventions and all inherited iteration,
step, gradient, damping and line-search limits. No stage 1, alternate seed,
restart search, quota borrowing or bandwidth promotion.

The residual/objective remains

\[
r_A(c)=|A|^{-1/2}\operatorname{stack}_{f\in A}
 [\Re((P_{f,256}(c)-d_f)/\|d_f\|_2),
  \Im((P_{f,256}(c)-d_f)/\|d_f\|_2)],\qquad
\Phi_A(c)=\tfrac12\|r_A(c)\|_2^2.
\]

`A` is the stage's active training-frequency set; `d_f` is the unchanged
24-pair observed complex vector; `c` is the retained real Fourier coefficient
vector. Use the established reduced-coordinate derivative path. The 512-node
objective uses the same scaling for candidate validation. Neither truth geometry
nor evaluation observations are arguments to the fitting function.

Keep objective target **1e-14**, disabled absolute loss-change stopping,
absolute acceptance margin **1e-14**, relative margin **1e-8**, and the existing
factor-5 production/refined loss-gain disagreement allowance. No outer 0.003
`recovered` early return. Do not reduce the margins because the finer mesh has
changed objective values. Report a margin-limited stop as such.

The intended invariant is better numerical resolution, not a new reconstruction
method. Any need to change the optimizer mathematics, geometry owner, physical
solver or inherited tolerances is outside scope.

## 5. Stage transitions, safety and exposure

Reuse TOP-017's typed distinction:

- A normal optimizer return or planned stage quota permits transition only from
  a feasible, qualified accepted endpoint with a completed usable model.
- Whole-trial solve/wall limits, numerical failure, failed physical solve,
  invalid retained geometry, unresolved derivative or unexpected exception
  hard-stop the affected trial. Never treat these as quota transitions.
- A quota that cannot fund a complete current Jacobian and a candidate/validation
  opportunity is an exposure/configuration obstruction, not a completed stage.

Reserve **12 frequency solves** for the six-frequency, two-resolution endpoint
score before consuming a stage quota. At q=34 reduced directions, an m-frequency
central-difference Jacobian costs about `2*q*m`; use the actual callback's
conservative reservation, not this estimate, for dispatch.

Score every predetermined accepted stage endpoint. Numerically qualify all six
frequencies, including unfitted ones, using the unchanged contract. Preserve
that S's checks at added frequencies are endpoint audits, not optimizer exposure.
If a numerical hard stop occurs inside fitting, save the retained state and
reason immediately; score it for reporting only when safely affordable from the
reserved work, and never use that reporting score to restart or release a later
stage. Missing or unqualified scores remain explicit.

Do not stop the companion arm based on unfavorable truth/evaluation scores.
Independent numeric/resource stops may leave one arm complete and the pair
incomplete. Do not claim a completed matched comparison then.

Log active frequencies, complete Jacobian batches, candidate attempts,
acceptance validation, accepted states and exact stop reasons. Gradients require
matching state, objective and resolution hashes. Never borrow an old gradient
for a new endpoint or run an extra terminal Jacobian merely to fill a table.

## 6. Budgets and concurrency

| Work | Attempted frequency-solve cap | Numerical wall ceiling |
|---|---:|---:|
| Phase A, including all prediction/derivative checks | 256 | 900 seconds |
| Phase B S | 7,000; stage quotas above | 7,200 seconds |
| Phase B F | 7,000; stage quotas above | 7,200 seconds |
| Entire authorized numerical campaign | 14,256 | 15,300 seconds |

These are ceilings, not spending targets or runtime predictions. At most two
read-only numerical workers may share the frozen source, using separate output
folders and single-thread BLAS. Report campaign elapsed separately from summed
worker time. The outer cap also supports sequential execution; do not reset it
when workers or stages change.

A hard cap cannot be extended under this ID. Account for attempted, completed
and failed physical frequency solves by category and frequency, including all
initial, derivative, rejected-candidate, refined-validation and scoring work.
Audit any interruption; report lower bounds where necessary. No hidden warmup or
uncounted diagnostic solve. Mocked/geometry-only tests are identified separately.

## 7. Required scorecard and interpretation

Report side by side:

- common-start, every retained stage and predetermined stage-4 geometry in mm;
- material IoU, original 0.5-GHz fit, each added training frequency, each
  1.5/2.5-GHz development-evaluation error, and the current aggregate objective;
- unchanged predicates: boundary <=1 mm, IoU >=0.90, refined original-training
  error <=0.003, worst evaluation error <=0.05; the fixed count is not newly
  recovered;
- stage exposure, numerical qualification, configured convergence, actual stop,
  attempts/acceptances, work and wall time as separate fields.

Do not compare changing aggregate objectives as one monotone sequence. Retain
common-frequency scores and within-stage gains. Do not select the best stage.
Keep a small separate row for the already-qualified TOP-017 central result,
clearly marked reused evidence at its historical resolution, not a new run.

Decisions:

| Result | Defensible conclusion / next decision |
|---|---|
| Phase A fails | Resolution not qualified by this bounded test. Do not run inverses or infer frequency-recovery failure |
| Runtime qualification or budget fails | Retain partial evidence; paired question remains unresolved at that obstruction |
| Both schedules qualify; F passes original gates and S does not | Successful two-star fixed-count recovery under F relative to this matched S control |
| Both pass | Both methods recover under these settings; frequency diversity was not shown necessary by this comparison |
| F improves geometry/prediction but still fails gates | Partial reconstruction benefit, not recovery or production promotion |
| Qualified complete F is no better or regresses | This finer-resolution cumulative protocol has no demonstrated advantage on this case; do not call all multifrequency inversion ineffective |

Regardless of outcome, no full suite, new merge inverse, adaptive scheme or
successor starts automatically. Even a new two-star success does not resolve
TOP-016's merge regression or demonstrate the fresh automatic count/shape
pipeline. Select one justified next experiment in closeout, rather than an
unbounded diagnostic tree.

## 8. Artifacts and closeout

Use a fresh directory:

`results/validation/topology/TOP-018-<actual-run-date>-resolution-qualified-pair/`

Required contents: README, frozen contract and source/input manifest, exact
commands/environment, Phase-A resolution table and state associations,
derivative checks, both arm histories, retained states, available diagnostics,
scorecard, physical-solve ledger, and the actual review record. A summary must
be rebuildable from saved artifacts without new physical work.

Save serialized rejected candidates in this new experiment as well as their
hashes when they cause a numerical failure; this is logging, not a change in
acceptance. Cache identity includes geometry, frequency/acquisition/materials,
node count, solver config and relevant source. Geometry preservation can be
tested without a physical solve.

After completion update the dashboard, topology handoff and results catalogue
with links rather than duplicate large tables. Open iteration 12 with the
measured answer and explicit limitations. Keep old bundles and iteration-11
`01_results.md` unchanged. Record actual approval/execution status here and in
the handoff; do not manufacture a reviewer, run or test result.

The package's user prompt authorizes committing validated task work on the
existing branch. It does not authorize push, merge, branch deletion, or creation
of a branch/worktree. Follow current root `AGENTS.md` for repository operations.
