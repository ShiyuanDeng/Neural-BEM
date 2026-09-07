# Solver-neutral wrong-SDF inverse comparison

A circle SDF initialized at `(0.48, 0.52) m`, radius `0.065 m` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

MOD and Kress received the same ordered Method-B boundary at each parameter evaluation and used the same bounded central-FD damped Gauss--Newton inverse. Only the forward solver differed.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MOD | 9.737e-01 | 2.713e-03 | 1.226e+05x | 7.044e-02 | 7.302e-02 | 0.0000 | 0.0568 | 7.50 s |
| KRESS | 9.741e-01 | 8.648e-11 | 1.294e+20x | 3.810e-10 | 8.195e-14 | 0.0000 | 0.0000 | 4.49 s |

MOD: `relative_step_tolerance` after 5 accepted updates / 42 forward evaluations; KRESS: `loss_tolerance` after 5 accepted updates / 42 forward evaluations.

For the same 42 inverse evaluations, MOD/Kress wall time was `1.67x`; the final held-out MOD/Kress error ratio was `1.849e+08x`.

Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

## Acceptance

- **PASS** `mod_optimizer_converged`: value `relative_step_tolerance`, required `converged stop condition`.
- **PASS** `mod_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `mod_training_loss_drop`: value `122596.40431432778`, required `>= 100`.
- **PASS** `mod_center_error`: value `2.158287904361139e-10`, required `<= 5e-4 m`.
- **PASS** `mod_radius_error`: value `5.6836950279665066e-05`, required `<= 1e-3 m`.
- **PASS** `mod_linear_system_residual`: value `7.857041666078413e-15`, required `<= 1e-10`.
- **PASS** `mod_holdout_relative_l2`: value `0.07043829589191654`, required `<= 0.15`.
- **PASS** `kress_optimizer_converged`: value `loss_tolerance`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `1.2943232813006596e+20`, required `>= 100`.
- **PASS** `kress_center_error`: value `2.79563577582858e-12`, required `<= 5e-4 m`.
- **PASS** `kress_radius_error`: value `8.00831623237741e-13`, required `<= 1e-3 m`.
- **PASS** `kress_linear_system_residual`: value `6.299380352012257e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `3.810069400282821e-10`, required `<= 0.15`.
- **PASS** `kress_holdout_accuracy`: value `3.810069400282821e-10`, required `<= 1e-6`.
- **PASS** `kress_holdout_beats_mod`: value `{'kress': 3.810069400282821e-10, 'mod': 0.07043829589191654}`, required `Kress < MOD`.
- **PASS** `kress_target_geometry_holdout_beats_mod`: value `{'kress': 8.195004317091178e-14, 'mod': 0.07302406119319439}`, required `Kress < MOD on the identical true boundary`.
- **PASS** `common_initial_boundary_identical`: value `0.0`, required `<= 1e-14 m`.
- **PASS** `common_target_boundary_identical`: value `0.0`, required `<= 1e-14 m`.

Overall: **PASS**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --output-dir results/inverse_solver_comparison/wrong-circle-mie-20260902 --overwrite
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

This establishes an auditable low-dimensional inverse baseline for smooth single-component Torch SDFs. The SDF-to-curve seam crosses NumPy and is not autograd-differentiable. A large randomly initialized SIREN therefore needs a topology-valid initialization and derivatives of the actual Kress weighted operators before it is a scalable inverse.
