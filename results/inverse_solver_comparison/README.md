# Implicit-initialization inverse comparisons

All three checked cases recover the same analytic circle from independent Mie
scattered-field observations. They use the same 12 paired measurements,
0.25/0.5 GHz training frequencies, 1/1.5/2.5 GHz holdout frequencies, ordered
Method-B geometry, parameter finite differences, and damped Gauss--Newton
policy. Only the initial implicit representation and selected forward solver
change.

| Initial field | Solver | Train relative L2, initial -> final | Holdout relative L2 | Final maximum circle error | Evaluations | Time |
|---|---|---:|---:|---:|---:|---:|
| Wrong circle SDF | MOD | `9.737e-1 -> 2.713e-3` | `7.044e-2` | `5.684e-5 m` | 42 | `7.50 s` |
| Wrong circle SDF | Kress | `9.741e-1 -> 8.648e-11` | `3.810e-10` | `3.601e-12 m` | 42 | `4.49 s` |
| Rotated quadratic ellipse, non-SDF | MOD | `9.272e-1 -> 2.713e-3` | `7.044e-2` | `5.684e-5 m` | 72 | `10.08 s` |
| Rotated quadratic ellipse, non-SDF | Kress | `9.283e-1 -> 7.115e-10` | `3.225e-9` | `3.412e-11 m` | 63 | `6.57 s` |
| Seeded random-feature neural implicit, non-SDF | MOD | `9.298e-1 -> 2.713e-3` | `7.044e-2` | `5.684e-5 m` | 190 | `31.67 s` |
| Seeded random-feature neural implicit, non-SDF | Kress | `9.298e-1 -> 3.696e-10` | `3.645e-9` | `5.003e-11 m` | 190 | `17.45 s` |

Every checked bundle passes all of its acceptance gates. The two non-SDF
cases additionally gate that the initial zero contour is materially
non-circular and that the field gradient is materially non-unit. Raw implicit
residual magnitude is retained only as a diagnostic because it changes under
field rescaling; the comparable geometric residual is `|F| / ||grad F||`.

The random-feature case is a small topology-constrained neural implicit. Its
seeded tanh features are fixed, while center, base radius, and four output
weights are optimized. Bounds guarantee one positive star-shaped radial zero
contour. It is not a claim that an arbitrary randomly initialized SIREN is
valid: a seeded unconstrained MLP is covered by an expected-failure regression
and is rejected during contour validation before either forward solver runs.

## Reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model ellipse \
  --max-iterations 8 \
  --output-dir results/inverse_solver_comparison/wrong-ellipse-mie-20260902 \
  --overwrite

OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model random_features \
  --max-iterations 16 --loss-tolerance 1e-14 \
  --output-dir results/inverse_solver_comparison/random-feature-implicit-mie-20260902 \
  --overwrite
```

Detailed configuration, per-frequency errors, solver residuals, model state,
trajectories, plots, and provenance are in each dated subdirectory.
