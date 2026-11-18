# Check early stage stops and shape bands

18 November 2026. Clean TG-002 real data at contrast 4, one centred start, recovered contrast. The [plan](plan.md) defines the changes and limits.

## What the four original fits did

All 16 early stage replays reproduced the saved boundary coefficients, loss and stop reason exactly. The table counts the change in data loss over the last five accepted iterations of each capped stage (iteration 17 to 22). A stage with no decreasing step had exhausted its allowed trial steps.

| Shape | End of stages 1 / 2 / 3 / 4 | Loss decrease at capped stages |
|---|---|---|
| Kite | Cap / cap / no decreasing step / no decreasing step | 0.102%, 0.060% |
| C-shape | No decreasing step / cap / cap / cap | Below 0.00001%, below 0.00001%, 0.0068% |
| Aphex Twin | Cap / no decreasing step / no decreasing step / cap | 0.026%, 2.97% |
| Cog | No decreasing step / no decreasing step / no decreasing step / cap | 0.0071% |

Across the original ten contrast-4 cases, seven of the twelve early stages on the three missed shapes hit the cap, compared with two of the twenty-eight stages on the seven recovered shapes. A cap records when a stage ended. The changed runs below test its effect. [Reference replays](../../../../results/bem/stage_stops/2026-11-18/reference/) · [Original fits](../../../../results/bem/default_clean_uc_fc/)

## What happened with more early iterations?

Raising the cap from 22 to 220 let all 16 early stages run until they found no decreasing step. Final area error was 486.69% for kite, 43.78% for C-shape, 196.91% for Aphex Twin and 2.01% for cog. The same three shapes missed. [Longer-stage fits](../../../../results/bem/stage_stops/2026-11-18/longer/)

Kite's first stage took 197 steps. Between steps 22 and 197, data loss fell another 2.00% while area error rose from 332.4% to 336.5%. For C-shape, running stage four from step 22 to 33 lowered loss by just 0.00010%. Cog's four extra steps changed its stage-four loss by about 0.000001%.

Aphex Twin was the one clear exception to the near-flat loss at the original cap. From step 17 to 22 in stage four its loss fell 2.97% and its area error fell from 198.50% to 196.85%. Extending all four stages changed the boundary entering stage four. That stage then stalled after nine steps at 196.91%. The comparison leaves open what extending only the original fourth stage would do.

## Can the stored curve describe the target?

Truncating the *true* curve to the first storage band (8) gives area errors of 0% for kite, 1.52% for C-shape, 7.68% for Aphex Twin and 9.80% for cog. At the second band (12) the corresponding errors are 0%, 0%, 2.79% and 1.11%. This checks each truth in its stored parameterisation. It does not determine which boundary the data will lead the fit to. Per-case records include all four storage bands.

On the default path, A1 stores the curve. The early storage bands increase from 8 to 12, 16 and 20. Each increase adds zero coefficients and preserves every old one, so those handoffs cannot repeatedly cut away detail. The first stage still restricts which shapes can be reached there. [Storage resize](../../../../solvers/bem_inverse/continuation/geometry.py#L44) · [Stage entry](../../../../solvers/bem_inverse/runner.py#L173)

## Later stages in the original fits

Kite entered the first 19-frequency stage and accepted zero steps. The forward solver rejected the curve because its wave-series roundoff estimate exceeded its numerical limit. Aphex Twin reached the same stage and accepted zero steps before its wall limit. Neither reached the later adaptive shape bands.

C-shape exhausted the 304-unit stage work allowance at update bands 25 and 31 after four and three accepted steps. It then hit the forward solver's numerical limit at band 37. Its area error was already 45.33% before the scheduled cleanup. Removing the stored harmonics above 64 changed that score by less than 0.00004 percentage points.

Cog crossed the 5% area threshold at band 15. Its measured frontier later supported a band of 94, but its whole-fit time ran out at band 49. The stage work quotas at bands 25, 31 and 37 advanced after four accepted steps each. Those stages reduced data loss by 63%, 48% and 52% from stage entry. The saved endpoints show that the refinement budgets mattered on a fit that had already recovered the shape. [Original C-shape stages](../../../../results/bem/default_clean_uc_fc/c_shape__c4/fit.json) · [Original cog stages](../../../../results/bem/default_clean_uc_fc/cog__c4/fit.json)

On this default path, B6 selects the shape changes available to the slider. C12 applies the stopping rules and advances the schedule on normal return or stage-quota exhaustion. The early update bands and the stored Cartesian bands are separate controls. [B6 slider](../../../../solvers/bem_inverse/geometry_update_methods/slider.py#L92) · [C12 stage return](../../../../solvers/bem_inverse/runner.py#L228) · [Real-only schedule](../../../../solvers/bem_inverse/real_only_policy.py#L91)
