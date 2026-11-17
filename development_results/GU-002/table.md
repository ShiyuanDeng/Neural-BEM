# GU-002 tables

## Saved-state preparation, CPU against CUDA

| State | K | M | Rank CPU / CUDA | Relative error | Curve difference (mm) | CPU s | CUDA s | Speedup | CUDA first use s | Passed |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| stage_1_damped | 8 | 3 | 33 / 33 | 3.7e-13 | 4.2e-14 | 0.0004 | 0.0018 | 0.2 | 0.279 | yes |
| release_M11 | 192 | 11 | 769 / 769 | 5.9e-11 | 5.0e-12 | 0.3079 | 0.0296 | 10.4 | 0.039 | yes |
| fixed_M67 | 192 | 67 | 769 / 769 | 4.8e-11 | 1.7e-12 | 0.3402 | 0.0346 | 9.8 | 0.035 | yes |

Median parts of a warmed preparation (s):

| State | Device | Sampling | Transfer | Dense rows and products | Solve |
|---|---|---:|---:|---:|---:|
| stage_1_damped | cpu | 0.0002 | 0.0000 | 0.0002 | 0.0001 |
| stage_1_damped | cuda | 0.0002 | 0.0001 | 0.0004 | 0.0011 |
| release_M11 | cpu | 0.0015 | 0.0000 | 0.2480 | 0.0581 |
| release_M11 | cuda | 0.0016 | 0.0002 | 0.0109 | 0.0169 |
| fixed_M67 | cpu | 0.0048 | 0.0000 | 0.2621 | 0.0733 |
| fixed_M67 | cuda | 0.0046 | 0.0007 | 0.0118 | 0.0174 |

CPU against CUDA, one bounded step (requested normal push peaking at 0.1 mm):

| State | Max normal move diff (m) | RMS normal move diff (m) | Speed-change spread diff | Speed ratio diff |
|---|---:|---:|---:|---:|
| stage_1_damped | 1.6e-17 | 4.6e-18 | 8.1e-18 | 0.0e+00 |
| release_M11 | 4.5e-16 | 1.8e-16 | 5.4e-15 | 2.2e-15 |
| fixed_M67 | 1.0e-16 | 1.1e-17 | 1.6e-17 | 2.4e-15 |

## Hook c13.3 fits, one at a time on this machine

| Arm | Outcome in last stage | Recovered | Fit s | Units | s per unit | Preparations | Preparation s | Share | s to release_M11 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| spectral | NUMERICAL_FAILURE in release_M11 | no | 8.3 | 695 | 0.0120 | 99 | 0.24 | 2.9% | 6.0 |
| slider_cpu | COMPLETED_SCHEDULE in fixed_M67 | yes | 49.7 | 2978 | 0.0167 | 142 | 21.48 | 43.2% | 4.6 |
| slider | COMPLETED_SCHEDULE in fixed_M67 | yes | 30.3 | 2978 | 0.0102 | 142 | 2.41 | 8.0% | 4.8 |

Ratios above 1 mean the CUDA-preparation slider is faster:

| Ratio | Fit time | Preparation | Per preparation | Time to release_M11 | s per unit |
|---|---:|---:|---:|---:|---:|
| slider_cpu/slider | 1.64 | 8.9 | 8.9 | 0.96 | 1.64 |
| spectral/slider | — | — | — | 1.24 | 1.18 |

Seconds per stage:

| Stage | spectral | slider_cpu | slider |
|---|---:|---:|---:|
| warmup_025_damped | 0.6 | 0.5 | 0.6 |
| stage_1_damped | 0.2 | 0.1 | 0.1 |
| stage_2_damped | 0.2 | 0.3 | 0.3 |
| stage_3_damped | 1.1 | 1.5 | 1.5 |
| stage_4_damped | 2.0 | 0.9 | 0.9 |
| stage_4_undamped | 2.0 | 1.3 | 1.3 |
| release_M11 | 2.3 | 15.4 | 8.7 |
| release_M15 | — | 12.6 | 7.2 |
| release_M19 | — | 3.4 | 1.8 |
| fixed_M25 | — | 2.1 | 1.2 |
| fixed_M31 | — | 1.9 | 1.1 |
| fixed_M37 | — | 1.3 | 0.7 |
| fixed_M43 | — | 1.3 | 0.7 |
| fixed_M49 | — | 2.0 | 1.1 |
| fixed_M55 | — | 3.4 | 2.0 |
| fixed_M61 | — | 0.6 | 0.3 |
| fixed_M67 | — | 0.6 | 0.3 |

## N-update with the level penalty on hook c13.3

Losses are at the last accepted curve, so they compare only where the last stage matches.

| Fraction | Outcome in last stage | Recovered | RMS (mm) | Hausdorff upper (mm) | Max residual | Data loss | Penalty | Last stage weight | Max speed ratio | Final E | Max normal move (mm) | Units | Fit s |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.01 (GU-001) | NUMERICAL_FAILURE (production evaluation failed at candidate state) in stage_3_damped | no | 8.2339 | 26.8620 | 1.60e+00 | 0.00583 | 1.2e-05 | 7.74e-05 | 2.562 | 1.59e-01 | 26.484 | 281 | 50 |
| 0.1 | NUMERICAL_FAILURE (production evaluation failed at candidate state) in stage_3_damped | no | 1.8254 | 4.6354 | 1.44e+00 | 0.00152 | 0.00027 | 7.71e-04 | 63.911 | 3.53e-01 | 26.482 | 171 | 4 |
| 1 | NUMERICAL_FAILURE (production evaluation failed at candidate state) in release_M11 | no | 1.0305 | 3.3792 | 1.01e+00 | 0.13 | 0.018 | 3.06e-01 | 21.148 | 5.83e-02 | 26.466 | 851 | 13 |
| 10 | COMPLETED_SCHEDULE (None) in fixed_M79 | no | 7.9544 | 25.3183 | 1.14e+00 | 0.266 | 0.0016 | 2.70e+00 | 1.176 | 6.05e-04 | 26.311 | 5993 | 66 |

Data loss of the last accepted curve in each stage:

| Stage | 0.01 | 0.1 | 1 | 10 |
|---|---:|---:|---:|---:|
| warmup_025_damped | 0.0362 | 0.0362 | 0.0362 | 0.0362 |
| stage_1_damped | 0.00961 | 0.00961 | 0.00961 | 0.00962 |
| stage_2_damped | 0.00916 | 0.00913 | 0.00912 | 0.00917 |
| stage_3_damped | 0.00583 | 0.00152 | 0.00583 | 0.00623 |
| stage_4_damped | — | — | 0.000267 | 0.00452 |
| stage_4_undamped | — | — | 0.0854 | 0.215 |
| release_M11 | — | — | 0.13 | 0.346 |
| release_M15 | — | — | — | 0.31 |
| release_M19 | — | — | — | 0.303 |
| fixed_M25 | — | — | — | 0.296 |
| fixed_M31 | — | — | — | 0.287 |
| fixed_M37 | — | — | — | 0.284 |
| fixed_M43 | — | — | — | 0.281 |
| fixed_M49 | — | — | — | 0.279 |
| fixed_M55 | — | — | — | 0.278 |
| fixed_M61 | — | — | — | 0.275 |
| fixed_M67 | — | — | — | 0.272 |
| fixed_M73 | — | — | — | 0.27 |
| fixed_M79 | — | — | — | 0.266 |

Speed ratio of the last accepted curve in each stage:

| Stage | 0.01 | 0.1 | 1 | 10 |
|---|---:|---:|---:|---:|
| warmup_025_damped | 1.000 | 1.000 | 1.000 | 1.000 |
| stage_1_damped | 1.024 | 1.023 | 1.022 | 1.019 |
| stage_2_damped | 1.115 | 1.091 | 1.088 | 1.063 |
| stage_3_damped | 2.562 | 63.911 | 1.345 | 1.162 |
| stage_4_damped | — | — | 3.452 | 1.141 |
| stage_4_undamped | — | — | 3.545 | 1.111 |
| release_M11 | — | — | 21.148 | 1.148 |
| release_M15 | — | — | — | 1.132 |
| release_M19 | — | — | — | 1.122 |
| fixed_M25 | — | — | — | 1.095 |
| fixed_M31 | — | — | — | 1.115 |
| fixed_M37 | — | — | — | 1.092 |
| fixed_M43 | — | — | — | 1.084 |
| fixed_M49 | — | — | — | 1.089 |
| fixed_M55 | — | — | — | 1.089 |
| fixed_M61 | — | — | — | 1.072 |
| fixed_M67 | — | — | — | 1.115 |
| fixed_M73 | — | — | — | 1.108 |
| fixed_M79 | — | — | — | 1.116 |
