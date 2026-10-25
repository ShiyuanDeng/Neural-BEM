# Maintained cleaned inverse

`bem_inverse` owns the cleaned SC/MA numerical implementation. It depends on
NumPy, SciPy, PyTorch, and the sibling `gpr_bem_kress`, `ordered_boundary`, and
`periodic_kress` packages. It has no runtime imports from `experiments/`, root
research drivers, or saved results. Use the existing EMNerf environment; this
is a source-tree package following the repository's `solvers/` convention.

## Reading the implementation

Use the [inverse information chain](../../docs/reference/inverse_information_chain.md):
`runner.fit()` → `fit_stage.fit_stage()` → the selected mathematical module.
`fit_stage()` keeps the iteration, damping-retry and backtracking loops visible.
Two local steps carry the mathematics: `evaluate` (A1–A4 forward solves, then
the B5 residual) and `linearize` (B6–B8). A trial curve is accepted when its
loss is lower than the current loss. Numerical conditions live in `checks.py`.

`fit_stage()` receives the selected methods as functions, chosen once where the
method is selected:

- `forward_solve(curve, observation, contrast, resolution)` comes from
  `physics.make_backend(solver)`, together with its physics context. Each file in
  `forward_solvers/` owns one context class (`ModalMuller`, `NodalKress`), its
  `forward_solve`, the reciprocal derivative, the resolution profile and the
  frontier, and registers the class with the function.
- `geometry_update(normal_update, *, prepared)` comes from
  `geometry_selection.make_update(name)`, together with its update object. Each
  file in `geometry_update_methods/` owns its preparation, stored data,
  measurements and `geometry_update()` function. Ordinary curve operations live
  in `continuation/geometry.py`.

`work.Ledger` charges every solve and derivative through `Ledger.calls`, which
also runs the active frequencies on the configured threads.

```python
from bem_inverse import Execution, make_backend
context, forward_solve = make_backend('nodal_kress', Execution(device='cpu'))
prediction = forward_solve(curve, observation, contrast, resolution)
```

Repeated calls should reuse one context, which caches geometry. Resolution is
`8*K_trace` for modal physics and the node count for nodal physics.

## API

From the repository root, set `PYTHONPATH=solvers:.`. The numerical package
also works with only the absolute `solvers/` directory on `PYTHONPATH`, from
outside the repository.

```python
from bem_inverse import (
    FourierCurve, PointSourceAcquisition, Observation, Problem, Execution, fit,
)

# `problem` is a Problem with an initial curve, matched real/damped observed
# catalogs, acquisition geometry, contrast, and physical length units.
result = fit(
    problem,
    solver="nodal_kress",
    execution=Execution(device="cpu", frequency_threads=1),
    output="path/to/fresh-run",
)
```

`Problem` contains fitting inputs, never truth geometry or a scene ID. `fit`
returns the unscored endpoint and `final_stage` (its M, storage band and any
stage-local geometry update). It does not check itself at a finer resolution;
an independent endpoint audit belongs to the caller. The TG-002 campaign runs
[`experiments/benchmark/audit.py`](../../experiments/benchmark/audit.py) after
`fit` returns, then scores against truth.

To select a complete named recipe instead of individual slots:

```python
from bem_inverse import pipelines
result = pipelines.fit(problem, "modal_fixed", execution=Execution(device="auto"), output="path/to/run")
```

| Pipeline | Physics | Geometry update |
|---|---|---|
| `nodal_baseline` | `nodal_kress` | `spline` (CI-001) |
| `nodal_fixed` | `nodal_kress` | `spectral` |
| `modal_fixed` | `modal_muller` | `spectral` (the TG-002 default) |

A pipeline fills only `fit`'s physics and geometry-update slots; policy, start
and localization stay with the caller. Selecting `solver='modal_muller'`
directly needs `forward_solvers.modal_muller.register()` first. Bare `fit()`
keeps `nodal_kress` with the spline update. Supported geometry names are
`spline`, `spectral`, `certified_spectral`, `analytic_spectral`,
`gaussian_lipschitz`, `similarity`, and the three GU-001 updates
`uncentred_spectral`, `n_update` and `slider`.

Every geometry update checks the final trial curve: coefficient area, sampled
minimum speed and sampled segment intersections. The spectral family builds
the trial curve from one N-point refit; `n_update` and `slider` add an exact
linear coefficient step with no refit.

The GU-001 updates keep the gauge in three ways. `uncentred_spectral` stores
the arclength refit R(w_a) itself. `n_update` moves along N = -i z' and slides
along z', and runs with the level penalty
([`level_penalty.py`](level_penalty.py), `fit(..., penalty=LevelPenalty())`),
which adds speed-unevenness rows under the data residual. `slider` takes the
linear step that moves the boundary normally and keeps the relative speed
change even. Terms are in [the glossary](../../GLOSSARY.md). `certified_spectral` keeps its optional certificate decisions.
Analytic spectral and Gaussian updates remain experimental; the Gaussian map
failed ON-001 curved-state qualification.

[`policies.py`](policies.py) names recipes as a parent plus one change; run
`python -m experiments.benchmark policies` for the table. The opt-in
four-phase schedule is `continuation_policy.ShapeFrequencyPolicy` (CS-001).
The agreement damping rule with its two progress exits is DP-001's. Both were
measured before the finer re-evaluations were removed (NR-001); their result
pages are on `feature/shape-frequency-continuation`.

`Execution(nodal_geometry_reuse="per_curve")` reuses exact-curve CUDA nodal
geometry within a fit; `nodal_resolution_profile="band_matched"` seeds the nodal
resolution from the storage band (PC-002, planned on `feature/shape-frequency-continuation`).

`fit_stage(..., pause_after=k)` returns a `StageCheckpoint` after an accepted
state with the current Jacobian, gradient, next damping, history and ledger.
`resume=checkpoint` checks the matching stage, update, curve and ledger;
`Ledger.restore` keeps elapsed time and stage/global work. `runner.FitResume`
carries the checkpoint and the remaining operation queue.

## Code map

| Modules | Responsibility |
|---|---|
| `problem`, `physics`, `policy`, `policies`, `pipelines`, `runner` | Inputs, physics registry and counters, the executable policy, named recipes, the operation queue |
| `fit_stage`, `stage_types`, `work`, `errors` | One stage's loops, its records, work charging and stop codes |
| `level_penalty` | Optional speed-unevenness rows added to the loss (GU-001) |
| `forward_solvers/`, `forward_batch` | Physics contexts and forward solves; dispatch over active frequencies |
| `a1_geometry`, `a2_muller`, `a3_waves`, `a4_fields`, `modal_cuda` | Modal Müller A1–A4 mathematics and its CUDA assembly |
| `b5_residual`, `b7_data_jacobian`, `b8_gauss_newton`, `c9_lm`, `c12_iteration`, `checks` | Residual, data Jacobian, Gauss–Newton, LM proposal, damping and the numerical conditions |
| `geometry_selection`, `geometry_update_methods/`, `continuation/` | Geometry methods and their selection; curves, the nodal forward model, geometry caching |
| `localization`, `mie_localize`, `mie_grid`, `normal_basis`, `reach`, `nodal_geometry`, `damped_cuda` | Exact-disk localization, frontier basis, reach clipping, nodal geometry reuse and damped CUDA assembly |
| `io` | Portable numerical receipts |

Dependency direction is campaigns → `bem_inverse` → reusable solver/geometry
packages. Put campaign selection, benchmark paths, endpoint audits and truth
scoring in `experiments/`, not in this package.

Modal radial coefficients come directly from analytic Bessel products; see the
[derivation](../../docs/reference/modal_radial_coefficients.md). Geometry-side
steps still sample the curve: the trial move and arclength reset, validity
checks, the domain box and the frontier
([sampling scope](../../docs/reference/node_free_scope.md)).

## Removed in the 2026-10 reorganisation

[The plan](../../docs/cleanup/bem_inverse_architecture_2026-10-24.md) lists
what went and why: compatibility shims and old import paths, the research
controllers and objectives, refined C11 solves and resolution promotion, the
2N-point geometry check, nodal stage selection, and the in-fit audits.
Historical results that used them keep their recorded meaning.

## Validation

On this organized branch, the retained tests are under `pytest/`:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 -m pytest pytest/bem_inverse -q
```

Shared geometry and physical solver checks remain in `pytest/ordered_boundary`
and `pytest/gpr_bem_kress`. Six extended-precision Bessel comparisons fail on
platforms whose `longdouble` has 52 mantissa bits; two validity-order and one
resume exact-equality test are intermittent at about 1e-16.
