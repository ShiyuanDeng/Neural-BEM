# GGB-003 runs: commands in order

Questions: How well does the real-only, unknown-contrast default recover TG-002, clean and with noise?
What changes with damped data, the nodal backend, a fixed shape band, all frequencies at once, or one frequency?

Plan: [GGB-003](../../docs/iterations/gaugal_comparison/iteration_02/03_plan.md).
Scoring rules: the docstring of [scoring.py](scoring.py). Noise rule: [noise.py](noise.py).

## How to run

Use the repository root and the EMNerf Python. The driver sets its own import paths and
single-threaded BLAS; no environment variables are needed.

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.comparison list                              # progress table
$PY -m experiments.comparison noise --percent 1 --draws 0 1 2   # shared noisy data, once
$PY -m experiments.comparison forward-check                     # run 10, about 30 s, no fit

$PY -m experiments.comparison run bem/default_clean_uc_fc        # run 1
$PY -m experiments.comparison run bem/default_n1d0_uc_fc         # run 2
$PY -m experiments.comparison run bem/default_n1d1_uc_fc
$PY -m experiments.comparison run bem/default_n1d2_uc_fc
$PY -m experiments.comparison run bem/default_clean_kc_fc        # run 3
$PY -m experiments.comparison run bem/default_cleandamped_uc_fc  # run 4
$PY -m experiments.comparison run bem/nodal_clean_uc_fc          # run 5
$PY -m experiments.comparison run bem/nodal_n1d0_uc_fc
$PY -m experiments.comparison run bem/fixedband37_clean_uc_fc    # run 6
$PY -m experiments.comparison run bem/default_clean_uc_fs        # run 7
$PY -m experiments.comparison run bem/default_clean_uc_sf0.5     # run 8
$PY -m experiments.comparison run bem/default_clean_uc_sf1
$PY -m experiments.comparison run bem/default_clean_uc_sf1.5
$PY -m experiments.comparison run bem/default_clean_uc_sf2
$PY -m experiments.comparison import-ggb002                      # saved clean GauGal fits, no refit
$PY -m experiments.comparison run gaugal/default_n1d0_uc_fs      # run 9, last, about 2 hours
```

- Each `run` picks its planned cases, skips fits already saved, scores each fit and rebuilds
  `results/metrics.csv`. Running the same command again continues where it stopped.
- One run at a time. Timings are recorded, so do not run two commands together.
- After each run: commit and push `results/` (code too if it changed), then go on.
- The first named follow-up is `bem/default_n5d0_uc_fc`; `run` writes the 5% noise itself.

## If something goes wrong

- A fit that fails is a result. It is saved and scored like any other; do not rerun it.
- If the command itself dies, run it again. `clean` removes case folders left without a
  finished fit. If it dies again on the same case, stop and report the last output lines.
- If scoring fails, the fits are safe. Report it; after a fix, `score <family>/<run>`
  rescores without refitting.
- Do not edit solver or scoring code to get a run through, and do not change settings.
  `run.json` is written once per run; changed settings are refused.

## What is where

| File | Role |
|---|---|
| [runs.py](runs.py) | Run names, the planned run table, the storage layout |
| [noise.py](noise.py) | The noise rule and the saved noisy data |
| [bem.py](bem.py) | Our method: one fit, no truth files opened |
| [gaugal.py](gaugal.py) | GauGal with the saved GGB-002 setting, untuned |
| [scoring.py](scoring.py) | Every truth-based score; the only reader of truth files |
| [forward_check.py](forward_check.py) | Run 10: one sealed field against RegPy's operators |
| [test_comparison.py](test_comparison.py) | Names, noise rule and scoring on shapes with known answers |

Storage, under `results/`:

```
_shared/noise/<data>/<case>.npz     noisy data, read by every family
_checks/forward_regpy/<case>.json   run 10
metrics.csv                         one row per fit, raw numbers only
<family>/<run>/run.json             settings, written once
<family>/<run>/<case>/fit.json fit.npz score.json
```

`fit.*` holds solver output only. `score.json` is written by the separate scoring step.
The success cut-off is not stored; `list` prints provisional counts at 5% area error.
