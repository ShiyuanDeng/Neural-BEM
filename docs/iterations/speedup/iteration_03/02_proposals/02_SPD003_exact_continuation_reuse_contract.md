# SPD-003 — exact per-frequency reuse through the full inverse

The user's subsequent big-picture clarification is recorded in the
[pipeline architecture brief](03_pipeline_redesign_outsider_view.md).
This contract remains a narrower candidate; it is not the presumed next task.

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION.
- **Execution status:** NOT STARTED.
- **Origin:** user's 2026-09-16 request for further full-inverse acceleration;
  [source audit and candidate ranking](01_further_full_inverse_speedups.md).
- **Question:** does exact prediction/derivative reuse across cumulative
  frequency stages materially reduce complete inverse time with the same
  recovery, stopping behavior and numerical qualification?
- **Falsifiable hypothesis:** at least 1.20x median full-case speedup over the
  current fast CPU profile on each of death and split, with all quality gates
  unchanged. The audit predicts 340 to 136 continuation derivative assemblies
  on these particular unchanged-state runs; a complete-key mismatch or weaker
  wall-time benefit falsifies that prediction or the benefit gate respectively.
- **Baseline:** [SPD-002](../01_results.md), with fresh baseline timings from
  original SPD-002 observations/starts. B0 supplies formulation/optimizer
  provenance; the performance comparator is the current fast analytic CPU,
  not historical FD. Freeze source and all relevant configurations at dispatch.
- **Intervention:** add a bounded run-local exact cache of per-frequency raw
  predictions and raw complex analytic response derivatives, shared by
  continuation optimizer calls. Reapply current normalization and the
  FD-compatible policy each time. Use complete immutable keys and explicit
  hit/miss/invalidation accounting. No approximate geometry matching.
- **Controls:** same observations and evaluation isolation, original starts,
  topology policy, gauge/basis, materials, acquisition, precision, 64/128
  topology and 256/512 continuation nodes, frequency schedule, FD steps,
  feasibility/refusal rules, LM settings, stopping checks and iteration limits.
  Keep one BLAS thread and sequential arms. Existing budget reservations remain
  conservative; do not change their policy to create extra optimizer steps.
- **Scope and shared interfaces:** cache plumbing in
  `solvers/sdf_inverse/analytic_jacobian.py`,
  `solvers/sdf_inverse/radial_topology.py`, and the continuation schedule
  in `run_top017.py:run_schedule`, reached by
  `experiments/top025/run.py:run_continuation`; an optional
  cache object may be threaded through those APIs. Add exact-cache accounting
  in the existing work ledgers and a dedicated `experiments/spd003_*` runner.
  Preserve uncached APIs/behavior and the `reference` profile. No default
  promotion, GPU kernels, parallel workers, objective-factor retention or
  endpoint-cache redesign is included in this first comparison.
- **Qualification:** compare full Jacobians and predictions against uncached
  fast analytic CPU, including changing active frequency weights. Require
  relative prediction error <= `2e-11`, full-Jacobian and nonzero-column
  relative errors <= `1e-10`. For zero columns require absolute error <=
  `1e-12 * max(||J_reference||_F, float64.tiny)`.
  Exercise mutations of state, order, basis, grids,
  frequency, strengths, materials, backend and feasibility settings; stale
  entries must miss. Include one-/multi-component states, valid and refused
  stencils, and cache eviction. Reuse existing FD derivative checks as an
  independent qualification reference. Account for attempted/failed work.
- **Full-case measurements:** three baseline/cache pairs per scene for death
  and split, alternating order. Report each observation and median ratio,
  including worker startup and cache preparation. Also run one baseline/cache
  pair from the original central-ellipse-star start as a changing-geometry
  control. Verify whether it actually accepts continuation steps; if not,
  label coverage inadequate rather than calling it a moving-state control.
  Do not silently add a replacement campaign.
- **Recovery criteria:** both arms pass original topology, geometry,
  production/refined and final recovery gates. Require identical event types
  and component counts, stopping classifications and accepted-step counts;
  compare per-stage boundaries and final coefficients with `1e-6 m` maximum
  tolerances. Any trajectory discrepancy needs separate attribution and blocks
  a claim of unchanged inverse behavior. Retain fresh failures.
- **Timers:** obtain disjoint full-worker categories for geometry/feasibility,
  primal preparation, derivative preparation/application, factor/solve,
  optimizer/controller work, endpoint checks, startup and unclassified time.
  Nested detail may be reported separately. Reconcile actual systems,
  directional assemblies, cache hits and conceptual stage exposure. A reused
  derivative can inform the current gradient without being a new solve.
- **Compute budget and stopping rules:** numerical qualification <= 900 s and
  5,000 total full-system-plus-directional-assembly attempts; full-case
  measurement <= 7,200 s total, at most 14 complete workers (12 death/split,
  2 central). Retain existing 4,000 topology / 8,012 continuation work caps
  and local watchdogs, with an additional 1,800 s outer ceiling per worker.
  Exhausting a cap is incomplete evidence, not permission to extend it.
  Bound additional cache storage to 1 GiB with exact eviction. Stop on
  numerical/parity or recovery regression, counter mismatch, source/input
  drift, unexpected concurrent numerical/rendering work, or budget exhaustion.
- **Artifacts:** fresh `results/validation/speedup/SPD-003-<timestamp>-exact-reuse/`
  containing source/config/input hashes, machine/process/thread state,
  qualification and invalidation results, all full-run trajectories and
  metrics, per-frequency cache statistics, raw timers, memory peaks, failed
  arms and final verification. Historical SPD bundles remain immutable.
- **Decision:** recommend adoption only if qualification and both repeated
  full-case benefit gates pass without recovery regression. Report the
  central control independently; a slowdown there prevents broad default
  promotion. A smaller saving can be documented but fails this contract's
  benefit gate. If reuse is rare or assembly remains dominant, use the profile
  to prepare the separate kernel-precomputation proposal.
- **Owner:** unassigned. **Reviewer:** unassigned. Current document author:
  Codex `/root`; no independent review or execution approval claimed.

The existing checkout and branch are the proposed implementation location.
Any new branch/worktree would require the user's separate explicit approval.
