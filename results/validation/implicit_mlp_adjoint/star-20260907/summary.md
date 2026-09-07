# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `1185 trainable weights, width 32, 1 hidden layers` was fit to independent Nystrom scattered-field data for the true `(0.50, 0.50) m` star `r(t) = 0.05 (1 + 0.25 cos(5t))`.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 1.126e+00 | 1.020e+00 | 1.237e+00x | 1.118e+00 | 4.850e-05 | 26.6065 | 14.8170 | 41.7873 | 19.30 s |

| Solver | amplitude error | rotation error radians |
|---|---|---|
| KRESS | 2.231e-01 | 2.565e-01 |

KRESS: `maximum_iterations` after 5 accepted updates / 26 forward evaluations.



Training frequencies: 0.5 GHz, 1.5 GHz. Holdout frequencies: 0.25 GHz, 1 GHz, 2.5 GHz.

Observations: nystrom_ref independent Nystrom/Muller solution of the exact star.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **FAIL** `kress_training_loss_drop`: value `1.236993743741008`, required `>= 100`.
- **FAIL** `kress_boundary_error_within_representation`: value `{'final': 0.041787291825766425, 'floor': 0.011563228848079634}`, required `<= 2x the same network fitted to the exact target`.
- **FAIL** `kress_boundary_error_improved`: value `{'final': 0.041787291825766425, 'initial': 0.038952139002019076}`, required `<= 0.25x the initial contour error`.
- **PASS** `kress_holdout_within_representation`: value `{'final': 1.1179023917507944, 'floor': 0.5965580820992592}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `1.0902774718489179e-14`, required `<= 1e-10`.
- **FAIL** `kress_holdout_relative_l2`: value `1.1179023917507944`, required `<= 0.15`.
- **PASS** `kress_warm_start_is_eikonal`: value `0.04863434519229104`, required `<= 0.25`.
- **PASS** `observation_oracle_self_convergence`: value `2.8601909761474735e-10`, required `<= 1e-8`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_implicit_mlp_inverse.py --target star --max-iterations 5 --num-pairs 6 --num-nodes 128 --mlp-hidden-features 32 --mlp-hidden-layers 1 --no-gate --output-dir results/validation/implicit_mlp_adjoint/star-20260907
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural adjoint updates differentiate the current extraction/Method-B branch into neural weights and validate the actual re-extracted candidate. Discrete connectivity and branch switches are not differentiated. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).

Editorial correction after the run: the derivative description above now matches the implemented branch-local autograd conversion. Measured metrics, trajectories and weights are unchanged.
