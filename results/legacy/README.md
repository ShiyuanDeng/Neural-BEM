# Historical and superseded evidence

These records retain superseded implementations and known-shape-family controls.
The current inverse pipelines are **Implicit MLP + Method B** and
**Explicit Radial Fourier**. Their results and current recovery status are
indexed under [inverse](../inverse/README.md).

| Directory | Why it is historical |
|---|---|
| [known_shape_family_parameter_inverse](known_shape_family_parameter_inverse/README.md) | Former `results/inverse/method_b`: 3–7 shape parameters with supplied circle/ellipse/five-lobe/radial-feature families; not full-MLP recovery. Measurements and videos preserved. |
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
limitations, and implications for [Implicit MLP + Method B](../../docs/pipelines/implicit_mlp.md).
