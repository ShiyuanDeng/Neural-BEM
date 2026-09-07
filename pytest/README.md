# Tests and validation

Tests mirror the package or study they own. Generated evidence lives only
under [`../results/`](../results); `pytest/` contains no result bundles.

## Layout

| Directory | Responsibility | Uses solver-error metrics? |
|---|---|---:|
| `gpr_bem_shared/` | Selector-backed tests shared by frozen `ref` and operational `mod` | Yes, in system/theory tests |
| `gpr_bem_mod/` | MOD-only adjoint, inverse, and shape-derivative checks | Yes, except the kernel-identity test |
| [`gpr_bem_kress/`](gpr_bem_kress) | Direct-import Kress/Müller blocks, systems, receivers, fields, and single-interface discrete JVP/objective-adjoint contracts | **Yes** |
| [`multicylinder_ref/`](multicylinder_ref) | Independent cylindrical-harmonic oracle for disjoint circular inclusions | **Yes** |
| `gpr_bem_kdiff/` | Retained k-difference and archived QBX assembly seam | Operator/system checks |
| `gprmax_ref/` | gprMax cache identity and scene policy | No |
| `nystrom_ref/` | Independent smooth-boundary forward oracle | Yes |
| `ordered_boundary/` | Continuous and node-owned geometry contracts | **No** |
| [`sdf_to_ordered_boundary/`](sdf_to_ordered_boundary) | Implicit-field extraction, A/B/C fits, geometry metrics, artifacts, and scalar Kress proxy | **No** |
| [`sdf_inverse/`](sdf_inverse) | Neural Kress-adjoint and Method-B reverse, actual-MLP acceptance/rollback, explicit radial policies, and legacy known-family parameter controls | **Yes** |
| [`sdf_bem_multicomponent/`](sdf_bem_multicomponent) | Automatic unknown-`M` extraction, readiness gates, direct boundary forwarding, ragged trajectories, and the one-to-two split | **Yes** |
| [`solver_comparisons/`](solver_comparisons) | Circle, ellipse, square, star, and two-circle solver comparisons | **Yes** |

The distinction among the geometry, inverse, and comparison rows is
deliberate. The ordered-boundary and SDF-to-boundary suites stop before any
Helmholtz/Müller operator assembly, linear solve, boundary density, or
receiver/scattered field. Their “errors”
are implicit zero-set residuals, geometric discrepancies, parameterization
diagnostics, or errors in one manufactured scalar logarithmic integral. The
dedicated cross-solver error tables and checked field-result bundles live in
`solver_comparisons/`; `sdf_inverse/` instead executes both physical forwards
inside one common numerical inverse, and other solver-owned unit suites test
their own systems and fields.

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

The final first-party validation command is deliberately scoped to this
directory:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/ -q
```

It passed `272 passed, 2 skipped` in 193.15 s (194.92 s process wall time) on
2026-09-02, before the later MLP-path tests were added; the skips are the
expected CuPy-dependent checks. Running
discovery at the repository root also
collects vendored optional projects whose dependencies are not installed, so
their unrelated collection errors are outside the first-party suite.

## Geometry and parameterization tests

The 2026-09-05 first-batch additions are covered by
`sdf_inverse/test_distillation_policy.py`, `test_representation_ablation_driver.py`,
`test_continuous_distance.py`, `test_smooth_redistance.py`,
`sdf_to_ordered_boundary/test_parameter_aware.py`, and
`solver_comparisons/test_parameterization_aware_driver.py`. They test strict
compatibility, no neural work during curve reconstruction, export rollback,
distance/sign/refinement and solver-N independence, ordered-fit validity and
fallbacks, and non-mutating evidence postprocessing. The C1/C2 physical-field
study remains a separate opt-in driver, not a new meaning for historical A/B/C
geometry metrics. See the [batch report](../docs/reports/sdf_kress_first_batch_2026-09-05.md)
and its validation entry for actual runs and failed experimental accuracy gates.

Run the complete solver-independent boundary suite with:

```bash
PYTHONPATH=solvers python -m pytest -q \
  pytest/ordered_boundary \
  pytest/sdf_to_ordered_boundary
```

The checked A/B/C evidence is consolidated under
[`../results/sdf_boundary_parameterization/`](../results/validation/sdf_boundary_parameterization):

- `smoke-20260902/`: small complete bundle with plots and native coefficients;
- `study-20260902/`: full grid/sample/bandwidth study; and
- [`kress-scalar-proxy-20260902/summary.md`](../results/validation/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md): manufactured scalar log-product-rule convergence and runtime.

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

The 2026-09-06 [follow-up](../docs/reports/sdf_kress_followup_2026-09-06.md) adds
`gpr_bem_kress/test_shape_derivative.py`,
`sdf_inverse/test_cylinder_sensitivity_reference.py` and
`solver_comparisons/test_kress_shape_derivative_driver.py`. They cover actual
operator/receiver/objective derivatives, repeated complex paired data,
zero-contrast material sensitivity and evidence-driver gates. Fixed-node
derivative tests are distinct from the opt-in driver's independent physical
refinement sweep. The distance-contact guards and driver accounting are
covered by `sdf_to_ordered_boundary/test_distance_tangency.py` and
`solver_comparisons/test_distance_tangency_driver.py`; geometry-only tests do
not acquire physical-field claims merely because their driver audits fields.

The follow-up's `sdf_inverse/test_neural_metric.py` covers mass projection,
exact radial jets, frozen-head accounting, true-objective acceptance and
budget/failure reporting. `sdf_inverse/test_material_inverse.py` and
`solver_comparisons/test_material_inverse_driver.py` cover material rebuilds,
immutable normalization/cache identity, scaled residual Jacobians, bounded
stopping, noise cohorts and independent material-sensitivity evidence.

`sdf_inverse/test_robust_material_inverse.py` additionally checks frequency/
complex-strength alignment, immutable full-band weighting, deterministic
starts, exact global/phase work accounting, partial failures, best-candidate
retention, and fixed-shape invariance. Its budget and stationarity tests do
not assert physical recovery. `solver_comparisons/test_material_robustness_driver.py`
checks frozen historical replay, independent new data, strict artifacts and
the all-selections-before-qualification barrier. The separate opt-in driver
provides the physical recovery measurements.

The automatic multi-component seam, including generic singular-event
rejection and the two-circle independent-oracle comparison, runs with:

```bash
PYTHONPATH=solvers python -m pytest -q \
  pytest/sdf_bem_multicomponent \
  pytest/gpr_bem_kress/test_multicomponent.py \
  pytest/multicylinder_ref
```

The checked exact/noncircular and frozen Method-B convergence tables are
indexed at
[`../results/ordered_boundary_nystrom/README.md`](../results/validation/ordered_boundary_nystrom/README.md).

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

## Inverse tests: neural adjoint, explicit radial and legacy controls

The full `pytest/sdf_inverse` suite contains distinct contracts for both current
pipelines and the archived controls. The neural tests include
[`test_implicit_adjoint.py`](sdf_inverse/test_implicit_adjoint.py),
[`test_method_b_pullback.py`](sdf_inverse/test_method_b_pullback.py) and
[`test_implicit_adjoint_driver.py`](sdf_inverse/test_implicit_adjoint_driver.py).
They check the actual weight-to-extraction-to-Method-B-to-BEM gradient,
accepted-network loss decrease, rollback and CLI routing. The solver-side
[`test_geometry_pullback.py`](gpr_bem_kress/test_geometry_pullback.py) checks
the discrete Kress geometry reverse. Passing derivative tests is separate
from successful reconstruction.

The archived parameter-control tests check that a single-frequency complex residual is
not erased, adjacent marching-squares duplicates at exact grid zeros are
handled safely, nonempty artifact directories require explicit overwrite,
both solvers receive the same ordered nodes and arc weights, both forwards
agree with analytic Mie data at their declared tolerances, large finite-
difference parameter sets are rejected, and a wrong circle converges under a
monotone fixed objective for both MOD and Kress. It also sends a rotated
quadratic ellipse and a seeded random-feature neural implicit through both
forward branches, verifies their non-circular/non-distance initial fields,
and confirms that an unconstrained random MLP with no valid closed contour is
rejected before a forward solve.

[`test_star_target_inverse.py`](sdf_inverse/test_star_target_inverse.py) adds
the lobed target: that the star level set, the oracle's parameterization, and
the exact point-to-curve distance describe one curve; that the star's bounds
reject an unidentifiable lobe phase; that the Nystrom observations are
self-converged and exactly linear in the source strength; and that the same
inverse recovers lobe depth and phase, which no circular target can exercise.
The star's geometry resolutions there are deliberately cheaper than the
driver's, so those are contract tests rather than accuracy evidence:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_inverse
```

The early recorded counts and timings are historical; current validation
history is in the [dated log](../docs/reports/validation_change_log.md).
The following command also includes the separate older MOD inverse contracts:

```bash
PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  pytest/sdf_inverse pytest/gpr_bem_mod/test_ibim_inverse.py
```

The corresponding runs are indexed in the [results catalogue](../results/README.md).
The current pipeline guides are [Implicit MLP + Method B](../docs/pipelines/implicit_mlp.md)
and [Explicit Radial Fourier](../docs/pipelines/explicit_radial_fourier.md).
The [legacy known-shape-family controls](../docs/legacy/known_shape_family_controls.md)
and [historical development record](../docs/reports/inverse_development_through_2026-09-06.md)
describe the older small-parameter FD tests. Their successful recovery does
not certify full-neural reconstruction.

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
`results/validation/solver_comparisons/current/`. The checked QBX-inclusive closeout is
kept separately at
[`../results/solver_comparisons/legacy/qbx-closeout-20260901/`](../results/legacy/solver_experiments/qbx-closeout-20260901).
The compact checked MOD/Kress/gprMax result is
[`kress-peer-20260902/summary.md`](../results/validation/solver_comparisons/kress-peer-20260902/summary.md).
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
live solver roles and [`../docs/qbx_closure.md`](../docs/legacy/qbx_closure.md) for
the archived QBX decision.
