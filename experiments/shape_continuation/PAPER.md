# Figure 1 preparation

Target: the **boundary inverse** contrast experiment in [Borges, Rachh and
Greengard, §4.1 / Figure 1](https://arxiv.org/html/2210.11607v1#S4.SS1).
The volume inverse and other figures are outside this profile. This is a
reproducible approximation with an explicit audit, not an exact replication.

The manuscript used for this audit is available as a
[local PDF](../../docs/reference/papers/borges_rachh_greengard_2210.11607v1.pdf)
([source and version details](../../docs/reference/papers/README.md)). Settings
the manuscript leaves loose are taken from the authors'
[reference implementation](../../docs/reference/papers/README.md#reference-implementation),
read but not vendored. Rows below marked **(code)** follow that implementation
where it contradicts the prose; the code is what produced the published figures.

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

`--mode run` is the campaign entry point. It requires explicit
`--max-forwards` and `--max-seconds`; the budget covers both contrasts unless
`--contrast 0.33` or `--contrast 10` selects one. `--k-stop` selects an endpoint
on the fixed grid. No large run is performed by the default command. These runs
start from the unit circle; checkpoint resume is not implemented in this harness.

`--profile` selects which reading of the settings to run — `paper` (§4's
prose), `driver` (the authors' transmission driver) or `scaled` (the driver with
the interior wavenumber restored in its band rule). They differ substantially;
see [Two readings of the settings](#two-readings-of-the-settings). For example:

```bash
$PY -m experiments.shape_continuation.paper --mode run --profile driver \
  --contrast 0.33 --k-stop 5 --max-forwards 8000 --max-seconds 3600 \
  --output /tmp/figure1-driver
```

## Profile and fidelity audit

| Control | Profile | Source / interpretation |
|---|---|---|
| Geometry | Existing analytic glider fixture; unit-circle initialization | §4.1 radial coefficients, §2.1 start |
| Contrast | `ki²/k² = 0.33, 10` | §4.1; do not invert this ratio |
| Frequencies | `1:0.25:30`; snapshots `1,5,10` | §4 defaults and Figure 1 snapshots; full default ladder retained |
| Acquisition | `floor(10k)` directions and receivers, radius 10 | §4; cyclic ordering starts at zero |
| Normal update band M | `floor(3 max(k,ki))` | §4 experimental rule, taken literally; the reference drivers instead set `use_lscaled_modes`, giving `floor(k·cL/2π)`, which for this glider (`L/2π = 1.137`) would be about 14% wider |
| Curve storage K | `max(previous K, M, ceil(70 L k / 2π))` | Exterior `k` in eq.12; extra `K>=M` for storage |
| Inverse nodes N | Even ceiling of `max(64, 70 L max(k,ki)/2π, 2(K+1))` | §2 shortest wavelength plus Kress/Fourier sampling constraint |
| Reference data | Mean 100 points/shortest wavelength, plus doubled nodes | §4 density; exact polar fixture and doubled data used here |
| Iteration / stopping | 50; residual and physical RMS update `1e-5` | §4 tolerances; RMS normalization is our convention |
| Steepest-descent step | Cauchy point `t = |J*r|²/|J J*r|²` | **(code)** eq.18 names only the direction; the raw adjoint has arbitrary magnitude |
| Gaussian filter | Harmonic `n` of `h` damped by `exp(-(n/M)²/sigma)`, `sigma=10^(1-level)`, 10 levels | **(code)** `update_inverse_iterate`; eq.19 instead writes the stored-curve band and `sigma²` |
| Added halvings | Disabled (`backtracks=0`) | `filter_type='gauss-conv'`, not `'step_length'` |
| Curvature band / tail | `max(20, M)` / energy `0.01` | **(code)** `n_curv = max(n_curv_min, M)` with driver `n_curv_min=20`; `eps_curv=0.1` bounds an amplitude ratio, so our energy fraction is its square |
| Direction offered | `FitConfig.directions`, the reference's `optim_type` | `paper` profile compares both ('min(gn,sd)'); `driver` profile uses steepest descent alone, which is what the transmission driver runs |
| Filter search order | Each direction filtered to admissibility independently, then survivors compared | **(code)** the reference's two loops; a joint sweep stopping at the first success skips a better candidate on the first contrast-10 update |

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
  sum of per-illumination norms, but the reference code also uses the stacked
  norm. Requiring the residual to decrease is likewise the reference behaviour,
  not a safeguard we added: its filter loop exits only on a non-increasing
  residual and reverts the step otherwise. Gradient stopping, projection
  tolerance `1e-7`, and SVD cutoff `1e-10` remain ours.
- `epsilon_f` is `eps_curv = 0.1` in the reference drivers, applied to
  `|tail|₂/|all|₂` of the arclength curvature spectrum. Successive filters do
  not compose there: each level re-filters the original update.
- The stopping step size is our arclength-weighted RMS physical displacement,
  not the reference's `|delta|₂` over the filtered update coefficients; both are
  compared against `1e-5`. The exact quantity is saved as `update_norm` on every
  trial, so the difference is measurable rather than assumed. The drivers
  loosen this to `1e-3`, which we do not adopt.
- GN and SD are filtered together here: the search takes the first level at
  which either is admissible and decreasing. The reference filters each
  direction to admissibility independently, then compares. This matters only
  when the two need different filter strengths.
- Every completed stage must pass an added N/2N field **and full normal
  Jacobian** check (`1e-6`). Failed qualification rolls back that stage and stops
  with evidence saved; it does not silently advance to the next frequency.

## Two readings of the settings

§4's prose and the authors' transmission driver
(`tests/driver_charlie_transmission.m`, the penetrable configuration that
matches Figure 1) disagree on every control that affects accuracy. Both are
selectable, and neither is a recovered Figure 1 input:

| Control | `--profile paper` (§4 prose) | `--profile driver` |
|---|---|---|
| Optimizer | Gauss-Newton and steepest descent compared | steepest descent alone (`optim_type='sd'`) |
| Update band M | `floor(3 max(k,ki))` | `floor(2 k L / 2π)` from the current perimeter, no `ki` |
| Inverse points/wavelength | 70 (§2 "in all our examples") | 30 (`nppw`) |
| Update tolerance | `1e-5` (§4) | `1e-3` (`eps_upd`) |
| Iteration cap | 50 (§4) | 100 (`maxit`) |

The band rules diverge sharply with contrast: at `ki²/k² = 10`, k=5 the prose
rule asks for 47 update modes and the driver rule for 10. The driver profile is
therefore the far more conservative reading.

## Area scoring

`metrics.area_error(truth, recovered)` approximates each boundary by a polygon
and reports `area(truth symmetric_difference recovered) / area(truth)`, using
Shapely/GEOS clipping. §4 says “set difference” without specifying a direction;
the reference drivers sum both one-sided differences, confirming the symmetric
interpretation, and we save missing and excess area separately.
This is not an exact Wasserstein distance, nor the absolute difference of areas.

**Whether Figure 1 plots this normalized quantity is unverified.** §4 defines
`εΓ = δA/A` and the figure's axis is labelled `εΓ`, but every driver in the
reference repository computes the raw `area(pdiff1) + area(pdiff2)` and nothing
there ever divides by the true area (2.6215 for this glider). The raw reading is
the more likely one on physical grounds: under the normalized reading the
published k=1 point, 0.781, is worse than the unit circle the run starts from
(0.361), after a stage that runs to its iteration cap under an enforced residual
decrease. Comparisons against Figure 1 report both readings.

Scoring uses 4096 and 8192 vertices by default, increasing for large stored bands,
and saves the absolute change in the normalized score. That is a refinement
diagnostic, not a rigorous continuous-curve bound. Invalid polygons fail rather
than being repaired. Scoring and its optional dependency never enter the optimizer
or policy context. Existing boundary-distance diagnostics remain available.

Actual Figure 1 recovery and high-frequency resolution/robustness remain untested
by this preparation. See [SC-011](../../results/validation/shape_continuation/SC-011-paper-preparation/README.md)
for the limited checks performed.
