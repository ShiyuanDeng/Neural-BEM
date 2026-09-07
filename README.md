# Neural SDF BEM AD

Research code for homogeneous full-space 2-D TMz dielectric transmission,
neural implicit geometry, boundary-element forward modeling, and inversion.

**Current research direction: repair strict MLP + Method B for single-object
inversion.** The MLP should own recovered geometry and Method B should faithfully
supply its boundary to the physical solver. Radial Fourier and other
experiments are diagnostic evidence for this work, not a replacement objective.

## Start here

- [Current architecture](docs/current_architecture.md): actual capabilities,
  defaults, and the distinction between implemented paths and planned repair.
- [Strict MLP + Method B](docs/pipelines/strict_mlp_method_b.md): failure
  evidence, repair priorities, and acceptance requirements.
- [Radial Fourier / MLP policies](docs/pipelines/radial_fourier.md) and
  [shape/material experiments](docs/pipelines/shape_material.md): what those
  branches establish and how their findings inform the strict pipeline.
- [Results catalogue](results/README.md): pipeline, scene, date, outcome, and takeaway.
- [Reproduction commands](docs/reproduction.md): controls and checks for the
  user; no tests or experiments were run during this cleanup.
- [Documentation map](docs/README.md): current guidance, reports, references, and legacy records.

## Implementation at a glance

| Entry point | What it currently runs |
|---|---|
| `run_sdf_inverse_comparison.py` | Implicit-parameter finite differences with Method-B extraction at each evaluation; MOD/Kress controls |
| `run_mlp_sdf_inverse_comparison.py` | Authoritative radial Fourier geometry with strict per-step MLP fitting/audits |
| `run_sdf_representation_ablation.py` | Radial reconstruction under strict, curve-only, and final-export policies |
| `run_material_inverse_comparison.py` | Fixed or radial-K2 shape plus one interior permittivity, using analytic Kress derivatives |
| `run_material_robustness_comparison.py` | Bounded continuation/restart comparison for that shape/material problem |
| `run_neural_metric_comparison.py` | Frozen neural-feature metrics on radial geometry; no training during inversion |

The MLP CLI's `legacy_strict` policy does **not** make the MLP own accepted
geometry or restore the old Method-B feedback loop. There is no current command
that alone constitutes the planned strict-pipeline repair. Small implicit-model
Method-B recovery and successful radial recovery are distinct from strict
neural recovery.

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
| `results/inverse/` | Method-B controls, radial diagnostics, material and metric experiments |
| `results/representation/` | Neural fitting and distance-supervision evidence |
| `results/validation/` | Geometry, forward, conversion, and derivative studies |
| `results/demos/` | Demonstrations, separate from inverse recovery claims |
| `results/legacy/` | Superseded inverse/development runs and archived solver experiments |
| `docs/pipelines/` | Pipeline explanations and the strict-pipeline repair plan |
| `docs/reports/`, `docs/reference/`, `docs/legacy/` | Dated evidence, technical detail, and superseded plans |

Measurements retain their original run IDs and machine-readable payloads.
[Relocations](results/relocations.json) record old and new paths;
`results/sdf_boundary_parameterization` is a compatibility link for recorded
geometry paths and the existing notebook. Original source snapshots and
commands describe the historical run, even when current code has moved on.
