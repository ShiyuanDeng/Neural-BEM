# FM-001 evidence bundle

Frozen plan: `docs/iterations/cleaned_interfaces/iteration_18/03_plan.md`.
Starting commit: `b23dbf3e`; existing branch: `feature/shape-frequency-continuation`.
No branches, worktrees, parameter tuning or default policy changes.

- `phase0/`: baseline source archive, environment, 102-test suite, and exact
  archived-decision replays for the contrast-13.3 and contrast-4 development C.
- `phase0_environment_failure/`: retained initial launch in an environment
  without pytest; no numerical campaign ran in that environment.
- `implementation.json`, `implementation.tar.gz`: implementation and original
  input seals, execution settings, case order, recovery thresholds and tau.
- `phase1/`: 16 focused regressions within the 128-test regression suite, exact post-change
  paired controls, gate summary, and catalog generation log. The initial numerical gates passed; one catalog lookup fix was needed for
  separately stored clean fresh-case references. Its failure, regression test and
  original implementation seal are retained in `bugfixes.json` and attempt-0 files.
- `catalogs/`: 36 independently qualified full real/damped catalogs, 1024-node
  production data and 2048-node qualification. NPZ arrays are frequency,
  source, receiver ordered. Archived observed diagonals are preserved exactly.
  New off-diagonal noise uses separately recorded seeds; effective sigma
  accounts for the old diagonal and new off-diagonal variances.
- `phase2/`: 81-point phase-aligned coefficient paths from archived stage-1,
  stage-4 damped and stage-4 real endpoints; 401-point disk radius scan.
  The truth catalogs are qualified separately. Invalid points remain recorded.
- `F/`, `FRr/`: plans, every accepted state, trials, decisions, numerical
  audits, scoring and arm stop receipts. FRr localization remains damped and
  paired. Relaxation adjoint RHS batches count against the original budgets.
- `stage_distances.json`, `summary.json`: external truth scoring and gates.
- `orchestration.json`, `run_remaining.py`, `*.log`: retained execution order,
  process exit statuses and failures, including evaluation-only fallback.

The maintained code is `experiments/cleaned_interface/fm001.py`,
`fm001_diagnostics.py`, and `full_matrix.py`. Invocations use:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=.:solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.cleaned_interface.fm001 COMMAND
```

Commands are `seal`, `verify`, `controls`, `catalogs`, `paths`,
`arm --arm F`, `arm --arm FRr`, `paths --fallback`, and `report`.
Source changes require a new evidence bundle; source seals are checked before
catalogs, paths and arms, and at the end of arms. Existing incomplete fits are
never overwritten. `phase1/gates.json` records the actual pytest/compatibility
results and hashes the supporting logs; arms require these gates.

Reports: `docs/iterations/cleaned_interfaces/iteration_18/01_results.md` and
`docs/reports/overnight_2026-10-03.md`. Use `orchestration.json` and arm status
files to distinguish completed measurements from pending work. The archived
28/36 count is combined historical retention, separate from 34/36 recovery;
the new report also gives the residual-only count on the unchanged paired data.

## Measured arm results and report reproduction

F completed 36 cases: 36 full-matrix recoveries, 32 unchanged-paired recoveries,
and 15 historical paired-residual retention passes. The C is recovered from both
starts. FRr stopped at its second retention loss: 0/4 recoveries, 13 cases not
run. These scopes must remain separate; four noisy F cases lose recovery on
the unchanged paired contract. `recovery_contracts.json` records both definitions
and the counterfactual stop point under the paired definition.

After the maintained `report` command, run the external reporting supplement:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=.:solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/cleaned_interfaces/FM-001/complete_report.py
```

This adds the explicit acquisition scopes, unchanged-paired recovery column and
C endpoint figure without changing any fit result or threshold. The extra
large-tau endpoint check covers all 19 real frequencies at N=512 for the
archived failed C and recovered F endpoint; worst relative loss discrepancy
is 4.43e-10, below 1e-9. See `phase1/large_tau_endpoints.json`, which hashes both
endpoint results. The initial synthetic large-tau check is retained separately.

Validation totals 139 distinct pytest cases: the 128-test regression suite plus
11 shared CUDA compatibility tests. Both forced CPU-factor fallback checks also
passed. `validation_additional.json` records the evidence. `final_verification.json`
checks source and input seals, all 36 catalogs, 40 fit results, 12 paths (972
samples), the 401-point radius scan, and both final report hashes. Recreate that
receipt after reporting with `final_check.py` in this folder.
