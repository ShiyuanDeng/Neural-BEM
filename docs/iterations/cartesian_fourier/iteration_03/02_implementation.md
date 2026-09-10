# Iteration 03 implementation — topology in the Cartesian Fourier chart

The user directed on 2026-09-10 that the Cartesian Fourier chart receive
topology treatments and match the radial chart's performance on every inverse
case, with discretion over the design. This records what was built and why the
design ended where it did. The measured outcome is in [03_results.md](03_results.md).

Nothing about the radial cycle changes. `--chart radial` is the default
everywhere and takes byte-identical code paths; the whole addition is opt-in
and every prior test still passes.

## What topology demanded that iteration 1 had not

Iteration 1 established the chart and its one hard requirement: the parameter
must be gauge-fixed to polar angle after every retraction, or the optimizer
spends its trust region on reparameterization the data cannot see. Three softer
controls were measured there and all three failed. Topology adds three places
where that requirement has to hold and did not previously exist:

1. **Seeds.** A birth or a split child is a circle, and a circle is mode one
   alone in the polar-angle chart — `c_1 = (r, 0)`, `s_1 = (0, r)`. So
   `circle_cartesian_fourier_state` is exact at every bandwidth and is an exact
   fixed point of the gauge; no seed costs the gauge anything.
2. **Contour fits.** The radial chart fits a mask contour in *arc length* and
   promotes it to a Cartesian component only when no radial component can hold
   it. Arc length is the parameter in which this project's targets are not
   band-limited, so under the Cartesian chart it is not a fallback but the one
   thing to avoid; `fit_mask_component` fits polar angle directly.
3. **The multi-component optimizer.** `run_multiradial_fd_inverse` gained
   `cartesian_gauge`. A purely radial state takes the identical path at either
   setting.

## Five measurements decided the design

Each of these was a failure first. They are recorded in the order they were
found, because each one only becomes visible after the previous is fixed.

### One re-gauge is not a gauge fixing

The re-gauge map is a linear iteration whose contraction was **exactly one
half** across every probed band and perturbation. Applying one per accepted
step leaves half the excess behind and the optimizer inherits the rate: on the
matched two-circle problem the loss fell by a factor of four per iteration
where the radial chart was quadratic.

`polar_angle_gauge_fixed_point` drives the iteration to its fixed point with
vector Aitken extrapolation over the measured ratio — two or three rounds, and
machine precision for a band-limited state.

### The gauge must be mandatory, never best-effort

A first version returned the input unchanged when the projection could not
improve it. That is the failure mode, not a safe default: the Jacobian is
measured on this map, so a projection that quietly does nothing lets the next
step be taken in the free chart, which walks further off the gauge-fixed set,
which makes the projection fail again. Measured on the split case, the peanut
left the star-shaped set entirely within two accepted updates, refined to a
loss the discrete split could no longer beat, and the run ended
`topology_stationary` at one component.

Both the per-component routine and `MultiRadialFourierState.polar_angle_gauge_fixed`
now raise instead, with no skip for a component that has drifted out. The
optimizer treats that as an infeasible trial and backtracks, which always
works: the excess is second order in the step, so a halved step is projectable.

The same rule governs candidate construction. A contour fit that cannot be
gauge-fixed inside the feature tolerance is *rejected*, not accepted ungauged —
otherwise the candidate's scored loss is not the loss the optimizer starts
from. Two centres are tried, the mask's centroid and the contour's own Fourier
mean, because a cut can leave a piece single-valued about one and not the
other. On the split case's topology pass this refuses 12 contour fits — the
chart's honest cost, recorded in that pass's `rejected_masks`.

### Re-gauging near a pinch needed a different Newton

The topology controller works precisely where a neck is closing, and the
original Newton solve did not converge there. Two changes, both of which keep
the exactness claim — every parameter is still polished, only the starting
point and the stopping test changed:

- **Start from a monotone interpolation** of a dense probe of
  `angle(gamma(t))` rather than from the target angles. Near a pinch the angle
  sweeps almost the whole turn over a few percent of the parameter, and the
  naive start does not converge in any budget. A probe that is not monotone
  now reports "not single-valued" immediately instead of after a spent budget.
- **Stop on displacement, not angle.** An angular tolerance of `1e-14` is below
  what double precision in the parameter can deliver near a pinch: Newton
  stalls above it forever while the point it selects is already correct to a
  femtometre. Scaling the angular residual by the local radius measures that
  displacement directly.

Re-gauging is now exact to machine precision on a peanut with a `0.1 mm` neck.

### The gauge-fixed set is a linear subspace, and the step belongs in it

This is the change that made the two charts agree. A curve is gauge-fixed
exactly when it is `m + rho(theta) e(theta)` for a band-`K-1` radial profile
`rho` with no mode one — and that map is **linear** in `(m, rho)`. So the
gauge-fixed set is a linear subspace of the coefficient space, of dimension
`2K - 1` against the chart's `4K + 2` coefficients.

The exact phase direction that iteration 1's `project_off_phase_gauge` removes
is therefore only *one* of the `2K + 3` directions the gauge annihilates. A
step chosen in the full chart spends most of itself on the others: measured on
the band-six ellipse/star stage, 63 proposed steps were rejected as
unprojectable against the radial chart's 1, and eight accepted updates moved
the objective by 7% where the radial chart moved it by 40%.

`polar_angle_gauge_tangent_basis` builds that subspace (once per bandwidth; it
depends on nothing else), and `MultiRadialFourierState.gauge_tangent_basis`
assembles it block-diagonally, giving a radial component its own coordinates
unchanged. Under `cartesian_gauge` the optimizer then measures its finite
differences along those directions, solves the Levenberg system in them, and
clips the trust region in them. Probing raw coefficients instead was both
wasteful and wrong: a raw probe is mostly off the subspace, the retraction has
to project it back and can refuse it, and a refused probe freezes its column to
zero, which corrupts every reachable direction that coefficient contributes to.

Measuring the Jacobian in the subspace is also what closed the cost gap.
Iteration 1 reported "26 coefficients against 11 means roughly 52 forward
solves per Jacobian against 22"; those 30 extra solves were being spent on
directions the gauge annihilates. The matched two-circle regression now asserts
*equal* evaluation counts, and the eight inverse cases run at the radial
suite's cost.

### The feature radius must be the same certificate, not a better one

`component_radius_floor` is what keeps a neck resolved while the controller
prepares a discrete cut. The Cartesian branch originally used the
equivalent-area radius, which is blind to a pinch — it barely moves while a
neck closes by a factor of twenty-six — so it was replaced with a certified
bound.

The first replacement was a *tight* one: sample `|gamma - centre|` and subtract
a Lipschitz margin. That was a mistake, and an instructive one. The radial
chart's certificate is the conservative coefficient-norm bound
`rho_0 - sum_{k>=2} |rho_k|`, and `RadialFourierCurveState` refuses to exist
below it — a constraint materially stronger than "the radius is positive". The
Cartesian chart has no constructor guard to inherit, so a tighter bound let the
ellipse/star run walk its star component to a `10 um` polar radius at an
equivalent-area radius of `38 mm`, where every later probe failed and the mode
continuation could not proceed. It reached a *lower* loss than the radial chart
on the way, which is what made it a trap.

`minimum_radius_lower_bound_m` is now that same coefficient-norm certificate,
computed through the polar-angle gauge where the parameter *is* the polar
angle. The two charts agree on it to nine figures on every shape in these
suites. A contour that is not star-shaped about its own centre has no such
interpretation and keeps the area radius; that branch is reachable only under
the radial chart, whose promoted arc-length contours are exactly those shapes.

## Two structural facts the implementation rests on

**Band `K` here equals radial band `K - 1`.** A radial component of band `K` is
a gauge-fixed Cartesian component of band `K + 1` to machine precision:
`r(theta) e(theta)` raises every radial mode by one, and the radial chart's
zeroed mode one keeps the Cartesian mean exactly on the radial centre, which is
the point the gauge measures its angle about. So `chart_contour_modes` asks the
Cartesian fit for one more mode, `_promote` pads a declared radial-mode
schedule to `K + 1`, and `cartesian_component` converts a whole initial state
exactly. Without that the Cartesian chart would run a mode behind at every
stage and the comparison would not be matched.

This also answers, in the direction these measurements reach, iteration 2's
open question 3: the gauge-fixed Cartesian chart's fixed-point set is exactly
the radial chart one band lower. The two are not distinguishable by what they
can represent once the gauge is imposed. What differs is the coordinates, and
the coordinates turned out to matter — every failure above was a coordinate
failure, not a representation failure.

**A trust region is a statement about coordinates.** The last case to come
right was ellipse/star, and what fixed it was expressing the step bound in the
subspace rather than per coefficient. A radial mode-`m` amplitude appears in
this chart as two coefficient pairs of *half* that amplitude, so a per-
coefficient bound of the radial value is twice as loose in the only units that
matter. Halving the Cartesian shape bound and clipping in the subspace
reproduces the radial trust region exactly — translations `0.025`, radius
`0.012 * sqrt(2)` for the normalized profile direction, shape modes `0.006` —
and the eight-stage ellipse/star continuation then agrees with the radial run
to five significant figures at every stage.

## Interfaces

| Entry point | Change |
|---|---|
| `run_fourier_topology_controller.py` | `--chart {radial,cartesian}`; output defaults under `results/inverse/cartesian_fourier/topology_controller/` |
| `run_radial_fourier_topology_challenges.py` | same `--chart` flag; `_promote`, seeds, sampling and metrics are chart-generic |
| `TopologyControllerConfig` | `chart` field, validated |
| `run_multiradial_fd_inverse` | `cartesian_gauge` keyword; `MultiRadialFDIteration.gauge_truncation_maximum_m` |
| `evaluate_birth_ladder` | `chart` keyword, which selects only which exact circle the newborn is |
| `CartesianFourierCurveState` | `minimum_radius_lower_bound_m`, `is_star_shaped_about_center`, `polar_offsets`; `mean_radius_m` is now the exact Fourier area |

Regressions are in `pytest/sdf_inverse/test_cartesian_fourier_topology.py`.
The chart's own gates stay in `test_cartesian_fourier_chart.py`.
