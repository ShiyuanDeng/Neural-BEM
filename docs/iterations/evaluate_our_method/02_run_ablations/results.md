# Ablations — run on 17 November 2026

All 200 ablation fits have saved scores. The damped-data arm with the old warm-up
recovered **19/20**, compared with **16/20** for the clean real-only control.
Fixed-band and simultaneous-frequency variants recovered **0/20** each.

This report uses [raw metrics](../../../../results/metrics.csv) and the unchanged 5% area criterion in the
[plan](plan.md). All rows below use the same 20 cases, excluding
contrast 13.3. Control rows reuse the clean/noisy activity's fits.

## Recovery and recorded fit times

| Configuration | Contrast 0.5 | Contrast 4 | Area success | Old count | Median fit s |
|---|---:|---:|---:|---:|---:|
| [Default control, clean](../../../../results/bem/default_clean_uc_fc/run.json) | 9/10 | 7/10 | 16/20 | 15/20 | 12.7 |
| [Contrast supplied](../../../../results/bem/default_clean_kc_fc/run.json) | 9/10 | 2/10 | 11/20 | 11/20 | 15.2 |
| [Damped data + old warm-up](../../../../results/bem/default_cleandamped_uc_fc/run.json) | 9/10 | 10/10 | 19/20 | 19/20 | 14.2 |
| [Nodal, clean](../../../../results/bem/nodal_clean_uc_fc/run.json) | 10/10 | 7/10 | 17/20 | 16/20 | 34.7 |
| [Default control, 1% draw 0](../../../../results/bem/default_n1d0_uc_fc/run.json) | 9/10 | 7/10 | 16/20 | 16/20 | 5.5 |
| [Nodal, 1% draw 0](../../../../results/bem/nodal_n1d0_uc_fc/run.json) | 9/10 | 7/10 | 16/20 | 16/20 | 14.6 |
| [Fixed band 37](../../../../results/bem/fixedband37_clean_uc_fc/run.json) | 0/10 | 0/10 | 0/20 | 0/20 | 112.9 |
| [All frequencies from the start](../../../../results/bem/default_clean_uc_fs/run.json) | 0/10 | 0/10 | 0/20 | 0/20 | 34.4 |
| [Only 0.5 GHz](../../../../results/bem/default_clean_uc_sf0.5/run.json) | 2/10 | 0/10 | 2/20 | 1/20 | 31.8 |
| [Only 1 GHz](../../../../results/bem/default_clean_uc_sf1/run.json) | 0/10 | 0/10 | 0/20 | 0/20 | 130.2 |
| [Only 1.5 GHz](../../../../results/bem/default_clean_uc_sf1.5/run.json) | 0/10 | 0/10 | 0/20 | 0/20 | 132.2 |
| [Only 2 GHz](../../../../results/bem/default_clean_uc_sf2/run.json) | 0/10 | 0/10 | 0/20 | 0/20 | 67.3 |

The medians include unsuccessful fits. They describe recorded fit time, not the
cost of reaching an equivalent solution. The 120 s setting is a nominal limit:
saved fit times can exceed it. Do not interpret it as a hard per-process cutoff.

## What the comparisons establish

- Adding damped observations together with the old warm-up increases recovery
  on this case set. These runs cannot separate those two changes. The only
  failed case in that arm is `hook__c0.5`, stopped at the trial wall limit.
- Supplying contrast recovered 11/20 versus the recovered-contrast control's
  16/20. This is the observed result under these schedules, not an explanation
  of the mechanism behind the difference.
- Nodal recovers one more clean case, but clean data were generated with the
  same solver family. Both backends recover 16/20 on noisy draw 0.
- The tested fixed-band and simultaneous-frequency choices recover none of
  the 20 cases. Single-frequency recovery is 2/20 at 0.5 GHz and 0/20 at each
  of 1, 1.5 and 2 GHz. These results apply to the recorded bands and budgets.

## Stops and completion

Fixed-band fits record 13 numerical failures and 7 trial wall limits;
simultaneous-frequency fits record 17 and 3 respectively. The 1 GHz and 1.5 GHz
runs are dominated by trial wall limits (18/20 and 17/20). Those stop reasons
limit what can be concluded about alternative schedules with different budgets.

Ablations began at 07:48 UTC. The original six-hour total stopped the 1 GHz batch
at 10:50 with 11 saved cases. Under the user's continuation request it resumed
at 11:38, then the 1.5 and 2 GHz runs followed. All ablations finished by 13:32.
The saved partial attempt remains in the execution history.

See the [initial stop record](../../../../results/_execution/ggb003/execution_final.json)
and [continuation record](../../../../results/_execution/ggb003/continuation/session.json).
Per-case errors and stops are in each run's `score.json` and `fit.json`.
No fit or score was regenerated for this report.
