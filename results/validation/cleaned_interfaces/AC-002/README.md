# AC-002 forward profile

[Plan](../../../../docs/iterations/CI-SPD/AC-002_plan.md) and
[report](../../../../docs/iterations/CI-SPD/AC-002_results.md).

`profile.json` contains 12 timed forward evaluations, four aggregate
breakdowns, source hashes, settings, device details and field differences.
Each device has three pairs: fresh geometry then reused geometry. All calls
passed the field-equivalence and exclusive-accounting assertions in the driver.
The source hashes were independently rechecked after execution.

Reproduce from the repository root with GPU access:

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.radial_forward_profile
```

This writes `profile.json`. Device/runtime warm-up is excluded, fresh geometry
construction is included, and CUDA synchronization is part of the instrumented
measurement. The profile covers a single TG-002 forward state, not an inverse
campaign. No production solver was modified.
