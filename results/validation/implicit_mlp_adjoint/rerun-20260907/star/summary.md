# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `8577 trainable weights, width 64, 2 hidden layers` was fit to independent Nystrom scattered-field data for the true `(0.50, 0.50) m` star `r(t) = 0.05 (1 + 0.25 cos(5t))`.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 1.228e+00 | 6.526e-01 | 3.693e+00x | 1.023e+00 | 4.716e-05 | 18.8941 | 7.0662 | 36.7466 | 1294.87 s |

| Solver | amplitude error | rotation error radians |
|---|---|---|
| KRESS | 1.350e-01 | 4.598e-01 |

KRESS: `no_decreasing_neural_step` after 27 accepted updates / 208 forward evaluations.



Training frequencies: 0.5 GHz, 1.5 GHz. Holdout frequencies: 0.25 GHz, 1 GHz, 2.5 GHz.

Observations: nystrom_ref independent Nystrom/Muller solution of the exact star.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `no_decreasing_neural_step`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **FAIL** `kress_training_loss_drop`: value `3.692672047068399`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.03674663766672505, 'floor': 0.0011508830570583892}`, required `<= 2x the same network fitted to the exact target`.
- **FAIL** `kress_boundary_error_improved`: value `{'final': 0.03674663766672505, 'initial': 0.04257547698805222}`, required `<= 0.25x the initial contour error`.
- **FAIL** `kress_holdout_within_representation`: value `{'final': 1.0230375042326103, 'floor': 0.02500961758417375}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `2.435964291590478e-14`, required `<= 1e-10`.
- **FAIL** `kress_holdout_relative_l2`: value `1.0230375042326103`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.21913682778349286`, required `<= 0.25`.
- **PASS** `observation_oracle_self_convergence`: value `2.879272198744391e-10`, required `<= 1e-8`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_implicit_mlp_inverse.py --target star --max-iterations 60 --num-pairs 8 --no-gate --output-dir results/validation/implicit_mlp_adjoint/rerun-20260907/star
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural updates propagate discrete Kress geometry sensitivities into network weights through a differentiable, branch-local extraction and Method-B conversion. Topology changes and interpolation branch switches are not differentiated. Every candidate is re-extracted and evaluated before acceptance. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).
