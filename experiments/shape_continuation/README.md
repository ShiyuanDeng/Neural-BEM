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
- `inverse.py`: one-frequency real least squares, GN/SD candidate evaluation,
  explicit feasibility and stopping, and stage-to-stage warm starts.
- `schedule.py`: explicit independent update/curve/quadrature resolutions,
  including the paper's fixed frequency grid and §4 update-mode rule.
- `run.py`: bounded synthetic recovery demonstration and saved provenance.
- `metrics.py`: evaluation-only boundary distances; no inverse dependency.
- `benchmark.py`: inverse-only replay timing from saved observations.
- `resolution.py`: independent field/Jacobian convergence and timing screen.
- `test_pipeline.py`: independent circle series, derivative convergence,
  geometry/reparameterization, recovery, continuation and import isolation.

Validation is bounded to unit/derivative checks, short synthetic smoke
recoveries, and a glider ladder through k=8 (1500 inverse forward evaluations
and 10 minutes of inverse work per run).
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
$PY -m pytest -q experiments/shape_continuation/test_pipeline.py
$PY -m experiments.shape_continuation.run --scene ellipse --output /tmp/continuation-ellipse-new
```

The library requires NumPy and SciPy; the demo plot also uses Matplotlib.
No neural or old inverse package is imported, even during forward evaluation.
`run_continuation(initial, observations, stages, contrast)` is the orchestration
entry point; `fit_frequency(...)` is the independent one-frequency operation.
`stages` can be a fixed list or a callable receiving the current shape,
next wavenumber and previous stage. `on_stage` receives each completed result
for checkpointing. Neither interface supplies true geometry or evaluation data.
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
work counters before its optional N/2N check. A failed check stops the run with
the checkpoint retained. The run also records observation-generation, inverse
(including requested stage checks) and endpoint-scoring wall times separately.

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
  resolution recorded, and area-size difference. The paper's symmetric-area
  reconstruction metric is not implemented. No volume inverse is implemented.

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
This establishes a small working inverse and continuation interface. It does
not establish robustness for gliders/cavities, high contrast, noisy/limited
aperture observations, unknown material, or multiple components.

The `glider` fixture matches the paper's listed radial coefficients, but the
short `k<=2` demo is not its reconstruction campaign. Full paper replication
still needs an agreed curvature tolerance/filter interpretation, the complete
frequency/resolution settings, and comparisons on the paper's harder shapes.

For subsequent adaptive experiments, keep geometry/solver/optimizer fixed and
change only the stage policy: repeat the current frequency, increase the update
band, increase frequency, or refine quadrature. Record the reason, data residual,
gradient, singular spectrum, curvature tail, projection error, and work.
Frequency jumps must select observations that actually exist; held-out data and
true boundary errors remain scoring inputs only. Small steps are not stationarity
certificates. Residuals at different frequencies are different objectives.
