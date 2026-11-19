# Measured-cylinder schedule results

19 November 2026. Tasks 1 and 2 complete; the two matched CUDA fits are pending the coordinator. No fits were run by this analysis.

The saved result does not establish that the data prefer a 19 mm, low-permittivity cylinder. At the fixed best-circle centre, that radius and material lie on a descending slope toward the 15.27 mm, permittivity 3.05 circle. One-frequency data do have a nearly flat radius–material valley, so a 1 GHz warm-up alone does not identify the nominal cylinder. Whether either schedule change improves the maintained fit remains pending.

The [trial replay](../../investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/trial_refusals.md) now explains the saved stop: ladder stage three left a 41 nm neck; later proposed moves crossed the outline. Full stage one eventually narrowed its neck to 1.53 nm. Accepted curves remain simple, while the two reconstructed refused trials genuinely cross. The outline could no longer take the proposed moves, even though the exact-circle slice still descends toward the best circle.

## Loss-map measurements

The map fixes the centre at (1.9393, 26.1912) mm, uses the measured rows and the exact circle series, divides each frequency's residual by its observed-data norm, and averages frequency losses equally (B5). It is an analysis outside the default fitting path, replacing A1–A4 only for an exact circle. [Analysis script](../../../../experiments/bem_on_baseline_data/csi_cylinder_loss_map.py), [series](../../../../experiments/bem_on_baseline_data/csi_forward_check.py#L96), [chain](../../../reference/inverse_information_chain.md#b5-predicted-data--observations--normalized-real-residual).

The nominal circle's all-frequency loss reproduces 0.0579452744. The saved noncircular BEM loss is 0.0840431331, while an exact circle with its area-equivalent radius, centre and material gives 0.0830639630. The brief's requested 0.0840 equality for that exact circle is therefore not exact. The best-circle loss reproduces 0.0375490374. Cached modal contractions agree with direct exact-series evaluations within 1e-10 at these three geometries.

**Material convention correction:** the stored `contrast` is already relative permittivity: the exact series and maintained forward solver both use its square root to scale the interior wavenumber. Adding one would misplace every stage marker. The actual start is therefore radius 65 mm, permittivity 1.0931. The physical contrast-minus-one is 0.0931. [Maintained A4 forward code](../../../../solvers/bem_inverse/forward_solvers/modal_muller.py#L141).

At physical contrast-minus-one 1 (permittivity 2), the 1 GHz valley has radius 19.4686 mm and loss 0.0935247. At contrast-minus-one 30 (permittivity 31), it has radius 3.2885 mm and loss 0.0904507. Loss changes by only 0.0030740, or 3.29%, despite a 5.92-fold radius change. This is at the map centre; the stopped warm-up changes its centre and shape too. If “contrast 1” means the stored solver parameter instead, it is permittivity 1 and has zero predicted scattering and loss 0.5, rather than the weakly changing valley quoted here.

The low-loss basin moves as frequencies are added. Its refined radius/permittivity/loss are 6.472 mm / 9.137 / 0.05102 for 1–2 GHz, 11.804 mm / 3.836 / 0.04395 for 1–3, 13.221 mm / 3.471 / 0.04113 for 1–4, and 15.266 mm / 3.053 / 0.03755 for 1–8. The 1–4 panel is the first with a clear dominant basin close to nominal size and material; only 1–8 puts its minimum at the all-frequency best circle. This is a dominant-basin observation, not a proof of a unique minimum over the full plotted rectangle; narrow valleys create extra sampled minima and there are higher-loss secondary features.

At radius 19.0453 mm and permittivity 2.1937, the fixed-centre all-frequency circle loss is 0.0739312. Its loss derivatives are −0.0022364 per mm of radius and −0.115625 per unit permittivity. Local descent from there reaches 15.2663 mm / 3.05253 and loss 0.0375490. It is on a slope in this circle slice, not a separate local minimum. This does not prove that the actual noncircular BEM endpoint has the same descent directions.

![Exact-circle loss maps and saved stage paths](figures/circle_loss_map.png)

The compressed grid is local and Git-ignored; rebuild it with `/home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/bem_on_baseline_data/csi_cylinder_loss_map.py` (omit `--reuse-grid` to rebuild). [Local compressed grid](../../../../results/bem/baseline_data/measured_schedule/2026-11-19/analysis/circle_loss_grid.npz) (about 1.2 MB), [numbers, checks and stage paths](../../../../results/bem/baseline_data/measured_schedule/2026-11-19/analysis/circle_loss_summary.json). Markers show stage exit area-equivalent radius and stored material; they do not imply that the stage centre or its noncircular shape equals the map's fixed circle. The JSON includes each exit centre and whether polygon repair was needed.

## Saved-fit stage measurements

Only the first stage reached its iteration cap. The next two accepted 19 and 7 steps. Six of the last seven stages accepted none; one all-frequency stage still accepted 13. The fit used 894 of 13,412 units (6.67%), leaving 12,518 unused. Recorded trial counts include accepted, loss-rejected and geometry-refused trials; “refused” below means every nonaccepted trial. Work in the last column is cumulative, not per-stage cost.

| Stage | GHz | Band | Steps | Stop | Loss in → out | ε in → out | Radius mm | Centre mm | Trials / refused | Cumulative units |
|---|---|---:|---:|---|---|---|---:|---|---:|---:|
| ladder_1_real | 1 | 3 | 22 | maximum_iterations | 0.227804 → 0.090942 | 1.0931 → 1.7313 | 22.895 | (2.630, 34.081) | 165 / 143 | 210 |
| ladder_2_real | 1–2 | 6 | 19 | no_decreasing_step | 0.108319 → 0.084791 | 1.7313 → 2.1367 | 18.844 | (3.081, 29.766) | 246 / 227 | 352 |
| ladder_3_real | 1–3 | 9 | 7 | no_decreasing_step | 0.081980 → 0.077270 | 2.1367 → 2.1474 | 18.974 | (3.233, 30.144) | 135 / 128 | 424 |
| ladder_4_real | 1–4 | 12 | 0 | no_decreasing_step | 0.075429 → 0.075429 | 2.1474 → 2.1474 | 18.974 | (3.233, 30.144) | 40 / 40 | 436 |
| full_1_M11 | 1–8 | 11 | 13 | no_decreasing_step | 0.099627 → 0.084057 | 2.1474 → 2.1937 | 19.045 | (2.983, 29.241) | 190 / 177 | 772 |
| full_2_M15 | 1–8 | 15 | 0 | no_decreasing_step | 0.084057 → 0.084057 | 2.1937 → 2.1937 | 19.045 | (2.983, 29.241) | 40 / 40 | 796 |
| full_3_M19 | 1–8 | 19 | 0 | no_decreasing_step | 0.084057 → 0.084057 | 2.1937 → 2.1937 | 19.045 | (2.983, 29.241) | 40 / 40 | 820 |
| full_4_M25 | 1–8 | 25 | 0 | no_decreasing_step | 0.084043 → 0.084043 | 2.1937 → 2.1937 | 19.045 | (2.983, 29.241) | 40 / 40 | 844 |
| full_5_M31 | 1–8 | 31 | 0 | no_decreasing_step | 0.084043 → 0.084043 | 2.1937 → 2.1937 | 19.045 | (2.983, 29.241) | 40 / 40 | 868 |
| full_6_M37 | 1–8 | 37 | 0 | no_decreasing_step | 0.084043 → 0.084043 | 2.1937 → 2.1937 | 19.045 | (2.983, 29.241) | 40 / 40 | 892 |

[Stage extraction script](../../../../experiments/bem_on_baseline_data/csi_cylinder_stage_table.py), [machine-readable stage table](../../../../results/bem/baseline_data/measured_schedule/2026-11-19/analysis/saved_stage_table.json), [saved fit](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01/fit.json). The trial-reason and self-intersection investigation belongs to [the other agent's note](../../investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes/trial_refusals.md).

## Matched fits and limits

The coordinator will supply full `warmup/attempt_02` and `first_cap/attempt_01`. Their comparison, unchanged-prefix checks and final nominal area errors remain pending. The original stopped warm-up's three exits are retained in the plot, not treated as a completed fit.

Nominal radius 15 mm, centre (0, 30) mm and permittivity 3 ± 0.3 are reference values with uncertainty. Measured-data loss and error against nominal must remain separate. The exact-circle map restricts shape and centre, and cannot establish the full shape-space landscape or why a slider trial was refused. No maintained solver or fit-wrapper code was changed.
