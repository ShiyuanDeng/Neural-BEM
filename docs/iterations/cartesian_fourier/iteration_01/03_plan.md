# Cartesian Fourier — iteration 1 plan

Agreed 2026-09-09. This opens a new project folder. It has no `01_results.md`
because no prior Cartesian-chart cycle exists; per the
[iterations convention](../../README.md) a first iteration may open directly
with its agreed plan.

Its provenance is the implicit-MLP cycle: the
[iteration-3 results](../../implicit_mlp/iteration_03/01_results.md), the
[direct Method-B Fourier guide](../../implicit_mlp/iteration_03/02_proposals/01_chatgpt_guide.md),
its [two reviews](../../implicit_mlp/iteration_03/02_proposals/02_claude_review.md),
the [gradient diagnosis](../../implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md),
and the [iteration-3 plan](../../implicit_mlp/iteration_03/03_plan.md) that this
one supersedes for the Cartesian control. The scientific question is narrower
than that plan's: this is not a diagnostic ablation of the implicit layer, it is
a parity target.

## Purpose

**Bring the Cartesian Fourier chart to the accuracy the radial Fourier chart
already reaches on the same problem, with no MLP anywhere in the optimization
loop.**

The reference is the saved radial run
`results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904`:
wrong ellipse to a five-lobed star, Kress solver, 24 angles, three-stage
frequency continuation, 44 accepted updates, train relative L2
`1.202 -> 1.068e-08`, holdout `1.133 -> 1.339e-08`, maximum boundary error
`4.181e-02 -> 2.570e-10 m`.

## The MLP is temporarily dropped

**No neural field participates in this cycle**, in the loop or as an audit.
The optimization state is a Cartesian Fourier curve from the first iteration to
the last; there is no extraction, no re-distancing, no Eikonal term, no
representation drift gate and no conversion audit. The existing
`distillation_policy="curve_only"` seam
(`solvers/sdf_inverse/neural_optimization.py:264`) already provides this, and
`pytest/sdf_inverse/test_distillation_policy.py:113,139` already assert that it
never evaluates, trains or audits the network and accepts a parameterless
placeholder in the network's place.

**This is temporary and is not a claim about the MLP.** The
[gradient diagnosis](../../implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md)
cleared both leading gradient hypotheses: the Kress shape gradient converges at
the finite-difference truncation rate with no floor at every audited state, and
the Method-B reverse agrees to better than `2e-6` outside two late paired states
where the production map is itself branch-noisy. Nothing measured so far
convicts the neural representation. Dropping it here removes a variable from a
parity experiment; it does not close the implicit-MLP cycle, whose iteration 3
remains open at its own plan. Re-attaching the network as a representation audit
over an accepted Cartesian trajectory is a later, separate step.

## The decisive measurement: parameterization, not bandwidth

A Cartesian Fourier chart is a curve `gamma(t)`, and *which* `t` decides whether
the target is reachable at all. For the exact target
`r(theta) = r0 (1 + eps cos(m theta))` with `r0 = 0.05 m`, `eps = 0.25`,
`m = 5` (`config/star_config.py:7-9`), taking `t = theta` gives the exact
identity

```text
gamma_x(theta) = r0 cos(theta) + (r0 eps / 2) [cos(6 theta) + cos(4 theta)]
gamma_y(theta) = r0 sin(theta) + (r0 eps / 2) [sin(6 theta) - sin(4 theta)]
```

so the star has **exactly three active Cartesian modes: 1, 4 and 6**. Numerical
confirmation of the truncation error of the exact target, and of the same target
resampled to arclength:

| Active band | polar-angle parameterization | arclength parameterization |
|---:|---:|---:|
| 5 | `6.250e-03 m` | `6.957e-03 m` |
| 6 | **`6.4e-17 m`** | `1.848e-03 m` |
| 16 | `6.4e-17 m` | `4.760e-04 m` |
| 32 | `6.4e-17 m` | `1.069e-04 m` |
| 48 | `6.4e-17 m` | `2.941e-05 m` |

Two decisions follow, and they are the load-bearing content of this plan.

**The active band is 6, and it is fixed before any inverse runs.** Band 5 is
short of the target by `6.25 mm`; band 6 contains it to machine precision. This
is not a tuned hyperparameter: it is the algebraic image of the reference run's
radial mode 5 under the polar-angle chart map, `K_cartesian = K_radial + 1`.

**No arclength refit appears anywhere in this cycle.** The right-hand column is
why the iteration-3 direct control priced a `43.311 um` frozen-tail floor at
B32: Method B's arclength chart is not the chart the target is band-limited in.
Removing the refit removes the floor. `DirectCartesianFourierCurveUpdate` will
report `arclength_refit_rms_m = 0.0` by construction, not by tolerance.

The initialization is comparable to the reference. Projecting the exact initial
shape (ellipse, semi-axes `0.072 / 0.038 m`, rotation `0.4 rad`,
`run_mlp_sdf_inverse_comparison.py:777-781`) into the band-6 polar-angle chart
leaves `5.163e-04 m` RMS / `8.404e-04 m` maximum, against the radial run's
recorded `7.265e-04 m` RMS / `1.196e-03 m` maximum. Both charts start about a
millimetre off-manifold; the Cartesian arm starts marginally closer. The runner
records its actual measured value at initialization rather than this estimate.

## Final decisions

| Topic | Decision |
|---|---|
| Question | Does the Cartesian Fourier chart reach the radial chart's accuracy on the same problem, with no MLP in the loop? |
| Authoritative state | `CartesianFourierCurveState` (`solvers/sdf_inverse/explicit_fourier.py:18`), incremented, never re-fitted after initialization |
| Active band | **6**, fixed by the algebraic identity above; not searched, not tuned against recovery |
| Parameterization | Polar angle at initialization; free thereafter. **No arclength refit** |
| Initialization | Polar-angle projection of the exact initial ellipse contour at band 6, with measured RMS/maximum truncation recorded |
| Neural field | **Absent.** `distillation_policy="curve_only"` with a parameterless placeholder |
| Derivatives | Central finite differences in the Cartesian coefficient basis, reusing the existing adaptive stencil |
| Optimizer | The reference run's Levenberg loop unchanged: `initial_damping 1e-3`, `curvature_penalty_weight 1e-4`, `max_stencil_shrinks 4`, `max_backtracks 6`, `max_damping_trials 5`, Armijo `1e-4` |
| Curvature prior | `k**4`, with translation (`a_0`) and mode 1 unpenalized, mirroring the radial branch's exempt `(mean radius, x, y)` block |
| Gauge | Exact phase direction projected out of every step; tangential motion **not** constrained, only measured |
| Trust region | `2 mm` maximum displacement on a dense audit, as in the reference run |
| Topology | **None.** Single fixed component; no birth, death, split or merge |
| Acquisition | Reference-matched: 24 angles, train `0.5, 1.5, 2.5 GHz`, holdout `0.25, 1.0, 2.0 GHz`, three-stage cumulative continuation |
| Output root | `results/inverse/cartesian_fourier/` |

---

# 1. Chart state

`CartesianFourierCurveState` already supplies the flatten/rebuild/validate seam
that `MultiRadialFourierState` consumes (`solvers/sdf_inverse/radial_topology.py:145-231`),
and the topology controller already promotes contours into it
(`solvers/sdf_inverse/topology_controller.py:222`). Two additions only:

- `incremented(coefficients, *, maximum_mode=None)`, mirroring
  `RadialFourierCurveState.incremented` (`solvers/sdf_inverse/curve_updates.py:237`),
  so a lower active band can move a full-band state. This is what makes stage
  continuation work.
- `active_parameter_count(K) = 4K + 2`.

At band 6 that is **26 stored coefficients, 25 active after the gauge**, against
the reference run's 11 radial parameters.

# 2. Coefficient derivatives

Three functions in `solvers/sdf_inverse/curve_updates.py`, each mirroring its
radial neighbour:

- `cartesian_fourier_displacement_basis(t, *, maximum_mode)` returning shape
  `t.shape + (4K + 2, 2)`. Exact basis identities, no solver involved, for
  `tau = 2 pi (t - t0) / P`:

```text
d gamma / d a_0 = (1, 0), (0, 1)
d gamma / d a_k = cos(k tau) * e
d gamma / d b_k = sin(k tau) * e
```

- `fit_cartesian_fourier_curve_state(curve, *, maximum_mode, center)`:
  polar-angle resample about `center`, real FFT, truncate. The projection recipe
  already exists at `solvers/sdf_inverse/topology_controller.py:214-222`; this
  reuses it with polar rather than arclength sampling, and records RMS and
  maximum truncation as the analogue of `initial_projection_radial_rms_m`. This
  is the sole allowed projection; every later state is reached by increment.
- `apply_cartesian_fourier_update(...)` returning
  `DirectCartesianFourierCurveUpdate` with the properties the trajectory writer
  already expects: `arclength_refit_rms_m` / `maximum_m` hard `0.0`, and
  `arclength_speed_ratio_before` / `after` computed honestly, since unlike the
  radial chart they now differ. Maximum-displacement audit over
  `max(validation_resolution, 64 (K + 1))` samples, as
  `apply_radial_fourier_update` does.

# 3. Optimizer branch

Additive changes in `solvers/sdf_inverse/neural_optimization.py`; the radial path
is not touched.

| Site | Change |
|---|---|
| `:370`, `:755` | accept `"cartesian_fourier"` as a third `direct_curve_retraction` |
| `:820` | third branch in `_ModalEvaluator.evaluate` calling the Cartesian retraction; stencil, caching and infeasibility handling inherited unchanged |
| `:993` | `_curvature_penalty` Cartesian ordering, exempt `a_0` and mode 1, `k**4` from `k >= 2` |
| `:1673` | initial-state branch accepting a supplied Cartesian state or fitting one |
| plumbing | add `initial_cartesian_curve_state` beside `initial_radial_curve_state` rather than generalizing the existing keyword |

Mode 1 is exempt because in the Cartesian chart it carries size and aspect,
which is the structural analogue of the radial chart's unpenalized mean radius.
Translation is `a_0`.

# 4. Phase gauge

The chart has exactly one redundant direction: shifting the parameter origin
rotates every mode pair without moving the point set. Its infinitesimal
generator in coefficients is

```text
a_k -> -k b_k,   b_k -> k a_k,   a_0 -> 0.
```

Project each step off that direction before retraction.

**Tangential motion is deliberately not constrained.** The target is band-6 in a
particular gauge, so the optimizer must be free to migrate the parameterization
toward it; projecting out tangential directions could remove the exact solution
from reach. Instead measure it: log tangential/normal energy ratio, the removed
gauge component and the speed ratio at every accepted state, and re-gauge only
if the measurement demands it. See section 9.

## 4.1 Amendment, 2026-09-09: the measurement demanded it

Execution overturned the paragraph above. Left free, the parameter drifts
immediately and compounds: the speed ratio multiplied by about `1.4` per
accepted update, running `1.92 -> 226` within fifteen updates while the
boundary error stalled near `34 mm` and the data loss kept falling. Six
accepted steps of `1.9 mm` each moved the boundary by `2.3 mm` in total, which
is the signature of a trust region spent on motion the data cannot see.

Three softer responses were measured and all failed:

| Response | Result |
|---|---|
| Cap tangential energy fraction at `0.5` | No effect; the speed ratio still reached `506`. The speed responds to the tangential displacement's *parameter derivative*, not to the displacement |
| Cap the speed ratio directly at `4.0` | Binds immediately and pins the iteration against the cap: steps collapse to zero at update 7 with the boundary error at `39.4 mm`. The drift is a property of the chart's metric, not an excursion |
| Tikhonov prior on the tangential Gram matrix | Monotone improvement with weight — `0.01 / 1 / 30` reach boundary `38.97 / 38.56 / 35.95 mm` — but even at `30` the ratio reaches `154` and the run stalls at loss `0.219` against the reference's `0.056` |

**The adopted response is to make the retraction itself gauge-fixing.** Every
retracted state is re-expressed in its own polar-angle parameter, by exact
Newton solution of `angle(gamma(t) - c) = theta` rather than interpolation, and
refitted at band `K`. This removes the null space instead of pricing it, and
the exact target is a fixed point of the map to `9.7e-17 m`.

This is **not** the arc-length refit that section 3 forbids, and the distinction
is the whole point: arc length is the parameter in which the target is *not*
band-limited, polar angle is the one in which it is. The map's band truncation
is measured and reported per accepted state as `regauge_rms_m` /
`regauge_maximum_m`.

Measured effect at matched stage-1 settings, with the tangential prior and the
speed cap both disabled so that re-gauging is the only active control:

| | free parameter | re-gauged |
|---|---|---|
| Speed ratio over 16 updates | `1.92 -> 448` | `1.92 -> 2.75` |
| Boundary error | `41.81 -> 38.97 mm`, stalled | `41.81 -> 22.55 mm`, monotone |
| Loss at update 16 | `0.385`, stalled at update 12 | `0.104`, still descending, no backtracks |
| Radial reference at update 16 | | `0.100` |

The tangential prior and the speed-ratio cap are retained in the code, default
to `0.0` and a loose `16.0`, and are not part of the adopted configuration.

# 5. Runner and outputs

`run_explicit_cartesian_fourier_inverse.py`, mirroring the reference runner's
argument surface and reporting, with the neural stages removed. Output root
`results/inverse/cartesian_fourier/`, one directory per run:

```text
results/inverse/cartesian_fourier/
  README.md
  cartesian-k6-ellipse-to-star-kress-<date>/
    metrics.json  kress_trajectory.csv  kress_responses.npz
    summary.md    stdout.log            contour_evolution.mp4
```

Trajectory columns drop `redistance_*`, `eikonal_*`, `radial_spectral_tail_*`
and `redistance_curve_drift_m` — there is no field to measure — and add
`tangential_energy_ratio`, `phase_gauge_component_removed_m`,
`maximum_normal_motion_m`, `maximum_tangential_motion_m` and the active/frozen
Cartesian spectrum.

Stage mode continuation maps the reference run's radial active mode `m` to
Cartesian band `m + 1`, preserving the staging.

# 6. Validation gates

No inverse is interpreted until all of these pass.

**Gate A — band identity.** The exact target at band 6 in the polar-angle chart
reproduces the analytic star to `< 1e-15 m`. This locks the band decision and
fails loudly if the chart convention drifts.

**Gate B — coefficient derivatives.** The analytic displacement basis agrees
with central differences of the curve under shrinking steps. No BEM solve
required.

**Gate C — gauge.** An explicit phase shift leaves the point set unchanged to
round-off, and the projector annihilates its generator.

**Gate D — acceptance and rollback.** One accepted and one rejected candidate
per run: accepted coefficients equal the solved curve, rejected trials restore
coefficients exactly.

**Gate E — no network.** Assert, in the manner of
`pytest/sdf_inverse/test_distillation_policy.py:113`, that no neural evaluation,
training or audit occurs anywhere in the run.

# 7. Primary experiment

Matched to the reference run in everything except the chart:

```text
initial shape: ellipse, semi-axes 0.072/0.038 m, rotation 0.4 rad
target:        star, mean radius 0.05 m, relative amplitude 0.25, 5 lobes
solver:        kress
acquisition:   24 angles, paired ring scan
train:         0.5, 1.5, 2.5 GHz, cumulative low-to-high continuation
holdout:       0.25, 1.0, 2.0 GHz
geometry:      bounds 0.3-0.7, 128 nodes, grid 257^2, bandwidth 48,
               validation resolution 1024
budget:        150 outer iterations, stage caps 19 / 20 / 111
motion cap:    2 mm
```

# 8. Parity criteria

Parity is claimed only if, at a saved state:

- train relative L2 `<= 1e-07` (reference `1.068e-08`);
- holdout relative L2 `<= 1e-07` (reference `1.339e-08`);
- maximum boundary error `<= 1e-08 m` (reference `2.570e-10 m`);
- no failed node-refinement or validity check.

Cost is reported beside the claim, never folded into it. The Cartesian arm has
25 active parameters against 11, so its finite-difference Jacobian costs 50
solves per iteration against 22, and more iterations are expected. A run that
reaches the accuracy gates in more iterations is parity; a run that misses any
gate is reported as partial, with the measured spectrum and gauge diagnostics.

# 9. Risks and contingencies

| Risk | Signal | Response |
|---|---|---|
| Parameterization drift: nothing pins the gauge, so sampling migrates away from polar angle and the Kress quadrature degrades before the target is reached | `arclength_speed_ratio_after` climbing past roughly 3-4, or tangential energy dominating | Add a measured, gated re-gauge step. Do **not** add an arclength refit, which reintroduces the truncation floor |
| Near-null tangential directions consume the trust region | many damping trials with small accepted motion | Report the singular spectrum; consider raising the prior floor before changing the chart |
| Mode 1 unpenalized permits large early size/aspect steps | visible in stage 1 | Fall back to `k**4` from `k >= 1` |
| Band 6 is right for this target and not generally | not a run-time signal | Record the band rule as target-algebraic, and do not generalize it to other targets without redoing the identity |

# 10. Explicitly deferred

- Any neural field, including a post-hoc representation audit of the accepted
  Cartesian trajectory;
- topology treatment of any kind — birth, death, split, merge, multi-component;
- analytic Jacobian columns through `linearize_kress_forward`, which become
  worthwhile only if finite-difference cost blocks the run;
- higher bands, other targets, other acquisitions, the paired/multistatic
  iteration-3 data, and the direct control's D-GN / D-Adam arm structure;
- replacing any production inverse with this one.

# 11. Execution sequence

```text
1. chart increment and active parameter count
2. displacement basis, polar-angle projection, update/retraction object
3. optimizer branch, curvature-prior ordering, state plumbing
4. phase-gauge generator and projection
5. runner and output writer
6. Gates A-E
7. bounded matched run
8. results, summary and evidence index under results/inverse/cartesian_fourier/
9. open iteration 2 from the measured outcome
```

Do not launch step 7 if any gate fails.

## Handoff

Executing this plan produces `iteration_02/01_results.md` in this project.
Until then this iteration is *agreed plan, execution pending*. The
implicit-MLP cycle remains open and unaffected at its
[iteration-3 plan](../../implicit_mlp/iteration_03/03_plan.md); this project
does not supersede it, and its results do not close it.
