> Frozen-initialization evidence supplied for iteration 2. This does not
> reproduce the missing production traceback or establish its exact cause.

# Archived ellipse initialization: geometry probe — 2026-09-08

The archived September 7 initial ellipse SIREN fails both conversion checks under the September 8 suite's geometry settings. This supports an initial conversion-failure explanation for the empty September 8 ellipse result directory. **It does not establish that run's original exception:** its freshly pretrained weights and traceback were not saved.

[probe.py](../../../../../results/validation/implicit_mlp_adjoint/iteration-02-20260908/ellipse-initial-geometry/probe.py) loads the archived initialization vector from [the September 7 metrics](../../../../../results/inverse/implicit_mlp/2026-09-07/ellipse-to-circle/metrics.json), checks its parameter order, and applies the settings parsed from [the September 8 suite record](../../../../../results/inverse/implicit_mlp/2026-09-08/wrong_start_suite.json). It runs geometry construction only: zero pretraining steps, inverse updates, or BEM forward solves. Weights remain exactly unchanged.

| Geometry check | Measured | Limit |
|---|---:|---:|
| Raw/converted contour distance | 3.211626 mm | 0.2 mm |
| Conversion refinement change | 0.073997 mm | 0.01 mm |

The probe raises `OrderedSDFGeometryError` with `conversion_distance` and `conversion_refinement_change`. Settings: 64 nodes, bandwidth 20, grid 257 × 257, 128 projected samples, 512 arc-length integration samples, and validation resolution 256. Geometry runtime: **7.508 seconds**.

[probe.json](../../../../../results/validation/implicit_mlp_adjoint/iteration-02-20260908/ellipse-initial-geometry/probe.json) records full precision values, the exception from this new probe, archived vector and source-file SHA-256 hashes, constructor and geometry settings, the recorded failed-run command, environment/package versions, current relevant source hashes, runtime, and the attribution caveat. The vector hash uses little-endian float64 values in the archived parameter-name order.

Run from the repository root:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/implicit_mlp_adjoint/iteration-02-20260908/ellipse-initial-geometry/probe.py
```

The script refuses to replace `probe.json`; preserve the saved record under a different name before repeating it. Compare the recorded source hashes when reproducing after code changes.
