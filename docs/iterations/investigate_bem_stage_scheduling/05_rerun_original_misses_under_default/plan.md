# Rerun the four original misses under the default with warm-up

19 November 2026, 15:15 UTC. Coordinator: Claude, Herdr pane `w4:p1`. Follows [activity 04](../04_adopt_warmup_and_supply_contrast/results.md).

## The user's words

Reading row A of the [final comparison report](../../final_comparison_report.md): "A. Original TG-002, 20 clean cases at contrasts 0.5 and 4 16/20 recovered, this is before warmup?? if so add warmup and quickly rerun the 4 failure cases".

- **Answer to the question:** yes. 16/20 is the 17 November default, which had no warm-up ([fits](../../evaluate_our_method/01_measure_clean_and_noisy_recovery/results.md)).
- **The four misses:** `cog__c0.5` (17.1%), `kite__c4` (467%), `c_shape__c4` (43.8%), `aphex_twin__c4` (197%).
- **"Add warmup":** done this afternoon. The warm-up is in the solver's default since commit `08200b1ab`.

## Question

Do the four cases recover under the default as it now stands?

## What is already known

- Last night all four were fitted with the same stage list, built on the experiment side: `cog__c0.5` 0.300%, `kite__c4` 0.098%, `aphex_twin__c4` 0.223%, `c_shape__c4` 43.97% (numerical failure). Three of four recover; that gives 19/20.
- `kite__c4` has already gone through the new default (13:50 UTC today): 0.098%, the same outline in all 11 stages. It is not run again.

## Test

The other three, through the default policy unchanged (`experiments.comparison.bem.policy`): sealed clean real data, the centred 65 mm start, weak contrast estimate then fitted contrast, `modal_muller`, `slider`, no localization, 13,412 work units, 120 s nominal wall.

**Comparison.** Each fit is compared stage for stage with last night's warm-up fit of the same case. Pass: same stage count, bands and accepted steps, outlines equal to 1e-9 relative.

**Success.** Recovery is an area error of 5% or less. The count out of four is the answer.

## Budget and one known risk

Three fits, one at a time. Alone on the GPU they took 10 s, 46 s and 56 s last night.

**The GPU is not free.** Four GauGal processes of the baseline coordinator (`w5`) are running at 95% load, and the user asked for a quick rerun. So these fits share the GPU. The work-unit limit does not depend on speed, but the 120 s wall does. If a fit ends on the wall, that is sharing, not the method: it is reported as such and run again when the GPU is free. A note goes to `w5:p1`, since its timings are shared for these minutes.

## Commands and outputs

```bash
cd /home/drdeng/Neural_SDF_BEM_AD_organised
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
for c in cog__c0.5 c_shape__c4 aphex_twin__c4; do
  $P -m experiments.comparison.compare_clean_default_contrasts recovered $c
done
```

Run from the detached launcher `results/bem/stage_scheduling/2026-11-19/clean_tg002/logs/batch_12_original_misses.sh`, with `batch_12.state` beside it. Do not relaunch it while that file exists.

Outputs: `results/bem/stage_scheduling/2026-11-19/clean_tg002/default_recovered/<case>.json`. Driver: [`compare_clean_default_contrasts.py`](../../../../experiments/comparison/compare_clean_default_contrasts.py).
