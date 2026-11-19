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

## Coordinator's changes, 19 November 2026, 02:28 UTC

The first team (Codex tasks outside Herdr) was stopped by the user at 02:20 UTC, 86 s into the warm-up fit. Its partial output stays as `warmup/dielTM_dec8f/cuda/attempt_01` (three stages saved, no score). The user named Claude in Herdr pane `w4:p1` as coordinator and asked for two subagents in Herdr. The choices below are the coordinator's.

- **Reruns.** The warm-up fit is run again in full as `attempt_02`; `first_cap` as planned. The coordinator runs both from pane `w4:p1`, because the agents are sandboxed without a GPU.
- **What the stopped run already shows.** The 1 GHz warm-up drove the contrast from 1.09 to 32.6 in 44 steps while loss fell to 0.0860; the original first stage reached 0.0909 at contrast 1.73. Two very different circles fit 1 GHz about equally. So add a loss map: measured-data loss of an exact circle over radius and permittivity, for the frequency sets of each stage (1; 1–2; 1–3; 1–4; 1–8 GHz), with the paths of the original fit, the warm-up fit and the first-cap fit drawn on it. CPU only.
- **Refused trials.** In the saved fit all 763 refused trials checked so far say `self_intersection`, including steps of 7 nm. Item 3 of the comparisons is therefore sharpened: decide whether the accepted stage-three curve itself fails the slider's intersection check, which accepted step introduced that, and whether the crossing is real on a fine grid. `tg-misses` (GPT-6.2-Astra, high) does this part, because the same check runs on TG-002; `cylinder` (GPT-6.1-Sol, medium) owns the loss map, the fit comparison and `results.md`.

## Round two: settle circle-scale geometry before shape release

19 November 2026. These two variants are the coordinator's choice. Question: if radius, place and material are settled on several frequencies before shape detail is released, does the fit reach the best-circle region (15.3 mm, permittivity 3.05, loss 0.0375) and stay near it? Band 1 with storage 4 is the existing low-detail warm-up parameterization, not a constraint to an exact disk.

Both variants start with five real-data stages: `circle_1_real` on 1 GHz, `circle_2_real` on 1–2, `circle_3_real` on 1–3, `circle_4_real` on 1–4, and `circle_full_real` on all eight frequencies. Each uses update band 1, storage band 4, quota 600 and 44 iterations. `circle_ladder` replaces the original four ladder stages, then keeps the original full-catalog stages, cleanup and frontier verbatim. `circle_then_ladder` prepends the five stages to every original operation verbatim.

Budget: two additional CUDA fits, run by the coordinator, each capped at the saved 3,600 s and 13,412 total work units. The added stage quotas do not raise that global cap. Keep the measured input, centred start, weak material estimate, slider, modal Müller, fitted material and other settings unchanged. Compare circle-stage exits and final results with the saved control and best circle: measured loss, radius, centre, permittivity and nominal area error; distinguish arrival near the circle from staying there after shape release.

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_measured_warmups.py circle_ladder
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_measured_warmups.py circle_then_ladder
```

Outputs: `results/bem/baseline_data/measured_schedule/2026-11-19/{circle_ladder,circle_then_ladder}/dielTM_dec8f/cuda/attempt_01/`, through the existing wrapper's attempt handling. Keep manifests, fits, stage/trial records, scores and failures; the coordinator commits them. Write comparisons in `results.md`.

Dry check, with no fit or forward solve: `/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_measured_warmups.py --dry-check`. It passed for both variants: input hash, original operation records, retained operation records, five added stage settings and saved global limits all match. It prints labels, frequencies, update/storage bands, quotas and iteration caps.

## Round three: bands capped at the measured frontier, 19 November 2026, 03:20 UTC (coordinator)

Round two showed that the band-1 stages on growing frequency sets reach the best circle and that the default low-frequency shape ladder then destroys it. The [frontier measurements](../../investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/stage_frontiers.md) say why: at the best circle the data support bands 2, 3, 4, 5 on the ladder and 8 on the whole catalog, against default bands 3, 6, 9, 12 and 11 to 37.

Test a rule that could also serve TG-002: keep the 1 GHz warm-up and every original stage, but cap each stage's band at the frontier measured when the stage is entered (current outline, that stage's highest frequency, the policy's 1% threshold; at least band 1). Reference: the `warmup` variant. Driver: `experiments/bem_on_baseline_data/csi_measured_frontier_caps.py` (coordinator's code; mixin in `experiments/comparison/frontier_capped.py`). It needs the one-line runner change recorded in the [TG-002 plan](../../investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/plan.md); the default path is unchanged. A dry check without a fit showed the expected queue: warm-up, then one measurement before each stage, ragged data kept, limits 13,412 units and 3,600 s.

| Variant | What |
|---|---|
| `frontier_capped` | bands capped |
| `frontier_measured` | control: the same measurements, no band changed; should repeat the `warmup` variant |

Budget: two fits. Compare with the saved fit, the `warmup` and `circle_ladder` variants and the best circle (15.27 mm, 3.05, loss 0.0375).

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_measured_frontier_caps.py frontier_capped
/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_measured_frontier_caps.py frontier_measured
```
