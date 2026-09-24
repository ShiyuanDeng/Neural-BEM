# SC-028 — qualified harness, failed full-atlas preflight

The [frozen plan](../../../../docs/iterations/shape_frequency_continuation/iteration_10/03_plan.md)
tests an M=2 first stage and continuation to 2.5 GHz. **The recovery campaign
was gated off before dispatch:** six of twelve P=48 Jacobian checks failed
the 1e-6 column-relative tolerance at N=512/1024. All field checks passed.
The failed checks and their original thresholds are preserved in
[`qualification.json`](qualification.json), with the gate's failing exit in
[`qualification.log`](qualification.log). No replay or recovery result is claimed.

| Case | Max field error | Max Jacobian column error | Verdict |
|---|---:|---:|---|
| Circle | 4.40e-15 | 7.21e-7 | pass |
| Star | 1.30e-14 | 5.48e-11 | pass |
| C | 1.51e-9 | 4.60e-6 | fail |
| Kite | 1.06e-10 | 3.25e-6 | fail |
| Peanut | 4.44e-10 | 6.17e-6 | fail |
| Hook | 4.55e-14 | 7.08e-9 | pass |

Cost: 48 solve/reciprocal work units; 11 seconds with six worker processes
and single-thread BLAS. This is a numerical gate, not a negative recovery
result for either strategy.

Implementation validation: **33 tests passed in 6.74 s**, combining
`test_atlas_strategy_tests.py`, `test_lm_backend.py`, `test_atlas_survey.py`
and `test_policies.py`. Existing matplotlib/pyparsing deprecation warnings
were the only warnings. Tests cover frozen schedules, work accounting,
failure stops and truth isolation, plus the existing numerical contracts.
No core numerical implementation or default changed.

Reproduce from the repository root with a fresh output directory:

```bash
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.shape_continuation.atlas_strategy_tests prepare --output <fresh>
$PY -m experiments.shape_continuation.atlas_strategy_tests qualify --output <fresh> --workers 6
```

The numerical sources and input hashes used by this result are in
[`manifest.json`](manifest.json). A separately scoped active-band diagnostic
may determine whether the failure concerns the proposed inverse space; it
cannot turn this P=48 gate into a pass.
