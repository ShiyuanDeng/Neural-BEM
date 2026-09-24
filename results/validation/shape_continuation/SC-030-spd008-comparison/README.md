# SC-030: SPD-008 and the clean hybrid

Status: implementation qualified; comparison pending.

- [Frozen approved contract](approved_plan.md)
- [Source/input/environment manifest](manifest.json), with complete measured sources in `sources/`
- [Pre-dispatch tests](pre_dispatch_tests.log): 76 passed
- [Numerical/cache qualification](qualification/result.json): PASS, 52 units, 58.34 s
- [Interpretation](../../../docs/iterations/shape_frequency_continuation/iteration_13/01_results.md)

The fresh benchmark compares SPD-008, hybrid cache off, and hybrid cache on
on each of the six atlas cases, with two sequential repetitions. Inputs, starts,
frequency schedule, resolution, work limits and independent endpoint scoring
are shared. Native parameterization, feasible set and update construction differ
as declared in the contract. Truth is used only after the inverse returns.

Run using `experiments.shape_continuation.spd008_comparison campaign --output`
with this directory, the EMNerf interpreter, `PYTHONPATH=solvers:.` and one BLAS
thread. Each worker writes its configuration, stage histories, cache counters,
work, separate inverse/evaluation timing and last accepted endpoint. Incomplete
or failed runs remain evidence; they are never silently replaced.
