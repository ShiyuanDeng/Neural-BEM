# Iteration 15 — SC-032: the curvature metric helps, but not enough, and the collapse remains

2026-09-24. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**SC-032 execution: COMPLETE.** All 12 four-stage continuations finished
their schedules without budget or numerical stops. Evidence:
[SC-032 bundle](../../../../results/validation/shape_continuation/SC-032-regularizing-metric-prefix/README.md).
Contract: [iteration-14 plan](../iteration_14/03_plan.md).

## What changed

No numerical code changed. The SC-031 driver gained a continuation phase
that resumes stage-A checkpoints in a fresh bundle, and it refuses to run
if any numerical source differs from SC-031's manifest.

## What the measurement established

| Contrast (six cases, 0.01-mm floor) | GM RMS ratio | Worst | Verdict |
|---|---:|---:|---|
| R2 Hanke + curvature / R0 current | 0.832 | 1.00 | **Fails the pre-set ≤ 0.8 bar**, narrowly. No regression, no added hard stop, star/kite safeguards pass. |
| R1 Hanke + L² / R0 | 1.103 | 1.79 (kite) | Worse than the current rule |
| R2 / R1 | 0.755 | 1.00 | The benefit R2 has comes from the curvature metric |

- **Where R2 helps:** kite RMS 2.98 → 1.55 mm (Hausdorff 9.6 → 6.8 mm,
  stage-4 misfit 70× lower); peanut 2.94 → 2.39 mm (Hausdorff 17.0 →
  8.3 mm); C 3.20 → 2.75 mm. Circle, star and hook change by ≤ 7%.
- **The collapse remains.** The minimum tightest radius on C, kite and
  peanut is 1.0–1.9 mm in every arm. R2 fits better around the corner
  (fewer refit refusals on C/kite/peanut). It does not avoid the corner.
- **Cost:** R1 and R2 end every stage at the 22-iteration cap on the three
  hard cases, with ρ ≈ 1.00. That is 6–68% more work units than R0 there.

## What remains uncertain

- Whether R2's gains hold on new shapes and starts; these are six
  development cases, one run each.
- Whether R2 would gain more with a larger iteration budget. Its hard-case
  stages are iteration-capped. Testing that would be a new contract, not a
  retry.
- Why the stage-1 objective prefers the corner. The evidence says the
  corner is reached by well-modelled descent under four step rules.
  Whether it is a spurious local minimum of the 0.5 GHz misfit, or a
  representation effect of M = 3 normal moves, is not separated.

## Claims

- **Rejected (SC-031 + SC-032):** any tested step rule removes the stage-1
  collapse. Hanke's rule with an L² metric is not a baseline repair.
- **Supported, development evidence only:** a curvature-change step metric
  improves fit and geometry around the collapsed corner, with no case worse
  on the six. The pre-registered adoption bar is not met, so **R0 remains
  the baseline**. R2 stays opt-in.
- **Unchanged:** SC-029's finding that the first band decides C/peanut
  versus kite/hook.

## Smallest next decision (proposed, not approved)

The binding limitation is the stage-1 curvature collapse, and step-level
fixes have now been exhausted. The next lever should act on the admissible
set or the stage-1 objective. Recommendation:

**SC-033 — Borges' curvature-tail admissibility filter in the clean hybrid.**
- The reference paper's own safeguard (eq. 13; the package's
  `curvature_tail`) refuses trials whose curvature energy lies mostly above
  the update band. The clean hybrid dropped it, and a 2 mm corner on a
  300–420 mm perimeter violates it by construction.
- **Arms:** R0 and R2, each with a filter-refusal option at the package's
  existing 10% default.
- **Design:** stage-1 screen gate as in SC-031, then prefixes. About 30 min
  and ≤ 10,000 units.
- **Risk to test:** iteration 06 found that the 1% form excludes the exact
  star. Star and kite are therefore the legitimate-detail controls.
- **Why it matters:** it is literature-grounded, it is a candidate repair of
  the competent baseline, and the brief requires the baseline to have such
  a repair before any atlas policy comparison (WP4/WP5).

**Alternatives:**
- A prospective, truth-free first-band switch (WP4) evaluated on genuinely
  new shapes. On the development data a stage-1 collapse detector would
  help C/peanut but hurt kite. Designing it on these six cases alone would
  overfit.
- An explicit curvature prior in the stage-1 objective. It carries bias
  risk and is deferred behind SC-033.
