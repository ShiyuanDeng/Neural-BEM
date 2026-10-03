# Cleaned inverse package checks

These tests check `solvers/bem_inverse` from a fresh process outside the
repository with research imports blocked. They cover standalone nodal/modal
fields, selectable geometry, a bounded audited inverse, module identity, and
historical pickle class lookups.

Run from the repository root:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/bem_inverse experiments/cleaned_interface -q
```

The existing cleaned-interface tests stay with their historical campaign
fixtures. See the [package guide](../../solvers/bem_inverse/README.md) for the
API and additional shared-numerics checks.
