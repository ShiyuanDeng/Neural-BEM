# Historical and superseded evidence

Archiving an implementation does not abandon its scientific question.
**Strict MLP + Method B remains the pipeline to fix.** These records show
where earlier implementations failed or were superseded, so the repair can
be assessed against actual evidence.

| Directory | Why it is historical |
|---|---|
| [inverse/mlp_feedback](inverse/mlp_feedback) | Earlier MLP-owned accepted geometry and modal/fitting feedback implementations |
| [inverse/normal_updates](inverse/normal_updates) | Pre-radial canonical curves, local normal modes, continuation and remeshing diagnostics |
| [inverse/siren_parameter_fd](inverse/siren_parameter_fd) | Small direct network-weight finite-difference experiment and one empty output folder |
| [development/representation_policy](development/representation_policy) | Early final export used the wrong 1.5 mm tolerance; its success status is superseded |
| [development/smooth_distance_supervision](development/smooth_distance_supervision) | Earlier extraction/audit study superseded by the refined bundle |
| [development/kress_shape_derivative](development/kress_shape_derivative) | Earlier zero-contrast audit scale; corrected 96/96 evidence is under validation |
| [solver_experiments](solver_experiments) | Closed QBX/kdiff comparison records |

Original measurements, failed rows, configurations, and commands remain
intact. Matching root logs were moved alongside their original bundles as
`stdout.log`. Do not replay old commands against new defaults and relabel
that as the same historical algorithm. Current diagnostics and pending
repair runs are separated in [reproduction](../../docs/reproduction.md).

Use the [catalogue](../README.md) for exact pipeline variants, scenes, dates,
limitations, and implications for [strict MLP + Method B](../../docs/pipelines/strict_mlp_method_b.md).
