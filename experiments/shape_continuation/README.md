# Shape and frequency continuation on nodal Müller/Kress

Implementation started 2026-09-22 under the user's explicit instruction to
replicate the algorithm in Borges, Rachh and Greengard, or build the inverse
until its continuation scheme can be implemented. Continued on the user-authorized
`feature/shape-frequency-continuation` branch, with committed/pushed checkpoints.
Owner: Codex. Independent reviewer: unassigned.

[Research iterations and current handoff](../../docs/iterations/shape_frequency_continuation/README.md)
record the experimental questions and decisions; this page owns the working API.

`action_atlas.predict(J, r, G, radius)` is SC-041's opt-in decision diagnostic.
Pass the residual Jacobian of the **complete trial construction** and its
physical normal-displacement mass metric. It returns one constrained
least-squares step and its predicted loss decrease. It does not assume a
noise model, prove a finite validity radius, or replace the LM fitter.
`descent_lower_bound` exposes the conditional Taylor-remainder bound; the
caller must justify any prospective remainder estimate. The older video
heatmap remains a descriptive, componentwise-capped QR score and is labelled
accordingly. See the [SC-041 contract](../../docs/iterations/shape_frequency_continuation/iteration_22/03_plan.md).

The current SPD comparison reference is **SPD-L**: SPD-008 compiled runtime,
real-Bessel CPU kernels and certified exact geometry reuse, with the K=4/6/8/10
state ladder and no legacy step controls (adopted after SC-034). The historical
SC-020/021 driver and results retain their original settings; they are not
timings of this reference. The [SC-030 contract](../../docs/iterations/shape_frequency_continuation/iteration_12/03_plan.md)
defines the six-case comparison and its cache-off hybrid control. The
[completed SC-030 comparison](../../docs/iterations/shape_frequency_continuation/iteration_13/01_results.md)
qualifies exact reuse for new clean-hybrid runs: 12.62% aggregate inversion-time
reduction, identical cached/off trajectories and 76 pre-dispatch tests. Keep
the fixed M=3/5/7/9 ladder as the baseline; no adaptive policy is promoted.

The clean hybrid supports the same opt-in, bounded, fit-local validation cache:

```python
from ordered_boundary.validation_cache import geometry_validation

snapshots = []
with geometry_validation("cache", on_fit=snapshots.append):
    result = run_policy(initial, policy, contrast, update, config, ledger)
```

Each `fit_stage` creates a fresh cache, released even after an exception.
Complete ordered point arrays and tolerances key both the hybrid's spatial
intersection test and the shared forward adapters' intersection tests.
Numerical predicates, derivative calculations, trial geometry and acceptance
rules are unchanged. No selection context means the original uncached path.
Pair-separation certification has no work to save on these single interfaces.
The callback's generic `num_nodes` field is unset for the hybrid API; read the
production/refined resolutions from its `FitStage` records.

`spd008_comparison.py` runs the approved fixed-topology comparison using the
existing two stage fitters. Use `prepare`, then `qualify`, then `campaign`, each
with the same `--output <fresh-output-directory>`; preserve the existing
[SC-030 evidence](../../results/validation/shape_continuation/SC-030-spd008-comparison/README.md).
Run under the EMNerf Python environment with `PYTHONPATH=solvers:.` and
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`. It freezes sources
and inputs, checks them before/after each worker, and keeps scoring outside
the inversion timer and training-only fit interfaces.

Reference: [On the robustness of inverse scattering for penetrable,
homogeneous objects with complicated boundary, Inverse Problems 39 (2023)
035004](https://doi.org/10.1088/1361-6420/acb2ec),
[author manuscript, §2.1 and §4](https://arxiv.org/html/2210.11607v1).
The same manuscript is stored in the documentation as a
[local PDF](../../docs/reference/papers/borges_rachh_greengard_2210.11607v1.pdf),
alongside the authors'
[reference implementation](../../docs/reference/papers/README.md#reference-implementation),
which settles several settings the prose leaves loose.

## Scope and file/API map

This is a new, isolated single-interface inverse, justified by the user's
request to remove legacy inverse dependencies. The core's only project dependencies
are `ordered_boundary` and public `gpr_bem_kress` forward APIs. No existing
numerical code or defaults are changed. No MLP, SDF, topology controller,
runtime selector, modal compression, or experimental Laurent solver is used by
the core. The separate legacy comparison harness imports the previous fixture
builders and inverse to establish a matched baseline.

- `geometry.py`: Cartesian Fourier curve storage, arclength reparameterization,
  scalar Fourier normal updates, Gaussian filtering, curvature-energy gate.
- `validation.py`: conservative spatial pruning of polygon intersection checks,
  qualified against the all-pairs reference at identical samples/tolerances.
- `forward.py`: plane-wave acquisition and optional line-source acquisition
  with paired or full receiver sampling, dense nodal Müller/Kress solves,
  reciprocal shape Jacobian.
- `inverse.py`: cached optimizer state, one GN/SD update, fixed-stage chunks,
  explicit feasibility/stopping, and compatibility entry points.
- `continuation.py`: decisions from full history, shared budgets, optional
  qualification/rollback, and an N/2N field plus Jacobian gate.
- `schedule.py`: explicit independent update/curve/quadrature resolutions,
  including the paper's fixed frequency grid and §4 update-mode rule.
- `run.py`: bounded synthetic recovery demonstration and saved provenance.
- `metrics.py`: evaluation-only boundary distances and polygon area differences.
- `paper.py`: audited Figure 1 profiles, zero-solve plan, capped smoke and explicit-budget runs.
- `benchmark.py`: inverse-only replay timing from saved observations.
- `legacy_cases.py`: matched regression against the previous explicit Cartesian
  Fourier inverse on its circle/star targets and circle/ellipse/star starts.
  Only this comparison harness imports the previous inverse drivers.
- `updates.py`: replaceable geometry updates. `BorgesUpdate` owns the
  normal-distance coordinates in metres, the velocities the Jacobian uses, the
  physical step metric, and the sample–move–arclength-refit trial with stable
  refusal reasons. It never sees data.
- `lm_backend.py`: the clean hybrid backend. `FitStage` is one policy decision
  (frequency set, weights, M, K, N, refined N, iterations, quota).
  `fit_stage` runs SPD's LM rules over any update strategy with SPD's
  acceptance, numerical-regime stop, work units and quota reservation.
  `run_policy` loops a policy and calls an external endpoint hook.
  `BackendConfig.step_control` is `"coefficient"` (SPD's per-coefficient
  clip, the default) or `"physical"` (scale the whole step to a maximum
  normal move); see `control_step`.
- `spd_cases.py`, `spd_report.py`: SC-020 harness and report. These are the
  only modules that import SPD code. They cover the coordinate/unit bridge, the
  SPD-matching policy, a fresh SPD rerun, and scoring through SPD's own scorer.
- `atlas_survey.py`: atlas layers in the backend's coordinates: sensitivity,
  signed gradient, Gauss–Newton block, LM and truncated GN steps. Stage blocks
  are weighted sums of per-frequency layers.
  - `conditional_step` solves on a declared coordinate set; this is not a
    slice of a larger solve.
  - `rms_weights`, `physical_norm` and `physical_cosine` give the arclength
    Fourier mass metric.
  - Evaluation only: `true_error` (a closest-distance proxy),
    `normal_ray_error` (the exact current-normal move to the truth) and
    `symmetric_rms_distance`.
- `atlas_cases.py`: SC-022 cases and oracle-checked frequency catalogs,
  fixed-schedule trajectories under a declared band rule (`fixed32` or
  `borges`), and the parallel atlas over every accepted state.
- `conditional_study.py`, `conditional_rules.py`: SC-023.
  - Q0 numerical qualification: atlas refinement, directional checks and the
    refit-gate record.
  - The offline candidate table: conditional steps, geometry-only trials and
    evaluation-only gains.
  - The declared truth-free band rules and their evaluation.
- `ablation_cases.py`: SC-024(a), shared-backend variants (step control,
  refit gate, iteration cap) of SC-022's trajectories.
- `probe_cases.py`: SC-024(b), rule-chosen steps executed at recorded states.
- `policy_cases.py`: SC-025, band policies (ladder, fixed32, progress, and the
  A2 `parsimonious` atlas rule) on development and declared held-out cases.
- `atlas_dataset.py`: SC-026's consolidated normalized Jacobians and residuals
  over 1,286 unique states, with separately stored evaluation-only layers.
- `atlas_strategy_tests.py`: SC-028/029's isolated initial-band and frequency
  comparison using the existing `fit_stage` API, fixed budgets and saved
  prefix reuse. The [run record](../../results/validation/shape_continuation/SC-029-atlas-strategies/README.md)
  distinguishes the failed P=48 preflight from the M<=19 inverse-space gate.
- `finite_paths.py`: SC-036's opt-in `RayUpdate`, a finite ray path about the
  current parameter-mean centre with exactly `BorgesUpdate`'s normal velocity,
  Jacobian and metric; non-star states are refused, or use the normal path
  only with `fallback=True`. `finite_path_study.py` is the matched replay
  screen; `test_finite_paths.py` checks circle equivalence, identical normal
  velocity, the actual-trial derivative and the refusals. Not adopted: see the
  [SC-036 record](../../results/validation/shape_continuation/SC-036-matched-finite-paths/README.md).
  SC-035's centred state-band update stays isolated in its result bundle.
- `pipeline_video.py`: one video per development scene through the current
  pipeline (SC-035 state band, then SC-038's release), each frame showing the
  saved state and its atlas; see the [video index](../../results/validation/shape_continuation/videos/README.md).
  `atlas_video.py` holds the atlas: per frequency and ripple order, the
  heuristic QR misfit score from ideal normal ripples, with an assumed display
  threshold. Its componentwise caps do not establish a physical joint-step
  bound or a stable recovery frontier; use `action_atlas.py` for the corrected
  complete-update diagnostic. `test_atlas_video.py` checks the preserved score
  algebra. Both renderers stop unless every
  atlas reproduces its run's saved loss.
- `render_videos.py`: the earlier side-by-side comparison (original hybrid,
  SC-035 state band, SPD-L), now written to `videos/three_method_comparison/`.
- `trajectory_atlas.py`: SC-039's raw boundary data along every saved
  trajectory (forward/reciprocal traces, node geometry, full 24x24 prediction
  at 19 frequencies on 512/1024 nodes), and the later-atlas helpers `load`,
  `jacobian`, `cartesian_velocities` and `normal_velocities`, which rebuild
  `shape_jacobian` in any coordinates without solves. `test_trajectory_atlas.py`
  checks the contraction against `shape_jacobian` and the Cartesian circle law.
- `test_atlas_survey.py`: the stage step assembled from per-frequency layers
  equals the backend's proposal. Also checked:
  - the GN step algebra and the Schur-complement conditional step;
  - the mass metric;
  - normal-ray exactness on offset circles;
  - the doubled harmonic created by one Borges move.
- `test_policies.py`: the declared band rules, regret evaluation, the
  progress controller, the band-policy loop and the held-out truths.
- `test_lm_backend.py`: the residual map is bitwise equal to SPD's; the
  acceptance rule equals SPD's; the Jacobian matches differences through the
  actual trial; accepted states decrease monotonically; the quota ends a stage
  normally; import isolation holds.
- `test_point_sources.py`: independent old Mie/Nyström oracle agreement,
  paired line-source derivative checks, cache invalidation, sparse frequency
  catalogs, curve-coordinate conversion and terminal progress checks.
- `resolution.py`: independent field/Jacobian convergence and timing screen.
- `test_pipeline.py`: independent circle series, derivative convergence,
  geometry/reparameterization, recovery, continuation and import isolation.
- `atlas.py`: frequency x shape-harmonic characterization at one geometry on an
  `L^2(ds)`-orthonormal normal-displacement basis, with a declared data
  whitening. Stores four separate layers -- sensitivity, signed residual
  gradient, the full Gauss-Newton block and its spectrum -- plus the energy
  each Jacobian column leaves off the circle's exact selection line.
- `horizon.py`: gauge-preserving finite displacements, and the residual-free
  measurement of where `J h` stops describing the measured change in the data.
- `policy.py`: continuation decisions from those measurements -- the update
  band from where detectability meets the horizon, the next frequency from
  whether its own model delivers its promised decrease.
- `survey.py`, `validity.py`, `campaign.py`: the drivers for SC-015, SC-016 and
  SC-017. Probes inside a policy are charged to the same `Work` budget as the
  inversion, so an arm that measures more has fewer solves left to optimize.
- `test_atlas.py`, `test_horizon.py`: the conventions above, an exact circle
  law (rotational equivariance forces each Jacobian column onto the line
  `a+b=p` and the order table to be rank one), and that a measured horizon
  does not move when the quadrature is refined.

Validation is bounded to unit/derivative checks, short synthetic smoke
recoveries, glider ladders through k=8, and checkpoint extensions through k=12
(1500 inverse forward evaluations and 10 minutes of inverse work per run).
The 117-frequency paper campaign and adaptive-policy comparisons are not
part of this implementation qualification. Truth generates observations and
scores the result; it is absent from the optimizer interface.

## Mathematical choices

On the unit circle, a finite Cartesian Fourier curve and a two-sided complex
Laurent polynomial are equivalent: `z(t)=x(t)+i y(t)=sum z_n exp(i n t)`.
There is no conjugate-symmetry restriction on `z_n`, because `z` is complex.
This does not make an arbitrary curve a univalent exterior conformal map.
Fourier geometry does not require Fourier–Galerkin boundary integral assembly.

The paper stores a general Cartesian curve, reparameterizes it by arclength,
and solves for a real scalar normal displacement `h(s)`, rather than optimizing
every Cartesian coordinate coefficient. Its regularization acts on the update
band and the curvature spectrum. Three resolutions must remain independent:
normal update modes, stored Cartesian curve modes, and forward quadrature nodes.
Arclength conversion generally needs more curve modes than a polar chart.

The reference algorithm uses one frequency per stage, not cumulative data.
§2.1 describes `ceil(c*k)` update/curvature bands; §4 actually uses
`floor(3*max(k,ki))` update modes, frequencies `1:0.25:30`, plane waves,
receivers on radius 10, and `floor(10*k)` directions and receivers. These are
dimensionless coordinates and wavenumbers: physical GHz values cannot be
substituted into a mode rule without choosing a length scale.

## Run

From the repository root, use a fresh output directory:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/shape_continuation
$PY -m experiments.shape_continuation.run --scene ellipse --output /tmp/continuation-ellipse-new
```

The library requires NumPy and SciPy; the demo plot also uses Matplotlib.
The [paper harness and fidelity audit](PAPER.md) additionally use Shapely only
for polygon area scoring. Its default command does no numerical solves:

```bash
$PY -m experiments.shape_continuation.paper --output /tmp/figure1-plan
```
No neural or old inverse package is imported, even during forward evaluation.
`run_adaptive(initial, observations, contrast, strategy)` is the general
controller. `prepare_state` and `optimise_step` expose one update with a retained
forward state; `fit_prepared` groups updates without losing that cache.
`fit_frequency(...)` remains a convenient fresh one-frequency fit.
`run_continuation(initial, observations, stages, contrast)` is a compatibility
adapter over the same controller for an increasing frequency ladder. Its
`stages` argument remains a list or callback `(shape, next_k, previous_stage)`,
and `on_stage` remains available for checkpointing. No optimizer/controller
interface supplies true geometry or evaluation data.
Observations own immutable complex data and acquisition arrays. `Stage` owns
the wavenumber, normal update band, curve storage band, Kress nodes, and
curvature band. The `Work` object enforces evaluation caps before new work and
checks elapsed time between operations; it cannot interrupt an in-flight solve.

By default the demo uses `k=1,1.25,1.5,1.75,2`, a unit-circle start, contrast `ki²/k²=1.44`,
and 48 stored curve modes / 128 Kress nodes. It generates observations at
512 nodes after a 256/512 check, uses `floor(10*k)` incident directions and
receivers, and evaluates the endpoint at doubled resolution and at an unused
frequency/acquisition. Synthetic reference generation and scoring have separate
work counters and never enter the inverse. With five stages, caps are 550
inverse + 10 observation + 22 evaluation solves (the latter includes optional
stage checks). Numerical work budgets and the frequency interval are explicit
CLI controls for subsequent qualifications; they are not silently extended.

For the wavelength-scaled resolution policy and checked stage handoffs:

```bash
$PY -m experiments.shape_continuation.run --scene glider --resolution paper \
  --verify-stages --k-stop 8 --max-iterations 50 --max-forwards 1500 \
  --max-seconds 600 --output /tmp/continuation-glider-new
```

This computes stage storage and quadrature from the current iterate's perimeter
and the declared points-per-wavelength setting. `--curve-modes` and `--nodes`
are minimum values in this policy; they are fixed values under `--resolution
fixed`. Every stage saves geometry, history, rejected trials, stop reason and
work counters before its optional N/2N field and full-Jacobian checks (both
relative differences must be at most `1e-6`). A failed check stops the run with
the checkpoint retained. The run also records observation-generation, inverse
(including requested stage checks) and endpoint-scoring wall times separately.

`--backtracks 0` disables the added step halvings before Gaussian filtering,
for comparisons with the paper's search sequence. The default remains 8;
the saved filter-only glider comparison did not improve recovery.

To continue a saved endpoint, use a new output directory and an explicit
frequency range and budget, for example:

```bash
$PY -m experiments.shape_continuation.run --scene glider --resolution paper \
  --verify-stages --resume-from results/validation/shape_continuation/SC-005-glider-filtered-step \
  --k-start 4.75 --k-stop 12 --max-iterations 50 --max-forwards 1500 \
  --max-seconds 600 --output /tmp/continuation-glider-extension
```

A restart may repeat the saved last frequency or advance. It checks material
contrast and the exact synthetic truth fixture, preserves stored modes, hashes
the parent bundle, and records cumulative inverse forward calls. Its initial
curve is the saved endpoint, not the unit disk. The new run has a fresh,
explicit budget; extension results must not be compared as though they had
the original run's budget. A restart requires a bundle with saved `summary.json`,
`inputs.npz`, and `states.npz`; an interrupted individual stage checkpoint can
still be loaded manually through the independent `fit_frequency` API.

`paper_wavenumbers()` supplies the full 117-stage grid. `paper_stage(...)`
supplies an explicit resolution proposal using the current perimeter and
previous storage band; it does not silently alter an optimization stage.
Its default 20 points/wavelength is a pilot setting; pass 70 to request the
paper's inversion setting. The Fourier sampling constraint may require more
nodes. A frequency/mode policy can replace these stage proposals while keeping
the single-frequency optimizer and data interface unchanged.

## Fidelity to the paper and declared differences

Implemented: general Cartesian Fourier geometry in an arclength gauge;
Fourier normal displacements; single-frequency recursive linearization;
plane waves and the full receiver matrix; known equal-density contrast;
curvature-spectrum admissibility; GN and SD candidates; Gaussian filtering
of the normal update; warm starts with nondecreasing storage band.

Differences that matter:

- Kress product integration replaces the paper's Alpert quadrature, as
  requested. The physical conventions are checked against an independent
  Fourier–Bessel circle solution; formulas are not copied across conventions.
- The shape Jacobian is the equal-density reciprocal/Hadamard identity using
  converged nodal traces. It reuses the forward LU for receiver-source traces.
  It approximates the continuous derivative and is **not** asserted to be the
  exact derivative of every underresolved finite matrix.
- Real-stacked least squares uses an SVD rank cutoff, not explicit normal
  equations. Candidate selection uses the stacked residual 2-norm consistently.
- Both GN and SD candidates are evaluated. SD is scaled to the Cauchy point
  `t = |J*r|²/|J J*r|²`, as in the authors' code; eq.18 names only the
  direction, whose raw magnitude is not a usable step. The residual-decrease
  requirement matches that code, which exits its filter loop only on a
  non-increasing residual. Backtracking is ours and is off in the paper profile.
- `geometry.gaussian_filter` damps harmonic `n` of the **normal update** by
  `exp(-(n/M)²/sigma)` with `sigma = 10^(1-level)`, following
  `update_inverse_iterate`. Eq.19 instead writes the stored-curve band and
  `sigma²`; read that way the first levels are no-ops and the rest collapse the
  update to a translation, leaving the search no intermediate strength.
- The curvature tail tolerance, rank threshold `1e-10`, projection
  tolerance `1e-7`, and backtracking controls were declared pilot choices. The
  tolerance now has a source: the authors' drivers set `eps_curv=0.1` on an
  amplitude ratio over `|n| > max(20, M)`, so the paper profile uses the
  equivalent energy fraction `0.01` on that band. The paper's residual/step
  tolerances `1e-5` and 50-iteration default are retained; the CLI bounds the
  pilot at 20 iterations per frequency. Stops distinguish data fit, stationarity,
  small step, no admissible decreasing step, iteration limit, and work limit.
  Step size is the arclength-weighted RMS physical displacement after Gaussian
  filtering, measured before reparameterization changes the point labels.
  Maximum displacement, the raw coefficient norm, and `update_norm` (the
  filtered update's 2-norm, which is the reference code's own step measure)
  are retained as diagnostics.
  A small filtered step can end a stage without asserting stationarity or a fit.
- The default smoke run fixes storage and forward resolution. The optional
  wavelength-scaled policy and N/2N stage checks support longer ladders. A
  failed stage check stops with saved state; there is no hidden solver switch
  or unbounded automatic refinement. Reference observations must separately
  pass the `data-nodes/2` versus `data-nodes` gate before inversion begins.
- Boundary errors use symmetric vertex-to-segment distance with sampling
  resolution recorded. A conservative continuous-curve error bound includes
  half-edge sampling and Fourier second-derivative interpolation bounds; the
  shape gate uses the error plus this bound. Area-size difference is also saved.
  `metrics.area_error` now supplies the paper harness's polygon symmetric-area
  score, both directed area differences, and an N/2N polygon-refinement check.
  The interpretation of the paper's set difference is documented in
  [the audit](PAPER.md#area-scoring). No volume inverse is implemented.

## Qualification and remaining work

See the [saved qualification](../../results/validation/shape_continuation/README.md).
The [cleanup/profile qualification](../../results/validation/shape_continuation/SC-002-profile-after/README.md)
reduced this ellipse inverse from 19.66 s to 0.835 s by accelerating the geometry
checks. Every saved accepted state is bitwise unchanged. This is measured at
128 Kress nodes and is not a high-frequency performance claim.
The subsequent [resolution screen](../../results/validation/shape_continuation/SC-003-resolution-refined/README.md)
qualified spectral arclength integration and a faster blocked reciprocal
contraction through k=8 on ellipse/glider geometries. Those numerical changes
are distinct from the bitwise-preserving SC-002 cleanup.
The [glider checkpoint extension through k=12](../../results/validation/shape_continuation/SC-008-glider-extension/README.md)
now passes field/Jacobian refinement, held-out prediction and conservative shape
gates, using 2022 cumulative inverse forward calls from the original circle.
The held-out error is 9.98e-6 and the relative boundary-error upper bound is
0.001803. The final stop is a small step, with residual 2.47e-5, rather than a
claim of meeting the stricter 1e-5 data-fit tolerance.
This establishes a working inverse and checked continuation interface for the
ellipse and one glider case. It does not establish general robustness for
cavities, high contrast, noisy/limited aperture observations, unknown material,
or multiple components.

The `glider` fixture matches the paper's listed radial coefficients, but the
short `k<=2` demo is not its reconstruction campaign. The
[Figure 1 audit](PAPER.md) supplies the two actual contrasts and selectable
profiles. The [latest review](../../docs/iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
accepts the optimizer fixes; it records remaining stopping/resolution differences
and unverified plotting provenance. SC-014 shows partial agreement at low
contrast, while high contrast remains unmatched. Full paper replication,
including its harder shapes, is not established.

For subsequent adaptive experiments, keep geometry/solver/optimizer fixed.
Frequency jumps must select observations that actually exist; held-out data and
true boundary errors remain scoring inputs only. Small steps are not stationarity
certificates. Residuals at different frequencies are different objectives.

## Measured characterization

`atlas.py`, `horizon.py` and `policy.py` add measurement, not new physics. They
change no solver, optimizer or geometry code, and the inverse is bitwise
unaffected when they are not used. Three conventions are fixed there once and
should not be re-derived elsewhere:

- a shape direction is a normal displacement with unit `L^2(ds)` norm on the
  current curve, not a Cartesian Fourier coefficient of `z(t)`; rescaling the
  basis rescales every diagonal information measure;
- data are whitened by `C = sigma^2 I` with `sigma` from a declared
  `Whitening`, and nothing else divides by a data norm;
- a displaced curve used for a finite-difference measurement keeps the
  arclength gauge and is checked against its own displacement, so a horizon
  never depends on a reparameterization tolerance.

The measurements are recorded in
[SC-015](../../results/validation/shape_continuation/SC-015-atlas-structure/README.md),
[SC-016](../../results/validation/shape_continuation/SC-016-validity-horizon/README.md)
and [SC-017](../../results/validation/shape_continuation/SC-017-atlas-controller/README.md).
The harmonic axis is not gauge-invariant off the circle; `transport_overlap`
and the recorded order-mixing fractions say how far a cell from one iterate may
be compared with a cell from another.

## Adaptive controller contract

```python
from experiments.shape_continuation.continuation import Decision, run_adaptive
from experiments.shape_continuation.inverse import FitConfig

# A strategy is just a callable: no inheritance, registry, or solver changes.
def strategy(context):
    # context.shape: last committed curve
    # context.history: all decisions, accepted/rejected trajectories and checks
    # context.available_wavenumbers: frequencies with measured data
    # context.work: cumulative counters and timings
    stage = choose_next_stage(context)  # experiment-specific rule
    if stage is None:
        return None
    return Decision(stage, FitConfig(max_iterations=1), reason="record the rule")

result = run_adaptive(initial, observations, contrast, strategy,
                      work=work, max_decisions=200, on_decision=save_checkpoint)
```

`choose_next_stage` and `save_checkpoint` are user-supplied functions in this
sketch. A decision controls frequency **k**, normal-update modes **M**, curvature
band **C**, curve storage **K**, quadrature **N**, and all `FitConfig` settings.
`max_iterations=1` returns control after at most one accepted update; a larger
value requests a fixed-stage chunk. Zero permits a resolution-only decision.
The controller permits repeated, skipped, or revisited available frequencies.
`FixedSchedule(stages, config)` supplies the simple fixed-list policy.

The execution flow is:

```text
shape = initial curve
live_state = empty
history = []
repeat:
    decision = strategy(shape, full history, available frequencies, work)
    if decision is STOP: finish
    enforce decision limit
    on first decision: refit initial curve by arclength at the chosen K
    state = prepare_state(shape, data[k], decision, cached=live_state)
    repeat up to decision.max_iterations:
        form normal Fourier basis and Jacobian using state's existing LU
        compute GN and SD directions
        search filter strengths and step halvings:
            reject invalid geometry, unresolved refits, excessive curvature tail
            solve valid candidates; accept the best decreasing GN/SD candidate
            at the first successful search level
        retain accepted candidate's already-computed forward state
        record diagnostics and every trial; stop chunk on local stopping rule
    optionally qualify endpoint (e.g. field AND Jacobian at N/2N)
    if qualification passes: commit endpoint and its live state
    else: retain previous curve and cache
    append decision, chunk report, qualification, commit flag and work counters
    checkpoint; stop globally if shared budget exhausted
```

Local stops (`data_fit`, `small_step`, `stationary`, `no_acceptable_step`,
`iteration_limit`) are evidence for the strategy; only the controller's
`policy_stop`, `decision_limit`, or `budget_exhausted` ends the run. The same
`Work` instance charges all decisions and optional checks; time limits are
checked between operations, not by interrupting an in-flight solve.

Changing M, C, tolerances, or zero-padding K reuses the current physical solve.
Changing the curve, k, contrast, acquisition, or N rebuilds it. A data-only
change reuses the prediction and recomputes its residual through `prepare_state`.
Cache matching is exact. Reducing stored K requires an explicit, separately
qualified projection; the controller refuses silent truncation. Input arrays
and policy history must be treated as read-only.

Use `qualify=ResolutionGate(tolerance=1e-6)` to require both fields and the full
normal Jacobian to agree at N/2N. This reuses the current N-node LU and adds one
2N solve plus two Jacobians. A failed check rolls back the **whole decision**;
the next policy call sees the rejected report and last committed curve. Budget
exhaustion before/during qualification also rolls back the unqualified chunk.
Without a gate, accepted partial progress is retained on budget exhaustion.
The initial curve is supplied by the caller; rollback does not certify it.

Each decision record contains its reason/settings, full `FitResult`, commit
flag, check diagnostics and work snapshots. A rejected report's endpoint may
therefore differ from `context.shape`. Gradient/rank/singular-value diagnostics
belong to the **input** of each update; they are not recomputed at its endpoint.
Reports retain coefficient histories, never dense matrices or factorizations.
Only the current live cache and transient candidate work retain dense arrays.
This is continuation infrastructure, not a claim that any adaptive rule is
more robust or faster than the fixed ladder.
