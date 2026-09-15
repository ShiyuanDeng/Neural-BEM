# Actual command

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.bie004_multi_derivative.run --output results/validation/boundary_bie/BIE-004-20260915-coupled-02 --previous results/validation/boundary_bie/BIE-004-20260915-coupled-01
```

## Saved-table audit and report

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.bie004_multi_derivative.summarize results/validation/boundary_bie/BIE-004-20260915-coupled-02
```

The reporting command performs no physical solves. It replays Jacobian errors
from stored matrices, verifies source/input/plan hashes and reconciles all work
counts. The predecessor `BIE-004-20260915-coupled-01` retains the single failed
algebra test and zero physical work. Global time includes that attempt.
