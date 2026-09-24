| Case | Star-shaped | SPD-008 | L | S | LS | Hybrid R0 | Hybrid R2 |
|---|---|---:|---:|---:|---:|---:|---:|
| Circle | yes | 7.49 (NUMERICAL_FAILURE) | 7.58e-06 | 18.5 (UNRESOLVED_DERIVATIVE) | 1.63e-05 | 0.00259 | 0.00183 |
| Star | yes | 7.34 (UNRESOLVED_DERIVATIVE) | 3.31e-05 | 1.67 | 4.75e-05 | 0.522 | 0.517 |
| C | no | 19 | 10.1 (UNRESOLVED_DERIVATIVE) | 25.3 | 11.2 (UNRESOLVED_DERIVATIVE) | 3.2 | 2.75 |
| Kite | yes | 21.3 | 1.25 (UNRESOLVED_DERIVATIVE) | 29.2 (UNRESOLVED_DERIVATIVE) | 8.63 (UNRESOLVED_DERIVATIVE) | 2.98 | 1.55 |
| Peanut | yes | 13.8 (UNRESOLVED_DERIVATIVE) | 1.21e-05 | 27.3 (UNRESOLVED_DERIVATIVE) | 0.137 | 2.94 | 2.39 |
| Hook | no | 12.6 | 9.36 (UNRESOLVED_DERIVATIVE) | 18.8 (UNRESOLVED_DERIVATIVE) | 9.58 (UNRESOLVED_DERIVATIVE) | 0.525 | 0.486 |

RMS in mm. Hausdorff upper bound (mm) / work units / accepted steps by stage:

| Case | Arm | Status | Hausdorff upper | Units | Accepted by stage | Endpoint qualified |
|---|---|---|---:|---:|---|---|
| Circle | SPD008 | HARD_STOP / NUMERICAL_FAILURE | 27 | 134 | [13] | False |
| Circle | L | COMPLETED_SCHEDULE | 0.0192 | 51 | [5, 0, 0, 0] | True |
| Circle | S | HARD_STOP / UNRESOLVED_DERIVATIVE | 60.6 | 226 | [22, 7] | True |
| Circle | LS | COMPLETED_SCHEDULE | 0.0192 | 137 | [22, 2, 0, 0] | True |
| Star | SPD008 | HARD_STOP / UNRESOLVED_DERIVATIVE | 24.6 | 607 | [19, 5] | True |
| Star | L | COMPLETED_SCHEDULE | 0.031 | 111 | [9, 4, 0, 0] | True |
| Star | S | COMPLETED_SCHEDULE | 5.8 | 1339 | [22, 18, 22, 22] | True |
| Star | LS | COMPLETED_SCHEDULE | 0.031 | 233 | [22, 14, 0, 0] | True |
| C | SPD008 | COMPLETED_SCHEDULE | 39 | 599 | [3, 0, 0, 4] | True |
| C | L | HARD_STOP / UNRESOLVED_DERIVATIVE | 29.5 | 56 | [7, 0] | True |
| C | S | COMPLETED_SCHEDULE | 80.4 | 822 | [22, 9, 0, 0] | True |
| C | LS | HARD_STOP / UNRESOLVED_DERIVATIVE | 23.7 | 404 | [22, 21, 0] | True |
| Kite | SPD008 | COMPLETED_SCHEDULE | 51.6 | 355 | [6, 0, 0, 0] | True |
| Kite | L | HARD_STOP / UNRESOLVED_DERIVATIVE | 3.17 | 869 | [7, 17, 22, 3] | True |
| Kite | S | HARD_STOP / UNRESOLVED_DERIVATIVE | 75.7 | 815 | [22, 10, 8] | True |
| Kite | LS | HARD_STOP / UNRESOLVED_DERIVATIVE | 21 | 372 | [22, 16, 0] | True |
| Peanut | SPD008 | HARD_STOP / UNRESOLVED_DERIVATIVE | 46.2 | 193 | [9, 1] | True |
| Peanut | L | COMPLETED_SCHEDULE | 0.0202 | 59 | [7, 0, 0, 0] | True |
| Peanut | S | HARD_STOP / UNRESOLVED_DERIVATIVE | 87.7 | 312 | [22, 6] | True |
| Peanut | LS | COMPLETED_SCHEDULE | 0.519 | 920 | [22, 22, 22, 22] | True |
| Hook | SPD008 | COMPLETED_SCHEDULE | 31.7 | 357 | [4, 0, 0, 0] | True |
| Hook | L | HARD_STOP / UNRESOLVED_DERIVATIVE | 20.2 | 50 | [7, 0] | True |
| Hook | S | HARD_STOP / UNRESOLVED_DERIVATIVE | 51.2 | 212 | [22, 3] | True |
| Hook | LS | HARD_STOP / UNRESOLVED_DERIVATIVE | 20 | 272 | [22, 9, 0] | True |

| GM RMS ratio (0.01 mm floor) | GM | Worst |
|---|---:|---:|
| all_six:L/SPD008 | 0.0177 | 0.741 |
| all_six:L/R0 | 0.34 | 17.8 |
| all_six:L/R2 | 0.408 | 19.3 |
| all_six:S/SPD008 | 1.2 | 2.47 |
| all_six:S/R0 | 23.1 | 1.85e+03 |
| all_six:S/R2 | 27.8 | 1.85e+03 |
| all_six:LS/SPD008 | 0.0385 | 0.758 |
| all_six:LS/R0 | 0.741 | 18.2 |
| all_six:LS/R2 | 0.89 | 19.7 |
| star_shaped_four:L/SPD008 | 0.00297 | 0.0588 |
| star_shaped_four:L/R0 | 0.0723 | 1 |
| star_shaped_four:L/R2 | 0.0899 | 1 |
| star_shaped_four:S/SPD008 | 1.11 | 2.47 |
| star_shaped_four:S/R0 | 27.1 | 1.85e+03 |
| star_shaped_four:S/R2 | 33.7 | 1.85e+03 |
| star_shaped_four:LS/SPD008 | 0.00925 | 0.405 |
| star_shaped_four:LS/R0 | 0.225 | 2.89 |
| star_shaped_four:LS/R2 | 0.28 | 5.56 |

| Arm:case | Stage-1 accepted | Largest stage-1 move mm | Stage-1 end radial RMS above mode 5 mm |
|---|---:|---:|---:|
| SPD008:wrong_circle | 13 | 20.35 | 8.850 |
| SPD008:circle_to_star | 19 | 40.82 | 9.925 |
| SPD008:kite | 6 | 18.69 | 6.482 |
| SPD008:peanut | 9 | 28.18 | 6.730 |
| L:wrong_circle | 5 | 20.96 | 0.000 |
| L:circle_to_star | 9 | 19.27 | 0.000 |
| L:kite | 7 | 21.68 | 0.000 |
| L:peanut | 7 | 20.15 | 0.000 |
| S:wrong_circle | 22 | 2.00 | 9.102 |
| S:circle_to_star | 22 | 2.00 | 9.521 |
| S:kite | 22 | 2.00 | 12.319 |
| S:peanut | 22 | 2.01 | 12.637 |
| LS:wrong_circle | 22 | 2.00 | 0.000 |
| LS:circle_to_star | 22 | 2.00 | 0.000 |
| LS:kite | 22 | 2.00 | 0.000 |
| LS:peanut | 22 | 2.00 | 0.000 |

| Arm:case | Proposals | Trust region binding | Damping range | Armijo refusals | Largest accepted move mm |
|---|---:|---:|---|---:|---:|
| S:wrong_circle | 29 | 0.138 | 8.8–1.2e+02 | 0 | 2.000 |
| S:circle_to_star | 94 | 0.16 | 1e-06–5.2e+07 | 0 | 2.005 |
| S:circle_to_c | 49 | 0.102 | 9.5–2.3e+06 | 0 | 2.002 |
| S:kite | 48 | 0.0625 | 5.5–6.3e+06 | 0 | 2.001 |
| S:peanut | 29 | 0.103 | 8.7–1.9e+02 | 0 | 2.009 |
| S:hook | 25 | 0.16 | 6.7–1.6e+02 | 0 | 2.001 |
| LS:wrong_circle | 39 | 0.0256 | 9e-05–10 | 0 | 1.998 |
| LS:circle_to_star | 51 | 0.118 | 7e-06–10 | 0 | 2.000 |
| LS:circle_to_c | 52 | 0.0577 | 7.2–6.5e+06 | 0 | 2.008 |
| LS:kite | 47 | 0.106 | 5.8–6.5e+06 | 0 | 2.000 |
| LS:peanut | 88 | 0.0114 | 1e-06–9.9 | 0 | 1.999 |
| LS:hook | 39 | 0.128 | 4.3–3.9e+06 | 0 | 2.003 |

H1 (LS recovers circle and star): **PASS** — {"wrong_circle": {"completed": true, "rms_mm": 1.6254580674428118e-05, "qualified": true, "pass": true}, "circle_to_star": {"completed": true, "rms_mm": 4.747403498696955e-05, "qualified": true, "pass": true}}

Kite/peanut classes: {"kite": "open", "peanut": "baseline_better_not_solved"}
