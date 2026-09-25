# SC-040 — the current pipeline on all six development scenes

**COMPLETE, 2026-09-25.** Owner: Claude (Opus 5.5); independent reviewer
unassigned. [Plan](../../../../docs/iterations/shape_frequency_continuation/iteration_21/03_plan.md).
Requested by the user: one video per scene through the latest pipeline.

The pipeline is SC-035's low state band (stages 1–4: 0.5 → 1.25 GHz,
M 3/5/7/9, K 8/12/16/20) followed by SC-038's update-band release (all 19
frequencies, 0.25–2.5 GHz, M 11/15/19, K=192). Before this run only C and kite
had the whole path. SC-040 ran the missing parts using those experiments' own
functions and settings, with nothing tuned:

- circle and hook: the state band from the common start circle (never run
  before), then the release;
- star and peanut: the release from SC-035's saved stage-4 state.

All four completed their schedules at 512/1024 nodes, so the declared
768/1536 replay was not needed. Every endpoint passes SC-038's audit: field
and Jacobian refinement at 2x nodes, and a full-trial finite difference.

| Scene | After state band (mm) | **Final RMS (mm)** | Hausdorff (mm) | Tightest radius (mm), final / target | Mean catalog residual | Source |
|---|---:|---:|---:|---:|---:|---|
| Circle | 0.00103 | **0.00024** | 0.00037 | 49.9 / 50.0 | 2.3e-8 | SC-040 |
| Star | 0.607 | **0.142** | 0.459 | 8.99 / 5.11 | 1.3e-3 | SC-040 |
| C | 0.472 | **0.0241** | 0.115 | 8.55 / 14.6 | 2.3e-4 | SC-038 |
| Kite | 0.574 | **0.110** | 0.445 | 0.091 / 2.14 | 1.1e-4 | SC-038, time-limited |
| Peanut | 0.141 | **0.0104** | 0.030 | 15.6 / 13.5 | 2.2e-6 | SC-040 |
| Hook | 0.429 | **0.0297** | 0.072 | 11.9 / 11.7 | 1.3e-4 | SC-040 |

"After state band" is the stage-4 endpoint (SC-035 for star, C, kite and
peanut; SC-040 for circle and hook). Truth enters only this scoring.

What this does and does not show:

- The release takes circle, C, peanut and hook to 0.03 mm or better, and star
  and kite to about 0.1 mm.
- **Star** completes its schedule (every stage ends on `no_decreasing_step`)
  with blunted tips: tightest radius 8.99 mm against the target's 5.11 mm, and
  the largest remaining catalog residual of the six.
- **Kite** is SC-038's endpoint. It hit its wall-clock limit while still
  improving, and it has a spurious sharp feature (radius 0.091 mm against
  2.14 mm).
- **The SPD-L baseline** (SC-034) recovers circle, star and peanut to about
  1e-5 mm, far better than this pipeline on those three. Its polar-angle
  parameter cannot represent C or hook, and it stops early on kite. These are
  development scenes, not a generalization test.

## Runs

| Scene | Path units (prefix + release) | Release seconds | Release stages (stop, accepted steps) |
|---|---:|---:|---|
| Circle | 353 | 294 | M11 no_decreasing_step 1 · M15 loss_tolerance 1 · M19 loss_tolerance 0 |
| Star | 652 | 649 | M11 no_decreasing_step 3 · M15 no_decreasing_step 2 · M19 no_decreasing_step 1 |
| Peanut | 940 | 996 | M11 no_decreasing_step 2 · M15 no_decreasing_step 2 · M19 no_decreasing_step 3 |
| Hook | 825 | 746 | M11 no_decreasing_step 3 · M15 no_decreasing_step 3 · M19 no_decreasing_step 2 |

Per scene, `runs/<scene>/` holds the state-band run (circle, hook), the
release (`release_m/`, with every stage history, configuration and
`result.json`) and `audit.json`.

**Provenance note.** Each worker ended on its own frozen-source assertion
*after* writing `result.json` and `audit.json`; each `failure.json` records
this. The assertion hashes every `experiments/shape_continuation/*.py`, and
during the run the video renderers (`render_videos.py`, `atlas_video.py`, new
`pipeline_video.py`) were edited for the videos. None of them is imported by
the inverse, scoring or audit. [`provenance.json`](provenance.json) lists the
changed hashes.

## Atlas data

`collect` stores SC-039-format data (traces, reciprocal traces, geometry and
full predictions at all 19 frequencies on 512 and 1024 nodes) for each of the 54
new accepted states in `shots/` (not in Git). The other 146 states of the six
trajectories are reused from SC-039. [`trajectories.json`](trajectories.json)
lists every accepted state of the six selected paths in SC-039's format; the
[six videos](../videos/README.md) are rendered from it.

## Reproduce

EMNerf, repository root. Existing run folders are refused.

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-040-six-scene-pipeline/run.py run
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-040-six-scene-pipeline/run.py collect
PYTHONPATH=solvers:. python -m experiments.shape_continuation.pipeline_video
```
