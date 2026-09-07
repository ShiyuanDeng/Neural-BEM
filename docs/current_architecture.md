# Current architecture

> **Status: living source of truth.** Last reconciled 2026-09-06. Update this
> document whenever a live pipeline, default, solver role, or known limitation
> changes.

## Scope and authority

The implemented physical problem is 2-D TMz dielectric transmission in an
infinite homogeneous full-space. It uses the free-space Hankel Green function
and line-source normalization `0.25j * H_0^(1)(k r)`. There is no air/ground
interface, layered Green function, absorbing boundary condition, or 3-D model
in the active path.

Neither active BEM path is literature-style Cartesian volume IBIM. The legacy
MOD path estimates geometry in a Cartesian narrow band and collocates dense
operators on a compressed point cloud. The ordered path extracts and projects
one zero contour, fits a smooth periodic curve, and applies the coherent
Kress/Nyström Müller discretization to that curve.

The 2026-09-05 inverse audit enforces the negative-inside material convention
at the single- and multi-component geometry seams, validates an omitted MLP
representation in strict mode when a canonical initial curve is supplied, and checks radial
curve sampling against its own Cartesian bandwidth. Parameter-FD stopping
does not treat missing derivatives or arbitrarily small rejected proposals
as convergence. New MLP artifacts include a complete physical experiment
snapshot. See the [dated review](inverse_pipeline_review_2026-09-05.md) for
evidence, repairs, and proposed design work.

The subsequent [A/B/C first batch](sdf_kress_first_batch_2026-09-05.md) adds
explicit `curve_only` and final `export_only` distillation policies while
retaining `legacy_strict` as the default. Reconstruction status and requested
SDF delivery are separate; absent representation audits are null. Canonical
validation remains mandatory. Smooth continuous-curve distance targets and
ordered-label Cartesian Fourier fitting are opt-in; historical polygon targets
and Method B are unchanged. The new parameterization study includes physical
field comparisons, unlike the original isolated A/B/C geometry study.

The [2026-09-06 follow-up](sdf_kress_followup_2026-09-06.md) adds an explicit-import
single-interface Kress geometry/material JVP and paired-objective adjoint, plus
an opt-in continuous-query distance/tangency fitting experiment. Separate
drivers test frozen neural-feature metrics on the explicit radial chart and
one unknown interior permittivity, with fixed geometry or joint radial-K2
shape. They do not change production inverse defaults, Method-B fallback, or
supported topology; multiple independent materials remain outside these tests.

The subsequent [material robustness branch](material_robustness_2026-09-06.md)
adds training-only continuation and bounded deterministic restarts to the
same explicit K2 chart, not a new representation or physical model. Its
common full-band selection, global work caps and separate stationarity/
recovery reports remain opt-in.

This page owns present-tense behavior. The
[validation change log](validation_change_log.md) owns chronology, the
[QBX closure](qbx_closure.md) owns that decision, and the
[ordered-boundary plan](ordered_boundary_nystrom_plan.md) owns future tasks.
The implemented low-dimensional MOD/Kress inverse is specified in
[`solver_neutral_inverse.md`](solver_neutral_inverse.md).

## Solver roles and selection

| Package | Current role | Normal selector |
|---|---|---|
| `solvers/gpr_bem_ref/` | Frozen original and regression control | `--solver=ref`; also the default |
| `solvers/gpr_bem_mod/` | Operational compressed-cloud forward, neural adjoint, and legacy inverse baseline; also a peer forward in `sdf_inverse` | `--solver=mod` or direct import |
| `solvers/gpr_bem_kress/` | Ordered Kress/Müller forward solver; opt-in single-interface discrete JVP/objective adjoint; existing inverses still use parameter FD | Direct import only |
| `solvers/sdf_inverse/` | Common ordered geometry, paired MOD/Kress dispatch, and bounded low-dimensional numerical inverse | No selector; explicit `solver=` argument |
| `solvers/gpr_bem_kdiff/` | Frozen compressed-cloud forward experiment and retained `TAssembler` seam | Not selectable |
| `solvers/gpr_bem_qbx/` | Archived full-row QBX `T` diagnostics invoked through kdiff | Not selectable |
| `solvers/gpr_bem_ndiff/` | Unvalidated normal-offset experiment; archived/unsupported | Not selectable |
| `solvers/nystrom_ref/` | Numerically independent, smooth single-component, forward-only precision oracle | Direct import only |
| `solvers/ordered_boundary/` | Solver-neutral exact/Fourier smooth-component geometry foundation | Direct import only |
| `solvers/kernel_diff_ref/` | Circle/perfect-sampling kernel-difference diagnostic; not an oracle | Direct import only |
| `solvers/gprmax_ref/` | Cached independent FDTD cross-check | Direct tools/tests only |

“Operational” does not mean selector default. `solvers/solver_select.py`
defaults to `ref`; omitting `--solver` runs the frozen control. Always include
`--solver=mod` when exercising the legacy maintained neural-adjoint path. The
solver-neutral inverse bypasses this alias and imports named peers, so it does
not promote Kress into `solver_select`.

## Current geometry pipelines

```text
SDF callable
  -> Cartesian grid and narrow-band selection
  -> SDF gradient, first-order level-set projection, normal, curvature
  -> regularized-delta and optional Jacobian-corrected weights
  -> weighted spatial-bin compression
  -> unordered ImplicitBoundarySamples2D cloud
```

`solvers/gpr_bem_mod/ibim_geometry.py` owns this path:

- `build_implicit_boundary_band` samples the SDF, keeps the narrow band,
  projects samples toward `phi=0`, and computes normals, curvature, ordinary
  weights, and Jacobian-corrected strict weights.
- `compress_implicit_boundary_band` rounds projected points into spatial bins
  and weight-averages each bin. It may reduce the requested merge distance to
  retain a minimum sample count.
- `ImplicitBoundarySamples2D` retains points, normals, ordinary/strict weights,
  merge metadata, bounds, and level.

The compressed object does **not** retain closed-component ordering,
connectivity, component identity, a cyclic phase, tangents, curvature, or a
smooth off-node curve evaluator. Its array order is an implementation artifact,
not a boundary parameter.

`solvers/gpr_bem_mod/neural_sdf.py` already contains marching-squares helpers
that extract ordered zero-level polygons and can build a multi-surface
`BoundaryMesh2D`. Those APIs are scaffolding. The active forward quadrature
does not consume them, and the piecewise-linear mesh/averaged mesh normals are
not solver-grade Kress geometry.

### Explicit ordered geometry foundation

`solvers/ordered_boundary/` provides an independent NumPy-only, node-based
geometry contract for exact or already-fitted smooth curves. Continuous
`PeriodicParameterization2D` producers retain off-node evaluators for `x`,
`x'`, `x''`, and optional `x'''`. Explicit `.discretize(...)` produces
`PeriodicCurve2D` node components and the flattened `OrderedBoundary2D` BIE
input. The node objects own positions, derivatives, speed, unit tangent, CCW
outward normal, curvature, ordinary arc-length weights, component-local
parameters, slices, and node ownership; they contain no hidden evaluator.

This package is not part of the selector-backed MOD forward driver.
`solvers/sdf_to_ordered_boundary/` supplies the shared marching/projection
front end and A/B/C parameterizations. Its Method-B path is now reused by
`solvers/sdf_inverse/`, which constructs one `PeriodicCurve2D` and either
passes it directly to `gpr_bem_kress` or presents copies of its points,
normals, and arc-length weights to MOD through an
`ImplicitBoundarySamples2D` adapter. The standalone A/B/C study remains a
geometry experiment, but its library is no longer solver-isolated.

When marching squares encounters a zero set exactly on grid vertices, it may
emit adjacent repeated vertices. The front end removes only consecutive
near-duplicates before polygon validation. Non-adjacent duplicates remain in
place and are rejected as genuine degenerate/self-touching geometry.

The ordered geometry package deliberately contains no Kress pairwise weights,
hypersingular regularisation, or materials. Solver-specific assembly stays in
the selected forward package; the legacy `merge_distance` adapter exists only
at the solver-neutral inverse seam. Kress, kernel-difference, QBX, panel, and
other solvers may build different discretisations from the same continuous
geometry. See
[`../solvers/ordered_boundary/README.md`](../solvers/ordered_boundary/README.md).

## Current forward pipeline

```text
compressed boundary cloud + Tx/Rx scan
  -> dense exterior/interior S, D, K', T operator families
  -> second-kind Müller block system
  -> direct dense solve for each frequency
  -> incident + scattered receiver response
  -> frequency window and trapezoidal inverse-frequency integral
  -> B-scan
```

The operational implementation is `gpr_bem_mod`:

- `ibim_tmz_forward.py` assembles layer potentials and operator families.
- `ibim_tmz_system.py` forms the transmission system, solves the traces, and
  evaluates receiver fields.
- `scan_paths.py` constructs bistatic scan pairs.
- `signal_processing.py` maps frequency responses to time samples. This is a
  weighted inverse Fourier integral, not an FFT/IFFT shortcut.
- `run_ibim_rectangular_scan_forward.py` is the canonical driver.

Library defaults are:

| Setting | Default | Qualification |
|---|---|---|
| Formulation | `muller` | Second-kind exterior/interior combination |
| Normal derivative | `analytic_extrapolated` | Dense stand-off/extrapolation scheme |
| State solve | `direct` | The historical squared solve remains optional |
| Assembly backend | `numpy` | CuPy is available where supported |
| Complex precision | `complex128` | `complex64` is optional |
| Strict quadrature | `False` | Canonical benchmark configuration may enable it |

`MULLER_OFFSET_SCALE = 0.1375` is an empirically tuned,
discretization-dependent trace-offset constant. It was fitted on a circle and
must not be treated as a derived universal parameter.

### Experimental Kress forward peer

`solvers/gpr_bem_kress/` is a sibling solver rather than a MOD submodule. It
owns cancellation-safe Müller kernels, all four Kress-discretized difference
blocks, the unsquared dense system, a package-local `Material` value type, and
forward result records. Its sole geometry input is an immutable, even-node
`PeriodicCurve2D`.

The receiver map is an explicit `ExteriorReceiverOperator`. For the state
ordering `q=[u_D,u_N]^T`, it stores fully weighted rows

```text
C = [D, -S],                    u_sc = C q.
```

`KressTMzForwardResult` retains the actual system `A`, right-hand side, solved
state, receiver operator, traces, and full `(source, receiver)` field arrays.
That ownership supports the opt-in `shape_derivative` discrete-adjoint seam,
`A^H lambda = C^H Psi`, without reconstructing either transpose by hand. For
the paired ACC observation, `y=P(Cq+u_inc)`: the reverse map must first scatter
the paired dual with `Psi=P^H psi` onto the diagonal of the full source/receiver
array (or arbitrary selected entries); repeated selections accumulate.
Passing a pair vector directly to `C^H` has the wrong RHS semantics.
`linearize_kress_forward` differentiates the actual weighted blocks, source
traces, receiver map and incident contribution. `KressDirection` supplies
coherent native-grid position/derivative jets and optional material or source
strength directions. Normals, speed, arc factors and diagonal splits move
consistently; topology, period, acquisition and kernel branch stay fixed.
`build_paired_objective_adjoint` returns a fixed real-stacked weighted data
objective whose directional contraction is a real scalar, not an arbitrary
normal shape-gradient density. Converting coefficient covectors into a
normal function requires an explicit basis and mass matrix; no extra `ds`
belongs on the covector. The dated follow-up separates fixed-node derivative
correctness from independent-oracle and physical-refinement evidence.

## Current inverse pipelines

### Legacy MOD neural B-scan adjoint

```text
observed B-scan + SirenSDF2D
  -> re-extract compressed cloud for the outer iteration
  -> forward fields, receiver rows, and time-domain residual
  -> frequency-response dual and A^H adjoint solve
  -> leading-order normal shape-gradient density
  -> fixed-boundary SDF surrogate + regularizers
  -> Adam update
  -> re-extract for the next outer iteration
```

The implementation is split across:

- `ibim_tmz_adjoint.py`: single/multifrequency/B-scan contexts, adjoint solves,
  and leading-order directional and normal shape gradients;
- `neural_sdf.py`: `SirenSDF2D`, Eikonal/Laplacian terms, contour scaffolding,
  and `shape_gradient_surrogate_loss`;
- `ibim_inverse.py`: boundary extraction, loss assembly, optimizer loop, and
  iteration records;
- `run_ibim_circle_inverse_bscan.py`: the staged circle benchmark driver.

Extraction and compression are frozen during each forward/adjoint/backward
evaluation. The code does not differentiate through marching squares,
projection, bin assignment, or remeshing. Instead, the shape-density surrogate
maps the accepted boundary gradient back to SDF parameters, followed by a new
extraction on the next outer iteration.

The audited path now treats adjoint failures explicitly. The default
`shape_gradient_fallback="error"` propagates the original exception; a sparse
finite-difference diagnostic is used only when the caller explicitly selects
`"finite_difference"`. Every iteration records which method ran. CUDA BEM
assembly is selected only when Torch CUDA and an importable CuPy package are
both available; otherwise it uses NumPy. The canonical driver no longer passes
the unsupported `min_boundary_samples` keyword, and its smoke test uses two
frequencies so trapezoidal frequency integration does not erase the objective.

This legacy B-scan adjoint remains MOD-only. The new fixed-grid Kress
frequency-domain objective adjoint is a separate direct-import experiment,
not permission to select Kress in this legacy driver.

### Solver-neutral ordered-curve parameter inverse

```text
analytic Mie scattered data + wrong Torch implicit field (SDF optional)
  -> common single-component extraction and Method-B periodic fit
  -> one immutable PeriodicCurve2D
  -> MOD adapter or native Kress forward
  -> paired complex frequency-domain residual
  -> bounded parameter finite differences
  -> damped Gauss--Newton/Levenberg--Marquardt update
```

`solvers/sdf_inverse/` separates models, geometry, paired forward prediction,
and optimization. Every objective evaluation repeats the complete extraction,
fit, remesh, and selected forward solve. MOD and Kress therefore receive the
same curve nodes and periodic arc-length weights rather than independent
discretizations. Kress' native full source-by-receiver response is reduced by
an explicit paired diagonal; MOD already returns paired values.

The fixed objective normalizes each complex frequency column by the observed
column norm and concatenates real and imaginary residuals. A bounded numerical
Jacobian and common damping/backtracking policy make the comparison independent
of either solver's derivative implementation. Checked initial models now cover
a three-parameter exact circle SDF, a four-parameter rotated quadratic ellipse
level set, a seven-parameter seeded random-feature neural implicit, and a
five-parameter radial star level set whose lobe depth and phase are controls.
Every controller refuses unexpectedly large parameter sets. This is an
auditable black-box inverse baseline, not a scalable full-network algorithm
and not a Kress adjoint.

[`run_sdf_inverse_comparison.py`](../run_sdf_inverse_comparison.py) selects
the analytic target with `--target`, and the target carries its own
observation oracle, initializations, frequency bands, geometry resolutions,
and shape gates:

| `--target` | Truth | Train / holdout | Fit | Controls |
|---|---|---|---|---|
| `circle` | `gpr_bem_ref` analytic Mie series | 0.25, 0.5 / 1, 1.5, 2.5 GHz | bandwidth 10, 64 nodes | center, radius (plus ellipse and random-feature variants) |
| `star` | `nystrom_ref` independent Nystrom solution of the exact curve | 0.5, 1.5 / 0.25, 1, 2.5 GHz | bandwidth 48, 128 nodes | center, mean radius, lobe amplitude, lobe rotation |

The star's higher bandwidth is measured, not chosen: an arc-length Fourier
curve represents a five-lobe star to `9.7e-4 m` at bandwidth 10 and `2.9e-5 m`
at bandwidth 48, while refining the extraction grid at fixed bandwidth changes
nothing. Its training band is likewise set by identifiability -- lobe phase is
almost invisible below 1 GHz. `--initial-model` accepts only the selected
target's own families. The star run additionally gates its observation oracle
against a half-resolution solve of the same curve before any inverse begins.
Default output paths carry a UTC timestamp; an explicit nonempty path requires
`--overwrite`, which removes only known driver artifacts. Optimizer
convergence is an acceptance gate. The contract, measured results, and
limitations are in [`solver_neutral_inverse.md`](solver_neutral_inverse.md).

The default strict experimental full-network path is
[`run_mlp_sdf_inverse_comparison.py`](../run_mlp_sdf_inverse_comparison.py).
Its accepted geometry is a validated `PeriodicCurve2D`; a geometrically
initialized residual MLP is the trainable signed-distance representation of
that contour, not a second geometry state. This established comparison path
still takes black-box derivatives in a handful of radial Fourier
coordinates rather than thousands of network weights. Finite-difference
probes update and solve that authoritative star-shaped curve directly, without
SDF extraction or repeated curve refitting. The basis size uses
the smaller of the training-band `ceil(ka + ka**(1/3))` estimate and the paired
scan's angular Nyquist limit. The default is cumulative low-to-high frequency
continuation; `--joint-full-band` and progressive-mode continuation are
explicit ablations.

The modal step uses a damping floor, a `k**4` curvature prior, log-refined
trust-region damping, and Armijo acceptance. Once a radial-state candidate has
sufficient data decrease, the identical curve receives dense continuous
validation. The probe BEM response remains its acceptance response because
cheap and full validation generate bit-identical nodes. All MLP weights are
then trained against its signed polygon distance plus zero/offset anchors and
Eikonal loss.
The MLP zero set is extracted once to audit topology and contour drift, but it
neither replaces the canonical curve nor triggers another BEM solve.
All inverse forward attempts are counted, every successful trial contributes
to the reported worst linear-system residual, and BEM, curve-update,
re-distancing, and selected-candidate audit timings are reported separately.
Full-validation rejection, failed MLP fitting, representation extraction
failure, and representation-drift rejection counters are separated rather
than being folded into the infeasible-forward count. The representation drift
limit is a `1.5 mm` acceptance safety cap; the independent `0.2 mm`
geometry-convergence tolerance remains part of the convergence claim.
Trajectory CSV and live progress also expose accepted backtracks, raw versus
accepted predicted decrease, arc-refit RMS/maximum displacement, and speed
ratio before/after refitting so parameterization collapse is observable online.
The line search evaluates the configured number of reductions in addition to
the un-backtracked trial. The new default of six reductions reaches `1/64`;
the former five-reduction limit omitted the sixth reduction that the
progressive-mode diagnostic showed was necessary to pass dense validation. A
full accepted step earns lower damping, but a backtracked accept retains the
damping that generated its direction instead of forcing the next iteration to
reject and rebuild it. If the direct canonical step is stationary, repeated
dense-validation failures stop as `geometry_limited_stationary`; without such
failures, an unmet MLP audit stops as `representation_limited_stationary`.
Neither diagnosis claims convergence or spends the remaining outer budget.
This gives MOD and Kress the same curve/representation coupling without using
the separate experimental Kress adjoint. The first canonical Kress diagnostic reduced
inverse time from `948.326 s` to `288.945 s`, but its low-frequency-first
schedule overshrank the mean radius. The following full-band progressive-mode
run also did not converge: after 74 accepts its training relative L2 was
`0.957988`, holdout had worsened to `1.075114`, and maximum boundary error had
worsened to `48.442 mm`. The faithful MLP audit (`0.243 mm` drift and
`0.002329` relative response discrepancy, with no MLP rejection) isolates the
failure from neural representation drift. Progressive mode staging was not
the only defect. The subsequent joint full-band `k<=6` diagnostic accepted 14
updates, reduced loss `1.423242 -> 0.542048`, and improved train/holdout
relative L2 `1.192384 -> 0.738845` / `1.053290 -> 0.935345`, but still stopped
nonconverged as `representation_limited_stationary` while maximum boundary
error changed only `42.031 -> 35.114 mm`. The final `k=5` vector was
`(-0.420, -4.817) mm` instead of `(12.500, 0) mm`. Its
minimum/mean parameter speed collapsed from about `1` to `0.003`, maximum
absolute curvature reached about `3.03e6 1/m`, and 83 dense validations
failed. Selected-update remeshing repaired that parameterization failure, but
the later identifiable `k<=5`, 24-pair joint run still did not converge: 56
accepted updates changed training/holdout relative L2
`1.19325 -> 0.79976` / `1.13855 -> 1.07342`, while maximum boundary error
worsened `42.22 -> 46.92 mm`. All 56 MLP fits and audits succeeded. Instead,
the canonical curve ceased to be star-shaped and its radial tail above `k=5`
grew from `0.723` to `6.258 mm` RMS. A local normal velocity therefore was
not a global band-limited shape state. Independent direction probes also show
the joint full-band initial step is target-misaligned, while 0.5 GHz/K3 is
strongly aligned. The current radial-Fourier state and corrected
K3/K5/K5 cumulative-frequency default address both defects. The completed
post-fix bundle recovered the canonical target to `2.57e-10 m` maximum
analytic boundary error, with train/holdout relative L2
`1.07e-8` / `1.34e-8` and roundoff-only tail above K5. The result remains
formally `representation_limited_stationary` because its extracted MLP contour
is `0.329 mm` from the canonical curve, above the separate `0.2 mm`
representation convergence gate.

[`run_sdf_inverse_contour_video.py`](../run_sdf_inverse_contour_video.py) is
read-only post-processing over a finished bundle: it animates both solvers'
stored contour trajectories, including labelled continuation-stage baselines,
side by side against the exact target. It imports no solver and recomputes no
physics.

### Separate bounded derivative-based inverse experiments

`run_neural_metric_comparison.py` uses the verified Kress objective adjoint
with an authoritative K5 radial curve. Identity, one Sobolev smoother and
three frozen initial neural-feature metrics share the same geometry, data,
normal-step cap and accepted-objective policy. The zero-head geometric MLP
initialization activates only 65/5,441 parameter derivatives, and there is no
training or neural zero-set extraction during reconstruction. This is not an
end-to-end neural inverse or evidence that true distance values are needed.

`run_material_inverse_comparison.py` uses Kress JVP residual Jacobians to fit
one positive lossless interior `epsr`, either on a fixed circle or jointly
with five radial-K2 geometric controls. Observations, source calibration,
exterior material and weighting are frozen; a candidate rebuilds its interior
material and complete forward system. Explicit bounds, noise/held-out-angle
tests and local scaled-Jacobian diagnostics distinguish numerical stopping
from physical recovery. Its fixed-count single-interface material state is
not a per-component multi-material model. Both modules require explicit
imports; neither replaces the baseline MOD/Kress inverse implementation.
See the [dated follow-up](sdf_kress_followup_2026-09-06.md) for bounded evidence
and failed outcomes rather than inferring general convergence from this API.

`sdf_inverse.robust_material_inverse` orchestrates that same material model
with `full_band`, `continuation`, or `multistart` policies. The latter screens
bound-derived starts while retaining both available material-contrast signs
about the known background. Only full-band training evaluations can supply
the returned candidate; low-band scores, target geometry and held-out data
cannot select it. Global attempt caps include screening, failed work and
selected-state derivative auditing. Search completion, stationarity and
physical recovery have distinct meanings. The separate
`run_material_robustness_comparison.py` freezes every training selection
before post-selection geometry/holdout qualification; it does not promote
these policies to a production default.

## Same-scene forward comparison

The smooth comparison cases use one case definition and one callable SDF for
the two BEM branches, while allowing each numerical method to construct its
own appropriate boundary representation:

```text
+-----------------------------------------------------------------------+
| pytest/solver_comparisons/test_{circle,ellipse,star}_comparison.py     |
| one analytic scene: Torch level-set callable, bounds, media,           |
| frequencies, _ring_scan() -> 24 Tx/Rx pairs                           |
+-------------------------+-------------------------+-------------------+
                          | same callable           | same callable
                          v                         v
+---------------------------------------+  +-----------------------------+
| solvers/gpr_bem_mod/                  |  | solvers/sdf_to_ordered_     |
| ibim_geometry.py                      |  | boundary/                   |
| build_implicit_boundary_band()        |  | prepare_single_component()  |
| -> compress_implicit_boundary_band()  |  | -> fit_method_b()           |
| -> ImplicitBoundarySamples2D          |  | -> .discretize(N=128)       |
+-------------------+-------------------+  | -> PeriodicCurve2D          |
                    |                      +---------------+-------------+
                    v                                      |
+---------------------------------------+                  v
| solvers/gpr_bem_mod/                  |  +-----------------------------+
| solve_ibim_tmz_total_field_batch()    |  | solvers/gpr_bem_kress/      |
| -> full 24 x 24 receiver work         |  | solve_kress_tmz_total_      |
| -> paired 24-vector                   |  | field_batch()               |
+-------------------+-------------------+  | -> full 24 x 24 matrix      |
                    |                      | -> explicit diagonal P      |
                    |                      +---------------+-------------+
                    |                                      |
                    +------------------+-------------------+
                                       v
                    +--------------------------------------+
                    | Mie / independent nystrom_ref oracle |
                    | -> full-ring receiver L2 over 24     |
                    +--------------------------------------+

same analytic target/material/scan identity (not the Torch callable)
                          |
                          v
+-----------------------------------------------------------------------+
| solvers/gprmax_ref/cache_io.py: load_frequency_sweep()                 |
| translated procedural/voxel FDTD scene -> cached pair 0 only           |
+-------------------------+---------------------------------------------+
                          v
            pair-0-only cross-check; never ranked as L2/24
```

Thus “same SDF” means the MOD and Kress branches begin with the same implicit
field but discretize it independently; sharing MOD's unordered cloud would
invalidate the comparison. The existing gprMax cache was produced out of
process from the matching procedural scene, not by consuming that Python SDF.
It contains one Tx/Rx pair. MOD/Kress/Nyström can report full-ring relative L2
over 24 paired receivers at each frequency, while gprMax supplies only the
pair-0 relative error at each frequency. Those coverages must remain separate
in tables and gates.

## Validation ladder

Validation is deliberately layered:

1. Shared kernel, operator, and system tests under `pytest/gpr_bem_shared/`,
   with MOD-only adjoint, inverse, and derivative-kernel checks under
   `pytest/gpr_bem_mod/` and retained kdiff checks under
   `pytest/gpr_bem_kdiff/`. `pytest/gpr_bem_kress/` independently checks the
   ordered blocks, system, explicit receiver operator, and physical fields.
2. Circle fields against the analytic penetrable-cylinder Fourier–Bessel/Mie
   series.
3. Smooth ellipse and star fields against the independent `nystrom_ref`
   implementation. This isolates geometry/quadrature; it shares the Müller
   formulation and therefore is not an independent proof of its signs.
4. Cached gprMax FDTD as an independent physics cross-check. Cache lookup
   prefers harmonic `contsine`, then scaled-Ricker, then legacy sweep data.
5. Square and two-circle checks using gprMax plus self-convergence; these have
   weaker oracle coverage than circle/ellipse/star.
6. The dated five-shape solver/QBX closeout report in
   [`../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md`](../results/solver_comparisons/legacy/qbx-closeout-20260901/aggregate_metrics.md).
7. Solver-neutral recovery from wrong circle, ellipse, and seeded
   random-feature implicit initializations using independent analytic Mie data,
   with fixed-objective monotonicity, parameter accuracy, held-out frequency
   error, and linear-residual gates for MOD and Kress. The exact-target-boundary
   control isolates each solver's holdout discretization floor from inverse
   parameter error. A fourth case recovers the five-lobe star, including its
   lobe depth and phase, from independent `nystrom_ref` observations that are
   themselves gated for self-convergence; there the shared Method-B
   representation, not the forward solver, sets Kress' floor. The checked
   bundles are
   [`../results/inverse_solver_comparison/README.md`](../results/inverse_solver_comparison/README.md).

Ordinary comparisons include `ref`, `mod`, and the frozen kdiff baseline; the
smooth circle/ellipse/star rows also exercise Kress from the same SDF.
Archived QBX rows require `--include-qbx-archive`, are not accuracy gates, and
may explicitly reproduce invalid-clearance cases as historical evidence.

The tests in `pytest/ordered_boundary/` and `pytest/sdf_to_ordered_boundary/`
sit beside, not inside, this solver-validation ladder. Their SDF residual,
speed, curvature, self-intersection, reference-contour, and scalar manufactured
Kress-action measurements establish geometry/parameterization readiness. They
are not BIE/PDE field, operator, or solve errors. The parallel
`pytest/gpr_bem_kress/` suite does assemble physical operators and solve
fields. `pytest/sdf_inverse/` additionally exercises the common ordered
geometry, both paired forward adapters, the nondegenerate complex objective,
convergence from a wrong circle, and the star target's oracle seam and
lobe-parameter recovery. Broader forward comparisons remain in
`pytest/solver_comparisons/` and dated result bundles. The Kress sibling's
compact exact-curve and frozen
Method-B convergence/runtime evidence is indexed at
[`../results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md).

## Known limits

- High-frequency accuracy degrades sharply on the compressed representation;
  the Nyström oracle shows this is a discretization issue, not a failure of the
  Müller equation or the modeled physics.
- The compressed boundary is unordered and lacks high-order component
  geometry, preventing coherent singular quadrature and stable density
  transfer.
- The trace offset is empirical and tied to merge distance.
- Exact corners are not in the first ordered Kress milestone. They require a
  later piecewise-smooth, graded-panel/product-integration backend.
- Disconnected exterior inclusions are tested, but nested material regions,
  holes, and material-adjacency topology are not modeled generally.
- The legacy staged neural B-scan benchmark uses solver-generated truth, and
  its cache identity does not yet encode every solver/formulation choice. The
  new circle parameter comparison instead uses analytic Mie truth, but that
  oracle does not generalize to arbitrary shapes.
- The physical environment is homogeneous full-space, not layered ground.
- `nystrom_ref` is forward-only and currently single-component.
- `gpr_bem_kress` is forward-only, dense CPU/NumPy, lossless/nonmagnetic, and
  currently accepts one smooth simple component with safely separated points.
- The solver-neutral inverse differentiates the full black-box pipeline by
  parameter finite differences. It is capped at small parameter counts and is
  not practical for a full random SIREN. The checked neural case uses fixed
  seeded features and a bounded radial envelope; an unconstrained random field
  may fail the required one-component topology before any solve starts. The
  newer alternating MLP path avoids weight-wise differences by using a small
  gauge-fixed radial-Fourier data step and geometry-anchored neural
  re-distancing. Its fixed
  wrong-circle skip is an initialization contract, and its topology checks are
  finite-resolution diagnostics rather than a global proof.
- Existing gprMax caches cover only pair index 0, not the full 24-pair scan.
- QBX/kdiff are closed only for the compressed-cloud architecture; this is not
  a mathematical rejection of QBX on high-order panelized geometry.

## Ordered-boundary status

The implemented smooth single-component path is:

```text
SDF grid
  -> one ordered, oriented zero-level component
  -> safeguarded projection to phi=0
  -> smooth periodic evaluator
  -> consistent nodes, x', x'', tangents, normals, curvature, and weights
  -> all-block Kress/Nyström Müller assembly
```

The SDF remains the geometry variable. The ordered representation replaces
the geometry/quadrature interface consumed by the high-accuracy forward
backend and is reused by the low-dimensional inverse. Remaining milestones
and gates are in
[`ordered_boundary_nystrom_plan.md`](ordered_boundary_nystrom_plan.md); the
architectural reason for leaving QBX/kdiff is in
[`qbx_closure.md`](qbx_closure.md).

The continuous/sampled geometry contract, exact analytic/Fourier producers,
and ordered extraction plus A/B/C fitting from SDF contours exist. The
direct-import sibling solver assembles coherent all-block Kress differences,
solves the unsquared Müller system, and evaluates separated receivers from
`PeriodicCurve2D` through explicit `C=[D,-S]` rows. Its additive
`gpr_bem_kress.multicomponent` path accepts an `OrderedBoundary2D`, discovers
the component arity at runtime, and assembles the smooth cross-component
blocks. Exact/noncircular, same-SDF receiver, independent multi-cylinder, and
three implicit-initialization inverse cases exercise these paths. The sibling
solver remains outside the selector. The opt-in derivative/objective-adjoint
module covers one fixed interface only; multi-interface derivatives and a
scalable topology-changing neural inverse are not implemented.

## Canonical commands

```bash
# Maintained operational paths
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
python run_ibim_geometry_demo.py --solver=mod

# Solver-neutral implicit-initialization comparison; imports both directly
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py

# Shared suite against mod; shape comparisons import both packages directly
python -m pytest pytest/ --solver=mod -q

# Current five-shape comparison evidence
python -m pytest pytest/solver_comparisons/test_*_comparison.py -s -q
python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py -s -q

# Diagnostics, not production gates
python -m pytest \
  pytest/solver_comparisons/test_circle_comparison.py \
  --perfect-sampling -s -q
python -m pytest \
  pytest/solver_comparisons/test_aggregate_comparison_results.py \
  --include-qbx-archive -s -q

# Direct-import ordered-curve Müller peer
PYTHONPATH=solvers python -m pytest pytest/gpr_bem_kress -q

# Common inverse and hardened legacy-inverse contracts
PYTHONPATH=solvers python -m pytest -q \
  pytest/sdf_inverse pytest/gpr_bem_mod/test_ibim_inverse.py
```

## Code and document map

| Area | Canonical location |
|---|---|
| Geometry band/compression | `solvers/gpr_bem_mod/ibim_geometry.py` |
| Ordered contour scaffolding | `solvers/gpr_bem_mod/neural_sdf.py`, `geometry.py` |
| Forward operators/system | `solvers/gpr_bem_mod/ibim_tmz_forward.py`, `ibim_tmz_system.py` |
| Ordered-curve forward peer | `solvers/gpr_bem_kress/`, [`gpr_bem_kress_implementation.md`](gpr_bem_kress_implementation.md) |
| Ordered-curve solver evidence | `pytest/gpr_bem_kress/`, [`../results/ordered_boundary_nystrom/README.md`](../results/ordered_boundary_nystrom/README.md) |
| Legacy MOD neural adjoint/inverse | `solvers/gpr_bem_mod/ibim_tmz_adjoint.py`, `ibim_inverse.py` |
| Solver-neutral parameter inverse | `solvers/sdf_inverse/`, [`solver_neutral_inverse.md`](solver_neutral_inverse.md), `run_sdf_inverse_comparison.py`, `run_sdf_inverse_contour_video.py` |
| Current shape calculus | [`ibim_shape_derivative.md`](ibim_shape_derivative.md) |
| Experimental discrete Kress calculus and bounded inverses | `solvers/gpr_bem_kress/shape_derivative.py`, [`sdf_kress_followup_2026-09-06.md`](sdf_kress_followup_2026-09-06.md) |
| Precision oracle | [`nystrom_reference_study.md`](nystrom_reference_study.md) |
| Independent FDTD check | [`gprmax_reference_study.md`](gprmax_reference_study.md) |
| SDF-to-ordered-boundary geometry evidence | [`sdf_boundary_parameterization_implementation.md`](sdf_boundary_parameterization_implementation.md), `results/sdf_boundary_parameterization/` |
| Solver comparison tests/evidence | `pytest/solver_comparisons/`, `results/solver_comparisons/` |
| Inverse comparison tests/evidence | `pytest/sdf_inverse/`, `results/inverse_solver_comparison/` |
| Numerical history | [`validation_change_log.md`](validation_change_log.md) |
| Superseded plans | [`legacy/`](legacy/README.md) |
