# Documentation map

Reorganized 2026-09-07. **Strict MLP + Method B is the pipeline to repair.**
Radial Fourier, fitting, material, and metric experiments supply evidence for
that work; they do not replace the research objective.

| Start here | Owns |
|---|---|
| [Current architecture](current_architecture.md) | Implemented capabilities, defaults, and agreed direction |
| [Strict MLP + Method B](pipelines/strict_mlp_method_b.md) | Intended geometry ownership, existing controls, failure evidence, and repair gates |
| [Radial Fourier and MLP policies](pipelines/radial_fourier.md) | Geometry ownership, fitting/export ablations, and frozen neural metrics |
| [Shape/material experiments](pipelines/shape_material.md) | Derivative, material, continuation, and restart evidence |
| [Results catalogue](../results/README.md) | Actual runs, scenes, dates, outcomes, provenance, and implications for the strict pipeline |
| [Reproduction commands](reproduction.md) | User-run checks and diagnostics; pending repair experiments are distinguished |

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
