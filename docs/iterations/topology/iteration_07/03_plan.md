# TOP-010 — separate stopping from stationarity

- **Approval status:** APPROVED under the user's 2026-09-12 direction after
  reading the [independent review](02_proposals/01_independent_review.md) that
  proposed it. The contract is that review's; this plan does not widen it.
- **Execution status:** COMPLETE (stage B gated stage not implemented; see closeout). [Iteration 08 results](../iteration_08/01_results.md).
- **Owner:** Claude. **Proposer and reviewer:** Codex.
- **Baseline:** `b82ad3f` on `feature/ordered-boundary-nystrom`; the TOP-009
  stage-4 final state, its data, chart and `K = 9`.
- **Branch:** continue `feature/ordered-boundary-nystrom`; no new branch.

## Question

Thirteen of the fourteen stage-4 rung refinements stopped on
`loss_change_tolerance` and none on the gradient test, so the saved record
establishes suboptimality without identifying its cause. Does the saved `K = 9`
state have a **resolvable feasible descent direction**, and does continued local
optimization use it?

## Falsifiable hypothesis

The apparent stagnation is explained by stopping or local step construction
rather than by stationarity. Stable small gradients together with no measurable
feasible descent would argue for a globalization study — and still would not
prove a local minimum.

## Two stages, the second gated

**Stage A — terminal audit. Diagnostic only, no source change.** At the saved
state, assemble the Jacobian with the feasible-side stencil at FD steps
**1.0e-4, 5.0e-5 and 2.5e-5**; record per-direction stencil choices, one-sided
and unresolved counts, the reduced gradient and its stability across the three
scales, and the reduced-Jacobian singular values. Then probe actual production
**and** refined loss change along the normalized negative-gradient and LM
directions, at the optimizer's existing trust bounds and backtracking scales.

**Stage B — paired continuation. GATED.** Comparing the recorded stopping rules
against loss-change stopping disabled with a `1.0e-14` absolute loss target
needs an optimizer option that does not exist. The review requires that option
to be **separately reviewed before numerical implementation**, so stage B does
not begin until stage A justifies it and that review is written. The `1e-14`
figure is a numerical diagnostic threshold, not a recovery or acceptance gate.

## Controls

Same production and refined resolutions, observations, radius floor, gauge,
trust bounds, damping and feasibility guards as the saved run. **Truth and
holdout may score results and must never select** a direction, a start or an
accepted step. No controller default changes and no new arm is introduced.

## Budget, declared before execution

At most **500 forward frequency solves** for the terminal audit and **2500
additional** for both continuations combined, within **600 seconds** total.
Limits are enforced at solver-call boundaries; diagnostics, rejected attempts
and holdout work are counted in separate ledger categories. On either limit the
run stops and retains partial evidence.

## Decision criteria

A stable measured descent direction **rejects** a stationarity claim. A lower
objective from local continuation **rejects** the claim that a restart is
already necessary. If local progress stalls with unresolved FD estimates, those
are resolved first. If stable local diagnostics find no descent, a separate
training-selected restart experiment is designed rather than started here. Any
later performance claim requires all twelve frozen scenes.

## Artifacts

Fresh `results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/`
with source and config hashes, direction probes, trajectories, complete work
counts, failure records and a summary.

## Closeout record

Both diagnostic stages ran inside their declared budgets using the **unmodified
optimizer and no source change**;
[bundle](../../../../results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/README.md),
[closeout](../iteration_08/01_results.md).

- **Stage A.** Terminal gradient 4.0134e-04 at the ladder endpoint — 4013x the
  optimizer's 1.0e-07 tolerance — stable to 3e-06 across the three declared FD
  steps, Jacobian full rank 34/34, zero one-sided and zero unresolved columns.
  A single LM step at the existing damping gives a 26.7% relative decrease at
  both resolutions. **The state is not stationary.**
- **Stage B.** Three restarts of the unmodified optimizer: 3.8613e-09 to
  2.2755e-09, a 1.7x improvement, 627 solves, 45 s. Each halted again on
  `loss_change_tolerance`. Premature stopping demonstrated operationally.
- **Plateau audit.** Still not stationary: gradient 824x its tolerance, full
  rank, and the best available step is 5.4379e-11 — downhill, but 0.54x the
  1e-10 acceptance margin, so refused. Three absolute constants sit at the same
  order as the entire remaining objective.
- **Geometry did not follow.** Matched error 11.849 to 11.991 mm, IoU unchanged
  at 0.7088, across the whole 1.7x objective gain.

Budgets: 224 and 239 solves against a 500-per-state audit cap; 627 against 2500
for the continuations; 110 s against a 600 s ceiling.

**Stage B's gated optimizer option was not implemented.** Stages A and B make it
uninformative rather than premature: the acceptance margin binds before the
loss-change threshold, and geometry does not respond across a 1.7x objective
change. The option remains available and unreviewed; this is a reported decision,
not a gate routed around.

All four decision criteria resolved as declared. The "local minimum" reading of
TOP-009 is refuted operationally, and no restart mechanism is yet warranted.
