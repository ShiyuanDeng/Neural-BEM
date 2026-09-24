| Case | Arm | Status | RMS, mm | Hausdorff, mm | Stage-1 loss | Units | Stage-1 end radius, mm | Min radius, mm | Refit / self-int. refusals |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| wrong_circle | R0 | COMPLETED_SCHEDULE | 0.3378 | 0.9159 | 1.33e-06 | 18 | 35.79 | 35.72 | 0 / 0 |
| wrong_circle | R1 | COMPLETED_SCHEDULE | 0.08787 | 0.1407 | 1.34e-07 | 69 | 46.46 | 46.16 | 0 / 0 |
| wrong_circle | R2 | COMPLETED_SCHEDULE | 0.08761 | 0.1413 | 1.52e-07 | 66 | 46.82 | 46.21 | 0 / 0 |
| circle_to_star | R0 | COMPLETED_SCHEDULE | 7.749 | 12.9 | 0.0026 | 30 | 38.10 | 37.71 | 0 / 0 |
| circle_to_star | R1 | COMPLETED_SCHEDULE | 7.689 | 12.68 | 0.0026 | 49 | 44.90 | 44.52 | 0 / 0 |
| circle_to_star | R2 | COMPLETED_SCHEDULE | 7.687 | 12.68 | 0.0026 | 49 | 45.24 | 44.85 | 0 / 0 |
| circle_to_c | R0 | COMPLETED_SCHEDULE | 8.957 | 26.8 | 0.0592 | 60 | 2.14 | 2.14 | 127 / 0 |
| circle_to_c | R1 | COMPLETED_SCHEDULE | 9.559 | 30.93 | 0.0901 | 69 | 1.87 | 1.87 | 144 / 0 |
| circle_to_c | R2 | COMPLETED_SCHEDULE | 8.403 | 19.77 | 0.0213 | 69 | 2.09 | 2.09 | 94 / 0 |
| kite | R0 | COMPLETED_SCHEDULE | 5.052 | 12.52 | 0.0105 | 42 | 2.18 | 2.18 | 90 / 0 |
| kite | R1 | COMPLETED_SCHEDULE | 6.01 | 11.23 | 0.0193 | 69 | 1.40 | 1.40 | 78 / 0 |
| kite | R2 | COMPLETED_SCHEDULE | 2.513 | 7.75 | 1.44e-05 | 69 | 1.51 | 1.51 | 9 / 0 |
| peanut | R0 | COMPLETED_SCHEDULE | 4.8 | 17.63 | 0.0116 | 33 | 1.94 | 1.94 | 50 / 30 |
| peanut | R1 | COMPLETED_SCHEDULE | 3.608 | 11.25 | 0.00488 | 69 | 2.23 | 2.23 | 67 / 0 |
| peanut | R2 | COMPLETED_SCHEDULE | 3.064 | 9.16 | 0.00104 | 69 | 2.24 | 2.24 | 56 / 0 |
| hook | R0 | COMPLETED_SCHEDULE | 9.941 | 22.12 | 0.0117 | 24 | 7.88 | 7.88 | 0 / 0 |
| hook | R1 | COMPLETED_SCHEDULE | 9.881 | 21.5 | 0.0116 | 50 | 8.09 | 7.38 | 0 / 0 |
| hook | R2 | COMPLETED_SCHEDULE | 9.826 | 21.19 | 0.0116 | 50 | 8.32 | 7.36 | 0 / 0 |

| Ratio (0.01-mm floor) | Geometric mean | Worst | Per case |
|---|---:|---:|---|
| R2/R0 | 0.650 | 0.992 | wrong_circle 0.259, circle_to_star 0.992, circle_to_c 0.938, kite 0.497, peanut 0.638, hook 0.988 |
| R1/R0 | 0.791 | 1.190 | wrong_circle 0.26, circle_to_star 0.992, circle_to_c 1.07, kite 1.19, peanut 0.752, hook 0.994 |
| R2/R1 | 0.822 | 1.000 | wrong_circle 0.997, circle_to_star 1, circle_to_c 0.879, kite 0.418, peanut 0.849, hook 0.994 |

Added hard stops: {'R1': [], 'R2': []}
Decision record: {'stage_a_only': True, 'gate_released': False, 'comparison': 'stage-1 endpoints (R0 truncated, geometry-only score)'}
