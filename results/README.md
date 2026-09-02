# Generated results

All generated measurements are consolidated here; tests live under
[`../pytest/`](../pytest/).

| Directory | Evidence type | Solver errors? |
|---|---|---:|
| `sdf_boundary_parameterization/` | implicit zero-set geometry, A/B/C curve quality, and manufactured scalar log-quadrature proxy | **No** |
| `ordered_boundary_nystrom/` | opt-in `PeriodicCurve2D` Müller/Kress block, solve, receiver-convergence, and runtime evidence | **Yes** |
| `solver_comparisons/` | BIE/FDTD/Nyström field comparisons, solve residuals, condition numbers, and runtime | **Yes** |
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
