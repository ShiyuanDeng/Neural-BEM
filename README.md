# Neural SDF BEM AD

Research code for homogeneous full-space 2-D TMz dielectric transmission,
neural implicit geometry, boundary-element forward modeling, and inversion.

**The two current inverse pipelines are Implicit MLP + Method B and Explicit
Radial Fourier.** The implicit pipeline updates neural weights with the Kress
adjoint; Method B supplies the MLP's boundary to the physical solver. Its
gradient is validated, but recovery remains **FAIL / unresolved**: the new
12-pair circle, ellipse-to-circle and star runs all fail overall acceptance.
Radial Fourier recovers its canonical curve on recorded cases; MLP fitting and
representation gates are separate. No matched comparison between these two
pipelines has been completed. The evidence is recorded in the
[implementation report](docs/reports/implicit_mlp_adjoint_2026-09-07.md).

## Start here

- [Current architecture](docs/current_architecture.md): actual capabilities,
  defaults, and the distinction between implicit and explicit geometry.
- [Implicit MLP + Method B](docs/pipelines/implicit_mlp.md): adjoint
  updates, historical evidence, and acceptance requirements.
- [Explicit Radial Fourier](docs/pipelines/explicit_radial_fourier.md): curve
  recovery, MLP representation policies, and frozen neural metrics.
- [Explicit Radial Fourier shape/material experiments](docs/pipelines/explicit_radial_shape_material.md):
  the radial variant with one unknown interior permittivity.
- [Results catalogue](results/README.md): pipeline, scene, date, outcome, and takeaway.
- [Reproduction commands](docs/reproduction.md): adjoint inverse, controls,
  gradient checks and fresh output paths.
- [Documentation map](docs/README.md): current guidance, reports, references, and legacy records.

## Implementation at a glance

| Entry point | What it currently runs |
|---|---|
| `run_implicit_mlp_inverse.py` | Implicit MLP + Method B: direct neural-weight Kress-adjoint updates with actual-MLP acceptance |
| `run_explicit_radial_fourier_inverse.py` | Explicit Radial Fourier: curve-owned inverse with MLP fitting/audits; old `run_mlp_sdf_inverse_comparison.py` alias retained |
| `run_sdf_inverse_comparison.py` | Shared comparison driver: Kress neural cases use adjoint by default; archived known-shape-family controls and explicit parameter-FD references remain runnable |
| `run_sdf_representation_ablation.py` | Explicit Radial Fourier under `legacy_strict`, `curve_only`, and `export_only` representation policies |
| `run_material_inverse_comparison.py` | Fixed or radial-K2 shape plus one interior permittivity, using analytic Kress derivatives |
| `run_material_robustness_comparison.py` | Bounded continuation/restart comparison for that shape/material problem |
| `run_neural_metric_comparison.py` | Frozen neural-feature metrics on radial geometry; no training during inversion |

The explicit radial CLI's `legacy_strict` policy describes per-step neural
fitting. The implicit MLP CLI instead updates network weights from the Kress
adjoint, with a fresh Method-B extraction and BEM solve controlling acceptance.
Gradient correctness and accepted data decrease are distinct from converged
physical reconstruction; retain the independent-reference accuracy gates.

The archived Method-B parameter inverses solved known shape families with
3 circle, 4 ellipse, 5 star or 7 random-feature controls. The star's five lobes
were fixed in advance; its center, radius, amplitude and rotation were recovered
from data. These are small-parameter family recoveries, not full-MLP inverses.
Their [archive](results/legacy/known_shape_family_parameter_inverse) preserves
the original observations and parameter-recovery evidence.

These [Legacy known-shape-family controls](docs/legacy/known_shape_family_controls.md)
are distinct from the neural
`--optimizer parameter_fd` reference, which updates every MLP weight through
numerical derivatives. Finite differences also validate adjoint derivatives;
those checks do not compare full reconstruction performance.

`gpr_bem_kress` supplies ordered Müller/Kress solves and opt-in single-interface
discrete geometry/material derivatives. `gpr_bem_mod` retains compressed-cloud
forward and neural B-scan adjoint implementations. Selector-backed commands
use `--solver`, then `SOLVER`, then frozen `gpr_bem_ref`; use `--solver=mod`
explicitly for MOD. Ordered inverse
drivers import their peers directly.

The radial inverse is single-component and star-shaped. Separate multi-component
extraction/forward demonstrations include a prescribed split, but there is no
data-driven object-count inverse. Layered ground and 3-D inversion are outside
the current implementation.

## Repository layout

| Location | Contents |
|---|---|
| `solvers/` | Project-owned geometry, forward solvers, inverse algorithms, and references |
| `pytest/` | Regression sources and validation drivers |
| `results/inverse/implicit_mlp/` | MLP-owned adjoint recovery runs, including failed cases |
| `results/inverse/radial_fourier/` | Curve-owned recovery, representation policies, shape/material and frozen-metric experiments |
| `results/representation/` | Neural fitting and distance-supervision evidence |
| `results/validation/` | Geometry, forward, conversion, and derivative studies |
| `results/demos/` | Demonstrations, separate from inverse recovery claims |
| `results/legacy/` | Known-shape-family parameter inverses, superseded inverse/development runs and archived solver experiments |
| `docs/pipelines/` | The two current pipelines, radial variants, and their validation limits |
| `docs/reports/`, `docs/reference/`, `docs/legacy/` | Dated evidence, technical detail, and superseded plans |

Measurements retain their original run IDs and machine-readable payloads.
[Relocations](results/relocations.json) record old and new paths;
`results/sdf_boundary_parameterization` is a compatibility link for recorded
geometry paths and the existing notebook. Original source snapshots and
commands describe the historical run, even when current code has moved on.
