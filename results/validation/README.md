# Supporting validation

| Family | What was measured |
|---|---|
| [Topology treatments](topology/README.md) | Candidate-allocation comparisons, selective-policy qualification and audited BIE work |
| [Implicit MLP adjoint](implicit_mlp_adjoint/README.md) | Kress geometry reverse, Method-B reverse and full neural gradients; early inverse runs retain failed recovery gates |
| [SDF boundary parameterization](sdf_boundary_parameterization) | Methods A/B/C geometry and a manufactured scalar quadrature proxy |
| [Ordered Nyström](ordered_boundary_nystrom/README.md) | Exact/frozen fitted curves, physical blocks, receiver fields and refinement |
| [Solver comparisons](solver_comparisons) | Forward field comparisons; includes undated overwrite-style current outputs |
| [Parameterization-aware fits](parameterization_aware/first-batch-20260905/summary.md) | Geometry labels, fitting and physical-field controls |
| [Distance/tangency](distance_tangency/first-batch-20260906/README.md) | Continuous-query conversion controls and negative results |
| [Kress derivatives](kress_shape_derivative/README.md) | Discrete JVP/adjoint and independent physical refinement |

These isolate numerical requirements for [Implicit MLP + Method B](../../docs/pipelines/implicit_mlp.md)
and [Explicit Radial Fourier](../../docs/pipelines/explicit_radial_fourier.md).
Forward or geometry success is not an inverse-recovery result. Superseded
validation attempts are preserved in [legacy development](../legacy/README.md).

The old `results/sdf_boundary_parameterization` path is a compatibility
symlink to this geometry family. Its recorded relative paths and hashes, and
the existing user-edited notebook, remain valid. The [catalogue](../README.md)
counts the real directory once.
