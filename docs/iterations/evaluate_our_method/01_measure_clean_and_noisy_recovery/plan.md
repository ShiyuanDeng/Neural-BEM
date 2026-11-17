# Measure clean and noisy recovery

Questions: how well does the default method recover shape and contrast on clean
TG-002 data? What changes with 1% noise across three fixed draws, and at each contrast?

## Status and original decisions

Runs completed on 17 November 2026. This plan was reorganised after execution;
it is a faithful summary of the pre-run choices, not a new experiment request.
The [original combined plan](../../../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md) and [earlier proposal and source checks](../../../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/02_proposals/01_stage_one_actions_verified.md) remain in the legacy workspace.

The user chose real-only observations, recovered contrast, a centred 65 mm start,
no localization, no warm-up and no tuning. Use `modal_muller` with `slider`.
The 10 TG-002 shapes at contrasts 0.5, 4 and 13.3 give 30 cases per run.

## Run matrix

| Data | Saved run under `results/bem/` | Fits |
|---|---|---:|
| Clean | `default_clean_uc_fc` | 30 |
| 1% noise, draw 0 | `default_n1d0_uc_fc` | 30 |
| 1% noise, draw 1 | `default_n1d1_uc_fc` | 30 |
| 1% noise, draw 2 | `default_n1d2_uc_fc` | 30 |

The user chose three shared noise draws. The implementation fixed seeds 0, 1, 2
and complex-Gaussian noise scaled per frequency. Save expected and realised levels;
all methods read the same arrays under `results/_shared/noise/`. No noisy run
receives damped observations. Five-percent noise was conditional on results and time.

## Shared method and scoring

Start with real 0.5 GHz, adding 0.75, 1.0 and 1.25 GHz one at a time. Then use all
19 real frequencies with shape bands 11, 15, 19, 25, 31 and 37, followed by an
adaptive tail up to 95 where the data supports it. The initial contrast uses the
weak-scatterer rule at the lowest real frequency available to the fit.

Recorded implementation: 13,412 work units and a nominal 120 s fit limit.
Stopping uses the existing residual, step and budget rules; noisy runs also use
the noise discrepancy rule. These limits do not use truth or recovery scores.

The user chose unaligned symmetric-difference area divided by true area as the
main metric, with **area error ≤5%** as provisional success. Score all components
and holes. Keep material-field error, boundary RMS, Hausdorff, Chamfer, centroid,
image scores, work counts and fit time. Changing the cut-off requires a dated recount.

The secondary old rule is boundary RMS ≤1 mm, Hausdorff upper bound ≤2 mm and
per-frequency residual within `max(0.003, 3 × realised noise)`. Protocol version 1
uses a shared 201 × 201 grid over ±0.1 m. Image support uses half the peak magnitude
with the peak's sign, even-odd filling and no minimum component size. Empty output
has area error 1. Image results also retain 0.3 and 0.7 threshold sensitivity scores.

The [saved clean manifest](../../../../results/bem/default_clean_uc_fc/run.json)
records exact settings, hardware and code revision. Fits run sequentially after an
untimed initialization solve; `fit_seconds` excludes the contrast-start solve,
final residual calculation and scoring. See [scoring.py](../../../../experiments/comparison/scoring.py)
and [noise.py](../../../../experiments/comparison/noise.py) for the fixed definitions.

## Independent forward check

Before inverse comparisons, compare `asymmetric__c4` at all 19 real frequencies
with RegPy. The predeclared limit is relative field difference ≤1e-6 at every
frequency. This is one independent forward check, not another fit.

## Budget, commands and outputs

These runs, the [ablations](../02_run_ablations/plan.md) and the
[untuned GauGal reference](../03_record_untuned_gaugal_reference/plan.md) shared the original six-hour limit.
Core runs came first; GauGal came last. The user later extended the limit to finish
the remaining listed commands. This reorganisation adds no run budget.

From the repository root, use the EMNerf Python:

```bash
python -m experiments.comparison noise --percent 1 --draws 0 1 2
python -m experiments.comparison forward-check
python -m experiments.comparison run bem/default_clean_uc_fc
python -m experiments.comparison run bem/default_n1d0_uc_fc
python -m experiments.comparison run bem/default_n1d1_uc_fc
python -m experiments.comparison run bem/default_n1d2_uc_fc
```

Each run stores `run.json`; each case stores `fit.json`, `fit.npz` and `score.json`.
[raw metrics](../../../../results/metrics.csv) holds the combined raw table. The forward check is under
`results/_checks/forward_regpy/`. Preserve failed fits and original manifests.
The runner resumes by skipping saved fits; these commands document the completed work.
