| Arm | Outcome | Data loss | RMS error (mm) | Max error (mm) | Fit time | Speed ratio |
|---|---|---:|---:|---:|---:|---:|
| spectral | NUMERICAL_FAILURE (production evaluation failed at candidate state) in release_M11 | 0.592 | 8.28 | 25.07 | 124 s, 695 units | 6.466 |
| uncentred | NUMERICAL_FAILURE (production evaluation failed at candidate state) in fixed_M55 | 0.308 | 7.58 | 23.30 | 1684 s, 4707 units | 1.054 |
| n_update | NUMERICAL_FAILURE (production evaluation failed at candidate state) in stage_3_damped | 0.00583 + penalty 1.2e-05 | 8.23 | 26.83 | 50 s, 281 units | 2.562 |
| slider | COMPLETED_SCHEDULE (loss_tolerance) in fixed_M67 | 6.22e-15 | 0.00 | 0.00 | 497 s, 2978 units | 1.698 |

| Arm | Accepted steps | Max speed ratio | Final E | Max E | Max zero-step jump (mm) | Max crop (mm) | Geometry s | s per unit | Audit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| spectral | 92 | 6.466 | 1.89e-02 | 2.08e-02 | — | 1.37e+00 | 11 | 0.178 | failed |
| uncentred | 166 | 2.023 | 6.40e-05 | 1.15e-02 | 0.583 | 9.09e-01 | 371 | 0.358 | failed |
| n_update | 43 | 2.562 | 1.59e-01 | 1.59e-01 | — | — | 0 | 0.179 | failed |
| slider | 125 | 1.716 | 8.78e-02 | 1.01e-01 | — | — | 39 | 0.167 | passed |

Speed ratio of the last accepted curve in each stage:

| Stage | spectral | uncentred | n_update | slider |
|---|---:|---:|---:|---:|
| warmup_025_damped | 1.013 | 1.000 | 1.000 | 1.000 |
| stage_1_damped | 1.018 | 1.002 | 1.024 | 1.030 |
| stage_2_damped | 1.018 | 1.011 | 1.115 | 1.161 |
| stage_3_damped | 1.036 | 1.017 | 2.562 | 1.703 |
| stage_4_damped | 1.058 | 1.037 | — | 1.712 |
| stage_4_undamped | 3.503 | 2.020 | — | 1.715 |
| release_M11 | 6.466 | 1.003 | — | 1.715 |
| release_M15 | — | 1.002 | — | 1.710 |
| release_M19 | — | 1.009 | — | 1.698 |
| fixed_M25 | — | 1.000 | — | 1.698 |
| fixed_M31 | — | 1.000 | — | 1.698 |
| fixed_M37 | — | 1.006 | — | 1.698 |
| fixed_M43 | — | 1.005 | — | 1.698 |
| fixed_M49 | — | 1.058 | — | 1.698 |
| fixed_M55 | — | 1.054 | — | 1.698 |
| fixed_M61 | — | — | — | 1.698 |
| fixed_M67 | — | — | — | 1.698 |
