# Supporting validation

| Family | What was measured |
|---|---|
| [SDF boundary parameterization](sdf_boundary_parameterization) | Methods A/B/C geometry and a manufactured scalar quadrature proxy |
| [Ordered Nyström](ordered_boundary_nystrom/README.md) | Exact/frozen fitted curves, physical blocks, receiver fields and refinement |
| [Solver comparisons](solver_comparisons) | Forward field comparisons; includes undated overwrite-style current outputs |
| [Parameterization-aware fits](parameterization_aware/first-batch-20260905/summary.md) | Geometry labels, fitting and physical-field controls |
| [Distance/tangency](distance_tangency/first-batch-20260906/README.md) | Continuous-query conversion controls and negative results |
| [Kress derivatives](kress_shape_derivative/README.md) | Discrete JVP/adjoint and independent physical refinement |

These isolate numerical requirements for [strict MLP + Method B repair](../../docs/pipelines/strict_mlp_method_b.md).
Forward or geometry success is not an inverse-recovery result. Superseded
validation attempts are preserved in [legacy development](../legacy/README.md).

The old `results/sdf_boundary_parameterization` path is a compatibility
symlink to this geometry family. Its recorded relative paths and hashes, and
the existing user-edited notebook, remain valid. The [catalogue](../README.md)
counts the real directory once.
