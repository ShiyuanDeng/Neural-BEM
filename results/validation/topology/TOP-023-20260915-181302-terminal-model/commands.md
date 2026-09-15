# TOP-023 commands

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/top023-matplotlib PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top023/run.py \
  --output results/validation/topology/TOP-023-20260915-181302-terminal-model \
  --validation experiments/top023/validation.json
```

The actual stdout/stderr is copied into `dispatch.log`. Exit 0. Preserve this
bundle; numerical reruns require a fresh directory and bounded contract.

No-solve artifact replay:

```bash
env OPENBLAS_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  experiments/top023/summarize.py \
  --output results/validation/topology/TOP-023-20260915-181302-terminal-model
```

The exact five-file test command and all source/test/log hashes are in
`pre_dispatch_validation.json`: 85 tests passed in 42.34 seconds, with mocked
forwards and geometry-only checks. Measured experiment dependencies and tests
are copied in `measured_sources/`.
