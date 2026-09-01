# Solvers

Two copies of the BEM solver package, so a formulation change can be developed
and measured against the original without either one moving underneath the other.

| Package | Role |
|---|---|
| `gpr_bem_ref/` | The original. **Frozen** — treat it as the control. |
| `gpr_bem_mod/` | The working copy. Convention/formulation changes go here. |

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
