# Iteration 24 — one-off repair versus recurrent state restrictions

2026-09-26. **SC-042 COMPLETE: 24/24 paths.** Owner: Codex; independent
reviewer: unassigned. The user's instruction to execute successive strategy
tests authorized this campaign. Existing checkout and branch retained;
numerical production code and defaults unchanged.

One-off cleanup passes the frozen development gate. Repeating cleanup or
permanently restricting the state to K64 produces essentially the same
geometry on these six continuation suffixes. This supports a simple repair
baseline for these starts; it does not supply a prospective intervention
rule for a full reconstruction.

[Frozen contract](../iteration_23/03_plan.md),
[full evidence and figures](../../../../results/validation/shape_continuation/SC-042-state-strategies/README.md),
[machine-readable comparison](../../../../results/validation/shape_continuation/SC-042-state-strategies/analysis.json).

## Returned endpoints

RMS errors in mm. All arms have the same allowance and M ladder within each
case. Actual work differs when a path stops early. The comparisons use a
0.01 mm floor; differences below it do not rank strategies.

| Case | None | Once | Each stage | Permanent cap | Fitting units per arm |
|---|---:|---:|---:|---:|---|
| Star | 0.017758 | 0.017755 | 0.017756 | 0.017772 | 1,159 |
| Kite | 0.047617 | 0.027887 | 0.027898 | 0.027910 | 760 none; 1,710 each treatment |
| Circle | 0.000245 | 0.000245 | 0.000245 | 0.000245 | 114 |
| C | 0.006343 | 0.006280 | 0.006281 | 0.006281 | 551 |
| Peanut | 0.002336 | 0.002336 | 0.002336 | 0.002336 | 779 |
| Hook | 0.002103 | 0.002103 | 0.002103 | 0.002103 | 893 |

For once versus none, the terminal geometric-mean RMS ratio is **0.91466**;
the worst floored RMS/Hausdorff ratio is **1.000054**. At a common work
allowance within each case, the geometric-mean RMS ratio is **0.98461**.
The larger terminal gain partly comes from the cleaned kite continuing after
the uncleaned path hits its numerical gate. These six development shapes are
not a sample supporting a population confidence interval.

## What the kite establishes

The unchanged kite's next proposed step decreases the objective on both
grids, but its field refinement discrepancy reaches 1.390e-7 against the
1e-7 gate. The returned, previously accepted state passes its endpoint audit.
It is a numerical stop, not convergence or demonstrated unobservability.

At the common 760-unit ceiling, one-off cleanup gives RMS 0.04339 versus
0.04762 mm and Hausdorff 0.14272 versus 0.31584 mm: improvements of 8.9% and
54.8%. At 1,710 units its RMS reaches 0.02789 mm, while Hausdorff remains
0.14120 mm. Report both comparisons; the last one is not equal actual work.

The sharpest point is an artifact on a flank, not a true tip. Cleanup
increases its minimum radius from 0.0933 to 1.2526 mm. However, the two true
tip radii are about 2.138 mm, whereas the cleaned reconstruction has roughly
2.83 and 2.92 mm near them. Better distances do not imply exact feature
curvature, and one initially sharper true tip becomes blunter.

Intrinsic curvature also exposes a remaining wall. Energy above arclength
order 64 is 95.0% for none, 32.2% for once, 29.9% for each-stage cleanup and
30.1% for the permanent K64 cap; the truth has 0.250%. A Cartesian storage
cutoff is not a curvature-spectrum constraint. The centered update preserves
the original zero-step parameterization; the resulting curves need not be
exactly uniform in arclength. See the [mechanism audit](../../../../results/validation/shape_continuation/SC-042-state-strategies/mechanism.md).

## Numerical qualification and cost

All 125 saved-evidence checks pass, including budgets, within-stage loss
monotonicity, matched first-stage cleanup trajectories and preservation of
the last accepted state. Work is **19,874 fitting units +2,663 original audit
units =22,537 units**. One unit denotes one frequency field solve or one
reciprocal batch; it is an accounting convention, not equal floating-point
cost. Shared-host elapsed time is not a controlled speed benchmark.

Twenty-one original endpoint audits pass. The kite boundary/cap and C
boundary audits time out during a host memory-pressure event. There is no
observed tolerance violation in those timed-out audits. Their original
flags remain false and prevent those arms passing their original gates.
[SC-045](../../../../results/validation/shape_continuation/SC-045-timeout-qualification/README.md)
records one separate serial qualification of each identical endpoint, with
unchanged tests and limits and all additional work charged. Its outcome is
pending at this closeout's initial writing. SC-045's first numerical result
was subsequently lost to a missing output directory: the failed execution
and up to 130 unrecorded work units remain recorded. A separately frozen
[SC-046 recovery](../../../../results/validation/shape_continuation/SC-046-lost-audit-recovery/README.md)
supplies one additional attempt without rewriting either original failure.

## Consequence for iteration and novelty

The experiments isolate repair, repeated cleanup and a permanent state cap;
they do not establish a new filtering principle. The [claims review](02_claims_review.md)
documents close prior work. Once/boundary/cap geometry is within the declared
5% tie band on every development case. A more complicated state strategy
needs a benefit on full trajectories, local features or robustness to earn
its additional machinery.

The frozen [SC-043 policy test](../../../../results/validation/shape_continuation/SC-043-prospective-band/plan.md)
asks whether a prospective action diagnostic beats fixed and stagnation
controls after paying its cost. The running [SC-044 transfer test](../../../../results/validation/shape_continuation/SC-044-noisy-fresh-cases/plan.md)
starts two new shapes from a circle and adds paired measurement noise.
Neither result is inferred from the successful kite repair. Conditions for
further iteration are recorded [separately](03_next_decisions.md).
