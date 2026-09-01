# Neural SDF BEM AD

Research code for 2-D TMz dielectric transmission, implicit neural/SDF
geometry, boundary-element forward modeling, and shape-based inversion.

## Project status

`gpr_bem_mod` is the maintained forward/adjoint/inverse baseline. The command
line still defaults to the frozen `gpr_bem_ref` control, so operational commands
must select `--solver=mod` explicitly.

The compressed-cloud QBX/kdiff investigation is closed. Current development
targets an ordered, component-aware SDF boundary followed by a coherent
Kress/Nyström Müller discretization.

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
- [Validation history](docs/validation_change_log.md)
- [QBX/kdiff closure decision](docs/qbx_closure.md)
- [Solver package guide](solvers/README.md)
- [Test and evidence guide](pytest/README.md)

## Repository layout

| Path | Role |
|---|---|
| `solvers/` | Frozen, operational, experimental, and oracle solver packages |
| `config/` | Shared target and simulation configuration |
| `pytest/` | Current validation gates, comparisons, and generated evidence |
| `docs/` | Current architecture, live plan, decisions, references, and history |
| `scratchpad/` | Explicitly non-production diagnostic scripts and retained probes |
| `run_ibim_*.py` | Forward, inverse, and geometry entry points |
