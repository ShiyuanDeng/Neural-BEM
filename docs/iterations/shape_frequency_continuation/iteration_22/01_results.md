# Iteration 22 — SC-040: the current pipeline on all six scenes, with atlas videos

2026-09-25. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**SC-040 COMPLETE.** [Plan](../iteration_21/03_plan.md),
[evidence](../../../../results/validation/shape_continuation/SC-040-six-scene-pipeline/README.md),
[videos](../../../../results/validation/shape_continuation/videos/README.md).

The user asked for one video per scene through the latest pipeline and
expected satisfactory recovery on all six. Only C and kite had the full path
(SC-035 state band, then SC-038's M 11/15/19 release on all 19 frequencies).
SC-040 ran the rest with those experiments' own functions and settings. All
four new paths complete their schedules at 512/1024 nodes, and every endpoint
audit passes.

| Scene | After state band (mm) | Final RMS (mm) | Tightest radius, final / target (mm) |
|---|---:|---:|---:|
| Circle | 0.00103 | 0.00024 | 49.9 / 50.0 |
| Star | 0.607 | 0.142 | 8.99 / 5.11 |
| C (SC-038) | 0.472 | 0.0241 | 8.55 / 14.6 |
| Kite (SC-038) | 0.574 | 0.110 | 0.091 / 2.14 |
| Peanut | 0.141 | 0.0104 | 15.6 / 13.5 |
| Hook | 0.429 | 0.0297 | 11.9 / 11.7 |

Four scenes reach 0.03 mm or better. Star and kite do not. The SPD-L
baseline still beats this pipeline on circle, star and peanut (about 1e-5 mm),
though it cannot represent C or hook.

The atlas, now rendered along every path, says why star stops. A five-pointed
star carries its content at multiples of 5. At M=11 and M=15 almost none of the
removable misfit waits at M+1…M+3 (4% and 1%). At M=19, 95% waits at m=20–22,
inside the data's resolution: the schedule ends one order short of the star's
next harmonic. Kite's last stage instead ends with 96% of it *inside* the box,
consistent with SC-038's wall-clock stop rather than a band limit. Every
other stage end has at least 81% just above the box.

A provenance caveat: each worker ended on its frozen-source assertion *after*
writing its result and audit, because the assertion hashes the whole package
and the video renderers were edited during the run. None is imported by the
inverse ([`provenance.json`](../../../../results/validation/shape_continuation/SC-040-six-scene-pipeline/provenance.json)).

## Proposed next (not run)

**Star, one more release stage at M=25**, from SC-040's star endpoint, with the
same settings. Prediction: the removable misfit at m=20–22 falls, the tightest
radius moves from 8.99 toward the target's 5.11 mm, and RMS drops below
0.142 mm. If it does not improve, the M+1 reading of the atlas is wrong for
this scene. Kite's open issues (time limit, spurious sharp point) are
unchanged from SC-038.
