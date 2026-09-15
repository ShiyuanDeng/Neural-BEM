# Idea 3 review — BIE-006

2026-09-15. Owner: Codex. Review: self-review; no independent reviewer assigned.
The user authorized the proposed bounded Idea 3 trial with “then go”. This
supersedes its historical deferred status and does not authorize a branch.

- **Accept:** compare exact E, tangent-data T and first-order operator O in
  native nodal coordinates with the existing single-interface derivative.
- **Accept:** charge a new factorization for every O prediction. Retain ordinary
  T as the comparator; solving a linearized operator is not a second-order model.
- **Accept:** saved geometry changes, no truth-selected directions. Use TOP-012
  H/central-ellipse-star trajectory row 1, the first updated noncircular state,
  and cumulative displacements to rows 2, 3, 4. These share component, chart,
  bandwidth and cycle. This is a local replay, not the original inverse.
- **Accept with explicit amendment:** 60 exact assemblies instead of the
  packet's suggested 48: 52 base/candidate evaluations including refinement,
  two production parity checks, six timing evaluations. Analytic cap stays 24.
  Every candidate gets its own refined reference; no enlarged scene suite.
- **Defer:** optional P. No reusable Krylov path is needed for the scientific
  comparison, so no new iterative solver will be built.
- **Accept:** finite-reuse accounting, including base setup, derivatives,
  geometry validation and separately identified exact validation costs.
- **Accept:** stop this first-order approach if it matches T at higher cost or
  cannot provide useful repeatable range and credible finite-reuse savings.
- **Defer:** higher orders, full Jacobian caching, inverse/controller integration,
  shared solver changes, multi-component reuse and topology-event transport.

## File/API map before implementation

Read-only production APIs: `ordered_boundary.fourier_curve`,
`validate_periodic_parameterization`, Kress `system`/`forward` factories,
`KressTMzForwardResult`, and `shape_derivative._directional_operators`.
Use SciPy LU factors and batched solves; no explicit inverses.

New experiment files only: `experiments/bie006_operator_reuse/` containing
fixture extraction, counted wrappers, E/T/O driver, algebra tests and saved-table
reporting. BIE-only plan, handoff and closeout changes. Protect imported solver
sources by hashes and stop on drift. Record concurrent numerical workers.

Tests before physical execution check first-order consistency using an
independently constructed polynomial operator family, exactness of O for affine
operators, fixed Fourier displacement correspondence, and finite break-even
handling. Physical parity/refinement checks belong to the counted campaign.
