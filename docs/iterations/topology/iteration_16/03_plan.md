# TOP-024 — approved bounded damping-reset continuation pair

- **Approval:** APPROVED under the user's recorded remaining-work instruction.
- **Execution:** COMPLETE; 98 source-bound pre-dispatch tests passed. The
  current user instructed one bounded continuation with unchanged gates.
- **Owner/reviewer:** Codex `/root`; independent reviewer unassigned.
- **Contract/API map:** [resolved proposal](02_proposals/01_damping_reset_pair_contract_and_review.md).
- **Workspace:** existing checkout and branch; no branch/worktree creation.

From the exact frozen failed TOP-022 endpoint, compare the existing four-frequency
optimizer with initial damping A=3.138105960899997e-15 and B=1e-2. No TOP-023
candidate enters either initialization. Identical K9 chart, 256/512 nodes,
observations, feasibility, step/damping/stopping rules and **12-update** horizon.
Reuse the shared saved initial endpoint score; charge all new fitting work and
the prescribed final endpoint. Truth/development only enter final scoring.

Each arm: one stage 4, **4000 calls including final scoring /3600 active seconds**.
Two isolated BLAS-1 subprocesses maximum, **8000 total calls**; each has a 3900-s
outer timeout and 10-s grace. Preserve failures, partial rows and work. No extra
reset, extension or best-state choice. Verify first-step agreement with the
TOP-023 witnesses under the contract's roundoff tolerance.

Dispatch only after the TOP-023 release/source checks and source-bound tests
pass. Save both configurations, predictions, trajectories, terminal gradients,
source/test snapshots, commands/exits and full counters. Replay without BIE work.

Only recovery under all original numerical and reconstruction gates can release
a separately declared fresh integration. Compare cost/accuracy if both pass.
If neither recovers, do not launch fresh/full-suite work on residual reduction
alone. Results open iteration 17; the broader roadmap remains evidence-gated
under the user's existing authorization.

## Execution closeout

Bundle: [TOP-024-20260915-201101-bounded-damping-pair](../../../../results/validation/topology/TOP-024-20260915-201101-bounded-damping-pair/README.md).
Outcome **NEITHER_ARM_RECOVERED**; 7,504 calls, 0 failed/refused.
Source/input checks and zero-solve replay pass. Results open
[iteration 17](../iteration_17/01_results.md). No successor was dispatched.
