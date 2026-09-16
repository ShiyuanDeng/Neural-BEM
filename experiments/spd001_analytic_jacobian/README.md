# SPD-001 — combined analytic Jacobian / CPU / CUDA timing

The [executed plan](../../docs/iterations/speedup/iteration_01/03_plan.md)
records the user's authorization, settings, gates, budgets and scope.

This experiment calls the real `run_multiradial_fd_inverse` with explicit
`jacobian_mode` and a scoped `gpr_bem_kress.execution.execution` context.
Numerical functions are not monkeypatched. The six arms vary the Jacobian
(FD/analytic) and execution (reference CPU/fast CPU/fast CPU plus CUDA).

- Qualification: full 192x34 weighted Jacobian versus the saved TOP-023 FD
  reference, direct backend parity, and selected refined-grid sensitivities.
- Jacobian timings: 34 directions, 1.25 GHz, N=256/component; three sequential,
  alternating-order repeats including base setup and refined feasibility.
- Optimizer timings: all four training frequencies and one update opportunity,
  including both Jacobians, candidate search and the existing production/refined
  acceptance rule. One complete measurement per arm.

The first run uses a fresh bundle with `baseline_sources/` and
`workspace_before.json` captured before numerical edits. The executed bundle
is linked from the speed-up track. To continue its frozen, budgeted phases:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=solvers:. \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.spd001_analytic_jacobian.run --bundle PATH --phase all
```

`--phase` also accepts `qualification`, `jacobian` or `optimizer`. Completed
rows are retained; source drift and another numerical/render worker stop
execution. No historical TOP/BIE artifact is written. A different experiment
requires a fresh declared contract and bundle; this command does not reset the
budget of an existing one.

After completion, rebuild the tables without BIE work:

```bash
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.spd001_analytic_jacobian.summarize PATH
```

The numerical defaults remain reference CPU and FD. Results are local runtime
and bounded optimizer evidence, not a completed recovery or all-scenes claim.
