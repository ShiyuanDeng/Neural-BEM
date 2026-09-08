# Iteration 3: completed long acquisition comparison

The long command finished successfully at 19:47:02 British Summer Time on
September 8, 2026. Both inverse results and all scheduled posthoc diagnostics
are saved; neither inverse converged. Paired accepted 42 updates and multistatic
31, both stopping at `no_decreasing_neural_step` before their work caps.

The self-contained research record is
[iteration 3 results](../../../../docs/iterations/implicit_mlp/iteration_03/01_results.md).
Raw artifacts remain in the original
[long run directory](../iteration-02-final/long-acquisition-20260908T174300326691Z/).
No inverse, BEM, extraction or gradient evaluation ran for this review.

| Evidence | Contents |
|---|---|
| [completion.json](completion.json) | Exit/status, qualification, timestamps, checkpoint/optimizer/trajectory counts and input hashes |
| [Geometric findings](motion-review/findings.md) | Raw/converted symmetric distances, matched work, mode-5 phase/amplitude and finite-probe coverage |
| [Full saved-motion review](motion-review/motion_review.json) | Per-state measurements, formulas and source hashes |
| [Terminal review](terminal-review/terminal_review.md) | Exact final candidate gates, field conditioning and exact replay of both short-run prefixes |
| [Terminal candidates](terminal-review/terminal_candidates.json) | All 60 rejected terminal trials, preserving specific failure stages |
| [Optimizer review](optimizer-review/optimizer_review.md) | Actual Adam state and proposal geometry, fallback resets and evidence limitations |
| [Comparison figure](comparison.png) | Final contours, work, evaluation, lobe amplitude, field spread and conversion distances |

`plot_results.py` produces the PNG and PDF figure from saved data.
`terminal-review/terminal_review.py` and
`optimizer-review/optimizer_review.py` reproduce the read-only arithmetic.
The reusable
[motion-review script](../iteration-02-acquisition-review/motion_review.py)
accepts the original long `--run-dir` and a fresh `--output-dir`; the generated
JSON preserves its reproduction arguments and hashes. Scripts and raw artifacts
stay here under `results/`, while the iteration folder contains the stage record.

Final symmetric raw RMS error is 14.097 mm paired and 9.506 mm multistatic.
The latter's mode-5 amplitude nevertheless shrinks to 1.530 mm against 12.5 mm
truth. Paired's final polar spectrum is unavailable. These are completed
experiments with unresolved recovery, not grounds to launch another long run
without reviewing the next proposed change.
