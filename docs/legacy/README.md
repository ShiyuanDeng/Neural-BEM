# Legacy plans and closed investigations

These files retain earlier reasoning and implementation instructions.
The current pipelines are [Implicit MLP + Method B](../pipelines/implicit_mlp.md)
and [Explicit Radial Fourier](../pipelines/explicit_radial_fourier.md).
See the [current architecture](../current_architecture.md) for their implementation
and recovery status. Method B remains the neural pipeline's contour conversion.

| Record | Classification |
|---|---|
| [ordered_boundary_nystrom_plan.md](ordered_boundary_nystrom_plan.md) | Earlier ordered-forward roadmap; current inverse descriptions live in the pipeline pages |
| [codex_sdf_kress_priorities_2026-09-05.md](codex_sdf_kress_priorities_2026-09-05.md) | Original task brief; subsequent work is recorded in dated reports |
| [qbx_closure.md](qbx_closure.md) | Closed compressed-cloud QBX/kdiff decision |
| [forward_solver_validation.md](forward_solver_validation.md) | Historical August forward-solver assessment |
| [adjoint_inverse_rebuild_plan.md](adjoint_inverse_rebuild_plan.md) | MOD plan that became an implementation record |
| [ibim_error_mitigation_literature_codex.md](ibim_error_mitigation_literature_codex.md) | Literature plus superseded roadmaps |
| [square_target_oracle_options.md](square_target_oracle_options.md) | Deferred corner/oracle research |

Original dated commands remain historical commands. Use
[reproduction](../reproduction.md) for runnable commands with organized output paths.

The [Legacy known-shape-family controls](known_shape_family_controls.md)
explain the archived parametric Method-B results and their supplied geometry priors.
They recover 3 circle, 4 ellipse, 5 star or 7 frozen-random-feature parameters
within prescribed families. The star fixes five lobes; its unknown center,
radius, amplitude and rotation are still recovered from observations. These
are not full-MLP reconstructions. The two current inverse result groups are
[implicit MLP](../../results/inverse/implicit_mlp) and
[radial Fourier](../../results/inverse/radial_fourier).
