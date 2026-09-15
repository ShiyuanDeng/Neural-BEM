# TOP-025 owner closeout review

Completed 2026-09-15. Codex `/root`; owner review, no independent-agent review claimed.

**7/12 original scenes pass every recovery and numerical gate.**
Successful scenes: repeated-birth, death, split, merge, mixed, far-two-circles, central-ellipse-star.

## Failed or incomplete scenes

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

## Execution and validation

- The user explicitly requested current-code results and videos for all scenes.
  TOP-025 is a descriptive single-candidate evaluation; TOP-021's old conditional
  matched-comparison gate was not declared passed or bypassed in that code.
- Every scene was freshly initialized from the immutable v1 inputs. Current
  H topology, returned-count K17/K9 capacity and cumulative F used one fixed
  protocol. No diagnostic damping reset, best-iterate choice or scene-specific
  rescue was introduced. No shared solver/default or recovery gate changed.
- 86 source-bound pre-dispatch tests pass, including MP4 encoding. All
  202 measured Python files are archived and verified.
- Saved arrays replay every scored endpoint, accepted-step margin, trajectory,
  terminal gradient association and work ledger with zero new BIE calls.
  Retained geometry reporting is guarded by a zero-call ledger. Missing
  predictions and partial counters remain explicitly unavailable/lower bounds.
- 43,694 charged calls, 42,181
  completed systems, 1,513 failed/refused calls,
  including 1,512 handled geometry refusals.
  Campaign elapsed 90.35 min, at most four BLAS-1
  numerical workers. Timing is descriptive. Exact commands/exits are preserved.
- Twelve scene videos plus one overview were rendered from saved accepted
  states. Every scene ends at its reported retained state; every saved accepted
  record appears at least once. No coefficient interpolation or new numerical
  solve was used. All MP4s pass ffprobe; final overlays and representative
  frames were visually checked. See `video_manifest.json` and `qa/`.

This completes the requested all-case visual inventory. It does not establish
causal improvement over old policies, generalization beyond these development
scenes, or production reliability. No corrective redesign or successor was run.
