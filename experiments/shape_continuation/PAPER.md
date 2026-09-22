# Figure 1 preparation

Target: the **boundary inverse** contrast experiment in [Borges, Rachh and
Greengard, §4.1 / Figure 1](https://arxiv.org/html/2210.11607v1#S4.SS1).
The volume inverse and other figures are outside this profile. This is a
reproducible approximation with an explicit audit, not an exact replication.

## Commands

From the repository root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pip install -r experiments/shape_continuation/requirements-paper.txt

# Default: full plan, no data generation or inverse solves.
$PY -m experiments.shape_continuation.paper --output /tmp/figure1-plan

# Both contrasts at k=1, at most one accepted update each.
$PY -m experiments.shape_continuation.paper --mode smoke --output /tmp/figure1-smoke
```

Smoke has a shared cap of **16 forward calls and 30 seconds** for both cases,
including reference generation and field/Jacobian qualification. Time is checked
between operations; it cannot interrupt an in-flight solve. This is an interface
check, not a reconstruction. Budget or qualification failures remain in the
output directory. Each checkpoint includes all trials and accepted states.

`--mode run` is the future campaign entry point. It requires explicit
`--max-forwards` and `--max-seconds`; the budget covers both contrasts unless
`--contrast 0.33` or `--contrast 10` selects one. `--k-stop` selects an endpoint
on the fixed grid. No large run is performed by the default command. These runs
start from the unit circle; checkpoint resume is not implemented in this harness.

## Profile and fidelity audit

| Control | Profile | Source / interpretation |
|---|---|---|
| Geometry | Existing analytic glider fixture; unit-circle initialization | §4.1 radial coefficients, §2.1 start |
| Contrast | `ki²/k² = 0.33, 10` | §4.1; do not invert this ratio |
| Frequencies | `1:0.25:30`; snapshots `1,5,10` | §4 defaults and Figure 1 snapshots; full default ladder retained |
| Acquisition | `floor(10k)` directions and receivers, radius 10 | §4; cyclic ordering starts at zero |
| Normal update band M | `floor(3 max(k,ki))` | §4 experimental rule |
| Curve storage K | `max(previous K, M, ceil(70 L k / 2π))` | Exterior `k` in eq.12; extra `K>=M` for storage |
| Inverse nodes N | Even ceiling of `max(64, 70 L max(k,ki)/2π, 2(K+1))` | §2 shortest wavelength plus Kress/Fourier sampling constraint |
| Reference data | Mean 100 points/shortest wavelength, plus doubled nodes | §4 density; exact polar fixture and doubled data used here |
| Iteration / stopping | 50; residual and physical RMS update `1e-5` | §4 tolerances; RMS normalization is our convention |
| Gaussian filter | Up to 10 levels, `sigma=10^(1-level)` | Eq.19; applied afresh to the Cartesian update |
| Added halvings | Disabled (`backtracks=0`) | Follow the paper's filtering order |
| Curvature band / tail | `ceil(2k)` / `0.1` | `c=2` from §2.1; numeric tail tolerance is our declared assumption |

The old `schedule.paper_stage` is the previously qualified pilot and is
unchanged. It puts `max(k,ki)` in **both** storage and quadrature estimates. The
new profile separates them. Neither should be described simply as “70 nodes per
wavelength”: storing modes `-K:K` requires more than `2K` samples. The manuscript
also quotes `N=70 L k/(2π)` after Theorem 2.1; this conflicts with taking eq.12
literally at the same sampling density and with the shortest-wavelength wording
at high contrast. Our interpretation is explicit, not a recovered author count.
Plan sizes use the initial circle; actual inverse sizes depend on its evolving
perimeter. Matrix bytes describe **one** dense complex matrix, not peak memory.

Remaining differences requiring care in any comparison:

- Nodal Müller/Kress replaces Alpert quadrature, by user choice. The continuous
  reciprocal Jacobian and real SVD least squares remain the qualified baseline.
- K and N are selected at each frequency handoff. Eq.12 describes updating K
  after individual deformations. A controller can refresh these between updates,
  but this fixed-stage profile does not implement candidate-dependent storage.
- Reference geometry keeps the exact polar Fourier parameterization. Its node
  density is a mean density, rather than uniform arclength. Data must pass an
  N/2N field check (`1e-7`); the inverse uses the doubled reference data.
- Candidate ranking uses the stacked Euclidean residual; the paper writes a
  sum of per-illumination norms. Strict residual decrease, gradient stopping,
  projection tolerance `1e-7`, and SVD cutoff `1e-10` remain our safeguards.
  Disabling backtracking does not remove these differences.
- No numerical value for `epsilon_f` was located in the manuscript. The precise
  normalization of the update 2-norm and whether successive Gaussian filters
  compose are also not specified sufficiently to claim identical trajectories.
- Every completed stage must pass an added N/2N field **and full normal
  Jacobian** check (`1e-6`). Failed qualification rolls back that stage and stops
  with evidence saved; it does not silently advance to the next frequency.

## Area scoring

`metrics.area_error(truth, recovered)` approximates each boundary by a polygon
and reports `area(truth symmetric_difference recovered) / area(truth)`, using
Shapely/GEOS clipping. §4 says “set difference” without specifying a direction;
we use the symmetric interpretation and save missing and excess area separately.
This is not an exact Wasserstein distance, nor the absolute difference of areas.

Scoring uses 4096 and 8192 vertices by default, increasing for large stored bands,
and saves the absolute change in the normalized score. That is a refinement
diagnostic, not a rigorous continuous-curve bound. Invalid polygons fail rather
than being repaired. Scoring and its optional dependency never enter the optimizer
or policy context. Existing boundary-distance diagnostics remain available.

Actual Figure 1 recovery and high-frequency resolution/robustness remain untested
by this preparation. See [SC-011](../../results/validation/shape_continuation/SC-011-paper-preparation/README.md)
for the limited checks performed.
