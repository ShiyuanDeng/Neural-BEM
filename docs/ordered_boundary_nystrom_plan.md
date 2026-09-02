# Ordered-boundary Kress/Nyström implementation plan

> **Status: active plan.** Started 2026-09-01 on
> `feature/ordered-boundary-nystrom`. This is the only live forward-backend
> task list. Record measured work in
> [`validation_change_log.md`](validation_change_log.md) and update
> [`current_architecture.md`](current_architecture.md) only when behavior is
> actually live.

> **Progress, 2026-09-02:** the solver-neutral continuous-producer and explicit
> node geometry contracts plus exact circle/ellipse/star and Fourier producers
> now live in `solvers/ordered_boundary/`. `PeriodicCurve2D` and
> `OrderedBoundary2D` are node-owned BIE inputs; off-node evaluation is confined
> to separately named `*Parameterization2D` producers. The isolated sibling
> `solvers/sdf_to_ordered_boundary/` now implements shared SDF extraction and
> the A/B/C parameterization study. Its geometry and manufactured scalar Kress
> metrics are not solver errors and do not complete the forward assembler.

> **Forward-candidate progress, 2026-09-02:** an isolated, direct-import
> `solvers/gpr_bem_kress/` peer solver now accepts one
> `PeriodicCurve2D`, constructs cancellation-safe all-block Kress differences,
> assembles the unsquared Müller system, and evaluates safely separated
> receiver fields through an explicit `ExteriorReceiverOperator` with
> `C=[D,-S]`. It owns its material value type and does not import MOD. It is not
> selector- or operational-driver-wired. Its architecture,
> translated `T/W` sign convention, numerical split, and current limitations
> are recorded in
> [`gpr_bem_kress_implementation.md`](gpr_bem_kress_implementation.md).
> Its solver-owned fast suite currently passes 41 tests, including the
> explicit receiver-operator contract as well as
> block actions, zero contrast, analytic traces, and Mie fields through a
> resolved 8 GHz case. Compact exact circle/ellipse/star and frozen Method-B
> `N`-refinement/receiver/runtime sweeps are stored under
> [`results/ordered_boundary_nystrom/`](../results/ordered_boundary_nystrom/README.md).
> Implementation and a fast regression pass are not acceptance: the Phase-3/4
> transmission, lossy-convention, reference self-convergence, broader-frequency,
> and production-comparison gates below still apply.

## Objective

Keep the neural/analytic SDF as the geometry and optimization variable, but
replace the unordered compressed-cloud discretization used by the precision
forward solver with ordered smooth components and a coherent all-block
Kress/Nyström Müller discretization.

The first accepted backend targets smooth disjoint dielectric components in
the existing 2-D TMz homogeneous full-space problem.

## Architectural rules

1. Never infer boundary order from `ImplicitBoundarySamples2D`. Extract order
   from the zero-level set before compression.
2. Treat marching-squares polygons and `BoundaryMesh2D` as topology carriers
   and fitting seeds, not final high-order solver geometry.
3. Derive points, first/second derivatives, speed, tangent, outward normal,
   curvature, and weights from one periodic evaluator per component.
4. Form exterior-minus-interior kernel differences analytically before
   evaluating singular limits.
5. Assemble S, D, K', and T coherently. Do not add Kress as another kdiff
   `TAssembler` strategy.
6. Keep `solvers/nystrom_ref/` numerically independent and unchanged as the
   oracle.
7. Freeze extraction/remeshing within one forward/adjoint/backward step. There
   is no requirement to differentiate through marching squares.
8. Reject unsupported geometry explicitly. Do not silently smooth exact
   corners, merge close components, or guess nested-material semantics.

## Non-goals for the first milestone

- exact square/corner discretization;
- holes, nested materials, or general material-adjacency graphs;
- layered backgrounds, 3-D geometry, or open curves;
- GPU optimization or fast multipole acceleration;
- further QBX radius/order/source-transfer tuning;
- replacing the current inverse path before the new forward backend passes its
  acceptance gates.

## Candidate isolation

Keep reusable geometry in the NumPy-only sibling package
`solvers/ordered_boundary/`. The numerical implementation is the focused
`solvers/gpr_bem_kress/` peer package, not a nested MOD backend and not another
copy of the complete legacy forward/adjoint/inverse stack. Keep it out of
normal drivers and
`solver_select.SOLVER_NAMES` until forward promotion. During development it is
direct-import and opt-in only.

The candidate must not import numerical implementations from `nystrom_ref`,
`gpr_bem_qbx`, or `gpr_bem_kdiff`. Add a static dependency test for that
boundary. Shared physical configuration and material constants are allowed;
oracle and archived solver numerics are not.

The intended eventual public surface is small and distinguishes producers from
solver-owned nodes:

- `PeriodicParameterization2D` and `OrderedBoundaryParameterization2D` for
  exact/fitted continuous geometry;
- node-based `PeriodicCurve2D` and `OrderedBoundary2D` for BIE assembly;
- an `OrderedBoundaryReport` with topology/geometry diagnostics;
- `extract_ordered_boundary(...)`;
- `build_kress_tmz_frequency_system(...)`;
- `build_exterior_receiver_operator(...)` with explicit `C=[D,-S]`;
- `solve_kress_tmz_total_field_batch(...)`; and
- `solve_kress_tmz_frequency_response(...)`.

The geometry package owns only the first two types and diagnostics. It does not
own Kress weights or enforce even node counts; those are discretisation
requirements of the future numerical candidate.

## Target geometry contract

The new solver-facing representation should contain a tuple of closed
components. Each component needs:

- stable component identity for an outer inverse iteration;
- deterministic orientation and cyclic phase;
- periodic parameter nodes `t_j` with no duplicated endpoint;
- node arrays for `x(t_j)`, `x'(t_j)`, `x''(t_j)`, and optional `x'''(t_j)`;
- derived speed, unit tangent, outward normal, curvature, and ordinary
  arc-length weights at those nodes;
- a separate fitted/analytic parameterization for off-node evaluation and
  local resolution changes, never a hidden second geometry inside the node
  object; and
- diagnostics for closure, orientation, minimum speed, self-intersection,
  inter-component clearance, projection residual, and fit residual.

For the initial disjoint-inclusion scope, accepted components are
counterclockwise and use the outward normal `(t_y, -t_x)`. Hole orientation and
material adjacency are deferred rather than inferred.

## Phase 0 — freeze the baseline and contracts

Deliverables:

- preserve the current `gpr_bem_mod`, `gpr_bem_kdiff`, QBX archive, Mie,
  Nyström, and gprMax comparison rows;
- define a new backend/API boundary without changing normal `--solver`
  selection;
- add a geometry diagnostic artifact format containing component counts,
  orientation, phase anchor, projection/fit residuals, minimum speed,
  curvature range, perimeter, and clearance;
- record the exact six-frequency/five-shape baseline command and commit.

Gate: the pre-existing default comparison suite remains unchanged before new
solver rows are introduced.

## Phase 1 — ordered topology extraction

Start from the existing functions in `gpr_bem_mod/neural_sdf.py`:

- `extract_zero_level_set_curves_from_grid`;
- `extract_zero_level_set_curves`;
- `extract_zero_level_set_mesh`;
- `BoundaryMesh2D.from_closed_curves` in `geometry.py`.

Add the missing contract rather than rewriting marching squares:

1. Detect and reject contours touching the sampling-box boundary or otherwise
   not demonstrably closed.
2. Remove duplicate/near-zero segments and reject self-intersections.
3. Preserve all valid components above an explicit area/perimeter threshold.
4. Normalize orientation for the supported disjoint-inclusion topology.
5. Choose a deterministic phase anchor and direction.
6. Match component identity between successive extractions using explicit
   geometry diagnostics, not array position alone.
7. Report close-component and topology-change events rather than silently
   merging or relabeling them.

Tests:

- analytic circle, ellipse, and star: one closed component with correct area,
  perimeter trend, orientation, and stable phase;
- two circles: exactly two separately identified components under grid
  refinement and small SDF perturbations;
- no zero set, box-touching contour, degenerate loop, self-intersection, and
  below-threshold component: deterministic rejection;
- component order/phase stable enough that unchanged geometry produces
  unchanged nodes across repeated extraction.

Gate: topology and identity tests pass without using compressed-cloud order.

## Phase 2 — project and fit smooth periodic components

For every accepted polygonal seed:

1. Project seed points to `phi=0` with safeguarded Newton updates using the SDF
   gradient. Limit steps and fail on small gradients or non-decreasing
   residuals.
2. Fit a periodic Fourier or periodic-spline evaluator. Keep the evaluator
   implementation swappable until the geometry convergence tests select one.
3. Resample at uniform periodic parameters appropriate for Kress weights.
4. Derive all geometric fields from the same evaluator; use the SDF gradient
   only to validate/project orientation, not as a second source of normals.
5. Check closure, positive minimum speed, orientation, self-intersection,
   inter-component clearance, and fit/projection residuals.

Do not pass `BoundaryMesh2D.node_normals` into the new solver. Those are
averaged piecewise-linear panel normals and are intentionally only a topology
visualization/legacy BEM quantity.

Tests and measurements:

- circle: radius, perimeter, normal, and curvature convergence;
- ellipse/star: point, tangent, normal, curvature, and perimeter convergence
  against analytic parameterizations;
- two circles: component-local evaluation with no phase or fit coupling;
- grid refinement and node refinement reported separately, so extraction
  error is not confused with quadrature error;
- injected exact analytic curves use the same downstream data contract to
  isolate fitting from operator assembly.

Gate: geometry errors decrease under grid/fit refinement and all accepted
components satisfy the recorded diagnostics. Exact-curve injection must be
indistinguishable from the native oracle geometry to the chosen tolerances.

## Phase 3 — coherent Kress/Nyström Müller assembly

Build the production candidate separately from `nystrom_ref` while using its
mathematical results as validation targets.

Assembly requirements:

- form the exterior-minus-interior kernels symbolically, avoiding subtraction
  of separately assembled singular matrices;
- evaluate bounded diagonal limits for S, D, and K';
- apply the periodic logarithmic product rule to the remaining log singularity
  in T;
- use component-local singular weights for same-component interactions;
- use ordinary high-order smooth quadrature for cross-component interactions;
- preserve the accepted Müller block signs/jump conventions and line-source
  normalization;
- expose operator-action, condition-number, residual, assembly-time, and
  solve-time diagnostics;
- solve the dense system directly first. Performance work follows correctness.

Tests:

- zero contrast gives zero scattered field;
- exterior representation/leak identity;
- circle, ellipse-degenerating-to-circle, and star-degenerating-to-circle;
- reciprocity on a non-circular shape;
- individual S/D/K'/T actions on several smooth Fourier density modes;
- same-component and cross-component blocks tested separately;
- refinement with exact injected curves before testing extracted curves.

Gate: exact-curve operator actions and fields agree with Mie/`nystrom_ref` and
converge with node refinement. No `gpr_bem_mod` stand-off offset or compressed
weights enter this path.

## Phase 4 — forward acceptance ladder

Run the same frequencies and scan geometry as the existing aggregate suite.
Keep solver-only and end-to-end geometry tests separate.

1. **Analytic circle:** compare against the Fourier–Bessel/Mie series at all
   six frequencies.
2. **Analytic ellipse and star:** compare against `nystrom_ref` at all six
   frequencies.
3. **SDF-extracted circle/ellipse/star:** repeat after marching-squares,
   projection, and periodic fitting.
4. **Two disjoint circles:** require stable component blocks and self-
   convergence; add an independent multicomponent oracle before claiming
   precision-oracle status.
5. **gprMax:** retain as an independent gross-physics check, not the precision
   threshold. Existing caches cover only Tx/Rx pair index 0; report its
   per-frequency relative error separately from the 24-pair BEM receiver L2.
6. **Square:** verify explicit smooth-only rejection. Do not reinterpret a
   smoothed square as square validation.

Provisional quantitative gates, to be revised only by a dated decision before
examining candidate results:

- linear-system relative residual at or below `1e-10` in complex128;
- exact injected smooth curves within `1e-6` scaled/mixed relative field error
  of Mie or `nystrom_ref` across the six-frequency band;
- SDF-extracted smooth curves within `1e-3` scaled/mixed relative field error
  after declared grid/fit refinement;
- no accepted smooth shape/frequency cell worse than `gpr_bem_mod`, and at
  least a tenfold reduction in the 8 GHz error on circle, ellipse, and star;
- stable or decreasing error under declared grid and node refinement, with any
  roundoff plateau identified rather than tuned through;
- all geometry and topology diagnostics valid, with no hidden fallback.

Pure relative error near a physical scattering null is diagnostic only; use
the repository's mixed/scaled metrics for gates.

Runtime must be measured with assembly and solve separated and with equal
Tx/Rx/frequency work. Initial acceptance is accuracy-first, but a large cost
regression must be documented before promotion.

Gate: add a normal comparison row only after the above criteria pass. Until
then, keep the backend opt-in and label every result experimental.

## Phase 5 — adjoint and inverse handoff

Begin only after the forward backend is accepted and frozen enough to
differentiate.

1. Derive the discrete adjoint from the complete accepted matrix and receiver
   map; use the literal forward matrices in `A^H lambda = C^H psi`, where the
   forward-owned receiver operator already records `C=[D,-S]`. Do not port
   compressed-cloud directional code piecemeal.
2. Validate receiver duals and frozen-geometry directional derivatives against
   finite differences on circle, ellipse, and star. Add a multicomponent case
   only after multicomponent Kress forward assembly is separately implemented
   and accepted; it is outside the initial one-component contract.
3. Convert the accepted boundary shape density to the existing
   `shape_gradient_surrogate_loss` interface. Name and test whether every
   quantity is a nodal directional derivative or an unweighted density so the
   curve's arc-length weight is applied exactly once.
4. Freeze ordered extraction and periodic fitting within each gradient
   evaluation; re-extract after the optimizer update.
5. Make any finite-difference fallback explicit and opt-in rather than a broad
   exception handler.
6. Run inverse smoke tests only after the gradient gates pass, then compare
   reconstruction behavior against the current `gpr_bem_mod` baseline.

Gate: adjoint directional derivatives meet declared tolerances before any
reconstruction image is treated as evidence.

## Deferred follow-on tracks

- Corners: piecewise-smooth components, explicit corner nodes, graded panels,
  one-sided geometry, and product integration. The historical square study is
  in [`legacy/square_target_oracle_options.md`](legacy/square_target_oracle_options.md).
- Nested media: containment and material-adjacency graph with orientation rules
  per interface.
- QBX: reconsider only under the criteria in
  [`qbx_closure.md`](qbx_closure.md), and only against the accepted ordered
  Kress backend on identical geometry.
- Performance: batching, accelerator kernels, iterative solves, and fast
  methods after correctness and conditioning are stable.

## Validation-entry template

Every completed phase or rejected alternative should append one entry to
`validation_change_log.md` containing:

1. date and hypothesis;
2. code paths and configuration changed;
3. exact commands and artifact paths;
4. geometry, operator, field, residual, conditioning, and timing measurements
   relevant to the hypothesis;
5. comparison to the predeclared gate; and
6. decision: accept, revise, defer, or close.

Keep geometry-contract tests under `pytest/ordered_boundary/` and place the
solver candidate's operator/system/field tests in the parallel
`pytest/gpr_bem_kress/` package. Store compact JSON/Markdown evidence under
`results/ordered_boundary_nystrom/`; do not commit dense matrices.
Geometry-only SDF and manufactured scalar-product-rule metrics remain under
`results/sdf_boundary_parameterization/`; they do not satisfy the operator or
field-error gates of this plan.
