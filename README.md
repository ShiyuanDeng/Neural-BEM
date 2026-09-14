# Neural SDF BEM AD

Research code for homogeneous full-space 2-D TMz dielectric transmission,
neural implicit geometry, boundary-element forward modeling, and inversion.

**The three current inverse pipelines are Implicit MLP + Method B, Explicit
Cartesian Fourier, and Explicit Radial Fourier.** The implicit pipeline updates neural weights with the Kress
adjoint; Method B supplies the MLP's boundary to the physical solver. Its
gradient is validated, but recovery remains **FAIL / unresolved**: the new
12-pair circle, ellipse-to-circle and star runs all fail overall acceptance.
Radial Fourier recovers its canonical curve on recorded cases; MLP fitting and
representation gates are separate. Cartesian Fourier runs without neural
fitting or audits and includes corresponding topology suites. A matched
three-way recovery benchmark has not been completed. Neural evidence is recorded in the
[implementation report](docs/reports/implicit_mlp_adjoint_2026-09-07.md).

## Start here

- [Project dashboard](docs/README.md): current baseline, the two current
  research objectives, active tracks and what each is waiting for. **Start
  here if you are picking up work.**
- [Baseline B0](docs/baselines/B0_2026-09-10.md): the executable comparison
  reference — commit `345038a`, the audited source for the current tracks —
  and its provenance limitations.
- [Current architecture](docs/current_architecture.md): actual capabilities,
  defaults, and the distinction between implicit and explicit geometry.
- [Implicit MLP + Method B](docs/pipelines/implicit_mlp.md): adjoint
  updates, historical evidence, and acceptance requirements.
- [Explicit Radial Fourier](docs/pipelines/explicit_radial_fourier.md): curve
  recovery, MLP representation policies, and frozen neural metrics.
- [Explicit Cartesian Fourier](docs/pipelines/explicit_cartesian_fourier.md):
  MLP-free curve inversion and automatic topology, with their representation limits.
- [Explicit Radial Fourier shape/material experiments](docs/pipelines/explicit_radial_shape_material.md):
  the radial variant with one unknown interior permittivity.
- [Results catalogue](results/README.md): pipeline, scene, date, outcome, and takeaway.
- [Reproduction commands](docs/reproduction.md): adjoint inverse, controls,
  gradient checks and fresh output paths.
- [Documentation map](docs/README.md): current guidance, reports, references, and legacy records.

**Track A update (2026-09-11):** TOP-001 and TOP-005 are complete. The new
opt-in `--include-simplest-candidate` policy reduces worst Cartesian split
error from 175 µm to 31 nm across ten replays, using 42% fewer BIE solves.
All five full-controller quality checks pass; total work falls 7%, with
extra cost on four unchanged cases. [Report, videos and reproduction commands](results/validation/topology/TOP-005-20260911/README.md).

**Broader performance benchmark:** [Topology scenes v1](docs/benchmarks/topology_scenes.md)
adds distant/enclosing starts, ellipses, stars and three different targets.
Current and future topology performance comparisons must report all twelve
scenes, including failures; circular split improvements alone do not establish
general recovery. TOP-006 tested both current policies: **5/12 scenes pass for
each; the distant ellipse/star case fails**. [Results and visual comparisons](results/validation/topology/TOP-006-20260911-scenes-v1/README.md).

**Track A update (2026-09-11, TOP-007):** four of those failures were uncaught
geometry exceptions, not bad reconstructions — the optimizer could stop on the
production resolution's feasibility boundary, which the refined evaluation then
refused. The opt-in `--refined-feasibility-guard` requires every optimizer step
to be admissible at both resolutions, using geometry checks and no extra
solves. Guarded runs abort nothing and return 9/12 against the default's 7/12,
with identical final states wherever both arms complete; **both arms still pass
5/12**, so the remaining failure is shape, not feasibility.
[Report and comparisons](results/validation/topology/TOP-007-20260911-refined-feasibility/README.md) ·
[videos of every scene](results/validation/topology/TOP-007-20260911-refined-feasibility/videos.md).

**Track A update (2026-09-12, TOP-008 and TOP-009):** the two candidates an
evidence-based literature review accepted are now both measured. TOP-008: a
probe the 8-mm radius floor refused was being recorded as a derivative of zero,
freezing its Jacobian column, and a gradient assembled from those zeros could
still report convergence. The opt-in `--feasible-fd-jacobian` measures the
feasible side instead; it frees the pinned component from 8.000 mm to 22.737 mm,
returns 10/12 runs against 9/12 and takes `split` to 0.000023 mm at a quarter of
the solves — but **buys no new benchmark pass**, still 5/12.
[Report](results/validation/topology/TOP-008-20260912-feasible-fd/README.md).

TOP-009 then added the missing shape bandwidth. Adding modes fits the training
data **248x better** while final boundary error, IoU and holdout error get
**worse**, which stopped the line before the benchmark. A stage-3
diagnostic corrected the reading: the **true geometry fits the same training
acquisition to 3.23e-07 relative error**, so the reconstruction is 7.1e6x worse
than this known attainable value. One component acquired star-like shape with
similar perimeter, area and isoperimetric ratio. A truth-selected rotation of
**34 degrees** reduces its boundary error, exposing a substantial phase mismatch.
A fourth stage ran the mode ladder to
exhaustion at K=9, enough for both a five- and a seven-lobed star: the answer
improves to 11.849 mm from 17.599, still ends worse than the circles it started
from, and remains **74,159x above the objective the true geometry attains**.
**Independent review:** this demonstrates a suboptimal reconstruction, not a
certified local minimum or unique inversion. Thirteen of fourteen refinements
stopped on small loss change; the final data error already satisfies the
controller's tolerance despite poor geometry. The next proposed check separates
optimizer stopping from stationarity before choosing a restart strategy.
[Review and counter repair](docs/iterations/topology/iteration_07/02_proposals/01_independent_review.md).
[Report](results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md).

**Track A update (2026-09-12, TOP-010):** the independent review's diagnostic
refutes the local-minimum reading. At the saved state the terminal gradient is
**4013x the optimizer's own tolerance**, stable across three finite-difference
scales, with a full-rank Jacobian — and three restarts of the **unmodified**
optimizer recover **1.7x** in the objective in 45 seconds with no source change.
Three absolute constants, one of them serving as both the loss target and the
accepted loss change, sit at the same order as the entire remaining objective.
Yet matched boundary error moved 11.849 to 11.991 mm and IoU stayed at 0.7088.
Four defects are now found and fixed — derivative, capacity, ladder truncation,
premature stopping — **each worth objective and none worth geometry**, and the
benchmark still passes 5/12. The open question is why the gated geometry is
insensitive to four orders of magnitude of training objective.
[Report](results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/README.md).

## Implementation at a glance

| Entry point | What it currently runs |
|---|---|
| `run_implicit_mlp_inverse.py` | Implicit MLP + Method B: direct neural-weight Kress-adjoint updates with actual-MLP acceptance |
| `run_explicit_radial_fourier_inverse.py` | Explicit Radial Fourier: curve-owned inverse with MLP fitting/audits; old `run_mlp_sdf_inverse_comparison.py` alias retained |
| `run_explicit_cartesian_fourier_inverse.py` | MLP-free single-component Cartesian Fourier inverse |
| `run_fourier_topology_controller.py --chart cartesian` | Automatic Cartesian Fourier birth, death, split and merge; optional selective candidate refinement |
| `run_selective_topology_experiment.py` | TOP-005: baseline replay checks, twenty paired split replays and five full-controller qualifications |
| `run_topology_scene_benchmark.py` | Frozen twelve-scene benchmark over named controller arms, geometry/holdout checks, overlays and difficult-case videos |
| `run_radial_fourier_topology_challenges.py --chart cartesian` | Cartesian versions of the three topology replacement challenges |
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

The single-component radial driver is star-shaped. The separate automatic
topology controller chooses birth, death, split and merge from data without a
supplied object count; its evidence is bounded to the recorded synthetic cases.
Layered ground and 3-D inversion are outside the current implementation.

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
| `docs/pipelines/` | The three current pipelines, radial variants, and their validation limits |
| `docs/reports/`, `docs/reference/`, `docs/legacy/` | Dated evidence, technical detail, and superseded plans |

Measurements retain their original run IDs and machine-readable payloads.
[Relocations](results/relocations.json) record old and new paths;
`results/sdf_boundary_parameterization` is a compatibility link for recorded
geometry paths and the existing notebook. Original source snapshots and
commands describe the historical run, even when current code has moved on.
