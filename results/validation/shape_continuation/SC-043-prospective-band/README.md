# SC-043 — prospective action diagnostic versus simple release rules

**COMPLETE, 2026-09-26: 18/18 paths; all 18 endpoint audits pass.**
**The frozen atlas superiority gate fails against both controls.**
[Full closeout and research implications](../../../../docs/iterations/shape_frequency_continuation/iteration_26/01_results.md),
[frozen contract](plan.md), [source/input hashes](manifest.json),
[complete tables](TABLES.md), [geometry against charged work](geometry_by_work.pdf).

Atlas geometric-mean RMS ratios are **1.11301 versus fixed escalation**
and **1.00512 versus stagnation**, against the required <=0.8. Worst floored
geometry ratios are 1.88097 and 1.67889. Common-work RMS ratios are
1.11425 and 1.00933. There are no additional numerical fitting failures;
these are qualified geometry comparisons, not timeout-driven negatives.

Kite is decisive: atlas keeps M22/M22/M22 and ends at RMS 0.06509 mm,
versus fixed M28/34/40 at 0.03461 and stagnation M22/22/28 at 0.03877 mm.
Atlas and stagnation spend exactly 817 units; fixed spends 798. On star,
atlas and fixed both release to M43 and achieve similar RMS, while
stagnation stops at M37. The converged circle is unchanged, with atlas
spending 342 versus 114 units for either control.

Six development starts, three policies, three decisions per path. Every
path receives the same initial K64 cleanup and subsequent K192 state.
All 19 frequencies are retained. These are continuation suffixes, not
fresh full inverses or an adaptive-frequency comparison.

Each block allows 304 units. Atlas spends 76 on qualified coarse/refined
fields and full Jacobians, leaving 228 for fitting. No cache reuse is
claimed. Its threshold is 10% additional optimal predicted loss decrease;
fixed always releases six modes, while stagnation uses the previous stop
and last accepted improvement. All decisions precede fitting and truth
scoring. All 36 low/high forecasts have inactive physical-radius caps.

Fitting/diagnostic totals: **3,496 fixed; 3,420 stagnation; 3,876 atlas**.
The atlas total includes 1,368 diagnostic units. Endpoint audits cost
114 each, or 2,052 overall. **Study total: 12,844 units.** A unit is one
frequency forward evaluation or reciprocal batch, not equal floating-point
cost across grids. Shared-host timing is not a speed benchmark.

All **248 evidence checks pass**, including decision rules, budgets,
endpoint receipts and matching initial trajectories when bands agree.
[Post-fit regularity](regularity.json) and [doubled geometry sampling](../strategy_metric_refinement.json)
remain descriptive checks and never replace original gates. The gate uses
0.01 mm floors, no geometry ratio above 1.25, no additional failure, and
qualified diagnostics/endpoints on all six cases against both controls.
Failure rejects this specific rule and cost model, not all possible atlases.

From the repository root, with EMNerf Python and `PYTHONPATH=solvers:.`:

```bash
python results/validation/shape_continuation/SC-043-prospective-band/analyse.py
python results/validation/shape_continuation/SC-043-prospective-band/regularity.py
```

The completed numerical runner is `run.py`; it never overwrites a run
directory. `dispatch.py` executed the same frozen workers after SC-042 and
the separately accounted SC-045/046 qualifications. The pre-solve
[resource-only tail amendment](scheduling_tail.md) limited heavy kite overlap;
[tail samples](host_tail.jsonl) record at most two workers and no nonzero
sampled 10-second memory-pressure average. Every job and monitor has exited.
All hashed sources and inputs are tracked in Git; analyses use portable JSON.

The single preflight rule revision is preserved in `preflight_v1/` and
explained in the contract/manifest. It preceded every policy diagnostic
and fit. No threshold or numerical source changed after the freeze.
