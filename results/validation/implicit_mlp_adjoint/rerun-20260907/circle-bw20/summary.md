# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `8577 trainable weights, width 64, 2 hidden layers` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 9.754e-01 | 1.795e-03 | 3.127e+05x | 7.053e-02 | 7.326e-14 | 0.0311 | 0.0141 | 1.1220 | 2632.47 s |

KRESS: `maximum_iterations` after 60 accepted updates / 479 forward evaluations.



Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

Observations: gpr_bem_ref analytic penetrable-cylinder Mie series.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `312731.47925753304`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.0011220219707639076, 'floor': 0.00028369938582735454}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_boundary_error_improved`: value `{'final': 0.0011220219707639076, 'initial': 0.04328759331911611}`, required `<= 0.25x the initial contour error`.
- **FAIL** `kress_holdout_within_representation`: value `{'final': 0.07052690969145073, 'floor': 0.014015825998437892}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `6.948302673426516e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `0.07052690969145073`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.009884260581966675`, required `<= 0.25`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  /tmp/claude-1001/-home-drdeng-Neural-SDF-BEM-AD/caa6f2cb-1251-4a2c-a99c-48e759f67062/scratchpad/run_circle_bw20.py --max-iterations 60 --num-pairs 8 --num-nodes 64 --no-gate --output-dir results/validation/implicit_mlp_adjoint/rerun-20260907/circle-bw20
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural updates propagate discrete Kress geometry sensitivities into network weights through a differentiable, branch-local extraction and Method-B conversion. Topology changes and interpolation branch switches are not differentiated. Every candidate is re-extracted and evaluated before acceptance. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).
