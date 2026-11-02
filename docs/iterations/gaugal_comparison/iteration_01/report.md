# BEM and GauGal on TG-002 — 30-case comparison

Generated 2026-11-02 05:46:17 GMT.

**All cases attempted:** GauGal outcomes for 30/30 cases. Failed and time-limited outcomes are retained.

Three separate arms use the same noiseless TG-002 real-frequency observations and geometry. BEM with supplied contrast knows the true contrast. BEM material recovery and GauGal estimate it. BEM also uses damped-frequency continuation data; GauGal uses the 19 real frequencies only.

The [frozen TG-002 benchmark](../../../../experiments/benchmark/README.md) supplies ten shapes at contrasts 0.5, 4 and 13.3 in a background of relative permittivity 6. The real frequencies span 0.25–2.5 GHz; all starts and measurement data are retained.

## Aggregate results

| Arm | Saved images | Finite boundaries | Shared shape/field limits | Full BEM recovery | Median RMS mm | Median image RRMSE | Median recorded seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| BEM: supplied contrast | 30 | 30 | 26 | 26 | 0.00336 | 0.000946 | 14.1 |
| BEM: recovered contrast | 30 | 30 | 26 | 23 | 0.00721 | 0.00122 | 18.3 |
| GauGal | 30 | 29 | 0 | not applicable | 25.2 | 0.277 | 340 |

Shared limits are RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm and maximum relative field residual ≤ 0.003. Full BEM recovery additionally requires its independent final numerical checks. GauGal has no equivalent BEM Jacobian check; its shared-limit count is not claimed as full TG-002 numerical qualification.

### Results by contrast

| Contrast | Arm | Full BEM recovery | Shared limits met | Finite boundaries | Median RMS mm | Median max field residual | Median image RRMSE |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.5 | BEM: supplied contrast | 9 | 9/10 | 10/10 | 0.0077 | 1.7e-06 | 0.00066 |
| 0.5 | BEM: recovered contrast | 9 | 9/10 | 10/10 | 0.0118 | 3.39e-06 | 0.00101 |
| 0.5 | GauGal | not applicable | 0/10 | 10/10 | 2.01 | 0.203 | 0.0921 |
| 4 | BEM: supplied contrast | 9 | 9/10 | 10/10 | 0.00388 | 2.34e-06 | 0.00101 |
| 4 | BEM: recovered contrast | 9 | 10/10 | 10/10 | 0.004 | 1.73e-06 | 0.00104 |
| 4 | GauGal | not applicable | 0/10 | 9/10 | 40.4 | 1.01 | 0.298 |
| 13.3 | BEM: supplied contrast | 8 | 8/10 | 10/10 | 0.000888 | 1.13e-06 | 0.00133 |
| 13.3 | BEM: recovered contrast | 5 | 7/10 | 10/10 | 0.00465 | 2.07e-05 | 0.00281 |
| 13.3 | GauGal | not applicable | 0/10 | 10/10 | 28.3 | 1 | 0.365 |

Medians include unsuccessful outputs with finite scores. Missing contours contribute no boundary value; the finite-boundary counts show those exclusions.

![Errors across all cases](comparison_figures/errors.png)

## Per-case results

Triples below are **supplied-contrast BEM / material-recovery BEM / GauGal**. A dash means no finite value was available. Circle cases were used for GauGal tuning.

| Case | RMS mm | Maximum field residual | Image RRMSE | GauGal status / iterations |
|---|---|---|---|---|
| circle__c0.5 | 7.64e-06 / 7.56e-06 / 28.4 | 8.88e-08 / 6.12e-08 / 0.952 | 0 / 5.69e-10 / 0.351 | completed / 80 |
| circle__c4 | 1.06e-05 / 8.6e-06 / — | 6.25e-06 / 1.73e-06 / 1.05 | 0 / 6.44e-09 / 0.332 | completed / 80 |
| circle__c13.3 | 7.58e-06 / 7.6e-06 / 14.6 | 1.06e-07 / 4.62e-07 / 1.08 | 0 / 7.17e-11 / 0.412 | completed / 80 |
| kite__c0.5 | 0.0119 / 0.0124 / 1.91 | 3.55e-06 / 4.36e-06 / 0.0836 | 0.000737 / 0.000823 / 0.0687 | completed / 80 |
| kite__c4 | 0.0157 / 0.0178 / 35.2 | 1.7e-05 / 2e-05 / 1.01 | 0.00219 / 0.00248 / 0.212 | completed / 80 |
| kite__c13.3 | 0.0138 / 0.0145 / 25.7 | 3.79e-05 / 4.01e-05 / 1.02 | 0.00429 / 0.00429 / 0.258 | completed / 80 |
| peanut__c0.5 | 0.00242 / 0.00252 / 1.86 | 1.13e-07 / 1.16e-07 / 0.167 | 0.000444 / 0.000417 / 0.0825 | completed / 80 |
| peanut__c4 | 0.00151 / 0.00152 / 26.1 | 1.97e-07 / 2e-07 / 1.01 | 0.000547 / 0.000547 / 0.264 | completed / 80 |
| peanut__c13.3 | 0.00052 / 0.00145 / 14.4 | 9.86e-08 / 2.63e-07 / 0.997 | 0.001 / 0.00126 / 0.328 | completed / 80 |
| star__c0.5 | 0.0211 / 0.0214 / 2.38 | 7.15e-06 / 3.01e-06 / 0.31 | 0.00178 / 0.00176 / 0.12 | completed / 80 |
| star__c4 | 0.00374 / 0.00371 / 84.9 | 7.71e-07 / 7.83e-07 / 1.01 | 0.00109 / 0.00112 / 0.338 | completed / 80 |
| star__c13.3 | 0.00126 / 0.00111 / 44.7 | 3.22e-07 / 2.16e-07 / 1 | 0.00165 / 0.0016 / 0.42 | completed / 80 |
| asymmetric__c0.5 | 0.0112 / 0.0109 / 1.79 | 3.07e-06 / 3.77e-06 / 0.238 | 0.00096 / 0.000944 / 0.0915 | completed / 80 |
| asymmetric__c4 | 0.00402 / 0.00429 / 44 | 1.42e-06 / 1.72e-06 / 1.01 | 0.000931 / 0.000957 / 0.31 | completed / 80 |
| asymmetric__c13.3 | 0.00297 / 37 / 32.6 | 1.94e-06 / 1.68 / 1 | 0.00166 / 0.41 / 0.384 | completed / 80 |
| c_shape__c0.5 | 0.0026 / 0.00295 / 2.05 | 3.15e-07 / 3.9e-07 / 0.253 | 0.000402 / 0.000488 / 0.11 | completed / 80 |
| c_shape__c4 | 0.000883 / 0.000883 / 85.2 | 3e-07 / 3.26e-07 / 1.01 | 0.000492 / 0.000467 / 0.307 | completed / 80 |
| c_shape__c13.3 | 3.76e-05 / 4.79e-05 / 42.5 | 3.1e-06 / 1.27e-06 / 0.998 | 0 / 3.04e-08 / 0.378 | completed / 80 |
| hook__c0.5 | 0.00419 / 4.35 / 1.32 | 3.22e-07 / 1.49 / 0.135 | 0.000583 / 0.165 / 0.0928 | completed / 80 |
| hook__c4 | 0.00966 / 0.00657 / 25.2 | 8.69e-06 / 6.53e-06 / 1.01 | 0.00199 / 0.00139 / 0.264 | completed / 80 |
| hook__c13.3 | 0.00023 / 0.00103 / 31 | 3.19e-07 / 2.6e-07 / 1 | 0.000495 / 0.00117 / 0.324 | completed / 80 |
| cross__c0.5 | 0.00293 / 0.0113 / 1.97 | 2.55e-07 / 2.04e-06 / 0.169 | 0.0004 / 0.00107 / 0.0871 | completed / 80 |
| cross__c4 | 0.00202 / 0.00204 / 40.4 | 5.18e-07 / 5.06e-07 / 1.03 | 0.000681 / 0.000727 / 0.29 | completed / 80 |
| cross__c13.3 | 0.000148 / 34.5 / 95.5 | 1.02e-07 / 1.5 / 1.01 | 0.000169 / 0.364 / 0.352 | completed / 80 |
| cog__c0.5 | 0.0481 / 0.0486 / 2.24 | 9.21e-06 / 8.86e-06 / 0.315 | 0.00319 / 0.0032 / 0.0955 | completed / 80 |
| cog__c4 | 0.00841 / 0.00809 / 91.3 | 3.27e-06 / 3.3e-06 / 1.04 | 0.00172 / 0.00171 / 0.312 | completed / 80 |
| cog__c13.3 | 0.472 / 3.25 / 17.8 | 0.247 / 1.49 / 1.05 | 0.22 / 0.556 / 0.386 | completed / 80 |
| aphex_twin__c0.5 | 5.98 / 0.0683 / 2.63 | 1.75 / 7.24e-06 / 0.114 | 0.185 / 0.00426 / 0.0818 | completed / 80 |
| aphex_twin__c4 | 0.338 / 0.0791 / 19.2 | 0.0089 / 0.000967 / 0.963 | 0.0428 / 0.00914 / 0.186 | completed / 80 |
| aphex_twin__c13.3 | 2.53 / 0.00785 / 23.7 | 1.01 / 5.48e-05 / 1 | 1.09 / 0.00401 / 0.232 | completed / 80 |

## Complete scores for each arm

Contrast error is signed relative error in percent. PSNR and contrast SNR are in dB. Medians use available finite scores, including unsuccessful fits. Missing traces are excluded from boundary medians.

### BEM: supplied contrast

| Case | RMS mm | Hausdorff upper mm | Max field residual | Contrast | Error % | Seconds | Recovery |
|---|---:|---:|---:|---:|---:|---:|---|
| circle__c0.5 | 7.6351e-06 | 0.019182 | 8.8827e-08 | 0.5 | 0 | 4.0507 | recovered |
| circle__c4 | 1.0553e-05 | 0.019186 | 6.2533e-06 | 4 | 0 | 3.6229 | recovered |
| circle__c13.3 | 7.5772e-06 | 0.019183 | 1.0572e-07 | 13.3 | 0 | 3.6267 | recovered |
| kite__c0.5 | 0.011905 | 0.062689 | 3.5489e-06 | 0.5 | 0 | 42.744 | recovered |
| kite__c4 | 0.015742 | 0.061521 | 1.7029e-05 | 4 | 0 | 22.046 | recovered |
| kite__c13.3 | 0.013842 | 0.063791 | 3.7904e-05 | 13.3 | 0 | 19.866 | recovered |
| peanut__c0.5 | 0.0024189 | 0.025153 | 1.1305e-07 | 0.5 | 0 | 9.2165 | recovered |
| peanut__c4 | 0.0015076 | 0.023241 | 1.9701e-07 | 4 | 0 | 9.2364 | recovered |
| peanut__c13.3 | 0.00051964 | 0.021159 | 9.8607e-08 | 13.3 | 0 | 9.3341 | recovered |
| star__c0.5 | 0.02111 | 0.082501 | 7.1496e-06 | 0.5 | 0 | 11.026 | recovered |
| star__c4 | 0.003745 | 0.039061 | 7.708e-07 | 4 | 0 | 16.625 | recovered |
| star__c13.3 | 0.0012564 | 0.033455 | 3.2211e-07 | 13.3 | 0 | 24.286 | recovered |
| asymmetric__c0.5 | 0.011221 | 0.077695 | 3.0725e-06 | 0.5 | 0 | 12.895 | recovered |
| asymmetric__c4 | 0.0040238 | 0.0474 | 1.4161e-06 | 4 | 0 | 16.786 | recovered |
| asymmetric__c13.3 | 0.0029723 | 0.039926 | 1.9436e-06 | 13.3 | 0 | 19.538 | recovered |
| c_shape__c0.5 | 0.0025969 | 0.042908 | 3.1469e-07 | 0.5 | 0 | 9.0829 | recovered |
| c_shape__c4 | 0.00088267 | 0.035569 | 2.9963e-07 | 4 | 0 | 13.383 | recovered |
| c_shape__c13.3 | 3.7621e-05 | 0.03226 | 3.1017e-06 | 13.3 | 0 | 14.119 | recovered |
| hook__c0.5 | 0.0041876 | 0.047325 | 3.2174e-07 | 0.5 | 0 | 18.198 | recovered |
| hook__c4 | 0.0096599 | 0.07877 | 8.6892e-06 | 4 | 0 | 21.428 | recovered |
| hook__c13.3 | 0.00023022 | 0.037484 | 3.1913e-07 | 13.3 | 0 | 32.774 | recovered |
| cross__c0.5 | 0.0029326 | 0.035554 | 2.5503e-07 | 0.5 | 0 | 11.388 | recovered |
| cross__c4 | 0.0020205 | 0.031885 | 5.1774e-07 | 4 | 0 | 10.801 | recovered |
| cross__c13.3 | 0.00014842 | 0.027296 | 1.0154e-07 | 13.3 | 0 | 19.627 | recovered |
| cog__c0.5 | 0.048063 | 0.16651 | 9.2101e-06 | 0.5 | 0 | 14.099 | recovered |
| cog__c4 | 0.0084082 | 0.044898 | 3.2654e-06 | 4 | 0 | 13.007 | recovered |
| cog__c13.3 | 0.47189 | 1.3197 | 0.24744 | 13.3 | 0 | 55.39 | not recovered |
| aphex_twin__c0.5 | 5.975 | 15.419 | 1.7479 | 0.5 | 0 | 11.103 | not recovered |
| aphex_twin__c4 | 0.33837 | 1.2476 | 0.0089022 | 4 | 0 | 72.636 | not recovered |
| aphex_twin__c13.3 | 2.5335 | 11.245 | 1.0094 | 13.3 | 0 | 83.611 | not recovered |

| Case | RRMSE | SSIM | PSNR dB | Contrast SNR dB |
|---|---:|---:|---:|---:|
| circle__c0.5 | 0 | 1 | 300 | 272.9 |
| circle__c4 | 0 | 1 | 312.04 | 288.46 |
| circle__c13.3 | 0 | 1 | 322.48 | 300.72 |
| kite__c0.5 | 0.00073698 | 0.99999 | 65.263 | 47.811 |
| kite__c4 | 0.0021901 | 0.99998 | 59.541 | 45.61 |
| kite__c13.3 | 0.0042885 | 0.99998 | 58.667 | 46.556 |
| peanut__c0.5 | 0.00044431 | 1 | 70.804 | 55.466 |
| peanut__c4 | 0.00054709 | 1 | 70.707 | 58.89 |
| peanut__c13.3 | 0.0010048 | 1 | 72.866 | 62.87 |
| star__c0.5 | 0.0017825 | 0.99995 | 58.063 | 45.026 |
| star__c4 | 0.0010933 | 0.99999 | 65.048 | 55.533 |
| star__c13.3 | 0.001652 | 1 | 68.553 | 60.857 |
| asymmetric__c0.5 | 0.00096038 | 0.99999 | 63.365 | 49.579 |
| asymmetric__c4 | 0.00093119 | 1 | 66.361 | 56.097 |
| asymmetric__c13.3 | 0.0016568 | 1 | 64.354 | 55.91 |
| c_shape__c0.5 | 0.0004016 | 1 | 70.427 | 56.454 |
| c_shape__c4 | 0.00049188 | 1 | 72.134 | 61.683 |
| c_shape__c13.3 | 0 | 1 | 322.48 | 299.91 |
| hook__c0.5 | 0.00058261 | 0.99999 | 67.639 | 52.282 |
| hook__c4 | 0.001994 | 0.99998 | 59.959 | 48.124 |
| hook__c13.3 | 0.00049456 | 1 | 79.856 | 69.841 |
| cross__c0.5 | 0.00040032 | 1 | 70.574 | 55.934 |
| cross__c4 | 0.00068055 | 1 | 69.246 | 58.128 |
| cross__c13.3 | 0.00016871 | 1 | 79.856 | 70.558 |
| cog__c0.5 | 0.0031901 | 0.99985 | 53.001 | 39.201 |
| cog__c4 | 0.0017188 | 0.99999 | 61.145 | 50.867 |
| cog__c13.3 | 0.21952 | 0.98589 | 28.786 | 20.327 |
| aphex_twin__c0.5 | 0.18533 | 0.90269 | 18.663 | 0.1548 |
| aphex_twin__c4 | 0.042775 | 0.9936 | 33.828 | 18.842 |
| aphex_twin__c13.3 | 1.0885 | 0.94046 | 19.565 | 6.3984 |

### BEM: supplied contrast: per-case stopping and failure reasons

| Case | Recorded stop | Observed reason / remaining failure | Saved evidence |
|---|---|---|---|
| circle__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c0.5/final_audit.json) |
| circle__c4 | COMPLETED_SCHEDULE; fixed_M37: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c4/final_audit.json) |
| circle__c13.3 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/circle__c13.3/final_audit.json) |
| kite__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c0.5/final_audit.json) |
| kite__c4 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c4/final_audit.json) |
| kite__c13.3 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/kite__c13.3/final_audit.json) |
| peanut__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c0.5/final_audit.json) |
| peanut__c4 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c4/final_audit.json) |
| peanut__c13.3 | COMPLETED_SCHEDULE; fixed_M49: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/peanut__c13.3/final_audit.json) |
| star__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c0.5/final_audit.json) |
| star__c4 | COMPLETED_SCHEDULE; fixed_M55: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c4/final_audit.json) |
| star__c13.3 | COMPLETED_SCHEDULE; fixed_M85: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/star__c13.3/final_audit.json) |
| asymmetric__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c0.5/final_audit.json) |
| asymmetric__c4 | COMPLETED_SCHEDULE; fixed_M49: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c4/final_audit.json) |
| asymmetric__c13.3 | COMPLETED_SCHEDULE; fixed_M55: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/asymmetric__c13.3/final_audit.json) |
| c_shape__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c0.5/final_audit.json) |
| c_shape__c4 | COMPLETED_SCHEDULE; fixed_M43: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c4/final_audit.json) |
| c_shape__c13.3 | COMPLETED_SCHEDULE; fixed_M67: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/c_shape__c13.3/final_audit.json) |
| hook__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap/runs/hook__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap/runs/hook__c0.5/final_audit.json) |
| hook__c4 | COMPLETED_SCHEDULE; fixed_M43: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/hook__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/hook__c4/final_audit.json) |
| hook__c13.3 | COMPLETED_SCHEDULE; fixed_M67: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/hook__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/hook__c13.3/final_audit.json) |
| cross__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c0.5/final_audit.json) |
| cross__c4 | COMPLETED_SCHEDULE; fixed_M43: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c4/final_audit.json) |
| cross__c13.3 | COMPLETED_SCHEDULE; fixed_M61: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cross__c13.3/final_audit.json) |
| cog__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c0.5/final_audit.json) |
| cog__c4 | COMPLETED_SCHEDULE; fixed_M49: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c4/final_audit.json) |
| cog__c13.3 | NUMERICAL_FAILURE; fixed_M73: production evaluation failed at candidate state | fixed_M73: \|W\|^2 lower bound not certified (coefficient residual 1.41).; field refinement discrepancy at 16 frequencies; worst tolerance ratio 1.802e+04 at 2.5 GHz; Jacobian discrepancy 0.003822 > 0.001; maximum field residual 0.2474 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/cog__c13.3/final_audit.json) |
| aphex_twin__c0.5 | NUMERICAL_FAILURE; stage_3_damped: production evaluation failed at candidate state | stage_3_damped: \|W\|^2 lower bound not certified (coefficient residual 1.98).; RMS (mm) 5.975 > 1; Hausdorff upper bound (mm) 15.42 > 2; maximum field residual 1.748 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap/runs/aphex_twin__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S3_slider_no_log_cap/runs/aphex_twin__c0.5/final_audit.json) |
| aphex_twin__c4 | NUMERICAL_FAILURE; fixed_M43: production evaluation failed at candidate state | fixed_M43: \|W\|^2 lower bound not certified (coefficient residual 2.04).; field refinement discrepancy at 16 frequencies; worst tolerance ratio 4001 at 2.375 GHz; Jacobian discrepancy 0.002837 > 0.001; maximum field residual 0.008902 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/aphex_twin__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/aphex_twin__c4/final_audit.json) |
| aphex_twin__c13.3 | NUMERICAL_FAILURE; fixed_M37: production evaluation failed at candidate state | fixed_M37: \|W\|^2 lower bound not certified (coefficient residual 2.79).; field refinement discrepancy at 17 frequencies; worst tolerance ratio 1.02e+04 at 2.375 GHz; Jacobian discrepancy 0.002073 > 0.001; RMS (mm) 2.533 > 1; Hausdorff upper bound (mm) 11.24 > 2; maximum field residual 1.009 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/aphex_twin__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S1_slider_known_contrast/runs/aphex_twin__c13.3/final_audit.json) |

### BEM: recovered contrast

| Case | RMS mm | Hausdorff upper mm | Max field residual | Contrast | Error % | Seconds | Recovery |
|---|---:|---:|---:|---:|---:|---:|---|
| circle__c0.5 | 7.557e-06 | 0.019182 | 6.1177e-08 | 0.5 | 1.2969e-07 | 4.9469 | recovered |
| circle__c4 | 8.6016e-06 | 0.019185 | 1.7308e-06 | 4 | 1.4577e-06 | 4.9931 | recovered |
| circle__c13.3 | 7.6031e-06 | 0.019189 | 4.6182e-07 | 13.3 | -1.6183e-08 | 6.4336 | not recovered |
| kite__c0.5 | 0.012421 | 0.060949 | 4.3611e-06 | 0.5 | -4.5099e-06 | 39.356 | recovered |
| kite__c4 | 0.01778 | 0.066155 | 1.9985e-05 | 4 | 3.3311e-06 | 27.063 | recovered |
| kite__c13.3 | 0.014459 | 0.064113 | 4.0118e-05 | 13.3 | 0.00024524 | 33.296 | recovered |
| peanut__c0.5 | 0.0025157 | 0.025137 | 1.1634e-07 | 0.5 | -9.3738e-07 | 10.703 | recovered |
| peanut__c4 | 0.0015247 | 0.023251 | 1.9976e-07 | 4 | 1.9989e-07 | 12.456 | recovered |
| peanut__c13.3 | 0.0014521 | 0.029043 | 2.627e-07 | 13.3 | 2.2655e-07 | 20.671 | recovered |
| star__c0.5 | 0.021437 | 0.076615 | 3.0081e-06 | 0.5 | -0.00017629 | 12.488 | recovered |
| star__c4 | 0.0037079 | 0.039088 | 7.8274e-07 | 4 | 1.803e-06 | 21.228 | recovered |
| star__c13.3 | 0.0011119 | 0.033382 | 2.1558e-07 | 13.3 | 3.4153e-08 | 40.625 | recovered |
| asymmetric__c0.5 | 0.010946 | 0.07584 | 3.773e-06 | 0.5 | -7.1956e-06 | 14.733 | recovered |
| asymmetric__c4 | 0.0042938 | 0.04326 | 1.7206e-06 | 4 | 2.4972e-06 | 21.769 | recovered |
| asymmetric__c13.3 | 36.985 | 54.923 | 1.6751 | 123.28 | 826.91 | 5.9135 | not recovered |
| c_shape__c0.5 | 0.0029499 | 0.045161 | 3.8967e-07 | 0.5 | -5.1701e-07 | 13.914 | recovered |
| c_shape__c4 | 0.00088326 | 0.034739 | 3.2621e-07 | 4 | 2.0815e-07 | 17.72 | recovered |
| c_shape__c13.3 | 4.787e-05 | 0.033403 | 1.2685e-06 | 13.3 | 7.4919e-06 | 35.124 | recovered |
| hook__c0.5 | 4.3534 | 13.157 | 1.4936 | 0.47692 | -4.6167 | 2.4785 | not recovered |
| hook__c4 | 0.0065729 | 0.062228 | 6.5299e-06 | 4 | 4.4146e-06 | 27.677 | recovered |
| hook__c13.3 | 0.0010256 | 0.039539 | 2.6012e-07 | 13.3 | 1.5138e-06 | 53.683 | recovered |
| cross__c0.5 | 0.011251 | 0.04315 | 2.0432e-06 | 0.5 | -5.0962e-05 | 10.96 | recovered |
| cross__c4 | 0.0020387 | 0.027965 | 5.0584e-07 | 4 | 2.7749e-06 | 15.349 | recovered |
| cross__c13.3 | 34.539 | 70.935 | 1.5032 | 73.617 | 453.51 | 11.69 | not recovered |
| cog__c0.5 | 0.048614 | 0.18648 | 8.8621e-06 | 0.5 | -5.0505e-05 | 16.568 | recovered |
| cog__c4 | 0.0080867 | 0.046764 | 3.2976e-06 | 4 | -7.3368e-06 | 18.869 | recovered |
| cog__c13.3 | 3.2524 | 9.536 | 1.4882 | 14.926 | 12.225 | 46.286 | not recovered |
| aphex_twin__c0.5 | 0.06834 | 0.25742 | 7.2365e-06 | 0.49996 | -0.0080435 | 47.974 | recovered |
| aphex_twin__c4 | 0.079134 | 0.35914 | 0.00096687 | 4 | 0.00091084 | 89.921 | not recovered |
| aphex_twin__c13.3 | 0.007852 | 0.057345 | 5.476e-05 | 13.3 | 0.00011806 | 83.491 | not recovered |

| Case | RRMSE | SSIM | PSNR dB | Contrast SNR dB |
|---|---:|---:|---:|---:|
| circle__c0.5 | 5.6871e-10 | 1 | 190.9 | 177.74 |
| circle__c4 | 6.4371e-09 | 1 | 163.87 | 154.23 |
| circle__c13.3 | 7.1731e-11 | 1 | 202.96 | 195.14 |
| kite__c0.5 | 0.00082315 | 0.99999 | 64.442 | 46.99 |
| kite__c4 | 0.0024814 | 0.99997 | 58.002 | 44.072 |
| kite__c13.3 | 0.0042858 | 0.99998 | 58.553 | 46.442 |
| peanut__c0.5 | 0.00041735 | 1 | 71.132 | 55.794 |
| peanut__c4 | 0.00054709 | 1 | 70.707 | 58.89 |
| peanut__c13.3 | 0.0012617 | 1 | 69.644 | 59.647 |
| star__c0.5 | 0.0017614 | 0.99995 | 58.156 | 45.119 |
| star__c4 | 0.0011225 | 0.99999 | 64.909 | 55.394 |
| star__c13.3 | 0.0016012 | 1 | 69.644 | 61.949 |
| asymmetric__c0.5 | 0.00094374 | 0.99999 | 63.481 | 49.695 |
| asymmetric__c4 | 0.00095665 | 1 | 66.624 | 56.36 |
| asymmetric__c13.3 | 0.4103 | 0.17782 | 7.8197 | -0.62463 |
| c_shape__c0.5 | 0.00048795 | 1 | 69.017 | 55.045 |
| c_shape__c4 | 0.00046729 | 1 | 73.547 | 63.096 |
| c_shape__c13.3 | 3.0424e-08 | 1 | 150.46 | 141.83 |
| hook__c0.5 | 0.16523 | 0.89554 | 19.678 | 4.3208 |
| hook__c4 | 0.001394 | 0.99999 | 63.133 | 51.298 |
| hook__c13.3 | 0.0011697 | 1 | 70.079 | 60.064 |
| cross__c0.5 | 0.0010677 | 0.99998 | 62.144 | 47.505 |
| cross__c4 | 0.00072654 | 1 | 68.776 | 57.658 |
| cross__c13.3 | 0.36404 | 0.29423 | 8.8756 | -0.42225 |
| cog__c0.5 | 0.0031964 | 0.99984 | 52.879 | 39.079 |
| cog__c4 | 0.0017087 | 0.99999 | 61.342 | 51.064 |
| cog__c13.3 | 0.5557 | 0.90845 | 16.884 | 8.4253 |
| aphex_twin__c0.5 | 0.0042648 | 0.99971 | 50.116 | 31.608 |
| aphex_twin__c4 | 0.0091449 | 0.99962 | 46.154 | 31.168 |
| aphex_twin__c13.3 | 0.004014 | 0.99999 | 60.314 | 47.147 |

### BEM: recovered contrast: per-case stopping and failure reasons

| Case | Recorded stop | Observed reason / remaining failure | Saved evidence |
|---|---|---|---|
| circle__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c0.5/final_audit.json) |
| circle__c4 | COMPLETED_SCHEDULE; fixed_M37: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c4/final_audit.json) |
| circle__c13.3 | COMPLETED_SCHEDULE; fixed_M37: no_decreasing_step | Jacobian discrepancy 0.002607 > 0.001; contrast start 1.729, warm-up end 8.966, final 13.3; truth 13.3 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/circle__c13.3/final_audit.json) |
| kite__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c0.5/final_audit.json) |
| kite__c4 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c4/final_audit.json) |
| kite__c13.3 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/kite__c13.3/final_audit.json) |
| peanut__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c0.5/final_audit.json) |
| peanut__c4 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c4/final_audit.json) |
| peanut__c13.3 | COMPLETED_SCHEDULE; fixed_M49: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/peanut__c13.3/final_audit.json) |
| star__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c0.5/final_audit.json) |
| star__c4 | COMPLETED_SCHEDULE; fixed_M55: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c4/final_audit.json) |
| star__c13.3 | COMPLETED_SCHEDULE; fixed_M85: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/star__c13.3/final_audit.json) |
| asymmetric__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c0.5/final_audit.json) |
| asymmetric__c4 | COMPLETED_SCHEDULE; fixed_M49: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c4/final_audit.json) |
| asymmetric__c13.3 | NUMERICAL_FAILURE; stage_1_damped: production evaluation failed at candidate state | stage_1_damped: \|W\|^2 lower bound not certified (coefficient residual 1.22).; field refinement discrepancy at 16 frequencies; worst tolerance ratio 337.6 at 2.375 GHz; RMS (mm) 36.99 > 1; Hausdorff upper bound (mm) 54.92 > 2; maximum field residual 1.675 > 0.003; contrast start 1.454, warm-up end 120.9, final 123.3; truth 13.3 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/asymmetric__c13.3/final_audit.json) |
| c_shape__c0.5 | COMPLETED_SCHEDULE; fixed_M37: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c0.5/final_audit.json) |
| c_shape__c4 | COMPLETED_SCHEDULE; fixed_M43: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c4/final_audit.json) |
| c_shape__c13.3 | COMPLETED_SCHEDULE; fixed_M67: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/c_shape__c13.3/final_audit.json) |
| hook__c0.5 | NUMERICAL_FAILURE; stage_2_damped: production evaluation failed at candidate state | stage_2_damped: log\|W\|^2 needs more than 4000 Chebyshev terms (beta/Lambda=1.34e-05); curve is nearly self-touching.; RMS (mm) 4.353 > 1; Hausdorff upper bound (mm) 13.16 > 2; maximum field residual 1.494 > 0.003; contrast start 0.8191, warm-up end 0.7333, final 0.4769; truth 0.5 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c0.5/final_audit.json) |
| hook__c4 | COMPLETED_SCHEDULE; fixed_M43: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c4/final_audit.json) |
| hook__c13.3 | COMPLETED_SCHEDULE; fixed_M67: loss_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/hook__c13.3/final_audit.json) |
| cross__c0.5 | COMPLETED_SCHEDULE; fixed_M37: gradient_tolerance | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c0.5/final_audit.json) |
| cross__c4 | COMPLETED_SCHEDULE; fixed_M43: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c4/final_audit.json) |
| cross__c13.3 | NUMERICAL_FAILURE; stage_2_damped: production evaluation failed at candidate state | stage_2_damped: log\|W\|^2 needs more than 4000 Chebyshev terms (beta/Lambda=1.02e-05); curve is nearly self-touching.; field refinement discrepancy at 16 frequencies; worst tolerance ratio 890.1 at 1.375 GHz; RMS (mm) 34.54 > 1; Hausdorff upper bound (mm) 70.93 > 2; maximum field residual 1.503 > 0.003; contrast start 1.212, warm-up end 241.7, final 73.62; truth 13.3 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cross__c13.3/final_audit.json) |
| cog__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c0.5/final_audit.json) |
| cog__c4 | COMPLETED_SCHEDULE; fixed_M49: no_decreasing_step | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c4/final_audit.json) |
| cog__c13.3 | NUMERICAL_FAILURE; release_M15: production evaluation failed at candidate state | release_M15: \|W\|^2 lower bound not certified (coefficient residual 1.76).; field refinement discrepancy at 18 frequencies; worst tolerance ratio 1.366e+04 at 2.5 GHz; Jacobian discrepancy 0.002978 > 0.001; full-trial finite-difference discrepancy 0.007446 > 0.001; RMS (mm) 3.252 > 1; Hausdorff upper bound (mm) 9.536 > 2; maximum field residual 1.488 > 0.003; contrast start 1.393, warm-up end 169.1, final 14.93; truth 13.3 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/cog__c13.3/final_audit.json) |
| aphex_twin__c0.5 | COMPLETED_SCHEDULE; fixed_M37: next complete batch and endpoint reserve exceed the stage quota | None: all TG-002 recovery checks passed. | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c0.5/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c0.5/final_audit.json) |
| aphex_twin__c4 | COMPLETED_SCHEDULE; fixed_M79: next complete batch and endpoint reserve exceed the stage quota | field refinement discrepancy at 16 frequencies; worst tolerance ratio 623.8 at 2.375 GHz; Jacobian discrepancy 0.002654 > 0.001; contrast start 1.501, warm-up end 2.675, final 4; truth 4 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c4/final_audit.json) |
| aphex_twin__c13.3 | COMPLETED_SCHEDULE; fixed_M73: next complete batch and endpoint reserve exceed the stage quota | field refinement discrepancy at 13 frequencies; worst tolerance ratio 13.37 at 2.5 GHz; Jacobian discrepancy 0.004618 > 0.001; contrast start 1.52, warm-up end 13.48, final 13.3; truth 13.3 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S2_slider_material_weak_start/runs/aphex_twin__c13.3/final_audit.json) |

### GauGal

| Case | RMS mm | Hausdorff upper mm | Max field residual | Contrast | Error % | Seconds | Recovery |
|---|---:|---:|---:|---:|---:|---:|---|
| circle__c0.5 | 28.391 | 77.719 | 0.95198 | 0.83749 | 67.498 | 341.39 | shared limits not met |
| circle__c4 | — | — | 1.0545 | — | — | 331.95 | shared limits not met |
| circle__c13.3 | 14.553 | 15.193 | 1.0772 | 1.0179 | -92.346 | 346.95 | shared limits not met |
| kite__c0.5 | 1.913 | 6.8521 | 0.083619 | 0.5447 | 8.9406 | 331.86 | shared limits not met |
| kite__c4 | 35.215 | 79.01 | 1.0101 | 0.82523 | -79.369 | 338.03 | shared limits not met |
| kite__c13.3 | 25.671 | 57.171 | 1.0179 | 1.1795 | -91.131 | 345.94 | shared limits not met |
| peanut__c0.5 | 1.8569 | 4.2164 | 0.16709 | 0.54648 | 9.2957 | 383.38 | shared limits not met |
| peanut__c4 | 26.144 | 57.204 | 1.0102 | 0.87525 | -78.119 | 347.38 | shared limits not met |
| peanut__c13.3 | 14.396 | 19.862 | 0.99745 | 0.92517 | -93.044 | 358.05 | shared limits not met |
| star__c0.5 | 2.382 | 5.6358 | 0.31026 | 0.56887 | 13.775 | 402.37 | shared limits not met |
| star__c4 | 84.944 | 153.01 | 1.0061 | 1.1121 | -72.198 | 326.45 | shared limits not met |
| star__c13.3 | 44.663 | 96.109 | 1.0026 | 1.145 | -91.391 | 328.68 | shared limits not met |
| asymmetric__c0.5 | 1.7874 | 4.1813 | 0.23753 | 0.54338 | 8.6769 | 401.44 | shared limits not met |
| asymmetric__c4 | 43.986 | 101.34 | 1.0116 | 0.88652 | -77.837 | 326.4 | shared limits not met |
| asymmetric__c13.3 | 32.611 | 75.263 | 1.0042 | 1.1506 | -91.349 | 330.89 | shared limits not met |
| c_shape__c0.5 | 2.0516 | 5.6781 | 0.2532 | 0.56684 | 13.368 | 407.16 | shared limits not met |
| c_shape__c4 | 85.228 | 144.79 | 1.0054 | 1.1685 | -70.787 | 339.18 | shared limits not met |
| c_shape__c13.3 | 42.47 | 94.745 | 0.99835 | 1.1185 | -91.59 | 329.01 | shared limits not met |
| hook__c0.5 | 1.3237 | 3.0458 | 0.13481 | 0.56984 | 13.968 | 365.52 | shared limits not met |
| hook__c4 | 25.161 | 41.949 | 1.0052 | 1.1876 | -70.31 | 333.3 | shared limits not met |
| hook__c13.3 | 31.028 | 75.503 | 1.0024 | 1.1934 | -91.027 | 320.14 | shared limits not met |
| cross__c0.5 | 1.9652 | 3.9083 | 0.16935 | 0.54761 | 9.5229 | 384.04 | shared limits not met |
| cross__c4 | 40.399 | 94.836 | 1.0312 | 0.81445 | -79.639 | 348.8 | shared limits not met |
| cross__c13.3 | 95.483 | 155.68 | 1.0073 | 0.87844 | -93.395 | 343.88 | shared limits not met |
| cog__c0.5 | 2.2387 | 4.9053 | 0.3155 | 0.54371 | 8.7411 | 392.76 | shared limits not met |
| cog__c4 | 91.317 | 154.12 | 1.0356 | 1.0987 | -72.531 | 331.29 | shared limits not met |
| cog__c13.3 | 17.766 | 56.851 | 1.054 | 0.96829 | -92.72 | 368.71 | shared limits not met |
| aphex_twin__c0.5 | 2.6309 | 10.792 | 0.11422 | 0.60766 | 21.533 | 317.74 | shared limits not met |
| aphex_twin__c4 | 19.234 | 56.377 | 0.96311 | 1.2633 | -68.417 | 336.28 | shared limits not met |
| aphex_twin__c13.3 | 23.701 | 72.205 | 1.0014 | 1.1938 | -91.024 | 326.59 | shared limits not met |

| Case | RRMSE | SSIM | PSNR dB | Contrast SNR dB |
|---|---:|---:|---:|---:|
| circle__c0.5 | 0.35148 | 0.86149 | 14.512 | 1.3496 |
| circle__c4 | 0.33177 | 0.53999 | 9.6665 | 0.025853 |
| circle__c13.3 | 0.41177 | 0.2729 | 7.8456 | 0.024823 |
| kite__c0.5 | 0.06867 | 0.92461 | 27.322 | 9.87 |
| kite__c4 | 0.21202 | 0.48372 | 14.201 | 0.27046 |
| kite__c13.3 | 0.25778 | 0.19245 | 12.162 | 0.050894 |
| peanut__c0.5 | 0.082489 | 0.88489 | 25.589 | 10.251 |
| peanut__c4 | 0.26399 | 0.48455 | 11.913 | 0.096182 |
| peanut__c13.3 | 0.32769 | 0.202 | 9.9948 | -0.0019852 |
| star__c0.5 | 0.12026 | 0.8232 | 22.183 | 9.1454 |
| star__c4 | 0.33821 | 0.51651 | 9.5619 | 0.046514 |
| star__c13.3 | 0.42039 | 0.25444 | 7.7315 | 0.035971 |
| asymmetric__c0.5 | 0.091485 | 0.86872 | 24.13 | 10.344 |
| asymmetric__c4 | 0.31006 | 0.49884 | 10.33 | 0.066249 |
| asymmetric__c13.3 | 0.3843 | 0.24695 | 8.4804 | 0.036142 |
| c_shape__c0.5 | 0.11025 | 0.83508 | 22.341 | 8.3687 |
| c_shape__c4 | 0.30695 | 0.48879 | 10.499 | 0.048952 |
| c_shape__c13.3 | 0.37787 | 0.22655 | 8.6479 | 0.017381 |
| hook__c0.5 | 0.092775 | 0.84984 | 24.138 | 8.7811 |
| hook__c4 | 0.26404 | 0.48929 | 11.907 | 0.071577 |
| hook__c13.3 | 0.32429 | 0.20527 | 10.076 | 0.060317 |
| cross__c0.5 | 0.087078 | 0.87981 | 25.075 | 10.435 |
| cross__c4 | 0.28994 | 0.48189 | 11.049 | -0.068235 |
| cross__c13.3 | 0.35215 | 0.21743 | 9.331 | 0.033137 |
| cog__c0.5 | 0.0955 | 0.85527 | 23.852 | 10.052 |
| cog__c4 | 0.31204 | 0.48918 | 10.246 | -0.03191 |
| cog__c13.3 | 0.38605 | 0.23879 | 8.4666 | 0.0081462 |
| aphex_twin__c0.5 | 0.081803 | 0.9075 | 25.541 | 7.0327 |
| aphex_twin__c4 | 0.18634 | 0.49536 | 15.321 | 0.33433 |
| aphex_twin__c13.3 | 0.23188 | 0.17122 | 13.234 | 0.067413 |

### GauGal: per-case stopping and failure reasons

| Case | Recorded stop | Observed reason / remaining failure | Saved evidence |
|---|---|---|---|
| circle__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 28.39 > 1; Hausdorff upper bound (mm) 77.72 > 2; maximum field residual 0.952 > 0.003; 5 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8375; truth 0.5; logged mean squared relative misfit 1 → 0.3524; 2261/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1139) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/circle__c0.5.json) |
| circle__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) unavailable; Hausdorff upper bound (mm) unavailable; maximum field residual 1.055 > 0.003; no closed half-peak contour; boundary scores and traced mean contrast unavailable; logged mean squared relative misfit 1 → 0.935; 2179/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.04633) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/circle__c4.json) |
| circle__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 14.55 > 1; Hausdorff upper bound (mm) 15.19 > 2; maximum field residual 1.077 > 0.003; 2 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.018; truth 13.3; logged mean squared relative misfit 1 → 0.9291; 2312/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.04813) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/circle__c13.3.json) |
| kite__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 1.913 > 1; Hausdorff upper bound (mm) 6.852 > 2; maximum field residual 0.08362 > 0.003; traced mean contrast 0.5447; truth 0.5; logged mean squared relative misfit 1 → 0.001292; 2186/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.5299) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/kite__c0.5.json) |
| kite__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 35.21 > 1; Hausdorff upper bound (mm) 79.01 > 2; maximum field residual 1.01 > 0.003; 3 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8252; truth 4; logged mean squared relative misfit 1 → 0.7131; 2258/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.03924) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/kite__c4.json) |
| kite__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 25.67 > 1; Hausdorff upper bound (mm) 57.17 > 2; maximum field residual 1.018 > 0.003; 6 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.18; truth 13.3; logged mean squared relative misfit 1 → 0.823; 2312/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.03521) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/kite__c13.3.json) |
| peanut__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 1.857 > 1; Hausdorff upper bound (mm) 4.216 > 2; maximum field residual 0.1671 > 0.003; traced mean contrast 0.5465; truth 0.5; logged mean squared relative misfit 1 → 0.01336; 2613/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.3526) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/peanut__c0.5.json) |
| peanut__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 26.14 > 1; Hausdorff upper bound (mm) 57.2 > 2; maximum field residual 1.01 > 0.003; 10 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8753; truth 4; logged mean squared relative misfit 1 → 0.7743; 2302/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.05845) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/peanut__c4.json) |
| peanut__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 14.4 > 1; Hausdorff upper bound (mm) 19.86 > 2; maximum field residual 0.9974 > 0.003; 6 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.9252; truth 13.3; logged mean squared relative misfit 1 → 0.8313; 2381/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.04347) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/peanut__c13.3.json) |
| star__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 2.382 > 1; Hausdorff upper bound (mm) 5.636 > 2; maximum field residual 0.3103 > 0.003; traced mean contrast 0.5689; truth 0.5; logged mean squared relative misfit 1 → 0.0445; 2763/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.06217) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/star__c0.5.json) |
| star__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 84.94 > 1; Hausdorff upper bound (mm) 153 > 2; maximum field residual 1.006 > 0.003; 12 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.112; truth 4; logged mean squared relative misfit 1 → 0.8759; 2163/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1157) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/star__c4.json) |
| star__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 44.66 > 1; Hausdorff upper bound (mm) 96.11 > 2; maximum field residual 1.003 > 0.003; 14 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.145; truth 13.3; logged mean squared relative misfit 1 → 0.7642; 2174/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.04535) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/star__c13.3.json) |
| asymmetric__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 1.787 > 1; Hausdorff upper bound (mm) 4.181 > 2; maximum field residual 0.2375 > 0.003; traced mean contrast 0.5434; truth 0.5; logged mean squared relative misfit 1 → 0.02632; 2756/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1286) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/asymmetric__c0.5.json) |
| asymmetric__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 43.99 > 1; Hausdorff upper bound (mm) 101.3 > 2; maximum field residual 1.012 > 0.003; 10 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8865; truth 4; logged mean squared relative misfit 1 → 0.8621; 2157/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.3404) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/asymmetric__c4.json) |
| asymmetric__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 32.61 > 1; Hausdorff upper bound (mm) 75.26 > 2; maximum field residual 1.004 > 0.003; 5 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.151; truth 13.3; logged mean squared relative misfit 1 → 0.8461; 2158/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.0409) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/asymmetric__c13.3.json) |
| c_shape__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 2.052 > 1; Hausdorff upper bound (mm) 5.678 > 2; maximum field residual 0.2532 > 0.003; traced mean contrast 0.5668; truth 0.5; logged mean squared relative misfit 1 → 0.03059; 2796/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.107) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/c_shape__c0.5.json) |
| c_shape__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 85.23 > 1; Hausdorff upper bound (mm) 144.8 > 2; maximum field residual 1.005 > 0.003; 8 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.169; truth 4; logged mean squared relative misfit 1 → 0.781; 2231/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.08497) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/c_shape__c4.json) |
| c_shape__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 42.47 > 1; Hausdorff upper bound (mm) 94.74 > 2; maximum field residual 0.9984 > 0.003; 8 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.119; truth 13.3; logged mean squared relative misfit 1 → 0.865; 2151/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.07618) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/c_shape__c13.3.json) |
| hook__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 1.324 > 1; Hausdorff upper bound (mm) 3.046 > 2; maximum field residual 0.1348 > 0.003; traced mean contrast 0.5698; truth 0.5; logged mean squared relative misfit 1 → 0.009636; 2441/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.09791) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/hook__c0.5.json) |
| hook__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 25.16 > 1; Hausdorff upper bound (mm) 41.95 > 2; maximum field residual 1.005 > 0.003; 8 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.188; truth 4; logged mean squared relative misfit 1 → 0.7783; 2189/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1425) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/hook__c4.json) |
| hook__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 31.03 > 1; Hausdorff upper bound (mm) 75.5 > 2; maximum field residual 1.002 > 0.003; 3 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.193; truth 13.3; logged mean squared relative misfit 1 → 0.7965; 2121/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.06706) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/hook__c13.3.json) |
| cross__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 1.965 > 1; Hausdorff upper bound (mm) 3.908 > 2; maximum field residual 0.1694 > 0.003; traced mean contrast 0.5476; truth 0.5; logged mean squared relative misfit 1 → 0.007717; 2580/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.2312) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cross__c0.5.json) |
| cross__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 40.4 > 1; Hausdorff upper bound (mm) 94.84 > 2; maximum field residual 1.031 > 0.003; 9 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8145; truth 4; logged mean squared relative misfit 1 → 0.7493; 2329/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.04153) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cross__c4.json) |
| cross__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 95.48 > 1; Hausdorff upper bound (mm) 155.7 > 2; maximum field residual 1.007 > 0.003; 3 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.8784; truth 13.3; logged mean squared relative misfit 1 → 0.7935; 2265/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1154) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cross__c13.3.json) |
| cog__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 2.239 > 1; Hausdorff upper bound (mm) 4.905 > 2; maximum field residual 0.3155 > 0.003; traced mean contrast 0.5437; truth 0.5; logged mean squared relative misfit 1 → 0.03696; 2701/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.1157) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cog__c0.5.json) |
| cog__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 91.32 > 1; Hausdorff upper bound (mm) 154.1 > 2; maximum field residual 1.036 > 0.003; 16 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.099; truth 4; logged mean squared relative misfit 1 → 0.8425; 2180/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.06325) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cog__c4.json) |
| cog__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 17.77 > 1; Hausdorff upper bound (mm) 56.85 > 2; maximum field residual 1.054 > 0.003; 11 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.9683; truth 13.3; logged mean squared relative misfit 1 → 0.8031; 2500/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.03156) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/cog__c13.3.json) |
| aphex_twin__c0.5 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 2.631 > 1; Hausdorff upper bound (mm) 10.79 > 2; maximum field residual 0.1142 > 0.003; traced mean contrast 0.6077; truth 0.5; logged mean squared relative misfit 1 → 0.002296; 2117/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.5595) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/aphex_twin__c0.5.json) |
| aphex_twin__c4 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 19.23 > 1; Hausdorff upper bound (mm) 56.38 > 2; maximum field residual 0.9631 > 0.003; 2 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.263; truth 4; logged mean squared relative misfit 1 → 0.6976; 2189/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.03443) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/aphex_twin__c4.json) |
| aphex_twin__c13.3 | iteration_limit | reached the declared 80-iteration budget; convergence not established; RMS (mm) 23.7 > 1; Hausdorff upper bound (mm) 72.21 > 2; maximum field residual 1.001 > 0.003; 8 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.194; truth 13.3; logged mean squared relative misfit 1 → 0.8142; 2162/3059 inner solves missed their convergence tolerance (largest logged inner residual 0.06666) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G2_all/aphex_twin__c13.3.json) |


## Methods and interpretation

**BEM selection was fixed before GauGal results.** Supplied-contrast BEM is slider S1 with both degree-cap cases replaced by S3, for 26/30 recorded recoveries. The other cases never hit that cap and reuse their unchanged paths. This is combined evidence, not a new full campaign. It ties spectral R1’s 26/30. Material recovery uses S2, the best completed truth-free full campaign at 23/30; truth-assisted R3 starts are excluded.

The sampled-log-interval experiments S4/S4b are not selected: they added no confirmed recoveries, and two cases timed out. Supplied-contrast BEM removes the degree cap; S2 retains its earlier numerical settings. Full source paths and all scores are in [comparison.csv](comparison.csv) and [comparison.json](comparison.json).

| Arm | Material information | Representation / start | Frequency data |
|---|---|---|---|
| BEM supplied contrast | True contrast supplied | One homogeneous object bounded by a Fourier curve; centred 65 mm circle | Real and damped continuation catalogs |
| BEM material recovery | Truth-free weak-scatterer contrast estimate | Same single-object curve prior and centred circle | Real and damped continuation catalogs |
| GauGal | No true contrast supplied; common susceptibility bounds | 2,601 Gaussian coefficients; zero susceptibility start | 19 real frequencies |

Each real frequency has 24 complex source–receiver measurements: 456 complex observations in total. GauGal’s 201×201 grid is used for quadrature and images, while its 51×51 lattice contains the unknown coefficients. BEM’s single homogeneous region is a stronger shape and material prior than GauGal’s spatially varying image.

**GauGal adaptation.** One susceptibility image is fitted to a sum of energy-normalized frequency losses on 24 source–receiver pairs at 19 real frequencies. Gaussian lattice 51×51, 201×201 quadrature pixels, width 0.7 lattice spacing, TV lambda scale 0.5, susceptibility bounds −0.9 to 15, released 100-iteration inner-solve cap. Initialization is zero susceptibility. Step sizes 1, 0.01 and 0.05 are tuned on the three circles only by mean image RRMSE. The two smaller steps replaced unrun larger steps after step 1 diverged on circle c0.5.

Chosen common step: **0.05**.

The final common budget is at most 80 outer iterations and 400 seconds of optimization, with a 480-second outer process limit. The T0 timing fit required 50.1 seconds for ten iterations, so the original 300-iteration default could not fit the morning budget. Partial images have explicit stop reasons and actual iteration counts; an iteration-limit exit does not establish convergence. Inner-solve summaries cover the whole fit, including the final prediction. Their convergence tolerance is 1e-4. The saved `completed` status means the iteration budget finished, not that an accuracy target was reached.

**Forward-model limitation.** The existing seven-case sweep did not identify any tested lattice meeting 1% error across those cases at the tested frequencies from 0.75 GHz upwards. All 19 real frequencies are retained under the morning-priority amendment. This measures this TG-002 adaptation under its stated budget; it is not a reproduction of GauGal’s published benchmark and does not establish an intrinsic ranking of the methods.

**Scores and times.** All three image arms are rasterized on the same 1 mm grid. RRMSE, SSIM and PSNR use relative permittivity; contrast SNR uses susceptibility. GauGal’s longest closed half-peak contour supplies its boundary and mean interior contrast. All image scores, contrast estimates and Hausdorff bounds are in the CSV. BEM seconds include the fit and final checks; GauGal seconds include process, operator build and scoring, so they are not pure optimizer speed ratios. CSV/JSON also separate the available component times. Failed BEM fits can stop early.

The overnight machine has an NVIDIA GeForce RTX 5090 (32,607 MiB reported), an Intel Core Ultra 9 285K and Python 3.9.25. At 02:42 London, the active GauGal worker was the only GPU compute process. The broad forward sweeps remained paused. Report scoring briefly ran on the CPU while tuning continued.

Image scores use the relative-to-background permittivity image. Pixel-exact BEM rasterizations can produce zero image RRMSE and very large finite PSNR/SNR from the metric routines’ denominator floors; this does not imply an exactly recovered curve.

RRMSE averages squared per-pixel relative errors. The released SingleTX SSIM routine normalizes each image by its own maximum before its 11×11 comparison, so SSIM alone does not measure material accuracy. Read it with contrast error and contrast SNR.

**Reading failure reasons.** A trial curve can be refused while the last accepted curve passes numerical checks. A failed positive-lower-bound calculation is inconclusive; it does not establish that the trial curve is invalid. The four supplied-contrast failures all stop on that calculation in the selected records.

In the material arm, circle c13.3 and aphex c4/c13.3 meet the shared shape/field limits but fail final numerical comparisons. Asymmetric and cross c13.3 show large contrast drift in the saved warm-up histories, before numerical refusal. Cog c13.3 also drifts in warm-up and returns toward the truth, but still ends at the wrong contrast and large residual.

Final BEM field refinement tolerances are 1e-5 through 0.5 GHz and 1e-7 above it; Jacobian and complete-trial finite-difference tolerances are 0.001. These numerical discrepancies are separate from the 0.003 measurement-residual limit.

For GauGal, a budget stop explains why computation ended; the scored shape and field errors explain why the saved output is unsuccessful. Limited iterations, approximate inner solves and representation error may each contribute. Their individual causal contributions are not established by these runs. Logged losses use extrapolated iterates and are not identical to the separately recomputed final field residual.


## Tuning and saved forward evidence

Frozen common step: **0.05**. [Selection and all tuning scores](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/tuning.json).

| Step | Circle c0.5 RRMSE | Circle c4 RRMSE | Circle c13.3 RRMSE | Mean RRMSE | Finite circles |
|---:|---:|---:|---:|---:|---:|
| 1 | 10.482 | 0.34695 | 0.4474 | 3.7589 | 3/3 |
| 0.01 | 0.41288 | 0.33124 | 0.40984 | 0.38465 | 3/3 |
| 0.05 | 0.36724 | 0.33136 | 0.40984 | 0.36948 | 3/3 |

The circle cases are tuning data, so their final scores are not held-out scores. No further settings were selected using the other 27 cases.

| Step / circle | Stop | Observed limitations | Evidence |
|---|---|---|---|
| 1 / circle__c0.5 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 44.15 > 1; Hausdorff upper bound (mm) 84.57 > 2; maximum field residual 687.9 > 0.003; 25 closed half-peak contours; the longest supplies the boundary; traced mean contrast 6.604; truth 0.5; logged mean squared relative misfit 1 → 1.552e+04; 1140/1159 inner solves missed their convergence tolerance (largest logged inner residual 669) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step1/circle__c0.5.json) |
| 1 / circle__c4 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 42.89 > 1; Hausdorff upper bound (mm) 60.56 > 2; maximum field residual 1.067 > 0.003; 2 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.294; truth 4; logged mean squared relative misfit 1 → 0.8513; 1106/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.01536) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step1/circle__c4.json) |
| 1 / circle__c13.3 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 14.26 > 1; Hausdorff upper bound (mm) 36.74 > 2; maximum field residual 1.293 > 0.003; 2 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.351; truth 13.3; logged mean squared relative misfit 1 → 0.7428; 1122/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.01063) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step1/circle__c13.3.json) |
| 0.01 / circle__c0.5 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 2.754 > 1; Hausdorff upper bound (mm) 3.533 > 2; maximum field residual 0.9816 > 0.003; 3 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.9695; truth 0.5; logged mean squared relative misfit 1 → 0.6223; 1044/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.03249) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.01/circle__c0.5.json) |
| 0.01 / circle__c4 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) unavailable; Hausdorff upper bound (mm) unavailable; maximum field residual 1.004 > 0.003; no closed half-peak contour; boundary scores and traced mean contrast unavailable; logged mean squared relative misfit 1 → 0.9922; 1042/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.07596) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.01/circle__c4.json) |
| 0.01 / circle__c13.3 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 27.33 > 1; Hausdorff upper bound (mm) 78.19 > 2; maximum field residual 1.012 > 0.003; 9 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.006; truth 13.3; logged mean squared relative misfit 1 → 0.9917; 1025/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.05883) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.01/circle__c13.3.json) |
| 0.05 / circle__c0.5 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 2.452 > 1; Hausdorff upper bound (mm) 3.516 > 2; maximum field residual 0.9141 > 0.003; 3 closed half-peak contours; the longest supplies the boundary; traced mean contrast 0.9122; truth 0.5; logged mean squared relative misfit 1 → 0.42; 1068/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.1158) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.05/circle__c0.5.json) |
| 0.05 / circle__c4 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) unavailable; Hausdorff upper bound (mm) unavailable; maximum field residual 1.019 > 0.003; no closed half-peak contour; boundary scores and traced mean contrast unavailable; logged mean squared relative misfit 1 → 0.9683; 1022/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.04633) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.05/circle__c4.json) |
| 0.05 / circle__c13.3 | iteration_limit | reached the declared 30-iteration budget; convergence not established; RMS (mm) 26.79 > 1; Hausdorff upper bound (mm) 77.14 > 2; maximum field residual 1.039 > 0.003; 6 closed half-peak contours; the longest supplies the boundary; traced mean contrast 1.022; truth 13.3; logged mean squared relative misfit 1 → 0.9695; 1045/1159 inner solves missed their convergence tolerance (largest logged inner residual 0.04813) | [result](../../../../results/validation/cleaned_interfaces/GGB-002/G1_tuning/step0.05/circle__c13.3.json) |

Existing forward checks at the selected lattice and width (relative field errors). These use truth-shaped coefficients and a 2,000-iteration inner cap. The inverse uses a cap of 100. These seven cases do not certify all 30 cases.

| Case | 0.25 GHz | 0.75 GHz | 1.25 GHz | 1.75 GHz | 2.5 GHz | Unconverged forward solves |
|---|---:|---:|---:|---:|---:|---:|
| [circle__c0.5](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/circle__c0.5.json) | 0.00028052 | 0.0028703 | 0.0076886 | 0.016898 | 0.032302 | 5/5 |
| [circle__c13.3](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/circle__c13.3.json) | 0.0072652 | 0.10802 | 1.5992 | 2.3261 | 0.52967 | 5/5 |
| [circle__c4](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/circle__c4.json) | 0.0006792 | 0.0091054 | 0.0083008 | 0.030738 | 0.37685 | 5/5 |
| [kite__c0.5](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/kite__c0.5.json) | 0.00033681 | 0.0030506 | 0.008392 | 0.015976 | 0.035643 | 5/5 |
| [kite__c13.3](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/kite__c13.3.json) | 0.0011479 | 0.051616 | 0.17386 | 0.92158 | 0.67275 | 5/5 |
| [kite__c4](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/kite__c4.json) | 0.00094996 | 0.0096721 | 0.022578 | 0.040453 | 0.12993 | 5/5 |
| [peanut__c0.5](../../../../results/validation/cleaned_interfaces/FW-001/F2_gaugal_sweep/peanut__c0.5.json) | 0.00050871 | 0.0027245 | 0.007127 | 0.016003 | 0.030271 | 5/5 |

Forward discrepancies combine representation error and remaining inner-solve error; the saved checks do not isolate either contribution. Likewise, unsuccessful inner solves in an inverse fit are evidence of approximate fields/gradients, not proof that this alone caused its reconstruction error.


## Earlier BEM diagnostic failures and timeouts

S4/S4b bypassed the inconclusive bound using a sampled interval. These outputs are preserved as diagnostics and do not replace either frozen comparison arm. Neither a timeout nor a visually close curve is counted as recovery.

| Run / case | Outcome | Observed reason | Evidence |
|---|---|---|---|
| S4 / cog__c13.3 | not recovered | field refinement discrepancy at 16 frequencies; worst tolerance ratio 3.273e+04 at 2.5 GHz; Jacobian discrepancy 0.008326 > 0.001; maximum field residual 0.246 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval/runs/cog__c13.3/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval/runs/cog__c13.3/final_audit.json) |
| S4b / aphex_twin__c4 | not recovered | field refinement discrepancy at 16 frequencies; worst tolerance ratio 4250 at 2.5 GHz; Jacobian discrepancy 0.00536 > 0.001; maximum field residual 0.003799 > 0.003 | [result](../../../../results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval/aphex_twin__c4/runs/aphex_twin__c4/result.json), [final checks](../../../../results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval/aphex_twin__c4/runs/aphex_twin__c4/final_audit.json) |
| S4 / aphex_twin__c0.5 | timeout; no final result | The 900 s campaign limit expired while fixed_M25 was active. Last completed-stage checkpoint: release_M19 at 702.6 s of fit work. No final numerical checks or recovery score exist. | [exit 124](../../../../results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval/execution_status.json), [checkpoint](../../../../results/validation/cleaned_interfaces/MR-001/S4_slider_sampled_log_interval/runs/aphex_twin__c0.5/checkpoint.json) |
| S4b / aphex_twin__c13.3 | timeout; no final result | The 300 s case limit expired while fixed_M85 was active. Last completed-stage checkpoint: fixed_M79 at 289.0 s of fit work. No final numerical checks or recovery score exist. | [exit 124](../../../../results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval/aphex_twin__c13.3/exit_code.txt), [active-stage log](../../../../results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval/aphex_twin__c13.3/run.log), [checkpoint](../../../../results/validation/cleaned_interfaces/MR-001/S4b_slider_sampled_log_interval/aphex_twin__c13.3/runs/aphex_twin__c13.3/checkpoint.json) |

The timeout records establish budget exhaustion. They do not establish that either fit would recover with more time. The saved active stages distinguish time spent progressing through the fit from an immediate numerical refusal.


## Reconstruction gallery

White outlines show truth; dashed black outlines show the selected GauGal contour used for boundary scoring. Every saved output is displayed, including inaccurate or partial outputs. Color clipping makes severely wrong material values less visible; read the contrast labels and failure tables alongside the images.

### Contrast 0.5

![Contrast 0.5 reconstructions](comparison_figures/gallery_c0.5.png)

### Contrast 4

![Contrast 4 reconstructions](comparison_figures/gallery_c4.png)

### Contrast 13.3

![Contrast 13.3 reconstructions](comparison_figures/gallery_c13.3.png)

