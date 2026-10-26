# PS-003: GPU slider policy comparisons

Questions: why are hook fits slow, which declared policy helps, and does slider recover other TG-002 cases?

Consumed fits: 1/13. Next fit: H2.

Saved GU-002 and PS-002 are references, not concurrent controls. No reference reruns.

| Run | Case | Recovered | Fit s | Final checks s | Accepted | Actual calls | Charged units | RMS mm |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GU-002 | hook__c13.3 | True | 30.29 | 2.52 | 125 | 2978 | 2978 | 0.0002302 |
| PS-002 | hook__c13.3 | False | 25.49 | 3.469 | 58 | 1676 | 1672 | 6.605 |
| H1 | hook__c13.3 | True | 25.46 | 1.95 | 119 | 2558 | 2558 | 0.0002482 |

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

Full scalar records, settings, histories and failures are in each run directory.
All fits use CUDA physics/preparation, four frequency threads, single-threaded BLAS, a centred start,
13,412 units / 120 s fit limits and 300 s final-check limits. Four-phase uses similarity only at warm-up.
One fit per setting cannot establish repeatability or a 30-case result. Defaults remain unchanged.
