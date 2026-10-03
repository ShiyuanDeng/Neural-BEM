# Legacy plans and closed investigations

These files retain earlier reasoning and implementation instructions.
Use the [repository guide](../../README.md) and
[maintained cleaned inverse](../../solvers/bem_inverse/README.md) for the active
code map. Historical plans and status statements below retain their dated scope.

| Record | Classification |
|---|---|
| [repository_overview_2026-10-03.md](repository_overview_2026-10-03.md) | Previous root README, preserved before package isolation |
| [dashboard_2026-10-03.md](dashboard_2026-10-03.md) | Previous research dashboard, preserving dated track status and decisions |
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
