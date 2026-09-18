# LAU-004 — protected Laurent spans and guarded reuse

[Contract](../../docs/iterations/laurent/iteration_05/03_plan.md) ·
[Measured closeout](../../results/validation/laurent/LAU-004-20260917-closeout/README.md).

Preserve the primal span (optionally receiver adjoints too), then compress
orthogonal tangent corrections. A guard based on finite-system equation defects
chooses reuse or rebuild; a refused rebuild falls back to the full model.
Neither physical reference outputs nor two evaluation directions enter the
construction, selection or guard. Full current matrices and a dense stability
SVD remain required, so this is not a speed-optimized implementation.

The pilot reduces rank 80→56 / 120→112 on ellipse/star and delivers 42/42 physical
passes through 18 reuses and 24 rebuilds. There are no observed false accepts;
six accurate frozen cases trigger conservative rebuilds. Compact nonanchor
reuse at <=half dimension fails, so the wider campaign is not released.

- `model.py`: protected spans and finite-matrix paired field/tangent bounds.
- `run.py`: training-only selection, physical checks, refresh/fallback policy,
  budgets and source-pinned evidence. Reuses LAU-003's solve/score read-only.
- `audit.py`: vector-derived gates, bound ingredients, ranks and policy read-back.
- `test_model.py`: span, complex-bound and information-isolation checks.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/laurent_adaptive_rom
$PY -m experiments.laurent_adaptive_rom.run --stage pilot --output /tmp/lau004-new
$PY -m experiments.laurent_adaptive_rom.audit /tmp/lau004-new
```
