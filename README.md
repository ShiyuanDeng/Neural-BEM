# Neural SDF BEM AD

Research code for 2-D TMz dielectric transmission, implicit neural/SDF
geometry, boundary-element forward modeling, and shape-based inversion.

## Project status

`gpr_bem_mod` is the maintained forward/adjoint/inverse baseline. The command
line still defaults to the frozen `gpr_bem_ref` control, so operational commands
must select `--solver=mod` explicitly.

The compressed-cloud QBX/kdiff investigation is closed. Current development
targets an ordered, component-aware SDF boundary followed by a coherent
Kress/Nyström Müller discretization. A solver-neutral exact/Fourier producer
and immutable node-based smooth-boundary contract are now available under
`solvers/ordered_boundary/`; no forward solver consumes them by default yet.
An opt-in `solvers/sdf_to_ordered_boundary/` experiment now compares spline,
Fourier, and SDF-constrained Fourier producers on one shared extracted loop;
it is likewise not connected to a solver pipeline. Its geometry and scalar
manufactured Kress-proxy metrics are not physical solver errors.

An experimental direct-import backend at
`solvers/gpr_bem_mod/ordered_nystrom/` now takes one immutable
`PeriodicCurve2D`, assembles all four cancellation-safe Kress/Müller blocks,
solves the unsquared system, and evaluates separated receivers. It remains
outside `solver_select` and every operational forward/adjoint/inverse driver;
see [its implementation record](docs/ordered_nystrom_implementation.md) and
the [skimmed solver-error/runtime tables](results/ordered_boundary_nystrom/README.md).

## Quick start

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
python -m pytest pytest/ --solver=mod -q
```

Omitting `--solver` runs the frozen `gpr_bem_ref` package.

## Documentation

- [Documentation map](docs/README.md)
- [Current architecture](docs/current_architecture.md)
- [Ordered-boundary Kress/Nyström plan](docs/ordered_boundary_nystrom_plan.md)
- [SDF boundary parameterization implementation and results](docs/sdf_boundary_parameterization_implementation.md)
- [Ordered Nyström/Müller candidate implementation](docs/ordered_nystrom_implementation.md)
- [Validation history](docs/validation_change_log.md)
- [QBX/kdiff closure decision](docs/qbx_closure.md)
- [Solver package guide](solvers/README.md)
- [Test and evidence guide](pytest/README.md)

## Repository layout

| Path | Role |
|---|---|
| `solvers/` | Frozen, operational, experimental, and oracle solver packages |
| `config/` | Shared target and simulation configuration |
| `pytest/` | Tests grouped by solver, oracle, geometry package, or comparison role |
| `results/` | Generated evidence grouped by experiment family and dated run |
| `docs/` | Current architecture, live plan, decisions, references, and history |
| `scratchpad/` | Explicitly non-production diagnostic scripts and retained probes |
| `run_ibim_*.py` | Forward, inverse, and geometry entry points |
| `run_sdf_boundary_parameterization_comparison.py` | Opt-in, solver-isolated A/B/C boundary parameterization study |
| `run_ordered_nystrom_validation.py` | Opt-in exact/frozen-curve Müller convergence and runtime study |
