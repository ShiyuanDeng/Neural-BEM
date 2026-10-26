# PS-003: GPU slider policy comparisons

Questions: why are hook fits slow, which declared policy helps, and does slider recover other TG-002 cases?

Consumed fits: 10/13. Next fit: O3S.

Saved GU-002 and PS-002 are references, not concurrent controls. No reference reruns.

| Run | Case | Recovered | Fit s | Final checks s | Accepted | Actual calls | Charged units | RMS mm |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GU-002 | hook__c13.3 | True | 30.29 | 2.52 | 125 | 2978 | 2978 | 0.0002302 |
| PS-002 | hook__c13.3 | False | 25.49 | 3.469 | 58 | 1676 | 1672 | 6.605 |
| D1 | hook__c13.3 | False | 43.48 | 3.175 | 117 | 3040 | 3036 | 0.5129 |
| D2 | hook__c13.3 | True | 19.7 | 1.641 | 122 | 2653 | 2653 | 0.0004239 |
| H1 | hook__c13.3 | True | 25.46 | 1.95 | 119 | 2558 | 2558 | 0.0002482 |
| H2 | hook__c13.3 | False | 26.86 | 2.046 | 129 | 3012 | 3012 | 0.06962 |
| H3 | hook__c13.3 | True | 16.26 | 1.701 | 122 | 2653 | 2653 | 0.0004252 |
| O1B | circle__c4 | True | 2.213 | 1.853 | 9 | 278 | 278 | 1.055e-05 |
| O1S | circle__c4 | False | 1.495 | 0.8166 | 9 | 277 | 277 | 1.056e-05 |
| O2B | kite__c0.5 | True | 41.83 | 2.077 | 117 | 4064 | 4064 | 0.0119 |
| O2S | kite__c0.5 | True | 15.66 | 0.9419 | 105 | 3283 | 3283 | 0.01265 |
| O3B | c_shape__c13.3 | True | 12.26 | 2.462 | 78 | 1383 | 1383 | 3.762e-05 |

## Saved-run explanation

GU-002 used 40 accepted iterations and 15.926 s in M11/M15, with no rejected trials there.
Its loss fell from 0.14065 to 0.024019. Releasing M19 then reached 0.000072 in four iterations.
This is consistent with restricted update directions, but the saved run alone cannot establish the cause.

PS-002 left stage_3_damped after six iterations at loss 0.005709; GU-002 used 19 and reached 0.000656.
PS-002 entered M11 at loss 0.550665 versus 0.14065. Its early exits changed the later path.
M43/M49 then cost 9.703 s, with eight rejected trials; it failed recovery in M55.

The saved runs lack raw/clipped proposal sizes, skipped tiny proposals and damping retry counts.
Thread-level physics times overlap and are not wall-time totals. New batch timers measure wall time.

## Stage evidence

| Run | Stage (M/K/Ku/F) | Accepted | Seconds | Entry loss | Final loss | Rejected | Stop |
|---|---|---:|---:|---:|---:|---:|---|
| GU-002 | warmup_025_damped (1/4/64/—) | 11 | 0.5849 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| GU-002 | stage_1_damped (3/8/64/—) | 7 | 0.1455 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| GU-002 | stage_2_damped (5/12/64/—) | 8 | 0.2697 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| GU-002 | stage_3_damped (7/16/64/—) | 19 | 1.532 | 0.0077 | 0.000656 | 8 | no_decreasing_step |
| GU-002 | stage_4_damped (9/20/64/—) | 8 | 0.9324 | 0.001229 | 0.0002032 | 0 | no_decreasing_step |
| GU-002 | stage_4_undamped (9/20/64/—) | 16 | 1.316 | 0.07096 | 0.008344 | 0 | no_decreasing_step |
| GU-002 | release_M11 (11/192/128/—) | 22 | 8.697 | 0.1406 | 0.0358 | 0 | maximum_iterations |
| GU-002 | release_M15 (15/192/128/—) | 18 | 7.229 | 0.0358 | 0.02402 | 0 | no_decreasing_step |
| GU-002 | release_M19 (19/192/128/—) | 4 | 1.848 | 0.02402 | 7.167e-05 | 0 | no_decreasing_step |
| GU-002 | fixed_M25 (25/192/128/—) | 2 | 1.205 | 7.167e-05 | 4.981e-06 | 0 | no_decreasing_step |
| GU-002 | fixed_M31 (31/192/128/—) | 2 | 1.087 | 4.981e-06 | 6.387e-07 | 0 | no_decreasing_step |
| GU-002 | fixed_M37 (37/192/128/—) | 1 | 0.6817 | 6.387e-07 | 2.128e-08 | 0 | no_decreasing_step |
| GU-002 | fixed_M43 (43/192/128/—) | 1 | 0.7013 | 2.128e-08 | 1.282e-09 | 0 | no_decreasing_step |
| GU-002 | fixed_M49 (49/192/128/—) | 2 | 1.107 | 1.282e-09 | 2.726e-13 | 0 | no_decreasing_step |
| GU-002 | fixed_M55 (55/192/128/—) | 4 | 1.971 | 2.726e-13 | 6.221e-15 | 0 | loss_tolerance |
| GU-002 | fixed_M61 (61/192/128/—) | 0 | 0.2754 | 6.221e-15 | 6.221e-15 | 0 | loss_tolerance |
| GU-002 | fixed_M67 (67/192/128/—) | 0 | 0.2692 | 6.221e-15 | 6.221e-15 | 0 | loss_tolerance |
| PS-002 | warmup_025_damped (1/4/64/—) | 4 | 0.5058 | 0.6269 | 0.03623 | 0 | progress_exit |
| PS-002 | stage_1_damped (3/8/64/—) | 3 | 0.07295 | 0.04931 | 0.009603 | 0 | progress_exit |
| PS-002 | stage_2_damped (5/12/64/—) | 5 | 0.1915 | 0.01977 | 0.009124 | 1 | progress_exit |
| PS-002 | stage_3_damped (7/16/64/—) | 6 | 0.479 | 0.007702 | 0.005709 | 3 | progress_exit |
| PS-002 | stage_4_damped (9/20/64/—) | 8 | 0.8754 | 0.004791 | 0.002775 | 5 | progress_exit |
| PS-002 | stage_4_undamped (9/20/64/—) | 8 | 0.8039 | 0.4698 | 0.2006 | 1 | progress_exit |
| PS-002 | release_M11 (11/192/128/—) | 4 | 2.282 | 0.5507 | 0.4425 | 0 | progress_exit |
| PS-002 | release_M15 (15/192/128/—) | 7 | 3.405 | 0.4425 | 0.3623 | 0 | progress_exit |
| PS-002 | release_M19 (19/192/128/—) | 2 | 1.229 | 0.3623 | 0.3488 | 0 | progress_exit |
| PS-002 | fixed_M25 (25/192/128/—) | 3 | 2.207 | 0.3488 | 0.3236 | 0 | progress_exit |
| PS-002 | fixed_M31 (31/192/128/—) | 2 | 1.438 | 0.3236 | 0.31 | 0 | progress_exit |
| PS-002 | fixed_M37 (37/192/128/—) | 2 | 1.416 | 0.31 | 0.2972 | 0 | progress_exit |
| PS-002 | fixed_M43 (43/192/128/—) | 2 | 3.357 | 0.2972 | 0.2943 | 3 | progress_exit |
| PS-002 | fixed_M49 (49/192/128/—) | 2 | 6.346 | 0.2943 | 0.2894 | 5 | progress_exit |
| PS-002 | fixed_M55 (55/192/128/—) | 0 | 0.3045 | 0.2894 | 0.2894 | 1 | — |
| D1 | warmup_025_damped (1/4/64/1) | 11 | 0.5938 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| D1 | stage_1_damped (3/8/64/1) | 7 | 0.1485 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| D1 | stage_2_damped (5/12/64/2) | 8 | 0.2804 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| D1 | stage_3_damped (7/16/64/3) | 19 | 1.542 | 0.0077 | 0.000656 | 8 | no_decreasing_step |
| D1 | stage_4_damped (9/20/64/4) | 8 | 0.9263 | 0.001229 | 0.0002032 | 0 | no_decreasing_step |
| D1 | stage_4_undamped (9/20/64/4) | 16 | 1.33 | 0.07096 | 0.008344 | 0 | no_decreasing_step |
| D1 | release_M19 (19/192/128/19) | 22 | 10.79 | 0.1406 | 0.02162 | 7 | maximum_iterations |
| D1 | fixed_M25 (25/192/128/19) | 5 | 3.31 | 0.02162 | 0.0162 | 4 | — |
| D1 | fixed_M31 (31/192/128/19) | 6 | 3.015 | 0.0162 | 0.01008 | 1 | — |
| D1 | fixed_M37 (37/192/128/19) | 5 | 3.364 | 0.01008 | 0.007931 | 3 | — |
| D1 | fixed_M43 (43/192/128/19) | 5 | 4.841 | 0.007931 | 0.007194 | 4 | — |
| D1 | fixed_M49 (49/192/128/19) | 3 | 5.884 | 0.007194 | 0.006922 | 7 | — |
| D1 | fixed_M55 (55/192/128/19) | 2 | 7.052 | 0.006922 | 0.006876 | 7 | — |
| D2 | warmup_025_damped (1/4/64/1) | 11 | 0.5792 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| D2 | stage_1_damped (3/8/64/1) | 7 | 0.1457 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| D2 | stage_2_damped (5/12/64/2) | 8 | 0.264 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| D2 | stage_3_damped (7/16/64/3) | 20 | 1.484 | 0.0077 | 0.0006484 | 6 | no_decreasing_step |
| D2 | stage_4_damped (9/20/64/4) | 7 | 0.5922 | 0.00113 | 0.0001789 | 0 | no_decreasing_step |
| D2 | stage_4_undamped (9/20/64/4) | 22 | 1.695 | 0.08043 | 0.008048 | 0 | maximum_iterations |
| D2 | release_M11 (11/24/128/19) | 15 | 3.717 | 0.1273 | 0.02387 | 0 | no_decreasing_step |
| D2 | release_M15 (15/32/128/19) | 13 | 3.44 | 0.02387 | 0.01366 | 0 | no_decreasing_step |
| D2 | release_M19 (19/40/128/19) | 5 | 1.459 | 0.01366 | 0.0002288 | 0 | no_decreasing_step |
| D2 | fixed_M25 (25/52/128/19) | 3 | 0.9584 | 0.0002288 | 2.242e-05 | 0 | no_decreasing_step |
| D2 | fixed_M31 (31/64/128/19) | 2 | 0.7258 | 2.242e-05 | 4.903e-07 | 0 | no_decreasing_step |
| D2 | fixed_M37 (37/76/128/19) | 2 | 0.773 | 4.903e-07 | 1.557e-08 | 0 | no_decreasing_step |
| D2 | fixed_M43 (43/88/128/19) | 1 | 0.6125 | 1.557e-08 | 3.299e-10 | 0 | no_decreasing_step |
| D2 | fixed_M49 (49/100/128/19) | 2 | 0.8967 | 3.299e-10 | 2.572e-12 | 0 | no_decreasing_step |
| D2 | fixed_M55 (55/112/128/19) | 4 | 1.45 | 2.572e-12 | 5.31e-15 | 0 | loss_tolerance |
| D2 | fixed_M61 (61/124/128/19) | 0 | 0.3794 | 5.31e-15 | 5.31e-15 | 0 | loss_tolerance |
| D2 | fixed_M67 (67/136/128/19) | 0 | 0.3039 | 5.31e-15 | 5.31e-15 | 0 | loss_tolerance |
| H1 | warmup_025_damped (1/4/64/1) | 11 | 0.583 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| H1 | stage_1_damped (3/8/64/1) | 7 | 0.1465 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| H1 | stage_2_damped (5/12/64/2) | 8 | 0.2743 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| H1 | stage_3_damped (7/16/64/3) | 20 | 1.491 | 0.0077 | 0.0006484 | 6 | no_decreasing_step |
| H1 | stage_4_damped (9/20/64/4) | 7 | 0.5955 | 0.00113 | 0.0001789 | 0 | no_decreasing_step |
| H1 | stage_4_undamped (9/20/64/4) | 22 | 1.691 | 0.08043 | 0.008048 | 0 | maximum_iterations |
| H1 | release_M11 (11/192/128/19) | 17 | 6.772 | 0.1273 | 0.02477 | 0 | no_decreasing_step |
| H1 | release_M15 (15/192/128/19) | 14 | 5.679 | 0.02477 | 0.01663 | 0 | no_decreasing_step |
| H1 | release_M19 (19/192/128/19) | 4 | 1.829 | 0.01663 | 5.122e-05 | 0 | no_decreasing_step |
| H1 | fixed_M25 (25/192/128/19) | 2 | 1.203 | 5.122e-05 | 2.585e-06 | 0 | no_decreasing_step |
| H1 | fixed_M31 (31/192/128/19) | 2 | 1.063 | 2.585e-06 | 3.094e-07 | 0 | no_decreasing_step |
| H1 | fixed_M37 (37/192/128/19) | 1 | 0.6745 | 3.094e-07 | 1.031e-08 | 0 | no_decreasing_step |
| H1 | fixed_M43 (43/192/128/19) | 1 | 0.6804 | 1.031e-08 | 9.235e-10 | 0 | no_decreasing_step |
| H1 | fixed_M49 (49/192/128/19) | 2 | 1.093 | 9.235e-10 | 2.052e-13 | 0 | no_decreasing_step |
| H1 | fixed_M55 (55/192/128/19) | 1 | 0.7052 | 2.052e-13 | 4.552e-14 | 0 | no_decreasing_step |
| H1 | fixed_M61 (61/192/128/19) | 0 | 0.262 | 4.552e-14 | 4.552e-14 | 0 | no_decreasing_step |
| H1 | fixed_M67 (67/192/128/19) | 0 | 0.2592 | 4.552e-14 | 4.552e-14 | 0 | no_decreasing_step |
| H2 | initialize_translation_scale (0/4/64/1) | 11 | 0.4785 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| H2 | stage_1_damped (3/8/64/1) | 7 | 0.2282 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| H2 | stage_2_damped (5/12/64/2) | 8 | 0.2835 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| H2 | stage_3_damped (7/16/64/3) | 20 | 1.485 | 0.0077 | 0.0006484 | 6 | no_decreasing_step |
| H2 | stage_4_damped (9/20/64/4) | 7 | 0.5987 | 0.00113 | 0.0001789 | 0 | no_decreasing_step |
| H2 | stage_4_undamped (9/20/64/4) | 22 | 1.689 | 0.08043 | 0.008048 | 0 | maximum_iterations |
| H2 | shape_1_M11 (11/24/64/19) | 15 | 2.574 | 0.1273 | 0.02388 | 0 | no_decreasing_step |
| H2 | shape_2_M15 (15/32/64/19) | 13 | 2.271 | 0.02388 | 0.01366 | 0 | no_decreasing_step |
| H2 | shape_3_M19 (19/40/64/19) | 5 | 1.028 | 0.01366 | 0.0002288 | 0 | no_decreasing_step |
| H2 | shape_4_M25 (25/52/64/19) | 3 | 0.7525 | 0.0002288 | 2.243e-05 | 0 | no_decreasing_step |
| H2 | full_release_M95 (95/192/128/19) | 18 | 15.37 | 2.242e-05 | 8.375e-07 | 16 | no_decreasing_step |
| H3 | warmup_025_damped (1/4/64/1) | 11 | 0.5772 | 0.6269 | 0.03623 | 0 | no_decreasing_step |
| H3 | stage_1_damped (3/8/64/1) | 7 | 0.1476 | 0.05039 | 0.009603 | 0 | no_decreasing_step |
| H3 | stage_2_damped (5/12/64/2) | 8 | 0.283 | 0.01972 | 0.009124 | 1 | no_decreasing_step |
| H3 | stage_3_damped (7/16/64/3) | 20 | 1.514 | 0.0077 | 0.0006484 | 6 | no_decreasing_step |
| H3 | stage_4_damped (9/20/64/4) | 7 | 0.6144 | 0.00113 | 0.0001789 | 0 | no_decreasing_step |
| H3 | stage_4_undamped (9/20/64/4) | 22 | 1.702 | 0.08043 | 0.008048 | 0 | maximum_iterations |
| H3 | release_M11 (11/24/64/19) | 15 | 2.55 | 0.1273 | 0.02388 | 0 | no_decreasing_step |
| H3 | release_M15 (15/32/64/19) | 13 | 2.242 | 0.02388 | 0.01366 | 0 | no_decreasing_step |
| H3 | release_M19 (19/40/64/19) | 5 | 1.019 | 0.01366 | 0.0002288 | 0 | no_decreasing_step |
| H3 | fixed_M25 (25/52/64/19) | 3 | 0.7473 | 0.0002288 | 2.243e-05 | 0 | no_decreasing_step |
| H3 | fixed_M31 (31/64/64/19) | 2 | 0.5562 | 2.243e-05 | 4.997e-07 | 0 | no_decreasing_step |
| H3 | fixed_M37 (37/76/96/19) | 2 | 0.6612 | 4.94e-07 | 1.567e-08 | 0 | no_decreasing_step |
| H3 | fixed_M43 (43/88/96/19) | 1 | 0.43 | 1.567e-08 | 3.291e-10 | 0 | no_decreasing_step |
| H3 | fixed_M49 (49/100/96/19) | 2 | 0.8148 | 3.291e-10 | 2.567e-12 | 0 | no_decreasing_step |
| H3 | fixed_M55 (55/112/96/19) | 4 | 1.317 | 2.567e-12 | 5.318e-15 | 0 | loss_tolerance |
| H3 | fixed_M61 (61/124/96/19) | 0 | 0.3071 | 5.318e-15 | 5.318e-15 | 0 | loss_tolerance |
| H3 | fixed_M67 (67/136/128/19) | 0 | 0.4265 | 5.311e-15 | 5.311e-15 | 0 | loss_tolerance |
| O1B | warmup_025_damped (1/4/64/1) | 9 | 0.5736 | 0.08708 | 4.709e-16 | 0 | loss_tolerance |
| O1B | stage_1_damped (3/8/64/1) | 0 | 0.01847 | 2.907e-14 | 2.907e-14 | 0 | no_decreasing_step |
| O1B | stage_2_damped (5/12/64/2) | 0 | 0.03259 | 5.885e-14 | 5.885e-14 | 0 | no_decreasing_step |
| O1B | stage_3_damped (7/16/64/3) | 0 | 0.03822 | 7.548e-14 | 7.548e-14 | 0 | no_decreasing_step |
| O1B | stage_4_damped (9/20/64/4) | 0 | 0.03734 | 9.513e-14 | 9.513e-14 | 0 | no_decreasing_step |
| O1B | stage_4_undamped (9/20/64/4) | 0 | 0.02386 | 8.18e-13 | 8.18e-13 | 0 | no_decreasing_step |
| O1B | release_M11 (11/192/128/19) | 0 | 0.2551 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1B | release_M15 (15/192/128/19) | 0 | 0.2049 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1B | release_M19 (19/192/128/19) | 0 | 0.219 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1B | fixed_M25 (25/192/128/19) | 0 | 0.2157 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1B | fixed_M31 (31/192/128/19) | 0 | 0.205 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1B | fixed_M37 (37/192/128/19) | 0 | 0.2146 | 3.14e-12 | 3.14e-12 | 0 | no_decreasing_step |
| O1S | warmup_025_damped (1/4/64/1) | 9 | 0.5433 | 0.08708 | 4.725e-16 | 0 | loss_tolerance |
| O1S | stage_1_damped (3/8/64/1) | 0 | 0.01938 | 2.917e-14 | 2.917e-14 | 0 | no_decreasing_step |
| O1S | stage_2_damped (5/12/64/2) | 0 | 0.03425 | 5.906e-14 | 5.906e-14 | 0 | no_decreasing_step |
| O1S | stage_3_damped (7/16/64/3) | 0 | 0.03346 | 7.575e-14 | 7.575e-14 | 0 | no_decreasing_step |
| O1S | stage_4_damped (9/20/64/4) | 0 | 0.03737 | 9.547e-14 | 9.547e-14 | 0 | no_decreasing_step |
| O1S | stage_4_undamped (9/20/64/4) | 0 | 0.02585 | 8.208e-13 | 8.208e-13 | 0 | no_decreasing_step |
| O1S | release_M11 (11/24/64/19) | 0 | 0.1048 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O1S | release_M15 (15/32/64/19) | 0 | 0.1133 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O1S | release_M19 (19/40/64/19) | 0 | 0.101 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O1S | fixed_M25 (25/52/64/19) | 0 | 0.09989 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O1S | fixed_M31 (31/64/64/19) | 0 | 0.1142 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O1S | fixed_M37 (37/76/96/19) | 0 | 0.1414 | 3.151e-12 | 3.151e-12 | 0 | no_decreasing_step |
| O2B | warmup_025_damped (1/4/64/1) | 6 | 0.5002 | 4.057 | 0.0002591 | 0 | no_decreasing_step |
| O2B | stage_1_damped (3/8/64/1) | 5 | 0.1283 | 0.006339 | 4.209e-05 | 0 | no_decreasing_step |
| O2B | stage_2_damped (5/12/64/2) | 12 | 0.3769 | 0.0005065 | 1.297e-05 | 0 | no_decreasing_step |
| O2B | stage_3_damped (7/16/64/3) | 16 | 0.6548 | 0.0001104 | 4.437e-07 | 0 | no_decreasing_step |
| O2B | stage_4_damped (9/20/64/4) | 15 | 1.068 | 3.035e-06 | 1.421e-07 | 9 | no_decreasing_step |
| O2B | stage_4_undamped (9/20/64/4) | 15 | 1.215 | 1.568e-07 | 4.961e-08 | 14 | no_decreasing_step |
| O2B | release_M11 (11/192/128/19) | 3 | 1.17 | 0.0001532 | 2.871e-06 | 0 | no_decreasing_step |
| O2B | release_M15 (15/192/128/19) | 16 | 10.28 | 2.871e-06 | 2.476e-08 | 21 | no_decreasing_step |
| O2B | release_M19 (19/192/128/19) | 16 | 16.97 | 2.476e-08 | 2.426e-09 | 45 | — |
| O2B | fixed_M25 (25/192/128/19) | 4 | 2.962 | 2.426e-09 | 2.333e-10 | 6 | — |
| O2B | fixed_M31 (31/192/128/19) | 4 | 3.177 | 2.333e-10 | 1.836e-11 | 6 | — |
| O2B | fixed_M37 (37/192/128/19) | 5 | 3.006 | 1.836e-11 | 1.522e-12 | 4 | — |
| O2S | warmup_025_damped (1/4/64/1) | 6 | 0.5031 | 4.057 | 0.0002591 | 0 | no_decreasing_step |
| O2S | stage_1_damped (3/8/64/1) | 5 | 0.1243 | 0.006339 | 4.209e-05 | 0 | no_decreasing_step |
| O2S | stage_2_damped (5/12/64/2) | 12 | 0.3727 | 0.0005065 | 1.297e-05 | 0 | no_decreasing_step |
| O2S | stage_3_damped (7/16/64/3) | 15 | 0.6122 | 0.0001104 | 4.436e-07 | 0 | no_decreasing_step |
| O2S | stage_4_damped (9/20/64/4) | 8 | 0.547 | 3.034e-06 | 1.476e-07 | 4 | no_decreasing_step |
| O2S | stage_4_undamped (9/20/64/4) | 10 | 0.6878 | 1.761e-07 | 5.457e-08 | 6 | gradient_tolerance |
| O2S | release_M11 (11/24/64/19) | 4 | 0.6007 | 0.000163 | 2.85e-06 | 0 | no_decreasing_step |
| O2S | release_M15 (15/32/64/19) | 13 | 2.954 | 2.85e-06 | 1.249e-08 | 12 | no_decreasing_step |
| O2S | release_M19 (19/40/64/19) | 22 | 4.614 | 1.249e-08 | 9.181e-10 | 13 | maximum_iterations |
| O2S | fixed_M25 (25/52/64/19) | 3 | 1.353 | 9.181e-10 | 3.009e-10 | 8 | — |
| O2S | fixed_M31 (31/64/64/19) | 4 | 1.478 | 3.009e-10 | 1.401e-11 | 6 | — |
| O2S | fixed_M37 (37/76/96/19) | 3 | 1.624 | 1.401e-11 | 1.071e-12 | 8 | — |
| O3B | warmup_025_damped (1/4/64/1) | 11 | 0.5832 | 0.498 | 0.07339 | 0 | no_decreasing_step |
| O3B | stage_1_damped (3/8/64/1) | 8 | 0.1842 | 0.05416 | 0.007901 | 0 | no_decreasing_step |
| O3B | stage_2_damped (5/12/64/2) | 22 | 0.7442 | 0.01637 | 0.002828 | 0 | maximum_iterations |
| O3B | stage_3_damped (7/16/64/3) | 9 | 0.7313 | 0.002775 | 0.0001009 | 5 | no_decreasing_step |
| O3B | stage_4_damped (9/20/64/4) | 4 | 0.3822 | 0.0001773 | 2.008e-05 | 1 | no_decreasing_step |
| O3B | stage_4_undamped (9/20/64/4) | 7 | 0.4772 | 0.008127 | 0.002518 | 0 | no_decreasing_step |
| O3B | release_M11 (11/192/128/19) | 7 | 2.729 | 0.05078 | 0.01309 | 0 | no_decreasing_step |
| O3B | release_M15 (15/192/128/19) | 3 | 1.259 | 0.01309 | 0.0003331 | 0 | no_decreasing_step |
| O3B | release_M19 (19/192/128/19) | 2 | 0.9353 | 0.0003331 | 1.417e-05 | 0 | no_decreasing_step |
| O3B | fixed_M25 (25/192/128/19) | 2 | 1.046 | 1.417e-05 | 8.811e-07 | 0 | no_decreasing_step |
| O3B | fixed_M31 (31/192/128/19) | 1 | 0.6034 | 8.811e-07 | 1.685e-08 | 0 | no_decreasing_step |
| O3B | fixed_M37 (37/192/128/19) | 1 | 0.5972 | 1.685e-08 | 2.289e-10 | 0 | no_decreasing_step |
| O3B | fixed_M43 (43/192/128/19) | 1 | 0.5936 | 2.289e-10 | 1.103e-12 | 0 | no_decreasing_step |
| O3B | fixed_M49 (49/192/128/19) | 0 | 0.2368 | 1.103e-12 | 1.103e-12 | 0 | no_decreasing_step |
| O3B | fixed_M55 (55/192/128/19) | 0 | 0.2483 | 1.103e-12 | 1.103e-12 | 0 | no_decreasing_step |
| O3B | fixed_M61 (61/192/128/19) | 0 | 0.2548 | 1.103e-12 | 1.103e-12 | 0 | no_decreasing_step |
| O3B | fixed_M67 (67/192/128/19) | 0 | 0.2595 | 1.103e-12 | 1.103e-12 | 0 | no_decreasing_step |

Full scalar records, settings, histories and failures are in each run directory.
All fits use CUDA physics/preparation, four frequency threads, single-threaded BLAS, a centred start,
13,412 units / 120 s fit limits and 300 s final-check limits. Four-phase uses similarity only at warm-up.
One fit per setting cannot establish repeatability or a 30-case result. Defaults remain unchanged.
