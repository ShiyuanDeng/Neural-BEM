# GGB-002 — Four-frequency case-8 follow-up

Approved 2026-10-05. The matched single-frequency control has completed;
the approved four-frequency arm follows after validation and push of S1.

## Qualified synthetic extension

The original archive has only 0.4 GHz fields. The new pixel-volume generator
retains case 8's original pixel mask, source/receiver coordinates and physical
normalization. It reproduces archived clean fields with relative error
3.22851e-6, passing the 1e-5 gate. New volume system residuals pass 1e-10.
Independent Mie checks pass at every new frequency (worst error 9.014e-15),
and rebuilt-geometry derivatives pass at both panel endpoints (worst error
2.133e-9). CPU qualification and the maintained-package tests pass: 85 tests.

This uses the standard four-real-frequency panel, 0.5/0.75/1.0/1.25 GHz,
with GGB-001's original M3 -> M7 -> M11 schedule and centred radius-0.35 m
start. It is a known-material shape control. The complete standard damped
warm-up and 19-frequency continuation recipe is outside this experiment.

## S1 control

S1 fits the new 0.5 GHz observations only. Its endpoint residual is 67.609%
against a 5.498% noise target, so it does not recover. M3 accepts 76 steps and
stops with `no_decreasing_step`; M7 accepts another 37 and returns
`NUMERICAL_FAILURE`, detail `production evaluation failed at candidate state`.
M11 is not entered, following the registered hard-failure exit rule.

The returned endpoint itself passes the production/refined field gate at
all five audited frequencies. This does not validate the refused candidate
or establish inverse recovery. The image has SSIM 0.92027, RRMSE 0.05588,
and contrast SNR -0.18 dB. The shape is distorted and elongated toward the
initial centre. All residuals, stages and trials are retained.

## Reporting correction and preserved provenance

After S1 saved its complete fit and audits, report generation encountered a
`KeyError`: it used `label` instead of the actual `StageResult.stage_label`.
The renderer was corrected and made able to print a null stop reason on a
numerical failure. No fit was rerun. The unchanged original preparation seal,
original driver snapshot and report-failure receipt remain in the evidence.

A separate `postprocessing_amendment.json` records the old and new source
hashes. AST comparison verifies that all code outside `report` and `sealed`
is unchanged; the latter recognizes this explicit provenance amendment.
Numerical functions, data, budgets and settings are unchanged. The corrected
report and read-back verification pass, and all 85 tests pass again.

See the [evidence report](../../../results/validation/cleaned_interfaces/GGB-002/report.md),
[reconstruction panel](../../../results/validation/cleaned_interfaces/GGB-002/comparison.png),
and [pre-registered plan](GGB-002_plan.md).
