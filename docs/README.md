# Documentation map

Use the [repository guide](../README.md) for the active code map and the
[maintained cleaned inverse](../solvers/bem_inverse/README.md) for its API,
dependencies, and checks. Read the guides relevant to the task; the dated
research records below retain their original scope.

## Implementation and reproduction

| Task | Guide |
|---|---|
| Develop or call the cleaned SC/MA inverse | [bem_inverse](../solvers/bem_inverse/README.md) |
| Prepare, inspect, or reproduce cleaned-interface campaigns | [Campaign commands and numerical limits](../experiments/cleaned_interface/README.md) |
| Understand solver and reference packages | [Solver map](../solvers/README.md) |
| Run package/solver regressions | [Validation guide](../pytest/README.md) |
| Work on implicit MLP, Cartesian, or radial inverse paths | [Implicit MLP](pipelines/implicit_mlp.md), [Cartesian Fourier](pipelines/explicit_cartesian_fourier.md), [radial Fourier](pipelines/explicit_radial_fourier.md) |
| Reproduce continuation research | [Shape/frequency continuation](pipelines/shape_frequency_continuation.md) |
| Reproduce older pipeline comparisons | [Reproduction commands](reproduction.md) |

## Research and evidence

- [Cleaned-interface track](iterations/cleaned_interfaces/README.md): CI, NU,
  and node-free reviews; historical FM-001/FM-002 records remain there.
- [Relaxed-BIE track](iterations/relaxed_bie/README.md): current interpretation,
  mathematical/evidence links, literature and GPU review, and the
  RB-001 numerical-resolution follow-up.
- [Results catalogue](../results/README.md): saved runs, including failures.
- [Iteration index](iterations/README.md): dated plans, decisions, and reports.
- [Research reports](reports/README.md) and [October 2 exploration](reports/exploration_2026-10-02.md).
- [Baselines](baselines/README.md), [technical references](reference/README.md),
  and [legacy records](legacy/README.md).
- [Broader architecture record](current_architecture.md): existing geometry and
  solver paths; use the package guide for the extracted cleaned-interface layout.

The [previous dashboard](legacy/dashboard_2026-10-03.md) and
[previous repository overview](legacy/repository_overview_2026-10-03.md) preserve
the former landing pages. Their dated status and approval statements are
historical records, not a replacement for the current task instructions.
