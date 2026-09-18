# LAU-003 — derivative-qualified Laurent trace reduction

User-directed innovation screen. [Contract](../../docs/iterations/laurent/iteration_04/03_plan.md)
· [Measured result](../../results/validation/laurent/LAU-003-20260917-closeout/README.md).

Three frozen bases compare forward POD, four analytic state tangents, and
receiver-adjoint closure. All solve the actual reduced dense system and
differentiate the same frozen model. Two evaluation directions and geometry/
acquisition changes do not enter training or rank selection. Existing numerical
packages are read-only imports.

The pilot establishes anchor derivative preservation with 48/194 unknowns,
but compact local reuse fails. The 120-dimensional tangent basis survives both
small geometry offsets, with half the full projected-family storage, while new
illumination fails. No inverse or speed claim. The campaign is **not released**:
one coarse finite-difference row fails its gate; all finer/enriched rows pass.

- `model.py`: training-only basis construction, projected solves and tangents.
- `run.py`: fixed-rank selection, independent Kress evaluation, resources/evidence.
- `test_model.py`: mathematical identities, complex conventions and FD checks.
- `audit.py`: artifact/source hashes, vector-derived gates, rank and budget read-back.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/laurent_tangent_rom
$PY -m experiments.laurent_tangent_rom.run --stage pilot --output /tmp/lau003-new
$PY -m experiments.laurent_tangent_rom.audit /tmp/lau003-new
```
