# TOP-006 — frozen multi-scene automatic-controller benchmark

- **Approval status:** APPROVED by the user's 2026-09-11 request to test a
  distant circle against ellipse/star targets and use more scenes in future.
- **Execution status:** COMPLETE. [Iteration 04 results](../iteration_04/01_results.md).
- **Owner:** Codex. **Independent reviewer:** unassigned.
- **Baseline:** `f391eb3`, merged into `feature/ordered-boundary-nystrom`.
- **Branch:** continue `feature/ordered-boundary-nystrom` per the session's
  branch consolidation; no new branch.
- **Review:** [decisions](02_proposals/02_scene_benchmark_review.md).

## Question and frozen comparison

Does the current automatic controller recover the right number and shapes from
unhelpful starts beyond the two-circle split? The hypothesis that selective F
generalizes is falsified by any new-scene failure of the declared checks;
compare its per-scene outcomes with default A rather than requiring a win.

Use `config/topology_scenes_v1.json`: five original controls plus seven new
scenes, two arms A/F, 24 full Cartesian inversions. Both arms use the same
0.5-GHz, 24-pair ring observations, noiseless exterior/interior materials,
64/128 production/refined nodes, raster 121, 22 fixed iterations, three
candidate steps, ten cycles, seven events, cap 48 and tolerance 0.003. Only
`include_simplest_candidate` differs. Initial circles in new scenes have
zero-initialized radial modes through K=2, converted to Cartesian identically;
there is no truth-dependent bandwidth promotion or prescribed topology event.

New-scene truth definitions and initial states are fixed before any inversion.
The far circle has radius 75 mm and is disjoint from both ellipse/star targets.
Its entire boundary and all targets fit the unchanged 200-mm inspection disk.
The oracle check compares 256/512-node predictions for noncircular targets at
0.5/1.5/2.5 GHz; maximum per-frequency relative difference must be <=1e-5.
All-circle targets use the independent cylindrical-harmonic oracle. Holdout
frequencies 1.5/2.5 GHz are evaluation-only and never reach optimization.

## Measures, budget and artifacts

Success requires correct component count; maximum matched symmetric
boundary-to-polyline distance <=1 mm; material-union IoU >=0.90 on a fixed
401-square grid spanning [0.2,0.8]^2; refined training relative L2 <=0.003;
maximum per-frequency holdout relative L2 <=0.05; and verified monotone
accepted states/cross-resolution event margins. Boundary distances use 1024
samples/segments per component with minimum-cost one-to-one assignment.
Keep the older qualification labels separate because these checks are stricter.

Maximum 24 inversions, four single-thread subprocess workers, ten-minute
per-inversion timeout and 45-minute suite wall ceiling. Timeouts/errors retain
checkpoints and count as failures. Oracle/setup and rendering are separately
recorded; solve-count comparisons exclude them. Stop on invalid oracle/scene
setup; never tune scenes or thresholds after observing inversion failures.

Touch only a new benchmark driver, scene JSON, benchmark tests and
documentation. No numerical-library or controller-interface changes.
Artifacts: fresh `results/validation/topology/TOP-006-20260911-scenes-v1/`,
portable observations and hashes, complete trajectories/trials, per-scene
metrics, a visual contact sheet, error/cost figure and distant ellipse/star
videos. Results open iteration 04. Future performance evaluations must report
the complete v1 scene matrix, preserve failed rows, and name any changed
acquisition/budget as a separate comparison.

## Closeout record

All 24 runs were attempted with the original contract: fourteen normal
returns, four geometry exceptions, six timeouts. Both policies pass 5/12 scenes.
No numerical controller change or inversion rerun followed the failures.
After all jobs stopped, benchmark reporting was improved to retain visible
failed states/work lower bounds and reuse frozen observations in future runs.
The exact executed harness is archived; source/AST checks separate those
post-run reporting changes from the measured implementation. See the results
for missing full trial diagnostics on aborted runs and the new questions.
