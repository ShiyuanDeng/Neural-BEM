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
