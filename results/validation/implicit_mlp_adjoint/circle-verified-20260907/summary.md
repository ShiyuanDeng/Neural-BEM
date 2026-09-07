# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `8577 trainable weights, width 64, 2 hidden layers` was fit to independent analytic Mie scattered-field data for the true `(0.50, 0.50) m`, radius `0.050 m` cylinder.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 9.754e-01 | 1.838e-03 | 2.979e+05x | 7.072e-02 | 9.425e-14 | 0.0238 | 0.0174 | 1.0379 | 36.54 s |

KRESS: `no_decreasing_neural_step` after 41 accepted updates / 312 forward evaluations.



Training frequencies: 0.25 GHz, 0.5 GHz. Holdout frequencies: 1 GHz, 1.5 GHz, 2.5 GHz.

Observations: gpr_bem_ref analytic penetrable-cylinder Mie series.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `no_decreasing_neural_step`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **PASS** `kress_training_loss_drop`: value `297871.1269759075`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.0010379034133198087, 'floor': 0.00023475232129879092}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_boundary_error_improved`: value `{'final': 0.0010379034133198087, 'initial': 0.04325939264716375}`, required `<= 0.25x the initial contour error`.
- **FAIL** `kress_holdout_within_representation`: value `{'final': 0.07072131119733882, 'floor': 0.01399210954860459}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `7.17856009947648e-15`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `0.07072131119733882`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.010191880864717673`, required `<= 0.25`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_implicit_mlp_inverse.py --max-iterations 60 --num-pairs 8 --num-nodes 64 --no-gate --output-dir results/validation/implicit_mlp_adjoint/circle-verified-20260907
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural adjoint updates differentiate the current extraction/Method-B branch into neural weights and validate the actual re-extracted candidate. Discrete connectivity and branch switches are not differentiated. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).

Editorial correction after the run: the derivative description above now matches the implemented branch-local autograd conversion. Measured metrics, trajectories and weights are unchanged.
