# Iteration 02 results — full material topology controller

Follow-up: [revised videos with off-ladder target radii, visible normal refinement, and a 100-mm-circle split](04_visible_refinement.md).

Implemented and demonstrated repeated birth, atomic death, interior-sensitivity split, exterior-sensitivity merge, and automatic restart. All five runs finish as `recovered`, using only observations and their initial explicit geometry to make topology decisions. No target object count or event sequence is supplied to the controller.

[Watch all five inversions](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/topology_changes.mp4) · [Complete result bundle](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/README.md) · [Implementation and numerical conventions](02_implementation.md)

| Video | Component trajectory | Production relative error | Refined relative error | Sampled Hausdorff (mm) |
|---|---|---:|---:|---:|
| [repeated-birth](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/repeated-birth/inversion.mp4) | 0 → 1 → 2 → 3 | 1.62e-07 | 1.62e-07 | 9.251e-06 |
| [death](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/death/inversion.mp4) | 3 → 2 | 1.1e-06 | 1.1e-06 | 4.054e-05 |
| [split](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/split/inversion.mp4) | 1 → 2 | 2.89e-07 | 2.89e-07 | 1.56e-05 |
| [merge](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/merge/inversion.mp4) | 2 → 1 | 7.98e-05 | 7.98e-05 | 0.7227 |
| [mixed](../../../../results/inverse/radial_fourier/topology_controller/iteration-02-20260909/mixed/inversion.mp4) | 2 → 3 → 2 | 4.27e-07 | 4.27e-07 | 1.418e-05 |

The mixed case starts with a connected peanut and a spurious circle. The controller splits the peanut into two children, preserves the unrelated circle, then deletes that circle in the next topology pass. The lineage is `parent → {t001.split1, t001.split2}`, followed by retirement of `spurious`. The pure split is a single `1 → 2` event. The merge replaces both original boundaries with one fitted outer contour before the next Kress solve.

Every accepted event decreases both production and refined Kress objectives. Saved accepted trajectories are monotone up to floating-point roundoff. The videos hold actual accepted states and show discrete transitions, the objective history and component count. Their fixed camera bounds include all trajectory components, including the drifting ghost in the mixed case.

## Validation and recorded scope

- **39 tests pass** across the new topology controller, existing topology/birth/challenge regressions and multi-component Kress tests.
- Manufactured interior fields agree with the shared Green representation. The integrated removal derivative agrees with a uniform-material finite difference within the tested 0.3% relative tolerance.
- Tests cover all four connectivity classes, hole rejection, exact rollback, refined-objective rejection, nonradial Cartesian promotion, mixed-chart vector reconstruction, three-parent merge lineage, thin-neck triggering, and preservation of components outside the inspection raster.
- The suite uses noiseless, same-material observations at 0.5 GHz. Production/refined boundaries use 64/128 nodes and the inspection grid has 121 × 121 points. Circle observations use independent cylindrical harmonics; the ellipse uses a 256-node analytic-boundary Kress reference.
- Per-case manifests record all budgets. The four core runs used a 12-candidate cap per event type; the mixed run used the expanded 48-candidate cap, which is now the controller default. This retains centred and off-centre cuts for actual-objective comparison.
- The final accepted demonstration states use radial charts. Cartesian fallback and optimization are implemented, and a nonradial C contour plus mixed-chart reconstruction are tested; general nonradial inversion recovery is not claimed by these five examples.

Nested holes, touching-boundary quadrature, noise robustness, multi-material reconstruction and global convergence remain outside the demonstrated scope. Finite candidate search can still stop as `topology_stationary`. Earlier development runs exposed both an unresolved radial pinch and incorrect counting of an off-grid component; the final controller has a feature-radius floor and a visible-connectivity regression for these cases.

## Run a fresh suite

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python run_fourier_topology_controller.py \
  --profile full --output results/inverse/radial_fourier/topology_controller/fresh-run
```

Use `--case repeated-birth|death|split|merge|mixed` for one case and `--skip-video` for numerical work. Re-render an existing bundle without solving with `--render-only --output <bundle-directory>`. The named `iteration-02-20260909` and `visible-refinement-20260909` evidence bundles include their MP4 videos, PNG figures, NPZ observations and sensitivity rasters in Git, alongside JSON traces, metrics and manifests. Fresh generated runs retain the repository's default binary ignore policy.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/sdf_inverse/test_topology_controller.py \
  pytest/sdf_inverse/test_radial_topology.py \
  pytest/sdf_inverse/test_radial_topology_challenges.py \
  pytest/gpr_bem_kress/test_multicomponent.py -q
```
