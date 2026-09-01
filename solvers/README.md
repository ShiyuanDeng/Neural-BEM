# Solvers

The repository keeps a frozen/reference BEM pair plus isolated experimental
operator assemblies.  Ref/mod remain separate packages; kdiff/QBX share one
solve path and vary only the hypersingular Muller difference block.

| Package | Role |
|---|---|
| `gpr_bem_ref/` | The original. **Frozen** — treat it as the control. |
| `gpr_bem_mod/` | The working copy. Convention/formulation changes go here. |
| `gpr_bem_kdiff/` | Frozen experimental compressed-cloud baseline and isolated T-assembly seam. |
| `gpr_bem_qbx/` | Archived full-row QBX T strategies; diagnostics, not a production solver. |

The measured QBX/kdiff production-direction investigation is closed. See
[`docs/qbx_closure.md`](../docs/qbx_closure.md) for the timing and accuracy
data, the important accuracy qualification, admissibility failures, retained
artifacts, and reopening criteria. `gpr_bem_mod` remains the operational
inverse/adjoint-capable solver while ordered-boundary Kress/Nyström work is
developed separately.

They start byte-identical. `diff -rq --exclude=__pycache__ gpr_bem_ref gpr_bem_mod`
shows exactly what you have changed.

## Why they are named apart

Two packages both called `gpr_bem` cannot be imported into one interpreter, which
would make a single-process numerical comparison impossible. Naming them apart
costs nothing — the packages use only relative imports internally (`from
.ibim_geometry import ...`) and never `import gpr_bem`, so the top-level directory
name is free.

Everything that consumes a solver still writes `from gpr_bem import ...`.
`solver_select.py` decides which package that name resolves to, by aliasing it
into `sys.modules` (submodules included, so class identity is preserved and the
`isinstance` checks inside the solver keep working).

## Running against one or the other

Tests — the files in `pytest/` are unmodified and run against either:

```bash
python -m pytest pytest/                   # ref, the default
python -m pytest pytest/ --solver=mod      # mod
SOLVER=mod python -m pytest pytest/        # same
```

The chosen package is printed in the pytest header, so a run is self-documenting.

Drivers — all three take the same flag, and the rectangular forward driver writes
to a solver-specific output directory (`results/rectangular_loop_forward_{ref,mod}`)
so two runs cannot overwrite each other:

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
python run_ibim_geometry_demo.py --solver=mod
```

Notebook — `notebooks/_build_notebook.py` reads the `SOLVER` environment variable
(default `ref`) and prints which package it resolved.

## Comparing them

`pytest/test_circle_comparison.py`, `pytest/test_square_comparison.py`,
`pytest/test_ellipse_comparison.py`, and `pytest/test_star_comparison.py`
ignore the selection mechanism and import both packages directly, running them
in one process on the same case and printing one row per solver. The circle
file gates against the Mie series; the square file (a target with a real
corner, and no closed-form oracle) gates against gprMax and self-convergence
instead; the ellipse/star files gate against `nystrom_ref`, the standalone
Nystrom oracle:

```bash
python -m pytest pytest/test_circle_comparison.py -s -q
python -m pytest pytest/test_square_comparison.py -s -q
python -m pytest pytest/test_ellipse_comparison.py -s -q
python -m pytest pytest/test_star_comparison.py -s -q
```

Those are the files to extend as you add metrics worth watching.

## Other solver packages under here

Not part of the `ref`/`mod` pair, and not selected by `--solver`:

| Package | Role |
|---|---|
| `nystrom_ref/` | Standalone explicit-boundary Nystrom oracle (`docs/nystrom_reference_study.md`). Deliberately shares no numerics with `gpr_bem_*`. |
| `kernel_diff_ref/` | Diagnostic: hosts `nystrom_ref`'s kernel-differenced quadrature against IBIM's own boundary object (`ImplicitBoundarySamples2D`), circle-only, perfect-sampling-only. Not an oracle -- see its module docstring and `docs/validation_change_log.md`. |
| `gprmax_ref/` | Cache-driven wrapper around an out-of-process FDTD run (`docs/gprmax_reference_study.md`). |

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
