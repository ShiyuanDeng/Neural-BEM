# GGB-002 — Four-frequency case-8 follow-up

Approved and completed 2026-10-05. **Neither arm recovered the target.**
The four-frequency arm stopped on a candidate production-evaluation failure
in its first stage, so this result does not settle whether the original
failure was caused by insufficient frequency information.

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

## F4 outcome and interpretation

F4 uses the four real frequencies jointly. It accepts 15 steps in M3 and
returns `NUMERICAL_FAILURE`, detail `production evaluation failed at candidate
state`. M7 and M11 are not entered. Its fit takes 4.769 seconds and endpoint
audits take 0.104 seconds. This short wall time reflects early failure, not
successful reconstruction or a demonstrated speedup.

| Frequency GHz | S1 endpoint residual | F4 endpoint residual | Noise target, approximately |
|---|---:|---:|---:|
| 0.5 | 67.609% | 111.127% | 5.50% |
| 0.75 | 71.120% | 110.948% | 5.50% |
| 1.0 | 71.282% | 110.826% | 5.49% |
| 1.25 | 72.350% | 111.283% | 5.49% |

F4's whitened joint loss is 0.61656 versus its noise discrepancy floor
0.0015096. The initial aggregate relative field residual is 225.55%; the
last accepted aggregate residual is 111.10%. Its image has SSIM 0.88896,
RRMSE 0.06749 and contrast SNR -2.36 dB. It stays near the initial centre
and forms an incorrect lobed shape.

The accepted endpoint passes the 1e-4 field-refinement gate at every fitting
frequency (worst relative difference 5.445e-8). The archived 0.4 GHz residual
is 112.009%. None of these field gates establishes inverse recovery.

S1 uses 346 of 2000 work units and F4 uses 193 of 8000. Neither fit exhausts
its registered budget. F4 has 18 proposals: 15 accepted, two self-intersection
refusals, and the terminal candidate whose physics evaluation fails. The
receipt retains the native generic failure detail; it does not retain the
underlying caught exception, so an exact low-level cause is not established.

Four-frequency information alone did not resolve case 8 under the frozen
GGB-001 start and optimizer schedule. The numerical hard stop prevents a
clean information-sufficiency test, and the complete standard continuation
recipe has not been tested here. No settings were retuned and no inverse
was retried after either unsuccessful outcome.

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

## Validation and closeout

Both endpoints, original-grid image metrics, all five per-frequency field
residuals, refinement errors and discrepancy decisions were recomputed from
the sealed saved arrays. The read-back receipt verifies both arms. The
reconstruction panel was visually inspected. Whitespace validation passes.

S1, including the report-failure evidence and correction, was committed and
pushed as `6406ea55` before F4 started. F4's unsuccessful evidence is also
preserved and committed/pushed after its validation. All work stays on the
existing `feature/shape-frequency-continuation` branch; no branch or worktree
was created. Concurrent unrelated workspace files remain untouched.

See the [evidence report](../../../results/validation/cleaned_interfaces/GGB-002/report.md),
[reconstruction panel](../../../results/validation/cleaned_interfaces/GGB-002/comparison.png),
and [pre-registered plan](GGB-002_plan.md).
