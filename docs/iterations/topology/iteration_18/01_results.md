# TOP-025 — latest integrated pipeline across all twelve scenes

Completed 2026-09-15 under the user's request for current-code videos of successes
and failures and the [iteration-17 plan](../iteration_17/03_plan.md).

**7/12 fresh scenes pass every original recovery and numerical gate.**
Successful scenes: repeated-birth, death, split, merge, mixed, far-two-circles, central-ellipse-star.

[All-scene gallery and scores](../../../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/README.md) ·
[Overview video](../../../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/videos/all_scenes.mp4) ·
[Final contact sheet](../../../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/all_scenes.png).

## What still fails

- **far-ellipse-star**: wrong component count; boundary > 1 mm or unmatched; IoU < 0.90; final prediction score unavailable; numerical qualification incomplete/failed; continuation incomplete; NUMERICAL_FAILURE.
  Recorded stop detail: automatic endpoint infeasible at continuation nodes.
- **enclosing-ellipse-star**: wrong component count; boundary > 1 mm or unmatched; IoU < 0.90; final prediction score unavailable; numerical qualification incomplete/failed; topology handoff incomplete/failed; continuation incomplete; TRIAL_WALL_LIMIT.
  Recorded stop detail: hard wall limit during numerical batch.
- **empty-ellipse-star**: wrong component count; boundary > 1 mm or unmatched; IoU < 0.90; final prediction score unavailable; numerical qualification incomplete/failed; continuation incomplete; NUMERICAL_FAILURE.
  Recorded stop detail: automatic endpoint infeasible at continuation nodes.
- **far-two-stars**: boundary > 1 mm or unmatched; IoU < 0.90; development error > 0.05.
  Recorded stop detail: next complete batch and endpoint reserve exceed planned stage quota.
- **far-three-shapes**: wrong component count; boundary > 1 mm or unmatched; IoU < 0.90; final prediction score unavailable; numerical qualification incomplete/failed; topology handoff incomplete/failed; continuation incomplete; TRIAL_WALL_LIMIT.
  Recorded stop detail: hard wall limit during numerical batch.

## Scope and verification

One fixed current H → cumulative-F pipeline, original starts and observations,
256/512 continuation, and returned-count K17/K9 capacity were used throughout.
No saved optimized starts, supplied count, case-specific rescue or damping reset.
TOP-025 was explicitly authorized as an all-case evaluation despite TOP-024's
negative result; TOP-021's conditional matched comparison remains undispatched.

86 pre-dispatch tests pass. All twelve rows, source/input hashes, saved
predictions, events, gradients, acceptance margins and work replay are verified.
New work: 43,694 charged calls / 42,181
completed systems. Elapsed 90.35 min with up to four
BLAS-1 numerical workers. Twelve per-scene videos and one overview contain only
saved accepted states and pass encoding/provenance checks.

This is a completed visual performance inventory, not a matched comparison or
promotion decision. Review the scene-level evidence before choosing further work.
