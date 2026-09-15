# Commands

From `/home/drdeng/Neural_SDF_BEM_AD`, existing branch
`feature/ordered-boundary-nystrom`, base `fa2666f` plus bundled source snapshots.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MPLCONFIGDIR=/tmp/top020-matplotlib PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top020/run.py --output results/validation/topology/TOP-020-20260915-153359-fresh-two-stars --validation experiments/top020/validation.json > experiments/top020/dispatch.log 2>&1
```

The numerical run is complete; its output directory must not be reused.
Report rebuilding performs no new physical solves:

```bash
env MPLCONFIGDIR=/tmp/top020-matplotlib /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/top020/summarize.py --output results/validation/topology/TOP-020-20260915-153359-fresh-two-stars
```

`pre_dispatch_validation.json` records the original test command and hashes.
Closeout tests added the saved-bundle reporter regression and the conditional
suite tests: `pytest/sdf_inverse/test_top020.py`, `test_recovery_followup.py`,
`test_top017.py`, `test_top019.py`, `test_top016_optimizer_hooks.py`, and
`test_top021.py` under the same test directory. See `closeout_tests.log`.
The frozen `approved_plan.md` retains links relative to its original
`docs/iterations/topology/iteration_13/` location; use the live linked plan for
navigation. Live status additions do not rewrite the frozen approved contract.
