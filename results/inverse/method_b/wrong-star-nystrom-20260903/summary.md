# Solver-neutral implicit-initialization inverse comparison

A `radial_star_level_set` field initialized with `center_x=0.48, center_y=0.52, radius=0.06, mean_radius=0.06, amplitude=0.12, rotation_radians=0.25, lobes=5` was fit to independent Nystrom scattered-field data for the true `(0.50, 0.50) m` star `r(t) = 0.05 (1 + 0.25 cos(5t))`.

MOD and Kress received the same ordered Method-B boundary at each parameter evaluation and used the same bounded central-FD damped Gauss--Newton inverse. Only the forward solver differed.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MOD | 1.200e+00 | 3.021e-03 | 1.514e+05x | 1.266e-02 | 1.260e-02 | 0.0000 | 0.0046 | 0.0666 | 116.98 s |
| KRESS | 1.196e+00 | 5.881e-06 | 3.932e+10x | 3.139e-05 | 4.824e-05 | 0.0000 | 0.0001 | 0.0387 | 74.00 s |

| Solver | amplitude error | rotation error radians |
|---|---|---|
| MOD | 4.916e-04 | 7.842e-05 |
| KRESS | 5.427e-06 | 1.352e-07 |

MOD: `loss_change_tolerance` after 11 accepted updates / 132 forward evaluations; KRESS: `relative_step_tolerance` after 10 accepted updates / 121 forward evaluations.

With MOD at 132 inverse evaluations and KRESS at 121 inverse evaluations, MOD/Kress wall time was `1.58x`; the final held-out MOD/Kress error ratio was `4.032e+02x`.

Training frequencies: 0.5 GHz, 1.5 GHz. Holdout frequencies: 0.25 GHz, 1 GHz, 2.5 GHz.

Observations: nystrom_ref independent Nystrom/Muller solution of the exact star.

## Acceptance

- **PASS** `mod_optimizer_converged`: value `loss_change_tolerance`, required `converged stop condition`.
- **PASS** `mod_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `mod_training_loss_drop`: value `151449.3306437254`, required `>= 100`.
- **PASS** `mod_center_error`: value `2.350677263767618e-09`, required `<= 5e-4 m`.
- **PASS** `mod_radius_error`: value `4.561867717176038e-06`, required `<= 1e-3 m`.
- **PASS** `mod_amplitude_error`: value `0.0004916382282703635`, required `<= 2e-2`.
- **PASS** `mod_rotation_error`: value `7.842252158742032e-05`, required `<= 2e-2 rad`.
- **PASS** `mod_final_boundary_error`: value `6.658087787432502e-05`, required `<= 1e-3 m`.
- **PASS** `mod_linear_system_residual`: value `9.32081993426543e-15`, required `<= 1e-10`.
- **PASS** `mod_holdout_relative_l2`: value `0.012658149631161426`, required `<= 0.15`.
- **PASS** `mod_initial_shape_non_circular`: value `0.014394825709740343`, required `>= 2e-3 m`.
- **PASS** `mod_initial_field_non_distance`: value `0.16842334916231927`, required `>= 5e-2`.
- **PASS** `kress_optimizer_converged`: value `relative_step_tolerance`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `39315937592.09939`, required `>= 100`.
- **PASS** `kress_center_error`: value `2.9235013839290633e-09`, required `<= 5e-4 m`.
- **PASS** `kress_radius_error`: value `9.462345088723234e-08`, required `<= 1e-3 m`.
- **PASS** `kress_amplitude_error`: value `5.427199987084741e-06`, required `<= 2e-2`.
- **PASS** `kress_rotation_error`: value `1.3519614467670297e-07`, required `<= 2e-2 rad`.
- **PASS** `kress_final_boundary_error`: value `3.868554363679945e-05`, required `<= 1e-3 m`.
- **PASS** `kress_linear_system_residual`: value `8.195614476935756e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `3.139459457220169e-05`, required `<= 0.15`.
- **PASS** `kress_initial_shape_non_circular`: value `0.014394825709740343`, required `>= 2e-3 m`.
- **PASS** `kress_initial_field_non_distance`: value `0.16842334916231927`, required `>= 5e-2`.
- **PASS** `kress_holdout_accuracy`: value `3.139459457220169e-05`, required `<= 1e-3`.
- **PASS** `kress_holdout_beats_mod`: value `{'kress': 3.139459457220169e-05, 'mod': 0.012658149631161426}`, required `Kress < MOD`.
- **PASS** `kress_target_geometry_holdout_beats_mod`: value `{'kress': 4.824084396454547e-05, 'mod': 0.012603589276959136}`, required `Kress < MOD on the identical true boundary`.
- **PASS** `observation_oracle_self_convergence`: value `2.879600833156596e-10`, required `<= 1e-8`.
- **PASS** `common_initial_boundary_identical`: value `0.0`, required `<= 1e-14 m`.
- **PASS** `common_target_boundary_identical`: value `0.0`, required `<= 1e-14 m`.

Overall: **PASS**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --target star --output-dir results/inverse_solver_comparison/wrong-star-nystrom-20260903 --overwrite
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

This establishes an auditable low-dimensional inverse baseline for smooth single-component Torch implicit fields. The field-to-curve seam crosses NumPy and is not autograd-differentiable. A large randomly initialized SIREN therefore needs a topology-valid initialization and derivatives of the actual Kress weighted operators before it is a scalable inverse.
