# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `8577 trainable weights, width 64, 2 hidden layers` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 1.344e+00 | 8.951e-03 | 2.392e+04x | 3.186e-01 | 8.781e-14 | 0.9172 | 0.1699 | 6.4504 | 49.86 s |

KRESS: `maximum_iterations` after 60 accepted updates / 364 forward evaluations.



Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

Observations: gpr_bem_ref analytic penetrable-cylinder Mie series.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `23921.70060027423`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.006450388680341972, 'floor': 0.00023475232129879092}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_boundary_error_improved`: value `{'final': 0.006450388680341972, 'initial': 0.05837678815139885}`, required `<= 0.25x the initial contour error`.
- **FAIL** `kress_holdout_within_representation`: value `{'final': 0.31863751213801206, 'floor': 0.015242010519366297}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `6.256191415287844e-15`, required `<= 1e-10`.
- **FAIL** `kress_holdout_relative_l2`: value `0.31863751213801206`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.11457397193819452`, required `<= 0.25`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_implicit_mlp_inverse.py --target circle --initial-model siren_ellipse --solvers kress --optimizer adjoint --max-iterations 60 --num-pairs 12 --output-dir results/inverse/implicit_mlp/ellipse-to-circle-20260907T151516
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural updates propagate discrete Kress geometry sensitivities into network weights through a differentiable, branch-local extraction and Method-B conversion. Topology changes and interpolation branch switches are not differentiated. Every candidate is re-extracted and evaluated before acceptance. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).
