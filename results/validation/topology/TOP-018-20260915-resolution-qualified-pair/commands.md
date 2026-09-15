# Commands and numerical environment

Existing checkout: `/home/drdeng/Neural_SDF_BEM_AD`, branch
`feature/ordered-boundary-nystrom`. Measured numerical revision: `9bde9d1`.
Python executable: `/home/drdeng/miniconda3/envs/EMNerf/bin/python`.
All numerical/test/render commands set
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`.
The [environment record](environment.json) contains Python/platform/CPU details;
[campaign.json](campaign.json) preserves exact child commands and both exit codes.

One campaign invocation:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top018/run.py campaign --bundle results/validation/topology/TOP-018-20260915-resolution-qualified-pair --validation experiments/top018/validation.json
```

Phase A passed, automatically releasing exactly S and F. No other campaign,
prefix, oracle, central inverse or numerical restart was executed. This command
is historical provenance, not permission to repeat TOP-018.

The final focused tests added the reporting regression to the pre-dispatch set:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q pytest/sdf_inverse/test_top018_reporting.py pytest/sdf_inverse/test_top018.py pytest/sdf_inverse/test_recovery_followup.py pytest/sdf_inverse/test_top017.py pytest/sdf_inverse/test_top016_preflight.py pytest/sdf_inverse/test_top016_screen.py pytest/sdf_inverse/test_top016_optimizer_hooks.py pytest/sdf_inverse/test_top016_pilot.py pytest/sdf_inverse/test_feasible_finite_differences.py
```

Reporting repair and summary/figure rebuilds, all using saved artifacts and zero
physical solves:

```bash
python results/validation/topology/TOP-018-20260915-resolution-qualified-pair/reconcile_reporting.py
python experiments/top018/summarize.py --bundle results/validation/topology/TOP-018-20260915-resolution-qualified-pair
python results/validation/topology/TOP-018-20260915-resolution-qualified-pair/render_endpoints.py
```

For reconciliation and rendering, `python` above is the recorded EMNerf
executable with the same thread settings. The JSON-only summarizer was run with
the shell's `python`; it imports no physical solver. The original failed
reporting regression is preserved in `reporting_regression_before.log`.
