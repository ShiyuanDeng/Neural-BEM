# Maintained cleaned inverse

`bem_inverse` owns the cleaned SC/MA numerical implementation. It depends on
NumPy, SciPy, PyTorch, and the sibling `gpr_bem_kress`, `ordered_boundary`, and
`periodic_kress` packages. It has no runtime imports from `experiments/`, root
research drivers, or saved results. Use the existing EMNerf environment; this
is a source-tree package following the repository's `solvers/` convention.

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

`Problem` contains fitting inputs, never truth geometry or a scene ID. The
runner returns unscored numerical results and audits. Campaign code owns
synthetic-data generation, truth loading, and recovery scoring.

To select modal physics explicitly:

```python
from bem_inverse.modal_muller import register
register()
result = fit(problem, solver="modal_muller", geometry_update="certified_spectral")
```

To select a complete named recipe instead of individual slots:

```python
from bem_inverse import pipelines
result = pipelines.fit(problem, "modal_fixed", execution=Execution(device="auto"), output="path/to/run")
```

| Pipeline | Physics | Geometry update | Unresolved trial |
|---|---|---|---|
| `nodal_baseline` | `nodal_kress` | `spline` | hard stop (CI-001) |
| `nodal_fixed` | `nodal_kress` | `certified_spectral` | one promotion to N1024/2048 (`ResolutionResponse`) |
| `modal_fixed` | `modal_muller` | `certified_spectral` | hard stop; no modal response exists, and one is refused |

A pipeline only fills `fit`'s physics, geometry-update and resolution slots; policy, start
and localization stay with the caller. Results gain `pipeline` and `resolution_promoted`.

Calling `fit` without a pipeline keeps the legacy default: `nodal_kress` with the spline projected update. Supported
explicit geometry names are `spline`, `spectral`, `certified_spectral`,
`analytic_spectral`, and `gaussian_lipschitz`; the last two are experimental
and the Gaussian map failed ON-001 curved-state qualification. Device selection and physics
selection remain independent. See the
[campaign guide](../../experiments/cleaned_interface/README.md) for numerical
limits, execution semantics, and the recorded evidence.

## ON-001 opt-in controls

`CumulativePolicy(required_accuracy=.003)` requests a passed current endpoint
audit at accepted full-real-catalog states meeting the maximum per-frequency
residual criterion. Failed audits remain charged and retry only after the
residual halves or the geometry/physics resolution changes. Optional
`audit_aggregate_seconds=30` reserves ten seconds for the terminal audit.
The ordinary defaults retain the original schedule and separate audit budgets.

ON-001 confirmed this E rule on all 30 TG-002 pairs: 26/30 recovered in
both arms, median paired audited-output speedup 1.546x, no new recovery. Evidence:
[iteration 31](../../docs/iterations/cleaned_interfaces/iteration_31/01_results.md).
`reach_fraction` and `working_anchors` retain the tested research controllers;
reach clipping and subset proposals closed screen-negative. The experimental
`gaussian_lipschitz` geometry selector retains its complete discrete tangent
and one-time ambient scaling, but failed ON-001 curved-state finite-trial
qualification under the unchanged endpoint gate. It is not a qualified
replacement for `certified_spectral`. No recipe default was changed.

## Experimental fair nodal profile (PC-002)

`Execution(nodal_geometry_reuse="per_curve", nodal_resolution_profile="band_matched",
resolution=130, device="cuda")` opts into fit-local exact-curve CUDA geometry
reuse and stage-entry nodal accuracy selection. Legacy defaults remain fixed512
and reuse off. The seed matches modal trace dimension, rounded to even N and
increased to resolve stored geometry. Each selected pair must pass every
active field tolerance and the normalized Jacobian-column 1e-3 gate; trial
acceptance retains its existing refinement check. Selection work counts in
stage/global budgets. Endpoint audits compare the native profile and an
independent N1024 result against N2048, including the full-trial derivative.

The cache retains at most four entries and 256 MiB each of host/device geometry.
Its exact key includes coefficient bytes, shape, dtype, nodes and device; it
contains no frequency kernels, matrices, factors or acquisition waves.
Receipts report builds, hits, memory, timing and stage-selected resolutions.
LU and reciprocal solves use CUDA; receiver/incident waves and Jacobian
contractions remain on CPU. See the
[PC-002 priority plan](../../docs/iterations/cleaned_interfaces/iteration_28/03_plan.md).

## Code map

| Modules | Responsibility |
|---|---|
| `problem`, `physics`, `policy`, `runner` | Input contract, solver service/registration, executable policy, and fitting/audits |
| `geometry`, `geometry_selection` | Projected finite trial and explicit update selection |
| `spectral`, `certified`, `batched`, `analytic_projection` | Extracted selectable geometry mathematics |
| `modal_geometry`, `modal_operator`, `modal_muller`, `modal_cuda` | Fourier–Galerkin Müller service and execution |
| `continuation/` | Shared Fourier curves, forward operations, geometry validation, and LM optimizer |
| `nodal_geometry`, `nodal_resolution` | Fit-local exact nodal geometry reuse and truth-free stage profile qualification |
| `normal_basis`, `mie_localize`, `mie_grid`, `damped_cuda` | Frontier basis, exact-disk localization, and damped execution |
| `full_matrix`, `relaxed_gradient` | Opt-in full-matrix relaxation, complete reduced-loss gradient, and prefix policy |
| `n_update`, `n_reparam`, `device_certified` | Retained opt-in research geometry implementations; not promoted to defaults |
| `pipelines` | Named recipes (`nodal_baseline`, `nodal_fixed`, `modal_fixed`) that fill `fit`'s slots |
| `io` | Portable numerical receipts |

Dependency direction is campaigns → `bem_inverse` → reusable solver/geometry
packages. Put new campaign selection, benchmark paths, and truth scoring in
`experiments/cleaned_interface/`, not in this package.

Relaxed fitting uses an analytic reverse derivative of the discrete Kress
objective after eliminating the auxiliary field. It includes derivatives of
the system, sources, receiver rows and median-row-norm penalty, composed with
the selected projected geometry tangent. The LM gradient is complete; its
positive curvature model still uses frozen-weight receiver sensitivities.
The reverse geometry assembly runs on CPU and reuses existing CPU/CUDA LU
factors for one additional correction solve per frequency. Median ordering
and kernel branches are locally fixed; the objective is piecewise smooth.
This capability currently belongs to the nodal backend, not modal Müller.
Its experiment history and proposed numerical-resolution follow-up are indexed
in the [relaxed-BIE research track](../../docs/iterations/relaxed_bie/README.md).

Ordinary nodal stages also support an opt-in `ResolutionResponse` in
`continuation.lm_backend`. It checks retained bases and candidates, promotes
to a declared finer pair when qualified, rebuilds the production linearization,
and otherwise continues the existing backtracking search. The default remains
the original hard stop. Accuracy-limited exhaustion and an unresolved finer
base have explicit outcomes. The response enables work accounting before
threaded dispatch.

`fit_stage(..., pause_after=k)` returns a `StageCheckpoint` after an accepted
state. It retains the current residual/Jacobian, next damping, refined cache,
history and consumed ledger state; `resume=checkpoint` validates the matching
stage, objective, update, curve and ledger. `Ledger.restore` preserves elapsed
time and stage/global work. At the policy level, `runner.FitResume` carries
that checkpoint and the remaining resolved operation queue. The
[RB-001 driver](../../experiments/relaxed_bie/README.md) reconstructs these
states from qualified archived evidence and owns the historical input mapping.

## Compatibility and source provenance

The former runtime modules in `experiments.cleaned_interface`, six shared
modules in `experiments.shape_continuation`, and `modal_atlas.mie_localize`
forward to the same module objects here. This preserves class identity,
registration, historical pickle lookups, and experiments that temporarily
replace module attributes. Mixed NU modules retain their campaign commands
and re-export the extracted classes and functions.

Existing campaign CLIs are unchanged. They run legacy scene sets; new experiments use
[`experiments/benchmark`](../../experiments/benchmark/README.md) (TG-002):

```bash
python -m experiments.cleaned_interface inventory
python -m experiments.cleaned_interface plan --cases modal__c4__development_c
python -m experiments.cleaned_interface.modal_muller --help
```

CI-001 and FM-001 seals include `solvers/**/*.py`, including this package.
Saved source archives and manifests are preserved. A pre-extraction seal
correctly refuses the changed checkout; reproduce it with its recorded sources
or prepare a fresh campaign directory. Do not rewrite old seals to accept new
code.

## Validation

From the repository root:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CI_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

"$CI_PY" -m pytest pytest/bem_inverse experiments/cleaned_interface -q
```

`pytest/bem_inverse` guards the package boundary, compatibility, and standalone
execution. The existing cleaned-interface suite retains its historical
fixtures and independent comparisons: forward fields, complete-trial
derivatives, CPU/CUDA execution, audit equivalence, and bounded inverse paths.

For changes to shared continuation or lower-level physics/geometry, also run:

```bash
"$CI_PY" -m pytest experiments/shape_continuation \
  pytest/gpr_bem_kress pytest/ordered_boundary -q
```

These are bounded checks, not the 36-case campaign. Package extraction changes
code ownership, not recovery claims or runtime qualifications.
