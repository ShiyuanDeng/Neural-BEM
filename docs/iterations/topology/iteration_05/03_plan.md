# TOP-008 — feasible finite differences at an active constraint

- **Approval status:** APPROVED under the user's 2026-09-12 direction to
  implement the Codex plan when it arrived. The plan is the
  [literature verdict](02_proposals/03_literature_verdict.md); this contract
  implements its rank 1 and nothing else.
- **Execution status:** IN PROGRESS.
- **Owner:** Claude. **Independent reviewer:** Codex (literature verdict).
- **Baseline:** `897e5da` on `feature/ordered-boundary-nystrom`.
- **Branch:** continue `feature/ordered-boundary-nystrom`; no new branch.
- **Proposal:** [contract](02_proposals/04_feasible_fd_contract.md) ·
  **Review:** [decisions](02_proposals/05_feasible_fd_review.md).

## Question

A probe the radius floor refuses currently freezes its Jacobian column to zero,
and the resulting gradient can still report convergence. Does measuring the
feasible side instead let the pinned mode-9 component move, and does that change
anything on the frozen benchmark?

## Intervention

One mechanism, opt-in, default off: `feasible_fd_jacobian`. Each side of every
difference quotient is attempted independently; both sides give the central
difference unchanged, one side gives the one-sided quotient at that same step,
and only a direction blocked on both sides stays an unresolved zero. A small
gradient certifies stationarity only when no column is unresolved. The feasible
set, the gauge, the 8-mm certificate, the refined guard, the acquisition, the
candidates and every default are untouched.

## Stages

| Stage | What it asks | Budget |
|---|---|---|
| 1 | Are the one-sided estimates trustworthy? | Geometry and stencil only, two saved states, declared steps 5.0e-5 / 1.0e-4 / 2.0e-4 m |
| 2 | Does a measured model produce a feasible decrease? | One fixed-topology continuation, ≤22 iterations, 600 s, ≤1200 BIE solves |
| 3 | Does it hold on the frozen benchmark? | Twelve v1 scenes, arms G and H, saved observations, original gates |

Each stage can stop the line. A change of stop reason alone is not a stage-2
pass. Stage 3 reports every gate separately and does not replace A as the
historical default.

## Pre-execution record

A geometry-only per-side census at the two saved guarded final states, run
before implementation, found every refused direction at `far-ellipse-star` has
exactly one feasible side (15 of 20 directions; none blocked both ways), and
that `far-two-stars` has no constrained direction at all. That settles the
verdict's open question about whether a usable one-sided stencil exists, and
separates rank 1 from rank 2 cleanly.

Nine unit tests on analytic residuals — no BIE solve — cover the stencil, the
sign convention, the unresolved case, the stopping semantics, and the
requirement that the flag off reproduces today's behaviour exactly. The full
`pytest/` suite reports **1037 passed, 2 skipped, 5 failed, 4 errors**; the same
five failures and four errors occur at `897e5da` without this change, all in
archived material and parameterization drivers with missing fixtures, none
touching topology. That set is pre-existing and unaffected.

## Closeout record

To be completed. Results go to [iteration 06](../iteration_06/01_results.md)
and the bundle at
`results/validation/topology/TOP-008-20260912-feasible-fd/`.
