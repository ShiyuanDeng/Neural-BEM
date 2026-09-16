# SPD-006 compiled Kress continuation

User-authorized integration from BIE-005, preserving the full Cartesian gauge,
optimizer and data policy. See the [plan](../../docs/iterations/speedup/iteration_05/03_plan.md).

The `compiled` runtime activates within analytic fits at 256 or more nodes;
single-component fits retain reciprocal Kress. Both campaign arms use the same
training-only readiness gate. Topology and independent refined/endpoint checks
retain their full Kress paths.

Run with the EMNerf Python environment, `PYTHONPATH=solvers:.`, and
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`:

```text
python -m experiments.spd006_compiled.qualify --bundle <fresh-qualification-directory>
python -m experiments.spd006_compiled.run campaign --bundle <fresh-campaign-directory> --qualification <qualified-directory> --test-log <passing-regression-log>
python -m experiments.spd006_compiled.reporting.summarize --bundle <campaign-directory>
```

Qualification has 1800 s / 2000 batch ceilings. The matched campaign has four
scenes, two arms and two repeats: at most 16 sequential workers, 2400 s per
worker and 10800 s total, with original inner budgets. Old recovery failures
remain evidence; new recovery loss, numerical failure or source/input drift
stops the campaign. Fresh output directories and source snapshots are required.
The summary command starts no solver. After the complete timed campaign, the
optional diagnostic command below performs one compiled update from the saved
central handoff, with a separate 240-second / 400-unit limit and archived
provenance. Its timings include profiler overhead and are not speedup timings.

```text
python -m experiments.spd006_compiled.reporting.profile_remaining <campaign-directory>
```

[SPD-006 closeout](../../docs/iterations/speedup/iteration_06/01_results.md):
16/16 full workers recover; compiled full runtime improves by 4.5%/5.6% on the
two hard cases. The profile identifies legacy geometry checks as the next cost.
