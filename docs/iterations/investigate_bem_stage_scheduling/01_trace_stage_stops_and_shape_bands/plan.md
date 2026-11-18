# Trace stage stops and shape bands

18 November 2026. New investigation for the BEM coordinator. The user asked whether early stages advance while the fit is still improving, and whether shape-band limits compound the error. The requested team is the BEM coordinator with subagents in Herdr. The previous comparison is [finished and saved](../../coordinate_bem_side.md#wiggle-check-opened-18-november-1120-utc). This brief is ready for dispatch.

## Starting evidence

Use the four clean TG-002 contrast-4 cases from the [short report](../../final_comparison_report.md). Kite, C-shape and Aphex Twin missed the 5% area target. Cog stopped early and passed. The runs used one centred start, real data, estimated contrast, no warm-up and no localization.

- **Stage stops.** Eight of 16 early stages hit the 22-step limit. Raising the cap to 220 let all 16 stall and recovered no additional shape. Extending only the most promising original stage moved Aphex Twin from 196.85% to 196.63% area error. [Matched runs](../../evaluate_our_method/04_check_stage_stops_and_shape_bands/results.md) · [Isolated replay](../../evaluate_our_method/05_extend_aphex_fourth_stage/results.md)
- **Shape bands.** Adding two early update modes at fixed storage reduced C-shape’s error from 43.78% to 0.07%. Kite stayed far from the target and did worse by stage three when given both wider updates and more steps. [Four settings and figure](../../evaluate_our_method/04_check_stage_stops_and_shape_bands/results.md)

## Coordinator handoff

1. Give one Herdr subagent the stage stops. Trace the first stage where each shape goes wrong. Distinguish the iteration cap, exhausted trial steps, work quota, time limit and forward-solver refusal. Compare data loss and area error at matched steps.
2. Give a second Herdr subagent the shape bands. Check which shape detail the early updates can move, what survives into the next stage and whether later bands can correct the outline. Use C-shape as the recovered example and kite as the interaction case.
3. Bring the findings together per shape. Identify which limit changed the recovery, where the evidence ends, and whether an unresolved cause needs a new run. Keep the short report brief and link the evidence.

Start with the [saved stage records](../../../../results/bem/stage_stops/2026-11-18/) and [original full fits](../../../../results/bem/default_clean_uc_fc/). This first evidence check needs zero new fits. If a cause remains open, record the smallest comparison, its commands, run budget and output paths before launching it. Save the findings in `results.md` beside this plan. Keep raw outputs in `results/` and report figures in `figures/`.
