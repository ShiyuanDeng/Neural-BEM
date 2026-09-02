# Neural SDF BEM AD

Research code for 2-D TMz dielectric transmission, implicit neural/SDF
geometry, boundary-element forward modeling, and shape-based inversion.

## Project status

`gpr_bem_mod` is the maintained compressed-cloud forward/adjoint/inverse
baseline. The normal selector still defaults to the frozen `gpr_bem_ref`
control, so selector-backed operational commands must choose `--solver=mod`
explicitly.

The compressed-cloud QBX/kdiff investigation is closed. The ordered path now
uses a component-aware SDF boundary followed by a coherent Kress/Nyström
Müller discretization. A solver-neutral exact/Fourier producer
and immutable node-based smooth-boundary contract are available under
`solvers/ordered_boundary/`. The direct-import Kress forward solver and the
new low-dimensional solver-neutral inverse now consume that contract. The
separate `solvers/sdf_to_ordered_boundary/` A/B/C study still reports geometry
and manufactured scalar Kress-proxy metrics, not physical solver errors.

An experimental direct-import sibling solver at `solvers/gpr_bem_kress/` now
takes one immutable
`PeriodicCurve2D`, assembles all four cancellation-safe Kress/Müller blocks,
solves the unsquared system, and evaluates separated receivers through an
explicit `ExteriorReceiverOperator` with `C=[D,-S]`. It owns a package-local
`Material` value and has no dependency on `gpr_bem_mod`. It remains outside
`solver_select` and has no operator adjoint or shape derivative. It is now
invoked directly by [`run_sdf_inverse_comparison.py`](run_sdf_inverse_comparison.py),
which gives MOD and Kress the same Method-B curve and the same bounded
parameter finite-difference inverse against analytic Mie data. It now covers
a wrong circle SDF, a rotated non-SDF ellipse, and a topology-constrained
seeded random-feature neural implicit; see
[the inverse baseline](docs/solver_neutral_inverse.md),
[the three-case results](results/inverse_solver_comparison/README.md),
[its implementation record](docs/gpr_bem_kress_implementation.md), and
the [same-SDF solver-error/runtime snapshot](results/solver_comparisons/kress-peer-20260902/summary.md).
The smooth circle, ellipse, and star comparison cases are the integration
surface: one callable SDF feeds independent MOD and Kress boundary paths before
their 24 paired receiver fields are compared. The existing gprMax cache is an
independent cross-check for pair index 0 only, not a full-ring L2 result.

## Quick start

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model ellipse --max-iterations 8
python -m pytest pytest/ --solver=mod -q
```

For selector-backed commands, omitting `--solver` runs the frozen
`gpr_bem_ref` package.

## Documentation

- [Documentation map](docs/README.md)
- [Current architecture](docs/current_architecture.md)
- [Solver-neutral SDF inverse baseline](docs/solver_neutral_inverse.md)
- [Ordered-boundary Kress/Nyström plan](docs/ordered_boundary_nystrom_plan.md)
- [SDF boundary parameterization implementation and results](docs/sdf_boundary_parameterization_implementation.md)
- [`gpr_bem_kress` Nyström/Müller implementation](docs/gpr_bem_kress_implementation.md)
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
| `run_sdf_inverse_comparison.py` | Wrong-SDF inverse with a common objective and MOD/Kress forward dispatch |
| `run_sdf_boundary_parameterization_comparison.py` | Opt-in, solver-isolated A/B/C boundary parameterization study |
| `run_ordered_nystrom_validation.py` | Opt-in exact/frozen-curve `gpr_bem_kress` convergence and runtime study |
