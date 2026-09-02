# Tests and validation

Tests mirror the package or study they own. Generated evidence lives only
under [`../results/`](../results/); `pytest/` contains no result bundles.

## Layout

| Directory | Responsibility | Uses solver-error metrics? |
|---|---|---:|
| `gpr_bem_shared/` | Selector-backed tests shared by frozen `ref` and operational `mod` | Yes, in system/theory tests |
| `gpr_bem_mod/` | MOD-only adjoint, inverse, and shape-derivative checks | Yes, except the kernel-identity test |
| [`gpr_bem_kress/`](gpr_bem_kress/) | Direct-import `PeriodicCurve2D` Kress/Müller blocks, system, receiver operator, and field validation | **Yes** |
| `gpr_bem_kdiff/` | Retained k-difference and archived QBX assembly seam | Operator/system checks |
| `gprmax_ref/` | gprMax cache identity and scene policy | No |
| `nystrom_ref/` | Independent smooth-boundary forward oracle | Yes |
| `ordered_boundary/` | Continuous and node-owned geometry contracts | **No** |
| [`sdf_to_ordered_boundary/`](sdf_to_ordered_boundary/) | Implicit-field extraction, A/B/C fits, geometry metrics, artifacts, and scalar Kress proxy | **No** |
| [`solver_comparisons/`](solver_comparisons/) | Circle, ellipse, square, star, and two-circle solver comparisons | **Yes** |

The distinction in the last three rows is deliberate. The ordered-boundary
and SDF-to-boundary suites stop before any Helmholtz/Müller operator assembly,
linear solve, boundary density, or receiver/scattered field. Their “errors”
are implicit zero-set residuals, geometric discrepancies, parameterization
diagnostics, or errors in one manufactured scalar logarithmic integral. The
dedicated cross-solver error tables and checked field-result bundles live in
`solver_comparisons/`; other solver-owned unit suites also test their own
systems and fields.

## Selector-backed IBIM tests

Only `gpr_bem_shared/` uses the bare `gpr_bem` alias selected by the root
`conftest.py`:

```bash
python -m pytest pytest/gpr_bem_shared -q                 # frozen ref
python -m pytest pytest/gpr_bem_shared --solver=mod -q    # operational mod
```

The root pytest header reports which alias is available. Other directories
either import an explicitly named package or are solver-independent.

MOD-only tests import `gpr_bem_mod` directly and need no selector flag:

```bash
python -m pytest pytest/gpr_bem_mod -q
```

## Geometry and parameterization tests

Run the complete solver-independent boundary suite with:

```bash
PYTHONPATH=solvers python -m pytest -q \
  pytest/ordered_boundary \
  pytest/sdf_to_ordered_boundary
```

The checked A/B/C evidence is consolidated under
[`../results/sdf_boundary_parameterization/`](../results/sdf_boundary_parameterization/):

- `smoke-20260902/`: small complete bundle with plots and native coefficients;
- `study-20260902/`: full grid/sample/bandwidth study; and
- [`kress-scalar-proxy-20260902/summary.md`](../results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md): manufactured scalar log-product-rule convergence and runtime.

Each manifest declares `contains_bie_assembly: false`,
`contains_linear_solve: false`, and `contains_solver_error_metrics: false`.
The historical schema names `sdf_residual` and `kress_diagonal` are retained
for compatibility: the former is an implicit-field zero-set residual (not all
fixtures are true distance fields), and the latter is only a removable-log
diagonal consistency diagnostic.

The ordered Kress sibling has its own solver-error suite:

```bash
PYTHONPATH=solvers python -m pytest -q pytest/gpr_bem_kress
```

It tests physical block actions, the coupled system, the explicit
`ExteriorReceiverOperator` (`C=[D,-S]`), boundary traces, and Mie receiver
fields. It does not turn the adjacent geometry-only metrics into solver errors
or register `gpr_bem_kress` with the normal solver selector.
The checked exact/noncircular and frozen Method-B convergence tables are
indexed at
[`../results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md).

Reproduce the scalar proxy from the checked compact coefficient bundles into
a new empty directory:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scratchpad/sdf_boundary_kress_proxy.py \
  --artifact-root results/sdf_boundary_parameterization/study-20260902 \
  --curve-root results/sdf_boundary_parameterization/\
kress-scalar-proxy-20260902/frozen_curves \
  --output-dir results/sdf_boundary_parameterization/kress-scalar-proxy-NEW \
  --timing-repeats 9
```

## Solver comparisons

Run the current solver/field comparisons with:

```bash
python -m pytest pytest/solver_comparisons/test_circle_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_ellipse_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_square_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_star_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_two_circle_comparison.py -s -q
python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py -s -q
```

The aggregate test writes current output to
`results/solver_comparisons/current/`. The checked QBX-inclusive closeout is
kept separately at
[`../results/solver_comparisons/legacy/qbx-closeout-20260901/`](../results/solver_comparisons/legacy/qbx-closeout-20260901/).
The compact checked MOD/Kress/gprMax result is
[`kress-peer-20260902/summary.md`](../results/solver_comparisons/kress-peer-20260902/summary.md).
Archived QBX rows are slow and opt-in:

```bash
python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py \
  --include-qbx-archive -s -q
```

The smooth circle, ellipse, and star modules are also the same-SDF integration
surface for `gpr_bem_kress`: the shared SDF is independently converted to a
MOD compressed cloud and a Method-B `PeriodicCurve2D`, then both BEM outputs
are compared on the same 24 paired receivers. Cached gprMax evidence remains
one-pair only, so its relative error at each frequency must be reported as
pair-0 coverage rather than presented as a full-ring norm.

See [`../docs/current_architecture.md`](../docs/current_architecture.md) for
live solver roles and [`../docs/qbx_closure.md`](../docs/qbx_closure.md) for
the archived QBX decision.
