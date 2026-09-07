# Explicit Radial Fourier: shape and material controls

Status reviewed on 2026-09-07. These implemented, opt-in experiments recover
one interior relative permittivity with either fixed geometry or joint K2
radial geometry. They belong to [Explicit Radial Fourier](explicit_radial_fourier.md)
and supply derivative, objective and starting-basin controls. Their accepted
state contains explicit shape/material parameters.
[Implicit MLP + Method B](implicit_mlp.md) is a separate implemented adjoint
pipeline whose current recovery remains unresolved; these material studies
do not establish its recovery or implement neural material inversion.

## State, derivative and solver

The joint state has six real physical parameters:

```text
[mean radius, center x, center y, radial cos(2t), radial sin(2t), interior epsr]
```

Fixed-shape arms update only the last parameter. The radial chart and bounds
guarantee positive radius throughout the declared box; there is one simple
star-shaped component. Exterior `epsr=6`, source calibration and acquisition
are fixed. The current experiments use lossless, nonmagnetic 2-D TMz physics.
They do not recover conductivity, permeability, object count or per-object
materials on several interfaces.

[The material evaluator](../../solvers/sdf_inverse/material_inverse.py)
rebuilds the direct radial curve and candidate material-dependent Kress
operators. Its cache keys include candidate shape/material state and the
fixed experiment. Observations, complex source strengths and residual
normalization remain immutable. The complex paired residual is stacked into
real and imaginary parts and optimized in declared scaled coordinates with
bounded trust-region least squares.

The Jacobian uses
[complete discrete Kress directional derivatives](../../solvers/gpr_bem_kress/shape_derivative.py),
including material-dependent operators, curve normals, quadrature factors,
right-hand side and receiver map. It is not parameter FD and does not query
an SDF, extract a contour, or perform Method-B fitting. The independent
[derivative validation](../../results/validation/kress_shape_derivative/refined-audits-20260906/summary.md)
supports this fixed-topology, coherent-curve contract. The geometry-to-neural
coupling is implemented and separately validated in Implicit MLP + Method B;
that validation does not extend these joint shape/material results to an
MLP-owned material inverse.

## Drivers and saved evidence

| Driver / run | Scene and recorded date | Measured takeaway |
|---|---|---|
| [Material comparison](../../run_material_inverse_comparison.py); [eight-arm result](../../results/inverse/radial_fourier/shape_material/material_inverse/bounded-20260906/README.md) | Mie circle at `(0.5,0.5)` m, radius `0.05` m, interior `epsr=3`; fixed/joint fits, clean and 1% complex noise; 2026-09-06 | Five of eight arms pass physical recovery. Three high-permittivity starts fail; local optimizer termination does not certify recovery |
| [Robustness comparison](../../run_material_robustness_comparison.py); [fifteen-workflow result](../../results/inverse/radial_fourier/shape_material/material_robustness/bounded-20260906/README.md) | Historical circle plus independent Nyström noncircle with interior `epsr=8.4`; clean/noisy joint cohorts and fixed-circle control; 2026-09-06 | Full-band local policy passes 0/5 cohorts, continuation 2/5, bounded multistart continuation 5/5 |

Both studies train at 0.5 and 1.5 GHz and qualify against shifted-angle
holdout acquisitions. The robustness study loads and hash-checks the exact
historical circle data, noise and starts rather than regenerating that
evidence. Its new noncircle is also within the K2 chart, on the opposite side
of the known background permittivity. Independent oracle refinement and
final candidate forward refinement are recorded separately.

The robustness layer in
[robust_material_inverse.py](../../solvers/sdf_inverse/robust_material_inverse.py)
adds full-band local fitting, cumulative low-to-high continuation and
deterministic multistart continuation. Starts are constructed from declared
bounds and background material. Low-frequency screening can retain branches,
but final selection uses the same original full-band training objective for
every eligible candidate. All selections are sealed before geometry and
holdout qualification. Failed branches and attempted work remain recorded.

The successful noisy joint recoveries have symmetric geometry error about
`64.89 µm` (circle) and `51.05 µm` (noncircle), with clean shifted-angle
holdout relative errors `0.003488` and `0.006427`. These are results for two
synthetic targets and one noise realization per target, not a statistical
robustness rate. The restart/continuation combination was tested together;
plain full-band multistart was not isolated. Actual work differs across
policies, so this is a bounded recovery comparison, not a matched-cost
speedup experiment.

## Interpretation across the two inverse pipelines

The useful transferable pieces are immutable data and normalization, explicit
parameter/material ownership, full candidate operator rebuilds, verified
discrete derivatives, counted trial work and training-only continuation or
restart selection. Geometry truth and held-out observations are qualification
data, not optimization inputs. Implicit MLP + Method B accepts its actual
re-extracted geometry and records adjoint/trial work. Its recovery gates
remain unsatisfied, and no matched comparison with these material controls
has been completed.

Keep four outcomes separate: search completion, optimizer status, independently
checked stationarity and physical recovery. In these studies even well-resolved
forward predictions and apparently successful optimizer stops can belong to
wrong solutions. Radius and material sensitivities can also be strongly
correlated (about `-0.96` in the successful circle control); a finite local
Jacobian condition number is not global identifiability.

The stored material benchmarks use physical gates of `0.2 mm` geometry error,
`2 µm` geometry-refinement agreement, `0.1` absolute material error and
`1e-5` forward refinement. Clean holdout field gates are `1e-4` for clean
training and `0.02` for noisy training; scaled projected-gradient stationarity
has a separate `1e-7` gate. These are the declared controls' tolerances, not
automatically the tolerances for an Implicit MLP + Method B experiment.

The robustness source received a nonfinite-objective guard after its timed
run. Saved hashes identify the measured revision; no current-source rerun
is implied by moving or indexing those artifacts. Preserve the frozen
material-input dependency when rerunning the robustness driver.
