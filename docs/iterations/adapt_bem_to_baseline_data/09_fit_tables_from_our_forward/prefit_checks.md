# Own-forward tables: checks before fitting

18 November 2026. Runner: `bem-own`. All four tables and checks pass.
No fit has started. This is the stop required by [the plan](plan.md); wait for the coordinator’s go.

Data forward: CPU reference `nodal_kress`, 2048 nodes, checked against 1024 nodes.
The unchanged forward computes all 36 by 72 pairs. The runner selects the frozen CSI mask afterward.
Each table has 8820 rows, 49 receivers per source and five frequencies. No solver edit was needed.

The source, receiver, frequency and incident columns equal the frozen tables numerically.
Row order and pair order are preserved. The reader returns the generated fields to round-off.
The unchanged `csi_forward_check.check_case` passes on each table at both modal resolutions.

All numbers below are relative errors unless marked percent. The accuracy limit is 1e-6.

| Shape | Worst 1024/2048 difference | Worst reader error | Worst modal truth mismatch | Layout checks |
|---|---:|---:|---:|---|
| circle | 6.809e-16 | 2.042e-16 | 9.650e-15 | pass |
| star | 1.208e-15 | 2.015e-16 | 9.906e-15 | pass |
| kite | 7.157e-16 | 4.312e-16 | 6.692e-15 | pass |
| hook | 2.020e-14 | 3.013e-16 | 1.759e-14 | pass |

Circle against the exact series, in frequency order 0.5, 1, 1.5, 2 and 2.5 GHz:
1.370e-15, 2.436e-15, 3.518e-15, 4.926e-15, 6.101e-15.

Difference to the frozen CSI table, percent, divided by the CSI scattered-field norm:

| Shape | 0.5 GHz | 1 GHz | 1.5 GHz | 2 GHz | 2.5 GHz |
|---|---:|---:|---:|---:|---:|
| circle | 0.442034 | 0.172326 | 0.134680 | 0.126049 | 0.176721 |
| star | 0.416448 | 0.172982 | 0.184197 | 0.143713 | 0.268444 |
| kite | 0.122862 | 0.190502 | 0.168532 | 0.200074 | 0.285510 |
| hook | 0.206659 | 0.173926 | 0.162682 | 0.140420 | 0.187653 |

These repeat activity 07: the largest absolute change in a relative mismatch is 3.229e-15.
This comparison reads saved checks only. No earlier run was repeated.

All four runs record their commit and a clean solver. Peak host memory is at most
0.705 GiB. All checks ran once; no failure or rerun.

Evidence: [summary](../../../../results/bem/baseline_data/fresnel_own_forward/2026-11-18/checks_summary.json),
[manifests and table hashes](../../../../results/bem/baseline_data/fresnel_own_forward/2026-11-18/data/),
[adapter checks](../../../../results/bem/baseline_data/fresnel_own_forward/2026-11-18/adapter_checks/).

Tables and prediction arrays stay local and ignored. Their manifests record sizes and SHA-256 values.
The fit runner changes only the input and output paths, then calls the unchanged wrapper.

```text
Activity: 09_fit_tables_from_our_forward; check stop, 18 November 2026
Runs: four nodal table preparations and four adapter checks; no fits yet
Result: all checks pass; 2048-node nodal reference data are ready
Failures: none
Upstream patches: none
Changes to our code: two new own_forward runners; no existing code changed
New unknowns: outline accuracy on these tables; fits wait for the coordinator’s go
Proposed next activity: finish this activity with the four unchanged GPU fits after go
```
