# SDF-to-ordered-boundary tests

This folder tests the isolated implicit-field-to-smooth-curve conversion
study. It is parallel to the package at
[`../../solvers/sdf_to_ordered_boundary/`](../../solvers/sdf_to_ordered_boundary/),
not part of `gpr_bem_mod`, `gpr_bem_kdiff`, or another forward solver.

## Measurement boundary

No test here assembles a Helmholtz/Müller BIE, solves a boundary density, or
computes receiver/scattered fields. Consequently, none of its reported errors
is a solver error.

- `test_sdf_boundary_frontend.py` through `test_sdf_boundary_experiment.py`
  cover contour extraction, projection, A/B/C parameterizations, topology,
  geometry, serialization, and runtime accounting.
- `test_sdf_boundary_isolation.py` proves the package is not imported by the
  active solver pipelines and adapts only to the solver-neutral geometry
  contract.
- `test_sdf_boundary_kress_proxy.py` checks Kress weights and one manufactured
  scalar logarithmic integral. Its “scalar-action error” is not a four-block
  operator, density, or PDE solution error.
- `test_result_scope.py` locks those statements into the checked manifests and
  verifies their paths and hashes.

The legacy JSON/CSV field `sdf_residual` means `F(gamma(t))`; for generic
implicit ellipse/star fixtures, it is not a signed-distance error. Its
gradient-normalized form is a first-order distance proxy. The legacy
`kress_diagonal` field is a local removable-log consistency check, not a test
of a production Kress solver.

Actual solver-error comparisons are under
[`../solver_comparisons/`](../solver_comparisons/).
