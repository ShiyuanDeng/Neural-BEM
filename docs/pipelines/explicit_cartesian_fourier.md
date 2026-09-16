# Explicit Cartesian Fourier inverse

Accepted geometry is a Cartesian Fourier curve, or a collection of disjoint
Cartesian Fourier components. No MLP is constructed, trained, evaluated or
audited. PyTorch remains a software dependency of the shared single-component
optimizer; its network argument is a parameterless placeholder.

## Entry points

| Driver | Purpose | Default results directory |
|---|---|---|
| `run_explicit_cartesian_fourier_inverse.py` | One component; circle/star targets with circle/ellipse/star initialization | `results/inverse/cartesian_fourier/` |
| `run_fourier_topology_controller.py --chart cartesian` | Automatic birth, death, split and merge, without a target count or prescribed event policy | `results/inverse/cartesian_fourier/topology_controller/` |
| `run_radial_fourier_topology_challenges.py --chart cartesian` | Three declared replacement challenges, with training, holdout, geometry and cross-resolution gates | `results/inverse/cartesian_fourier/topology_challenges/` |

The shared topology drivers default to **radial**; selecting Cartesian requires
`--chart cartesian`. Their Python controller also converts supplied radial
initial geometry when `TopologyControllerConfig(chart='cartesian')` is used.

## Two optimizer paths

The single-component study uses `run_alternating_neural_inverse` with
`direct_curve_retraction='cartesian_fourier'` and `distillation_policy='curve_only'`.
It extracts the chosen **analytic** initial level set once, then optimizes the
explicit coefficients. Each accepted increment is re-gauged to polar angle by
default, with Fourier truncation recorded in the trajectory. `--no-regauge`
disables that operation for parameterization experiments. Its finite-difference
Jacobian still uses the full coefficient space with a phase gauge removed.

The topology path uses `run_multiradial_fd_inverse(cartesian_gauge=True)`.
Since SPD-002, this API defaults to **analytic Jacobians and faster CPU kernels**,
including candidate refinement and the current four-stage continuation. Existing
Cartesian topology commands use the faster mode without extra flags. Restore
FD/reference CPU with `--inverse-runtime reference` on the controller, benchmark,
challenge or TOP-025 runner, or set `SDF_INVERSE_RUNTIME=reference` for any caller.
The mode is inherited by worker processes and saved in new run manifests.
CUDA remains optional. This default change was directly requested by the user;
the [SPD-002 plan](../iterations/speedup/iteration_02/03_plan.md) records its validation.

It enforces a converged polar-angle gauge, and computes steps and Jacobians in
the subspace that preserves it. Gauge convergence checks both truncation and
the change in parameterized geometry; zero truncation alone is insufficient.
Topology contour fits must also preserve the source contour within the feature
tolerance after gauge fixing.

These are distinct algorithms. The topology optimizer's smaller Jacobian and
cost measurements do not describe the single-component study.

## Representation limits

Under the topology gauge, Cartesian bandwidth K represents the same shape
family as radial bandwidth K−1, with the radial first harmonic removed by its
translation convention. Circles retain three free parameters. Topology events
can change the number of components, but every individual component must still
be representable in this star-shaped family. A non-star-shaped contour is
rejected by the Cartesian topology policy. The radial controller separately
allows ungauged Cartesian fallback contours; that is a different policy.

### Open concern: the restriction this chart was adopted to escape

Recorded 2026-09-15 by the project owner; unresolved, and no fix is proposed
or scheduled here. The Cartesian chart was taken up in part to get away from
the radial chart's star-shaped restriction. Under the polar-angle gauge it
does not deliver that. The gauge-fixed set is exactly the curves that are
star-shaped about their own Fourier mean, so the two charts carry the same
shape family; the `contour_modes + 1` compensation in
`sdf_inverse/topology_controller.py` exists precisely to keep the two matched,
and a mask that is not star-shaped about either candidate centre is refused
outright by `fit_mask_component`. What the Cartesian chart is measured to buy
over radial is conditioning and step behaviour on that shared family, not a
larger one. This note exists so the objection is not lost behind the
favourable conditioning results.

The demonstrated topology cases have disjoint, same-material components.
Nested holes, touching interfaces and multi-material topology are not covered.

## Run and verify

Use a fresh output directory for each run. In this workspace the tested Python
environment is `/home/drdeng/miniconda3/envs/EMNerf/bin/python`.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_fourier_topology_controller.py --chart cartesian --profile full \
  --output results/inverse/cartesian_fourier/topology_controller/fresh-run
```

Use `--case` to select one topology case, `--skip-video` for numerical checks,
and `--profile quick` for wiring checks only. Controller `--render-only` reads
saved trajectories and manifest settings without rerunning the inverse.

The [results index](../../results/inverse/cartesian_fourier/README.md) links the
single-component study and both topology suites. The [pipeline audit](../../results/validation/cartesian_fourier/pipeline-audit-20260910/README.md)
records subsequent fixes and fresh verification. Historical measured bundles
retain their original results.

## TOP-001 allocation experiment

The shared controller accepts `--candidates-refined-per-group` and
`--candidate-refinement-iterations`, defaulting to B0's one candidate and three
LM iterations. Controller bundles now include per-stage work counts and source
provenance. `run_topology_allocation_experiment.py` replays saved pre-event states
under declared A/B/C budgets, with held-out observations used only for final
qualification. See the [topology handoff](../iterations/topology/README.md).

Use `--include-simplest-candidate` to enable TOP-005's qualified selective
policy. It preserves the normal shortlist and adds the minimum-dimension
family champion only when the raw leader is more complex. The default stays
unchanged. [Quality/cost tradeoffs, videos and commands](../../results/validation/topology/TOP-005-20260911/README.md).

Use `--refined-feasibility-guard` to require every optimizer step to be
admissible at the refined discretization as well as the production one. The
check is geometric and costs no forward solve; with it off, the optimizer can
stop on the production feasibility boundary and the next refined evaluation
then raises. The default stays unchanged.

The [twelve-scene topology benchmark](../benchmarks/topology_scenes.md) is the
required broader performance comparison, including distant starts and
ellipse/star targets. Its runner wraps the existing automatic controller
without supplying target count, event policy, shape family or mode schedule.
