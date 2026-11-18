# Extending Aphex Twin's original fourth stage

**The 22-step cap stopped a moving fit, but the remaining improvement was small.** On 18 November 2026 the same stage accepted 47 steps and then found no further step that lowered loss. The extra 25 steps reduced data loss by 0.20% and moved area error from 196.85% to 196.63%. The best outline was the last one. Recovery requires 5% or less. [Saved steps and curves](../../../../results/bem/stage_stops/2026-11-18/aphex_fourth/aphex_twin__c4.json)

| Point in the stage | Accepted steps | Data loss | Area error | Estimated contrast |
|---|---:|---:|---:|---:|
| Stage entry | 0 | 0.433904 | 256.15% | 1.9235 |
| Original cutoff | 22 | 0.279368 | 196.85% | 2.0673 |
| Last step recorded within the original time remaining | 34 | 0.278811 | 196.63% | 2.0698 |
| Natural stop | 47 | 0.278799 | 196.63% | 2.0698 |

The original whole fit had 81.7 seconds left at stage entry. The replay reached step 34 at 80.8 seconds and stalled at 98.6 seconds. These timings depend on load. The first 22 step losses and contrast values, and the boundary at step 22, matched the original reference exactly.

The replay used the saved stage-three boundary and estimated contrast from the original centred fit. It kept the same four real frequencies, normal-update band 9, curve storage band 20 and stage work quota. It ended at stage four, with a diagnostic allowance of 240 seconds. [Plan](plan.md) · [Full-fit comparisons and limitations](../04_check_stage_stops_and_shape_bands/results.md)
