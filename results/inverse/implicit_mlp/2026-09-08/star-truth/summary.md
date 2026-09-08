# Implicit-field Method-B inverse comparison

A `siren_neural_implicit` field initialized with `8577 trainable weights, width 64, 2 hidden layers` was fit to independent Nystrom scattered-field data for the true `(0.50, 0.50) m` star `r(t) = 0.05 (1 + 0.25 cos(5t))`.

Every candidate is evaluated from its own implicit field after extraction and Method-B conversion. KRESS: Kress discrete adjoint → branch-local extraction/Method-B reverse → Adam weight update. One solver branch is evaluated.

## Outcome

| Solver | Initial train rel. L2 | Final train rel. L2 | Loss drop | Final holdout rel. L2 | True-boundary holdout rel. L2 | Center error (mm) | Radius error (mm) | Max node-to-boundary (mm) | Inverse wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KRESS | 1.073e-02 | 7.452e-03 | 2.096e+00x | 8.926e-02 | 7.201e-07 | 0.2197 | 0.0853 | 1.2902 | 318.71 s |

| Solver | amplitude error | rotation error radians |
|---|---|---|
| KRESS | 1.773e-03 | 6.890e-04 |

KRESS: `maximum_iterations` after 3 accepted updates / 27 forward evaluations.



Training frequencies: 0.5 GHz, 1.5 GHz. Holdout frequencies: 3 GHz.

Observations: nystrom_ref independent Nystrom/Muller solution of the exact star.

## Acceptance

- **FAIL** `kress_optimizer_converged`: value `maximum_iterations`, required `converged stop condition`.
- **PASS** `kress_accepted_losses_monotone`: value `True`, required `True`.
- **FAIL** `kress_training_loss_drop`: value `2.095885051625418`, required `>= 100`.
- **PASS** `kress_boundary_error_within_representation`: value `{'final': 0.0012901892905574372, 'floor': 0.0011911248509951348}`, required `<= 2x the same network fitted to the exact target`.
- **FAIL** `kress_boundary_error_improved`: value `{'final': 0.0012901892905574372, 'initial': 0.0011911248509951348}`, required `<= 0.25x the initial contour error`.
- **PASS** `kress_holdout_within_representation`: value `{'final': 0.08925832607707636, 'floor': 0.11963352659549378}`, required `<= 2x the same network fitted to the exact target`.
- **PASS** `kress_linear_system_residual`: value `1.572491371335889e-14`, required `<= 1e-10`.
- **PASS** `kress_holdout_relative_l2`: value `0.08925832607707636`, required `<= 0.15`.
- **FAIL** `kress_warm_start_is_eikonal`: value `0.3534567894738916`, required `<= 0.25`.
- **PASS** `observation_oracle_self_convergence`: value `4.263433330839791e-10`, required `<= 1e-8`.

Overall: **FAIL**.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_implicit_mlp_inverse.py --target star --start-at-truth --max-iterations 3 --num-pairs 8 --num-nodes 194 --bandwidth 96 --grid-resolution 513 --projected-samples 256 --mlp-pretrain-eikonal-weight 0 --train-ghz 0.5,1.5 --holdout-ghz 3.0 --max-backtracks 14 --no-gate --output-dir results/inverse/implicit_mlp/2026-09-08/star-truth
```

`metrics.json` contains per-frequency errors, geometry distances, linear-solve residuals, timings, configuration, and provenance. The CSV files contain every accepted iterate. Timings are one-run engineering measurements, not a formal benchmark.

## Scope

The accepted geometry belongs to the implicit model. Neural updates propagate discrete Kress geometry sensitivities into network weights through a differentiable, branch-local extraction and Method-B conversion. Topology changes and interpolation branch switches are not differentiated. Every candidate is re-extracted and evaluated before acceptance. Parameter finite differences remain explicit reference controls. These results concern smooth, topology-valid single-component fields at the recorded conversion resolution.

Accepted neural weights, architecture and run metadata: [kress_model.pt](kress_model.pt).
