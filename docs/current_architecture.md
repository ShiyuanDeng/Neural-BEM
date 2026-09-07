# Current architecture and research direction

Updated 2026-09-07. The two current inverse pipelines are **Implicit MLP +
Method B** and **Explicit Radial Fourier**. They differ in which representation
owns the accepted geometry and receives the physics update.

## Current inverse pipelines

| Pipeline | Geometry authority and update | Forward / derivative | Measured status |
|---|---|---|---|
| [Implicit MLP + Method B](pipelines/implicit_mlp.md) | Neural weights; the candidate network's extracted Method-B boundary determines acceptance | Kress discrete adjoint through branch-local extraction/conversion reverse; Adam/backtracking | Gradient validated; all three current 12-pair recovery runs fail overall acceptance |
| [Explicit Radial Fourier](pipelines/explicit_radial_fourier.md) | Radial Fourier coefficients; an MLP fits/audits the accepted curve | MOD or Kress; radial finite differences in the main driver | Canonical curve recovery succeeds on recorded cases; the extracted MLP can still fail representation gates |

`run_implicit_mlp_inverse.py` selects Implicit MLP + Method B. Its September 7
circle, ellipse-to-circle and star experiments remain **FAIL / unresolved**.
Correct gradients and accepted data decrease do not establish physical recovery.
Method B remains the neural pipeline's conversion method and an active
development target.

`run_explicit_radial_fourier_inverse.py` selects Explicit Radial Fourier;
`run_mlp_sdf_inverse_comparison.py` remains its compatibility name. The CLI uses
radial retraction and the `legacy_strict` per-step neural fitting policy.
Changing that policy does not change who owns the geometry. The library's
normal-update default and the CLI's radial override remain distinct.

No matched recovery benchmark between these two pipelines has been completed.
The [September 7 report](reports/implicit_mlp_adjoint_2026-09-07.md) and
[results catalogue](../results/README.md) retain the measured outcomes and limits.

## Explicit Radial Fourier variants

These experiments keep explicit radial geometry; they are not additional
MLP-owned pipelines.

| Variant | Driver and role |
|---|---|
| MLP representation policies | `run_sdf_representation_ablation.py` compares `legacy_strict`, `curve_only`, and `export_only`; reconstruction and representation are assessed separately |
| [Shape/material](pipelines/explicit_radial_shape_material.md) | `run_material_inverse_comparison.py` and `run_material_robustness_comparison.py` use a fixed curve or radial K2 state plus one interior permittivity, with analytic Kress derivatives |
| Frozen neural metric | `run_neural_metric_comparison.py` uses an initial neural-feature metric on radial geometry; no neural weights are trained during inversion |

## Legacy known-shape-family controls and numerical references

The [Legacy known-shape-family controls](legacy/known_shape_family_controls.md)
optimize three circle, four ellipse, five star, or seven frozen-random-feature
parameters through extraction and Method B. The star family fixes five lobes;
its center, radius, amplitude and rotation are recovered from measurements.
These runs establish recovery within prescribed families, not full-MLP recovery.
Their observations and measured trajectories remain in the
[result archive](../results/legacy/known_shape_family_parameter_inverse).

`run_sdf_inverse_comparison.py` retains these controls and the distinct neural
`--optimizer parameter_fd` reference. For `siren_*` models that option updates
all network weights using a numerical Jacobian and damped Gauss–Newton. Kress
neural cases default to the adjoint; MOD cases in this comparison retain
parameter finite differences. The FD and adjoint optimizers also differ in
update policy and regularization, so switching the flag alone does not isolate
the derivative method. No matched FD-versus-adjoint neural recovery benchmark
has been completed.

Finite differences used to check an adjoint derivative are validation probes,
not complete FD inverse runs. Separately, the older MOD neural B-scan inverse
uses a compressed boundary cloud and its own adjoint shape surrogate; it does
not use Method B.

## Physics, geometry, and solvers

The physical model is homogeneous full-space 2-D TMz dielectric transmission
with free-space Hankel kernels. Current ordered inverse evidence uses one
regular closed component. Radial geometry additionally requires a star-shaped
object. There is no implemented air/ground interface, 3-D inverse, object-count
recovery, or per-component unknown-material inverse.

Separate multi-component extraction/forward demonstrations include a
prescribed split; they do not optimize object count from data.

`ordered_boundary` owns smooth continuous producers and immutable even-node
curve data. Method B fits Cartesian coordinate Fourier series to an extracted,
projected contour and redistributes arc length. Radial Fourier represents
radius as a function of angle; these are different geometry paths.

| Package | Role |
|---|---|
| `gpr_bem_ref` | Frozen original; selector default |
| `gpr_bem_mod` | Compressed-cloud implementation, older neural adjoint, and ordered inverse comparison peer |
| `gpr_bem_kress` | Ordered Müller/Kress forward, multi-component forward extension, and opt-in single-interface discrete derivatives |
| `nystrom_ref` / cylinder Mie series | Independent observation and refinement controls |
| `sdf_to_ordered_boundary` | Extraction/projection, Methods A/B/C, and opt-in conversion studies |
| `sdf_inverse` | Implicit-parameter, curve, representation, metric, and material experiments |

Kress is directly imported, not a `solver_select` alias. For selector-backed
commands, `--solver` overrides `SOLVER`; if both are absent, REF is selected.
Use `--solver=mod` explicitly for MOD. The verified Kress
derivative handles coherent fixed-grid curve/material directions. The new
geometry reverse and branch-local Method-B reverse connect it to neural
weights. Discrete connectivity and branch switches are not differentiated.

## Evidence and reproduction

[Results](../results/README.md) classify runs by geometry ownership, solver,
MLP role, scene, recorded date, and outcome.
Reconstruction, SDF delivery, physical recovery, optimizer stopping, and
forward validation remain separate claims. Failed arms stay with their comparison.

[Reproduction commands](reproduction.md) cover the implemented adjoint inverse
and its separate controls. The [September 7 adjoint report](reports/implicit_mlp_adjoint_2026-09-07.md)
records gradient validation and failed circle, ellipse-to-circle and star
experiments. Active result locations are `results/inverse/implicit_mlp/` and
`results/inverse/radial_fourier/`; shape/material and frozen-neural-metric studies
are subgroups of the latter. Old family controls are preserved in
[their archive](../results/legacy/known_shape_family_parameter_inverse).
Earlier implementation details and recommendations remain in
[dated reports](reports/README.md); mathematics and numerical protocols remain
in [technical references](reference/README.md). Dated plans describe their
original checkpoints; use this page and the current pipeline pages for present
capabilities and defaults.
