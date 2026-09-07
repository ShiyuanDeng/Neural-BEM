# Solver-neutral implicit-initialization inverse comparison

A `rotated_quadratic_ellipse` field initialized with `center_x=0.48, center_y=0.52, radius=0.0523068, semi_axis_x=0.072, semi_axis_y=0.038, axis_ratio=1.89474, rotation_radians=0.4` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

MOD and Kress received the same ordered Method-B boundary at each parameter evaluation and used the same bounded central-FD damped Gauss--Newton inverse. Only the forward solver differed.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MOD | 9.272e-01 | 2.713e-03 | 1.082e+05x | 7.044e-02 | 7.302e-02 | 0.0000 | 0.0568 | 10.08 s |
| KRESS | 9.283e-01 | 7.115e-10 | 1.746e+18x | 3.225e-09 | 8.195e-14 | 0.0000 | 0.0000 | 6.57 s |

MOD: `loss_change_tolerance` after 7 accepted updates / 72 forward evaluations; KRESS: `loss_tolerance` after 6 accepted updates / 63 forward evaluations.

With MOD at 72 inverse evaluations and KRESS at 63 inverse evaluations, MOD/Kress wall time was `1.53x`; the final held-out MOD/Kress error ratio was `2.184e+07x`.

Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

## Acceptance

- **PASS** `mod_optimizer_converged`: value `loss_change_tolerance`, required `converged stop condition`.
- **PASS** `mod_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `mod_training_loss_drop`: value `108175.00274843551`, required `>= 100`.
- **PASS** `mod_center_error`: value `2.5872365430303017e-14`, required `<= 5e-4 m`.
- **PASS** `mod_radius_error`: value `5.6836945368850256e-05`, required `<= 1e-3 m`.
- **PASS** `mod_final_boundary_error`: value `5.683694596170241e-05`, required `<= 1e-3 m`.
- **PASS** `mod_linear_system_residual`: value `7.857041666078413e-15`, required `<= 1e-10`.
- **PASS** `mod_holdout_relative_l2`: value `0.07043829608334681`, required `<= 0.15`.
- **PASS** `mod_initial_shape_non_circular`: value `0.03377257566063645`, required `>= 2e-3 m`.
- **PASS** `mod_initial_field_non_distance`: value `51.658665785964374`, required `>= 5e-2`.
- **PASS** `kress_optimizer_converged`: value `loss_tolerance`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `1.746252461512758e+18`, required `>= 100`.
- **PASS** `kress_center_error`: value `1.7308817556933925e-12`, required `<= 5e-4 m`.
- **PASS** `kress_radius_error`: value `5.66796609646758e-13`, required `<= 1e-3 m`.
- **PASS** `kress_final_boundary_error`: value `3.4118971536933884e-11`, required `<= 1e-3 m`.
- **PASS** `kress_linear_system_residual`: value `6.299380352012257e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `3.2248682457599538e-09`, required `<= 0.15`.
- **PASS** `kress_initial_shape_non_circular`: value `0.03377257566063645`, required `>= 2e-3 m`.
- **PASS** `kress_initial_field_non_distance`: value `51.658665785964374`, required `>= 5e-2`.
- **PASS** `kress_holdout_accuracy`: value `3.2248682457599538e-09`, required `<= 1e-6`.
- **PASS** `kress_holdout_beats_mod`: value `{'kress': 3.2248682457599538e-09, 'mod': 0.07043829608334681}`, required `Kress < MOD`.
- **PASS** `kress_target_geometry_holdout_beats_mod`: value `{'kress': 8.195004317091178e-14, 'mod': 0.07302406119319439}`, required `Kress < MOD on the identical true boundary`.
- **PASS** `common_initial_boundary_identical`: value `0.0`, required `<= 1e-14 m`.
- **PASS** `common_target_boundary_identical`: value `0.0`, required `<= 1e-14 m`.

Overall: **PASS**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model ellipse --max-iterations 8 --output-dir results/inverse_solver_comparison/wrong-ellipse-mie-20260902 --overwrite
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

This establishes an auditable low-dimensional inverse baseline for smooth single-component Torch implicit fields. The field-to-curve seam crosses NumPy and is not autograd-differentiable. A large randomly initialized SIREN therefore needs a topology-valid initialization and derivatives of the actual Kress weighted operators before it is a scalable inverse.
