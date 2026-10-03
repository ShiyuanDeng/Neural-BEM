# RB-001 — recover the trajectories stopped by numerical resolution

2026-10-03. Drafted at the user's request to organize relaxed BIE as its own
track and plan the follow-up discussed after FM-002.

- **Approval status:** APPROVED by the user's 2026-10-03 request, "go on relaxed bie track".
- **Execution status:** IN PROGRESS. Archive verification and Stage-A replay implementation started 2026-10-03.
- **Owner:** Codex, in the existing checkout; plan prepared by Codex.
- **Reviewer:** unassigned; no independent review is claimed.
- **Question:** Can the four FM-002 real-prefix trajectories pass their
  numerical obstruction and recover when forward accuracy is controlled
  without loosening the original tolerances?
- **Falsifiable hypothesis:** At least one stopped trajectory can take a
  qualified decreasing step through refinement or a smaller step, and at
  least one can subsequently satisfy the existing recovery contract within
  the bounded continuation. Report these two claims separately.

## Baseline and fixed scope

Use the four original FM-002 failures, in this fixed order:

| Case | Arm | Stopped stage | Accepted steps before the stop |
|---|---|---|---:|
| `modal__c13.3__development_c` | R0 | `fixed_M49` | 3 |
| `modal__c13.3__development_c` | R1 | `release_M11` | 14 |
| `modal__c13.3__shifted_star` | R0 | `fixed_M49` | 0 |
| `modal__c13.3__shifted_star` | R1 | `fixed_M49` | 1 |

The [evidence index](../evidence_index.md#four-stopped-trajectories-to-replay)
links the exact stage records. FM-002's manifest records commit
`415a5655352d3a412a07516aae26bd355b380f90`; its archived source bytes, not that
commit alone, define the reference because the original run included workspace
changes. Preserve the manifest, archive, observations, original failures and
report hashes. Seal the new implementation and its differences separately.

R0 and R1 retain their different archived prefixes. All four resumed stages
use the ordinary real-data objective. Apply the same resolution-response
policy to both arms; do not select directions or retry rules by truth error.
The historical D0/D1 successes and easier C case remain context and regression
controls, not new matched timing runs. This is a four-trajectory development
diagnostic, not an all-36 or original-initialization campaign.

Keep acquisition, noise samples, observations, frequency weights, material
contrast, spline projected update, geometry band, validity guards, frequency
and update-band policy, optimizer metric, curvature approximation, stopping
tolerances and recovery thresholds fixed. The existing data-driven frontier
rule may resolve later bands differently on a changed trajectory; preserve
the rule and log its inputs/decisions rather than forcing archived outcomes.
Do not change the relaxed penalty sequence or introduce a new objective.

## A. Reproduce and diagnose the stop before changing it

1. Verify the archived artifact hashes. Read each stopped stage's entry curve,
   accepted-state history, damping sequence, trial metadata, per-frequency
   thresholds, ledger and terminal check. Record exact inputs in a new bundle.
2. Reproduce the stopped stage under the original hard-stop rule at N512/1024,
   beginning from that stage's saved entry state. Do not repeat localization
   or the earlier relaxed prefix. Capture the rejected candidate coefficients
   and complete optimizer state as observational output. Original trial records
   contain scalars but not the rejected coefficients: do not silently substitute
   an arbitrary nearby shape or claim a saved candidate that does not exist.
3. Require identical accepted-step counts, trial decisions and stop location;
   per-frequency fields and normalized losses must agree within
   `1e-10 + 1e-8 * abs(reference)` elementwise, and maximum coefficient
   difference must be <=1e-9 in the stored dimensionless coordinates. Record
   tighter achieved errors and distance to each acceptance threshold. A mismatch
   blocks that trajectory's causal continuation until explained; do not rewrite
   the reference or relax this gate after seeing the result.
4. Re-evaluate the same last accepted base and rejected candidate at the pair
   N1024/2048. Reuse N1024 fields where their exact inputs match. Apply the
   original per-frequency discrepancy limits and loss-decrease/margin checks
   to both base and candidate; compare losses on the same resolution.
5. Separately test the original proposal at the remaining scheduled half-step
   lengths, up to the existing seven backtracks, at N512/1024. This is a
   diagnostic of the immediate hard-stop decision, not a search over new
   directions or penalties. Save every attempt; stop that half-step scan at
   its first fully qualified decreasing step.

Report whether refinement alone, a smaller step alone, both, or neither removes
each stop. Finer agreement and decreasing loss are separate requirements.
Do not infer which discretization is correct merely from agreement of two
nearby meshes; record field trends and solver residuals, and label unresolved
cases explicitly.

**Gate to continuation:** the original stopped stage reproduces, the retained
base is numerically qualified at the selected pair, and at least one fixed
diagnostic candidate passes all unchanged acceptance/geometry gates. Run Stage A
for all four cases regardless of earlier outcomes. A case that fails the gate
remains in the report and does not consume a full continuation allocation.

## B. Qualify one opt-in numerical-response policy

Preserve the original hard-stop behavior as the default. For the experimental
policy, a production/refined discrepancy failure at a decreasing candidate
triggers the following deterministic sequence:

1. At N512/1024, try the same base/candidate at N1024/2048 before abandoning
   the direction. Do not loosen the original discrepancy or acceptance limits.
2. If the finer pair qualifies both states and the candidate decreases loss
   under the unchanged cross-resolution rule, accept that candidate and retain
   N1024/2048 for the rest of this resumed trajectory. Rebuild its objective,
   derivatives and curvature at the new production resolution for the next
   iteration; discard caches tied to the old resolution.
3. If the finer candidate does not qualify or does not pass acceptance, reject
   it and continue the existing half-step/damping search. If the base requires
   promotion to qualify, promote the base, recompute its direction at that
   resolution, and retry the same iteration without adding an iteration quota.
4. N1024/2048 is the largest permitted pair. At that pair, an unresolved
   candidate is rejected and the existing smaller-step search continues. If
   the base itself cannot qualify, stop as an unresolved numerical state.
5. Exhausted accuracy-limited trials must be reported as such. Do not label
   them stationary or merge them silently with a search in which every
   candidate was accurately evaluated and nondecreasing. Genuine geometry,
   factorization, implementation and nonfinite failures retain their own
   diagnostics; do not catch every exception as a retryable resolution error.

This is one bounded response mechanism. Stage A separates its two components;
Stage C measures their combined ability to continue. It is not a sweep over
retry algorithms. Log every rejected trial, refinement event, resolution,
discrepancy, loss margin and reason for continuing or stopping.

Meaningful validation before continuation:

- Original default reproduces the four Stage-A stops and the existing ordinary
  regression fixtures; relaxed-gradient qualification remains intact.
- A resolution failure can trigger refinement or backtracking without accepting
  an inaccurate candidate. A finer base failure terminates explicitly.
- An accepted promotion rebuilds all resolution-dependent calculations; no
  production/refined losses from different bases or resolutions are mixed.
- New evaluations, derivatives, failed attempts and validation solves are
  charged; caps are checked before dispatch, including threaded reservations.
- Pause/resume at an accepted state agrees with uninterrupted execution at a
  short deterministic ordinary stage, including next damping, counters and
  accepted steps. Merely restarting `fit_stage` with its initial damping is
  not equivalent and does not meet this requirement.

## C. Continue the qualified tails

Resume at the last accepted state immediately before each original failed
proposal, with its stage iteration, next damping, remaining stage quota,
global consumed work and policy state preserved. Retry the original proposal
under the qualified response rule; do not reset stage or global budgets.
The replay work is separately reported diagnostic overhead, not counted a
second time as historical fitting work.

Run all Stage-A-qualified trajectories, not just the first successful one.
Continue the original policy until its normal end, an explicit numerical or
geometry stop, or a declared resource cap. Do not choose the best iterate
using truth. Record the final accepted endpoint even when it fails.

Final scoring uses ordinary real observations and the existing FM-002 full
and unchanged-paired recovery contracts. Retain the original shape thresholds
(RMS <=1 mm, Hausdorff upper <=2 mm), residual limits and numerical audit.
Qualify the endpoint with the permitted finer pair when the original audit
resolution cannot resolve it; label this resolution change explicitly and
also report the original N512/1024 audit outcome. A missing qualified audit
cannot count as recovery.

## Budgets and execution

- **Stage A:** at most 4,000 dispatched frequency evaluations/derivative batches
  and 1,800 seconds total. This includes reproduced stopped stages, both
  resolutions, failed solves and half-step probes; no N4096 escalation.
- **Stage C:** each trajectory retains the FM-002 global fit cap of 13,412
  charged units and 1,800 seconds including its archived fit/localization cost.
  Subtract already consumed work and time; do not grant a fresh full budget.
  Preserve remaining stage iteration/work quotas. Report fresh run time and
  historical-plus-new cost separately.
- **Overall numerical execution ceiling:** 10,800 seconds (three hours) across
  replay, qualification, continued fitting and final audits. Smaller stage or
  per-trajectory limits still bind. Insufficient budget for an audit means
  unscored/inconclusive, not a failed recovery threshold.
- Use existing CUDA kernels and double/complex-double precision, four frequency
  workers at N512/1024 and one at N1024/2048 to bound peak memory. Log this
  execution change. Run trajectories sequentially and record hardware, memory,
  thread counts, other GPU jobs and every fallback. Never terminate another job
  to obtain a quiet machine.
- The discussed **2–4 hours** is an engineering estimate for implementation,
  checks and this bounded follow-up, not a promise or an experiment cap. The
  first diagnostic was estimated at 30–60 minutes. Report budget exhaustion
  honestly; do not extend scope silently.

Existing GPU acceleration is part of the baseline. Do not add GPU gradient
kernels, factor-residency changes or frequency batching to this experiment.
Profile the resumed ordinary stages and retain transfer/factorization/memory
data where available; a later optimization requires a separate matched
benchmark. No claimed additional GPU speedup is assumed by the plan.

## Implementation boundary and artifacts

Proposed code map, to be checked against the checkout before implementation:

| Location | Scoped change |
|---|---|
| `solvers/bem_inverse/continuation/lm_backend.py` | Opt-in resolution response and exact optimizer-state resume; unchanged default |
| `solvers/bem_inverse/runner.py`, `policy.py` | Minimal propagation of resumed stage, remaining budgets and qualified audit resolution |
| `solvers/bem_inverse/physics.py` | Reuse existing resolution-aware evaluation service; no new physics formulation |
| `experiments/relaxed_bie/rb001.py` (proposed) | Archive verification, four-case replay, fresh manifests, scoring and reporting |
| `pytest/bem_inverse/` and experiment tests | Focused response/resume/budget regressions plus the maintained package and affected numerical suites |

No numerical package imports from experiments, truth files or saved results.
Do not duplicate the optimizer or forward solver in the experiment driver.
Use the existing checkout; branch/worktree creation requires the user's
separate explicit approval. No such creation is part of this plan.

Create `results/validation/relaxed_bie/RB-001/` only when execution starts.
Refuse incomplete-run overwrites. Required outputs are: source/input/plan
manifest and source archive; source differences from FM-002; qualification
logs; reconstructed candidate and resume-state receipts; every replay and
retry; stage/work/timing/memory records; all continued endpoints and failures;
full/paired audits and truth-based scores; a reproducible comparison and
endpoint plot; and final artifact verification. Preserve all FM-001/FM-002
files untouched.

## Decisions and closeout

| Observation | Permitted conclusion |
|---|---|
| A candidate becomes accurate but the continuation still fails | The immediate stop was removable; recovery remains unestablished |
| Both R0 and R1 recover after the response change | A shared numerical limitation mattered; relaxation has no demonstrated additional recovery benefit on those cases |
| R1 recovers where equally treated R0 does not | Evidence for a conditional benefit of the relaxed prefix on these selected cases; not a general or all-36 claim |
| Neither passes the numerical gate within N2048 and the budget | Resolution question remains unresolved within this allocation; not a stationary failure or universal rejection |
| Fully qualified paths stop without recovery | Negative evidence for these settings, with optimizer stop reason reported separately from numerical and resource stops |

Do not promote a default based on one rescued trajectory. Report recovery,
shape improvement, residual fit, numerical reliability and cost separately.
Any broader campaign, alternate penalty/curvature method or GPU port gets a
new scoped proposal. Results open `iteration_02/01_results.md`; update the
track handoff when execution actually begins and when the experiment closes.
