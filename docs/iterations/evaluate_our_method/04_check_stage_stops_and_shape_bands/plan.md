# Check early stage stops and shape bands

18 November 2026. The user asked whether stages move on before the fit stalls and whether shape band limits compound the effect. Study the four clean contrast-4 fits discussed in the report: kite, C-shape, Aphex Twin and cog. Cog is the comparator that stopped early but passed the 5% area rule.

## Comparisons and limits

Use the saved real-only default as the reference. Count iteration limits, work quotas, loss/step stops and numerical failures separately. Check the saved damped run, the fixed-band-37 run and the other six contrast-4 default fits for context.

Replay the four default frequency-prefix stages for each case. Check recorded endpoints, stops and losses against the saved run. The code revision is newer, so report any difference before interpreting a replay. Capture accepted loss and geometry without file writes during the fit.

Change only the first four stages in three full-length comparisons:

| Comparison | Early iteration limit | Early normal-update bands |
|---|---:|---|
| Reference | 22 | 3, 5, 7, 9 |
| More iterations | 220 | 3, 5, 7, 9 |
| Wider shape updates | 22 | 5, 7, 9, 11 |
| Both | 220 | 5, 7, 9, 11 |

Keep the stored shape bands at 8, 12, 16 and 20, with the same physics resolution, frequency sequence, quotas, contrast start and later stages in every comparison. Use the default slider and real data, one centred start, no warm-up or localization. The two changed settings and their values are diagnostic choices. The user did not choose them.

Budget: four short prefix replays and twelve changed fits, one worker at a time on the GPU. Keep the original 13,412 work units and nominal 120 seconds per full fit. An early stage can still hit a quota or a normal stopping rule before 220. Keep all outcomes. No tuning, grid search or change to the default solver.

## What would answer the questions

- If a stage accepts more steps after 22, compare data loss and shape error at 22 with its own endpoint. Lower loss with a worse shape still counts as a failed recovery.
- Judge final recovery by area error at most 5%. Compare at common stage endpoints as well, since a longer early stage may leave less time for later work.
- Compare the wider-band fits with the same iteration budget, and check whether the iteration effect changes at the wider band. For A1 geometry storage, score each true curve after truncation to the four storage bands. This tests the stored representation in its original parameterisation.
- Stop once these contrasts answer the question for the four cases. Do not extrapolate to the ten contrast-13.3 cases.

## Commands and evidence

From the repo root run `PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.comparison.check_stage_stops ARM` for `reference`, `longer`, `wider` and `both` in order. The driver sets single-threaded BLAS. Each arm writes case records under `results/bem/stage_stops/2026-11-18/`. The baseline fits remain under `results/bem/default_clean_uc_fc/`. Interpret the results in this folder's `results.md` and the short comparison report.
