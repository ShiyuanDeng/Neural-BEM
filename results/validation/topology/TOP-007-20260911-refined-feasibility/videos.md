# TOP-007 videos — the refined feasibility guard on all twelve scenes

One video per guarded run, plus the default arm on the two scenes whose outcome
the guard changed. Each frame is an actual accepted state from the run's saved
trajectory: the left panel draws truth dashed and the current components solid,
the right panels track the Kress data objective and the component count. These
were rendered after the suite from saved states; **no inversion or forward
solve was rerun** ([record](videos.json)).

## Start here — what the fix changed

| | Video | What happens |
|---|---|---|
| **Before** | [A / far-ellipse-star](runs/A/far-ellipse-star/inversion.mp4) | Distant 75-mm circle → ellipse + star. Three circles form; two drift within 9.971 mm of each other, and the run dies on the refined quadrature check at cycle 4 |
| **After** | [G / far-ellipse-star](runs/G/far-ellipse-star/inversion.mp4) | The same scene and the same data. The guard refuses the steps that close that gap, the controller **merges** the pair instead, and the run finishes with the correct 2/2 object count — in the wrong shapes, 18.62 mm out |
| **Before** | [A / empty-ellipse-star](runs/A/empty-ellipse-star/inversion.mp4) | Empty start → ellipse + star. Same death, same 9.971-mm clearance, 22 saved states |
| **After** | [G / empty-ellipse-star](runs/G/empty-ellipse-star/inversion.mp4) | Finishes, and lands on the same two components as the distant start above to within 1e-8 m |

The two "after" runs are the whole result in one picture: the crash is gone, the
object count is right, and what is left is that a circle and a mode-9 curve are
standing in for a star and an ellipse.

## Every guarded scene

| Scene | Video | Outcome | Objects | Matched error |
|---|---|---|---|---:|
| Empty start → three circles | [G / repeated-birth](runs/G/repeated-birth/inversion.mp4) | recovered | 3/3 | 9.26e-06 mm |
| Remove a spurious circle | [G / death](runs/G/death/inversion.mp4) | recovered | 2/2 | 4.06e-05 mm |
| Peanut → two circles | [G / split](runs/G/split/inversion.mp4) | recovered | 2/2 | 0.175 mm |
| Two circles → one ellipse | [G / merge](runs/G/merge/inversion.mp4) | recovered | 1/1 | 0.554 mm |
| Split a peanut and remove a circle | [G / mixed](runs/G/mixed/inversion.mp4) | recovered | 2/2 | 1.42e-05 mm |
| Distant large circle → two circles | [G / far-two-circles](runs/G/far-two-circles/inversion.mp4) | recovered | 2/2 | 6.85e-05 mm |
| Distant large circle → ellipse + star | [G / far-ellipse-star](runs/G/far-ellipse-star/inversion.mp4) | topology_stationary | 2/2 | 18.62 mm |
| Central circle → ellipse + star | [G / central-ellipse-star](runs/G/central-ellipse-star/inversion.mp4) | **timeout** | 5/2 at the last saved state | 22.7 mm |
| Enclosing circle → ellipse + star | [G / enclosing-ellipse-star](runs/G/enclosing-ellipse-star/inversion.mp4) | **timeout** | 5/2 at the last saved state | 148.9 mm |
| Empty start → ellipse + star | [G / empty-ellipse-star](runs/G/empty-ellipse-star/inversion.mp4) | topology_stationary | 2/2 | 18.62 mm |
| Distant large circle → 5- and 7-lobed stars | [G / far-two-stars](runs/G/far-two-stars/inversion.mp4) | topology_stationary | 2/2 | 7.60 mm |
| Distant large circle → ellipse + star + circle | [G / far-three-shapes](runs/G/far-three-shapes/inversion.mp4) | **timeout** | 5/3 at the last saved state | 57.7 mm |

Only five of these pass every gate; the table above reports geometry, and the
[full report](README.md) reports each gate separately. A timed-out video ends on
the last state that was saved before the ten-minute ceiling, labelled as failed —
it is not a finished reconstruction, and how far it got depends on machine load.

## Why the default arm has only two videos

On the seven scenes where both arms completed, they returned **identical final
states**, so a second video would be the same animation. Those scenes are listed
once, under the guarded arm, and the default arm's numbers are in the
[per-scene table](README.md#per-scene-outcomes). The default arm's three timeouts
are also omitted here: they neither changed nor finished. Rebuild any missing
video from saved states with

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-007-20260911-refined-feasibility/render_videos.py
```
