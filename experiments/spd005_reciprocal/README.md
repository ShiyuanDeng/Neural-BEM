# SPD-005 — reciprocal derivatives in the full Kress inverse

The [plan](../../docs/iterations/speedup/iteration_04/03_plan.md) owns scope and
dispatch gates. This package reuses the TOP-025 full worker and SPD-004 readiness
gate; it does not implement another optimizer or topology controller.

- `qualify.py`: saved pre/post-event states, difficult handoffs, selected grid
  refinement checks, full production gauge bases and independent directional FD.
- `run.py`: frozen-source, sequential comparison of operator, reciprocal and
  reciprocal + readiness arms on identical inputs. All original quality gates
  and conservative batch reservations remain.
- `reporting/summarize.py`: rebuilds quality/work/timing comparisons without
  solving anything. Reporting code is outside the frozen numerical source glob.

Run with the EMNerf environment, `PYTHONPATH=solvers:.`, and
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`.
Use separate fresh directories for qualification and campaign outputs. A
campaign refuses a failed or stale qualification; it stops on failed recovery
or source/input drift. No historical bundle is rewritten.

```text
python -m experiments.spd005_reciprocal.qualify --bundle QUALIFICATION
python -m experiments.spd005_reciprocal.guard_qualify --bundle GUARDED_QUALIFICATION --reference QUALIFICATION
python -m experiments.spd005_reciprocal.run campaign --bundle CAMPAIGN --qualification GUARDED_QUALIFICATION --test-log TEST_LOG
python -m experiments.spd005_reciprocal.reporting.summarize CAMPAIGN
```

Physical-system counts exclude reciprocal illuminations, which reuse existing
factors. Reciprocal batches have their own attempted/completed/failed counters
and consume one budget unit each. Shape contractions and primal/receiver RHS
columns are reported separately. Topology owns a nested passive ledger; worker
performance records the outer continuation ledger, and reporting combines them.

The qualification deliberately calls the raw derivative for diagnostics. Its
coarse-grid failures must remain visible even if the production runtime routes
those grids to the existing operator derivative. Full worker times include
endpoint verification, while saved truth-data generation is outside the timer.
