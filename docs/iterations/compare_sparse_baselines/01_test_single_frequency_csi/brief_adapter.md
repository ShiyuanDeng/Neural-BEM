# Brief for `native-adapter`: acquisition adapter and forward check

You are a subagent of the baseline coordinator (Claude, Herdr pane
`w5:p1`). Work in `/home/drdeng/Neural_SDF_BEM_AD_organised`, branch
`organised`. Do not create a branch or worktree. Read `AGENTS.md` and
[plan.md](plan.md) first. Times are UTC; take them from `date -u`.

## Goal

Feed the sealed native TG-002 observations at 0.5 GHz to the pinned
classical CSI code, for `circle__c4` and `kite__c4`, and prove the
adapter is right before any inversion runs. You run no inversion.

## What is fixed

- Data: the sealed real catalog, the 0.5 GHz column, 24 complex
  readings per case. Loader: `experiments/comparison/bem.py`
  (`observations`) and `experiments/cleaned_interface/benchmark.py`
  (`acquisition`, `observations`). Noise draw 0 lives in
  `results/_shared/noise/n1d0/<case>.npz`; support `--data n1d0` too.
- Acquisition: 24 sources on the 0.30 m ring, one receiver 0.20 rad
  ahead of each source. Keep the pair order. Source strength as in the
  native model. No fitted gain or phase anywhere.
- Material: exterior relative permittivity 6, interior 24 (ratio 4).
  The background wavenumber must equal the native one. You may use the
  native material argument or the exact equivalent frequency in vacuum.
  Record which, and how the image converts to the ratio (true value 4).
- Phase convention: our BEM uses exp(-j omega t); CC-CSI uses
  exp(+j omega t). Declare each conjugation and scale you apply.
- Inverse grid: 166 by 166 cells of 1.25 mm, centred on the ring
  centre, as in `experiments/baselines/csi/campaign_ten_frequency.py`.
- Pinned code: `~/neural_bem_external/CC-CSI` at `73a64e1` and
  `~/neural_bem_external/maxwellfdfd`. Do not edit them. `CSI.m` must be
  byte-identical to the commit. The old reader assumes a 36-by-49 vacuum
  table, so write an owned configuration instead of patching upstream.
- Earlier work to reuse: `experiments/baselines/csi/generate_synthetic.m`
  (FDFD forward on the native material path), `circle_grid_check.py`,
  `docs/iterations/csi_adaptation/03_prepare_simulated_tg002_cases/`
  (`pipeline.md`, `frame.md`) and `05_check_circle_grid_convergence/`.

## Deliverables

Code in `experiments/baselines/csi/native_tg002/`. You own `inputs.py`,
`check_table.py`, `check_forward.py` and these MATLAB functions:

- `native_configuration(input_dir)` returns everything `CSI.m` needs
  (`Emea, Phi, A, chi, vJ, eIncInv, eTot, pars`) with the native
  back-propagation start, plus an `info` struct: grid axes in metres
  relative to the ring centre, cell size, mask indices, and the scale
  and conjugation that return a field to native units.
- `native_predict(chi_image, config)` returns the 24 predicted scattered
  readings in native units for an image on the inverse grid. The run
  agent uses it for the final-image residual.

Do not create or edit `fit.py`, `native_fit.m` or `score.py`: the
`native-run` agent owns those. Tell the coordinator the function
signatures as soon as they are stable.

Commands, exactly as in [plan.md](plan.md) (tell the coordinator before
changing a command, so the plan is updated first):

1. `inputs`: write `RUN/inputs/<case>__<data>/` with the frozen 24
   readings, positions, wavenumber, the CSI table or arrays, the mask,
   and `inputs.json` holding SHA-256 of the sealed file, the noise file
   if used, the 24 readings, the table, the mask, `CSI.m`, and both
   pinned commits with their dirty state.
2. `check_table`: read the saved input through `native_configuration`.
   Require an exact pair-index match and a relative round-trip error
   below 1e-10 on the 24 readings after undoing conventions. Show that
   CSI scores exactly 24 readings: mask size, non-zeros of `Emea`, the
   data normaliser and the data residual of `CSI.m`. Record the native
   back-propagation normalisation, which uses the full operator.
3. `check_forward`: for `circle__c4`, predict the 24 scattered readings
   with the same 1.25 mm operators `CSI.m` receives, using the true
   circle. Compare with the exact circle: the sealed readings and an
   independent analytic series if one is at hand
   (`solvers/bem_inverse/mie_grid.py`). Pass: relative error at most 1%
   over the 24 readings with no fitted gain or phase. Also record the
   0.625 mm value, and the best-fit complex gain as a diagnostic only.

Results go to `results/csi/native_tg002/2026-11-19/inputs/` and
`checks/`. Write `adapter_report.md` in this folder.

## Rules

- If the round trip or the forward check fails, stop. Save the
  discrepancy (numbers, per-pair table, what you ruled out) and report
  it to the coordinator. Do not loosen a limit or add a fitted factor.
- One MATLAB process at a time, `maxNumCompThreads(8)`, no GPU. Before
  each MATLAB launch check that `pgrep -x MATLAB` is empty and that
  `MemAvailable - 8 GiB - expected growth of other jobs >= 16 GiB`.
  The coordinator gives the growth figure; until then count each
  BEM-side Python fit process up to 4 GiB. If the rule fails, tell the
  coordinator and wait. Save the sample with each check.
- Minimal tests: each command runs end to end and the checks above.
- You have full access. Do not ask for approvals.
- Git: the index is shared. Commit only your own paths with
  `git commit -m "..." -- <paths>`, then `git push`. Commit after the
  inputs and after each check, failures included. Keep each commit
  under about 5 MB; leave bulk local with its SHA-256 recorded.
- Other agents work in this checkout. Do not touch their files, the
  solver, the scoring code or `AGENTS.md`.
- Questions on physics, data or settings go to the coordinator: stop
  and ask in your pane.
- Terminal answers: at most three lines per paragraph, plain words.

## Report

End with this block, and wait:

```text
Activity: compare_sparse_baselines/01_test_single_frequency_csi (adapter), <date>
Runs: <done>/<planned>; wall time <h:mm>
Result: <input hashes; round-trip error; readings scored; forward error at 1.25 and 0.625 mm>
Failures: <what failed, where the log is>
Upstream patches: <none | files>
Changes to our code: <files>
New unknowns: <list>
Proposed next activity: <one line>
```
