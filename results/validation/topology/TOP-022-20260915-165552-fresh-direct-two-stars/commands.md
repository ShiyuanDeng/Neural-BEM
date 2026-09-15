# TOP-022 commands

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/top022-matplotlib PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top022/run.py \
  --output results/validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars \
  --validation experiments/top022/validation.json
```

The output directory must be fresh; preserve this completed negative bundle.
The actual dispatch stdout/stderr is in `dispatch.log`. Process exit was 0.

Saved-artifact replay and figure generation, with no physical solves:

```bash
env MPLCONFIGDIR=/tmp/top022-matplotlib \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top022/summarize.py \
  --output results/validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars
```

The exact seven-file test command and source/test/log hashes are in
`pre_dispatch_validation.json`; 112 tests passed in 32.57 seconds. Measured
experiment dependencies and tests are preserved in `measured_sources/`.
