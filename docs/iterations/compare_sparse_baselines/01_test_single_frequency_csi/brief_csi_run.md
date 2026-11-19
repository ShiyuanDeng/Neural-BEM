# Brief for `native-run`: the CSI fits, scores and records

You are a subagent of the baseline coordinator (Claude, Herdr pane
`w5:p1`). Work in `/home/drdeng/Neural_SDF_BEM_AD_organised`, branch
`organised`. Do not create a branch or worktree. Read `AGENTS.md` and
[plan.md](plan.md) first. Times are UTC; take them from `date -u`.

## Goal

Run the pinned classical `CSI.m` on the native 24-pair data at 0.5 GHz
for clean `circle__c4`, then clean `kite__c4`, and score both.

**Launch no fit until the coordinator writes "checks passed, go".**
Until then, prepare and test the launcher and the scoring.

## What is fixed

- Method: `~/neural_bem_external/CC-CSI/functions/CSI.m` at `73a64e1`,
  unchanged. Native back-propagation start, one start per case, no
  tuning, 2,048 iterations. Keep the settings the earlier classical CSI
  runs used (see `experiments/baselines/csi/campaign_case.m`,
  `csi_record_snapshot.m`, `save_outputs.m`). Pass `epsinv` empty so no
  truth enters the fit.
- Inputs and operators come from the `native-adapter` agent:
  `native_configuration(input_dir)` and `native_predict(chi_image,
  config)` in `experiments/baselines/csi/native_tg002/`. Do not edit
  its files. If something there looks wrong, tell the coordinator.
- Scoring: `experiments/comparison/scoring.py`, frozen. Do not edit it.
  Earlier CSI scoring to adapt: `experiments/baselines/csi/
  registered_metrics.py` and `register_saved.py`.

## Deliverables

You own `fit.py`, `native_fit.m` and `score.py` in
`experiments/baselines/csi/native_tg002/`, and
`results/csi/native_tg002/2026-11-19/fits/` and `logs/`.
Commands exactly as in [plan.md](plan.md).

`fit` must:

- Refuse to start unless the adapter's checks are marked passed for
  that input, no MATLAB runs (`pgrep -x MATLAB`), and
  `MemAvailable - 8 GiB - expected growth of other jobs >= 16 GiB`.
  Expected growth: count each BEM-side Python fit process up to 4 GiB,
  unless the coordinator gives another figure. Save the sample.
- Start MATLAB detached (`setsid nohup`), `maxNumCompThreads(8)`, no
  GPU, with a state file. Limit its process family to 8 GiB
  (`systemd-run --user --scope -p MemoryMax=8G` if it works here, else
  a watcher that stops the group above 8 GiB). No stop on time.
- Record the wall time at iteration 64 and the projected finish. Send
  both to the coordinator when the first fit reaches iteration 64.
- Save the final image, the 64-step snapshots, the cost log, the MATLAB
  log, resource samples, timing and the input hashes it read.

`score` must write `score.json` per case with:

- area error at half the signed peak, and at 0.3 and 0.7;
- material error on the shared scoring grid, with the image converted
  to susceptibility relative to the background (true value 3);
- the relative scattered-field residual over the 24 readings, predicted
  from the final image with `native_predict`. Report CSI's own data and
  state costs separately; they are a different quantity;
- runtime, peak memory, failures.

Two self-tests before the first fit, saved under `checks/`:

1. Score the true circle sampled on the inverse grid through your
   scoring path. Area error must be near zero; this proves the frame.
2. Predict the 24 readings from that true image. The residual must
   match the adapter's forward-check error.

Also copy the two BEM rows for the table: area error, material error
and field residual from `results/bem/default_clean_uc_sf0.5/
{circle__c4,kite__c4}/` (`score.json`, `fit.json`). Do not rerun BEM.

## Rules

- A fit that fails is a result. Keep it, commit it, report it. Do not
  rerun without the coordinator's word.
- One MATLAB at a time. Circle first, then kite. The noisy pair runs
  only if the coordinator says so.
- You have full access. Do not ask for approvals.
- Git: the index is shared. Commit only your own paths with
  `git commit -m "..." -- <paths>`, then `git push`, after each run.
  Keep each commit under about 5 MB; leave bulk local and record its
  SHA-256. `/results/**/*.npz` and `*.png` are git-ignored: put report
  figures in this folder's `figures/`.
- Do not touch other agents' files, the solver or `AGENTS.md`.
- Questions on physics, data or settings go to the coordinator: stop
  and ask in your pane.
- Terminal answers: at most three lines per paragraph, plain words.

## Report

Write `run_report.md` in this folder. End with this block, and wait:

```text
Activity: compare_sparse_baselines/01_test_single_frequency_csi (runs), <date>
Runs: <done>/<planned>; wall time <h:mm>
Result: <per case: area error at 0.5, 0.3, 0.7; material error; field residual; runtime>
Failures: <what failed, where the log is>
Upstream patches: <none | files>
Changes to our code: <files>
New unknowns: <list>
Proposed next activity: <one line>
```
