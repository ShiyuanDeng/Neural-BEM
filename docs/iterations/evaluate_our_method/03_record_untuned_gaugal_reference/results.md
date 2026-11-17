# Untuned GauGal reference — recorded on 17 November 2026

GauGal recovered **0/20** cases on the new 1% noisy run. The 30 imported clean
fits also recovered **0/30** under the new all-component area criterion.
These are untuned reference results, not a fair comparison with external baselines.

The [plan](plan.md) records the reused settings and limitations.
This summary reads [raw metrics](../../../../results/metrics.csv) without fitting or rescoring.

## Recovery

| Data and origin | Contrasts 0.5 and 4 | Contrast 13.3 | All cases | Old count |
|---|---:|---:|---:|---:|
| [Clean fits from 2 November, imported on 17 November](../../../../results/gaugal/default_clean_uc_fs/run.json) | 0/20 | 0/10 | 0/30 | 0/30 |
| [New 1% noise draw 0](../../../../results/gaugal/default_n1d0_uc_fs/run.json) | 0/20 | Not run | 0/20 | 0/20 |

All 20 new noisy fits and all 30 imported records have a `COMPLETED` outcome.
Normal optimizer completion does not imply geometric recovery; none meets area
error ≤5%. Raw area, material and boundary scores remain in the case score files.

The matched default BEM noisy draw recovers 16/20 on the common contrasts.
GauGal reused older settings with no new tuning, and BEM was told the noise level
for discrepancy stopping. These differences preclude a general method ranking.

## Timing and scope

The import ran at 13:32–13:33 UTC; it rescored existing clean reconstructions.
The new noisy command ran at 13:33–15:32 UTC, taking 7,144 s including overhead.
Its median optimization time was 328.1 s per case; setup is separate.

On the earlier native single-frequency cylinder cases, GauGal optimization took
0.814, 1.265 and 0.865 s. The much longer TG-002 times use different data and
settings; their full cause has not been established. See the
[preserved native timing record](../../../../../Neural_SDF_BEM_AD/development_results/GauGal-native/README.md).

The [execution record](../../../../results/_execution/ggb003/continuation/19_gaugal_n1d0.attempt1.json)
and [completion record](../../../../results/_execution/ggb003/continuation/session.json)
record the finish. Other external baseline comparisons were outside this Stage 1
study and have not been added to these results.
