# TOP-008 — feasible finite differences at an active constraint

Guarded **G** against **H**, the same policy with `feasible_fd_jacobian` on, on the frozen twelve-scene v1 matrix, reusing TOP-007's observations and initial states byte-for-byte with zero new oracle solves. The stencil is the only difference between the arms.

Implements rank 1 of the [literature verdict](../../../../docs/iterations/topology/iteration_05/02_proposals/03_literature_verdict.md) and nothing else: a probe the radius floor refuses is no longer recorded as a derivative of zero. The feasible set, the gauge, the 8-mm certificate, the acquisition, the candidates and every default are unchanged.

## Stage 1 — is a one-sided estimate trustworthy?

A per-direction probe of two saved final states, no optimizer and no topology search. Steps 0.5h, h and 2h around the configured 1.0e-4 m were declared in the contract before execution, as was the 0.25 agreement tolerance.

At the pinned `far-ellipse-star` state, **15 of 20 gauge directions are refused on exactly one side and none on both**, so every column the defect froze is recoverable. Estimates are stable across the declared sequence to a worst relative difference of **7.20e-03**, against a tolerance of 0.25. Where a central difference also exists, the one-sided estimate differs from it by at most **4.50e-03** — so the mixed-order Jacobian the correction assembles is a measured, small effect rather than an assumed-safe one. The interior control reproduces its own central differences to 1e-5. **0 directions** had no usable side at any step.

[Per-direction record](stage1_derivative_probe.json) · [script](stage1_derivative_probe.py)

## Stage 2 — does a measured model produce a feasible decrease?

One bounded fixed-topology continuation from the saved guarded `far-ellipse-star` final state, run with each stencil. No topology event, no candidate, no new observation. Budgets — 22 iterations, 600 s, 1200 solves — were declared before execution and all were respected.

| | Frozen columns | Feasible columns |
|---|---|---|
| Stop reason | `infeasible_jacobian` | `maximum_iterations` |
| Iterations taken | 0 | 22 |
| Production loss | 4.699775e-04 | 1.028875e-04 |
| Refined loss | 4.694624e-04 | 1.028876e-04 |
| Refined training error | 0.03064 | 0.01434 |
| Matched boundary error | 18.624 mm | 9.070 mm |
| Pinned mode-9 component's radius certificate | 8.000 mm | 22.737 mm |
| Decrease at **both** resolutions | False | True |

The frozen arm takes **zero** iterations: every direction that would move the pinned component is a zeroed column, so there is no step to take and the run stops immediately. With the feasible stencil the same state, same data and same budgets give a genuine decrease at both resolutions under the existing margin convention, and **the pinned component leaves the floor entirely**, from 8.000 mm to 22.737 mm. That is the hypothesis stated in the contract, and it holds.

Two honest qualifications. The continuation stopped at `maximum_iterations`, so it was still improving when the declared budget ran out — this is a lower bound on what the corrected model can do from that state, not a converged answer. And 9.07 mm of boundary error is still far outside the 1-mm gate: the component moved, it did not arrive.

[Continuation record](stage2_continuation.json) · [script](stage2_continuation.py)

## Stage 3 — the frozen benchmark

G returns 9/12 runs and H returns 10/12. G passes 5/12 scenes and **H passes 5/12**. **The correction buys no new benchmark pass.** Stages 1 and 2 qualified the mechanism; this stage says the mechanism is not by itself sufficient for these scenes, which is what the verdict's low confidence for the suite anticipated.

What did change, reported in both directions:

- `central-ellipse-star` **completes** under H where G spends the full ten minutes, ending at 9.22 mm and 0.777 IoU. One fewer timeout.
- `split` improves sharply and gets cheaper: matched error 0.175 mm to 0.000023 mm, worst holdout error 1.13e-2 to 3.24e-6, and 281 solves against 1172. It passed in both arms, so this buys accuracy and cost, not a pass.
- `far-two-stars` returns a final state **identical** to G. Its census found no constrained direction, and the run bears that out — the control behaved as a control.
- `far-ellipse-star` and `empty-ellipse-star` are **mixed**: boundary error improves 18.62 mm to 17.62 mm, while refined training error gets *worse*, 3.06e-2 to 6.45e-2, on a trajectory that takes different events and stops earlier. A better-measured Jacobian changed where the run went, not only how well it descended. This is reported as mixed rather than as an improvement.

Arm H records one-sided columns on every completed run (2 to 55) and unresolved columns on one (`far-two-circles`, 2). Every guarded run used at least one one-sided column, so the declared "inert wherever no column is one-sided" check again has no members; the identical `far-two-stars` final state stands in its place and is recorded per scene.

[Error and work](error_and_work.svg) · [All initial scenes](initial_scenes.svg) · [New scene results](new_results.svg) · [Original controls](original_results.svg)

## Per-scene outcomes

| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | Worst holdout error | BIE solves | One-sided cols | Unresolved cols | Stop |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| [repeated-birth](runs/G/repeated-birth/metrics.json) | G | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 789 | — | — | recovered |
| [repeated-birth](runs/H/repeated-birth/metrics.json) | H | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 789 | 32 | 0 | recovered |
| [death](runs/G/death/metrics.json) | G | PASS | 2 / 2 | 4.0575e-05 | 0.9987 | 1.103e-06 | 5.4e-06 | 811 | — | — | recovered |
| [death](runs/H/death/metrics.json) | H | PASS | 2 / 2 | 2.0085e-06 | 0.9987 | 5.972e-08 | 2.451e-07 | 293 | 6 | 0 | recovered |
| [split](runs/G/split/metrics.json) | G | PASS | 2 / 2 | 0.17521 | 0.9954 | 6.873e-06 | 0.01128 | 1172 | — | — | recovered |
| [split](runs/H/split/metrics.json) | H | PASS | 2 / 2 | 2.3357e-05 | 0.9987 | 6.788e-07 | 3.239e-06 | 281 | 16 | 0 | recovered |
| [merge](runs/G/merge/metrics.json) | G | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 553 | — | — | recovered |
| [merge](runs/H/merge/metrics.json) | H | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 538 | 16 | 0 | recovered |
| [mixed](runs/G/mixed/metrics.json) | G | PASS | 2 / 2 | 1.42e-05 | 0.9987 | 4.283e-07 | 2.075e-06 | 1360 | — | — | recovered |
| [mixed](runs/H/mixed/metrics.json) | H | PASS | 2 / 2 | 0.17177 | 0.9974 | 4.561e-06 | 0.01288 | 2284 | 38 | 0 | recovered |
| [far-two-circles](runs/G/far-two-circles/metrics.json) | G | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2028 | — | — | recovered |
| [far-two-circles](runs/H/far-two-circles/metrics.json) | H | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2035 | 32 | 2 | recovered |
| [far-ellipse-star](runs/G/far-ellipse-star/metrics.json) | G | FAIL | 2 / 2 | 18.624 | 0.7043 | 0.03064 | 1.4 | 3593 | — | — | topology_stationary |
| [far-ellipse-star](runs/H/far-ellipse-star/metrics.json) | H | FAIL | 3 / 2 | 17.616 | 0.6928 | 0.06453 | 1.357 | 2431 | 40 | 0 | topology_stationary |
| [central-ellipse-star](runs/G/central-ellipse-star/failure.json) | G | FAIL | 5 / 2† | 22.718† | 0.5211† | — | — | ≥3464 | — | — | timeout |
| [central-ellipse-star](runs/H/central-ellipse-star/metrics.json) | H | FAIL | 2 / 2 | 9.2226 | 0.7775 | 0.01567 | 0.8922 | 2618 | 55 | 0 | topology_stationary |
| [enclosing-ellipse-star](runs/G/enclosing-ellipse-star/failure.json) | G | FAIL | 5 / 2† | 148.94† | 0.1770† | — | — | ≥2887 | — | — | timeout |
| [enclosing-ellipse-star](runs/H/enclosing-ellipse-star/failure.json) | H | FAIL | 7 / 2† | 150.43† | 0.1751† | — | — | ≥2014 | — | — | timeout |
| [empty-ellipse-star](runs/G/empty-ellipse-star/metrics.json) | G | FAIL | 2 / 2 | 18.624 | 0.7043 | 0.03064 | 1.4 | 1938 | — | — | topology_stationary |
| [empty-ellipse-star](runs/H/empty-ellipse-star/metrics.json) | H | FAIL | 3 / 2 | 17.616 | 0.6928 | 0.06453 | 1.357 | 776 | 40 | 0 | topology_stationary |
| [far-two-stars](runs/G/far-two-stars/metrics.json) | G | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | — | — | topology_stationary |
| [far-two-stars](runs/H/far-two-stars/metrics.json) | H | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | 2 | 0 | topology_stationary |
| [far-three-shapes](runs/G/far-three-shapes/failure.json) | G | FAIL | 5 / 3† | 57.691† | 0.2040† | — | — | ≥3306 | — | — | timeout |
| [far-three-shapes](runs/H/far-three-shapes/failure.json) | H | FAIL | 7 / 3† | 30.306† | 0.3724† | — | — | ≥2898 | — | — | timeout |

† Failed-run quantities describe the last saved accepted state, not a qualified final solution, and their solve counts are lower bounds. Column counts are summed over the cycles whose records were written before a run stopped, so a timed-out run under-reports them, and they are recorded only in arm H. Arm totals are not a cost comparison: measuring a column the other arm froze is extra work by construction.

## Verification

Artifact verification: **PASS**. [Machine-readable checks](verification.json) recheck source and observation hashes, paired inputs, rederived gates, exact reproduction of TOP-007 by the guarded arm, the stage-1 stability tolerance and the stage-2 both-resolution decrease. This is a re-reading of artifacts by the implementation owner, not independent scientific review. Reviewer: unassigned.

The [plan](../../../../docs/iterations/topology/iteration_05/03_plan.md), [contract](../../../../docs/iterations/topology/iteration_05/02_proposals/04_feasible_fd_contract.md) and [frozen specification](scene_spec.json) fix all scenes, budgets, gates and stage thresholds before execution. Observations and initial states are copied from [TOP-007](../TOP-007-20260911-refined-feasibility/README.md); no new oracle solve was performed. Per-run timeout is ten minutes and the suite ceiling is 45 minutes. Four single-thread subprocesses may overlap, so elapsed times are not a controlled speed comparison.

[Execution](execution.log) · [Full metrics](suite_metrics.json) · [Tests](tests.log)

Rebuild this analysis from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/topology/TOP-008-20260912-feasible-fd/analyze.py
```
