# Saved measured-cylinder comparisons

All-frequency losses use saved BEM residual evaluations. Nominal area error uses the 15 mm disk at (0,30) mm. Registered error translates that reference to the fixed best-circle centre; missing final evaluations stay pending.

| Variant / attempt | Status | Loss, 1–8 GHz | Radius mm | Centre mm | Permittivity | Nominal area error | Registered area error | Units |
|---|---|---:|---:|---|---:|---:|---:|---:|
| saved / attempt_01 | complete; COMPLETED_SCHEDULE | 0.0840431 | 19.0453 | (2.983, 29.241) | 2.19373 | 0.67845 | 0.614888 | 894 |
| warmup / attempt_01 | stopped by coordinator at 02:20 UTC; partial run | pending | pending | pending | pending | pending | pending | pending |
| warmup / attempt_02 | complete; TRIAL_WALL_LIMIT | 0.206605 | 3.33575 | (1.800, 31.218) | 32.0756 | 0.950546 | 0.950546 | 1076 |
| first_cap / attempt_01 | complete; COMPLETED_SCHEDULE | 0.0428901 | 12.7872 | (2.188, 27.063) | 3.79299 | 0.460712 | 0.352415 | 2552 |
| circle_ladder / attempt_01 | complete; COMPLETED_SCHEDULE | 0.0375382 | 15.2764 | (1.945, 26.190) | 3.05177 | 0.365853 | 0.0371975 | 6445 |
| circle_then_ladder / attempt_01 | complete; TRIAL_WALL_LIMIT | 0.0772304 | 10.3411 | (2.756, 27.475) | 4.76155 | 0.607174 | 0.573402 | 1937 |
| frontier_capped / attempt_01 | complete; NUMERICAL_FAILURE | 0.136051 | 5.51145 | (2.046, 26.974) | 13.7258 | 0.873466 | 0.864995 | 1344 |
| frontier_measured / attempt_01 | stopped by coordinator at 04:00 UTC; not a failure | pending | pending | pending | pending | pending | pending | pending |
| best exact circle / diagnostic | exact-series least squares; not a BEM fit | 0.037549 | 15.2662 | (1.939, 26.191) | 3.05255 | 0.365514 | 0.0358112 | pending |
| MF-CC-CSI | CSI half-peak support | not evaluated | 15.3117 | (1.887, 26.351) | 2.72927 (support mean) | 0.35123 | not evaluated | not comparable |
| MF-MR-CSI | CSI half-peak support | not evaluated | 15.0931 | (1.615, 26.282) | 3.01211 (support mean) | 0.342226 | not evaluated | not comparable |
| CSI | CSI half-peak support | not evaluated | 13.4285 | (1.838, 26.530) | 3.28088 (support mean) | 0.384729 | not evaluated | not comparable |

## saved / attempt_01

Evidence: `results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01`. Outcome: COMPLETED_SCHEDULE. Last saved stage: full_6_M37.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.227804 → 0.0909416 | 1.0931 → 1.73128 | 22.8948 | (2.630, 34.081) | 165 / 143 | nondecreasing:141, refused:2; self_intersection:2 |
| ladder_2_real | 1,2 | 6 | 19 | no_decreasing_step | 0.108319 → 0.0847914 | 1.73128 → 2.13673 | 18.8439 | (3.081, 29.766) | 246 / 227 | refused:216, nondecreasing:11; self_intersection:216 |
| ladder_3_real | 1,2,3 | 9 | 7 | no_decreasing_step | 0.0819803 → 0.0772697 | 2.13673 → 2.14736 | 18.9736 | (3.233, 30.144) | 135 / 128 | refused:128; self_intersection:128 |
| ladder_4_real | 1,2,3,4 | 12 | 0 | no_decreasing_step | 0.0754287 → 0.0754287 | 2.14736 → 2.14736 | 18.9736 | (3.233, 30.144) | 40 / 40 | refused:40; self_intersection:40 |
| full_1_M11 | 1,2,3,4,5,6,7,8 | 11 | 13 | no_decreasing_step | 0.0996269 → 0.084057 | 2.14736 → 2.19373 | 19.045 | (2.983, 29.241) | 190 / 177 | refused:177; self_intersection:177 |
| full_2_M15 | 1,2,3,4,5,6,7,8 | 15 | 0 | no_decreasing_step | 0.084057 → 0.084057 | 2.19373 → 2.19373 | 19.045 | (2.983, 29.241) | 40 / 40 | refused:40; self_intersection:40 |
| full_3_M19 | 1,2,3,4,5,6,7,8 | 19 | 0 | no_decreasing_step | 0.084057 → 0.084057 | 2.19373 → 2.19373 | 19.045 | (2.983, 29.241) | 40 / 40 | refused:40; self_intersection:40 |
| full_4_M25 | 1,2,3,4,5,6,7,8 | 25 | 0 | no_decreasing_step | 0.0840431 → 0.0840431 | 2.19373 → 2.19373 | 19.0453 | (2.983, 29.241) | 40 / 40 | refused:40; self_intersection:40 |
| full_5_M31 | 1,2,3,4,5,6,7,8 | 31 | 0 | no_decreasing_step | 0.0840431 → 0.0840431 | 2.19373 → 2.19373 | 19.0453 | (2.983, 29.241) | 40 / 40 | refused:40; self_intersection:40 |
| full_6_M37 | 1,2,3,4,5,6,7,8 | 37 | 0 | no_decreasing_step | 0.0840431 → 0.0840431 | 2.19373 → 2.19373 | 19.0453 | (2.983, 29.241) | 40 / 40 | refused:40; self_intersection:38, irregular_parameterization:2 |

## warmup / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/warmup/dielTM_dec8f/cuda/attempt_01`. Outcome: None. Last saved stage: ladder_2_real.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| warmup_1GHz_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.0860223 → 0.0860099 | 32.5689 → 32.6194 | 3.21116 | (2.216, 32.397) | 266 / 244 | refused:29, nondecreasing:215; irregular_parameterization:13, self_intersection:16 |
| ladder_2_real | 1,2 | 6 | 13 | no_decreasing_step | 0.0826144 → 0.0617784 | 32.6194 → 31.6861 | 3.32505 | (1.560, 31.321) | 194 / 181 | refused:169, nondecreasing:12; self_intersection:168, irregular_parameterization:1 |

## warmup / attempt_02

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/warmup/dielTM_dec8f/cuda/attempt_02`. Outcome: TRIAL_WALL_LIMIT. Last saved stage: full_1_M11.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| warmup_1GHz_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.0860223 → 0.0860099 | 32.5689 → 32.6194 | 3.21116 | (2.216, 32.397) | 266 / 244 | refused:29, nondecreasing:215; irregular_parameterization:13, self_intersection:16 |
| ladder_2_real | 1,2 | 6 | 13 | no_decreasing_step | 0.0826144 → 0.0617784 | 32.6194 → 31.6861 | 3.32505 | (1.560, 31.321) | 194 / 181 | refused:169, nondecreasing:12; self_intersection:168, irregular_parameterization:1 |
| ladder_3_real | 1,2,3 | 9 | 11 | no_decreasing_step | 0.120449 → 0.0878197 | 31.6861 → 32.1123 | 3.33819 | (1.809, 31.212) | 190 / 179 | refused:179; self_intersection:176, irregular_parameterization:3 |
| ladder_4_real | 1,2,3,4 | 12 | 6 | no_decreasing_step | 0.110681 → 0.109307 | 32.1123 → 32.1075 | 3.33652 | (1.809, 31.226) | 131 / 125 | refused:125; self_intersection:125 |
| full_1_M11 | 1,2,3,4,5,6,7,8 | 11 | 6 | TRIAL_WALL_LIMIT | 0.207791 → 0.206605 | 32.1075 → 32.0756 | 3.33575 | (1.800, 31.218) | 128 / 121 | refused:121, unresolved:1; self_intersection:121 |

## first_cap / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/first_cap/dielTM_dec8f/cuda/attempt_01`. Outcome: COMPLETED_SCHEDULE. Last saved stage: full_10_M61.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| ladder_1_real | 1 | 3 | 101 | STAGE_QUOTA_REACHED | 0.227804 → 0.0870056 | 1.0931 → 3.56784 | 11.9408 | (1.924, 32.611) | 799 / 697 | nondecreasing:682, refused:15, unresolved:1; self_intersection:9, irregular_parameterization:6 |
| ladder_2_real | 1,2 | 6 | 22 | maximum_iterations | 0.0693294 → 0.0561632 | 3.56784 → 4.21795 | 11.1096 | (2.869, 28.187) | 185 / 163 | refused:26, nondecreasing:137; self_intersection:25, irregular_parameterization:1 |
| ladder_3_real | 1,2,3 | 9 | 22 | maximum_iterations | 0.0455332 → 0.0433122 | 4.21795 → 4.54239 | 10.6029 | (2.328, 27.539) | 217 / 195 | refused:138, nondecreasing:57; irregular_parameterization:2, self_intersection:136 |
| ladder_4_real | 1,2,3,4 | 12 | 9 | no_decreasing_step | 0.0426255 → 0.040467 | 4.54239 → 4.68552 | 10.7905 | (2.529, 27.779) | 157 / 148 | refused:147, nondecreasing:1; self_intersection:147 |
| full_1_M11 | 1,2,3,4,5,6,7,8 | 11 | 5 | no_decreasing_step | 0.0726255 → 0.0434477 | 4.68552 → 3.79333 | 12.7874 | (2.197, 27.096) | 61 / 56 | refused:56; self_intersection:56 |
| full_2_M15 | 1,2,3,4,5,6,7,8 | 15 | 3 | no_decreasing_step | 0.0434477 → 0.0434043 | 3.79333 → 3.79332 | 12.7876 | (2.197, 27.094) | 87 / 84 | refused:84; self_intersection:84 |
| full_3_M19 | 1,2,3,4,5,6,7,8 | 19 | 9 | no_decreasing_step | 0.0434043 → 0.0428883 | 3.79332 → 3.79299 | 12.7885 | (2.191, 27.063) | 160 / 151 | refused:151; self_intersection:151 |
| full_4_M25 | 1,2,3,4,5,6,7,8 | 25 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |
| full_5_M31 | 1,2,3,4,5,6,7,8 | 31 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |
| full_6_M37 | 1,2,3,4,5,6,7,8 | 37 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |
| full_7_M43 | 1,2,3,4,5,6,7,8 | 43 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; irregular_parameterization:2, self_intersection:38 |
| full_8_M49 | 1,2,3,4,5,6,7,8 | 49 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |
| full_9_M55 | 1,2,3,4,5,6,7,8 | 55 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |
| full_10_M61 | 1,2,3,4,5,6,7,8 | 61 | 0 | no_decreasing_step | 0.0428901 → 0.0428901 | 3.79299 → 3.79299 | 12.7872 | (2.188, 27.063) | 40 / 40 | refused:40; self_intersection:40 |

First-stage prefix: incomplete or different; 23 states compared.

## circle_ladder / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/circle_ladder/dielTM_dec8f/cuda/attempt_01`. Outcome: COMPLETED_SCHEDULE. Last saved stage: full_6_M37.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| circle_1_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| circle_2_real | 1,2 | 1 | 13 | no_decreasing_step | 0.0836046 → 0.0506795 | 32.5689 → 9.04287 | 6.51512 | (1.926, 27.223) | 49 / 36 | nondecreasing:36 |
| circle_3_real | 1,2,3 | 1 | 11 | no_decreasing_step | 0.0691289 → 0.0436721 | 9.04287 → 3.83208 | 11.8153 | (1.971, 26.932) | 27 / 16 | nondecreasing:16 |
| circle_4_real | 1,2,3,4 | 1 | 9 | no_decreasing_step | 0.0442809 → 0.0410357 | 3.83208 → 3.47071 | 13.2231 | (1.943, 26.582) | 9 / 0 |  |
| circle_full_real | 1,2,3,4,5,6,7,8 | 1 | 14 | no_decreasing_step | 0.0459027 → 0.037549 | 3.47071 → 3.05254 | 15.2663 | (1.939, 26.191) | 14 / 0 |  |
| full_1_M11 | 1,2,3,4,5,6,7,8 | 11 | 12 | STAGE_QUOTA_REACHED | 0.037549 → 0.0375472 | 3.05254 → 3.05253 | 15.2659 | (1.939, 26.192) | 168 / 155 | nondecreasing:147, refused:8, unresolved:1; self_intersection:8 |
| full_2_M15 | 1,2,3,4,5,6,7,8 | 15 | 14 | STAGE_QUOTA_REACHED | 0.0375472 → 0.037544 | 3.05253 → 3.05245 | 15.2664 | (1.940, 26.192) | 165 / 150 | refused:9, nondecreasing:141, unresolved:1; self_intersection:9 |
| full_3_M19 | 1,2,3,4,5,6,7,8 | 19 | 14 | STAGE_QUOTA_REACHED | 0.037544 → 0.0375388 | 3.05245 → 3.05178 | 15.2765 | (1.945, 26.190) | 164 / 149 | refused:8, nondecreasing:141, unresolved:1; self_intersection:8 |
| full_4_M25 | 1,2,3,4,5,6,7,8 | 25 | 1 | STAGE_QUOTA_REACHED | 0.0375388 → 0.0375385 | 3.05178 → 3.05177 | 15.2765 | (1.945, 26.190) | 39 / 37 | refused:7, nondecreasing:30, unresolved:1; irregular_parameterization:3, self_intersection:4 |
| full_5_M31 | 1,2,3,4,5,6,7,8 | 31 | 1 | STAGE_QUOTA_REACHED | 0.0375385 → 0.0375383 | 3.05177 → 3.05177 | 15.2765 | (1.945, 26.190) | 40 / 38 | refused:8, nondecreasing:30, unresolved:1; irregular_parameterization:3, self_intersection:5 |
| full_6_M37 | 1,2,3,4,5,6,7,8 | 37 | 1 | STAGE_QUOTA_REACHED | 0.0375383 → 0.0375382 | 3.05177 → 3.05177 | 15.2764 | (1.945, 26.190) | 41 / 39 | refused:9, nondecreasing:30, unresolved:1; irregular_parameterization:4, self_intersection:5 |

## circle_then_ladder / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/circle_then_ladder/dielTM_dec8f/cuda/attempt_01`. Outcome: TRIAL_WALL_LIMIT. Last saved stage: full_4_M25.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| circle_1_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| circle_2_real | 1,2 | 1 | 13 | no_decreasing_step | 0.0836046 → 0.0506795 | 32.5689 → 9.04287 | 6.51512 | (1.926, 27.223) | 49 / 36 | nondecreasing:36 |
| circle_3_real | 1,2,3 | 1 | 11 | no_decreasing_step | 0.0691289 → 0.0436721 | 9.04287 → 3.83208 | 11.8153 | (1.971, 26.932) | 27 / 16 | nondecreasing:16 |
| circle_4_real | 1,2,3,4 | 1 | 9 | no_decreasing_step | 0.0442809 → 0.0410357 | 3.83208 → 3.47071 | 13.2231 | (1.943, 26.582) | 9 / 0 |  |
| circle_full_real | 1,2,3,4,5,6,7,8 | 1 | 14 | no_decreasing_step | 0.0459027 → 0.037549 | 3.47071 → 3.05254 | 15.2663 | (1.939, 26.191) | 14 / 0 |  |
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.139479 → 0.0867727 | 3.05254 → 4.16169 | 10.6784 | (2.155, 32.072) | 176 / 154 | refused:7, nondecreasing:147; self_intersection:5, irregular_parameterization:2 |
| ladder_2_real | 1,2 | 6 | 14 | no_decreasing_step | 0.0648638 → 0.0569827 | 4.16169 → 4.73569 | 10.1987 | (3.057, 27.957) | 191 / 177 | refused:137, nondecreasing:40; self_intersection:137 |
| ladder_3_real | 1,2,3 | 9 | 0 | no_decreasing_step | 0.0459085 → 0.0459085 | 4.73569 → 4.73569 | 10.1987 | (3.057, 27.957) | 40 / 40 | refused:34, nondecreasing:6; self_intersection:34 |
| ladder_4_real | 1,2,3,4 | 12 | 9 | no_decreasing_step | 0.05255 → 0.0466895 | 4.73569 → 4.76214 | 10.2847 | (2.762, 27.477) | 153 / 144 | refused:144; self_intersection:144 |
| full_1_M11 | 1,2,3,4,5,6,7,8 | 11 | 0 | no_decreasing_step | 0.0824956 → 0.0824956 | 4.76214 → 4.76214 | 10.2847 | (2.762, 27.477) | 40 / 40 | refused:40; self_intersection:40 |
| full_2_M15 | 1,2,3,4,5,6,7,8 | 15 | 0 | no_decreasing_step | 0.0824956 → 0.0824956 | 4.76214 → 4.76214 | 10.2847 | (2.762, 27.477) | 40 / 40 | refused:40; self_intersection:40 |
| full_3_M19 | 1,2,3,4,5,6,7,8 | 19 | 9 | no_decreasing_step | 0.0824956 → 0.0772293 | 4.76214 → 4.76155 | 10.3411 | (2.756, 27.475) | 147 / 138 | refused:138; self_intersection:138 |
| full_4_M25 | 1,2,3,4,5,6,7,8 | 25 | 0 | TRIAL_WALL_LIMIT | pending → pending | 4.76155 → 4.76155 | 10.3411 | (2.756, 27.475) | 0 / 0 |  |

## frontier_capped / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/frontier_capped/dielTM_dec8f/cuda/attempt_01`. Outcome: NUMERICAL_FAILURE. Last saved stage: ladder_4_real.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| warmup_1GHz_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| ladder_1_real | 1 | 1 | 22 | maximum_iterations | 0.0860223 → 0.0859664 | 32.5689 → 118.6 | 1.62215 | (2.191, 32.323) | 122 / 100 | nondecreasing:100 |
| ladder_2_real | 1,2 | 1 | 22 | maximum_iterations | 0.168944 → 0.0506818 | 118.6 → 9.03539 | 6.51233 | (1.926, 27.215) | 129 / 107 | nondecreasing:107 |
| ladder_3_real | 1,2,3 | 3 | 17 | no_decreasing_step | 0.0689586 → 0.0417031 | 9.03539 → 13.7285 | 5.50989 | (2.046, 26.976) | 139 / 122 | nondecreasing:94, refused:28; self_intersection:28 |
| ladder_4_real | 1,2,3,4 | 10 | 1 | NUMERICAL_FAILURE | 0.0453633 → 0.0452882 | 13.7285 → 13.7258 | 5.51145 | (2.046, 26.974) | 18 / 17 | refused:11, nondecreasing:5, physics_failed:1; self_intersection:11 |

## frontier_measured / attempt_01

Evidence: `results/bem/baseline_data/measured_schedule/2026-11-19/frontier_measured/dielTM_dec8f/cuda/attempt_01`. Outcome: None. Last saved stage: ladder_4_real.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
| warmup_1GHz_real | 1 | 1 | 44 | maximum_iterations | 0.227804 → 0.0860223 | 1.0931 → 32.5689 | 3.205 | (2.191, 32.323) | 232 / 188 | nondecreasing:188 |
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.0860223 → 0.0860099 | 32.5689 → 32.6194 | 3.21116 | (2.216, 32.397) | 266 / 244 | refused:29, nondecreasing:215; irregular_parameterization:13, self_intersection:16 |
| ladder_2_real | 1,2 | 6 | 13 | no_decreasing_step | 0.0826144 → 0.0617784 | 32.6194 → 31.6861 | 3.32505 | (1.560, 31.321) | 194 / 181 | refused:169, nondecreasing:12; self_intersection:168, irregular_parameterization:1 |
| ladder_3_real | 1,2,3 | 9 | 11 | no_decreasing_step | 0.120449 → 0.0878197 | 31.6861 → 32.1123 | 3.33819 | (1.809, 31.212) | 190 / 179 | refused:179; self_intersection:176, irregular_parameterization:3 |
| ladder_4_real | 1,2,3,4 | 12 | 6 | no_decreasing_step | 0.110681 → 0.109307 | 32.1123 → 32.1075 | 3.33652 | (1.809, 31.226) | 131 / 125 | refused:125; self_intersection:125 |

## best exact circle / diagnostic

Evidence: `results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json`. Outcome: DIAGNOSTIC. Last saved stage: None.

| Stage | GHz | Band | Steps | Stop | Loss in → out | Material in → out | Radius mm | Centre mm | Trials / nonaccepted | Refusal statuses |
|---|---|---:|---:|---|---|---|---:|---|---|---|
