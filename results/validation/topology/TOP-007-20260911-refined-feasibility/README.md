# TOP-007 — refined-discretization feasibility inside the optimizer

Default **A** against guarded **G** on the frozen twelve-scene v1 matrix, reusing TOP-006's observations and initial states byte-for-byte with zero new oracle solves. The guard is the only difference between the arms.

**No guarded run aborts.** A returns 7/12 runs and G returns 9/12; the two runs that ended TOP-006 with an uncaught `MultiComponentTopologyError` now finish. Both arms still pass 5/12 scenes: the guard removes the crash, not the shape error.

Arm A reproduces TOP-006 exactly — identical final states, solve counts, stop reasons and training errors on every completed scene, and the same two aborts with the same 9.971374e-03 m clearance against the 1.0e-02 m floor. On **every scene both arms completed, the two final states are identical**; five also match solve-for-solve, while repeated-birth costs 30 more solves and far-two-circles 9 more for the same answer.

The guard rejected between 1 and 216 trial states per guarded run, and the controller-level rollback never fired: refusing the step was enough, and no accepted state ever had to be withdrawn. Guarded runs do not merely park on the floor either — the two newly completing scenes end with 38.1 mm of refined clearance.

`far-ellipse-star` is the requested case. Guarded, it runs birth, birth, death, birth and then **merge** — merging the two components whose approach ended the unguarded run — and stops `topology_stationary` with the **correct 2/2 object count**, 18.62 mm matched boundary error, 0.704 IoU, 3.06% refined training error and 140% worst holdout error. `empty-ellipse-star` starts from an empty domain and converges to the same two components to within 1e-8 m. Two very different initializations reaching the same wrong shapes places the remaining error in the representation and the objective, not in the start.

That reconstruction is a mode-1 circle where the star is and a mode-9 curve where the ellipse is. The ellipse component already carries nine modes and still stops 18.6 mm away with 3.06% training error, so bandwidth alone is not the missing ingredient — the optimizer is not exploiting the bandwidth it has. Any shape-capacity experiment has to account for that.

Three scenes still reach the ten-minute ceiling in both arms (central, enclosing and far-three-shapes), unchanged from TOP-006. How far a timed-out run gets depends on machine load, so those rows differ from their TOP-006 counterparts in progress and in their solve lower bounds; only completed runs are exactly reproducible.

[Requested distant-circle comparison](far_ellipse_star.svg) · [All initial scenes](initial_scenes.svg) · [New scene results](new_results.svg) · [Original controls](original_results.svg) · [Error and work](error_and_work.svg)

**[All videos](videos.md)** — every guarded scene, plus the default arm on the two scenes whose outcome changed. The before/after pair is [default](runs/A/far-ellipse-star/inversion.mp4) against [guarded](runs/G/far-ellipse-star/inversion.mp4) on the requested scene.

## Per-scene outcomes

| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | Worst holdout error | BIE solves | Guard-rejected trials | Stop |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| [repeated-birth](runs/A/repeated-birth/metrics.json) | A | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 759 | — | recovered |
| [repeated-birth](runs/G/repeated-birth/metrics.json) | G | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 789 | 42 | recovered |
| [death](runs/A/death/metrics.json) | A | PASS | 2 / 2 | 4.0575e-05 | 0.9987 | 1.103e-06 | 5.4e-06 | 811 | — | recovered |
| [death](runs/G/death/metrics.json) | G | PASS | 2 / 2 | 4.0575e-05 | 0.9987 | 1.103e-06 | 5.4e-06 | 811 | 5 | recovered |
| [split](runs/A/split/metrics.json) | A | PASS | 2 / 2 | 0.17521 | 0.9954 | 6.873e-06 | 0.01128 | 1172 | — | recovered |
| [split](runs/G/split/metrics.json) | G | PASS | 2 / 2 | 0.17521 | 0.9954 | 6.873e-06 | 0.01128 | 1172 | 19 | recovered |
| [merge](runs/A/merge/metrics.json) | A | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 553 | — | recovered |
| [merge](runs/G/merge/metrics.json) | G | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 553 | 32 | recovered |
| [mixed](runs/A/mixed/metrics.json) | A | PASS | 2 / 2 | 1.42e-05 | 0.9987 | 4.283e-07 | 2.075e-06 | 1360 | — | recovered |
| [mixed](runs/G/mixed/metrics.json) | G | PASS | 2 / 2 | 1.42e-05 | 0.9987 | 4.283e-07 | 2.075e-06 | 1360 | 16 | recovered |
| [far-two-circles](runs/A/far-two-circles/metrics.json) | A | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2019 | — | recovered |
| [far-two-circles](runs/G/far-two-circles/metrics.json) | G | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2028 | 52 | recovered |
| [far-ellipse-star](runs/A/far-ellipse-star/failure.json) | A | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥2255 | — | exception |
| [far-ellipse-star](runs/G/far-ellipse-star/metrics.json) | G | FAIL | 2 / 2 | 18.624 | 0.7043 | 0.03064 | 1.4 | 3593 | 216 | topology_stationary |
| [central-ellipse-star](runs/A/central-ellipse-star/failure.json) | A | FAIL | 6 / 2† | 25.821† | 0.4676† | — | — | ≥4286 | — | timeout |
| [central-ellipse-star](runs/G/central-ellipse-star/failure.json) | G | FAIL | 5 / 2† | 22.718† | 0.5211† | — | — | ≥3464 | — | timeout |
| [enclosing-ellipse-star](runs/A/enclosing-ellipse-star/failure.json) | A | FAIL | 6 / 2† | 148.94† | 0.1742† | — | — | ≥3845 | — | timeout |
| [enclosing-ellipse-star](runs/G/enclosing-ellipse-star/failure.json) | G | FAIL | 5 / 2† | 148.94† | 0.1770† | — | — | ≥2887 | — | timeout |
| [empty-ellipse-star](runs/A/empty-ellipse-star/failure.json) | A | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥600 | — | exception |
| [empty-ellipse-star](runs/G/empty-ellipse-star/metrics.json) | G | FAIL | 2 / 2 | 18.624 | 0.7043 | 0.03064 | 1.4 | 1938 | 214 | topology_stationary |
| [far-two-stars](runs/A/far-two-stars/metrics.json) | A | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | — | topology_stationary |
| [far-two-stars](runs/G/far-two-stars/metrics.json) | G | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | 1 | topology_stationary |
| [far-three-shapes](runs/A/far-three-shapes/failure.json) | A | FAIL | 6 / 3† | 53.316† | 0.2331† | — | — | ≥4139 | — | timeout |
| [far-three-shapes](runs/G/far-three-shapes/failure.json) | G | FAIL | 5 / 3† | 57.691† | 0.2040† | — | — | ≥3306 | — | timeout |

† Failed-run quantities describe the last saved accepted state, not a qualified final solution, and their solve counts are lower bounds. Guard-rejected trials are counted only in the guarded arm and only for cycles whose records were written before the run stopped, so a timed-out run reports none. Arm totals are not a cost comparison: G spends more in total precisely because two of its runs survive to finish.

Every guarded run that completed rejected at least one trial, so the declared "identical wherever the guard rejects nothing" check has no members. The stronger observed fact stands in its place and is recorded per scene: wherever both arms completed, their final states are identical.

## Verification

Artifact verification: **PASS**. [Machine-readable checks](verification.json) recheck source and observation hashes, paired inputs, rederived gates, exact reproduction of TOP-006 by the default arm, and identical final states and stop reasons wherever both arms completed. This is a re-reading of artifacts by the implementation owner, not independent scientific review. Reviewer: unassigned.

The [plan](../../../../docs/iterations/topology/iteration_04/03_plan.md) and [frozen specification](scene_spec.json) fix all scenes, budgets and gates before execution. Observations and initial states are copied from [TOP-006](../TOP-006-20260911-scenes-v1/README.md); no new oracle solve was performed. Per-run timeout is ten minutes and the suite ceiling is 45 minutes. Four single-thread subprocesses may overlap, so elapsed times are not a controlled speed comparison.

[Execution](execution.log) · [Full metrics](suite_metrics.json) · [Tests](tests.log)

Rebuild this analysis from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/topology/TOP-007-20260911-refined-feasibility/analyze.py
```
