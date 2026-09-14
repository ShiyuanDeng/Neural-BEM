# TOP-017 — finish the frequency-exposure comparison from saved states

Prepared 2026-09-14. Read the [TOP-016 review](02_proposals/01_TOP016_review_and_next_steps.md)
and [staged-execution amendment](02_proposals/02_staged_execution_addendum.md).

## Status, authority and placement

- **Approval status:** APPROVED
- **Execution status:** IN PROGRESS
- **Owner:** Codex `/root`. **Reviewer:** Codex `/root/top017_review` (independent, read-only).
- **Reviewed base:** `track/topology-TOP-016` at `9ad3c8b191c7f1130764c0476480290b0f6a6e4a`.
- **Experiment branch after approval:** `track/topology-TOP-017`, separate worktree.
- **Authorized scope when approved:** one implementation preflight, one bounded
  control/input audit, four principal continuation trials, tests and closeout.
- **Not included:** new topology policy, optimizer/derivative redesign, principal
  bandwidth change, new measurements, further local-control or merge inverse
  runs, generalization study, or twelve-scene suite.

Record the actual user's approval, actual execution commit and real assignments
before numerical edits/runs. Creating this file does not grant that approval.
The installation prompt approves these conditional stages once; valid stage
transitions do not require repeated permission. Do not infer approval of any
successor experiment.

These documents belong in **iteration_10**. Execution results open
`iteration_11/01_results.md`; do not create that results file before evidence
exists. Do not change TOP-016's executed plan or overwrite iteration_10's
existing `01_results.md`.

## 1. Scientific question and limits

**Question:** From TOP-016's shared low-frequency endpoints, does the remaining
bounded cumulative-frequency schedule improve fixed-topology geometry and
prediction relative to further single-frequency fitting?

**Hypothesis:** The added local sensitivity measured by TOP-016 yields useful
reconstruction progress once the new data actually enters the optimization.

This tests the remaining acquisition/continuation protocol from these saved
states. It does not isolate frequency information from scheduling, establish
global identifiability, demonstrate convergence, or recover an unknown count.
It also does not determine what would happen from an earlier, less optimized
low-frequency state. No alternative starts are searched.

## 2. Frozen inputs and reuse

Let `B` denote this immutable source bundle:

`results/validation/topology/TOP-016-20260914-fixed-topology/`

Use the following **retained stage-1 endpoints** as starts for both new arms:

| Case | Source within B |
|---|---|
| `far-two-stars` | `runs/S-far-two-stars/metrics.json`, field `final_state` |
| `central-ellipse-star` | `runs/S-central-ellipse-star/metrics.json`, field `final_state` |

For each case verify the corresponding `runs/F-<scene>/metrics.json::final_state`
is coefficient-identical, that both records ended at stage 1, and that the
accepted checkpoint and saved endpoint score refer to those same coefficients.
Copy exact serialized states to the new bundle, preserving component IDs and
chart metadata. Save source file hashes and normalized state hashes. A missing
or inconsistent state is an obstruction, not a reason to rerun TOP-016 or choose
a more favourable endpoint.

Reuse B's `phase1/<scene>_training_observations.json`, `phase0/inputs/<scene>/observations.json`,
scene specification, selected nodes, material/solve settings and saved evidence.
The original 24 paired source/receiver positions remain unchanged. Do not use
the 48-pair benchmark. New observations and oracle regeneration are not in scope.

Keep Cartesian **K=9**, the existing polar-angle gauge, current finite-difference
LM, refined feasibility and feasible-side derivative treatment. The principal
representation and information screens already passed; do not repeat them.
The old sensitivity screen applies to the states it actually measured, not
necessarily every new endpoint.

Keep **128/256 nodes per component** and the exact qualified TOP-016 optimizer,
normalization and acceptance settings. Read B's contract, preflight and
`runs/.../stage_1/optimizer.json`; record a complete resolved configuration in
the new contract. Reset internal optimizer state at the new stage boundary,
identically for both arms. This is an explicit restarted continuation, not a
bitwise continuation of a partially assembled Jacobian or damping state.

## 3. Phase A — one small preflight and control audit

### A1. Mechanical implementation review, no forward work required

Inspect the current tree and intervening changes relative to the reviewed base.
Preserve user work. Confirm ID and path availability. Write a short API/file map
and resolve implementation risks in one review. Reuse `run_top016_preflight.py`,
`run_top016_pilot.py` and the existing optimizer hooks where sound; leave their
historical behaviour intact. A small new experiment driver/ledger is preferable
to a new framework or a second copy of the inverse solver.

Use structured stage/trial stop semantics from Section 5. Mock the forward,
finite-difference batch cost, clock and endpoint scorer to test them **before**
real continuation. No full TOP-016 replay is necessary.

Reconcile `docs/README.md`, `docs/iterations/topology/README.md` and the results
catalogue to the actual state. Link this review; add the dated shared-principles
amendment link. Numerical measurements stay in bundles, not several dashboards.

### A2. Audit the merge control without reoptimizing it

Rebuild a stage-by-stage table from the saved `S-merge` and `F-merge` artifacts:
active frequencies, all six frequency errors, within-stage gains, boundary
error, IoU, actual stops, correctly associated gradient diagnostics and work.
Compare stage-start and endpoint values under each *same* active objective;
do not compare differently normalized aggregate objectives across stage changes.
Locate the first recorded geometric/prediction deterioration. Existing artifacts
already suffice for the basic table; missing records stay explicitly missing.

Then perform a single evaluation-only representation check for the analytic
merge ellipse from the frozen scene specification:

1. Apply the existing truth-to-constrained-chart projection procedure at K=9.
   Check geometry against the analytic boundary, including densely sampled
   bidirectional distance and the original benchmark metric. Verify the gauge,
   component-radius constraint and production/refined feasibility.
2. Repeat **once at K=17** as a representation-only comparator. This is not an
   inverse arm or an instruction to change principal bandwidth. Use dense
   geometry sampling (16,384 and 32,768 samples) to verify projection/distance
   stability; no bandwidth ladder or best-of-many fits.
3. Evaluate these two projections at 0.5, 0.75, 1.0, 1.25, 1.5 and 2.5 GHz
   against the original observations. Use 128/256 numerical checks. A single
   512-node comparison is allowed solely to qualify the audit projection if
   needed; do not change principal resolutions. If it still fails, report the
   audit result as numerically unresolved.

Neither truth-fitted state can initialize an inverse, choose a step, select a
frequency, replace the merge control, or feed an optimizer objective. Record
projection geometry error, prediction error and discretization error separately.
One poor projection does not prove a best-approximation lower bound, and a good
projection does not prove that the inverse will find it. This audit can identify
an unqualified control assumption without excusing the actual regression.

### A3. Validate reuse and release the principal trials

Recheck the retained principal starts with the frozen numerical pair and existing
training observations. Apply TOP-016's numerical tolerances: 1e-7 relative
production/refined discrepancy for added training frequencies, and the recorded
1e-5 checks for original/evaluation predictions. No retuning against shape scores.

Release Phase B if input/source/configuration consistency, principal-state
feasibility/numerics and orchestration tests pass. An unresolved *merge-only*
projection result is reported but does not prevent asking the principal question.
A shared solver/data inconsistency, invalid principal start or unsafe accounting
is a hard obstruction. Do not perform a repair that changes the physical model,
optimizer mathematics or comparison intervention under this ID.

**Phase-A ceiling: 256 attempted frequency solves and 300 seconds of numerical
audit wall time, including all projection predictions and start rechecks.**
Artifact reading, document preparation and mocked tests require no BIE solves.
This ceiling is not a target. Do not consume it on a new sensitivity survey.

## 4. Phase B — only the unfinished principal stages

Run S and F for each of the two principal cases, four trials total. Start from
the paired retained states in Section 2; **do not repeat the 0.5-GHz stage**.
The S arm still fits only 0.5 GHz in all remaining stages.

| New stage label | S active GHz | F active GHz | Per-arm stage quota |
|---|---|---|---:|
| `stage_2` | 0.5 | 0.5, 0.75 | 1,250 frequency solves |
| `stage_3` | 0.5 | 0.5, 0.75, 1.0 | 1,750 |
| `stage_4` | 0.5 | 0.5, 0.75, 1.0, 1.25 | 4,000 |

These are exactly the unspent planned allocations of TOP-016, now assigned
explicit **quota-transition** semantics. The total is **7,000 solves and
1,800 seconds per trial**. No quota borrowing, budget doubling or opportunistic
restarts. Identical reset and maximum-iteration settings apply in S and F.
Unused quota is reported, not transferred.

Each quota includes start evaluation, derivative work, trial/refinement work,
rejections and endpoint scoring. Reserve **12 frequency solves** for the
existing six-frequency, two-resolution endpoint scorer. First-stage start
rechecks belong to Phase A or are charged to stage 2; never omit them from cost.
Avoid duplicate evaluation where a proven state/configuration cache suffices.

The objective is unchanged from TOP-016. For active set A:

\[
r_A(c)=|A|^{-1/2}\,\mathrm{stack}_{f\in A}
\left[\Re\frac{F_f(c)-d_f}{\|d_f\|_2},
      \Im\frac{F_f(c)-d_f}{\|d_f\|_2}\right],\qquad
\Phi_A(c)=\tfrac12\|r_A(c)\|_2^2.
\]

`c` is the real coefficient vector in the existing reduced/gauged chart;
`F_f(c)` is the predicted complex 24-pair response; `d_f` is its observed
counterpart; `|A|` is the number of active frequencies. Keep equal per-frequency
mean-squared relative-error weighting. Verify this against the actual residual
builder rather than scaling a different objective's derivative.

Maintain objective target 1e-14, disabled absolute loss-change stopping,
absolute acceptance margin 1e-14, relative margin 1e-8, the existing factor-5
production/refined gain-disagreement allowance, and inherited gradient, step,
damping, backtracking and feasibility settings. No outer 0.003 early return.
Candidate acceptance must remain training-only and numerically qualified.

## 5. Stop taxonomy: the central implementation change

The new driver needs structured outcomes, not string matching of generic budget
messages. Preserve old public defaults and TOP-016's runner behaviour.

| Stage outcome | Action |
|---|---|
| Normal optimizer return, including configured iteration/gradient/step stop | Save and qualify the retained endpoint, then advance. Preserve the actual optimizer stop separately. |
| `STAGE_QUOTA_REACHED`: next complete batch plus endpoint reserve cannot fit the stage quota, while trial solve/time limits remain safe | Do not start that batch. Save/score the retained state, record nonconvergence/unknown convergence, then advance. |
| `TRIAL_SOLVE_CAP` or `TRIAL_WALL_LIMIT` | Hard-stop the trial; never reset the counter/clock and continue. |
| Unresolved derivative, `infeasible_jacobian`, invalid retained geometry, failed numerical qualification or failed physical solve | Hard-stop and classify; do not switch frequencies to hide it. |
| Unexpected exception | Hard-stop as implementation error, preserve traceback and evidence. |
| Quota cannot fund even one model/step opportunity | Configuration/exposure obstruction; do not call that stage tested. |

A valid stage transition carries only the **last accepted**, feasible,
numerically qualified state. No rejected candidate or partial Jacobian is
committed. No later stage is allowed after an unsafe or unclassified interruption.

Before dispatch, compute the actual complete-Jacobian reservation using the
existing callback. As a scale check, with q=34 reduced directions and m active
frequencies a central-difference Jacobian alone is approximately `2*q*m` solves
(136, 204, 272 for F's three remaining stages), before objective/validation and
endpoint work. Record the implementation's conservative bound; the approximation
is not permission to exceed it. Mock a nonconvergent valid optimizer and prove
that all three stages receive a complete model/step opportunity within quotas.

Record **effective training exposure**: at each frequency, separate objective
calls, completed Jacobian batches, candidate attempts and acceptance validation
from endpoint scoring. Predicting 1.25 GHz for a plot is not training at 1.25 GHz.
A legitimately small-gradient endpoint after a complete current Jacobian can
count as an exposed stage even when no step is needed; score-only calls cannot.

Stage completion, schedule completion, convergence and reconstruction success
are separate fields. A final planned quota end may produce a
`COMPLETED_SCHEDULE` result with `convergence: UNCONFIRMED`; that is a valid
negative/positive measurement of this *bounded* protocol, not proof of a local
minimum. A global limit before stage 4 remains an incomplete comparison.

## 6. Tests and diagnostics that make this safe

Required mocked/geometry-only tests:

- A valid stage-quota event advances; global solve and wall limits do not.
  Test a wall interruption during a batch, not only between stages.
- An insufficient reservation starts no partial Jacobian and cannot consume
  endpoint reserve. Failed physical calls still count as attempted work.
- All scheduled F frequencies enter a real optimization-model evaluation;
  S never receives added-frequency observations for fitting.
- Paired starts are identical and TOP-016's completed stage 1 is not replayed.
- Rejected/partial candidates never replace accepted checkpoints. Endpoint
  scores cannot remain attached to a later, different state.
- Gradients include exact state hash, active frequencies, normalization and
  resolution. Stale diagnostics are explicitly historical or null.
- Defaults and archived source-bundle hashes remain unchanged. Existing focused
  optimizer tests still pass; do not reproduce an expensive physical trajectory
  merely to test defaults.

Use current hooks to preserve feasibility/rejection and one-sided/unresolved
counts where available. Missing fine-grained diagnostics must be disclosed;
no new full Jacobian is required solely to decorate a quota-limited endpoint.
At minimum save current accepted coefficients and objective, actual stops,
exposure, last measured gradient with its associated state, work and numerical
validation. Prefer a missing terminal gradient to falsely inferred stationarity.

## 7. Scoring, controls and decision

Only after each predetermined training endpoint is fixed, evaluate original
geometric metrics and all frequency errors. Do not choose an iterate, stage,
restart, frequency or bandwidth from truth/1.5/2.5-GHz scores. Keep optimizer and
scorer interfaces separate.

Report each principal case at the original TOP-016 start, reused stage-1 endpoint
and every new endpoint. Headline comparisons use the **same reused start** for
both arms. Historical/common-prefix work and new incremental work are separate.
Show both aggregate active-objective and per-frequency errors; do not claim
aggregate monotonicity when the active objective changes.

Keep original gate predicates visible: count fixed/correct; matched boundary
error <=1 mm; IoU >=0.90; refined 0.5-GHz error <=0.003; worst 1.5/2.5-GHz error
<=0.05. Report added-frequency fit too. These trials are not v1 benchmark passes.
The evaluation frequencies are repeatedly consulted development data, not a
fresh generalization test.

A **promising principal recovery result** requires all of the following,
predeclared here to prevent promoting a smaller training residual alone:

- Both S/F pairs have complete effective exposure and numerical qualification.
- F improves each principal boundary error by >=30% and worst evaluation error
  by >=20% relative to its reused start, without lowering IoU.
- At least one F principal endpoint satisfies all original gate predicates.
- F is not worse than S in either principal boundary or worst evaluation error,
  and is at least 20% better on boundary or worst evaluation error in one case.

These thresholds are operational decisions, not mathematical guarantees.
Always retain the raw continuous metrics and mixed improvements.

**No promotion to production or a full suite is authorized even if that principal
predicate passes.** Carry forward TOP-016's completed merge-regression record.
No new merge inverse has tested whether its issue is resolved, and a
truth-projection audit cannot substitute for that test.

Closeout must choose one next decision:

| Outcome | Next decision to record, not execute |
|---|---|
| Principal predicate passes | Whether one control-qualified follow-up is justified, using the merge audit to scope it. |
| Full exposure but weak/mixed/no useful principal benefit | Close this bounded fixed-K cumulative protocol as not qualified; consider one separately justified representation/regularization or optimizer question. No automatic more-budget version. |
| Exposure incomplete or numerics invalid | State the exact obstruction and what evidence remains usable. Do not label frequency diversity successful or unsuccessful. |

Do not run new truth-assisted local trials, another merge inverse, a twelve-scene
suite, TOP-013/014/015, or any successor ID under this contract.

## 8. Work ceilings and artifacts

Maximum new physical work: **28,256 attempted frequency solves**
(256 audit + four trials of 7,000). Phase-A numerical time is capped at 300 s;
each trial at 1,800 s. Use at most two numerical workers, single-thread BLAS,
separate output directories and an outer 7,500-s campaign watchdog. These are
ceilings, not spending targets or convergence promises. Failed/unavailable
trials remain in the report. No running worker may observe a changing source
checkout; record and recheck source hashes.

Use a fresh bundle:
`results/validation/topology/TOP-017-<run-id>/`.

Required compact contents: frozen contract and manifests, source/observation/
initial-state hashes, Phase-A control audit, four principal runs with stage
checkpoints/exposure and work, complete scorecard, commands/environment,
focused-test log, independent review where available, and README decision.
Write atomically; a report must rebuild from saved records without forward or
inverse reruns. Preserve available evidence on hard stops; unavailable exit
codes and gradients must not be invented.

Update track/dashboard status while executing. On closeout, create
`docs/iterations/topology/iteration_11/01_results.md` linking the bundle and
record exactly one next decision. Leave this executed contract intact apart
from dated status/closeout entries. Commit validated work locally if authorized;
no push, merge, branch deletion or successor execution without user direction.

## Approval and implementation record — 2026-09-14

The user explicitly approved TOP-017 exactly as scoped and budgeted and adopted
the staged-execution amendment. Installation uses the verified, clean TOP-016
commit `9ad3c8b191c7f1130764c0476480290b0f6a6e4a`, with no intervening code changes.
Worktree: `/home/drdeng/Neural-BEM-TOP-017`; branch: `track/topology-TOP-017`.
The uploaded ZIP was fetched from feature-branch commit `739a8c1` and extracted
temporarily; all package checksums passed. Only its three new docs were installed.
The execution source revision will be committed and recorded in the bundle
manifests before physical work. Validated commits stay local; no push or merge.

[Implementation preflight and review](../../../../results/validation/topology/TOP-017-20260914-staged-continuation/preflight.md)
owns the file/API map and review resolutions.
