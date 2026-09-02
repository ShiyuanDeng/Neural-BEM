# Solvers

For the end-to-end geometry, forward, adjoint, and inverse pipelines, see
[`docs/current_architecture.md`](../docs/current_architecture.md). The
implemented low-dimensional inverse is described in
[`docs/solver_neutral_inverse.md`](../docs/solver_neutral_inverse.md); remaining
ordered-boundary work is tracked in
[`docs/ordered_boundary_nystrom_plan.md`](../docs/ordered_boundary_nystrom_plan.md).

The repository keeps a frozen/reference BEM pair plus isolated experimental
operator assemblies.  Ref/mod remain separate packages; kdiff/QBX share one
solve path and vary only the hypersingular Muller difference block.

| Package | Role |
|---|---|
| `gpr_bem_ref/` | The original. **Frozen** — treat it as the control. |
| `gpr_bem_mod/` | Operational forward/adjoint/inverse baseline. Maintained changes go here. |
| `gpr_bem_kress/` | Experimental ordered `PeriodicCurve2D` Kress/Müller peer solver; direct import only. |
| `gpr_bem_kdiff/` | Frozen experimental compressed-cloud baseline and isolated T-assembly seam. |
| `gpr_bem_qbx/` | Archived full-row QBX T strategies; diagnostics, not a production solver. |
| `gpr_bem_ndiff/` | Archived/unsupported normal-offset experiment; unvalidated and not selector-wired. |
| `ordered_boundary/` | Solver-neutral continuous producers plus immutable ordered BIE nodes and diagnostics. |
| `periodic_kress/` | Shared canonical periodic logarithmic product weights; no geometry or physics ownership. |
| `sdf_to_ordered_boundary/` | Shared SDF extraction/Method-B fitting used by `sdf_inverse`, plus the opt-in A/B/C geometry study. |
| `sdf_inverse/` | Common single-component implicit extraction, MOD/Kress dispatch, and bounded low-dimensional parameter-FD inverse. |

The measured QBX/kdiff production-direction investigation is closed. See
[`docs/qbx_closure.md`](../docs/qbx_closure.md) for the timing and accuracy
data, the important accuracy qualification, admissibility failures, retained
artifacts, and reopening criteria. `gpr_bem_mod` remains the operational
neural-adjoint solver. Kress is also available through the direct-import
`sdf_inverse` comparison, but that path uses a numerical parameter Jacobian
and does not add a Kress adjoint.

They start byte-identical. `diff -rq --exclude=__pycache__ gpr_bem_ref gpr_bem_mod`
shows exactly what you have changed.

## Why they are named apart

Two packages both called `gpr_bem` cannot be imported into one interpreter, which
would make a single-process numerical comparison impossible. Naming them apart
costs nothing — the packages use only relative imports internally (`from
.ibim_geometry import ...`) and never `import gpr_bem`, so the top-level directory
name is free.

Selector-backed code writes `from gpr_bem import ...`. `solver_select.py`
decides which package that name resolves to, by aliasing it into `sys.modules`
(submodules included, so class identity is preserved and the `isinstance`
checks inside the solver keep working). Direct comparison code imports named
peer packages instead; it does not mutate selector behavior.

## Running against one or the other

`gpr_bem_mod` is operational but is not the selector default. An omitted flag
runs frozen `gpr_bem_ref`; selector-backed maintained
forward/adjoint/inverse commands must use `--solver=mod` explicitly.

Selector-backed tests live in `pytest/gpr_bem_shared/` and run unchanged
against either solver. The full `pytest/` tree also contains package-specific,
reference, geometry, and cross-solver groups:

```bash
python -m pytest pytest/                   # ref, the default
python -m pytest pytest/ --solver=mod      # mod
SOLVER=mod python -m pytest pytest/        # same
```

The alias made available to `gpr_bem_shared/` is printed in the pytest header.
Tests under `gpr_bem_mod/` import that package explicitly and ignore the flag.

Drivers — all three take the same flag, and the rectangular forward driver writes
to a solver-specific output directory (`results/rectangular_loop_forward_{ref,mod}`)
so two runs cannot overwrite each other:

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
python run_ibim_geometry_demo.py --solver=mod
```

The solver-neutral implicit-initialization driver is separate from that selector. It
extracts and fits one `PeriodicCurve2D`, passes the same nodes and arc weights
to MOD through an adapter or directly to Kress, and applies an identical
bounded parameter finite-difference inverse to both:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py
```

Its observations come from the analytic circle Mie series. The checked result
and limitations are in
[`results/inverse_solver_comparison/README.md`](../results/inverse_solver_comparison/README.md)
and [`docs/solver_neutral_inverse.md`](../docs/solver_neutral_inverse.md).

Notebook — `notebooks/_build_notebook.py` reads the `SOLVER` environment variable
(default `ref`) and prints which package it resolved.

## Comparing them

The files under `pytest/solver_comparisons/` ignore the selection mechanism and
import peer packages directly, running them in one process on the same case and
printing one row per solver. Smooth circle, ellipse, and star comparisons give
MOD and Kress independent discretizations of the same SDF and normalize Kress'
full source-by-receiver response to the paired scan diagonal. The circle file
gates against the Mie series; the square file (a target with a real corner, and
no closed-form oracle) gates against gprMax and self-convergence instead; the
ellipse/star files gate against `nystrom_ref`, the standalone Nystrom oracle:

```bash
python -m pytest pytest/solver_comparisons/test_circle_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_square_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_ellipse_comparison.py -s -q
python -m pytest pytest/solver_comparisons/test_star_comparison.py -s -q
```

Those are the files to extend as you add metrics worth watching. Existing
gprMax caches contain only the index-0 Tx/Rx pair: their table value is a
one-pair relative error at each frequency, whereas the BEM/Nyström rows report
the full 24-pair receiver L2 at each frequency. Do not label the gprMax row as
full-ring coverage.

The checked, skimmed same-SDF error/runtime snapshot is
[`results/solver_comparisons/kress-peer-20260902/summary.md`](../results/solver_comparisons/kress-peer-20260902/summary.md).

Do not read the adjacent `pytest/ordered_boundary/` or
`pytest/sdf_to_ordered_boundary/` measurements as solver errors. They test the
geometry contract, SDF fidelity, and one manufactured scalar Kress action; they
do not assemble or solve the physical BIE. Solver field/operator and inverse
errors belong to `pytest/gpr_bem_kress/`, `pytest/sdf_inverse/`, and
`pytest/solver_comparisons/`, with result bundles under
`results/ordered_boundary_nystrom/`, `results/inverse_solver_comparison/`, and
`results/solver_comparisons/`, respectively.

## Other solver packages under here

Not part of the `ref`/`mod` pair, and not selected by `--solver`:

| Package | Role |
|---|---|
| `nystrom_ref/` | Standalone explicit-boundary Nystrom oracle (`docs/nystrom_reference_study.md`). Deliberately shares no numerics with `gpr_bem_*`. |
| `kernel_diff_ref/` | Diagnostic: hosts `nystrom_ref`'s kernel-differenced quadrature against IBIM's own boundary object (`ImplicitBoundarySamples2D`), circle-only, perfect-sampling-only. Not an oracle -- see its module docstring and `docs/validation_change_log.md`. |
| `gprmax_ref/` | Cache-driven wrapper around an out-of-process FDTD run (`docs/gprmax_reference_study.md`). |
| `ordered_boundary/` | Shared NumPy-only node boundary, with separate exact/Fourier parameterization producers, for future Kress, kernel-difference, QBX, panel, or other BIE backends. |
| `periodic_kress/` | Universal full-log periodic weights reused by the scalar proxy and ordered Müller candidate. |
| `sdf_to_ordered_boundary/` | Shared marching/projection front end, spline/Fourier/SDF-refined producers, common metrics, and study orchestration; Method B is also reused by `sdf_inverse` (`docs/sdf_boundary_parameterization_implementation.md`). |
| `gpr_bem_kress/` | Experimental dense all-block Kress/Müller solver accepting exactly one immutable `PeriodicCurve2D`; owns its package-local `Material`, explicit receiver operator, system, and forward results; direct import only. |
| `sdf_inverse/` | Common Method-B geometry, legacy-MOD adapter, paired MOD/Kress prediction, circle/ellipse/random-feature implicit controls, and bounded parameter-FD Levenberg--Marquardt loop. |

## Selecting experimental T assembly in the kdiff solve

This interface exists to reproduce controlled operator experiments. It is not
a production solver-selection path. In particular, a finite QBX result with
invalid clearance is not a validated result.

The default and explicit legacy calls are equivalent:

```python
gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(...)
gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
    ...,
    t_assembly=gpr_bem_kdiff.LegacyLocalT(),
)
```

Full-row QBX uses the same solve function.  Only the T strategy changes:

```python
from gpr_bem_qbx import FullRowQBX, ParameterizedFourierSources

gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
    ...,
    t_assembly=FullRowQBX(
        source=ParameterizedFourierSources(
            parameterization=curve,
            oversampling_factor=8,
            target_parameters=target_t,  # optional for uniform ordered targets
        ),
        expansion_order=16,
    ),
)
```

Select `SameNodeSources()` for the plain no-oversampling full-row operator.
For disconnected analytic curves, use `ComponentParameterizedFourierSources`
with one `FourierComponent` per curve so Fourier prolongation cannot couple
unrelated components. For raw SDF-band sources, select `RawSDFBandSources` and
pass `sdf_fn` to the same solve call. Its `grid_refinement_factor=8` refines
the Cartesian grid; it does not promise exactly 8N retained band sources.

The resulting `system.t_assembly_report` records the source count, actual
source ratio, prolongation error, Fourier conditioning where applicable,
clearance, parameters, cache state, and T assembly time. Nonzero invalid
clearance counts make a row diagnostic rather than a validated QBX result.
