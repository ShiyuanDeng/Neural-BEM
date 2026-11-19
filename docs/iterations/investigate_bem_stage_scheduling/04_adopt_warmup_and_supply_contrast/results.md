# The warm-up is the default; supplying the contrast does not rescue 13.3

19 November 2026, 13:46 to 14:07 UTC. Coordinator: Claude, Herdr pane `w4:p1`. [Plan](plan.md) · follows the [joint results](../03_compare_schedule_effects/results.md).

## Answer

**The default now has the warm-up.** The user: "yes default with warm up". The solver's real-only schedule runs one band-1 stage on the lowest frequency before the ladder, and it repeats last night's warm-up fits exactly.

**Supplying the true contrast does not rescue the contrast-13.3 cases.** One of ten recovers, the circle, the same as with recovered contrast. Seven of the other nine get worse. So contrast recovery is not what fails at 13.3. With the contrast held, the warm-up finds the right place and size only for the circle and the star; a ten times longer warm-up changes nothing.

## Part 1: the default

- **Change.** [`RealOnlyPolicy`](../../../../solvers/bem_inverse/real_only_policy.py) has `warmup=True` by default. In the `continuation` schedule one stage runs first: the lowest real frequency alone, update band 1, storage band 4, 600 work units, 44 steps. `warmup=False` is the 17 November schedule. Commit `08200b1ab`.
- **Place in the chain.** One more stage in the list that C12 walks through. A1 to C11 are unchanged.
- **Check 1.** `pytest pytest/bem_inverse/test_real_only.py`: five tests pass. The default's stage list is the old one with the warm-up in front, and `warmup=False` gives the old one record for record.
- **Check 2.** `kite__c4` and `circle__c13.3` through the default policy: 11 stages each, the same bands and accepted steps in every stage, and outlines identical to the saved warm-up fits (relative difference 0.0 in every stage). Area error 0.098% and 0.000%. [Check fits](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_recovered/)
- **Also changed.** `AGENTS.md` names the warm-up in the default method. The solver README says the same.

Three choices here are the coordinator's and the user may want them different:

- `CsiPolicy` and `B1Policy`, the wrappers for other groups' data, keep `warmup=False`, as in all their saved fits. On the measured cylinder a warm-up on the lowest frequency alone gave 95% against 68%.
- The `simultaneous` and `single` frequency schedules get no warm-up. Neither was tested with one.
- The saved tables under `results/bem/default_*` are from the default without warm-up and were not run again. For the new default the evidence is last night's warm-up fits: 20/30 clean, 20/30 on noise draw 0.

## Part 2: contrast supplied at 13.3

Ten fits, 13:47 to 14:03 UTC, one at a time on the GPU, all exited normally. Each is the new default with one change: the contrast is set to 13.3 and not fitted. Reference: last night's warm-up fits with recovered contrast. Area error is against the true outline; 5% or less is a recovery. [Scores](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_known/comparison.csv)

| Case | Recovered contrast | Contrast supplied | How the supplied fit ended | Warm-up exit: loss | radius mm (true) | centre error mm |
|---|---:|---:|---|---:|---:|---:|
| `circle__c13.3` | 0.00% | **0.00%** | completed | 0.0000 | 50.0 (50.0) | 0.0 |
| `star__c13.3` | 80.2% | 35.8% | wall | 0.0000 | 50.4 (50.8) | 0.0 |
| `kite__c13.3` | 316% | 433% | completed | 0.446 | 77.2 (30.6) | 9.1 |
| `aphex_twin__c13.3` | 107% | 680% | numerical failure | 0.287 | 75.5 (27.3) | 6.6 |
| `c_shape__c13.3` | 115% | 221% | wall | 0.394 | 51.8 (45.7) | 89 |
| `hook__c13.3` | 579% | 312% | completed | 1.007 | 57.6 (39.0) | 132 |
| `peanut__c13.3` | 150% | 317% | completed | 0.746 | 55.4 (39.0) | 136 |
| `cog__c13.3` | 74.5% | 244% | wall | 0.735 | 56.3 (46.5) | 144 |
| `cross__c13.3` | 154% | 235% | wall | 0.748 | 51.6 (42.2) | 147 |
| `asymmetric__c13.3` | 186% | 224% | numerical failure | 0.667 | 59.6 (46.6) | 147 |

Radius is the equal-area radius. For scale: an empty scene has loss 0.5 on this measure, whatever the outline.

- **Count.** 1/10 with the contrast supplied, 1/10 with recovered contrast. Star and hook improve and still miss; seven get worse.
- **The warm-up now has three unknowns** (two shifts and the radius). It finds the right disk in four or five steps for the circle and the star, the two largest targets. For the star that disk is 31% off in area, and the shape stages end at 36%.
- **For the other eight it does not find the disk.** Six end with the disk 89 to 147 mm from the true centre, five of them at a loss worse than an empty scene. Kite and Aphex Twin stay within 10 mm of the centre but 2.5 and 2.8 times too large in radius.
- **The start is worse than an empty scene in all ten.** The 65 mm disk at contrast 13.3 starts at loss 0.54 to 1.91. With recovered contrast the fit starts weak instead (the weak estimate), which is why the two rows differ.

### Was the warm-up stopped early?

Six of the misses ended the warm-up on its 44-step cap. For those six the warm-up stage alone was run again with a 440-step cap and ten times the work quota, 14:04 to 14:05 UTC. [Scores](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_known_warmup_long/comparison.csv)

| Case | Loss at 44 steps | Loss with a 440-step cap | Steps taken | Why it stopped |
|---|---:|---:|---:|---|
| `kite__c13.3` | 0.44581 | 0.44581 | 47 | no decreasing step |
| `peanut__c13.3` | 0.74613 | 0.74613 | 49 | no decreasing step |
| `hook__c13.3` | 1.00672 | 1.00670 | 99 | no decreasing step |
| `asymmetric__c13.3` | 0.66727 | 0.66699 | 165 | no decreasing step |
| `cross__c13.3` | 0.74845 | 0.74844 | 440 | cap |
| `cog__c13.3` | 0.73518 | 0.73490 | 440 | cap |

**No.** The loss changes by at most 0.0003, the radius does not change, and the centre error stays within 0.1 mm of the 44-step value. Four stages stop by themselves. Cross and cog use all 440 steps to slide the disk sideways, by 2 and 13 mm, at the same loss.

## What this means

- **At 13.3 the obstacle is the path from the one centred start, not the contrast estimate.** Give the fit the true contrast and it still leaves the target in eight of ten cases, at the first stage, before any shape detail is released.
- **It is not an early stop.** Ten times the warm-up steps end at the same place.
- **Coordinator's reading, not tested:** the centred 65 mm disk is 1.6 to 5.7 times the target's area. At full contrast it scatters far more than the target, and with the contrast held it cannot weaken. The first moves that lower the loss carry it away from the target or leave it oversized, and it stops in a local minimum.
- **The same shows at contrast 4 in saved runs.** The 17 November default recovered 7/10 with recovered contrast and 2/10 with the contrast supplied (`bem/default_clean_kc_fc`). Those fits had no warm-up.

This leaves point 3 of the joint results where it was: the two remedies that helped at 13.3 both try more than one start.

## Limits

- Ten fits from one start; each row is a single run.
- The reading above is from stage records. Why the disk moves away, and whether the domain check refused its last trials, was not looked at.
- Supplied contrast under the new default was run at 13.3 only. The 0.5 and 4 numbers quoted are from the default without warm-up.
- The longer warm-up is a one-stage diagnostic and gives no recovery count.
- Four of the ten fits ended on the 120 s wall, far from recovery (36% to 244%).

Evidence: [supplied-contrast fits](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_known/) · [longer warm-up stages](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/default_known_warmup_long/) · [driver](../../../../experiments/comparison/compare_clean_default_contrasts.py) · [scorer](../../../../experiments/comparison/score_clean_default_contrasts.py) · [launcher state](../../../../results/bem/stage_scheduling/2026-11-19/clean_tg002/logs/batch_10.state)
