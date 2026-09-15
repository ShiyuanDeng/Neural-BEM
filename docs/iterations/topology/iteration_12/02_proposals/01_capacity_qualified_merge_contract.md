# TOP-019 — capacity-qualified merge-control comparison

**Later approval:** the user replied “go” to the named TOP-019 request on
2026-09-15. The [execution plan](../03_plan.md) now owns approval and execution
status; the original proposal below is preserved.

Prepared 2026-09-15 from pushed source `8cbf207cd50e87832f40b71a6dea3b75a4b3fe65`.
This is the first step of the [completion roadmap](../../README.md#completion-roadmap).
[Source and contract review](02_source_and_contract_review.md).

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Owner:** Codex `/root`. **Independent reviewer:** unassigned. The linked
  review is an owner review, not an independent review.
- **Current authorization:** the user's “see latest push, keep it going”
  authorizes preparing the next decision. No named TOP-019 approval has been
  received under the [shared workflow](../../../README.md#approval-rule).
- **Checkout:** existing `/home/drdeng/Neural_SDF_BEM_AD`, branch
  `feature/ordered-boundary-nystrom`.

## 1. Question, hypothesis and reference

**Question:** Does cumulative-frequency continuation recover the saved merge
control when both arms have the previously qualified K=17 representation?

**Falsifiable hypothesis:** under this bounded matched protocol, F reaches all
original recovery gates without introducing the geometric gate failure observed
in TOP-016. A completed, numerically qualified F endpoint that fails those gates
rejects success for this protocol. Budget exhaustion does not prove recovery is
impossible; numerical failure does not decide the recovery hypothesis.

The [TOP-016 merge regression](../../iteration_10/01_results.md) remains the
historical reference: F ended at 1.108232 mm boundary error and 0.1679487 worst
development-evaluation error. The [TOP-017 projection audit](../../iteration_11/01_results.md#merge-control-audit)
found a K=17 witness with 0.0171234 mm and 0.00234457 respectively, passing every
original gate. That witness establishes representability, not inverse recovery.
B0 remains the [controller baseline](../../../../baselines/B0_2026-09-10.md).

The primary comparison is the **new matched K=17 S/F pair**. Relative to
TOP-016, both arms share more shape coefficients, 256/512 nodes, and the
TOP-017 distinction between planned stage quotas and hard stops. Thus a
historical improvement cannot be attributed to bandwidth alone. S versus F
tests the combined acquisition/continuation protocol at the frozen capacity.
This is fixed-count post-merge refinement, not a new automatic merge event.

## 2. Freeze the start, observations and feasible set

Let `T` denote
`results/validation/topology/TOP-016-20260914-fixed-topology/` and `B` denote
`results/validation/topology/TOP-017-20260914-staged-continuation/`.

Use **`T/phase0/inputs/merge/state.json`**, the original K=9 controller endpoint
used to start both TOP-016 merge arms. It equals TOP-008
`runs/H/merge/metrics.json::final_state`, with one ID, `t001.merge1`.
Its canonical state SHA-256 is
`ea1512563437fd71226342022cde7d7879b2c8f562627c04bfc30d17990984c3`.

Extend each Cartesian cosine/sine array through K=17 with zeros using the
existing `zero_padded_component`; preserve the center, old coefficients and ID.
Both arms start with the identical extended state **before stage 1**. Do not
initialize from either later TOP-016 arm endpoint or the truth projection.
Verify old coefficients exactly and pointwise boundary change <=1e-10 m on
4096 and 8192 uniformly spaced angles. Check gauge consistency (maximum
coefficient change <1e-10), without using gauge retraction to silently replace
the frozen start. Any mismatch stops preflight.

Reuse, without oracle generation:

- `B/inputs/merge/training_observations.json`: 24 pairs at
  0.5/0.75/1.0/1.25 GHz; byte-identical to `T/phase1/merge_training_observations.json`.
- `B/inputs/merge/observations.json`: original 0.5-GHz data and 1.5/2.5-GHz
  development evaluation; byte-identical to `T/phase0/inputs/merge/observations.json`.
- `B/scene_spec.json`, semantically identical to `config/topology_scenes_v1.json`;
  original materials, positions, source strengths and physical solve settings.

Freeze source-file and canonical-state hashes, all observations and configuration
values before numerical dispatch. Verify the original training column is exact
in both observation files. The optimizer receives training observations and the
start, not truth or development-evaluation observations. The scorer owns truth.

Keep the gauge-constrained Cartesian chart, homogeneous 2D TMz physical model,
8-mm component radius floor, clearance rules and feasible-side FD treatment.
K=17 is fixed throughout; there is no bandwidth ladder. Use **256/512 nodes per
component** for both arms and every stage, including refined feasibility.
This is a declared common resolution accommodation following TOP-018, not a
claim that the historical 128/256 projection was unqualified. Discrete
feasibility can change with node count; record both checks.

## 3. Phase A: binding capacity and numerical audit

Maximum **256 attempted frequency solves / 900 seconds**. First perform the
mechanical input review and mocked/geometry tests listed in §7 after approval.
Then audit only these fixed states:

| State | Purpose |
|---|---|
| Original K=9 start | Verify padding preserves predictions as well as geometry |
| Zero-padded K=17 start | Qualify the primary start and its derivative directions |
| Saved `B/phase_a/audit.json::merge_projection["17"].state` | Evaluation-only capacity witness; never passed to fitting |

The witness's canonical hash is
`c3117d6954da02bb5d15ea48c1c7952c3ea9a894d66de82170e97ce13e87fa35`.
Reuse its coefficients, not a newly selected/refitted truth projection.

Evaluate all six frequencies at 256 and 512 for all three states (36 solves).
At each frequency use the existing column-wise relative discrepancy
`||P_256 - P_512|| / ||P_512||`. Thresholds remain **1e-7 at
0.75/1.0/1.25 GHz** and **1e-5 at 0.5/1.5/2.5 GHz**. Require finite nonzero
denominators, physical feasibility and all six numerical checks. At the same
resolution the original/padded predictions must agree to relative error <=1e-10.
The fixed witness must also retain all original recovery gates (§6) and its
<=0.1-mm representation gate; do not recalibrate thresholds from new scores.

At the K=17 start, check the **first and last rows** of its deterministic reduced
gauge tangent basis (indices 0 and 32). Use the four-frequency normalized
residual, steps 1e-4 and 5e-5, both signs and both resolutions, with the existing
feasible-side estimator. Preserve the TOP-018 criterion: relative difference
between step estimates <=0.25 at both resolutions, and half-step residual
signal >=5 times the maximum of repeatability, 64 machine epsilons, and
cross-resolution directional-change uncertainty. Record stencils, refused
sides, physical normal displacement, basis ordering and every floor. No search
for substitute directions or full sensitivity spectrum. This needs at most
68 additional solves (64 side predictions and four repeatability calls), with
bases reused from the table. All dispatches remain inside the 256 cap.

**Release both arms only if every required check passes.** A failed or
floor-limited direction, missing input, failed capacity witness or numerical
failure closes the audit without an inverse. No higher-resolution fallback,
new projection, relaxed threshold or additional diagnostic is released.

## 4. Phase B: one matched pair

Run S and F sequentially from the same K=17 start. Each runs stages 1–4;
stage 1 is measured anew at K=17 for each arm and charged to that arm. Preserve
both records and require matching canonical endpoint hashes before F stage 2.
A mismatch hard-stops F as an implementation obstruction to the paired
conclusion; do not substitute a preferred endpoint. If S stopped before a
qualified stage-1 endpoint exists, stop the campaign with an incomplete pair.

| Stage | S training GHz | F training GHz | Per-arm attempted solve quota |
|---|---|---|---:|
| 1 | 0.5 | 0.5 | 1,000 |
| 2 | 0.5 | 0.5, 0.75 | 1,250 |
| 3 | 0.5 | 0.5, 0.75, 1.0 | 1,750 |
| 4 | 0.5 | 0.5, 0.75, 1.0, 1.25 | 4,000 |

These preserve TOP-016's quotas, with TOP-017's qualified quota transitions.
Each stage resets damping/optimizer counters and retains the accepted geometry.
Use the existing per-frequency observed-L2 normalization and equal frequency
weights: `Phi_A = 0.5 * mean_f(||P_f - d_f||^2 / ||d_f||^2)` for active set A.
Production/refined objectives use the same observations, weights and scaling.

Rebuild `_optimizer_config` from the K=17 state: **70 stored parameters, 33
reduced directions**, `max_parameters=70`; translation/first-harmonic/higher-mode
step bounds 0.018/0.012/0.003 m in the existing parameter-name ordering. Preserve
22 iterations per stage, FD step 1e-4, gradient/relative-step tolerances 1e-7,
initial damping 1e-3, damping increase/decrease 10/0.3, five damping trials and
seven backtracks. Set objective target 1e-14 and disable absolute loss-change
stopping, as in TOP-017/018. Keep absolute/relative acceptance margins
1e-14/1e-8 and the factor-5 cross-resolution gain check. No outer `recovered`
early return, altered optimizer mathematics, restart, stage selection or tuning.

Reserve **12 solves inside each stage quota** for its six-frequency,
two-resolution endpoint. At 33 directions, an initial objective, complete
central FD Jacobian, candidate/validation opportunity and endpoint require
`70*m + 12` solves: 82/152/222/292 for one through four active frequencies.
Use actual conservative callback reservations and physical call accounting;
these arithmetic bounds are not measured cost predictions.

Normal returns and planned quotas can advance only with a completed usable
Jacobian/model and feasible, numerically qualified accepted endpoint. A quota
is not convergence. Hard trial limits, unresolved derivatives, numerical or
physical failure, invalid geometry and exceptions stop the arm. Preserve exact
machine stop strings and separate schedule completion, exposure, configured
convergence and recovery. Reporting-only endpoint scores cannot release a stop.
Never use truth/evaluation scores to select updates, stop a companion arm or
skip a prescribed stage. The final result is always stage 4 when reached.

## 5. Total budget and artifacts

| Work | Attempted frequency-solve ceiling | Numerical wall ceiling |
|---|---:|---:|
| Phase A | 256 | 900 s |
| S, all four stages including endpoint scores | 8,000 | 7,200 s |
| F, all four stages including endpoint scores | 8,000 | 7,200 s |
| Entire numerical campaign | **16,256** | **15,300 s (4 h 15 min)** |

One numerical worker at a time, single-thread BLAS. The campaign watchdog starts
at Phase A and does not reset between arms; no quota borrowing or automatic
retries. Unspent work is not a target. Record elapsed campaign time separately
from active numerical time, without historical speedup claims. Count every
attempted/completed/failed solve, derivative, rejected step, refined validation,
scoring call and cache hit. Reuse only exact state/configuration predictions.

Create a fresh `results/validation/topology/TOP-019-<timestamp>-qualified-merge/`
after approval. Preserve frozen inputs/contract/source hashes, approval record,
environment/commands, audit, per-stage initial/accepted/rejected states and
predictions, objective associations, exposure, gradient-state associations,
worker exits/tracebacks, scorecard and reconciled ledger. Save a common-start/S/F
figure. A summary must rebuild from saved artifacts with zero physical solves.
Retain all failed attempts; measured sources stay frozen during the campaign.
Closeout opens iteration 13, including audit-only or inconclusive results.

## 6. Scoring and the decision this releases

Score the initial state and every prescribed stage endpoint: correct fixed
count, **boundary <=1 mm, IoU >=0.90, original refined 0.5-GHz error <=0.003,
worst 1.5/2.5-GHz development-evaluation error <=0.05**, plus numerical checks,
feasibility and accepted-state objective monotonicity within each active set.
Report all six frequency errors and both-resolution objectives, not just gates.
Original topology events remain historical; this experiment introduces none.

| Qualified completed pair | Decision |
|---|---|
| F passes all gates, S fails recovery | Merge-control recovery established for this protocol; prepare a fresh automatic two-star integration contract |
| Both pass | Merge recovery established; no binary recovery advantage for F. Compare precision/work before choosing the next candidate |
| S passes, F fails | Preserve an adverse matched control; diagnose F's measured failure before integration |
| Both fail | The bounded K=17 protocol does not recover this control; distinguish stalled optimization from quota exhaustion and propose one bounded diagnosis |
| Either arm incomplete or unqualified | Preserve any valid single-arm success, but no completed matched conclusion; identify the numerical, exposure or resource obstruction |

Audit failure ends at Phase A. Continuous metric deterioration remains visible
even when binary gates pass. Completed quota-limited failures establish a failed
bounded protocol, not a global impossibility result. No outcome automatically
releases fresh two-star runs, a suite, a new optimizer, production promotion or
another experiment ID. Preserve central/two-star successes and the old merge
regression as separate evidence.

## 7. Implementation scope and verification after approval

Use an experiment-owned driver/summary under `experiments/top019/` and focused
tests. Reuse `run_top017.py::Ledger`, `fit_stage`, explicit `stage_plan` support
in `run_schedule`, TOP-016 scoring, and TOP-018's corrected reporting conventions.
Reuse small pure helpers where compatible; do not invoke a historical `main`,
patch module constants or silently inherit its scene-specific inputs/gates.
No shared geometry/objective/solver API or numerical default change is planned.

Before physical dispatch, record a short API map and verify: exact zero padding
and IDs; 70-entry step bounds/33-direction basis; training-only fitting;
Phase-A failure dispatches no inverse and pass permits only this pair; fixed
nodes/schedules; complete batch and endpoint reservations; typed quota/hard
stops; immutable accepted checkpoint on rejection; exact objective/gradient
associations including list/tuple frequency metadata; zero-solve summary rebuild.
Use mocked physical calls and geometry checks, then the approved audit. Check
historical drivers/defaults remain unchanged. An implementation defect may be
repaired inside this scope before dispatch; a needed mathematical/interface
change stops for a scoped decision.
