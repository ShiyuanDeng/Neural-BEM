# Compare the 14 clean TG-002 misses with the 16 passes

19 November 2026. The user chose the two suspects, missing warm-up and early stops, and requested matched tests on the clean TG-002 cases. I chose the cases and budgets below. The original measurements stay in place.

## Questions and saved evidence

Which shapes and contrasts miss the original 5% area rule? At which stage do their outline and recovered contrast separate from those of the passes? How often do the two groups hit iteration caps, stage work limits, whole-fit wall limits, optimizer stops and numerical refusals?

Read all 30 [original fits and scores](../../../../results/bem/default_clean_uc_fc/). Score their saved stage-exit curves against the sealed truths after fitting. Keep original final area scores. Record stage steps, loss, contrast, time, work and stop. Use the [damped ablation](../../evaluate_our_method/02_run_ablations/results.md) only for context. It also changed the data, weak start, ladder and return to real observations and omitted high contrast. Reuse [earlier contrast-4 cap tests](../01_trace_stage_stops_and_shape_bands/results.md) and the [Aphex Twin fourth-stage replay](../../evaluate_our_method/05_extend_aphex_fourth_stage/results.md).

## Matched comparisons

Use the same 19 sealed real-frequency observations, one centred 65 mm start, weak contrast estimate, recovered contrast, modal Müller solver, slider, no localization, one GPU process, 13,412 work units and nominal 120 s. Each intervention changes only the specified setting relative to that case's saved fit. Compare exact start values, settings and any unchanged prefix endpoints with the saved records. If a prefix disagrees materially, rerun its control before interpreting a difference.

- **Real warm-up.** Insert one fit at the existing real 0.25 GHz observation before the unchanged ladder. Borrow the older warm-up's update band 1, storage band 4, quota 600 and 44-step cap. Fit contrast in that stage. Keep the global limits. Test cog at 0.5 (lone low-contrast miss), kite at 4 (earlier longer caps failed), circle at 4 (passing control), circle at 13.3 (high-contrast miss without a capped ladder stage) and asymmetric at 13.3 (high-contrast miss with its weak estimate clipped to 0.05).
- **Early iteration cap.** On asymmetric at 13.3, change only its first capped stage, ladder stage two, from 22 to 220 iterations. Keep its quota, every other stage and both global limits. Compare the saved step-22 endpoint, the extended endpoint and the final recovery.
- **Whole-fit wall limit.** On C-shape at 13.3, change only the nominal time limit from 120 to 240 s. It had the highest second-stage contrast among the high-contrast misses and reached the second full-catalog stage before time ran out. Check the common accepted steps against the original endpoint.

The outcome is area error at most 5% at return. Record contrast, stop reason, work and stage scores even if recovery fails. Distinguish improvements that cross the threshold from improvements that still miss. A matched test only establishes the effect on that case. Treat end labels on other cases as observations.

## Commands, budget and output

From the checkout root with single-threaded BLAS, use the EMNerf Python:

```sh
export PYTHONPATH=solvers:.
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$P -m experiments.comparison.compare_clean_schedules inventory
$P -m experiments.comparison.compare_clean_schedules warmup CASE
$P -m experiments.comparison.compare_clean_schedules longer_stage asymmetric__c13.3
$P -m experiments.comparison.compare_clean_schedules longer_wall c_shape__c13.3
```

Seven planned new fits, one at a time, plus up to two same-case controls only for a mismatch or a time-sensitive verdict. The seven nominal limits sum to 16 fit minutes. Solver calls may overrun between checks. Wait for the measured worker to release the GPU. Save the 30-case and stage CSVs and one JSON per new fit in [results/bem/stage_scheduling/2026-11-19/clean_tg002](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/). Push each result before starting the next fit. Write findings in this activity's results.md.

## Coordinator's changes, 19 November 2026, 02:28 UTC

The first team (Codex tasks outside Herdr) was stopped by the user at 02:20 UTC, after the inventory and the circle warm-up control. The user then named Claude in Herdr pane `w4:p1` as coordinator: "you are the coordinator: i have two tasks for you to investigate overnight: failure of bem in 14/30 cases; and failure of bem in measured data case from csi." and "open two subagents here in herdr, based on task difficulty use astra and sol accordingly". The suspects are the user's, given in pane `w3:p1`: "my biggest suspects of these bem failures are about schedules, for examples missing warming up, early stops". The choices below are the coordinator's.

- **Warm-up on every miss.** Run the real 0.25 GHz warm-up on all 14 misses, not five. The denominator then needs no extrapolation. The nine added cases are `c_shape__c4`, `aphex_twin__c4` and the other seven at contrast 13.3. If the warm-up rescues a miss, also run it on the other 15 passes before calling it safe.
- **Third suspect, from the saved records.** Every miss ends with an outline that is too large and a contrast that is too low (kite and Aphex Twin near 2 at contrast 4; 0.0002 to 8.7 at contrast 13.3). The measured cylinder ends the same way (radius 19 mm, permittivity 2.2, nominal 15 mm and 3). Test whether the 65 mm start with the weak contrast estimate leads into a "large and weak" fit that later stages cannot leave. Use the saved stage records, and exact-circle loss maps over radius and contrast for the circle cases. No fit is needed for this part.
- **Refused trials.** In the measured fit every trial after stage three was refused as a self-intersection, down to steps of a few nanometres. Count stage exits where every trial was refused, by reason, in the 14 misses and the 16 passes, and find what makes the check refuse an almost unchanged curve.
- **Who runs what.** The agents are sandboxed (no GPU, no push), so the coordinator runs every GPU fit from pane `w4:p1`, one at a time, and commits by path. `tg-misses` (GPT-6.2-Astra, high) owns this activity's analysis and `results.md`.
- **Budget.** 13 more warm-up fits, the two planned cap and wall fits, and up to 15 warm-up controls on the passes: at most 30 fits at the unchanged 120 s nominal limit (240 s for the wall test). Follow-up fits beyond that need a new plan entry first.

## Round two, 19 November 2026, 02:47 UTC (coordinator)

First results of the warm-up on the misses (batch 01): it recovers `cog__c0.5`, `kite__c4`, `aphex_twin__c4` and `circle__c13.3`. It does not recover `c_shape__c4` (the known stage-one band cause) or the other nine contrast-13.3 cases. Those nine split in two groups in the saved stages:

- **Start on the wrong side of the background.** The weak estimate is below one for kite (0.485) and clipped at 0.05 for peanut, asymmetric, hook, cross and cog. The warm-up then drives the stored contrast to zero.
- **Warm-up cut at its cap.** Star, C-shape and Aphex Twin start above one and move towards 13.3 (12.3, 27.1, ...), but the warm-up ends at its 44-step cap with loss 0.37 to 0.47, and the fit later ends on the 120 s wall.

Round two tests those two readings, each arm changing one thing relative to the warm-up arm. Driver: `experiments/comparison/compare_clean_warmups.py` (coordinator's code; the first driver is untouched).

| Arm (output folder) | Change | Cases |
|---|---|---|
| `warmup_long` | warm-up cap 44 → 220 steps, quota 600 → 3,000 units | star, C-shape, Aphex Twin at 13.3 |
| `warmup_long_wall600` | the same, and nominal wall 120 → 600 s | the same three |
| `two_sided` | warm up from the weak estimate s and from its mirror image 2 − s (same strength, other side of the background); keep the side with the lower 0.25 GHz loss at the end of the warm-up | kite, peanut, asymmetric, hook, cross, cog at 13.3 |
| `two_sided_long` | two-sided and the longer warm-up | the same six |

The two-sided choice uses the fit's own loss only. It is a diagnostic of the start, not a proposed default: the user's rule is one centred start and no grid search, and whether a two-branch contrast start fits that rule is the user's call. The two extra warm-ups are outside the 13,412-unit budget and are recorded with their work.

Budget: 18 fits, 120 s nominal (600 s for three). One CPU self-test of the driver ran on `hook__c13.3` from 02:44 to 02:47 (two threads, output not kept as a result): the dense-side warm-up stalled at loss 0.40 after 14 steps, so the wrong side (0.21) was chosen and the fit failed as before. A first self-test at about 02:43 used the GPU for 16 s by mistake while `longer_stage asymmetric__c13.3` ran; that fit ends on iteration caps, not on time.

Commands, from the checkout root with the batch 01 environment:

```sh
$P -m experiments.comparison.compare_clean_warmups warmup_long CASE --warmup-iterations 220 --warmup-quota 3000
$P -m experiments.comparison.compare_clean_warmups warmup_long_wall600 CASE --warmup-iterations 220 --warmup-quota 3000 --seconds 600
$P -m experiments.comparison.compare_clean_warmups two_sided CASE --start two_sided
$P -m experiments.comparison.compare_clean_warmups two_sided_long CASE --start two_sided --warmup-iterations 220 --warmup-quota 3000
```

## Warm-up frequency control, 19 November 2026, 02:57 UTC (coordinator)

`tg-misses` proposed one control: the same band-1 warm-up at 0.5 GHz, the default ladder's first frequency, instead of 0.25 GHz. It separates two readings of the rescue: the extra low frequency, or the band-1 stage itself. Approved and widened from `circle__c13.3` to all four rescued cases (`cog__c0.5`, `kite__c4`, `aphex_twin__c4`). Budget: four fits at the unchanged limits, after round two. Output: `results/bem/stage_scheduling/2026-11-19/clean_tg002/warmup_050/`.

```sh
$P -m experiments.comparison.check_warmup_frequency CASE
```

## Round three: the measured cylinder's remedy on TG-002, 19 November 2026, 03:03 UTC (coordinator)

On the measured cylinder the fit that works settles a circle (band 1) on growing frequency sets and on the whole catalog, then runs the full-catalog stages only; re-running the low-frequency shape ladder after the circle stages destroys it ([measured plan](../../adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/plan.md)). TG-002 must say whether either form can be a common schedule.

| Arm (output folder) | Stages | Cases |
|---|---|---|
| `circle_then_default` | band-1 stages on 0.25 GHz, on each default ladder set and on the whole catalog; then the unchanged default schedule | all 30 |
| `circle_then_full` | the same band-1 stages; then the default full-catalog stages only (shape ladder dropped) | all 30 |

Driver: `experiments/comparison/compare_clean_circle_ladders.py` (coordinator's code). A CPU self-test on `star__c4` at about 03:00 (two threads, output not kept): `circle_then_default` reached 0.9% when the CPU run hit the wall; `circle_then_full` missed at 40%. Budget: 60 fits at the unchanged 120 s nominal limit, after round two and the frequency control. Pass rule unchanged (5% area). The comparison is against the plain warm-up (20/30) and the default (16/30).

```sh
$P -m experiments.comparison.compare_clean_circle_ladders circle_then_default CASE
$P -m experiments.comparison.compare_clean_circle_ladders circle_then_full CASE
```

## Round four: bands capped at the measured frontier, 19 November 2026, 03:17 UTC (coordinator)

**Why.** `cylinder` measured the solver's own observable frontier at each stage's frequencies ([note](stage_frontiers.md)). On the small measured cylinder it is 2, 3, 4, 5 on the ladder and 8 on the whole catalog, against default bands 3, 6, 9, 12 and 11 to 37. On the TG-002 contrast-4 truths it is above every ladder band. So the default releases shape detail the measured data cannot see, and not on TG-002. One rule may then serve both: cap each stage's band at the frontier measured when the stage is entered.

**Change.** Reference arm: the 0.25 GHz warm-up schedule. Before each later stage the runner measures the frontier at the current outline and contrast, at that stage's highest frequency, with the policy's own threshold (1%), and the stage runs with band max(1, min(default, frontier)). Storage follows the default formula. Stages, order, data, quotas, caps and limits are unchanged. Each measurement costs two work units. Code: [mixin](../../../../experiments/comparison/frontier_capped.py), [TG-002 driver](../../../../experiments/comparison/compare_clean_frontier_caps.py).

**Solver change, approved by the coordinator.** One line in [`runner.py`](../../../../solvers/bem_inverse/runner.py): a frontier operation may name the real observation it measures at (`details['observation_index']`); without that key it measures at the highest real frequency as before. The default path is unchanged. Check: the `frontier_measured` control (measurements made, no band changed) reproduced the saved warm-up fit of `kite__c4` stage for stage at 03:13 (same steps, losses and contrasts; 20 more work units). The capped arm changed only its last two stages there (bands 31 and 37 to 26) and returned 0.29% (warm-up arm 0.10%).

| Arm (output folder) | What | Cases |
|---|---|---|
| `frontier_capped` | bands capped | all 30 |
| `frontier_measured` | control, no band changed | `circle__c4`, `kite__c4`, `star__c13.3`, `aphex_twin__c0.5` |

Budget: 34 fits at the unchanged 120 s nominal limit, after round three. Reading: the capped arm must keep the warm-up arm's 20 recoveries to be a candidate default; the measured cylinder's result is in the measured activity.

```sh
$P -m experiments.comparison.compare_clean_frontier_caps frontier_capped CASE
$P -m experiments.comparison.compare_clean_frontier_caps frontier_measured CASE
```

**Round four withdrawn, 03:35 UTC (coordinator).** The measured-cylinder fit with the same rule failed at 03:29 (area error 87%, forward-solver failure at the fourth ladder stage; [measured plan](../../adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/plan.md)). The frontier measured on the way was 1, 1, 3 and 10 at the four ladder stages: on a small, strong outline the 1% rule lets shape detail through that the noisy data cannot fix. The rule is therefore not a candidate common default, and the 30-case run was removed from the queue before it started. What stands from this round: the `kite__c4` test (capped 0.29%, control identical to the warm-up arm) and the runner hook, which stays default-preserving.

## Disk-start diagnostic, 19 November 2026, 03:17 UTC (coordinator)

`tg-misses` found that a truth-free search over exact disks on the real 0.25 GHz data gives a close start for four of the nine contrast-13.3 misses (kite, star, cross, cog) and a wrong one for five. Approved as a diagnostic on those four: the disk start, then the same warm-up and ladder. The user's default is localization `none` and no grid search, so this tests the cause (the start), not a proposed default. Budget: four fits. Driver: `experiments/comparison/check_localized_real_warmup.py` (the agent's).

```sh
$P -m experiments.comparison.check_localized_real_warmup CASE
```

### Check a second real frequency on the five missed disk starts

The coordinator requested a CPU diagnostic on peanut, asymmetric, C-shape, hook and Aphex Twin at 13.3. Repeat the bounded joint disk search twice, adding 0.375 or 0.5 GHz to 0.25 GHz. Use one common disk across frequencies and equal B5 weights. Repeat on the independent mesh from Task 4. Save the selected starts before scoring radius (within 10%) and contrast (within 15%). Compare the measured ring responses at 0.25 GHz to explain the original selections. Budget two meshes, five cases, two frequency pairs, at most four CPU threads. Run `$P -m experiments.comparison.compare_real_disk_frequencies` with BLAS/OpenMP limited to two threads. Outputs go to `results/bem/stage_scheduling/2026-11-19/real_disk_frequency_pairs/`.

The first two meshes disagreed on Aphex Twin with 0.5 GHz. Check that ranking with a third mesh (57 × 57 centres, 61 radii, 201 contrasts), refining up to 50 local minima plus previous observation-only minima. Compare all five cases on this mesh to check for other changes of rank.

## Warm-up under noise, 19 November 2026, 03:37 UTC (coordinator)

The clean result (16/30 to 20/30, every pass kept) rests on one data set. The saved default fits on the first 1% noise draw also recover 16/30, with the same contrast-4 misses. Run the same warm-up on that frozen draw, all 30 cases, to see whether the effect repeats under noise. The fit keeps the declared noise level it had in the saved run (loss weights and the discrepancy stop). Driver: `experiments/comparison/compare_noisy_warmups.py` (coordinator's code). A self-test on `kite__c4` at 03:36 (output not kept, four measured fits were sharing the machine) returned 0.73% against the saved 336.8%. Budget: 30 fits at the unchanged limits, after the disk-start diagnostic. Output: `results/bem/stage_scheduling/2026-11-19/noisy_tg002/warmup_n1d0/`.

```sh
$P -m experiments.comparison.compare_noisy_warmups CASE --draw 0
```

## Round five: warm-up with wider early bands, 19 November 2026, 05:16 UTC (coordinator)

`c_shape__c4` is the one miss at contrasts 0.5 and 4 that the warm-up does not recover (44%). The [earlier activity](../01_trace_stage_stops_and_shape_bands/results.md) showed its cause by a matched test: the first stage at band 3 closes the opening, and ladder bands 5, 7, 9, 11 recover it (0.07%) without a warm-up. The [frontier measurements](stage_frontiers.md) agree: every tested TG-002 truth supports more than the default ladder bands. That activity left one question open: whether the wider ladder is safe on the other cases. Test it together with the warm-up, which is the arm that now recovers the other four.

Arm `warmup_wide`: the warm-up arm with each ladder band two higher, built as the 18 November `wider` arm. All 30 cases, so the count needs no extrapolation. Budget: 30 fits at the unchanged limits, after round three. Driver: `experiments/comparison/compare_clean_wide_ladder.py` (coordinator's code). Reading: recovery of `c_shape__c4` with every warm-up pass kept would put contrasts 0.5 and 4 at 20/20; any lost pass counts against the wider ladder.

```sh
$P -m experiments.comparison.compare_clean_wide_ladder CASE
```
