# Documentation map

Last reconciled: 2026-09-02.

This page is the navigation entry point. It does not own implementation
details; each fact should have one canonical document below.

## Start here

| Document | Status | Owns |
|---|---|---|
| [`current_architecture.md`](current_architecture.md) | Living, normative | What the repository does today: scope, pipelines, defaults, solver roles, validation, and limitations |
| [`solver_neutral_inverse.md`](solver_neutral_inverse.md) | Implemented baseline | Common ordered geometry, MOD/Kress numerical inverse, reproduction command, measured recovery, and scalability limits |
| [`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md) | Living plan | Remaining ordered-boundary/Kress implementation sequence and acceptance gates |
| [`validation_change_log.md`](validation_change_log.md) | Append-only history | What changed, what was run, what was measured, and what decision followed |
| [`qbx_closure.md`](qbx_closure.md) | Closed decision record | Why compressed-cloud QBX/kdiff stopped, retained artifacts, qualifications, and reopening criteria |

If a historical document disagrees with `current_architecture.md` about the
present, the architecture page wins. If it disagrees about what happened in a
past experiment, the dated validation entry and stored artifacts win.

## Active technical references

| Document | Role |
|---|---|
| [`ibim_shape_derivative.md`](ibim_shape_derivative.md) | Mathematics and code mapping for the current `gpr_bem_mod` shape derivative |
| [`solver_neutral_inverse.md`](solver_neutral_inverse.md) | Audited low-dimensional implicit-initialization inverse using one Method-B curve and either MOD or Kress |
| [`nystrom_reference_study.md`](nystrom_reference_study.md) | Independent smooth-boundary forward precision oracle |
| [`sdf_boundary_parameterization_implementation.md`](sdf_boundary_parameterization_implementation.md) | Implemented isolated SDF-to-smooth-boundary A/B/C experiment, architecture verdict, commands, and measured convergence |
| [`neural_sdf_to_kress_implementation_guide.md`](neural_sdf_to_kress_implementation_guide.md) | Authoritative scope and numerical protocol for that experiment |
| [`muller_blocks_implementation_guide.md`](muller_blocks_implementation_guide.md) | Scope, numerical protocol, and acceptance ladder used for the ordered forward backend |
| [`gpr_bem_kress_implementation.md`](gpr_bem_kress_implementation.md) | Experimental sibling-solver record: architecture, exact conventions, Kress split, forward/receiver APIs, future adjoint seam, and limitations |
| [`deep-research-report.md`](deep-research-report.md) | Design background and literature review; not blanket implementation scope |
| [`gprmax_reference_study.md`](gprmax_reference_study.md) | Independent cached FDTD physics cross-check |
| [`../results/sdf_boundary_parameterization/smoke-20260902/metrics.csv`](../results/sdf_boundary_parameterization/smoke-20260902/metrics.csv) | Checked smoke evidence for geometry/parameterization only; not solver errors |
| [`../results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md`](../results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md) | Readable manufactured scalar Kress-action error/runtime table; not a BIE solve |
| [`../results/sdf_boundary_parameterization/study-20260902/metrics.csv`](../results/sdf_boundary_parameterization/study-20260902/metrics.csv) | Full SDF-boundary grid/sample/bandwidth study; geometry metrics, not solver errors |
| [`../results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md) | Skimmed physical Müller block/trace/receiver error and runtime evidence for exact and frozen Method-B curves |
| [`../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md`](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md) | Dated five-shape solver-error evidence and archived QBX closeout rows |
| [`../results/inverse_solver_comparison/README.md`](../results/inverse_solver_comparison/README.md) | Checked MOD/Kress recovery from circle, ellipse, and random-feature implicit initializations against analytic Mie data |
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
- Put generated measurements under `results/`, grouped by experiment family
  and dated run; keep `pytest/` for tests. Do not hand-copy measurements into
  multiple live documents.
