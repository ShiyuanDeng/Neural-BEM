# Test the measured cylinder schedule

19 November 2026. The user chose the original measured Fresnel cylinder, missing warm-up and early stops as the leading suspects, matched tests, and one centred start. This activity tests BEM on that one measured case. The results from 18 November remain the reported baseline.

## What the saved fits show

The original CUDA fit completed all ten stages with 894 of 13,412 work units. Only the first stage reached its 22-step cap. The other nine ended with no decreasing step. At the six zero-step stages, every recorded trial failed geometry checks, before a candidate loss was evaluated. The CPU cross-check stopped after 134 s on its separate 120 s limit. [GPU and CPU receipts](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/)

The nominal cylinder has radius 15 mm, centre (0, 30) mm and relative permittivity 3 ± 0.3. A previously fitted exact circle on these data gives radius 15.3 mm, centre (1.9, 26.2) mm and permittivity 3.05. Its all-frequency loss is 0.0375 versus 0.0840 for BEM. Nominal shape error therefore includes position uncertainty. [Circle comparison](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json)

## Comparisons

Use the saved CUDA fit as control. Check the hash of the original eight-frequency input and the generated baseline operation records against the saved manifest. Use the original 3,600 s ceiling, four frequency threads, 13,412 work units, measured rows and calibration. Pin BLAS to one thread as in the current wrapper; compare outcomes and the unchanged prefix numerically. Timing comparisons with the original would include host load and BLAS differences.

1. Prepend one narrow-band warm-up at the lowest measured frequency (1 GHz), then run every original stage verbatim. The warm-up uses the established 1-mode update, 4-mode storage, 44 iterations and 600 units. Use the same slider, objective, fitted contrast and weak start throughout. No extra observations. This tests a real-frequency warm-up available on this cylinder.
2. From the original start, raise only the first ladder stage's iteration cap from 22 to 220. Keep its 1,000-unit limit, the remaining operations and the whole-fit limits. Compare the first 22 accepted losses and boundary to the saved run. Measure whether more steps at the cap change the end result.
3. Use the saved trials to count the actual reasons the later stages exited. Check the stage-entry curve on the slider's validation grid for the first zero-step stage and the first zero-step all-frequency stage. This distinguishes a refused proposal from a data loss that failed to fall. If a late stage is already blocked by an invalid unchanged entry on its check grid, a larger iteration cap cannot force another iteration past that refusal.

## Settings, budget and decision

Use the original centred 65 mm circle, weak material estimate from 1 GHz, recovered contrast, eight frequencies at 1–8 GHz, modal Müller, slider, zero damping of the observations, no localization, no declared noise level and the original series limit. Truth enters only in scoring after the fit. No changes to the maintained solver.

Budget two full CUDA fits, each at most 3,600 s and 13,412 units. Reuse the control. Commit and push each run, including a failed fit, before starting the next. Compare per-stage stops, accepted steps, trial refusals, matched initial trajectories, work units, all-frequency loss, radius, centre, nominal area error and permittivity. Record any geometry repair during scoring.

Call a schedule change an improvement in recovery if it reduces measured loss and nominal area error, and moves radius and permittivity closer to nominal. Report mixed results as such. Compare the final loss and geometry with the independent circle fit; keep the measured-case uncertainty explicit. The iteration limits above and these criteria are investigator choices.

## Commands and output

From the checkout root, run each command once with the EMNerf Python. The comparison script reuses the measured adapter and fit wrapper.

```bash
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$P experiments/bem_on_baseline_data/csi_measured_schedule.py warmup
$P experiments/bem_on_baseline_data/csi_measured_schedule.py first_cap
```

The script writes under `results/bem/baseline_data/measured_schedule/2026-11-19/{warmup,first_cap}/dielTM_dec8f/cuda/attempt_01/`. Keep the manifest, fit, stage and trial records, curve, score and residuals. Write the comparisons in [results.md](results.md).
