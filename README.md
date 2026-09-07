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

An experimental direct-import sibling solver at `solvers/gpr_bem_kress/` has
an established one-`PeriodicCurve2D` core and an additive arbitrary-component
`OrderedBoundary2D` assembly. It assembles all four cancellation-safe Kress/Müller blocks,
solves the unsquared system, and evaluates separated receivers through an
explicit `ExteriorReceiverOperator` with `C=[D,-S]`. It owns a package-local
`Material` value and has no dependency on `gpr_bem_mod`. It remains outside
`solver_select`. Its opt-in `shape_derivative` module now supplies verified
fixed-grid geometry/material JVPs and a paired-objective conjugate adjoint;
the existing inverse drivers still use their unchanged numerical Jacobians.
It is now
invoked directly by [`run_sdf_inverse_comparison.py`](run_sdf_inverse_comparison.py),
which gives MOD and Kress the same Method-B curve and the same bounded
parameter finite-difference inverse against independent observations. Against
analytic Mie data it covers a wrong circle SDF, a rotated non-SDF ellipse, and
a topology-constrained seeded random-feature neural implicit. A fourth case
recovers the five-lobe star `r(t) = 0.05 (1 + 0.25 cos 5t)`, including its
lobe depth and phase, from independent `nystrom_ref` observations; see
[the inverse baseline](docs/solver_neutral_inverse.md),
[the four-case results](results/inverse_solver_comparison/README.md),
[its implementation record](docs/gpr_bem_kress_implementation.md), and
the [same-SDF solver-error/runtime snapshot](results/solver_comparisons/kress-peer-20260902/summary.md).
An experimental companion,
[`run_mlp_sdf_inverse_comparison.py`](run_mlp_sdf_inverse_comparison.py), uses
one validated `PeriodicCurve2D` as the accepted optimization geometry and a
full residual MLP as its trainable signed-distance representation. Modal
finite-difference probes perturb and solve the ordered curve directly, without
re-running marching squares or Method B. For the star-shaped benchmark the
curve is an authoritative, gauge-fixed radial Fourier state: accepted steps
change its centre and radius coefficients directly, so repeated updates cannot
accumulate geometry above the requested mode. Each accepted curve is then
re-distanced into every MLP weight, and the extracted MLP zero set is checked
against the canonical contour; representation error is audited but is not
recycled into the next Jacobian and does not trigger another BEM solve. The
default is cumulative low-to-high frequency continuation;
`--joint-full-band` and progressive-mode continuation are explicit ablations.
A damping floor, `k**4` curvature prior, refined trust-region damping, and
Armijo acceptance control unresolved directions. Its bundles carry a progress gate
only, not the parametric driver's accuracy gates; see
[`docs/solver_neutral_inverse.md`](docs/solver_neutral_inverse.md).
The completed joint Kress `k<=5`, 24-pair run is also a non-convergence result:
56 accepted updates reduced training relative L2 from `1.19325` to `0.79976`,
but holdout error ended at `1.07342` and maximum boundary error worsened from
`42.22` to `46.92 mm`. All 56 MLP fits and audits succeeded. The canonical
curve itself left the star-shaped class and accumulated `6.26 mm` RMS above
`k=5`, exposing that repeated local normal velocities were not a global
`k<=5` shape parameterization. Direction audits additionally found the joint
0.5/1.5/2.5 GHz initial step points away from the target, whereas the 0.5 GHz
`k<=3` step is target-aligned. The radial state and corrected
0.5 GHz/K3 -> 0.5+1.5 GHz/K5 -> full-band/K5 schedule address those two
specific defects. The completed post-fix run reached training and holdout
relative L2 errors `1.07e-8` and `1.34e-8`, maximum analytic boundary error
`2.57e-10 m`, and roundoff-only content above K5. Its full MLP state remains
formally nonconverged only because the extracted representation is `0.329 mm`
from the canonical curve, above the deliberately stricter `0.2 mm` gate.
The smooth circle, ellipse, and star comparison cases are the integration
surface: one callable SDF feeds independent MOD and Kress boundary paths before
their 24 paired receiver fields are compared. The existing gprMax cache is an
independent cross-check for pair index 0 only, not a full-ring L2 result.

Automatic unknown-count extraction and direct multi-Kress forwarding live in
`solvers/sdf_bem_multicomponent/`. Its canonical geometry is always an
`OrderedBoundary2D`, so one object is just the `M=1` case. The accompanying
Cassini validation starts from a large circle, passes through one explicitly
unsolved singular pinch, and finishes as two exact circles. Its video and
ragged component-aware archive are produced by
[`run_multicomponent_split_demo.py`](run_multicomponent_split_demo.py). The
fixed MLP inverse remains a deliberately one-curve optimizer; supporting a
split there requires a future topology-state handoff, not a predictor swap.

## Quick start

The [2026-09-05 SDF/Kress first batch](docs/sdf_kress_first_batch_2026-09-05.md)
adds explicit curve-only/final-export policies without changing strict defaults,
smooth-curve distance supervision, and a bounded parameterization-aware Fourier
experiment. It includes fresh saved-star timings and explicit failed-export
results. Material inversion, topology changes and 3-D are not part of that batch.

The [2026-09-06 follow-up](docs/sdf_kress_followup_2026-09-06.md) records the
complete discrete Kress derivative, distance/tangency controls, frozen neural
update metrics and bounded single-permittivity recovery. These are independent
opt-in experiments, not a change to established inverse defaults.

The separate [shape/material robustness branch](docs/material_robustness_2026-09-06.md)
adds training-only frequency continuation and bounded deterministic restarts
on the explicit curve, with common full-band selection and shared work caps.
It requires no SDF and does not add per-component materials or 3-D physics.

```bash
python run_ibim_rectangular_scan_forward.py --solver=mod
python run_ibim_circle_inverse_bscan.py --solver=mod
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --initial-model ellipse --max-iterations 8
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_sdf_inverse_comparison.py --target star
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_mlp_sdf_inverse_comparison.py --target star --solvers kress \
  --initial-shape ellipse --frequency-continuation
python run_sdf_inverse_contour_video.py \
  results/inverse_solver_comparison/wrong-star-nystrom-20260903
PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_multicomponent_split_demo.py
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
| `run_sdf_inverse_comparison.py` | Wrong-SDF inverse against a Mie circle or a Nystrom star, with a common objective and MOD/Kress forward dispatch |
| `run_mlp_sdf_inverse_comparison.py` | Experimental radial-Fourier curve-state inverse with direct modal BEM probes, cumulative-frequency continuation by default, and an audited full-MLP SDF representation |
| `run_sdf_inverse_contour_video.py` | Optional post-processing: side-by-side MOD/Kress contour video from an existing inverse bundle |
| `run_multicomponent_split_demo.py` | Automatic unknown-`M` extraction video: one circle, an explicitly unsolved pinch, then two circles |
| `run_sdf_boundary_parameterization_comparison.py` | Opt-in, solver-isolated A/B/C boundary parameterization study |
| `run_ordered_nystrom_validation.py` | Opt-in exact/frozen-curve `gpr_bem_kress` convergence and runtime study |
| `run_kress_shape_derivative_validation.py` | Opt-in actual discrete geometry/material derivative and paired-objective adjoint checks |
| `run_distance_tangency_comparison.py` | Metric-distance contacts versus zero-projection/tangent fitting with explicit fallbacks |
| `run_neural_metric_comparison.py` | Frozen neural-feature curve metrics versus explicit identity/Sobolev updates |
| `run_material_inverse_comparison.py` | Fixed-circle and joint radial-K2 shape/interior-permittivity recovery with immutable Mie data |
| `run_material_robustness_comparison.py` | Bounded full-band/continuation/multistart controls, frozen circle replay and independent noncircular data |
