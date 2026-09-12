# TOP-009 — controlled bandwidth enrichment of surviving components

- **Approval status:** APPROVED under the user's 2026-09-12 directions to
  implement the Codex plan and to keep going. The plan is the
  [literature verdict](../iteration_05/02_proposals/03_literature_verdict.md);
  this contract implements its rank 2, the only other candidate it accepts.
- **Execution status:** STOPPED AT STAGE 2. [Iteration 07 results](../iteration_07/01_results.md).
- **Owner:** Claude. **Independent reviewer:** Codex (literature verdict).
- **Baseline:** `106929b` on `feature/ordered-boundary-nystrom`.
- **Branch:** continue `feature/ordered-boundary-nystrom`; no new branch.
- **Proposal:** [contract](02_proposals/01_bandwidth_capacity_contract.md) ·
  **Review:** [decisions](02_proposals/02_bandwidth_capacity_review.md).

## Question

`far-two-stars` stops with two Cartesian mode-1 components against a five- and a
seven-lobed star, nothing pinned, 22 mm of headroom and 1.4% of the training
residual unexplained — and its final state is bit-identical under both stencils,
so TOP-008 did not touch it. Under the polar-angle gauge a mode-1 component can
only translate and scale. Does letting a stalled component enter a strictly
richer nested space recover shape, and are the added directions observable at
all from 24 observations at one frequency?

## Intervention

One mechanism, opt-in, default off: `bandwidth_promotion`. Attempted **only when
a cycle would otherwise stop** `topology_stationary`. The ladder is the smallest
bandwidth that strictly increases the gauge dimension, capped at the existing
`chart_contour_modes`; promotion is exact zero padding; the promotion is
retained only on a training decrease beyond the existing acceptance margin at
**both** resolutions, and reverted otherwise. No holdout frequency, truth count,
lobe count or location enters any of it.

## Pre-execution record

Measured before implementation, and now asserted in tests:

| Cartesian `K` | 1 | 2 | 3 | 4 | 9 |
|---|---:|---:|---:|---:|---:|
| Parameters | 6 | 10 | 14 | 18 | 38 |
| Gauge directions | 3 | **3** | 5 | 7 | 17 |

`K = 1` and `K = 2` carry the same three directions, so the ladder runs
1 → 3 → 4 → 5 → 6 → 7 → 8 → 9 and never spends a rung that buys no direction.

Fourteen geometry-and-gauge tests, no BIE solve: the skipped rung, strict
dimension increase at every rung, the cap coming from the existing contour
setting rather than from a truth, boundary points unmoved by padding to within
1e-15, the padded state surviving regauging, and refusal to pad the radial chart
or to pad downward. `pytest/sdf_inverse` reports **578 passed** with the flag
off, unchanged from TOP-008's 564 plus these 14.

## Stages

| Stage | What it asks | Budget |
|---|---|---|
| 1 | Are the added directions observable above numerical noise, and do they explain residual the existing columns cannot? | Two saved states, per-rung, no topology search |
| 2 | Does climbing actually reduce the objective? | One continuation with and without promotion, ≤22 iterations per rung, 600 s, ≤2500 BIE solves |
| 3 | Does it hold on the frozen benchmark? | Twelve v1 scenes, arms H and J, saved observations, original gates |

Each stage can stop the line. Reaching a higher mode count is **not** a stage-2
pass; a run that climbs and reverts everything is a clean negative and is
reported as one.

## Declared risk

The fine ladder is expensive — at `K = 9` one Jacobian is 17 directions. The
plausible bad outcome on the three scenes that already time out is **more
timeouts, not more passes**. Declared here so it cannot be presented later as a
surprise.

## Closeout record

Stage 1 passed, stage 2 failed its declared predicate, and the line was stopped
before the suite;
[bundle](../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md),
[closeout](../iteration_07/01_results.md).

- **Stage 1 PASS.** 14 of 14 rungs observable at `far-two-stars`, explaining up
  to 0.6445 of the residual beyond the existing span, against 0 of 14 and at most
  3.8e-7 at the circular control. Zero padding moved the boundary by 0.000e+00 m;
  columns stable to 7.3e-5 against the 0.25 tolerance.
- **Stage 2 FAIL.** All seven rungs retained by the training-only rule. Training
  loss fell 248x, 9.219e-05 to 3.717e-07, while matched boundary error rose
  7.595 mm to 17.599 mm, union IoU fell 0.7468 to 0.6383 and worst holdout error
  rose 1.003 to 1.514. The endpoint is worse than the start on every gated
  measure; the path is **not** monotone -- matched error improves on two of the
  seven retained rungs.
- **Stage 3 NOT RUN.** The stage-2 predicate included boundary error, so the gate
  holds. Tuning the rule after seeing its result is what the stage structure
  exists to prevent.

The declared risk — that the fine ladder would cost timeouts rather than buy
passes — did not get the chance to materialize, because the rule failed on
accuracy first.

Recorded overrun: the climb used 3127 solves against the declared 2500 cap, as
the stage script tests the cap between rungs. The overrun turned out to matter --
[stage 4](../iteration_07/01_results.md) showed the cap had stopped the climb at
its single worst rung.

`bandwidth_promotion` ships opt-in and off.

**Amended the same day.** The closeout first read stage 2 as overfitting on an
under-determined acquisition. A [stage-3 diagnostic](../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage3_correction.py)
refutes that: the true geometry fits the training acquisition to 5.2068e-14
(relative L2 3.23e-07), so the climb's answer is 7,139,598x worse than
achievable. A truth-selected 34-degree rotation of component `t001` reduces its
boundary error to 6.523 mm, against the 7.595 mm circle it started from, which
scores a phase mismatch without measuring training descent; and the ladder
stopped on its solve cap with `t003` three rungs below the K >= 8 its seven-lobed
truth requires. The stage-2 gate outcome stands.

**Further amended after independent review.** A low truth residual establishes
forward consistency, not identifiability, so "the data is not the limit" is
withdrawn -- the final K=9 state satisfies the controller's 0.003 data tolerance
at 8.7878e-05 while its boundary error is 11.849 mm. Thirteen of the fourteen
stage-4 rung refinements stopped on `loss_change_tolerance` and none on the
gradient test, so no local minimum is certified either. See the
[review](../iteration_07/02_proposals/01_independent_review.md). Recorded as
amendments rather than rewrites.

**Independent review amendment, 2026-09-12:** the preceding causal conclusion
is superseded by the [iteration-07 review](../iteration_07/02_proposals/01_independent_review.md).
Truth consistency does not establish identifiability; stage 4 completed the
bandwidth ladder but 13/14 refinements stopped on small loss change. Stage-2
boundary error also improved on two intermediate rungs, so the monotonicity
claim above is incorrect. The measurements and failed stage-2 gate stand.
