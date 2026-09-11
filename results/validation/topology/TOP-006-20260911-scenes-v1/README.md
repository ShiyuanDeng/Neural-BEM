# TOP-006 — current automatic controller on twelve frozen scenes

This is a measurement of the existing default A and selective F, with no controller changes or scene-specific tuning.

**Both policies pass 5/12 scenes.** All 24 declared runs were attempted: fourteen returned normally, four stopped with a geometry exception, and six reached the ten-minute limit. Ten normal returns pass all quality gates; the merge and two-star scene fail in both policies.

The requested distant 75-mm-radius circle does **not** recover the ellipse and star. Both policies find their approximate locations but represent them with circles, add a third small circle, and then fail the refined separation check (9.971 mm against a required >10 mm). The true objects are separated; the error is in an inferred intermediate geometry. The last saved state has 0.695 material IoU and 17.59-mm maximum matched boundary error.

The same distant initialization succeeds for two circular targets. Two stars also expose a count-versus-shape distinction: both policies return two circles, with 7.60-mm boundary error and 100.3% error at the 2.5-GHz holdout. The original merge looks close (0.554-mm boundary error) but fails the new 5% holdout gate at 9.40%. Its previous qualification was relative to the old baseline and is preserved, not relabeled retroactively.

[Requested distant-circle comparison](far_ellipse_star_failure.svg) · [All initial scenes](initial_scenes.svg) · [New scene results](new_results.svg) · [Original controls](original_results.svg) · [Error and work](error_and_work.svg)

[Default requested-scene video](runs/A/far-ellipse-star/inversion.mp4) · [Selective requested-scene video](runs/F/far-ellipse-star/inversion.mp4)

## Per-scene outcomes

| Scene | Arm | Pass | Objects / truth | Matched error (mm) | Union IoU | Refined train error | Worst holdout error | BIE solves | Stop |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| [repeated-birth](runs/A/repeated-birth/metrics.json) | A | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 759 | recovered |
| [repeated-birth](runs/F/repeated-birth/metrics.json) | F | PASS | 3 / 3 | 9.2617e-06 | 1.0000 | 1.621e-07 | 1.116e-06 | 835 | recovered |
| [death](runs/A/death/metrics.json) | A | PASS | 2 / 2 | 4.0575e-05 | 0.9987 | 1.103e-06 | 5.4e-06 | 811 | recovered |
| [death](runs/F/death/metrics.json) | F | PASS | 2 / 2 | 4.0575e-05 | 0.9987 | 1.103e-06 | 5.4e-06 | 907 | recovered |
| [split](runs/A/split/metrics.json) | A | PASS | 2 / 2 | 0.17521 | 0.9954 | 6.873e-06 | 0.01128 | 1172 | recovered |
| [split](runs/F/split/metrics.json) | F | PASS | 2 / 2 | 2.5911e-05 | 0.9987 | 7.524e-07 | 3.586e-06 | 616 | recovered |
| [merge](runs/A/merge/metrics.json) | A | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 553 | recovered |
| [merge](runs/F/merge/metrics.json) | F | FAIL | 1 / 1 | 0.55416 | 0.9934 | 7.879e-05 | 0.09398 | 581 | recovered |
| [mixed](runs/A/mixed/metrics.json) | A | PASS | 2 / 2 | 1.42e-05 | 0.9987 | 4.283e-07 | 2.075e-06 | 1360 | recovered |
| [mixed](runs/F/mixed/metrics.json) | F | PASS | 2 / 2 | 1.42e-05 | 0.9987 | 4.283e-07 | 2.075e-06 | 1384 | recovered |
| [far-two-circles](runs/A/far-two-circles/metrics.json) | A | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2019 | recovered |
| [far-two-circles](runs/F/far-two-circles/metrics.json) | F | PASS | 2 / 2 | 6.8497e-05 | 1.0000 | 1.421e-06 | 9.064e-06 | 2305 | recovered |
| [far-ellipse-star](runs/A/far-ellipse-star/failure.json) | A | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥2255 | exception |
| [far-ellipse-star](runs/F/far-ellipse-star/failure.json) | F | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥2255 | exception |
| [central-ellipse-star](runs/A/central-ellipse-star/failure.json) | A | FAIL | 6 / 2† | 25.821† | 0.4671† | — | — | ≥4210 | timeout |
| [central-ellipse-star](runs/F/central-ellipse-star/failure.json) | F | FAIL | 5 / 2† | 22.718† | 0.5211† | — | — | ≥3978 | timeout |
| [enclosing-ellipse-star](runs/A/enclosing-ellipse-star/failure.json) | A | FAIL | 6 / 2† | 148.94† | 0.1742† | — | — | ≥3812 | timeout |
| [enclosing-ellipse-star](runs/F/enclosing-ellipse-star/failure.json) | F | FAIL | 6 / 2† | 148.94† | 0.1742† | — | — | ≥4003 | timeout |
| [empty-ellipse-star](runs/A/empty-ellipse-star/failure.json) | A | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥600 | exception |
| [empty-ellipse-star](runs/F/empty-ellipse-star/failure.json) | F | FAIL | 3 / 2† | 17.587† | 0.6947† | — | — | ≥600 | exception |
| [far-two-stars](runs/A/far-two-stars/metrics.json) | A | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | topology_stationary |
| [far-two-stars](runs/F/far-two-stars/metrics.json) | F | FAIL | 2 / 2 | 7.5951 | 0.7468 | 0.01358 | 1.003 | 1548 | topology_stationary |
| [far-three-shapes](runs/A/far-three-shapes/failure.json) | A | FAIL | 6 / 3† | 53.588† | 0.2314† | — | — | ≥4098 | timeout |
| [far-three-shapes](runs/F/far-three-shapes/failure.json) | F | FAIL | 6 / 3† | 54.574† | 0.2293† | — | — | ≥4291 | timeout |

† Failed-run quantities describe the last saved accepted state, not a qualified final solution. Their solve counts are lower bounds; full candidate trials are unavailable after an uncaught controller exception. Saved progress records and tracebacks remain intact. No physics was rerun to fill missing fields.

Matched error uses one-to-one minimum-cost component assignment and boundary-to-polyline distances. When counts differ, unmatched components are not in that distance; the independent count and material-union overlap gates prevent a misleading pass.

## Protocol and verification

The [pre-execution plan](../../../../docs/iterations/topology/iteration_03/03_plan.md) and [frozen specification](scene_spec.json) define all scenes, budgets and gates. Use [the benchmark instructions](../../../../docs/benchmarks/topology_scenes.md) for future comparisons.

All 24 inversions use the current Cartesian automatic controller: 0.5-GHz training, 24 paired ring measurements, 64/128 nodes, ten cycles, seven events and unchanged acceptance rules. 1.5/2.5-GHz predictions are evaluation-only. No count, truth shape or prescribed event enters inversion. The two arms share the exact observations and initial state for each scene.

Noncircular observations use analytic boundaries at 256 nodes and the same Kress solver, checked at 512 nodes. Circular scenes use independent cylindrical harmonics. This is noiseless, separated, same-material 2-D evidence; the star is a smooth lobed boundary, not a sharp polygon.

Birth proposals in the current automatic controller remain circular; surviving components are not generally promoted to richer shape modes. The older prescribed ellipse/star challenge used explicit mode and frequency schedules. Missing automatic shape adaptation and refined feasibility of inner optimizer updates are next questions; neither is fixed by this measurement.

Four single-thread inversion subprocesses may run concurrently. Solve counts exclude oracle and final evaluation work; elapsed times are not a controlled speed comparison. The inverse test suite also ran concurrently for about 72 seconds, and saved failure videos were rendered while later inversions ran. Per-run timeout is ten minutes; the inversion suite ceiling is 45 minutes. Solve counts are not weighted by matrix dimension, and failed-run counts are only checkpoint lower bounds.

All 155 measured source files were checked before any post-run changes ([checks](pre_reporting_source_verification.json)). The exact [executed harness](executed_run_topology_scene_benchmark.py) is archived for source identity. After all jobs stopped, the working harness gained failed-state rendering, unclipped plots, partial-work reporting and a frozen-data reuse option ([change record](postrun_reporting_changes.json)). AST checks confirm the inversion, geometry metrics, gates, budgets and job execution functions are unchanged. No inversion was rerun. The archive is a source snapshot, not a standalone entry point in this result directory.

Artifact verification: **PASS**. [Machine-readable checks](verification.json) recheck source/observation hashes, paired inputs, original-control reproduction and outcome gates. This is an independent re-reading of artifacts by the implementation owner, not independent scientific review. Reviewer: unassigned.

[Tests](tests.log) · [Execution](execution.log) · [Full metrics](suite_metrics.json)

Rebuild this analysis from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/topology/TOP-006-20260911-scenes-v1/analyze.py
```
