# Solver comparisons

This is the test family that measures actual forward-solver quantities:
relative scattered-field error, linear-system residual, condition number, and
wall-clock time. It compares `gpr_bem_ref`, `gpr_bem_mod`, the sibling
`gpr_bem_kress` solver on smooth one-component cases, retained k-difference
rows, independent Nyström/Mie references where available, and cached gprMax
cross-checks.

For circle, ellipse, and star, MOD and Kress receive the exact same Torch
implicit-field callable. MOD constructs its compressed IBIM cloud; Kress uses
the shared marching-squares/Newton front end and Method B (`M=256`, Fourier
bandwidth `K=48`) before discretizing `N=128` periodic nodes. Both report the
relative L2 error of all 24 paired receiver fields against Mie/Nyström truth.
Their index-0 errors and direct discrepancies against cached gprMax are also
retained so there is an honest one-pair common coverage comparison.

The existing gprMax caches contain only the index-0 Tx/Rx pair. They describe
the same analytic target zero set, but were generated from gprMax's analytic or
voxelized shape description rather than by evaluating the Torch callable.
Consequently they are an independent one-pair FDTD cross-check, not a 24-pair
L2 result and not literally the same sampled-SDF branch.

Every exported solver row separates error coverage from receiver workload:

- `error_pair_count` is the number of paired fields entering the reported
  error (`24` for the smooth MOD/Kress L2 rows, `1` for pair-0 checks, and `0`
  for a timing-only row);
- `num_sources`, `num_receivers`, and `internal_receiver_matrix_shape` state
  the work actually evaluated (`receiver_matrix_shape` is a compatibility
  alias); MOD/ref/Kress materialize a full matrix, while `gpr_bem_kdiff`
  evaluates the paired receiver vector directly;
- `reported_field_shape` and `receiver_selection` state what was retained; and
- `receiver_evaluation_scope` explains which entries were retained.

`pair_count` remains only as a compatibility alias for `error_pair_count` in
older notebooks. Each per-scene `metrics.json` also carries the bounds, grid,
target parameters, material constants, exact Tx/Rx coordinates, SDF identity,
and Kress component ID needed to interpret the arrays without test-module
context.

Run the complete same-SDF peer comparison and regenerate the readable tables
with:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 \
python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py -s -q
```

The `archived_qbx/` helper is used only with `--include-qbx-archive`. Those rows
reproduce closed negative-result evidence and are not production candidates.
The checked snapshot lives under
[`../../results/solver_comparisons/legacy/qbx-closeout-20260901/`](../../results/solver_comparisons/legacy/qbx-closeout-20260901/).
