# TA-001: replay the four refusals through a tangent-angle chart

## Questions

1. In the default pipeline's four TG-002 refusals, is the refused trial
   curve nearly cusped (speed near zero)? Or is it nearly self-touching,
   with two distant parts close together?
2. If the same recorded step goes through a positive-speed tangent-angle
   chart, does the physics accept the trial curve? Is its exact loss below
   the last accepted curve's?
3. Would Haibing's coefficient bound have flagged the original step before
   any physics was attempted?

**Plan finalized 2026-10-26.** The user asked for 2–3 directions "to be
experimented overnight" and chose D08 among them. This track is the chart
branch only; the slider belongs to another agent. Execution starts when the
user launches this track's agent. Status: **NOT STARTED**.

Shared rules and the morning report: [overnight README](../../overnight_2026-10-26/README.md).
Fill in Track B there. Direction: [D08](../../../directions.md#d08-make-useful-shape-moves-easier).

## Why this question

All four default failures stop on the same refusal: the modal physics cannot
certify a lower bound on `|W|^2` ([NR-001](../../../../results/validation/cleaned_interfaces/NR-001/README.md)).
`W` is the divided difference of the curve; on the diagonal it is the curve's
speed. So a small minimum means either a near-cusp or a near-touch.

A tangent-angle chart keeps speed positive by construction. It can remove
near-cusps but not near-touches. The type of refusal therefore decides which
remedy is worth building.

[Haibing's review](../../../../Haibing_directions.md) item 3 gives a
coefficient bound on the same `|W|`. It warns the bound is often
inconclusive for non-convex shapes. Its prior-work list (Möbius-energy
penalty, algebraic self-intersection barrier) names the near-touch remedies.

## Inputs

| Case | Source | Last stage |
|---|---|---|
| aphex_twin__c0.5 | NR-001 M1 | stage_3_damped |
| aphex_twin__c4 | NR-001 M1 | stage_2_damped |
| aphex_twin__c13.3 | NR-001 M1 | stage_4_undamped |
| hook__c13.3 | NR-001 M1 | release_M11 |

Each stage record holds the last accepted curve and the refused trial row:
damping, backtrack, step norm, maximum normal move and speed ratio. The hook
row's speed ratio is 8.65. The refused curves themselves are not saved.

Optional rows, if time remains: the slider-path refusals in PS-002 M55 and
PS-003 D1 M55. These come from the latest experiments.

## Method

1. **Rebuild each refused trial.** Recompute the LM proposal at the saved
   accepted curve with that stage's settings and recorded damping. Check it
   against the saved step norm, maximum normal move and speed ratio. NR-001
   ran on a Mac CPU, so expect small rounding differences. If a trial does
   not reproduce, report it and stop that row.
2. **Classify.** Find where the minimum of `|W|^2` lies on the torus. Near
   the diagonal means a near-cusp; far from it means a near-touch. Also
   report the minimum speed ratio and the closest approach between distant
   parts.
3. **Haibing's bound.** Evaluate the item 3 coefficient bound for the
   original step: would it have refused, accepted or been inconclusive?
4. **Chart.** Derive and implement:
   - the map from a stored Fourier curve to chart coordinates (length,
     tangent angle, position);
   - closure;
   - the map back to the stored band K.

   Require round-trip error at most 0.001 mm on each accepted curve, the
   GU-002 curve-difference limit.
5. **Replay.** Map the recorded step's normal velocity into the chart, so
   it matches the original to first order. Apply it at the full step and at
   the halvings the fit tried. Evaluate each chart trial with exact physics
   at the stage's catalog and resolution.

## Decision

The answer to question 2 is **positive** if, in at least one case, a chart
trial is accepted by the physics with lower exact loss than the last
accepted curve. That shows a finite-map effect only; it is not recovery.

If every refusal is a near-touch, a negative answer to question 2 is
expected. The morning answer should then point to the near-touch remedies.

## Morning report

- A table with one row per case. Columns:
  - refusal type;
  - the original trial: physics status and loss;
  - the chart trial: physics status, loss, minimum speed ratio and closest
    approach;
  - Haibing bound verdict;
  - round-trip error.
- One figure per case: last accepted curve, original trial and chart trial,
  with the `|W|^2` minimum marked.
- Track B's section of the overnight README, answering the three questions
  with numbers.

## Continuation, only if `AGENTS.md` then allows it

If question 2 is positive:

- implement the chart as a `geometry_adapter`, with a B6 derivative of its
  actual finite map;
- check that derivative against finite differences;
- run the four failing cases once each with modal CUDA physics and the
  default `CumulativePolicy`;
- compare with NR-001.

Otherwise write the near-touch next step as a proposal; do not run it.
Stop all computation by 07:00 on 2026-10-27.

## Saved work

Prototype under `experiments/geometry_charts/`; results under
`results/validation/cleaned_interfaces/TA-001/`. Save settings, code
revision, rebuilt steps, classifications, chart errors and figures. Commit
and push after each completed step, then verify the push and working-tree
status.
