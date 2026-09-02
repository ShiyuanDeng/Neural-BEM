# Solver comparisons

This is the test family that measures actual forward-solver quantities:
relative scattered-field error, linear-system residual, condition number, and
wall-clock time. It compares `gpr_bem_ref`, `gpr_bem_mod`, retained k-difference
rows, independent Nyström/Mie references where available, and cached gprMax
cross-checks.

The `archived_qbx/` helper is used only with `--include-qbx-archive`. Those rows
reproduce closed negative-result evidence and are not production candidates.
The checked snapshot lives under
[`../../results/solver_comparisons/legacy/qbx-closeout-20260901/`](../../results/solver_comparisons/legacy/qbx-closeout-20260901/).
