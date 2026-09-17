# SPD-007 default promotion validation

The [promotion record](../../docs/iterations/speedup/iteration_07/01_results.md)
describes the new normal default. This bounded check runs fresh death and merge
through `python -m experiments.top025.run scene` with no runtime flag or runtime
environment override. It checks both readiness skip and full-schedule fallback,
original recovery gates, source/input integrity, work accounting and agreement
with the qualified SPD-006 endpoints and accepted steps.

Use the EMNerf Python environment, `PYTHONPATH=solvers:.`, and one BLAS thread:

```text
python -m experiments.spd007_default_promotion.run --bundle <fresh-directory> --test-log <passing-regression-log>
```

`SDF_INVERSE_RUNTIME` must be unset. At most two sequential workers run, each
limited to 600 seconds and the pair to 1200 seconds. Existing topology and
continuation inner budgets remain active. Artifacts include original inputs,
source snapshots, the test log, worker logs, replay checks and a final seal.
Elapsed times are smoke-validation observations, not a matched speedup claim.
