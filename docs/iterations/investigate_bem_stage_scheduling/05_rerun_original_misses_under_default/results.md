# Under the default with warm-up, three of the four original misses recover

19 November 2026, fits 15:15 to 15:18 UTC. Coordinator: Claude, Herdr pane `w4:p1`. [Plan](plan.md) · follows [activity 04](../04_adopt_warmup_and_supply_contrast/results.md).

## Answer

**Yes, the 16/20 in row A of the final comparison report is before the warm-up.** It is the 17 November default. The default as it now stands, with the warm-up, recovers three of those four misses. That makes **19/20** on the clean cases at contrasts 0.5 and 4. `c_shape__c4` still misses.

## The four cases

Each went through the default policy unchanged: sealed clean real data, the centred 65 mm start, contrast estimated and fitted, `modal_muller`, `slider`, no localization. Area error is against the true outline; 5% or less is a recovery.

| Case | Before warm-up | Default with warm-up | How it ended | Fitted contrast (true) | Seconds |
|---|---:|---:|---|---:|---:|
| `cog__c0.5` | 17.1% | **0.300%** | completed, 11 stages | 0.500 (0.5) | 31 |
| `kite__c4` | 467% | **0.098%** | completed, 11 stages | 4.000 (4) | 23 |
| `aphex_twin__c4` | 197% | **0.223%** | completed, 14 stages | 4.000 (4) | 56 |
| `c_shape__c4` | 43.8% | 43.97% | numerical failure in the tenth stage (band 31) | 3.882 (4) | 65 |

- **Count.** 3/4 recover. With the 16 cases that already passed, 19/20.
- **Same as last night.** Each fit repeats last night's experiment-side warm-up fit of the same case exactly: same stage count, bands and accepted steps, and identical outlines (relative difference 0.0 in every stage). So last night's 30-case warm-up table is the new default's table: 20/30 clean (10, 9, 1).
- **The other 16 were not run again here.** All 16 passed last night with the same stage list, with errors from 0.000% to 0.64%. [Thirty-case scores](../03_compare_schedule_effects/results.md)
- **`kite__c4`** ran at 13:46 UTC as the check in activity 04 and was not repeated.

## The one miss left

`c_shape__c4` fails the same way with and without the warm-up: a numerical failure while band 31 is being fitted, with the outline 44% off. The warm-up does not touch it.

Last night a wider first stage did recover it (44.0% to 0.0046%), but the same change lost both low-contrast Aphex Twin fits. A band rule that serves both is point 4 of the [joint results](../03_compare_schedule_effects/results.md) and still waits for the user.

## Run conditions

- **GPU sharing.** The baseline coordinator's four GauGal fits were running when the launcher started. They were paused at 15:16:53 UTC, on the user's order, and resumed after the launcher ended.
  - `cog__c0.5` ran fully shared: 31 s against 10 s alone last night.
  - `c_shape__c4` ran partly shared: 65 s against 46 s.
  - `aphex_twin__c4` ran alone: 56 s, as last night.
- **No fit ended on the 120 s wall**, so sharing changed the seconds and nothing else. The work units match last night's (1523, 5116, 4221).
- All three exited normally. Launcher state: `logs/batch_12.state`.

## Limits

- Four fits, one start each, clean data only.
- The 19/20 joins three fits run now, one run this afternoon and 16 from last night. All 20 use the same stage list, but only four went through the solver's own default class.
- Row A of the final comparison report is not edited here; its caption says the 16/20 is the original schedule, and the text below it already gives 19/20.
- The saved table `results/bem/default_clean_uc_fc` is still the 17 November run without warm-up.

Evidence: [four default fits](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_recovered/) · [last night's warm-up fits](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/warmup/) · [driver](../../../../experiments/comparison/compare_clean_default_contrasts.py) · [launcher state](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/logs/batch_12.state)
