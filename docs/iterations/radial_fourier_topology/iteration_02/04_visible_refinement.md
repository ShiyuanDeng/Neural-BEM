# Revised videos — visible boundary refinement and a large-circle split

[Watch both revised inversions (69 seconds)](../../../../results/inverse/radial_fourier/topology_controller/visible-refinement-20260909/topology_changes.mp4)

## Why the original circle births looked finished immediately

The target radii were not entries in the searched birth ladder. The original three targets were 28, 30 and 27 mm; their closest searched radii were approximately 1.676, 0.324 and 0.873 mm away, respectively. However, the controller performed three local LM steps during candidate scoring before emitting the accepted topology frame. For the last birth, a roughly 19.595-mm raw seed had already become 27.000084 mm by the time it first appeared as an accepted component. The original video omitted those candidate-local steps.

The revised demonstrations set `candidate_refinement_iterations=0`. They accept a raw finite topology candidate only if the production and refined objectives improve, then restart the normal inverse. Every ensuing LM update appears in the video. Dotted contours preserve the accepted topology seeds; solid contours show the current reconstruction, and dashed contours show truth. Circle radii are displayed in millimetres, with one second per regular inverse update.

## Birth radii explicitly between the searched values

[Repeated birth and normal refinement video](../../../../results/inverse/radial_fourier/topology_controller/visible-refinement-20260909/repeated-birth/inversion.mp4)

The fixed birth ladder is **16, 24, 36 and 48 mm**. The synthetic targets are **27.3, 31.7 and 25.9 mm**, respectively 3.3, 4.3 and 1.9 mm from the closest ladder entry. The controller receives the observations and declared ladder; target radii are used only to generate observations and audit the result.

The accepted births use 36, 24 and 24 mm, producing `0 → 1 → 2 → 3`. After the final birth, the third component's radius follows these actual normal-LM iterates:

| Stage | Radius (mm) |
|---|---:|
| Accepted raw birth / LM iteration 0 | 24.000000 |
| LM iteration 1 | 26.065654 |
| LM iteration 2 | 25.823901 |
| LM iteration 3 | 25.900252 |
| LM iteration 4 | 25.900000 |

The other two centres and radii adjust simultaneously. Final production/refined relative data error is approximately `1.01e-9`. The exact searched values and distances to every target are saved in [radius_audit.json](../../../../results/inverse/radial_fourier/topology_controller/visible-refinement-20260909/repeated-birth/radius_audit.json).

## Actual split from one large circle

[100-mm-circle → two components → normal refinement video](../../../../results/inverse/radial_fourier/topology_controller/visible-refinement-20260909/split/inversion.mp4)

The initial geometry is an exact circle centred at `(0.5, 0.5) m` with radius **100 mm**. Both target circles, of radii 31.7 and 36.1 mm, lie entirely inside it. The initial radial Fourier shape modes are zero and can change during ordinary refinement; the inversion does not start with a peanut.

A large-circle cut initially exposed a limitation of the coarse contour conversion: equivalent-area circular seeds for two semicircular regions can overlap, so Kress rejects them. The controller now supports a finite split-seed radius scale search. This demonstration evaluates scales `1, 0.75, 0.5` of each cut region's equivalent-area radius, alongside the full contour fit. These scales use current material-mask geometry and are scored by the actual Kress objective.

The resulting accepted event is a genuine **split, `1 → 2`**, with parent `large_circle` and children `t001.split1`, `t001.split2`. The raw child radii are approximately **36.6241 and 36.3818 mm**. Three visible normal-LM updates move the centres and radii to the two targets. The event itself reduces the objective from `0.514603` to `0.0576707`; subsequent normal refinement reduces it to `5.31e-13`, for relative data error `1.03e-6` at both boundary resolutions. No Cartesian promotion was needed.

Exploratory runs without smaller split seeds recovered through deletion and rebirth. They remain in the bundle under `large-circle-100mm-restart` and `large-circle-115mm-restart` and are not labelled as direct split demonstrations.

## Reproduction and checks

Run either case with the new demonstration flag:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python run_fourier_topology_controller.py \
  --case repeated-birth --demonstration visible-refinement --profile full \
  --output results/inverse/radial_fourier/topology_controller/new-visible-run
```

Then repeat with `--case split` and the same output root. The index combines completed case videos. Historical demonstrations retain `--demonstration original`; re-rendering reads the recorded demonstration and truth from each manifest.

**42 focused tests pass**, including new regressions for the exact fixed birth ladder, off-ladder targets, raw birth visibility before ordinary refinement, the initially circular enclosing geometry, and separated split seeds from a large-circle cut. Both videos were inspected and the combined MP4 decoded without errors. All accepted events improve production and refined objectives; the saved trajectories are monotone.
