# Six development cases: inversion videos

Each video shows three inversions side by side, from the common start circle
through stages 1–4 (0.5 GHz, then 0.75, 1.0 and 1.25 GHz added one per stage)
to the final states:

- **Original hybrid**: SC-029's baseline (normal steps, K=192), which SC-036
  replays bitwise.
- **State band**: the SC-035 low arm (K 8/12/16/20, then a K=192 release stage).
  It was run on peanut, C, star and kite only, so the circle and hook panels
  say so.
- **SPD-L**: SC-034's arm L, the adopted SPD reference. Its state is a Cartesian
  Fourier curve with band K 4/6/8/10 whose parameter is fixed to the polar angle,
  so it selects K directly and only holds star-shaped curves.

Every saved accepted state is shown, with no interpolation and no new field
solves. A panel holds its last state when a run takes no step in a stage or
has stopped. The dashed target and the RMS readout are evaluation only; the
RMS uses the same metric as each run's saved score. Rendering stops unless
every video ends at the scored endpoint and reproduces its recorded RMS.

| Case | Video | Final frame | Original hybrid RMS (mm) | State band RMS (mm) | SPD-L RMS (mm) |
|---|---|---|---:|---:|---:|
| Circle | [wrong_circle.mp4](wrong_circle.mp4) | [png](wrong_circle_final.png) | 0.0026 | not run | 7.6e-6 |
| Star | [circle_to_star.mp4](circle_to_star.mp4) | [png](circle_to_star_final.png) | 0.522 | 0.607 | 3.3e-5 |
| C (not star-shaped) | [circle_to_c.mp4](circle_to_c.mp4) | [png](circle_to_c_final.png) | 3.20 | 0.472 | 10.1, hard stop |
| Kite | [kite.mp4](kite.mp4) | [png](kite_final.png) | 2.98 | 0.574 | 1.25, hard stop |
| Peanut | [peanut.mp4](peanut.mp4) | [png](peanut_final.png) | 2.94 | 0.141 | 1.2e-5 |
| Hook (not star-shaped) | [hook.mp4](hook.mp4) | [png](hook_final.png) | 0.525 | not run | 9.36, hard stop |

SPD-L's hard stops are `UNRESOLVED_DERIVATIVE`; its polar-angle parameter
cannot represent C or hook. All other runs complete their schedules. Playback time is
not solve time. These are development cases, not a generalization test.

![Peanut, final states](peanut_final.png)

Rebuild all six (about a minute, EMNerf, repository root):

```bash
PYTHONPATH=solvers:. python -m experiments.shape_continuation.render_videos
```

[`manifest.json`](manifest.json) records the renderer and input hashes, the
number of accepted states per panel, and each video's ffprobe check.
