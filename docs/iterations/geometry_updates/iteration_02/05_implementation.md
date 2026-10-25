# GU-001 implementation notes

Built on 2026-10-25 on the existing `organised` branch, in
`/Users/sean/Projects/Neural-BEM`. No branch or worktree was created. Plan:
[03_plan.md](03_plan.md). Results:
[GU-001](../../../../results/validation/cleaned_interfaces/GU-001/README.md).

## What was added

| Piece | File | Selected by |
|---|---|---|
| Uncentred refit | `geometry_update_methods/uncentred_spectral.py` | `--geometry-update uncentred_spectral` |
| N-update | `geometry_update_methods/n_update.py` | `--geometry-update n_update` |
| Slider | `geometry_update_methods/slider.py` | `--geometry-update slider` |
| Level penalty | `level_penalty.py`, `fit_stage(penalty=...)`, `runner.fit(penalty=...)` | `--level-penalty` |
| Campaign driver | `experiments/benchmark/gu001.py` | `python -m experiments.benchmark.gu001` |

Each geometry update is one file, one branch in `make_update` and one CLI
choice. `fit_stage` was not edited for any of them. The level penalty is the
one addition to `fit_stage`, as planned.

## Choices made while building

- **Penalty rows.** The loss is 0.5‖r‖². The rows are
  2√λ_J ρ_m/ρ_0 for m = 1..2K, real parts then imaginary parts. Then the
  rows add exactly λ_J E to the loss, as in the method document. The plan's
  "√λ_J ρ_m/ρ_0 (m ≠ 0)" would add half of that.
- **Penalty and checkpoints.** `fit_stage` refuses a penalty together with
  `resume` or `pause_after`. λ_J is not stored in a checkpoint.
- **Slider solve.** A is the least-squares solution of
  (BᵀB + ξUᵀU) A = BᵀH (numpy `lstsq`, default cutoff). On a constant-speed
  curve, such as the start circle, a parameter shift moves nothing and keeps
  the speed change even. The matrix is singular there, and the solve drops
  that direction.
- **Slider and N-update metric.** Both support only the default Marquardt
  damping. The N-update's tangential columns have no normal move.
- **Failed trial curve.** The run's code (`645fc19e3`) also saved a
  physics-refused trial curve in the trial record. That duplicated the
  `candidate_coefficients` the physics failure record already holds, so it was
  removed after the run. The videos read the failure record.
- **CLI form.** All four arms run as
  `--solver modal_muller --geometry-update <name>`. For `spectral` this is the
  same physics and update as `--pipeline modal_fixed`; the CLI does not
  combine `--pipeline` with `--geometry-update`.
- **Threads.** Four arms run at once with two frequency threads each, so
  eight threads share the eight cores. NR-001 used two workers with four
  threads each.
- **Endpoint audit and the N-update.** The audit checks every Jacobian
  column against its own norm. The constant slide s_0 is a parameter shift,
  which is in band, so its data column is exactly zero (the other s columns
  are near zero while the curve content stays below K − M). The N-update
  audit was therefore expected to fail on those columns. The audit is
  unchanged. In the run it did not: the zero column agreed between the two
  resolutions (worst column 8.6e-5); the audit failed on field agreement.
- **Stop tests with the penalty.** The loss tolerance and the noise stop
  compare the penalised loss. Neither applies to noiseless hook c13.3.
- **E for every arm.** History rows keep the full coefficients. The report
  computes E and the speed ratio of every accepted curve from them. The
  penalty arm also logs E, λ_J, data loss and penalty loss live.

## Review before the run

A standards and a spec review ran before the run. Fixed: the uncentred update
no longer inherits spectral's class (flat-class rule, iteration 01 A1); λ_J is
set visibly at stage entry; the README lists the new names. Kept: duplicated
small methods between method files (accepted in iteration 01), the four tests,
and post-run E for arms without the penalty. Not covered: a trial refused by
the geometry checks saves no curve, so a video cannot show it.

## Tests

`pytest/bem_inverse/test_gauge_updates.py`, one check per new piece:

- uncentred refit: the trial is in the arclength gauge, and its slope is
  spectral's derivative;
- N-update: the trial equals the sampled z + ηN + τz′, and is exactly linear;
- slider: the step moves normally by h and keeps dJ/J even, against ξ = 0;
- level penalty: E equals the sampled spread, and the row derivative matches
  a central difference along a tangential column.

Full `pytest/bem_inverse` and the benchmark tests: 94 passed, 8 failed,
2 skipped. The 8 failures are the known ones: six extended-precision Bessel
comparisons and two validity-order comparisons.
