# Executed commands

All numerical work ran in `/home/drdeng/Neural_SDF_BEM_AD`, on the existing
`feature/ordered-boundary-nystrom` branch. Python was
`/home/drdeng/miniconda3/envs/EMNerf/bin/python`; BLAS settings were
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`.

The output directories below are immutable evidence. The driver refuses to
reuse an existing output directory.

```bash
python run_topology_recovery_followup.py --phase resolution --output results/validation/topology/TOP-017-followup-20260914-engineering/resolution
python run_topology_recovery_followup.py --phase central --output results/validation/topology/TOP-017-followup-20260914-engineering/central
python run_topology_recovery_followup.py --phase central --repair-of results/validation/topology/TOP-017-followup-20260914-engineering/central --output results/validation/topology/TOP-017-followup-20260914-engineering/central-validated
```

The first two phases measured revision `c4f00ca`. The corrected central
validation measured `5aff98a`. The first central attempt is preserved: an
instrumentation exception wrapper prevented a routine candidate refusal.
The corrected attempt charges that work against the same original budget.

Focused validation:

```bash
python -m pytest -q pytest/sdf_inverse/test_recovery_followup.py pytest/sdf_inverse/test_top017.py pytest/sdf_inverse/test_top016_preflight.py pytest/sdf_inverse/test_top016_screen.py pytest/sdf_inverse/test_top016_optimizer_hooks.py pytest/sdf_inverse/test_top016_pilot.py pytest/sdf_inverse/test_feasible_finite_differences.py
```

Rendering and artifact verification read saved outputs only:

```bash
python results/validation/topology/TOP-017-followup-20260914-engineering/render_central.py
python results/validation/topology/TOP-017-followup-20260914-engineering/verify_followup.py
```
