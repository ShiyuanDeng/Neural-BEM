# Tests and validation

The live pipeline and solver roles are documented in
[`docs/current_architecture.md`](../docs/current_architecture.md). This file
owns test layout and reproduction commands only.

## Test layout

This directory now keeps only the Neural-SDF/IBIM mainline tests.

- `artefacts/test_neural_sdf.py`: SIREN SDF utilities, contour extraction, and surrogate losses.
- `artefacts/test_ibim_geometry.py`: implicit-boundary sampling, compression, and quadrature geometry.
- `artefacts/test_kdiff_t_assembly.py`: T-strategy isolation, legacy parity,
  full-row QBX source modes, and system-quadrant invariance.
- `artefacts/test_nystrom_reference.py`: independent smooth-boundary oracle
  checks and convergence controls.
- `artefacts/test_gprmax_ref_cache.py`: gprMax cache identity and lookup policy.
- `artefacts/test_ibim_tmz_forward.py`: implicit-boundary layer-potential and operator assembly.
- `artefacts/test_ibim_tmz_system.py`: implicit TMz forward system assembly and CPU/GPU consistency.
- `artefacts/test_ibim_tmz_theory_validation.py`: analytic transmission and
  representation checks.
- `artefacts/test_ibim_tmz_adjoint.py`: IBIM adjoint contexts and leading-order shape gradients.
- `artefacts/test_ibim_inverse.py`: end-to-end IBIM inverse-loop smoke and benchmark helpers.
- `artefacts/test_scan_paths.py`: Tx/Rx scan-path construction.
- `test_ibim_shape_derivative_kernels.py`: current Müller shape-kernel
  directional checks.
- `test_ordered_periodic_curve.py`: separate analytic/Fourier continuous
  producers and immutable node-based periodic curves, node jets, derived
  differential geometry, provenance, and resolution-independent validation.
- `test_ordered_boundary.py`: node-owned component IDs/slices and flattened BIE views,
  topology/clearance diagnostics, rejection cases, JSON reports, and static
  dependency isolation for the ordered geometry package.
- `test_sdf_boundary_frontend.py`, `test_sdf_boundary_methods_ab.py`, and
  `test_sdf_boundary_method_c.py`: the isolated shared SDF front end and the
  three smooth-boundary methods, including guarded checkpoint/fallback behavior.
- `test_sdf_boundary_metrics.py`, `test_sdf_boundary_experiment.py`,
  `test_sdf_boundary_notebook.py`, and `test_sdf_boundary_isolation.py`:
  common metrics/artifacts, controlled sweeps, artifact-only analysis, and
  proof that the experiment is not imported by active solver pipelines.
- `test_sdf_boundary_kress_proxy.py`: independent circle identities, the
  scalar logarithmic product rule, an independently integrated smooth
  remainder, spline/Fourier convergence behavior, even-node enforcement, and
  static isolation of the scratchpad probe from every solver implementation.
- `test_circle_comparison.py`: runs **both** solver packages side by side, plus
  gprMax, on a circle target and prints a one-row-per-solver metrics table
  against the Mie series. Also carries a `kernel_diff*` row (`solvers/kernel_diff_ref/`),
  `gpr_bem_mod`'s formulation with no finite trace offset, at the same N,
  always on a perfect boundary -- see `test_circle_kernel_diff_perfect_sampling`
  and `docs/validation_change_log.md`. See below.
- `test_square_comparison.py`: the parallel case for a square target (a real
  corner, and no closed-form oracle -- leans on gprMax and self-convergence
  instead). See below.
- `test_ellipse_comparison.py`: smooth non-circular ellipse target, using the
  standalone Nystrom solver as the numerical oracle and gprMax as an index-0
  FDTD cross-check.
- `test_star_comparison.py`: smooth star-shaped target with the same
  Nystrom-baselined structure as the ellipse comparison.
- `test_two_circle_comparison.py`: two disjoint circular components, using the
  same gprMax index-0/self-convergence structure as the square comparison.
- `test_aggregate_comparison_results.py`: runs the five comparison cases and
  exports tables, scalar metrics, scattered fields, boundary samples, and
  `geometry.png` files under `pytest/results/<case>/`, plus a combined
  `pytest/results/aggregate_metrics.md` report that states each case baseline.

All five comparison files carry a `gpr_bem_kdiff` row plus three assemblies
that use its identical solve path and replace only the hypersingular `T` block
when `--include-qbx-archive` is supplied:

- `gpr_bem_qbx`: same-node, no-oversampling full-row QBX;
- `qbx_fourier8`: 8x analytic Fourier sources (component-wise for two circles);
- `qbx_sdfraw8`: raw band from an 8x-refined SDF grid with IDW prolongation.

The last label describes grid refinement, not an exactly 8N source count; the
actual ratio and QBX clearance diagnostics are stored in each `metrics.json`.
These rows are experimental and are not accuracy-gated. `gpr_bem_kdiff`
itself is kernel-differenced quadrature assembled directly on the real (or,
for the circle under `--perfect-sampling`, perfect) boundary with no finite
trace offset.
They are retained as closeout evidence, not as candidate production solvers.
One regenerated five-shape pass over all three QBX rows took about 24.7
minutes, so they are omitted by default. See `docs/qbx_closure.md` for the decision and
`docs/validation_change_log.md` for the chronological experiments.

## Choosing a solver

Every file here except the shape-comparison files imports the plain name
`gpr_bem` and is unmodified from the original suite. `conftest.py` at the repo root decides which package
under `solvers/` that name resolves to:

```bash
python -m pytest pytest/                   # solvers/gpr_bem_ref (default)
python -m pytest pytest/ --solver=mod      # solvers/gpr_bem_mod
SOLVER=mod python -m pytest pytest/        # same
```

The selected package is printed in the pytest header, so every run says which
solver it exercised.

`test_circle_comparison.py`, `test_square_comparison.py`,
`test_ellipse_comparison.py`, `test_star_comparison.py`, and
`test_two_circle_comparison.py` deliberately ignore that flag: they import both
packages directly and run them in one process on the same case. They treat
`gpr_bem_ref` as the frozen first-kind control and `gpr_bem_mod` as the
modified formulation. The circle file gates against the analytic cylinder
reference, the square file against gprMax and self-convergence, the
ellipse/star files against the standalone Nystrom reference, and the
two-circle file against gprMax and self-convergence. Run any of them with `-s`
to see the table:

```bash
python -m pytest pytest/test_circle_comparison.py -s -q
python -m pytest pytest/test_square_comparison.py -s -q
python -m pytest pytest/test_ellipse_comparison.py -s -q
python -m pytest pytest/test_star_comparison.py -s -q
python -m pytest pytest/test_two_circle_comparison.py -s -q
python -m pytest pytest/test_aggregate_comparison_results.py -s -q

# Explicitly reproduce the archived QBX rows (slow; not a production gate):
python -m pytest pytest/test_aggregate_comparison_results.py \
  --include-qbx-archive -s -q
```

## Isolated SDF-boundary Kress proxy

The active fast check is:

```bash
PYTHONPATH=solvers python -m pytest -q \
  pytest/test_sdf_boundary_kress_proxy.py
```

The checked evidence is
[`results/ordered_nystrom/sdf-boundary-kress-proxy-20260902/summary.md`](results/ordered_nystrom/sdf-boundary-kress-proxy-20260902/summary.md).
It reports the smooth, geometry-dependent `q`-remainder error separately from
the error in the complete manufactured logarithmic action. This prevents the
known canonical convolution from masking differences between the frozen curve
representations. It also separates the earlier one-time SDF-to-curve runtime
from the runtime of one full-grid scalar logarithmic proxy action.

The checked source manifest and metrics plus the compact `frozen_curves/`
bundles make the recorded sweep reproducible without the full study's ignored
curve directory. Choose a new empty output directory:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scratchpad/sdf_boundary_kress_proxy.py \
  --artifact-root results/sdf_boundary_parameterization/study-20260902 \
  --curve-root pytest/results/ordered_nystrom/\
sdf-boundary-kress-proxy-20260902/frozen_curves \
  --output-dir results/sdf_boundary_parameterization/kress-proxy-NEW \
  --timing-repeats 9
```

This is a scalar manufactured diagnostic, not a Müller assembly or solver
row. It reconstructs the authoritative spline/Fourier coefficients once and
never refits a curve while changing the declared even-node ladder. Its action
timing includes dense `N x N` matrix formation and application; it is not the
cost of an FFT implementation, a four-block BIE assembly, or a solve. Each
reported converter time independently includes the same shared marching-
squares/projection front end, so converter times from A/B/C rows must not be
summed. Pass/fail is determined by the configured gates recorded with the
generated evidence.

`test_circle_comparison.py` also accepts `--perfect-sampling`, a diagnostic
toggle that swaps the real compressed boundary for exact uniform-arclength
circle nodes at the same N, to isolate how much error node irregularity is
responsible for.

gprMax cache lookup prefers the newer per-frequency cache layout generated by:

```bash
/home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
  --target-shape circle   # or square / ellipse / star / two_circles
```

The default is `--frequency-mode harmonic`: one background+target pair per
frequency driven by gprMax's continuous-sine `contsine` waveform at that exact
frequency. Cache lookup prefers harmonic entries, then the older per-frequency
scaled-Ricker entries, then the fixed-`1mm`, 1.5 GHz-centered broadband sweep.
