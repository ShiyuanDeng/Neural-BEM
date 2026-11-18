# Trace stage stops and shape bands

18 November 2026. New investigation for the BEM coordinator. The user asked whether early stages advance while the fit is still improving, and whether shape-band limits compound the error. The requested team is the BEM coordinator with subagents in Herdr. The previous comparison is [finished and saved](../../coordinate_bem_side.md#wiggle-check-opened-18-november-1120-utc). Dispatched 18 November, 15:50 UTC; see [Dispatch](#dispatch).

## Starting evidence

Use the four clean TG-002 contrast-4 cases from the [short report](../../final_comparison_report.md). Kite, C-shape and Aphex Twin missed the 5% area target. Cog stopped early and passed. The runs used one centred start, real data, estimated contrast, no warm-up and no localization.

- **Stage stops.** Eight of 16 early stages hit the 22-step limit. Raising the cap to 220 let all 16 stall and recovered no additional shape. Extending only the most promising original stage moved Aphex Twin from 196.85% to 196.63% area error. [Matched runs](../../evaluate_our_method/04_check_stage_stops_and_shape_bands/results.md) · [Isolated replay](../../evaluate_our_method/05_extend_aphex_fourth_stage/results.md)
- **Shape bands.** Adding two early update modes at fixed storage reduced C-shape’s error from 43.78% to 0.07%. Kite stayed far from the target and did worse by stage three when given both wider updates and more steps. [Four settings and figure](../../evaluate_our_method/04_check_stage_stops_and_shape_bands/results.md)

## Coordinator handoff

1. Give one Herdr subagent the stage stops. Trace the first stage where each shape goes wrong. Distinguish the iteration cap, exhausted trial steps, work quota, time limit and forward-solver refusal. Compare data loss and area error at matched steps.
2. Give a second Herdr subagent the shape bands. Check which shape detail the early updates can move, what survives into the next stage and whether later bands can correct the outline. Use C-shape as the recovered example and kite as the interaction case.
3. Bring the findings together per shape. Identify which limit changed the recovery, where the evidence ends, and whether an unresolved cause needs a new run. Keep the short report brief and link the evidence.

Start with the [saved stage records](../../../../results/bem/stage_stops/2026-11-18/) and [original full fits](../../../../results/bem/default_clean_uc_fc/). This first evidence check needs zero new fits. If a cause remains open, record the smallest comparison, its commands, run budget and output paths before launching it. Save the findings in `results.md` beside this plan. Keep raw outputs in `results/` and report figures in `figures/`.

## Dispatch

The user, 18 November about 15:40 UTC, in the coordinator's pane `w2:p1`: "as investigator, you coordinate subagent work. go ahead."

| Agent | Part | Difficulty | Own files |
|---|---|---|---|
| `stage-stops` | Handoff item 1 | Hard part: telling the five stop causes apart in the code, not from labels | `stage_stops.md` here · `experiments/comparison/trace_stage_stops.py` · `results/bem/stage_scheduling/2026-11-18/stage_stops/` · `figures/stage_stops_*.png` |
| `shape-bands` | Handoff item 2 | Hard part: a sound measure of what an update band can move, and telling a band limit from an optimiser stall | `shape_bands.md` here · `experiments/comparison/trace_shape_bands.py` · `results/bem/stage_scheduling/2026-11-18/shape_bands/` · `figures/shape_bands_*.png` |

The coordinator writes `results.md` from both notes (handoff item 3).

Coordinator's choices; the user did not make them:

- Both are Codex agents on the configured astra model at high effort, in two panes split from `w2:p1`. Both parts are analysis with code reading, so neither is a monitoring task.
- Both run in Codex's workspace sandbox with approval prompts off. The check needs no fit, GPU, network or git. The coordinator commits each agent's paths. If a new run opens, the coordinator runs it or asks the user for full access.
- No fit, replay or solver edit by either agent. A proposed run comes to the coordinator as a written comparison first.

## Rules for both agents

- Read `AGENTS.md`, this plan, and the results of [activity 04](../../evaluate_our_method/04_check_stage_stops_and_shape_bands/results.md) and [activity 05](../../evaluate_our_method/05_extend_aphex_fourth_stage/results.md) first. Build on them; re-derive a number only to check it.
- Zero new fits and zero stage replays. Read saved records and code. Scoring a saved curve or projecting it onto a band is fine. If only a run can settle a cause, write the smallest comparison (commands, run budget, output paths, what each outcome would mean) in your note and carry on with the rest.
- Edit only your own files from the table. Nothing under `solvers/`. The other agent works beside you; do not touch its files.
- You are sandboxed with prompts off. Do not run `git add`, `commit` or `push`; the coordinator commits your paths. No network, no GPU.
- Python: `PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python`, one process, `OMP_NUM_THREADS=1`. Other fits share the CPU. Set `MPLCONFIGDIR` to a temporary folder if matplotlib asks.
- Raw outputs: small JSON or CSV, under 2 MB in total. Figures: PNG in `figures/`, style of `experiments/shape_continuation/render_videos.py` (surface `#fcfcfb`, ink `#0b0b0b`, muted `#52514e`, dashed muted truth, footnote naming the data and "no new solves").
- Name solver steps by their place in the A1–C12 chain of `docs/reference/inverse_information_chain.md`, link the code lines, and say whether each is on the default path.
- Your note: the answer first, per shape. Short sentences, plain words. Every number links to its record file. Say where the saved evidence ends.
- Decide open points yourself and write the decision in your note. Stop only if the work needs a run or a solver edit.
- Final message: at most 12 lines. One verdict per shape, the open causes, your file paths.

## Brief: stage stops

Question: do the stages advance while the fit is still improving, and in which stage does each shape first go wrong? Shapes: kite, C-shape, Aphex Twin, cog, contrast 4.

1. **Every stage of the original fit**, not only the first four. From `results/bem/default_clean_uc_fc/<shape>__c4/fit.json` (`stages`, `decisions`, `fit_work`, `physics`, `geometry_work`) list for each stage: bands, accepted steps, loss at entry and exit, area error at exit, work used against its quota, time used, refused or failed solves, and the stop.
2. **One cause per stop**, from exactly these: iteration cap, exhausted trial steps, stage work quota, whole-fit time limit, forward-solver refusal. Name anything else. Find where the code sets each (C12 stage return in `solvers/bem_inverse/runner.py`, the B6 slider, the work and time accounting) and check the counts against the label: steps against the cap, units against the quota, seconds against the limit, refused trials. Say when two limits were both close.
3. **First stage that goes wrong.** Track loss and area error at every stage entry and exit. Name the first stage whose exit is further from the truth than its entry while loss fell, and the first stage after which no later stage recovers. State your criterion. Compare against the seven recovered contrast-4 shapes in the same run folder for what a healthy stage looks like.
4. **Matched steps.** The records in `results/bem/stage_stops/2026-11-18/{reference,longer,wider,both,aphex_fourth}/` hold per-step loss and contrast (`accepted_iteration_loss_contrast`) and sampled area error (`sampled_area_error`). Compare loss and area error at the same step counts across settings. At the 22-step cap, was each stage still improving in loss, in shape, in both or in neither? Where a longer stage lowers loss and worsens shape, show the step where they part.
5. **Verdict per shape.** Which stop changed the recovery, which did not, where the evidence ends, and whether a run is needed.

Known from activities 04 and 05, to check and build on: eight of 16 early stages hit the cap and eight exhausted trial steps; 220 steps recovered no shape; kite's stage one took 197 steps for 2.00% less loss and a worse area error; Aphex Twin's fourth stage ran to step 47 for 0.22 points of area error; cog and C-shape ran out of stage work at bands 25 and 31; kite and C-shape met the forward solver's limit and Aphex Twin the time limit at later stages.

## Brief: shape bands

Question: do the shape-band limits compound the error? Two limits act in each early stage on the default path: A1 stores the curve (bands 8, 12, 16, 20; `solvers/bem_inverse/continuation/geometry.py#L44`) and B6 sets the normal directions the slider may try (bands 3, 5, 7, 9; `solvers/bem_inverse/geometry_update_methods/slider.py#L92`). C-shape is the recovered example (43.78% to 0.07% with update bands 5, 7, 9, 11). Kite is the interaction case (278.87% with wider updates, 493.76% with wider updates and more steps).

1. **What the early updates can move.** Read how B6 builds its directions. For each early stage, split the gap between the entry curve and the truth into the part the stage's update band can reach and the part it cannot. Compare with what the stage did move, entry to exit. Define the measure in one paragraph and say what it cannot show (the truth's parameterisation is one of many). Do it for C-shape and kite in full, Aphex Twin and cog in brief, for the original and the wider setting.
2. **What survives a handoff.** On the saved curves, check that the A1 resize only adds zeros. Then follow the content: which harmonics set in stage k are unchanged at the end of each later stage and in the final curve? Does an early wrong feature, such as C-shape's filled opening, persist to the end?
3. **Whether later bands correct the outline.** From stage five on, the bands are wide enough to express the fix. For the original C-shape and kite fits, show per stage whether the curve moved towards the truth: loss, area error, which harmonics changed. Separate "the band could not express the fix" from "the band could, and the stage stopped first". Report the saved stop label for the second kind; `stage-stops` classifies it.
4. **Kite's interaction.** Find the stage and step where the wider-and-longer fit leaves the wider-only fit, and what changed there: which harmonics, the contrast estimate, self-crossing, refused solves. Say whether it is a band effect, a step-count effect or something else, and where the evidence ends.
5. **Verdict per shape.** Which band limit changed the recovery, which did not, where the evidence ends, and whether a run is needed.

Known from activity 04, to check and build on: the true curves cropped to band 8 score 0%, 1.52%, 7.68% and 9.80% area error (kite, C-shape, Aphex Twin, cog) and are below 3% by band 12; C-shape reached 4.44% in stage three with wider updates against 56.66%; with wider updates C-shape, cog and Aphex Twin stalled before step 22 in every early stage. Truth and scoring: `experiments/comparison/scoring.py` (`truth_for`), driver `experiments/comparison/check_stage_stops.py`.
