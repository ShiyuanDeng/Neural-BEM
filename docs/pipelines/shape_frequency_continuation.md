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

`fit_frequency` is the experiment unit: it receives a current curve, one
immutable observation, and a stage, then returns the curve, stop reason,
accepted states, residual/gradient/rank history, and every rejected trial.
`run_continuation` supplies a fixed increasing frequency ladder and allows a
policy to choose stage resolutions. An adaptive controller that repeats a
frequency can call `fit_frequency` directly. This keeps policy experiments
outside the physical solver and one-frequency optimizer.

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
