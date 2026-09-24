# SC-028 — test atlas-derived initial-band protection and frequency extension

2026-09-24. Owner: Codex. Independent reviewer: unassigned.

- **Approval status: APPROVED.** The user's current instruction explicitly
  requests analysis, proposed strategies, then tests and documented results,
  with commit/push at each milestone. That instruction authorizes this
  bounded follow-up and supersedes the older per-ID pause for this scope.
- **Execution status: NOT STARTED.** This plan is frozen before recovery
  outcomes. Its checkpoints are dataset analysis/plan, qualified harness,
  then executed results.
- **Checkout:** existing `feature/shape-frequency-continuation`; no new
  branch or worktree. Claude's completed source is `9b8918c`.

## Question and hypotheses

Does an M=2 first stage prevent early roughening, and does extending data
to 2.5 GHz improve geometry beyond additional work on the old data?
S1 and S2 are defined in the [proposal](02_proposals/01_atlas_strategies.md).

## Frozen comparison

Six cases: wrong_circle, circle_to_star, circle_to_c, kite, peanut, hook.
All are **development** cases. Observations and truth files are the existing
SC-022/SC-025 oracle-qualified 19-frequency catalogs, with hashes checked.
The common start, material, geometry, normalization, optimizer, numerical
resolution and acceptance settings are SC-025's ladder with backend V2:
K=192, N=512/1024, refit tolerance 1e-5, 22 iterations per stage.

Two four-stage prefixes are rerun from scratch:

- **baseline:** original M=(3,5,7,9), f=(0.5,0.75,1,1.25) GHz, cumulative
  data, uniform frequency weights, quotas (1000,1250,1750,4000).
- **protect:** M=(2,5,7,9), otherwise identical.

Each prefix yields three endpoints:

| Suffix | Data | Band and work |
|---|---|---|
| none | The prefix endpoint | Original 8012-unit cap |
| repeat | Original four frequencies throughout | Five extra stages use the same larger bands as extend, 22 iterations and 1500 units each |
| extend | Add 1.5, 1.75, 2, 2.25, 2.5 GHz cumulatively | M=floor(3 max(k,ki)) at each added frequency, 22 iterations and 1500 units each |

New cumulative objectives use equal weights over active frequencies.
Discrepancy tolerances remain 1e-5 at 0.5 GHz and 1e-7 above it. Both
suffixes use coefficient step control. Each suffix starts from the exact
same saved prefix and carries its work counts; prefix work is counted once
per complete comparison path. Damping restarts at each stage in all arms,
as in the existing backend. Stages advance on normal return or quota,
including `no_decreasing_step`; a numerical or hard work stop terminates
the path. There is no truth-dependent frequency trigger or rollback.

`repeat` is an **equal-ceiling** control, not equal actual work or equal
iteration cost. Actual units and stage stops are reported. The comparison
isolates new data conditional on the same enlarged bands and stage budget;
none versus extend alone conflates data, bands and extra optimization.

## Numerical and implementation gates

Before full recovery dispatch:

1. Independent dataset hashes/index/SC-022 algebra pass.
2. Existing targeted backend tests and new harness tests pass. Check the
   frozen frequency/weight/band schedules, prefix/suffix budgets, truth
   isolation, and stopping/ledger behavior. No shared numerical defaults
   or core solver code changes.
3. At each of the six saved SC-025 ladder endpoints, compare fields and
   the P=48 Jacobian at N=512/1024 at 1.5 and 2.5 GHz. Relative field and
   maximum column-relative Jacobian errors must each be <=1e-6. Record
   all 12 checks, with <=48 solves/reciprocal batches, <=10 minutes.
4. A fresh baseline wrong-circle prefix must reproduce the stored endpoint
   to <=1e-10 coefficient relative error and identical work/stop history.
   This prefix is reused in the campaign. If a gate fails, retain the
   failure and close the affected experiment without silently changing N,
   tolerances, budgets or interventions.

Each accepted inverse step retains the existing production/refined gate.
Endpoint scores include common-frequency relative residuals at all 19
catalog frequencies using N=1024, outside the fitting interface and ledger.
They are evaluation data, not fresh held-out data. Score actual symmetric
RMS and Hausdorff geometry, and record radius, unresolved-projection
refusals, accepted-step sizes, quotas and hard stops. Normal-ray truth
projections do not choose or score the optimizer.

## Decision criteria, frozen before runs

Compare protect/none against baseline/none for S1, and extend against
repeat within each prefix for S2. The combined path is also compared with
baseline/none, but alone cannot identify a mechanism.

A strategy qualifies **for a future fresh-case test** if the geometric
mean of six RMS-error ratios is <=0.8, no case worsens by >1.5x after a
0.01-mm RMS floor, and it causes no additional hard/numerical stop. Report
the raw errors and all Hausdorff changes alongside this primary criterion.
The floor prevents micron-level circle errors dominating a safety ratio;
it does not replace the reported measurement. For S2, this gate must pass
in both prefixes to claim a robust main effect; otherwise state the
interaction explicitly. This is a development screen, not default promotion.

## Budget, files and preservation

- At most 12 distinct prefixes and 24 suffixes: 36 reported endpoints.
- Per prefix: 8012 work units. Per complete extended/repeat path: 15512
  units including sunk prefix work, <=3600 seconds of active path work.
- At most 12 worker processes, one BLAS thread each. No controlled timing
  speedup claim. Numerical preflight <=10 min. Campaign <=2 hours wall;
  any unfinished path is budget-limited, not a completed negative.
- Endpoint evaluation: <=36*19=684 additional field solves, separately
  reported. Geometry-only metrics do not count as physics solves.
- Implementation: one isolated `experiments/shape_continuation/atlas_strategy_tests.py`
  harness using `fit_stage`, with its focused tests. Preserve all core APIs.
- Fresh artifacts: `results/validation/shape_continuation/SC-028-atlas-strategies/`:
  manifest, configuration, qualification, histories, checkpoints, results,
  case table, comparisons and plots. Dense inputs stay in their hashed
  source bundles. Reproduction instructions accompany the results.
- Closeout opens iteration 11. Failed arms remain recorded. No parameter
  amendments or additional successor campaign are implied by this plan.
