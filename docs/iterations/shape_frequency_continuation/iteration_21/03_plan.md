# SC-040 plan — the current pipeline on all six development scenes

2026-09-25. Owner: Claude (Opus 5.5). Requested directly by the user: one video
per scene, "based on those trajectories" with the extra continuation, and a
clean videos folder.

## Question

Does the current pipeline recover all six development scenes, and what does
the atlas show along each path? The pipeline is SC-035's low state band
(stages 1–4: 0.5 → 1.25 GHz, M 3/5/7/9, K 8/12/16/20) followed by SC-038's
update-band release (all 19 frequencies, M 11/15/19, K=192). Only C and kite
have the complete path today.

## Runs (settings copied, nothing tuned)

| Scene | State-band prefix | Release |
|---|---|---|
| C, kite | reuse SC-035 | reuse SC-038 (kite: its recorded 768/1536 path) |
| Star, peanut | reuse SC-035 stage 4 | **new** |
| Circle, hook | **new**, SC-035 `low` worker settings (stage 1: 600 units / 900 s; stages 2–4: 3,000 units total / 2,700 s total) | **new** |

A new release uses SC-038's `schedules(case, 'release_m')`, ProjectedUpdate,
512/1024 nodes and `Ledger(cap=4500, seconds=1800)`. SC-035's
`stage_5_release_repeat` is not run: SC-038 starts from the stage-4 state.

Declared before any result: if a release stage hard-stops on the 512/1024
field gate, the remaining release stages are replayed once at 768/1536 nodes
from the last completed stage's endpoint, with the unspent units and 1,800 s.
This is the rule SC-038 applied to kite. There is no other retry, no tolerance
or band change, and no truth-based selection. Truth enters only in scoring
after a run returns.

## Checks

- Every new endpoint: SC-038's audit (field and Jacobian refinement at
  2x nodes, full-trial finite difference).
- SC-039-format data for every new accepted state (512/1024, plus
  768/1536 if a dense replay occurs), with the same integrity checks as the
  atlas renderer: saved losses rebuilt from stored predictions, and 2x-node
  display agreement.

## Outputs

`results/validation/shape_continuation/SC-040-six-scene-pipeline/` (runs,
new shots, summary), and six videos in
`results/validation/shape_continuation/videos/`: shape against target,
the atlas, and the state strip for one trajectory per scene. The earlier
three-method comparison videos move to `videos/three_method_comparison/`
unchanged.

"Satisfactory" is not a pre-declared threshold. Every endpoint RMS,
Hausdorff distance and minimum curvature radius is reported, including any
that stay poor.
