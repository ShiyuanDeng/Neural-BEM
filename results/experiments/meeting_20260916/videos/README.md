# Updated reconstruction videos

[All twelve topology scenes](all_scenes.mp4) · [Material scene overview](materials/all_material_scenes.mp4)

Videos show saved states and finish at the scored endpoints. Promotion and proposed-birth trials are labelled. Playback time is independent of computation time.

## Topology scenes

| Scene | Result | Boundary error (mm) |
|---|---|---:|
| [Empty start → three circles](repeated-birth.mp4) | PASS | 2.0665e-06 |
| [Remove a spurious circle](death.mp4) | PASS | 1.1838e-06 |
| [Peanut → two circles](split.mp4) | PASS | 2.703e-05 |
| [Two circles → one ellipse](merge.mp4) | PASS | 0.10199 |
| [Split a peanut and remove a circle](mixed.mp4) | PASS | 1.7684e-07 |
| [Distant large circle → two circles](far-two-circles.mp4) | PASS | 1.1349e-06 |
| [Distant large circle → ellipse + star](far-ellipse-star.mp4) | PASS | 0.052329 |
| [Central circle → ellipse + star](central-ellipse-star.mp4) | PASS | 0.052392 |
| [Enclosing circle → ellipse + star](enclosing-ellipse-star.mp4) | PASS | 0.052392 |
| [Empty start → ellipse + star](empty-ellipse-star.mp4) | PASS | 0.052329 |
| [Distant large circle → 5- and 7-lobed stars](far-two-stars.mp4) | PASS | 0.0016747 |
| [Distant large circle → ellipse + star + circle](far-three-shapes.mp4) | PASS | 0.046702 |

## Material scenes and noise variants

| Run | Objects | Noise | Acquisition | Seed |
|---|---:|---:|---|---:|
| [empty start clean](materials/mixed_empty_start_clean.mp4) | 2 | 0% | Ring, 0.12 rad offset | 16092026 |
| [empty start 1pct](materials/mixed_empty_start_1pct.mp4) | 2 | 1% | Ring, 0.12 rad offset | 16092026 |
| [empty start 5pct](materials/mixed_empty_start_5pct.mp4) | 2 | 5% | Ring, 0.12 rad offset | 16092027 |
| [empty one metal](materials/mixed_empty_one_metal.mp4) | 1 | 1% | Ring, 0.12 rad offset | 16092026 |
| [empty three objects](materials/mixed_empty_three_objects.mp4) | 3 | 1% | Ring, 0.12 rad offset | 16092026 |
| [empty swapped](materials/mixed_empty_swapped.mp4) | 2 | 1% | Ring, 0.12 rad offset | 16092026 |
| [empty project acquisition](materials/mixed_empty_project_acquisition.mp4) | 2 | 1% | Project | 16092026 |
| [project 5pct](materials/mixed_project_5pct.mp4) | 2 | 5% | Project | 16092026 |
| [project 1pct seed2](materials/mixed_project_1pct_seed2.mp4) | 2 | 1% | Project | 16092027 |
| [project 5pct seed2](materials/mixed_project_5pct_seed2.mp4) | 2 | 5% | Project | 16092027 |

The first two noisy material runs saved only accepted birth geometries; their clips show those states explicitly. The later runs include the saved optimizer steps. Metal is ideal PEC; the material search assumes circles and a known material library.

[VLC-compatible playlist](all_videos.m3u)
