# PS-002: 5% over two accepted iterations on hook c13.3

## Result

The rule reduced the work but lost recovery. One requested fit ran on
2026-10-26, with no reruns or additional scenes. The unchanged GPU slider
baseline is the saved GU-002 run on the same RTX 5090 machine.

| Measure | GU-002 baseline | PS-002: 5% / 2 |
|---|---:|---:|
| Recovered | yes | no |
| Fit seconds | 30.294 | 25.492 |
| Accepted iterations | 125 | 58 |
| Physics work units | 2,978 | 1,672 |
| RMS error, mm | 0.000230 | 6.6047 |
| Hausdorff upper bound, mm | 0.0375 | 24.1316 |
| Maximum relative residual | 3.19e-7 | 1.1644 |
| Final numerical checks | passed | failed |
| Last stage | M67 | M55 |

The fit took 15.9% less time and used 43.9% fewer work units, but these are
costs of different outcomes, not a faster recovery. The baseline was not rerun;
the two timings were recorded on different days.

## What happened

All 14 completed stages stopped at the first combined loss decrease below 5%
over two accepted iterations. The history resets at each stage. At M55, the
first trial failed before any new curve was accepted.

D3 left after 6 accepted iterations at loss 0.00570859. GU-002 left D3 after
19 at 0.000656038. The new path continued, but its full-catalog loss remained
high: M11 ended at 0.442493, M19 at 0.348801 and M49 at 0.289437.

The M55 trial was nearly self-touching. Modal physics refused it because the
logarithmic kernel expansion needed more than its unchanged limit of 4,000
Chebyshev terms. The last accepted curve was preserved and checked afterward.
This identifies the immediate failure, not which earlier exit was decisive.

Only stage progress exits changed. LM damping, backtracking, K/M/Ku/F selection
rules, geometry construction and recovery criteria were retained. The plot
therefore shows the effect of the all-stage rule on this one trajectory.

## Evidence and checks

- [Approved plan](../iteration_01/03_plan.md).
- [Run report and stage table](../../../../results/validation/cleaned_interfaces/PS-002/README.md).
- [Loss comparison](../../../../results/validation/cleaned_interfaces/PS-002/loss_vs_iteration.png).
- [Machine-readable comparison](../../../../results/validation/cleaned_interfaces/PS-002/comparison.json).
- [Result checks](../../../../results/validation/cleaned_interfaces/PS-002/validation.json).
- [Full case records](../../../../results/validation/cleaned_interfaces/PS-002/runs/hook__c13.3).

The code revision at launch was `4249588d4`. Twelve focused code checks passed.
Saved configuration confirms CUDA preparation and scheduled LM damping; each
recorded progress exit was checked against the exact first-trigger rule.

The default remains unchanged. No further fit or threshold tuning was run.
