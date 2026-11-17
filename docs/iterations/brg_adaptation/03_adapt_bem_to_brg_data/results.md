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

- (a) A3/A4 CPU table forward and analytic disk/BRG low-k checks: pending.
- (b) Masked table derivatives and ragged residuals: pending.
- (c) One end-to-end glider eta=0.33 fit and final default regression: pending.

The [approved plan](plan.md) records exact modal plane waves, masks, the
unchanged cancellation check, capped frequency prefixes and all limits.
