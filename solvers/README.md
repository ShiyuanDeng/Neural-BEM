# Solvers

| Package | Role |
|---|---|
| [`bem_inverse/`](bem_inverse/README.md) | The inverse pipeline: problem, policy, runner, modal Müller physics, geometry updates |
| [`gpr_bem_kress/`](gpr_bem_kress/README.md) | Nodal Kress/Nyström Müller solver; generated the TG-002 data and serves as the `nodal_kress` control |
| [`ordered_boundary/`](ordered_boundary/README.md) | Ordered periodic curve geometry and validity checks |
| `periodic_kress/` | Periodic Kress logarithmic quadrature weights |

Set `PYTHONPATH=solvers:.` from the repository root. Other solver packages were removed
on this branch and remain on `feature/shape-frequency-continuation`.
