# SDF Boundary Parameterization: Implementation and Decision Record

Date: 2026-09-02

## Status and authority

This document records the implementation decisions for the isolated experiment that converts a two-dimensional implicit field into a smooth, ordered, periodic boundary parameterization. It should be read with:

- [`deep-research-report.md`](deep-research-report.md), which provides the literature review and broader design background; and
- [`neural_sdf_to_kress_implementation_guide.md`](neural_sdf_to_kress_implementation_guide.md), which is authoritative for the first-pass scope, software contract, comparison protocol, and implementation order.

The report discusses many promising methods. Their presence in the report is not permission to implement all of them. This first experiment implements only:

- Method A: periodic cubic-spline interpolation and arc-length refit;
- Method B: bandlimited Fourier least squares and arc-length refit; and
- Method C: Method B followed by staged SDF-constrained Fourier-coefficient refinement, arc-length refit, and a short final correction.

No boundary-integral equation, Kress product weights, Helmholtz kernel, Müller assembly, active inverse pipeline, or differentiable marching implementation is part of this work.

## Decision summary

The implementation uses **one module per method, one shared extraction front end, one canonical comparison driver, and one artifact-only analysis notebook**.

The user's idea of keeping the methods separate is correct at the representation and fitting level. Separate end-to-end scripts are not the canonical experiment, because independent scripts could evaluate different grids, choose different contours, project different point sets, or compute metrics at different resolutions. That would confound extraction error with representation error.

The adopted structure is therefore:

```text
implicit field + physical bounds + shared configuration
                         |
                         v
       one Cartesian marching/projection front end
                         |
              one frozen projected loop
                 /       |       \
                v        v        v
          Method A   Method B   Method C
             |          |          |
             +----------+----------+
                         |
             common metrics and artifacts
                         |
          CSV / JSON / NPZ / diagnostic plots
                         |
         artifact-only comparison notebook
```

Thin method-specific debugging entry points would be acceptable if they call this same library code, but they must not become independent implementations of contour extraction, projection, validation, or metrics. The canonical experiment is:

```bash
python run_sdf_boundary_parameterization_comparison.py \
  --profile smoke
```

The full convergence study is:

```bash
python run_sdf_boundary_parameterization_comparison.py \
  --profile study
```

The notebook is [`notebooks/sdf_boundary_parameterization_comparison.ipynb`](../notebooks/sdf_boundary_parameterization_comparison.ipynb). It reads saved artifacts; it does not perform contour extraction, fit coefficients, refine Method C, or define an alternative source of experimental truth.

## Integration with the existing geometry model

The repository already has the correct separation between continuous geometry and sampled solver geometry. This implementation extends that model instead of introducing parallel `ParametricBoundary2D` and `KressGeometry2D` class hierarchies.

### Continuous result

The authoritative smooth output of every successful method is the existing `ordered_boundary.PeriodicParameterization2D`:

- it represents one connected component on a periodic interval;
- `evaluate(t)` returns position, first derivative, second derivative, and an optional third derivative at arbitrary parameters;
- it retains explicit orientation and provenance;
- it can be validated independently of a solver; and
- it can be discretized repeatedly without refitting the geometry.

The method-native representations retain the actual fitted state:

- `PeriodicSplineBoundary` owns periodic spline knots and power-basis coefficients;
- `FourierBoundary` owns real cosine and sine coefficient arrays; and
- both expose `to_parameterization()` to produce the shared continuous contract.

Point samples are therefore never the authoritative final curve.

### Sampled result

When uniform nodes are required, `PeriodicParameterization2D.discretize(N, require_even=True)` creates the existing immutable `PeriodicCurve2D`. It stores:

- $t_j = 2\pi j/N$, without a repeated endpoint;
- points, first and second derivatives, and an optional third derivative;
- speed, unit tangent, outward normal, signed curvature; and
- periodic trapezoidal arc-length weights.

This is the future solver-facing geometry seam. The present experiment tests its readiness but does not pass it to any active BIE assembler.

The distinction is important: projected marching nodes initialize a fit; `PeriodicParameterization2D` is the smooth result; `PeriodicCurve2D` is one requested uniform discretization of that result.

The guide's boundary-interface vocabulary is mapped onto the existing repository contract rather than copied under a second set of class and method names:

| Required concept | Existing repository API |
|---|---|
| $\gamma(t)$, $\gamma'(t)$, $\gamma''(t)$ | `PeriodicParameterization2D.evaluate(t).points`, `.first_derivatives`, `.second_derivatives` |
| uniform parameter samples | `PeriodicParameterization2D.discretize(N, require_even=...)` |
| tangent, outward normal, speed, curvature | derived immutable arrays on `PeriodicCurve2D` |
| area and $ds$ weights | `PeriodicCurve2D.signed_area` and `.arc_length_weights` |
| representation/fit/validation diagnostics | `BoundaryMethodResult`, `ArcLengthResult`, and the existing ordered-boundary validation report |

Keeping diagnostics beside the operation that produced them, rather than mutating the geometry object, preserves the current immutable geometry design. Thus the implementation satisfies the guide's semantic interface while deliberately retaining the repository's `evaluate`/`discretize` naming and its separation of continuous geometry, sampled geometry, and diagnostics.

### Components

The low-level front end records all closed components and assigns deterministic spatial component identifiers. It never selects the largest component. The Phase-1 entry point `prepare_single_component(...)` fails before fitting unless exactly one component is detected.

This reconciles two requirements:

- the initial comparison is restricted to one smooth, simple, closed component; and
- the data model remains compatible with the existing `OrderedBoundaryParameterization2D`, where disconnected components are represented by independent periodic curves rather than concatenated into one discontinuous map.

## Repository layout and responsibilities

The implementation is isolated under [`solvers/sdf_to_ordered_boundary/`](../solvers/sdf_to_ordered_boundary/):

| Module | Responsibility |
|---|---|
| `fields.py` | `ImplicitField2D`, NumPy-callable and lazy Torch adapters, field-call accounting, analytic circle/ellipse/radial-Fourier benchmark fields and references |
| `frontend.py` | Cartesian grid evaluation, marching squares, physical-coordinate conversion, closure/bounding-box checks, CCW orientation, deterministic phase, self-intersection checks, chord resampling, safeguarded Newton projection |
| `representations.py` | Coefficient-owning periodic cubic-spline and Fourier representations, plus linear Fourier least squares |
| `arclength.py` | Shared dense arc-length integration, monotone inversion, native-representation refit, and displacement/speed diagnostics |
| `method_a.py` | Periodic cubic-spline baseline |
| `method_b.py` | Fourier least-squares baseline |
| `method_c.py` | Staged SDF-constrained Fourier refinement, checkpoint validation, final correction, and Method-B fallback |
| `results.py` | Immutable method and reparameterization result records |
| `metrics.py` | Common geometry, topology, parameterization, spectral, and Kress-readiness metrics |
| `artifacts.py` | Strict JSON, flattened CSV, non-pickled NPZ, and common diagnostic plots |
| `experiment.py` | Analytic cases, reproducible smoke/study profiles, shared-front-end orchestration, accounting, and artifact persistence |

The root [`run_sdf_boundary_parameterization_comparison.py`](../run_sdf_boundary_parameterization_comparison.py) driver owns shape/profile sweeps and writes the experiment artifacts. The notebook reads those artifacts and performs comparison and visualization only. The driver refuses a non-empty output directory so an old and a new sweep cannot be silently mixed.

## Shared implicit-field and front-end contract

`ImplicitField2D` requires:

```python
value(xy)       # (..., 2) -> (...,)
gradient(xy)    # (..., 2) -> (..., 2)
```

Coordinates are physical `(x, y)`. The field may be a true SDF or a generic regular implicit function. Analytic field objects declare `is_signed_distance` and a sign convention; Method C and normalized residual metrics use that metadata rather than assuming $\lVert\nabla F\rVert=1$.

Available adapters and fixtures include:

- `CallableImplicitField2D` for NumPy-compatible value and gradient callables;
- `TorchImplicitField2D`, which imports Torch lazily and can use a supplied spatial-gradient function, a model's `spatial_gradient`, or Torch autograd;
- `CountedImplicitField2D`, which records vectorized calls and the number of physical points evaluated;
- `CircleSDF`, an exact Euclidean SDF;
- `EllipseLevelSet`, explicitly marked as a generic dimensionless level set; and
- `RadialFourierLevelSet`, including a smooth radial-star constructor and an analytic reference parameterization.

The shared front-end sequence is fixed:

1. evaluate the field on one physical Cartesian grid;
2. run `skimage.measure.find_contours` at the configured level;
3. convert array `(row, column)` locations to physical `(x, y)` coordinates;
4. reject open contours and contours touching the supplied bounding box;
5. retain every component, orient it counterclockwise, set a deterministic phase, and reject polygon self-intersections;
6. resample each cyclic polygon by cumulative chord length;
7. apply safeguarded iterative Newton/closest-point projection to the zero set;
8. reject or explicitly report near-critical gradients and non-converged points;
9. recheck orientation and self-intersections after projection; and
10. optionally perform a second chord resampling and reprojection before assigning final chord-length parameters.

The projected points and their parameters are immutable and shared unchanged by A, B, and C for a given field/grid run.

### Front-end configuration

`FrontendConfig` makes the following choices explicit:

- physical bounds in repository form `((xmin, ymin), (xmax, ymax))`;
- Cartesian `grid_shape=(ny, nx)`;
- projected sample count;
- contour level;
- bounding-box and contour-closure tolerances;
- self-intersection and minimum-area tolerances; and
- whether to perform the second resample/reprojection pass.

`ProjectionConfig` controls:

- field-residual tolerance;
- maximum iteration count;
- minimum gradient norm;
- denominator safeguard;
- maximum correction as a fraction of local grid spacing; and
- whether non-convergence raises immediately.

The result retains raw contours, initial chord-resampled points, every projection pass, per-point convergence/iteration/clipping diagnostics, final projected points, chord-length parameters, polygon diagnostics, grid data, and optional field-call counts.

## Method contracts

### Method A: periodic cubic spline

Method A interpolates the common projected points with a true periodic cubic boundary condition, differentiates the retained spline analytically, performs the shared arc-length inversion/refit in the same spline representation, and validates the final continuous curve.

This is intentionally an interpolation baseline. No hidden smoothing parameter is used. Its finite knot smoothness remains a scientific limitation and is measured rather than concealed.

`MethodAConfig` contains the arc-length and continuous-validation configurations.

### Method B: Fourier least squares

Method B fits independent coordinate functions in one real trigonometric design matrix. It requires at least `2K+1` samples, retains conditioning and residual diagnostics, reparameterizes by arc length, and refits at the same bandwidth.

It does not optimize an SDF loss. This separation is essential: Method B is the strong linear baseline against which Method C must demonstrate an improvement.

`MethodBConfig` exposes Fourier bandwidth, least-squares `rcond`, arc-length resolution/refit count, and continuous-validation configuration.

### Method C: constrained Fourier refinement

Method C requires a successful, valid Method-B `FourierBoundary` and starts from those exact coefficients. It optimizes coefficients using the implicit field's values and first spatial gradients. The staged objective supports:

- raw or gradient-normalized zero-set fidelity;
- an anchor to the common projected loop;
- derivative-weighted spectral regularization;
- speed-uniformity and minimum-speed penalties;
- oriented normal agreement when the field sign convention is known; and
- an optional nonlocal-distance penalty.

Stages, weights, iteration counts, checkpoint interval, relative learning rates, dense sample counts, Adam parameters, gradient clipping, speed threshold, anchor-drift limit, and allowable residual degradation are configurable through `MethodCConfig`, `RefinementStage`, and `RefinementWeights`.

Each stage retains the valid checkpoint with the lowest weighted objective for that stage; objectives with different stage weights are not compared as though they were the same scalar. The chosen checkpoint starts the next stage. The history contains every optimizer step plus structured validation checkpoints, including intersections, minimum nonlocal sampled distance, speed, and residuals. After nonlinear shape refinement, Method C applies the common arc-length refit and a short final correction.

The public field contract deliberately requires only $F$ and $\nabla F$. For a generic field, the normalized-fidelity denominator and optional field-normal target therefore use a documented stop-gradient policy: the numerator follows the exact Fourier-coefficient chain rule, while differentiating those terms through a field Hessian is deferred. This also keeps the lazy Torch adapter solver-neutral; Torch computes spatial gradients, then the coefficient optimizer uses the analytic Fourier basis.

The final curve is accepted only if it remains valid, regularly parameterized, close setwise to the original projected loop, within configured area/perimeter drift, within the configured speed-ratio envelope, and no worse than Method B in both maximum and RMS normalized residual. The brief final-correction anchor is recorded separately from the hard setwise component anchor.

If an intermediate checkpoint becomes invalid, Method C stops that stage and restores its earlier best valid checkpoint before continuing. If a stage initializer is invalid, optimization throws an error, or the returned curve develops bad speed, drift, self-intersection, or fails final acceptance, Method C returns Method B's representation with status `fallback`, the failure reason, and the recorded history. A complicated method is not allowed to win merely by returning its last iterate.

### Shared arc-length configuration

`ArcLengthConfig` independently exposes:

- dense integration/inversion resolution;
- native refit sample count; and
- validation resolution used to measure refit displacement and speed change.

Arc-length refitting is applied to A and B as required by the implementation guide, and to C after its first nonlinear refinement. The final computational nodes are still uniform in the resulting periodic parameter. Arc length is a way to improve that parameter map; it is not a replacement for uniform computational `t_j`.

## Metrics, artifacts, and notebook contract

`BoundaryMetricConfig` separates dense geometry resolution, reference-set resolution, sampled topology resolution, FFT resolution and tail cutoff, Kress-diagonal probe resolution/offsets, frozen-curve even node counts, gradient safeguard, intersection tolerance, and nonlocal-neighbour exclusion.

The metrics remain separate rather than being collapsed into a score:

- raw maximum and RMS field residual;
- gradient-normalized maximum and RMS residual;
- minimum and maximum field-gradient norm;
- signed area, perimeter, and reference errors;
- phase-independent symmetric sampled-set distances;
- nearest-reference normal-angle and curvature errors;
- seam errors through derivative order two;
- minimum, maximum, and mean speed, speed ratio, minimum/mean speed, and speed coefficient of variation;
- sampled self-intersection count, minimum nonlocal distance, and winding tests;
- common FFT coefficient tails weighted through derivative orders zero, one, and two;
- the smooth Kress-remainder diagonal proxy at several offsets; and
- frozen-curve samples at configurable even $N$, including uniform-grid validity, speed/log-speed ranges, $ds$ weights, orientation, signed area, and convergence of the $ds$-weight sum to the dense perimeter.

Every configured $N$ measurement discretizes the same accepted `PeriodicParameterization2D` with `require_even=True`; no curve is refitted as $N$ changes. The smoke profile uses $N\in\{32,64,128\}$, while the study continues through $N\in\{64,128,256,512,1024\}$ so it gets past possible spline-knot aliasing. The CLI exposes this independent axis as `--kress-samples`.

Reference-set comparisons sample both candidate and reference at the independent `reference_resolution`. They do not reuse a coarser field-metric grid, which would create an avoidable Hausdorff floor. A finite nearest-sample floor can still remain when two parameter phases differ; convergence interpretation must account for the configured reference resolution.

The driver adds run identity, method status/failure reason, grid resolution, projected sample count, representation resolution or bandwidth, runtime, optimization history, and field/gradient call accounting.

Each output root contains:

```text
manifest.json
metrics.json
metrics.csv
curves/
plots/
```

- JSON is standards-compliant and never writes `NaN` or `Infinity`.
- CSV is a flattened table with a stable union of columns.
- NPZ curve bundles reject object arrays and do not rely on pickling.
- Plots use one common six-panel format: extracted/fitted geometry, pointwise field residual, speed, curvature, coordinate Fourier spectrum, and either reference-normal error or normalized residual.

The notebook reads `manifest.json`, `metrics.csv`/`metrics.json`, and curve bundles, then builds its own tabular and graphical analysis. It must not call the fitting methods. This keeps experimental generation deterministic, command-line reproducible, and independent of notebook cell history.

## Tests and commands

Focused unit tests are organized under `pytest/sdf_to_ordered_boundary/`, with
the independent geometry-contract tests beside them under
`pytest/ordered_boundary/`. These tests stop at geometry/parameterization
readiness. Their residual and discrepancy columns are not BIE/PDE solver
errors; even the Kress proxy is a manufactured scalar product-rule action with
no physical operator assembly or solve.

- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_frontend.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_frontend.py): field contracts, analytic references, Torch optionality, field accounting, circle and generic ellipse extraction/projection, zero/multiple components, deliberately underresolved grids, open/bounding-box contours, step limiting, near-critical gradients, self-intersections, and cyclic resampling;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_methods_ab.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_methods_ab.py): coefficient ownership, spline seam continuity, exact finite-Fourier recovery, circle recovery at `K=1`, arc-length speed improvement, underdetermined-fit rejection, and explicit rejection when a near-Nyquist fit creates a self-intersection from a simple input polygon;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_method_c.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_method_c.py): exact Method-B initialization, generic ellipse and radial-star refinement, analytic coefficient gradients, normalized-field scale invariance, weighted valid-checkpoint selection and restoration, full optimizer history, component/area/perimeter diagnostics, and exception fallback;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_metrics.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_metrics.py): exact-circle metrics, phase-independent set comparison, normalized residual scaling, self-intersection detection, frozen-curve $N/2N/4N$ readiness and perimeter convergence, strict artifact writers, and required plots;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_experiment.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_experiment.py): one-front-end fairness, coefficient/sample artifacts, primary metric columns, converter time/count accounting, CLI overrides, and non-empty-output protection;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_notebook.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_notebook.py): valid artifact-only notebook structure and explicit grid/bandwidth/frozen-node/status analysis;
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_isolation.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_isolation.py): import-direction isolation and adaptation of all three outputs to the existing continuous/even-node ordered-boundary contracts; and
- [`pytest/sdf_to_ordered_boundary/test_sdf_boundary_kress_proxy.py`](../pytest/sdf_to_ordered_boundary/test_sdf_boundary_kress_proxy.py): analytic Fourier identities, independent reference checks, frozen-bundle replay, and explicit solver isolation for the scalar Kress proxy.

The focused Python tests can be run with:

```bash
PYTHONPATH=solvers python -m pytest -q \
  pytest/sdf_to_ordered_boundary \
  pytest/ordered_boundary
```

Generate a fresh smoke bundle in the driver's timestamped default directory with:

```bash
python run_sdf_boundary_parameterization_comparison.py \
  --profile smoke
```

Run the full grid/bandwidth convergence experiment with:

```bash
python run_sdf_boundary_parameterization_comparison.py \
  --profile study
```

The smoke profile is integration evidence, not a method-ranking study. The study profile is the full convergence sweep.

## How results must be interpreted

No method is selected visually and no scalar aggregate score defines a winner.

For each shape and extraction grid, the exact same projected loop must be fed to every method. Interpretation should then proceed in this order:

1. reject invalid status, open curves, wrong component count, self-intersections, non-positive/nearly degenerate speed, or failed seam checks;
2. compare field and reference-set fidelity among the valid curves;
3. inspect speed, spectral tails, curvature, and the Kress-diagonal proxy;
4. check area and perimeter stabilization;
5. check convergence under Cartesian-grid refinement;
6. independently check convergence under projected sample count and spline/Fourier representation resolution;
7. for B and C, examine plateaus or deterioration as `K` increases; and
8. sample a frozen final curve at different even `N` without refitting it, so node-resolution effects are not confused with geometry changes.

Method C's `fallback` status is a scientific result, not a hidden failure to remove from the table. It means the nonlinear method did not demonstrate a valid improvement over its Method-B initializer under the configured acceptance policy.

Plots are diagnostic evidence for locating residual oscillations, crowding, curvature artifacts, or unresolved spectral tails. They are not the ranking criterion.

## Deliberate limitations and deferred work

This implementation does not provide:

- a Kress quadrature rule or any BIE assembly;
- coupling to `gpr_bem_ref`, `gpr_bem_mod`, `gpr_bem_kdiff`, `gpr_bem_qbx`, or the active inverse/adjoint drivers;
- topology changes during optimization;
- certified/adaptive contouring or predictor-corrector contour tracking;
- differentiable marching squares or end-to-end differentiation through extraction;
- MeshSDF, DMTet, FlexiCubes, Analytic Marching, or Marching Neurons;
- direct shrinking from a circle;
- Beylkin-Rokhlin tangent-angle fitting;
- positive radial or speed-plus-tangent-angle production representations;
- learned parametric decoders;
- neural-Hessian production curvature; or
- near-touching-component/close-evaluation quadrature.

Additional current limitations are:

- marching-squares topology remains grid-resolution dependent;
- sampled self-intersection and minimum-distance checks are numerical, not certified;
- general Fourier coordinates do not guarantee simplicity by construction;
- Method C is nonconvex and its outcome depends on explicitly recorded weights and schedules;
- the cubic spline has finite global smoothness at knots;
- arc-length refitting introduces a measured geometric displacement;
- radial-Fourier fixture positivity is checked densely rather than certified analytically; and
- a generic ellipse or radial level-set residual is not a physical distance unless normalized by gradient magnitude.

These limitations are reasons to report convergence and failure status, not reasons to silently tune away unsuccessful runs.

## Isolation from current solver pipelines

This work is opt-in research infrastructure:

- it lives in a new `sdf_to_ordered_boundary` package;
- it consumes the solver-neutral `ordered_boundary` geometry contract;
- active solver packages do not import it;
- it does not alter `solver_select.py` or any default solver selection;
- it does not modify forward, adjoint, inverse, QBX, k-difference, or IBIM execution;
- importing the package does not choose a solver or write artifacts; and
- the comparison driver writes only to the explicitly supplied output directory.

Future integration should happen only after this comparison establishes a valid method and resolution policy. At that point the integration seam is a deliberately sampled `PeriodicCurve2D`, not the SDF, marching polygon, optimizer, or notebook.

## Empirical smoke-run results

The checked run used the project EMNerf Python environment:

```bash
MPLCONFIGDIR=/tmp/neural_sdf_bem_smoke_mpl \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_boundary_parameterization_comparison.py \
  --profile smoke \
  --output results/sdf_boundary_parameterization/smoke-REPRO
```

That explicit evidence target is now non-empty and is deliberately protected against accidental overwrite. Reproduce the smoke run with the timestamped-default command above or choose a new empty directory.

It produced three shared front ends and 15 method rows: 14 `success`, one `fallback`, and zero hard failures. Every reported curve had positive minimum speed and zero sampled self-intersections. The strict artifacts are in [`results/sdf_boundary_parameterization/smoke-20260902/`](../results/sdf_boundary_parameterization/smoke-20260902/): [`manifest.json`](../results/sdf_boundary_parameterization/smoke-20260902/manifest.json), [`metrics.csv`](../results/sdf_boundary_parameterization/smoke-20260902/metrics.csv), [`metrics.json`](../results/sdf_boundary_parameterization/smoke-20260902/metrics.json), 15 native-coefficient/sample NPZ bundles, 15 run records, three front-end bundles, and 15 six-panel plots.

The single fallback is Method C on the radial-Fourier star at $K=4$. Its final normalized maximum/RMS residual did not remain within the configured Method-B envelope, so the recorded C geometry is the valid Method-B fallback. This is the intended safety policy, not a missing row.

Selected B-to-C observations from this one-grid integration run are shown only to verify the metrics path:

| Shape | K | B max $|F|$ | C status / max $|F|$ | B speed ratio | C returned speed ratio |
|---|---:|---:|---:|---:|---:|
| circle | 4 | $4.65\times10^{-12}$ | success / $2.91\times10^{-12}$ | 1.0000 | 1.0000 |
| circle | 8 | $4.22\times10^{-13}$ | success / $2.37\times10^{-13}$ | 1.0000 | 1.0000 |
| rotated ellipse | 4 | $2.65\times10^{-2}$ | success / $1.70\times10^{-2}$ | 1.111 | 1.169 |
| rotated ellipse | 8 | $2.43\times10^{-3}$ | success / $2.08\times10^{-3}$ | 1.017 | 1.038 |
| radial-Fourier star | 4 | $8.89\times10^{-2}$ | fallback / $8.89\times10^{-2}$ | 1.636 | 1.636 |
| radial-Fourier star | 8 | $2.06\times10^{-2}$ | success / $1.61\times10^{-2}$ | 1.279 | 1.313 |

These rows expose trade-offs but do not establish a winner. The smoke profile has one $65\times65$ extraction grid, 64 projected points, and only $K\in\{4,8\}$.

## Full grid, sample-count, bandwidth, and frozen-node study

The full study used Cartesian grids $65^2$, $129^2$, and $257^2$; projected sample counts $M\in\{128,256\}$; Fourier bandwidths $K\in\{4,8,16,32\}$; and frozen-curve even node counts $N\in\{64,128,256,512,1024\}$. Its local artifacts are in [`results/sdf_boundary_parameterization/study-20260902/`](../results/sdf_boundary_parameterization/study-20260902/), including [`manifest.json`](../results/sdf_boundary_parameterization/study-20260902/manifest.json), [`metrics.csv`](../results/sdf_boundary_parameterization/study-20260902/metrics.csv), [`metrics.json`](../results/sdf_boundary_parameterization/study-20260902/metrics.json), 162 coefficient/sample bundles, 162 run records, 18 shared front-end bundles, and 162 six-panel plots. In accordance with the repository's existing `/results/**/*.npz` and `/results/**/*.png` policy, the full-study JSON/CSV evidence is versioned while its reproducible NPZ/PNG files remain local; the smaller checked smoke bundle under `results/sdf_boundary_parameterization/smoke-20260902/` versions all formats.

The sweep produced 162 rows: all 18 Method-A rows and all 72 Method-B rows succeeded; Method C returned 28 accepted refinements and 44 guarded Method-B fallbacks; there were no hard failures. All returned curves had positive minimum speed and zero sampled self-intersections. Of the C fallbacks, 32 failed the max/RMS residual envelope and 12 failed the speed-ratio envelope.

Method-C acceptance counts out of the six grid/$M$ cases at each bandwidth were:

| Shape | $K=4$ | $K=8$ | $K=16$ | $K=32$ |
|---|---:|---:|---:|---:|
| circle | 6/6 | 3/6 | 1/6 | 0/6 |
| rotated ellipse | 6/6 | 6/6 | 0/6 | 0/6 |
| radial-Fourier star | 0/6 | 6/6 | 0/6 | 0/6 |

The convergence evidence is not a visual ranking:

- Grid refinement produced a plateau at fixed method, $M$, and $K$. Safeguarded Newton projection already placed samples on the analytic zero set at the coarse grid once the correct component was resolved. For example, at $M=256$, Method A's normalized maximum residual remained approximately $6.80\times10^{-10}$ for the circle, $3.71\times10^{-8}$ for the ellipse, and $2.56\times10^{-6}$ for the star across all three grids.
- Increasing $M$ from 128 to 256 reduced Method A's normalized maximum residual by about $16\times$ for the circle and ellipse and $25\times$ for the star. Method B was effectively unchanged at fixed $K$; its bandwidth controlled the resolved geometry in these cases.
- Method B showed clear bandwidth convergence. On the finest-grid, $M=256$ ellipse, normalized maximum residual fell from $2.43\times10^{-2}$ at $K=4$ to $5.97\times10^{-8}$ at $K=32$; on the star it fell from $8.89\times10^{-2}$ to $3.98\times10^{-4}$. Circle geometry was already represented to roundoff at $K=4$.
- Accepted Method-C runs often improved low-bandwidth fidelity while spending some speed uniformity. At ellipse $K=8$, the finest-case normalized maximum residual changed from $2.23\times10^{-3}$ to $3.95\times10^{-4}$ while speed ratio changed from 1.02 to 1.07. At star $K=8$, residual changed from $2.05\times10^{-2}$ to $1.15\times10^{-2}$ while speed ratio changed from 1.28 to 1.35. At higher bandwidth the acceptance gates usually returned B because there was little safe improvement left.
- Sampled reference-set discrepancies reached a finite-resolution floor: the ellipse Hausdorff measure plateaued near $3.5\times10^{-4}$ by $K=16$ even while field residual continued to fall. The circle's point-cloud Hausdorff/normal values varied with sampling phase although its field residual stayed at roundoff, so those values are not evidence of geometric deterioration.
- Every accepted or fallback continuous curve was also sampled without refitting through $N=1024$. All node sets were finite, positive-speed, counterclockwise, endpoint-free, and had positive $ds$ weights. Method A exposed the expected knot-grid aliasing plateau at $N=64,128$, then its worst relative perimeter error decreased from $1.16\times10^{-6}$ at $N=256$ to $7.23\times10^{-8}$ at $N=512$ and $4.25\times10^{-9}$ at $N=1024$ (roughly $16$--$17\times$ per doubling). B and returned C geometries reached roundoff-level perimeter error by $N=256$. This is why the stored ladder extends beyond the largest spline knot count.

These observations establish bandwidth convergence for B and selected accepted C runs, projected-sample convergence for A, and a grid plateau after correct extraction/projection. They do not establish a universal winning method.

The artifact-only notebook was executed against the full study and loaded all 162 CSV rows and all 162 NPZ bundles. It found zero shared-front-end identifier mismatches and produced 78 grid-trend rows, 21 bandwidth-trend rows, and 648 adjacent frozen-$N$ comparisons. The final focused verification command covered the new SDF package plus the existing ordered-boundary contract tests:

```text
66 passed, 0 failed
```

The only emitted warnings were Matplotlib/PyParsing deprecations from the pinned environment; they did not originate in the geometry implementation.

## Subsequent isolated logarithmic-product proxy

A later, explicitly requested follow-up applies a scalar Kress logarithmic
product rule to frozen coefficient-owning A/B/C outputs. It remains a
non-production scratchpad diagnostic and does not change this package's scope
or connect any fitted curve to an active solver. It reports the smooth,
geometry-dependent remainder error separately from the full manufactured
action error. Runtime is likewise split: converter rows each include their
identical shared front end and must not be summed, while action time means
dense `N x N` proxy-matrix formation and application, not an FFT, BIE
assembly, or solver time. The skimmed error/runtime table and its checked
`frozen_curves/` reproduction inputs are in
[`results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md`](../results/sdf_boundary_parameterization/kress-scalar-proxy-20260902/summary.md),
and its rationale, independent-reference construction, gates, and limitations
are recorded in
[`validation_change_log.md`](validation_change_log.md#frozen-sdf-boundaries-isolated-scalar-kress-proxy).
