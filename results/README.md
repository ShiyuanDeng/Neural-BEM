# Generated results

All generated measurements are consolidated here; tests live under
[`../pytest/`](../pytest/).

| Directory | Evidence type | Solver errors? |
|---|---|---:|
| `sdf_boundary_parameterization/` | implicit zero-set geometry, A/B/C curve quality, and manufactured scalar log-quadrature proxy | **No** |
| `ordered_boundary_nystrom/` | opt-in `PeriodicCurve2D` Müller/Kress block, solve, receiver-convergence, and runtime evidence | **Yes** |
| `solver_comparisons/` | BIE/FDTD/Nyström field comparisons, solve residuals, condition numbers, and runtime | **Yes** |
| `inverse_solver_comparison/` | checked solver-neutral MOD/Kress implicit inverse trajectories and held-out errors | **Yes** |
| [`sdf_representation_ablation/`](sdf_representation_ablation/README.md) | identical-data strict/curve-only/final-export inverse policies, separate work and delivery status | **Yes** |
| [`smooth_distance_supervision/task-b-circle-star-refined-20260905/`](smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md) | frozen polygon versus continuous-distance labels, neural fit/extraction and refined fields | **Yes** |
| [`parameterization_aware/first-batch-20260905/`](parameterization_aware/first-batch-20260905/summary.md) | exact ellipse control and ordered-label K/N experiment, including failed fits | **Yes** |
| [`kress_shape_derivative/`](kress_shape_derivative/README.md) | Complete discrete geometry/material JVP and paired-objective adjoint; independent reference and physical refinement | **Yes** |
| [`distance_tangency/first-batch-20260906/`](distance_tangency/first-batch-20260906/README.md) | Exact/distorted/neural distance contacts versus zero-projection and tangent controls; negative results and explicit fallbacks | **Yes** |
| [`neural_metric/comparison-20260906/`](neural_metric/comparison-20260906/summary.md) | Frozen neural tangent metrics versus identity/Sobolev; bounded progress, numerical refinement and held-out errors | **Yes** |
| [`material_inverse/bounded-20260906/`](material_inverse/bounded-20260906/README.md) | Single interior-permittivity and joint radial-K2 recovery; noisy data, derivative checks and retained failed starts | **Yes** |
| [`material_robustness/bounded-20260906/`](material_robustness/bounded-20260906/README.md) | Frozen difficult-start full-band/continuation/multistart recovery controls; independent opposite-contrast noncircular target and sealed training-only selection | **Yes** |
| `multicomponent_split_demo/` | automatic unknown-`M` one-circle to two-circle extraction, ragged trajectory, and endpoint multi-Kress check | **Yes, except the explicitly unsolved pinch frame** |
| `rectangular_loop_forward*/` | end-to-end forward-driver outputs | Yes |
| `ibim_geometry_demo/` | geometry demonstration | No |

Within `sdf_boundary_parameterization/`, `smoke-20260902/` is the compact
checked run, `study-20260902/` is the full convergence sweep, and
`kress-scalar-proxy-20260902/` is a scalar manufactured quadrature check. The
last directory is intentionally not under `ordered_nystrom`: no Nyström BIE
backend or PDE solve was exercised.

The checked five-shape QBX closeout is historical and therefore lives under
`solver_comparisons/legacy/qbx-closeout-20260901/`. New aggregate solver runs
write to `solver_comparisons/current/`.

Run `python run_ordered_nystrom_validation.py --preset quick` from the
repository root to create a timestamped circle/ellipse/star validation under
`ordered_boundary_nystrom/`. Its CSV, JSON, and Markdown files contain scalar
metrics only; the driver does not persist dense operators or solution arrays.
Start with the
[`ordered_boundary_nystrom/README.md`](ordered_boundary_nystrom/README.md)
index for the checked exact-curve and frozen Method-B error/runtime tables.
