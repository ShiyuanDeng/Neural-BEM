# TOP-019 execution and verification commands

Run from `/home/drdeng/Neural_SDF_BEM_AD` on the existing
`feature/ordered-boundary-nystrom` branch. The commands below document the
completed run; the numerical output directory must not be reused.

## Pre-dispatch validation

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/top019-matplotlib PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_inverse/test_top019.py pytest/sdf_inverse/test_top017.py \
  pytest/sdf_inverse/test_top018.py pytest/sdf_inverse/test_top018_reporting.py \
  pytest/sdf_inverse/test_top016_optimizer_hooks.py
```

84 passed in 47.17 s; mocked physical calls and geometry only. The source and
test hashes, log hash and exact argv are in `pre_dispatch_validation.json`.

## Completed campaign

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/top019-matplotlib PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top019/run.py campaign \
  --bundle results/validation/topology/TOP-019-20260915-144340-qualified-merge \
  --validation experiments/top019/validation.json
```

The parent dispatched S then F, with exact worker commands, exit codes and
elapsed times in `campaign.json`. `environment.json` records hardware, initial
load, interpreter and threading. The UTC directory timestamp came from the
session clock; campaign wall time comes from its monotonic watchdog.

## Saved-artifact replay

```bash
env MPLCONFIGDIR=/tmp/top019-matplotlib \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top019/summarize.py \
  --bundle results/validation/topology/TOP-019-20260915-144340-qualified-merge
```

No physical solves. Reconstructs frequency errors/objectives from saved complex
predictions, verifies source/input/state/gradient/acceptance/work associations,
and renders the saved coefficient curves. Final classification:
`BOTH_ARMS_RECOVERED`, 6,232 attempted/completed solves, zero failed.
