| Case | Arm | Status | RMS, mm | Hausdorff, mm | Stage-1 loss | Final loss (stage) | Units | Stage-1 end radius, mm | Min radius, mm | Refit / self-int. refusals |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wrong_circle | R0 | COMPLETED_SCHEDULE | 0.002594 | 0.005072 | 1.33e-06 | 1.55e-11 (4) | 87 | 35.79 | 35.72 | 0 / 0 |
| wrong_circle | R1 | COMPLETED_SCHEDULE | 0.002103 | 0.004435 | 1.34e-07 | 2.1e-11 (4) | 342 | 46.46 | 46.16 | 0 / 0 |
| wrong_circle | R2 | COMPLETED_SCHEDULE | 0.001833 | 0.003857 | 1.52e-07 | 1.6e-11 (4) | 351 | 46.82 | 46.21 | 0 / 0 |
| circle_to_star | R0 | COMPLETED_SCHEDULE | 0.5222 | 1.425 | 0.0026 | 4.26e-06 (4) | 139 | 38.10 | 11.44 | 0 / 0 |
| circle_to_star | R1 | COMPLETED_SCHEDULE | 0.5154 | 1.486 | 0.0026 | 7.05e-06 (4) | 211 | 44.90 | 13.34 | 0 / 0 |
| circle_to_star | R2 | COMPLETED_SCHEDULE | 0.5172 | 1.494 | 0.0026 | 7.24e-06 (4) | 211 | 45.24 | 13.33 | 0 / 0 |
| circle_to_c | R0 | COMPLETED_SCHEDULE | 3.202 | 11.79 | 0.0592 | 0.0213 (4) | 651 | 2.14 | 1.75 | 625 / 12 |
| circle_to_c | R1 | COMPLETED_SCHEDULE | 2.893 | 11.1 | 0.0901 | 0.0209 (4) | 690 | 1.87 | 1.68 | 710 / 0 |
| circle_to_c | R2 | COMPLETED_SCHEDULE | 2.745 | 11.84 | 0.0213 | 0.0151 (4) | 690 | 2.09 | 1.81 | 378 / 0 |
| kite | R0 | COMPLETED_SCHEDULE | 2.983 | 9.58 | 0.0105 | 0.0132 (4) | 411 | 2.18 | 1.11 | 503 / 42 |
| kite | R1 | COMPLETED_SCHEDULE | 5.344 | 9.52 | 0.0193 | 0.0814 (4) | 690 | 1.40 | 1.16 | 570 / 0 |
| kite | R2 | COMPLETED_SCHEDULE | 1.554 | 6.769 | 1.44e-05 | 0.000184 (4) | 690 | 1.51 | 1.02 | 258 / 0 |
| peanut | R0 | COMPLETED_SCHEDULE | 2.944 | 16.99 | 0.0116 | 0.011 (4) | 528 | 1.94 | 1.27 | 531 / 78 |
| peanut | R1 | COMPLETED_SCHEDULE | 3.315 | 10.4 | 0.00488 | 0.0317 (4) | 690 | 2.23 | 1.88 | 781 / 0 |
| peanut | R2 | COMPLETED_SCHEDULE | 2.385 | 8.27 | 0.00104 | 0.0165 (4) | 690 | 2.24 | 1.85 | 427 / 0 |
| hook | R0 | COMPLETED_SCHEDULE | 0.5254 | 1.506 | 0.0117 | 5.98e-06 (4) | 195 | 7.88 | 7.88 | 2 / 0 |
| hook | R1 | COMPLETED_SCHEDULE | 0.525 | 2.019 | 0.0116 | 6.64e-06 (4) | 308 | 8.09 | 6.94 | 0 / 0 |
| hook | R2 | COMPLETED_SCHEDULE | 0.4864 | 1.86 | 0.0116 | 6.37e-06 (4) | 296 | 8.32 | 6.81 | 0 / 0 |

| Ratio (0.01-mm floor) | Geometric mean | Worst | Per case |
|---|---:|---:|---|
| R2/R0 | 0.832 | 1.000 | wrong_circle 1, circle_to_star 0.99, circle_to_c 0.857, kite 0.521, peanut 0.81, hook 0.926 |
| R1/R0 | 1.103 | 1.792 | wrong_circle 1, circle_to_star 0.987, circle_to_c 0.904, kite 1.79, peanut 1.13, hook 0.999 |
| R2/R1 | 0.755 | 1.003 | wrong_circle 1, circle_to_star 1, circle_to_c 0.949, kite 0.291, peanut 0.72, hook 0.926 |

Added hard stops: {'R1': [], 'R2': []}
Decision record: {'stage_a_only': False, 'gate_released': None, 'comparison': 'four-stage prefix endpoints', 'r2_qualifies': False, 'attributed_to_metric': True, 'r1_passes': False, 'detail_regression': {}}
