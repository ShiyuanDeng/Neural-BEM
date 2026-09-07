# Solver-neutral implicit-initialization inverse comparison

A `topology_constrained_random_feature_neural_implicit` field initialized with `center_x=0.48, center_y=0.52, radius=0.06, network_weight_l2=1.31909, network_weight_max_abs=0.8` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

MOD and Kress received the same ordered Method-B boundary at each parameter evaluation and used the same bounded central-FD damped Gauss--Newton inverse. Only the forward solver differed.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MOD | 9.298e-01 | 2.713e-03 | 1.108e+05x | 7.044e-02 | 7.302e-02 | 0.0000 | 0.0568 | 31.67 s |
| KRESS | 9.298e-01 | 3.696e-10 | 6.631e+18x | 3.645e-09 | 8.195e-14 | 0.0000 | 0.0000 | 17.45 s |

MOD: `gradient_tolerance` after 11 accepted updates / 190 forward evaluations; KRESS: `loss_tolerance` after 11 accepted updates / 190 forward evaluations.

For the same 190 inverse evaluations, MOD/Kress wall time was `1.81x`; the final held-out MOD/Kress error ratio was `1.932e+07x`.

Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

## Acceptance

- **PASS** `mod_optimizer_converged`: value `gradient_tolerance`, required `converged stop condition`.
- **PASS** `mod_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `mod_training_loss_drop`: value `110819.057185147`, required `>= 100`.
- **PASS** `mod_center_error`: value `5.509220886688407e-10`, required `<= 5e-4 m`.
- **PASS** `mod_radius_error`: value `5.683694399234718e-05`, required `<= 1e-3 m`.
- **PASS** `mod_final_boundary_error`: value `5.6837071372543846e-05`, required `<= 1e-3 m`.
- **PASS** `mod_linear_system_residual`: value `7.857041666078413e-15`, required `<= 1e-10`.
- **PASS** `mod_holdout_relative_l2`: value `0.07043829614301819`, required `<= 0.15`.
- **PASS** `mod_initial_shape_non_circular`: value `0.00751076926391072`, required `>= 2e-3 m`.
- **PASS** `mod_initial_field_non_distance`: value `1.0175355584663501`, required `>= 5e-2`.
- **PASS** `kress_optimizer_converged`: value `loss_tolerance`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `6.63080155818517e+18`, required `>= 100`.
- **PASS** `kress_center_error`: value `2.1907688299190896e-10`, required `<= 5e-4 m`.
- **PASS** `kress_radius_error`: value `7.238237786921786e-13`, required `<= 1e-3 m`.
- **PASS** `kress_final_boundary_error`: value `5.002653152841319e-11`, required `<= 1e-3 m`.
- **PASS** `kress_linear_system_residual`: value `6.588881469691846e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `3.645213116359831e-09`, required `<= 0.15`.
- **PASS** `kress_initial_shape_non_circular`: value `0.00751076926391072`, required `>= 2e-3 m`.
- **PASS** `kress_initial_field_non_distance`: value `1.0175355584663501`, required `>= 5e-2`.
- **PASS** `kress_holdout_accuracy`: value `3.645213116359831e-09`, required `<= 1e-6`.
- **PASS** `kress_holdout_beats_mod`: value `{'kress': 3.645213116359831e-09, 'mod': 0.07043829614301819}`, required `Kress < MOD`.
- **PASS** `kress_target_geometry_holdout_beats_mod`: value `{'kress': 8.195004317091178e-14, 'mod': 0.07302406119319439}`, required `Kress < MOD on the identical true boundary`.
- **PASS** `common_initial_boundary_identical`: value `0.0`, required `<= 1e-14 m`.
- **PASS** `common_target_boundary_identical`: value `0.0`, required `<= 1e-14 m`.

Overall: **PASS**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model random_features --max-iterations 16 --loss-tolerance 1e-14 --output-dir results/inverse_solver_comparison/random-feature-implicit-mie-20260902 --overwrite
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

This establishes an auditable low-dimensional inverse baseline for smooth single-component Torch implicit fields. The field-to-curve seam crosses NumPy and is not autograd-differentiable. A large randomly initialized SIREN therefore needs a topology-valid initialization and derivatives of the actual Kress weighted operators before it is a scalable inverse.
