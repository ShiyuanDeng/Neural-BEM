# Isolated shape and frequency continuation

The working research entry point is
[`experiments/shape_continuation`](../../experiments/shape_continuation/README.md).
It follows the boundary-inversion structure in Borges, Rachh and Greengard,
*On the robustness of inverse scattering for penetrable, homogeneous objects
with complicated boundary*, Inverse Problems 39 (2023) 035004,
[DOI](https://doi.org/10.1088/1361-6420/acb2ec).

```text
Cartesian Fourier curve, parameterized by arclength
    → ordered boundary nodes
    → dense nodal Müller/Kress, plane-wave illumination
    → complex scattered fields and normal-shape Jacobian
    → single-frequency GN/SD update + geometry/curvature checks
    → reparameterize and accept only a decreasing candidate
    → hand the curve to the next frequency/update band
```

The normal update band, curve storage band, and quadrature node count are
separate. There is no polar-angle restriction. Complex Fourier coefficients
are an equivalent storage notation for Cartesian Fourier geometry; they do
not select the native Fourier–Galerkin Müller solver.

The experiment controls have distinct jobs:

| Control | Meaning |
|---|---|
| `Stage.wavenumber` | Selects one measured complex data matrix and its acquisition. |
| `Stage.update_modes` | Chooses the `2M+1` real Fourier coefficients of the normal update. This is the primary shape-harmonic continuation control. |
| `Stage.curvature_modes` | Sets the curvature-energy band used for admissibility; its tail tolerance is explicit in `FitConfig`. |
| `Stage.curve_modes` | Resolves Cartesian curve storage and arclength refitting. Insufficient storage rejects a proposal rather than silently smoothing it. |
| `Stage.nodes` | Resolves nodal Müller/Kress quadrature, independently of the update band. |

`optimise_step` is the experiment unit: it attempts one accepted update and
retains the candidate's already-computed forward state and LU. `prepare_state`
reuses that solve when only M/C, tolerances, or zero-padded K change; changes to
geometry, frequency, acquisition, material or N rebuild it. `fit_prepared`
groups updates into a chunk; `fit_frequency` prepares a fresh one-frequency fit.

`run_adaptive` asks a plain callable strategy for `Decision(Stage, FitConfig,
reason)`, or `None` to finish. The strategy sees the current committed curve,
full decision history, available frequencies and cumulative work. It may repeat
or revisit frequencies and alter harmonics/resolution between updates by using
`max_iterations=1`. One work budget spans the whole run, including optional
N/2N qualification. Failed qualification rolls back the entire decision while
preserving its rejected trajectory for the next strategy call. Decision records
do not retain dense physics caches. The existing `run_continuation` API is now
an adapter over this controller, preserving the increasing-ladder baseline.

See the [controller contract and pseudocode](../../experiments/shape_continuation/README.md#adaptive-controller-contract)
for cache rules, stopping semantics, diagnostics and checkpoint hooks.

The synthetic harness saves stage checkpoints, can resume a saved run with an
explicit new budget, and qualifies both fields and normal Jacobians at N/2N.
Truth and held-out observations remain evaluation inputs. A small filtered
step means small physical movement; it does not assert stationarity or recovery.

The only project dependencies are `ordered_boundary`, `gpr_bem_kress`, and its
`periodic_kress` dependency. The former inverse drivers, SDF/MLP machinery,
topology controller, automatic runtime selection, and modal research packages
are absent from the import graph. Production defaults remain unchanged.

The package README owns the API, exact commands, paper-to-code differences,
and limitations. The [qualification record](../../results/validation/shape_continuation/README.md)
owns measurements. The pilot is a single-component, known-contrast,
lossless/equal-density, full-aperture problem in dimensionless coordinates.
It is ready for controlled continuation development; the paper's complete
high-frequency and complicated-boundary results have not been reproduced.
