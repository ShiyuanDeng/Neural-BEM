# BEM and GauGal on TG-002 — 30-case comparison

Generated 2026-11-02 02:28:45 GMT.

**INCOMPLETE:** GauGal outcomes for 1/3 cases. Failed and time-limited outcomes are retained.

Three separate arms use the same noiseless TG-002 observations and geometry. BEM with supplied contrast knows the true contrast. BEM material recovery and GauGal estimate it. BEM also uses damped-frequency warm-up data; GauGal uses the 19 real frequencies only.

## Aggregate results

| Arm | Saved images | Shared shape/field limits | Full BEM recovery | Median RMS mm | Median image RRMSE | Median recorded seconds |
|---|---:|---:|---:|---:|---:|---:|
| BEM: supplied contrast | 3 | 3 | 3 | 7.64e-06 | 0 | 3.63 |
| BEM: recovered contrast | 3 | 3 | 2 | 7.6e-06 | 5.69e-10 | 4.99 |
| GauGal | 1 | 0 | not applicable | 39.3 | 0.335 | — |

Shared limits are RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm and maximum relative field residual ≤ 0.003. Full BEM recovery additionally requires its independent final numerical checks. GauGal has no equivalent BEM Jacobian check; its shared-limit count is not claimed as full TG-002 numerical qualification.

![Errors across all cases](comparison_figures/errors.png)

## Per-case results

Triples below are **supplied-contrast BEM / material-recovery BEM / GauGal**. A dash means no finite value was available. Circle cases were used for GauGal tuning.

| Case | RMS mm | Maximum field residual | Image RRMSE | GauGal status / iterations |
|---|---|---|---|---|
| circle__c0.5 | 7.64e-06 / 7.56e-06 / — | 8.88e-08 / 6.12e-08 / — | 0 / 5.69e-10 / — | not_run / — |
| circle__c4 | 1.06e-05 / 8.6e-06 / 39.3 | 6.25e-06 / 1.73e-06 / 1.08 | 0 / 6.44e-09 / 0.335 | completed / None |
| circle__c13.3 | 7.58e-06 / 7.6e-06 / — | 1.06e-07 / 4.62e-07 / — | 0 / 7.17e-11 / — | not_run / — |

## Methods and interpretation

**BEM selection was fixed before GauGal results.** Supplied-contrast BEM is slider S1 with both degree-cap cases replaced by S3, for 26/30 recorded recoveries. The other cases never hit that cap and reuse their unchanged paths. This is combined evidence, not a new full campaign. It ties spectral R1’s 26/30. Material recovery uses S2, the best completed truth-free full campaign at 23/30; truth-assisted R3 starts are excluded.

The sampled-log-interval experiments S4/S4b are not selected: they added no confirmed recoveries, and two cases timed out. Supplied-contrast BEM removes the degree cap; S2 retains its earlier numerical settings. Full source paths and all scores are in [comparison.csv](comparison.csv) and [comparison.json](comparison.json).

**GauGal adaptation.** One susceptibility image is fitted to a sum of energy-normalized frequency losses on 24 source–receiver pairs at 19 real frequencies. Gaussian lattice 51×51, 201×201 quadrature pixels, width 0.7 lattice spacing, TV lambda scale 0.5, susceptibility bounds −0.9 to 15, released 100-iteration inner-solve cap. Initialization is zero susceptibility. Step sizes 1, 0.01 and 0.05 are tuned on the three circles only by mean image RRMSE. The two smaller steps replaced unrun larger steps after step 1 diverged on circle c0.5.

Tuning selection is not yet available.

The final common budget is at most 80 outer iterations and 400 seconds of optimization, with a 480-second outer process limit. The T0 timing fit required 50.1 seconds for ten iterations, so the original 300-iteration default could not fit the morning budget. Partial images have explicit stop reasons and actual iteration counts; an iteration-limit exit does not establish convergence. Final inner-solve summaries are retained in the case JSON.

**Forward-model limitation.** The existing seven-case sweep did not identify any tested lattice meeting 1% error across those cases at 0.75 GHz and above. All 19 real frequencies are retained here rather than discarding 18 frequencies. Thus this measures this TG-002 adaptation under its stated budget; it is not a reproduction of GauGal’s published benchmark and does not establish an intrinsic ranking of the methods.

**Scores and times.** Both image arms are rasterized on the same 1 mm grid. RRMSE, SSIM and PSNR use relative permittivity; contrast SNR uses susceptibility. GauGal’s longest closed half-peak contour supplies its boundary and mean interior contrast. All image scores, contrast estimates and Hausdorff bounds are in the CSV. BEM seconds are recorded fit times; GauGal seconds include process, operator build and scoring, so they are not pure optimizer speed ratios. GauGal JSON separates build and optimizer times. Failed BEM fits can stop early.

## Reconstruction gallery

### Contrast 0.5

![Contrast 0.5 reconstructions](comparison_figures/gallery_c0.5.png)

### Contrast 4

![Contrast 4 reconstructions](comparison_figures/gallery_c4.png)

### Contrast 13.3

![Contrast 13.3 reconstructions](comparison_figures/gallery_c13.3.png)

