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

## Run all twelve scenes with the promoted default

`all_scenes_validation.json` reuses the passing SPD-007 regression log after
verifying exact current numerical-source, archived-test and evidence hashes.
It is accepted by the normal TOP-025 campaign runner. Solver/runner changes
require a new qualifying validation record; the runner rejects stale hashes.

From the repository root, with the EMNerf Python environment, `PYTHONPATH=solvers:.`
and `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and
`NUMEXPR_NUM_THREADS` set to `1`:

```bash
inverse_run="results/validation/topology/TOP-025-compiled-$(date +%Y%m%d-%H%M%S)"
python -u -m experiments.top025.run campaign \
  --inverse-runtime compiled \
  --bundle "$inverse_run" \
  --validation experiments/spd007_default_promotion/all_scenes_validation.json &&
python -m experiments.top025.summarize --bundle "$inverse_run"
```

This dispatches all twelve original scenes with up to four concurrent CPU
workers, one BLAS thread each, and writes a scorecard including failed/stopped
cases. The output folder must be new. The campaign has a seven-hour hard ceiling;
that ceiling is not a runtime estimate. Numerical sources must remain unchanged
during the campaign. This command does not render videos.
