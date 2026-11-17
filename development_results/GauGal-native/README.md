# GauGal on its native cylinder scenes

The original GGB-001 comparison used cases 8, 13 and 14 at 0.4 GHz, 300 GauGal
iterations and an RTX 5090. These timings must stay separate from the
19-frequency TG-002 adaptation's approximately 340-second median.

| Case | Build (s) | Optimise (s) | Total excluding load (s) | Load (s) |
|---|---:|---:|---:|---:|
| 8 | 0.176 | 0.814 | 1.184 | 0.601 |
| 13 | 0.006 | 1.265 | 1.386 | 0.558 |
| 14 | 0.006 | 0.865 | 0.990 | 0.539 |

Source: [GGB-001 results](/home/drdeng/Gau-Gal/docs/iterations/GGB-001/results.md).
The original records remain in that workspace. These are single executions,
including first-use costs; the full reason for the timing gap was not established.
