# TOP-019 implementation map and owner review

Approved by the user's “go” on 2026-09-15 under
`docs/iterations/topology/iteration_12/03_plan.md`. Owner/reviewer: Codex `/root`;
owner review only, independent reviewer unassigned.

## File/API map before implementation

- `experiments/top019/run.py`: frozen merge-only inputs, K=17 zero padding,
  numerical audit, sequential campaign, four-stage adapter and exact ledgers.
- `experiments/top019/summarize.py`: JSON-only verification, scorecard, work
  reconciliation and coefficient-derived SVG. No inverse or forward imports.
- `pytest/sdf_inverse/test_top019.py`: mocked dispatch, reservations, failure
  preservation, source/input identity, real geometry and reporting checks.
- Reuse `run_top017.Ledger`, `fit_stage`, `run_schedule(stage_plan=...)`;
  `topology_controller.zero_padded_component` and `_optimizer_config`;
  TOP-018's pure discrepancy, quotient and derivative qualification helpers.
- Build experiment-specific objective identities: TOP-018's identity helper
  embeds its two-star observation path and must not label merge artifacts.
- Reuse the mathematical derivative audit with merge provenance; preserve its
  fixed two rows, two steps, nodes, feasible-side estimator and floor rule.
- No numerical defaults, historical drivers or shared physical APIs change.

## Risks to resolve before dispatch

Rebuild 70-entry steps and parameter limit; preserve coefficients while padding;
keep truth witness outside fitting; enforce Phase A before either arm; compare
both stage-1 endpoints before F stage 2; count all endpoint work within quotas;
preserve typed hard stops and current accepted states; retain both-resolution
predictions and objective/gradient hashes; preserve failed workers and avoid
list/tuple metadata comparison defects. Freeze the actual source and inputs
against the passing test record before dispatch, with one writer and one
numerical worker.

## Pre-dispatch verdict

PASS before physical dispatch, 2026-09-15. The source-bound validation record
in `validation.json` and `pre_dispatch_tests.log` records **84 passed tests**
(47.17 s), with zero physical solves. The only warnings are Matplotlib's
existing Pyparsing deprecations during figure generation.

Owner source review confirms: one merge-only campaign, three prescribed audit
states, immutable zero padding, 256/512 throughout, unchanged derivative and
acceptance mathematics, four explicit quotas and sequential dispatch. All
84 tests cover the new seams and inherited optimizer/budget/checkpoint behavior.
The artifact roundtrip independently recalculates errors from saved complex
predictions and rejects corrupted reported errors. Both list/tuple gradient
associations and failed-audit zero-dispatch are exercised. Historical numerical
drivers and defaults have no workspace changes.

The measured source is the recorded base revision plus hashed experiment-owned
files; those new Python files are copied into the result bundle before dispatch.
No commit is required to make that frozen source reconstructible. Physical
qualification and reconstruction remain unmeasured at this review point.
