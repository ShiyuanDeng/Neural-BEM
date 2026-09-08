# Documentation map

Updated 2026-09-08. The current inverse pipelines are **Implicit MLP + Method B**
and **Explicit Radial Fourier**. The implicit adjoint gradient is validated;
the [iteration 2 comparison](iterations/implicit_mlp/iteration_02/README.md) has
two completed 12-pair cases that fail recovery acceptance and one execution
failure. Radial
canonical recovery works on recorded cases; its MLP representation gates
remain separate. These are not matched benchmark results.

| Start here | Owns |
|---|---|
| [Current architecture](current_architecture.md) | Implemented capabilities, defaults, and agreed direction |
| [Implicit MLP + Method B](pipelines/implicit_mlp.md) | Neural adjoint implementation, geometry ownership, derivative checks, and remaining accuracy gates |
| [Implicit MLP diagnostics](implicit_mlp_diagnostics.md) | Frozen conversion, controlled Eikonal activation, and one-update transfer; contract tests run, experiments not yet run |
| [Experiment iterations](iterations/README.md) | Complete per-iteration results, possible fixes, ChatGPT guides, discussion and final reviews |
| [Explicit Radial Fourier](pipelines/explicit_radial_fourier.md) | Explicit curve ownership, fitting/export ablations, and frozen neural metrics |
| [Explicit Radial Fourier shape/material experiments](pipelines/explicit_radial_shape_material.md) | Radial variant with an unknown interior permittivity; derivative, continuation, and restart evidence |
| [Results catalogue](../results/README.md) | Actual runs, scenes, dates, outcomes, and provenance for both pipelines and their controls |
| [Reproduction commands](reproduction.md) | Neural adjoint inverse, gradient checks and separate controls |
| [Legacy known-shape-family controls](legacy/known_shape_family_controls.md) | Prescribed family parameter inverses and why they are distinct from full-MLP recovery |

Active inverse results live under `results/inverse/implicit_mlp/` and
`results/inverse/radial_fourier/`; the latter includes shape/material and
frozen-metric experiments. The old Method-B controls are archived as
[known-shape-family parameter inverses](../results/legacy/known_shape_family_parameter_inverse).
These **Legacy known-shape-family controls** estimate 3, 4, 5 or 7 controls in
prescribed families, not a full neural field. The neural `--optimizer
parameter_fd` reference remains part of Implicit MLP + Method B; it updates
network weights. Finite-difference derivative checks are a third use and do
not establish a matched inverse benchmark.

## Detailed records

- [Technical references](reference/README.md): mathematics, geometry, solvers,
  and validation protocols. Check dated implementation claims against the current map.
- [Dated reports](reports/README.md): original numerical conclusions in their
  historical context, including negative results and earlier recommendations.
- [Legacy plans and solver work](legacy/README.md): superseded work orders,
  archived approaches, and closed decisions.
- [Validation change log](reports/validation_change_log.md): chronological
  commands and measurements; historical commands retain their original paths.
- [Test layout](../pytest/README.md) and [solver layout](../solvers/README.md).

## Maintenance

Update the architecture and relevant pipeline page when implementation changes.
Use the results catalogue as the entry point for measurements rather than
copying tables into several living documents. Preserve original run IDs,
commands, observations, source hashes, and failed arms; new measurements get
fresh output directories. Label inferred dates and absent audits explicitly.

The [relocation map](../results/relocations.json) maps old paths to organized
locations. One geometry compatibility alias preserves recorded artifact paths
and the existing notebook without modifying its user edits.
