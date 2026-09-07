# Solvers and inverse implementations

The current research objective is to [repair strict MLP + Method B](../docs/pipelines/strict_mlp_method_b.md).
See the [architecture](../docs/current_architecture.md) for supported scope and
[results catalogue](../results/README.md) for measured evidence. Radial shape,
representation and material experiments supply diagnostics for that repair.

## Package ownership

| Package | Role |
|---|---|
| `gpr_bem_ref` | Frozen original and selector default |
| `gpr_bem_mod` | Maintained compressed-cloud forward, older neural B-scan adjoint, and ordered inverse comparison peer |
| `gpr_bem_kress` | Ordered Müller/Kress forward, multi-component assembly and opt-in single-interface discrete derivatives |
| `ordered_boundary` | Continuous exact/Fourier producers and immutable ordered BIE node geometry |
| `periodic_kress` | Shared periodic logarithmic product weights |
| `sdf_to_ordered_boundary` | Extraction/projection, Methods A/B/C, and experimental conversion studies |
| `sdf_inverse` | Implicit-parameter, direct-curve, neural representation, metric, and material experiments |
| `sdf_bem_multicomponent` | Automatic loop extraction, multi-Kress forward, and prescribed split demonstration |
| `nystrom_ref` | Independent smooth-boundary forward oracle |
| `multicylinder_ref` | Independent multiple-cylinder oracle |
| `gprmax_ref` | Cached FDTD physics cross-check |
| `kernel_diff_ref` | Perfect-sampling circle diagnostic |
| `gpr_bem_kdiff`, `gpr_bem_qbx` | Frozen/archived compressed-cloud operator experiments |
| `gpr_bem_ndiff` | Unsupported normal-offset experiment |

Solver-specific operators and materials stay in their solver packages.
`PeriodicCurve2D` supplies the common ordered geometry to Kress, or copied
nodes, normals and weights to the MOD adapter. Kress has its own material
value type and is not a MOD submodule.

## Selector-backed and direct-import paths

`solver_select.py` aliases either REF or MOD to `gpr_bem` for older drivers
and shared tests. `--solver` overrides the `SOLVER` environment variable;
if both are absent, REF is selected. Use `--solver=mod` explicitly for MOD.
The two remain separate packages so a comparison can
import both in one interpreter. Kress is a direct import, not a selector alias.

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
python -m pytest pytest/gpr_bem_shared --solver=mod
```

The rectangular forward output goes under
`results/demos/rectangular_loop_forward_{ref,mod}`. Older B-scan inverse
output goes under `results/legacy/inverse/ibim/`.
These commands are for the user; no solver or test was run during cleanup.

## Current inverse entry points

| Driver | Actual geometry ownership and derivative |
|---|---|
| `run_sdf_inverse_comparison.py` | Implicit-model parameters; extraction and Method B at every finite-difference evaluation |
| `run_mlp_sdf_inverse_comparison.py` | Explicit radial state; finite differences and strict MLP fitting/audits |
| `run_sdf_representation_ablation.py` | Explicit radial state; strict, curve-only and final-export policies |
| `run_neural_metric_comparison.py` | Explicit radial state; Kress objective adjoint and frozen neural metrics |
| `run_material_inverse_comparison.py` | Fixed or radial-K2 shape and one interior permittivity; analytic Kress derivatives |
| `run_material_robustness_comparison.py` | Same shape/material model; training-only continuation and bounded restarts |

The main MLP driver's `legacy_strict` policy does not reinstate MLP-owned
accepted geometry. Method B remains in its initialization and representation
audits. The strict repair needs an explicit accepted-state and physical
objective contract; see [the repair plan](../docs/pipelines/strict_mlp_method_b.md).

The complete discrete Kress derivative now exists, but implicit-parameter
and radial comparison drivers retain their finite-difference Jacobians.
Its fixed-correspondence derivative is not automatically the derivative of
MLP weights through extraction, Method-B fitting, and remeshing.

## Detailed documentation and reproduction

- [Runnable diagnostic commands](../docs/reproduction.md).
- [Radial ownership and MLP policies](../docs/pipelines/radial_fourier.md).
- [Shape/material and derivative controls](../docs/pipelines/shape_material.md).
- [Geometry foundation](ordered_boundary/README.md) and [Kress implementation](gpr_bem_kress/README.md).
- [Technical references](../docs/reference/README.md).
- [Historical inverse development](../docs/reports/inverse_development_through_2026-09-06.md).
- [Closed QBX decision](../docs/legacy/qbx_closure.md).

Keep failed runs and exact original source/observation identities. A new run
gets a fresh directory under its actual pipeline, rather than overwriting a
historical bundle or promoting progress-only acceptance into a recovery claim.
