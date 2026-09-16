# SPD-004: training-only pipeline readiness

This experiment asks whether the full inverse can return an already adequate
topology result without running a mandatory frequency-continuation optimizer.
It wraps the existing TOP-025 scene worker in a separate process and changes
only its continuation callback. Shared production code and defaults are not
modified.

The gate uses four training frequencies at 256 and 512 nodes. Each prediction
must have relative L2 error <= 1e-5, and the two grids must agree within the
existing frequency-specific numerical tolerances. Geometry must be admissible
at both grids. The decision function has no truth, scene identity, target count
or evaluation-observation argument. A rejected screen runs the existing
continuation and charges its screening overhead. A passed screen still receives
independent endpoint assessment and records that stationarity and continuation
stage exposure were not measured.

[Approved bounded plan](../../docs/iterations/speedup/iteration_03/03_plan.md)
and [architecture brief](../../docs/iterations/speedup/iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md).
The [completed measurements](../../docs/iterations/speedup/iteration_04/01_results.md)
show additional 5.12x/6.72x full-runtime speedups on death/split and preserved
merge fallback, with identical paired final geometry.

## Reproduce in a fresh directory

Use the repository's EMNerf Python environment, `PYTHONPATH=solvers`,
`SDF_INVERSE_RUNTIME=fast`, and one thread for `OMP_NUM_THREADS`,
`OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS`.
Set `MPLCONFIGDIR` to a writable temporary directory. From the repository root:

```bash
python -m experiments.spd004_pipeline_readiness.audit BUNDLE/archive
python -m pytest -q pytest/sdf_inverse/test_spd004.py pytest/sdf_inverse/test_spd002.py pytest/sdf_inverse/test_top025.py
python -m experiments.spd004_pipeline_readiness.run qualify --bundle BUNDLE
python -m experiments.spd004_pipeline_readiness.run campaign --bundle BUNDLE --test-log TEST_LOG
python -m experiments.spd004_pipeline_readiness.summarize BUNDLE
```

Capture the test output to `TEST_LOG` for the campaign's evidence bundle. The
archive audit and qualification must pass before dispatch. A prepared campaign
cannot be overwritten. Qualification uses at most 64 physical systems and
300 seconds. The sequential campaign permits ten full workers and 3,600 seconds
total, with 1,200 seconds per worker and unchanged inner optimizer caps.

The comparison contains two repetitions per arm for death/split and one merge
pair. Fresh runs always begin at the original initialization. Saved handoffs
are used only for qualification and the retrospective audit. Parent and worker
both check source/input integrity. Source snapshots and every failed or stopped
arm remain in the bundle. Host-wide process isolation cannot be inferred from
the sandbox PID namespace; the environment records that limitation.

`gate.py` owns the pure decision; `audit.py` reads historical evidence;
`run.py` owns qualification, experiment-only routing and timed execution;
`summarize.py` checks recovery, retained geometry, physical/derivative counts
and timing targets. A complete benchmark result does not promote a new default.
