# TOP-017 reproducibility commands

Run from the experiment worktree `/home/drdeng/Neural-BEM-TOP-017`.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q pytest/sdf_inverse/test_top017.py pytest/sdf_inverse/test_top016_preflight.py pytest/sdf_inverse/test_top016_screen.py pytest/sdf_inverse/test_top016_optimizer_hooks.py pytest/sdf_inverse/test_top016_pilot.py pytest/sdf_inverse/test_feasible_finite_differences.py
python summarize_top017.py --bundle results/validation/topology/TOP-017-20260914-staged-continuation --merge-only
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python run_top017_campaign.py --bundle results/validation/topology/TOP-017-20260914-staged-continuation
python summarize_top017.py --bundle results/validation/topology/TOP-017-20260914-staged-continuation
```

The campaign owns its7500-second outer watchdog and launches only approved Phase A and, on PASS, four trials with at most two concurrent numerical workers. Its JSON records exact worker commands/exit codes. Fresh execution folders are mandatory; do not rerun into this historical bundle. The summary commands only read saved JSON and rebuild reports; they perform zero physical solves. Tests use analytic/mock forwards and geometry only.
