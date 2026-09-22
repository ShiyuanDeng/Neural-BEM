# Shape and frequency continuation on nodal Müller/Kress

Implementation started 2026-09-22 under the user's explicit instruction to
replicate the algorithm in Borges, Rachh and Greengard, or build the inverse
until its continuation scheme can be implemented. Continued on the user-authorized
`feature/shape-frequency-continuation` branch, with committed/pushed checkpoints.
Owner: Codex. Independent reviewer: unassigned.

Reference: [On the robustness of inverse scattering for penetrable,
homogeneous objects with complicated boundary, Inverse Problems 39 (2023)
035004](https://doi.org/10.1088/1361-6420/acb2ec),
[author manuscript, §2.1 and §4](https://arxiv.org/html/2210.11607v1).

## Scope and file/API map

This is a new, isolated single-interface inverse, justified by the user's
request to remove legacy inverse dependencies. The only project dependencies
are `ordered_boundary` and public `gpr_bem_kress` forward APIs. No existing
numerical code or defaults are changed. No MLP, SDF, topology controller,
runtime selector, modal compression, or experimental Laurent solver is used.

- `geometry.py`: Cartesian Fourier curve storage, arclength reparameterization,
  scalar Fourier normal updates, Gaussian filtering, curvature-energy gate.
- `validation.py`: conservative spatial pruning of polygon intersection checks,
  qualified against the all-pairs reference at identical samples/tolerances.
- `forward.py`: plane-wave acquisition, full receiver/illumination matrix,
  dense nodal Müller/Kress solves, reciprocal shape Jacobian.
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
- `resolution.py`: independent field/Jacobian convergence and timing screen.
- `test_pipeline.py`: independent circle series, derivative convergence,
  geometry/reparameterization, recovery, continuation and import isolation.

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
of the Cartesian displacement; warm starts with nondecreasing storage band.

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
- Both GN and raw SD candidates are evaluated. Backtracking and an explicit
  residual-decrease requirement are added before increasing the Gaussian
  filter level. This is a safeguarded adaptation of the paper's GN/SD/filter
  procedure, not a claim of identical author code or textbook Powell dogleg.
- The curvature tail tolerance `0.1`, rank threshold `1e-10`, projection
  tolerance `1e-7`, and backtracking controls are declared pilot choices. They
  are not presented as recovered author settings. The paper's residual/step
  tolerances `1e-5` and 50-iteration default are retained; the CLI bounds the
  pilot at 20 iterations per frequency. Stops distinguish data fit, stationarity,
  small step, no admissible decreasing step, iteration limit, and work limit.
  Step size is the arclength-weighted RMS physical displacement after Gaussian
  filtering, measured before reparameterization changes the point labels.
  Maximum displacement and the raw coefficient norm are retained as diagnostics.
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
short `k<=2` demo is not its reconstruction campaign. Full paper replication
still needs verified author curvature/filter settings and comparisons on the
paper's harder shapes. [Figure 1 preparation](PAPER.md) supplies the two actual
contrasts and an explicit frequency/resolution profile; its small smoke is not
a reproduction of the published reconstructions.

For subsequent adaptive experiments, keep geometry/solver/optimizer fixed.
Frequency jumps must select observations that actually exist; held-out data and
true boundary errors remain scoring inputs only. Small steps are not stationarity
certificates. Residuals at different frequencies are different objectives.

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
