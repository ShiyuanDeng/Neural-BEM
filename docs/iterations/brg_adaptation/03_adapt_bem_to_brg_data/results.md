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
- (c) One glider eta=0.33 fit finished; numerical refusal entering k=12. Coordinator checkpoint reached.

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

## Default-path regression after the final solver edit

The full CPU suite passed **109 tests, with 3 CUDA-only skips**, in 55.44 s.
The default TG-002 `circle__c0.5` fit completed in 35.8640 s. Its curve
coefficients, predicted complex fields and material image are **bit-identical**
to the pre-edit reference. Contrast, residuals, accepted decisions, stage
records and work counts also match exactly after excluding clock fields.

[Comparison](../../../../results/brg/bem_adaptation/2026-11-17/regression/comparison.json)
and [after reference](../../../../results/brg/bem_adaptation/2026-11-17/regression/after/)
retain the evidence. The complete after-check process took 98.323 s.
No default behavior change was observed; the new paths require explicit options.

## Glider eta 0.33 forward prefix

All 15 ladder frequencies from k=1 through **k=12** pass. Maximum relative
BRG field difference is **1.30165e-06**; maximum
refinement difference is **4.86729e-10**.
The complete qualification took **13.013 s** of its 30-minute budget.

At k=15 the unchanged regular-wave cancellation check refuses the solve:
4.3e-9 exceeds 1e-9 at geometry-radius product 19.2. The approved BEM prefix
therefore ends at k=12. No higher frequency or redesign is pursued.

[Qualification and per-frequency records](../../../../results/brg/bem_adaptation/2026-11-17/glider_033/forward/)
include field errors by illumination/receiver, refinement, source hashes and
the preserved k=15 refusal. Bulk field arrays remain local with SHA-256.

## Stage (c): one glider fit, 17 November

The known-eta 0.33 fit took **59.758 s** (60.455 s including scoring),
using 1,819 work units. It reached k=10 with **0.214169% area error** and
maximum active-frequency field residual **1.28515e-4**. It began from the
unit circle, with one CPU frequency worker, modal Müller and slider.

Entering k=12 returned `NUMERICAL_FAILURE`: the reconstructed curve’s
coefficient-based wave radius gives |k|rho=18.2 and cancellation estimate
1.6e-9, above the unchanged 1e-9 limit. The true-shape qualification had
passed k=12 because its wave radius is smaller. Thus the forward-qualified
cap is 12, but the actual fitted endpoint is **k=10**. No rerun or loosening
was attempted, and no high-k redesign is proposed.

The returned accepted curve is preserved. BRG’s saved glider area errors
are 0.241786% at k=10 and 0.0517798% at k=15 (0.00311943% at k=30).
Those BRG scores use its documented 2,048-point truth polygon; the BEM score
uses the frozen comparison region functions with 16,384 truth samples.
These small endpoint differences are not a claim of superiority.

[Fit and failure evidence](../../../../results/brg/bem_adaptation/2026-11-17/glider_033/inverse/)
retains the curve, every accepted state, residuals, full numerical failure,
source hashes, timings and bulk checksums. [Endpoint figure](figures/glider_033.png).
Both BRG paper jobs overlapped this fit; timing is indicative.

Stage (c) is reported to the coordinator. The other five BEM inversions
remain unstarted. Activity 02 continues to its newly requested k=15
endpoints. Activity 04 is a plan only for the main TG-002-shape comparison.

## Solver handover at the coordinator's stage (c) stop

BEM implementation and runs stop here. No other BEM case has run and no
further solver edit is planned by this agent. The coordinator is arranging
separate BEM ownership. Activity 04's plan had already been created and
pushed in `a8ca0b993` before the hold arrived; it is now held without further
work. It has no runs. Existing pushed history is retained.

### Every changed solver file

The complete list below is the diff from the saved pre-edit reference
`46fc141e0` through stage (b), `4dde44c96`. Stage (c) made no further solver
edit. Reference and experiment wrappers are outside the solver package.

| File | Chain / change |
|---|---|
| [__init__.py](../../../../solvers/bem_inverse/__init__.py) | Exports `PlaneWaveAcquisition`, an alias of the existing plane-wave acquisition. |
| [continuation/forward.py](../../../../solvers/bem_inverse/continuation/forward.py) | Acquisition masks, shape validation, measured-pair order and acquisition equality; direct legacy nodal calls refuse masks. |
| [a3_waves.py](../../../../solvers/bem_inverse/a3_waves.py) | A3 extracts unchanged regular-wave arithmetic for reuse; adds exact scaled plane-wave coefficients, centre phase and a tail bound. |
| [a4_fields.py](../../../../solvers/bem_inverse/a4_fields.py) | A4 adds explicit full-table contraction and masked C-order selection; retains paired einsum. |
| [forward_solvers/modal_muller.py](../../../../solvers/bem_inverse/forward_solvers/modal_muller.py) | Explicit CPU table dispatch, plane-wave RHS, table state/diagnostics, B7 dispatch and flattened table frontier norms. |
| [forward_solvers/nodal_kress.py](../../../../solvers/bem_inverse/forward_solvers/nodal_kress.py) | Clear refusal of unsupported masked tables; unmasked legacy behavior unchanged. |
| [b7_data_jacobian.py](../../../../solvers/bem_inverse/b7_data_jacobian.py) | B7 all-pair nonconjugated reciprocal contraction in receiver blocks, followed by the same mask as A4. |
| [data_blocks.py](../../../../solvers/bem_inverse/data_blocks.py) | New shared B5/B8 frequency-block offsets, scales, normalization and relative residuals. |
| [b5_residual.py](../../../../solvers/bem_inverse/b5_residual.py) | Explicit ragged evaluation; original rectangular evaluation unchanged. |
| [b8_gauss_newton.py](../../../../solvers/bem_inverse/b8_gauss_newton.py) | Explicit block Jacobian uses exactly the B5 map. |
| [forward_batch.py](../../../../solvers/bem_inverse/forward_batch.py) | Optional tuple of variable-size frequency predictions; default remains column_stack. |
| [fit_stage.py](../../../../solvers/bem_inverse/fit_stage.py) | Explicit ragged B5/B8 branches, block-aware material column, copied/reused frequency blocks. No LM or acceptance-rule change. |
| [stage_types.py](../../../../solvers/bem_inverse/stage_types.py) | Ragged opt-in, matching layout in StageEntry reuse, offsets in new stage receipts; omit default-false field from legacy receipts. |
| [problem.py](../../../../solvers/bem_inverse/problem.py) | Explicit allowance for variable acquisitions across frequencies; matched real/damped checks retained. |
| [runner.py](../../../../solvers/bem_inverse/runner.py) | C12 accepted-state maximum relative residual supports frequency blocks. No continuation decision change. |
| [checks.py](../../../../solvers/bem_inverse/checks.py) | Finite-trial check accepts a tuple of frequency blocks. Cancellation threshold is unchanged. |
| [README.md](../../../../solvers/bem_inverse/README.md) | Documents new options, layout, CPU restriction and default preservation. |

Also updated the [A1–C12 reference](../../../reference/inverse_information_chain.md).
No CUDA implementation, geometry-update module or shared comparison/scoring
file was edited. Only stages (a)/(b) changed the core.

### New options and defaults

| Entry point | New option / default | Meaning when enabled |
|---|---|---|
| `ModalSettings` | `table_mode=False` | `True` enables unpaired point or plane-wave tables, with explicit `Execution(device='cpu')`. Auto/CUDA requests are refused for this new mode. |
| `PlaneWaveAcquisition` / existing `Acquisition` | `mask=None` | None measures all direction/receiver pairs; a boolean mask selects C-order rows. Unmasked shape is `(direction,receiver)`, masked shape `(measured_pairs,)`. |
| `PointSourceAcquisition` | `mask=None` | Mask is available only with existing `paired=False`; the existing `paired=True` default is unchanged. |
| `Problem` | `allow_variable_acquisition=False` | Allows changing real acquisition/counts across frequencies. Real/damped pairs still must match. |
| `FitStage` | `ragged_data=False` | Uses shared frequency blocks and records offsets. Existing policies keep their rectangular branch. |
| `solve_frequencies` | `ragged_data=False` | Internal dispatch returns a tuple only when explicitly requested. |
| `solve_and_predict` | `table=False`, `mask=None` | Internal A4 table contraction; default paired arithmetic unchanged. |
| `ModalState` / `StageEntry` | `table_mode=False` / `ragged_data=False` | Internal state markers prevent cross-layout reuse. |

`plane_wave_kernels` is a new A3 function, not a changed default selection.
`series_loss=1e-9` and all material positivity rules remain unchanged. Known
contrast still means `material=None`; eta below one required no new option.
The BRG schedule lives only in the experiment wrapper, not a default policy.

### Tests added and retained proof

- [test_table_forward.py](../../../../pytest/bem_inverse/test_table_forward.py):
  seven cases covering translated-disk modal values/flux, independent disk
  scattering at eta 0.33 and 2, masks, unpaired point tables and refusals.
- [test_table_derivative.py](../../../../pytest/bem_inverse/test_table_derivative.py):
  six cases covering every table entry against paired contractions, full and
  masked complete-slider differences, equal-frequency residual/Jacobian
  order, explicit variable acquisition, material columns and entry reuse.
- Experiment checks preserve the true-glider BRG comparison, two-step full
  and masked derivative errors, and all qualified-prefix frequencies.

The saved pre-edit CPU suite passed 96 tests with 3 CUDA-only skips. The
post-edit suite passed 109 with the same 3 skips. Both use the pinned EMNerf
CPU environment, single-threaded BLAS and the same existing test suite.

The default TG-002 `circle__c0.5` fit used the existing comparison runner,
`modal_muller` + `slider`, real data, recovered contrast, default settings
and its 120 s limit, with CPU execution pinned. Before/after arrays are
byte-identical: 385 complex curve coefficients, all 19-by-24 complex
predictions and the 201-by-201 material image. Returned eta is identical
at 0.5000000000469913; maximum residual is 2.0105158339865096e-7.

Stable decisions, stage outcomes and work are also identical: 596 units,
402 forward solves, 194 derivative batches, 17 accepted steps, 10 stages.
Only clocks and added default-false receipt fields are excluded from record
comparison. Source hashes pin both versions; no solver edit followed this
passing comparison. See [machine-readable proof](../../../../results/brg/bem_adaptation/2026-11-17/regression/comparison.json).

Commit sequence: `f81719a31` (A3/A4), `4dde44c96` (B7/B5/B8),
`da5690467` (default-path proof), `3abcc6759` (forward prefix),
`a8ca0b993` (one-fit checkpoint and then-authorized activity 04 draft).
