# Documentation map

Last reconciled: 2026-09-02.

This page is the navigation entry point. It does not own implementation
details; each fact should have one canonical document below.

## Start here

| Document | Status | Owns |
|---|---|---|
| [`current_architecture.md`](current_architecture.md) | Living, normative | What the repository does today: scope, pipelines, defaults, solver roles, validation, and limitations |
| [`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md) | Living plan | The only active implementation sequence for the next forward backend |
| [`validation_change_log.md`](validation_change_log.md) | Append-only history | What changed, what was run, what was measured, and what decision followed |
| [`qbx_closure.md`](qbx_closure.md) | Closed decision record | Why compressed-cloud QBX/kdiff stopped, retained artifacts, qualifications, and reopening criteria |

If a historical document disagrees with `current_architecture.md` about the
present, the architecture page wins. If it disagrees about what happened in a
past experiment, the dated validation entry and stored artifacts win.

## Active technical references

| Document | Role |
|---|---|
| [`ibim_shape_derivative.md`](ibim_shape_derivative.md) | Mathematics and code mapping for the current `gpr_bem_mod` shape derivative |
| [`nystrom_reference_study.md`](nystrom_reference_study.md) | Independent smooth-boundary forward precision oracle |
| [`sdf_boundary_parameterization_implementation.md`](sdf_boundary_parameterization_implementation.md) | Implemented isolated SDF-to-smooth-boundary A/B/C experiment, architecture verdict, commands, and measured convergence |
| [`neural_sdf_to_kress_implementation_guide.md`](neural_sdf_to_kress_implementation_guide.md) | Authoritative scope and numerical protocol for that experiment |
| [`deep-research-report.md`](deep-research-report.md) | Design background and literature review; not blanket implementation scope |
| [`gprmax_reference_study.md`](gprmax_reference_study.md) | Independent cached FDTD physics cross-check |
| [`../pytest/results/aggregate_metrics.md`](../pytest/results/aggregate_metrics.md) | Generated five-shape numerical evidence |
| [`../solvers/README.md`](../solvers/README.md) | Package selection and experiment reproduction |
| [`../pytest/README.md`](../pytest/README.md) | Test layout, gates, and evidence commands |

## Legacy records

Superseded plans and dated assessments live in [`legacy/`](legacy/README.md).
They remain versioned because their reasoning, negative results, and original
measurements are useful. Their present-tense language is not current guidance.

## Maintenance rules

- Update `current_architecture.md` in the same change that alters a live
  pipeline, default, solver role, or limitation.
- Keep the ordered-boundary task list only in
  `ordered_boundary_nystrom_plan.md`; other documents link to it.
- Append validation entries with date, hypothesis, change, command, measured
  result, and decision. Do not rewrite old conclusions into new ones.
- Keep decision records stable after closure. Add a dated amendment if a
  decision is reopened.
- Put generated measurements under `pytest/results/`; do not hand-copy them
  into multiple live documents.
