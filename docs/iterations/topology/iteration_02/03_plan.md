# TOP-005 — selectively include the simplest candidate

- **Approval status:** APPROVED within the user's 2026-09-11 request to take
  Track A as far as possible.
- **Execution status:** COMPLETE. Closed 2026-09-11; [iteration 03 results](../iteration_03/01_results.md).
- **Owner:** Codex. **Independent reviewer:** unassigned.
- **Baseline:** `746c9fb`, the completed TOP-001 implementation/evidence. Its
  default remains B0's best raw candidate with three refinement iterations.
- **Branch:** `track/topology-TOP-005`.

## Decision and hypothesis

Accept a selective allocation diagnostic from the
[iteration 02 results](01_results.md). Reject universal three-candidate/one-step
allocation: it failed the broader quality/cost qualification. Defer trigger,
construction and acceptance changes (TOP-002–TOP-004), and 3DGS-inspired policies.

F retains the usual raw shortlist and three-step budget. If the best raw
candidate's optimization dimension exceeds the minimum dimension available in
its `(event kind, resulting component count)` group, also refine the best raw
candidate of that minimum dimension, unless already shortlisted. Add at most
one candidate. Use accessible gauge dimension for Cartesian, parameter count
otherwise. A raw leader already in the cheapest dimension gets no extra work.

Hypothesis: this reaches the missed circular split seed while preserving the
baseline on groups already led by simple candidates. It should reduce total
work without the death/birth cost and stopping changes of E. This is falsified
if the five-case quality comparison fails or total work increases.

## Scope, controls, budget and decisions

Declared shared changes: optional `include_simplest_candidate=False` in the
controller config/CLI; a shortlist helper; selection-rank/dimension diagnostics;
an optional replay-harness argument for this separate experiment ID. No geometry,
solver, candidate construction, objective, trigger or acceptance change. Keep
the existing default available.

First confirm a raw-default replay still reproduces B0 in both charts. Then
run F on the exact twenty TOP-001 initial states (two charts × ten conditions),
and on the five full Cartesian controller cases. Compare against the already
recorded A controls. Maximum 27 new inversions/replays, one-hour wall ceiling,
up to six independent single-thread tasks at once. All observations, nodes,
seeds, initial states, iterations, tolerances and holdouts stay fixed.

Use fresh `results/validation/topology/TOP-005-20260911/` artifacts with source
hashes, portable observations, complete trials/events and work counts. Reuse
the prior geometry/train/holdout comparison gates: E's failed gates are not
retuned for F. Require all five controller quality gates and no increase in
summed full-controller or summed per-chart split BIE work. Record selection
stability and exact trajectory/work equality where F does not select an extra
candidate. A passing result qualifies an opt-in policy on these cases; it does
not justify claims beyond this bounded synthetic regime.
