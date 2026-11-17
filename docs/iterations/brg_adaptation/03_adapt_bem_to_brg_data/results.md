# Adapt the BEM inverse to BRG data: staged results

## Status

Authorized by the coordinator on 17 November 2026; BRG holds the solver lock.
Activity 02 MATLAB runs keep priority. Stage (c) is limited to glider eta=0.33;
the other five BEM fits wait for the coordinator after that report.

## Unmodified reference, 17 November

Before any solver edit, the existing CPU-pinned suite passed **96 tests**,
with **3 CUDA-only skips**, in 59.12 seconds of pytest time. The default
TG-002 `circle__c0.5` fit completed its schedule in 37.7601 seconds.
It used `modal_muller` + `slider`, real data, recovered contrast and the
default 120-second fit limit; only execution was pinned to CPU.

The complete check process took 104.762 seconds of the shared one-hour
check budget. Scientific settings, coefficients, predicted fields, contrast,
decisions, source hashes, command, JUnit XML and logs are retained in
[the before reference](../../../../results/brg/bem_adaptation/2026-11-17/regression/before/).
No solver file was edited before both reference runs finished.

## Stages

- (a) A3/A4 CPU table forward and analytic disk/BRG low-k checks: passed.
- (b) Masked table derivatives and ragged residuals: passed.
- (c) One end-to-end glider eta=0.33 fit and final default regression: pending.

The [approved plan](plan.md) records exact modal plane waves, masks, the
unchanged cancellation check, capped frequency prefixes and all limits.

## Stage (a), 17 November

Seven tests passed in 0.67 s: exact plane-wave modes/flux on a translated
disk, disk-series tables at eta 0.33 and 2, masks, unpaired point tables,
and explicit CPU/option validation. No upstream change was needed.

The exact true glider at k=1, eta=0.33 agrees with saved BRG data to
**1.30165e-6 relative complex error**; raising trace/workspace resolution
changes the prediction by **1.19354e-15**. Both declared thresholds pass.
This forward check took 0.550 s. Numerical evidence and source-data hash:
[stage (a)](../../../../results/brg/bem_adaptation/2026-11-17/stage_a/).

New behavior requires explicit table mode on CPU. Paired defaults retain
their previous branch. Table derivatives remain refused until stage (b).

## Stage (b), 17 November

Thirteen table-forward/derivative/layout tests passed in 2.09 s. They cover
rectangular and masked tables, per-frequency normalization, the material
column, explicit variable-acquisition opt-in, and ragged stage-entry reuse.
The paired contraction remains on its original branch.

For the true glider at k=1, eta=0.33, the complete-slider derivative error
fell from **1.41022e-6 to 3.52554e-7** when the difference step halved from
0.002 to 0.001. The masked 66-pair table gave **1.40423e-6 to 3.51057e-7**.
Both pass the 1e-3 threshold with the expected second-order decrease.
The check took 2.706 s on one CPU thread.

Evidence: [stage (b)](../../../../results/brg/bem_adaptation/2026-11-17/stage_b/).
These short checks ran while three MATLAB jobs were active. The longer
default regression and BEM inverse wait for a heavy-worker slot. No CUDA
code, LM acceptance rule, slider formula or upstream BRG file changed.
