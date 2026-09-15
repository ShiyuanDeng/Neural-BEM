# BIE-006 — first-order operator reuse

Experiment-local E/T/O diagnostic using unchanged single-interface production
factories and their analytic operator derivative. No inverse/controller changes.

- Contract: [iteration 03 plan](../../docs/iterations/boundary_bie/iteration_03/03_plan.md).
- Result: [BIE-006 bundle](../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md).
- Decision: **STOP_FIRST_ORDER_OPERATOR_REUSE** on this bounded test.

## Files

`fixtures.py` selects chronological saved geometry without reading objective or
truth values. `models.py` implements T/O algebra. `support.py` counts production
assembly, LU and batched solves and protects measured sources. `run.py` freezes
inputs, conducts the bounded campaign and retains raw predictions.
`summarize.py` replays saved arrays and work counts, then rebuilds tables/figures.

## Commands

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  experiments/bie006_operator_reuse/test_models.py

# Reporting only: no new physical solves.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.bie006_operator_reuse.summarize \
  results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse
```

The physical campaign has completed its approved scope and exact-assembly
budget. Its exact command and source snapshots are in the bundle; rerunning
physics is not required for reporting. Four tests use synthetic matrix algebra
and Fourier geometry only. Tables distinguish cost probes from accuracy-qualified
predictions, and audit-free amortization from validation-inclusive cost.
