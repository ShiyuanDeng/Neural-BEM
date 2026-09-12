# Topology scenes v1 — required performance comparison

The user requested broader current and future scene evaluation on 2026-09-11.
The frozen specification is
[`config/topology_scenes_v1.json`](../../config/topology_scenes_v1.json),
executed by [`run_topology_scene_benchmark.py`](../../run_topology_scene_benchmark.py).
Its first measurement is [TOP-006](../../results/validation/topology/TOP-006-20260911-scenes-v1/README.md):
both current policies pass 5/12 scenes. The requested distant ellipse/star case
fails; retain it as a regression target rather than removing it from the suite.
Its second is [TOP-007](../../results/validation/topology/TOP-007-20260911-refined-feasibility/README.md),
which adds the guarded arm: still 5/12, but nothing aborts and the requested
case finishes with the correct object count and the wrong shapes. Its third is
[TOP-008](../../results/validation/topology/TOP-008-20260912-feasible-fd/README.md),
which corrects the finite-difference stencil at an active constraint: 10/12 runs
return against 9/12, `split` improves to 0.000023 mm at a quarter of the solves,
and the pass count is **still 5/12**.
[TOP-009](../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md)
stopped before reaching this suite: its stage-2 gate showed that adding shape
bandwidth fits the training data 248x better while leaving final boundary error,
IoU and holdout error worse, so the suite was not spent on a rule that
degrades a gated metric. Its stage-3 diagnostic then traced most of that
degradation to rotational phase on a ladder truncated by its own solve cap, and
established that the true geometry fits this acquisition to 3.23e-07 relative
error. Stage 4 then exhausted the ladder at K=9 and the failure survived it.
[Independent review](../iterations/topology/iteration_07/02_proposals/01_independent_review.md)
qualifies the interpretation: the `far-two-stars` truth is representable and
consistent with the observations, but uniqueness and terminal stationarity
were not established. Thirteen of fourteen rung refinements stopped on small
loss change. This diagnostic bypassed the full controller and does not qualify
promotion on the twelve-scene benchmark.

## Scene matrix

| Group | Scenes | What they distinguish |
|---|---|---|
| Original controls | repeated-birth, death, split, merge, mixed | Existing automatic-controller behavior |
| Distant circle-only control | far-two-circles | Poor initialization without noncircular truth |
| Same shape family, different starts | far-ellipse-star, central-ellipse-star, enclosing-ellipse-star, empty-ellipse-star | Translation, excess material, connectivity and shape recovery |
| More boundary detail | far-two-stars | Five- and seven-lobed noncircular children |
| More objects and shape diversity | far-three-shapes | Ellipse, star and circle, with no supplied count |

The requested distant circle has a 75-mm radius at (0.40, 0.57). The ellipse
is centered at (0.55, 0.43), with 45/26-mm semiaxes, rotated 0.55 rad. The
five-lobed star is centered at (0.61, 0.53), with 36-mm mean radius and 24%
radial modulation. The initial circle and targets are disjoint and entirely
inside the unchanged inspection disk. Exact values for every scene live in
the JSON; scene names alone do not define a reproducible comparison.

## Required reporting for future topology performance claims

Run all twelve scenes with the candidate and reference policy, using the
same initial states, observations, acquisition, nodes and budgets. Report
every row, including timeout, exception, wrong count, wrong shape and poor
holdout predictions. A selected easy subset is a diagnostic, not a replacement
for the performance suite. Keep the existing circular replay studies for
mechanism diagnosis alongside the broader benchmark.

Keep v1 immutable. A changed scene, acquisition, mode schedule, tolerance or
budget is a separately named comparison; never overwrite v1 evidence or loosen
its gates to turn a failure into a pass. New scenes extend coverage in a new
version. Do not infer generalization from the number of runs on the same truth.

Use the stored portable observations as the comparison reference. Confirm
their hashes match across arms and against the baseline bundle; if data
generation changes with a solver change, reuse the original observations
rather than treating newly generated data as the same experiment.
The runner's `--reference-data` option copies the original observations and
starting coefficients, validates the acquisition/material specification, and
performs no new oracle solves. Use it for future v1 comparisons.

Success requires correct count, <=1-mm matched boundary error, >=0.90 material
IoU, <=0.003 refined training error, <=0.05 worst held-out-frequency error,
monotone accepted states and valid cross-resolution event margins. Report each
criterion separately. A `recovered` controller stop tests the training fit and
does not establish geometrical recovery.

The benchmark remains noiseless, separated, same-material and two-dimensional.
Noncircular data use analytic curves with a checked finer Kress discretization,
not an independent physical solver. Object counts and truth shape definitions
are used only for observation generation and evaluation.

## Running and reviewing

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_topology_scene_benchmark.py --workers 4 --arms A,G --experiment-id TOP-007 \
  --reference-data results/validation/topology/TOP-006-20260911-scenes-v1 \
  --output results/validation/topology/my-fresh-scene-comparison
```

The output directory must be new. `--arms` names the controller policies to
compare — `A` default, `F` selective refinement, `G` default plus the refined
feasibility guard, `H` that guard plus the feasible finite-difference stencil,
and `J` that pair plus bandwidth promotion — and defaults to `A,F`. The chosen arms and their policy
overrides are recorded in the run manifest, and every arm shares the same
scenes, observations, initial states, budgets and gates: an arm changes the
controller policy and nothing else. A candidate policy needs its own name
here rather than a changed default, so the reference arm stays comparable.
**Do not edit any hashed source while a suite is running** — the runner
re-checks `solvers/**/*.py`, `run_*topology*.py` and `config/**/*.py` before
each inversion and fails the run if they changed.

The runner checks oracle convergence, then runs each requested arm. Each
inversion has a ten-minute ceiling; the suite has a 45-minute inversion ceiling. Four single-thread subprocesses
may overlap; elapsed times are descriptive, not a controlled speed comparison.

Start visual review with `initial_scenes.svg`, `far_ellipse_star.svg`, then
`new_results.svg` and `original_results.svg`. Dashed curves are targets,
dotted curves are initial shapes, and solid teal curves are reconstructions.
The requested case also gets one video per arm from actual accepted states.
On an exception or timeout, figures show the last saved state and label it as
failed; partial solve counts are lower bounds, not complete cost measurements.
Read `suite_metrics.json` for all outcomes and pairing checks, and each run's
`topology_passes.json` for candidate-level causes. `--summary-only` rebuilds
figures and metrics from saved runs without rerunning inversion.
