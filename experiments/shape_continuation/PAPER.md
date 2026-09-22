# Figure 1 profiles and fidelity audit

Target: the **boundary inverse** contrast experiment in [Borges, Rachh and
Greengard, §4.1 / Figure 1](https://arxiv.org/html/2210.11607v1#S4.SS1).
The volume inverse and other figures are outside this profile. This is a
reproducible approximation with an explicit audit. **Figure 1 reproduction
remains provisional.** The [2026-09-22 Codex review](../../docs/iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
accepts the optimizer fixes and records the remaining fidelity concerns.

The manuscript used for this audit is available as a
[local PDF](../../docs/reference/papers/borges_rachh_greengard_2210.11607v1.pdf)
([source and version details](../../docs/reference/papers/README.md)). Settings
the manuscript leaves loose are taken from the authors'
[reference implementation](../../docs/reference/papers/README.md#reference-implementation),
read but not vendored at commit `bda24bddbf4562497280b671bc174ef891b47c6b`.
Rows marked **(code)** follow inspected routines or driver conventions where
they differ from the prose. The exact source/settings and plotting path used
for Figure 1 have not been identified.

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

`--profile` selects `paper` (our interpretation of §4), `driver` (inspired by
an upstream transmission example) or `scaled` (our variant using the interior
wavenumber in the driver-inspired band rule). The names are existing CLI labels;
none denotes recovered Figure 1 inputs. They differ substantially; see
[Profile settings and provenance](#profile-settings-and-provenance). For example:

```bash
$PY -m experiments.shape_continuation.paper --mode run --profile driver \
  --contrast 0.33 --k-stop 5 --max-forwards 8000 --max-seconds 3600 \
  --output /tmp/figure1-driver
```

## Profile and fidelity audit

Sizing and stopping values below describe the default `paper` profile unless
another profile is named; the full comparison appears in the next section.

| Control | Profile | Source / interpretation |
|---|---|---|
| Geometry | Existing analytic glider fixture; unit-circle initialization | §4.1 radial coefficients, §2.1 start |
| Contrast | `ki²/k² = 0.33, 10` | §4.1; do not invert this ratio |
| Frequencies | `1:0.25:30`; snapshots `1,5,10` | §4 defaults and Figure 1 snapshots; full default ladder retained |
| Acquisition | `floor(10k)` directions and receivers, radius 10 | §4; cyclic ordering starts at zero |
| Normal update band M | `floor(3 max(k,ki))` | `paper` profile takes §4 literally; `driver` follows the inspected `use_lscaled_modes` rule `floor(2 k L/2π)`; `scaled` is our variant, described below |
| Curve storage K | `max(previous K, M, ceil(70 L k / 2π))` | Exterior `k` in eq.12; extra `K>=M` for storage |
| Inverse nodes N | Even ceiling of `max(64, 70 L max(k,ki)/2π, 2(K+1))` | §2 shortest wavelength plus Kress/Fourier sampling constraint |
| Reference data | Mean 100 points/shortest wavelength, plus doubled nodes | §4 density; exact polar fixture and doubled data used here |
| Iteration / stopping | 50; residual and physical RMS update `1e-5` | §4 tolerances; RMS normalization is our convention |
| Steepest-descent step | Cauchy point `t = \|J*r\|²/\|J J*r\|²` | **(code)** eq.18 names only the direction; the raw adjoint has arbitrary magnitude |
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
- The stopping step size is our arclength-weighted RMS physical displacement.
  The reference tests `|delta|₂` over the filtered update coefficients, saved
  here as `update_norm`. The `paper` profile uses threshold `1e-5`; `driver`
  and `scaled` use `1e-3`, still against RMS. In SC-014's low-contrast driver
  arm, 6 of 17 stages stop while the coefficient norm remains above `1e-3`.
  This is an unresolved fidelity difference, not an equivalent normalization.
- The former joint GN/SD filter sweep was corrected in `49f4128`: selected
  directions are now searched independently before comparing survivors.
  `FitConfig.directions` also removes the chunk-local SD warm-up counter;
  a frequency-scoped warm-up schedule belongs in the calling strategy.
- Every completed stage must pass an added N/2N field **and full normal
  Jacobian** check (`1e-6`). Failed qualification rolls back that stage and stops
  with evidence saved; it does not silently advance to the next frequency.

## Profile settings and provenance

The upstream `tests/driver_charlie_transmission.m` is a Charlie-cavity
transmission example with different material settings, not an identified
Figure 1 glider driver. It supplies useful optimizer conventions. Our three
selectable profiles combine those conventions with explicit local choices:

| Control | `--profile paper` | `--profile driver` | `--profile scaled` |
|---|---|---|---|
| Optimizer | GN and SD compared | SD only | SD only |
| Update band M | `floor(3 max(k,ki))` | `floor(2 k L / 2π)` | `floor(2 max(k,ki) L / 2π)` |
| Inverse sizing factor in K/N formulas | 70 | 30 | 30 |
| RMS displacement tolerance | `1e-5` | `1e-3` | `1e-3` |
| Iteration cap | 50 | 100 | 100 |

**Resolution attribution correction, 2026-09-22:** upstream's local `nppw=30`
is used only for data generation. It never sets inverse `opts.nppw`, and it
initializes the inverse with 500 nodes. With no such option,
`update_inverse_iterate` leaves `rlam=Inf` and `update_geom` retains at least
the existing node count. Our factor 30 in inverse K/N sizing was therefore a
misreading, not a recovered driver setting. The saved N/2N checks pass, so this
does not by itself show our discretization is inaccurate. The numerical profile
is unchanged by this documentation correction; its resolution remains our choice.

The upstream `eps_upd=1e-3` applies to coefficient norm, unlike the RMS test
used by all three profiles. The driver-inspired optimizer, band rule and
iteration cap follow the inspected example, but the resolution and stopping
measure do not. `scaled` is an experimental rule selected after inspecting the
high-contrast comparison; it is not an author setting.

The band rules diverge sharply with contrast: on a unit circle at
`ki²/k² = 10`, k=5, `paper` asks for 47 modes and `driver` for 10. The actual
driver-inspired band changes with the recovered perimeter. The existing
comparison changes several controls together and does not isolate the band's
effect or identify the rule used in Figure 1.

## Area scoring

`metrics.area_error(truth, recovered)` approximates each boundary by a polygon
and reports `area(truth symmetric_difference recovered) / area(truth)`, using
Shapely/GEOS clipping. §4 says “set difference” without specifying a direction;
the reference drivers sum both one-sided differences, confirming the symmetric
interpretation, and we save missing and excess area separately.
This is not an exact Wasserstein distance, nor the absolute difference of areas.

**Whether Figure 1 plots this normalized quantity is unverified.** §4 defines
`εΓ = δA/A` and the figure's axis is labelled `εΓ`, while the inspected
reference drivers save raw `area(pdiff1) + area(pdiff2)`. The true area is
2.6215 for this glider. We have not recovered the Figure 1 plotting path, which
could apply normalization later. Raw-area plotting is a plausible hypothesis
and gives better low-contrast agreement in SC-014; it is not established.
Decreasing scattering residual does not guarantee decreasing shape-area error,
so comparison with the initial circle cannot settle the convention.
Comparisons report both readings.

Scoring uses 4096 and 8192 vertices by default, increasing for large stored bands,
and saves the absolute change in the normalized score. That is a refinement
diagnostic, not a rigorous continuous-curve bound. Invalid polygons fail rather
than being repaired. Scoring and its optional dependency never enter the optimizer
or policy context. Existing boundary-distance diagnostics remain available.

[SC-014](../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md)
reports partial agreement over k=1…5 at contrast 0.33 under the raw-area
hypothesis: published/ours ratios span 0.65–1.57, with median 1.04 and log10 RMS
0.117. Contrast 10 remains unmatched through k=3. Neither the full Figure 1
range nor the paper's harder cases are reproduced. The
[review](../../docs/iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
records the confirmed optimizer repairs and remaining concerns before an
adaptive baseline is frozen.
