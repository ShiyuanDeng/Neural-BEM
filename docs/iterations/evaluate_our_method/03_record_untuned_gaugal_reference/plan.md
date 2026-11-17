# Record the untuned GauGal reference

Question: what does GauGal produce on the shared first 1% noise draw when its
settings from the 2 November 2026 comparison are reused without tuning?

## Status and scope

The noisy run completed on 17 November 2026. Thirty older clean fits were imported
and rescored that day, without refitting. This document separates that reference
work from the [original combined plan](../../../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md); it does not turn it into a fair external-baseline study.

The user required GauGal to run last and remain untuned. New fits cover only the
20 cases at contrasts 0.5 and 4. Imported clean results cover the original 30 cases;
show contrast 13.3 separately and use only the shared 20 for cross-method tables.

Use the same shared noisy observations and
[all-component scoring protocol](../01_measure_clean_and_noisy_recovery/plan.md). GauGal receives observations
only; the adapter removes the truth fields before fitting. Unlike the BEM noise
runs, it is not given noise levels for a discrepancy stopping rule.

## Frozen settings and budgets

The [noisy run manifest](../../../../results/gaugal/default_n1d0_uc_fs/run.json)
records grid 51, width 0.7, TV weight 0.5, step 0.05, susceptibility upper limit 15,
80 iterations and all 19 real frequencies simultaneously. These settings came
from clean-circle tuning on 2 November; there was no new tuning on 17 November.

Allow 400 s optimization and 600 s outer time per case, one child process per fit.
This activity shared the original six-hour total; the user's later continuation
request covered its completion after the ablations. Original native cylinder
runs used different data/settings and took seconds per case; these TG-002 timings
must not be presented as GauGal's general runtime.

## Commands and outputs

From the repository root, use the EMNerf Python:

```bash
python -m experiments.comparison import-gaugal-2026-11-02
python -m experiments.comparison run gaugal/default_n1d0_uc_fs
```

The import command now reads the preserved historical endpoints from
`/home/drdeng/Neural_SDF_BEM_AD/development_results/`. Its descriptive name replaced
the older command after execution; the saved logs retain the command actually used.

Current records are in `results/gaugal/default_clean_uc_fs/` and
`results/gaugal/default_n1d0_uc_fs/`, with a manifest per run and fit/score files
per case. Use [raw metrics](../../../../results/metrics.csv) for the common table. Report failures and incomplete
recovery even when the optimizer exits normally.
