# TOP-023 — approved frozen-terminal model diagnosis

- **Approval:** APPROVED under “cp first. then i approve you to finish the rest”.
- **Execution:** RUNNING.
- **Owner/reviewer:** Codex `/root`; no independent review claimed.
- **Authoritative contract and file/API map:** [resolved proposal](02_proposals/01_terminal_model_contract_and_review.md).
- **Branch:** existing `feature/ordered-boundary-nystrom`; no branch/worktree creation.

Freeze the verified failed TOP-022 terminal state and training-only inputs.
Reconstruct one 256-node h=1e-4 Jacobian and compare its gradient to the saved
terminal model. Qualify the prescribed two directions at h/h2 and 256/512
using existing TOP-018 thresholds. These are selected-direction checks, not
full-Jacobian or basin qualification.

Conditionally compare the unchanged LM formula at the exact next terminal
damping, 1e-6, 1e-4 and 1e-2. Same coordinate bounds, geometry, numerical and
acceptance rules; at most eight backtracks and first qualified decreasing
candidate per arm. All candidates remain diagnostic records. No inverse run,
truth/development-guided choice or changed shared source/default is authorized
by this experiment itself.

Hard ceiling **600 new charged frequency calls /1,200 active seconds**, one
numerical worker and one BLAS thread. Exact worst-case measurement bound 580;
every whole batch must be reserved. Reuse eight historical training prediction
systems; no new oracle/evaluation calls. Preserve all failures and partial work.

Pre-dispatch tests must bind current sources and cover model replay, input
isolation, stencil refusal, selected-direction gating, whole-batch reservation,
damping controls, acceptance/numerical failures and saved-array replay. Save
raw probes, model arrays, all four arm records, source snapshots and exact work.

An alternative releases only a separately declared bounded continuation
comparison if it gives >=2× the baseline production gain with no more candidate
calls (or succeeds when the baseline has no qualified decreasing step). Reject
the damping-change line if absent. No full-suite release or recovery claim.
Results open iteration 16. Continue the remaining roadmap according to evidence
under the user's broader approval; do not silently extend this diagnostic.

## Dispatch

85 pre-dispatch tests pass (42.34 seconds, zero physical solves).
202 measured source files and five test files are pinned.
Output: `results/validation/topology/TOP-023-20260915-181302-terminal-model`. The inherited TOP-022 source guard passes.
