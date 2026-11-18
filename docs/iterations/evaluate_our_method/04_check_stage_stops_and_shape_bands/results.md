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

## Can the stored curve describe the target?

Truncating the *true* curve to the first storage band (8) gives area errors of 0% for kite, 1.52% for C-shape, 7.68% for Aphex Twin and 9.80% for cog. At the second band (12) the corresponding errors are 0%, 0%, 2.79% and 1.11%. This checks each truth in its stored parameterisation. It does not determine which boundary the data will lead the fit to. Per-case records include all four storage bands.

The original final recovery count on these four was 1/4. Cog passed the 5% area rule. The other three missed. The prefix replay ends deliberately after stage four and does not supply final recovery scores.
