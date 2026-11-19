# Brief for `tg-misses` (GPT-6.2-Astra, high), pane `w4:p2`

From the coordinator, Claude in pane `w4:p1`. 19 November 2026, 02:30 UTC.

## The question

The user wants to know overnight why our BEM inverse misses 14 of the 30 clean TG-002 cases, and why it does poorly on the measured Fresnel cylinder. The user's suspects, in their words: "my biggest suspects of these bem failures are about schedules, for examples missing warming up, early stops". Test those two first and report what the evidence says, for or against. You have the hard part: the mechanisms.

Read first, in this order:

1. `AGENTS.md` (terminal answer rules, experiment rules).
2. [Your activity plan](../02_compare_clean_failures_and_passes/plan.md), including the coordinator's changes at the end.
3. [Earlier stage results](../01_trace_stage_stops_and_shape_bands/results.md) and [ablations](../../evaluate_our_method/02_run_ablations/results.md).
4. `docs/reference/inverse_information_chain.md` (use its A1–C12 terms) and `solvers/bem_inverse/README.md`.
5. The saved inventory: `results/bem/stage_scheduling/2026-11-19/clean_tg002/original_cases.csv` and `original_stages.csv`.

## How we work tonight

- Your sandbox has no GPU and no network. You write code, analyse on the CPU and write the notes. **The coordinator runs every GPU fit and makes every commit.** Never ask for approval; if something is blocked, say so in your reply and carry on with the rest.
- To get a fit run: give me the exact command and the output path in your reply. I review and run it, then tell you where the output is.
- A batch is already running (started 02:28 UTC): the real 0.25 GHz warm-up on the 13 remaining misses, then `longer_stage asymmetric__c13.3` and `longer_wall c_shape__c13.3`. Outputs land in `results/bem/stage_scheduling/2026-11-19/clean_tg002/{warmup,longer_stage,longer_wall}/`. Progress: `.../clean_tg002/logs/batch_01.state`. Do not start fits yourself, also not on the CPU, while it runs: the fits have a wall limit and need the machine quiet. Keep your own analysis to four threads.
- Do not edit `solvers/bem_inverse/`. If you think a solver change is needed, describe it to me with the reason; it must be general, not tuned to one dataset.
- Do not edit `experiments/comparison/compare_clean_schedules.py` while the batch runs (it records its own hash). Put new code in new files under `experiments/comparison/`.
- Files you own: `experiments/comparison/` new files, `results/bem/stage_scheduling/2026-11-19/` (not `logs/`), and in `docs/iterations/investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/`: `results.md`, `trial_refusals.md`, `figures/`. The other agent, `cylinder` (pane `w4:p3`), owns `docs/iterations/adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/` and `experiments/bem_on_baseline_data/`. Read its files freely, do not edit them.
- Keep committed data small: under 5 MB per run folder. Figures as PNG in the activity's `figures/` (the palette of `render_videos/atlas-mock` if you draw new ones).
- Separate measurement from reading. A budget-limited or single-case result is "not shown", not "ruled out". Name every case a claim rests on.

## Task 1: why does the slider refuse almost unchanged curves? (start here)

In the saved measured fit, `results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01/local/<stage>.json`, every refused trial I checked has reason `self_intersection`: 128 of 135 trials in `ladder_3_real`, all 40 in `ladder_4_real`, 177 of 190 in `full_1_M11`, all 40 in `full_2_M15`. Step sizes go down to 7e-9 m. A step that small cannot create a crossing. So either the accepted curve itself fails the intersection check, or the check misfires.

Find out which, with the solver's own check ([`checks.py`](../../../solvers/bem_inverse/checks.py), the slider in `solvers/bem_inverse/geometry_update_methods/`):

- Does the unchanged stage-entry curve of `ladder_4_real` (the exit of `ladder_3_real`) fail the slider's intersection check on the slider's own grid? On which sample pair, and how large is the loop or the overlap?
- Is the crossing real on a much finer grid, or an artefact of the sampling or a tolerance?
- Which accepted step first produced a curve that fails, and why did acceptance let it through (different grid, different check, or no check of the accepted state)?
- Then the denominator on TG-002: over the 30 clean fits, count stages that ended with every trial refused, by reason, for the 14 misses and the 16 passes. The per-stage `trials` are in `results/bem/default_clean_uc_fc/<case>/fit.json` if saved there; say so if they are not.

This is the "early stop" suspect at the level of mechanism: a fit that can no longer move, whatever its caps. Write it up in `trial_refusals.md` (short; method, counts, the one figure that shows the crossing). Send me the headline as soon as you have it, before the write-up.

## Task 2: are the misses "large and weak" fits?

Observation from the inventory: the misses end with an outline that is too large and a contrast that is too low (kite and Aphex Twin near 2 at true contrast 4; 0.0002 to 8.7 at true contrast 13.3; five weak starts clipped at 0.05). The measured cylinder ends the same way. At the lowest frequency the data fix little more than contrast times area, so a large weak object and a small strong one fit about equally.

- From `original_stages.csv` plus the saved curves: per case and stage, area over true area, contrast over true contrast, and their product. Do passes and misses separate, and at which stage? One figure.
- For the two circle cases (`circle__c4` passes, `circle__c13.3` misses) the unknowns are radius and contrast only. Map the loss of an exact circle over radius and contrast for the frequency set of each default stage, with the TG-002 acquisition, and draw the saved stage path and the weak start on it. Use an exact disk series already in the repo if there is one (the localization model and `experiments/bem_on_baseline_data/csi_cylinder_info.py` use one); otherwise the BEM forward on a circle. CPU only. This shows whether the 65 mm start with the weak estimate sits in the wrong valley, and which frequency set would break the tie.

## Task 3: the matched schedule tests

When I tell you the batch is done, score it against the saved fits as the plan says: per case, did the warm-up, the longer stage or the longer wall move the endpoint, and did it cross 5%? Check the unchanged prefix where there is one. Then write `results.md` for the activity: answer first, one table over all 14 misses, evidence links, limits. If Tasks 1 and 2 suggest one further matched test, propose it to me with command, budget and what it would settle.

## Replies

Short and plain, at most three lines per paragraph. Reply when Task 1 has a headline, when each task is written, or when you are blocked. I am watching your pane.
