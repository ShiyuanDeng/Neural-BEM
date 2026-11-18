# MF-CC-CSI simulated TG-002 campaign

Updated 2026-11-18T02:00:15.045739+00:00. State: **batch 1 awaiting coordinator: first-batch forecast exceeds nine hours**.

Nine-hour budget. Ten shapes, contrast 4, 2048 iterations, native back-propagation start.
Grid 166-by-166 at 1.25 mm; native forward 332-by-332 at 0.625 mm. No settings shortened.

Snapshot scores use unchanged protocol-1 image helpers. Area error is symmetric difference over true area.
Contrast error is relative error of mean epsilon_r in the half-peak support against 4.

| Case | Iterations | Area error % | Support mm2 | Mean epsilon_r | Contrast error % | Centre error mm | Native elapsed s |
|---|---:|---:|---:|---:|---:|---:|---:|
| circle | 256 | 12.873 | 8865.023 | 3.1495 | 21.2624 | 1.6662 | 1105.367 |
| circle | 512 | 14.166 | 8966.601 | 3.2849 | 17.8775 | 1.6227 | 2146.683 |
| circle | 1024 | 14.416 | 8986.187 | 3.3705 | 15.7363 | 1.4436 | 4461.090 |
| circle | 2048 | 13.672 | 8927.802 | 3.4313 | 14.2166 | 1.1795 | 9711.300 |

circle: completed.

| kite | 256 | 45.377 | 4281.718 | 2.7483 | 31.2917 | 0.6248 | 1099.235 |
| kite | 512 | 32.699 | 3908.320 | 2.9276 | 26.8096 | 0.6779 | 2136.472 |
| kite | 1024 | 21.053 | 3554.893 | 3.1047 | 22.3830 | 0.8452 | 4427.208 |
| kite | 2048 | 16.110 | 3362.681 | 3.2541 | 18.6485 | 0.8035 | 9682.229 |

kite: completed.

| peanut | 256 | 29.868 | 6194.288 | 2.8768 | 28.0806 | 2.7615 | 1099.544 |
| peanut | 512 | 28.004 | 6107.449 | 2.9988 | 25.0306 | 2.5434 | 2137.732 |
| peanut | 1024 | 25.298 | 5978.320 | 3.1070 | 22.3249 | 2.2695 | 4447.877 |
| peanut | 2048 | 21.130 | 5779.458 | 3.2095 | 19.7633 | 1.9057 | 9700.709 |

peanut: completed.


The measured-cylinder nominal registration is not used for these simulated truths.
For that measured case, registered area error, support size and centre offset remain separate; its nominal position is only about 30 mm.

Raw data, full histories and native logs stay local and ignored. Per-case manifests give SHA-256.
Raw checkpoint arrays, compressed logs, costs, timing/resources and all sensitivity scores are committed.

The output-only owned copy differs by a function rename and one snapshot callback (patch 0003).
The upstream numerical function, objective, projection, line search and settings are unchanged.
Native timers include the small snapshot writes; checkpoint_writes.csv records that I/O separately.

The BEM side must check the exact hashed simulated data on each true boundary later.
Timings overlap other MATLAB work and are not isolated final-comparison timings.

## First-batch time check

```json
{
  "utc": "2026-11-18T02:00:15.045505+00:00",
  "observed_seconds_per_iteration": [
    4.74184578125,
    4.727650699707032,
    4.736674220703125
  ],
  "conservative_rate": 4.74184578125,
  "elapsed_seconds": 9801.41659526527,
  "remaining_forecast_seconds": 29472.29821983166,
  "total_forecast_hours": 10.909365226415813,
  "budget_hours": 9,
  "method": "elapsed + three remaining batches at slowest completed first-batch wall + seven forward generations at 43 s",
  "exceeds_budget": true
}
```
