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

The default remains `nodal_kress` with the spline projected update. Supported
explicit geometry names are `spline`, `spectral`, `certified_spectral`, and
`analytic_spectral`; the last is experimental. Device selection and physics
selection remain independent. See the
[campaign guide](../../experiments/cleaned_interface/README.md) for numerical
limits, execution semantics, and the recorded evidence.

## Code map

| Modules | Responsibility |
|---|---|
| `problem`, `physics`, `policy`, `runner` | Input contract, solver service/registration, executable policy, and fitting/audits |
| `geometry`, `geometry_selection` | Projected finite trial and explicit update selection |
| `spectral`, `certified`, `batched`, `analytic_projection` | Extracted selectable geometry mathematics |
| `modal_geometry`, `modal_operator`, `modal_muller`, `modal_cuda` | Fourier–Galerkin Müller service and execution |
| `continuation/` | Shared Fourier curves, forward operations, geometry validation, and LM optimizer |
| `normal_basis`, `mie_localize`, `mie_grid`, `damped_cuda` | Frontier basis, exact-disk localization, and damped execution |
| `full_matrix`, `relaxed_gradient` | Opt-in full-matrix relaxation, complete reduced-loss gradient, and prefix policy |
| `n_update`, `n_reparam`, `device_certified` | Retained opt-in research geometry implementations; not promoted to defaults |
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
