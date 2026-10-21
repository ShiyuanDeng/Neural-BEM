# Maintained cleaned inverse

`bem_inverse` owns the cleaned SC/MA numerical implementation. It depends on
NumPy, SciPy, PyTorch, and the sibling `gpr_bem_kress`, `ordered_boundary`, and
`periodic_kress` packages. It has no runtime imports from `experiments/`, root
research drivers, or saved results. Use the existing EMNerf environment; this
is a source-tree package following the repository's `solvers/` convention.

## Reading the implementation

Use the [inverse information chain](../../docs/reference/inverse_information_chain.md):
`runner.fit()` → `fit_stage.fit_stage()` → the selected mathematical module.
The retry loops stay in `fit_stage.py`; numerical conditions live in `checks.py`.

Each file in `geometry_update_methods/` owns its preparation, stored data,
measurements and `geometry_update()` entry point, without update-class
inheritance. Ordinary curve operations live in `continuation/geometry.py`.

`endpoint.py` owns independent endpoint calculations, `objective.py` owns
dispatch/caches, and `work.py` owns charging. Old geometry paths retain
compatibility exports and call these implementations.

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

The [agreed continuation schedule](../../docs/iterations/CI-SPD/CONTINUATION_SCHEDULE.md)
has an opt-in implementation, `bem_inverse.continuation_policy.ShapeFrequencyPolicy`:
exact translation/scaling initialization at damped 0.25 GHz, the preserved
frequency ladder and M/K progression, four full-catalog stages with
(M,K_geometry)=(11,24)/(15,32)/(19,40)/(25,52), then full release at (95,192).
The recorded CS-001 comparison used `geometry_update="certified_spectral"`;
stage-local similarity affects the initial fit only, and independent endpoint
checks retain the selected ordinary geometry update. The default `CumulativePolicy` remains unchanged.
The bounded paired TG-002 [CS-001 validation](../../docs/iterations/CI-SPD/CS-001_results.md)
recovered 4/8 versus 5/8 for the current-policy control: 1.499x median
speedup on four retained successes, but a C-shape recovery regression.
The compact shape storage selects lower modal trace cutoffs, and the
regression stopped at the candidate-resolution gate. This configuration
is not qualified for promotion; full release was not reached by this screen.

To select modal physics explicitly:

```python
from bem_inverse.modal_muller import register
register()
result = fit(problem, solver="modal_muller", geometry_update="spectral")
```

To select a complete named recipe instead of individual slots:

```python
from bem_inverse import pipelines
result = pipelines.fit(problem, "modal_fixed", execution=Execution(device="auto"), output="path/to/run")
```

| Pipeline | Physics | Geometry update | Unresolved trial |
|---|---|---|---|
| `nodal_baseline` | `nodal_kress` | `spline` | hard stop (CI-001) |
| `nodal_fixed` | `nodal_kress` | `spectral` | one promotion to N1024/2048 (`ResolutionResponse`) |
| `modal_fixed` | `modal_muller` | `spectral` | hard stop; optional `modal_response` is a separate recipe |
| `modal_response` | `modal_muller` | `spectral` | optional promotion to trace cutoffs 128/160 |

A pipeline only fills `fit`'s physics, geometry-update and resolution slots; policy, start
and localization stay with the caller. Results gain `pipeline` and `resolution_promoted`.

The maintained named pipelines and TG-002 now use sampled spectral geometry
with batched preparation. Each moved curve and final candidate must pass direct
area, minimum-speed and sampled-intersection checks.

Removing certificates changes which trials are accepted: sampled checks are
decisive and do not establish continuous-curve simplicity. This refactor includes
no new inverse experiment and establishes no runtime improvement.

`certified_spectral` remains an explicit optional method with the previous
certificate decisions. Historical reference selections and results keep that
meaning; certificate-order settings affect only this optional method.

Calling bare `fit()` keeps `nodal_kress` with the spline projected update.
Supported geometry names are `spline`, `spectral`, `certified_spectral`,
`analytic_spectral`, `gaussian_lipschitz`, and `similarity`.

Analytic spectral and Gaussian updates remain experimental; the Gaussian map
failed ON-001 curved-state qualification. Device and physics selection remain
independent. See the
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
replacement for the `certified_spectral` method used in that experiment.
ON-001 itself changed no recipe default.

## CI-SPD feedback and exact reuse (DP-001)

`CumulativePolicy(damping_rule="agreement", avoid_terminal_linearization=True)`
selects gain/accepted-fraction damping feedback with a scaled curvature floor,
pre-geometry budget checks, a stage proposal cap and a shortened-progress stop.
The schedule default remains unchanged. `Execution(audit_frequency_batch=2)`
streams two frequencies concurrently within the configured frequency threads;
the default is one. The ordinary acceptance, validity and endpoint checks
remain active. Terminal tangent omission preserves callback and checkpoint
requirements. The approved [DP-001 comparison](../../docs/iterations/CI-SPD/DP-001_results.md)
retained 26/30 TG-002 recoveries, with no new recovery or regression. All 26
recovered outputs were faster: median paired speedup 1.134x and 8.4% less
summed output time including failures. The four failed cases still stop at
the numerical-resolution gate, and their summed time increased. This supports
the combined recipe under the tested contract, not case-8 recovery or an
isolated speed claim for each change. These switches remain opt-in.

Immutable base geometry and resolution-only assembly arrays are cached, and
wave expansions append missing cells. Receipts retain candidate exceptions,
actual geometry proposals, failed phase timings and exclusive audit phases.
CUDA assembly reports lock/prior-work wait, event device span, synchronized
host span and host transfer; these are nested measurements, not additional
runner wall time. Bounded tests establish numerical equivalence; inverse
recovery and runtime evidence comes from the paired campaign.

## RG-001 opt-in resolution gate

`CumulativePolicy(resolution_gate="decision")` retains the existing
production/refined gain acceptance decision when a candidate exceeds the
stage's absolute field tolerance. Receipts record the mode, per-frequency
overshoot ratios, accepted-overshoot count and largest accepted overshoot.
Failed or non-finite evaluations stop both modes; endpoint audit tolerances
remain unchanged. The default gate is `"absolute"`.

RG-001 retained all 26 TG-002 recoveries and their accepted paths bitwise,
with no new recovery. Aphex 4 improved from 1.685 to 0.664 mm RMS, but its
Hausdorff and field gates failed. Larger-budget diagnostics did not produce
qualified endpoints. Decision mode remains experimental; the study supports
a follow-up on modal resolution response. See the
[RG-001 results](../../docs/iterations/cleaned_interfaces/iteration_31/05_results.md).

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

`coefficient_geometry` is an isolated NG-001 engine for centred arclength
updates and complete directional tangents without curve quadrature.
`interval_geometry` uses the optional `mpmath` dependency for directed arc
range certificates and direct increment reuse. They are not registered fit
strategies; approximation residuals remain float64. See the
[component results](../../docs/iterations/node_free_geometry/NG-001_results.md)
for accuracy, unresolved cases and complete cost.
The [NG-002 follow-up](../../docs/iterations/node_free_geometry/NG-002_results.md)
adds opt-in `speed_method="newton"` within this isolated engine and directed
Laurent Horner proof evaluation. All 31 saved bases prove within five seconds;
178/279 finite moves construct accurately with the declared band escalation.
New-move admissibility and complete-trial improvement are not established.

`complex_radius` is an isolated research instrument for genuinely complex
disk radii, exact transmission jets and scalar holomorphic continuation.
[Track 12](../../docs/iterations/complex_geometry/README.md) qualified local
fold monodromy but found no real endpoint for three fixed measured-data
detours. It does not implement complex FourierCurve geometry or enter `fit`.

Modal radial coefficients are now constructed directly from analytic Bessel
products, including the regularized Hankel terms through their Neumann series.
CPU and CUDA assembly share this path; it performs no radial sampling or DCT.
Derivatives and the removable material-difference quotient are formed in
coefficient space. See the [derivation](../../docs/reference/modal_radial_coefficients.md)
and [AC-001 validation](../../docs/iterations/CI-SPD/AC-001_results.md).
The retained `radial_functions` evaluator serves as an independent test reference.
Geometry-side steps still sample the curve. These include the trial move and
arclength reset, validity fallback, domain box and frontier. The
[sampling scope](../../docs/reference/node_free_scope.md) lists them.

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

On this organized branch, the retained tests are under `pytest/`:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 -m pytest pytest/bem_inverse -q
```

Shared geometry and physical solver checks remain in `pytest/ordered_boundary`
and `pytest/gpr_bem_kress`. Earlier references above to removed campaign test
folders describe the historical source layout, not runnable commands here.

The [refactor status](../../docs/reference/inverse_refactor_status.md) records
before/after comparisons and the local platform's existing precision limits.
No full inverse benchmark is required for this readability refactor.
