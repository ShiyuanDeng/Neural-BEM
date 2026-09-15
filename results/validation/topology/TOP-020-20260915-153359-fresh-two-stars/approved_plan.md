# TOP-020 — approved fresh automatic two-star integration

- **Approval status:** APPROVED
- **Execution status:** IN PROGRESS
- **Pre-dispatch validation:** 84 tests pass; source-bound record in `experiments/top020/validation.json`.
- **Authority:** 2026-09-15 user “yeah go”, followed by “cp first. then i approve
  you to finish the rest”; [scope and owner source review](02_proposals/01_fresh_two_star_contract_and_review.md).
- **Owner:** Codex `/root`. **Independent reviewer:** unassigned; owner review.
- **Checkout:** existing `feature/ordered-boundary-nystrom`, base `fa2666f`.

## Frozen contract

One fresh `far-two-stars` automatic run. Use its byte-identical original
`initial.circle` (center 0.40/0.57 m, radius 0.075 m) and scene specification from
TOP-008's frozen v1 data. Reuse TOP-017's 24-pair observations at training
0.5/0.75/1/1.25 GHz and development evaluation 1.5/2.5 GHz, verifying the
original 0.5 GHz and evaluation columns against v1. No new oracle solves.

1. Existing H controller at 64/128 nodes on 0.5 GHz alone, unchanged controller
   configuration and geometry/material settings. Maximum 4,000 physical API
   attempts (including TD systems and geometry refusals), 600 seconds.
   Only `recovered` or `topology_stationary` may hand off; numerical, physical,
   resource or implementation hard stops may not. Require valid saved event
   margins and monotone accepted topology states. Never require a particular
   component count to proceed.
2. Zero-pad every returned component to K9 without changing coefficients,
   geometry or IDs. Require feasibility at 256/512 nodes and 8-mm radius floor.
   Use the existing parameter-scaled, gauge-constrained Cartesian FD LM
   optimizer: FD step 1e-4, gradient and relative step tolerances 1e-7,
   objective target 1e-14, 22 iterations, 5 damping trials and 7 backtracks;
   loss-change stopping disabled. Existing step limits and damping unchanged.
3. Fresh cumulative F stages: [.5], [.5,.75], [.5,.75,1], [.5,.75,1,1.25] GHz.
   Quotas 1,000/1,250/1,750/4,000 frequency solves, each including 12 endpoint
   scoring solves. Additional initial score: 12. Continuation maximum **8,012
   solves / 7,200 seconds**. Reset optimizer each stage, retain accepted geometry.
   Planned quotas may transition only with complete usable optimization exposure
   and qualified retained endpoints; keep hard failures distinct.

Total ceiling **12,012 charged attempts / 7,800 active seconds**, one worker,
single-thread BLAS. No automatic retry, schedule extension or best-stage choice.
TOP-019 is not rerun. Existing fresh central artifacts are verified without new
physical work, and retained as historical regression evidence.

Normalization is `0.5 * mean_f(relative observed-L2 error_f squared)`.
Candidate loss acceptance retains absolute/relative margins 1e-14/1e-8 and
factor-5 production/refined gain disagreement. Prediction tolerances remain
1e-7 at 0.75/1/1.25 GHz, 1e-5 at 0.5/1.5/2.5 GHz. Require numerical qualification
at initial and all prescribed stage endpoints. No truth/evaluation signal enters
the topology controller, fitting, stage scheduling or endpoint selection.

## Decision and artifacts

Final is prescribed stage 4. Pass requires complete effective exposure, qualified
numerics, valid topology events and monotonicity, correct count, boundary error
<=1 mm, IoU >=0.90, refined 0.5-GHz error <=0.003, worst evaluation error <=0.05.
Report each gate, every stage, stopping/convergence separately, attempted and
completed solves, geometry refusals, other failures and wall time.

Save a fresh `results/validation/topology/TOP-020-<timestamp>-fresh-two-stars/`
bundle: frozen inputs, source-bound tests, contract, source snapshots, both
phase trajectories and work, event/candidate records, endpoint complex
predictions, state/objective/gradient associations, final score, verification,
figure and owner closeout. Results open iteration 14.

Pass releases scoping/execution of a separately recorded complete twelve-scene
candidate/reference comparison under the user's remaining-work approval. Failure
blocks that dispatch and requires a bounded diagnosis under the same approval.
No production promotion follows from this single scene.
