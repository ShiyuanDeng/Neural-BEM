# Claude review of the direct Method-B Fourier proposal

Recorded 2026-09-08 by Claude, after the
[ChatGPT guide](01_chatgpt_guide.md) and the
[iteration-3 results](../01_results.md). This is a review, not a plan and not
authorization. It records agreements, corrections and open questions; the
decisions belong in `03_plan.md`.

The guide's core instinct is right and the iteration should act on it: the
existing radial control confounds two factors, and a curve-owned control in the
*same* Method-B Cartesian chart is the clean way to separate them. Its analytic
pullback is correct, its work limits are sensible, and its refusal to read
`exit 0` as recovery matches the discipline of the previous two cycles.

Three things in the design do not survive contact with the code and the saved
run, and one of them changes what the experiment can conclude. Four read-only
probes over the saved trajectories settle the numbers; they are indexed at the
end, and every value is stated inline.

## The control is matched to the failure and not to the success

**This is the substantive objection.** Section 2 says the experiment "changes
only the first factor", geometry ownership. That is true relative to the
implicit failure. It is not true relative to the radial success, and the
conclusion in section 10.1 is stated against the radial success.

The working radial inverse is not Adam with backtracking. It is
Levenberg-damped Gauss-Newton on an explicit modal Jacobian
(`solvers/sdf_inverse/neural_optimization.py:1875`, damping at `:1055`) with a
`k**4` curvature Tikhonov prior (`_curvature_penalty`, `:982`) at weight
`1.0e-4`, on a chart the code calls gauge-fixed
(`solvers/sdf_inverse/curve_updates.py:276`). The recorded configurations
confirm all of it: every radial policy in
`results/inverse/radial_fourier/representation_policies/saved-star-20260905/metrics.json`
carries `direct_curve_retraction: radial_fourier`,
`curvature_penalty_weight: 0.0001` and `maximum_mode: 5`, which is
**11 real parameters**.

Section 5.4 proposes instead Adam, no prior, and 386 real parameters. Against
the radial success that changes the chart, the optimizer, the prior and the
dimension by a factor of 35. So a negative result would not carry the meaning
section 10.3 assigns it: "the direct Cartesian control also collapsed" would be
fully explained by the optimizer, and would say nothing about the objective,
the acquisition or identifiability. The design as written can support the
weaker claim in 10.2 and cannot support 10.1.

**Correction.** Declare two direct arms and name what each isolates:

| Arm | Chart | Optimizer | Isolates |
|---|---|---|---|
| D-Adam | Cartesian Fourier, active band | Adam + backtracking, no prior, as section 5.4 | Ownership, against the implicit failure |
| D-GN | Cartesian Fourier, same band | Levenberg GN + `k**4` prior at `1.0e-4`, as the radial runs | Chart, against the radial success |

Together those bracket the gap. Neither alone does. D-GN is affordable only at a
low active band, which is the same conclusion the next two sections reach from
different directions, so the three constraints agree rather than compete.

## At bandwidth 96 the chart constrains nothing

Section 8.1 is right that 386 coefficients against 256 real residual components
is not an identifiability certificate. The situation is worse than that, and
the guide's staging depends on the difference.

`solvers/sdf_inverse/geometry.py:158` requires `num_nodes >= 2 * bandwidth + 2`,
and production sits exactly at the minimum: `bandwidth 96`, `num_nodes 194`.
The 194 nodes carry `388` real degrees of freedom; the bandwidth-96 constraint
removes exactly the Nyquist bin, two of them. **386 of 388.** Measured on the
saved contours, the Nyquist bin is `9.6e-18 m` initially and `4.4e-17 m` at E1's
final state — the constraint is exactly one mode, and nothing else.

So "optimize the full-B96 Cartesian coefficients" is, to within two degrees of
freedom, "move the 194 solver nodes freely". The Fourier chart supplies no
smoothness, no bandlimiting and no regularization at the production setting.
Section 8.1.A calls this arm the matched one and 8.1.B the fallback. That is
backwards: full-B96 is the *more permissive* arm, with access to boundary
detail the neural pipeline could only reach through extraction, projection and
a conversion gate, and the solver grid cannot resolve products of a mode-96
curve with the kernel. The node-refinement check of section 7.4 is the right
instrument for that risk and should run at the end of the short probe as well as
at the start.

## The Cartesian chart carries a gauge the radial chart does not

Not mentioned in the guide, and it interacts with the trust region.

A shift of the parameter origin rotates each mode pair by `k * s` and changes
the point set not at all. The shape functional is therefore exactly flat along
it, and approximately flat along every tangential direction, so roughly half of
the 386 coefficients are near-null for shape. Measured on the shared initial
curve, whose perimeter is `410.325 mm` and whose speed ratio is `1.002066`:

| Parameter shift | Fixed-parameter max displacement | Geometric change |
|---:|---:|---|
| `0.001 rad` | `0.0654 mm` | none |
| `0.010 rad` | `0.6537 mm` | none |
| `0.0333 rad` | `2.1778 mm` | none |

The middle column is the quantity the production motion cap measures, and the
quantity section 5.4 nominates as "the invariant step-scale control". A pure
gauge move saturates the entire `2 mm` cap while changing no geometry at all.

Adam makes this worse rather than better. Its per-coordinate normalization gives
a direction with a tiny gradient the same step as a well-determined one, so the
near-null gauge directions are exactly the ones it will drift along — consuming
the trust region, degrading the speed ratio that section 6 asks to monitor, and
making "physical boundary motion per accepted step" not a measure of shape
change.

**Correction.** Measure the trust region on the normal component,
`max |<d gamma(t), n(t)>|`, and report the tangential and normal split of every
accepted step as a first-class diagnostic. Do this on a dense grid, the way
`apply_radial_fourier_update` already does at
`max(validation_resolution, 64 * (K + 1))` (`curve_updates.py:588`), not at the
194 nodes.

The same argument cuts the other way and is worth recording: once the gauge is
removed, the effective shape dimension is about `2B + 1 = 193`, not 386, against
`256` real residual components. The naive count in section 8.1 is therefore not
evidence of underdetermination. The real question is the decay of the
shape-to-data singular spectrum, not the parameter count.

## Section 8.1.B measures a quantity the design does not use

The rule as written is "the smallest band whose frozen-tail removal/change is
below a strict curve-approximation budget on the initial Method-B boundary".
But the design does not remove the tail — it freezes it and carries it. A
truncation-error budget prices an approximation the experiment never makes.

Priced anyway, on the shared initial curve:

| Active band `B_a` | Active real coefficients | Largest frozen-tail displacement |
|---:|---:|---:|
| `8` | `34` | `947.909 um` |
| `16` | `66` | `491.833 um` |
| `32` | `130` | `146.862 um` |
| `40` | `162` | `55.661 um` |
| `48` | `194` | `25.114 um` |
| `64` | `258` | `8.463 um` |

A "strict" budget therefore forces `B_a` of 48 to 64, which is `194` to `258`
active real coefficients — at or above the `256` real residual dimension. The
rule defeats its own purpose.

**Correction.** The repository already owns a predeclared, target-free band rule
and the radial control already uses it: `resolvable_maximum_mode`
(`neural_optimization.py:953`, the `ka + (ka)**(1/3)` localization capped at 12)
intersected with the angular Nyquist limit `(sources - 1) // 2`
(`run_mlp_sdf_inverse_comparison.py:862`). Reuse it rather than inventing a
second rule.

It also lands in the right place. The star's Cartesian signature is modes 4 and
6, not mode 5 — a polar lobe multiplied by `(cos t, sin t)` splits — and the
measured initial spectrum shows exactly that: after mode 1 at `85.3857 mm`, the
largest modes are `k=4` at `5.8369 mm` and `k=6` at `4.1023 mm`. A band of
`B_a = 6` to `8` is `26` to `34` real coefficients, the Cartesian analogue of the
radial chart's 11, and it makes D-GN affordable: the existing FD modal Jacobian
(`_modal_jacobian`, `neural_optimization.py:893`) costs one forward solve per
active parameter per outer iteration, so `34` is the same order as the radial
control's `11`. Section 4 is right to reject coefficient finite differences at
`B = 96` and should not be read as rejecting them at `B_a = 8`.

**The trade-off must be declared, not resolved.** You cannot simultaneously
start from the exact production Method-B curve, restrict to an identifiable
band, and carry no frozen detail. At `B_a = 8` the frozen tail is `947.909 um`
of boundary detail the arm can never correct. Record it as the control's error
floor; against E1's final raw symmetric RMS of `9.506 mm` it is not
disqualifying, and it is honest.

## The direct forward seam checks less than the radial path

Section 6 says the topology gates "cease to exist because the direct Fourier
curve is itself the authoritative geometry". Authoritative is not the same as
simple. A Cartesian Fourier curve can self-intersect, and
`_curve_geometry_build` (`solvers/sdf_inverse/forward.py:432`) checks bounds and
`sampled_self_intersection_count` **at the 194 nodes only** (`:461`). At
`B = 96` with `N = 194` that polygon is critically sampled — exactly the
resolution sensitivity the guide criticizes in the marching-grid check it
replaces.

The radial path does not accept this. `radial_fourier_state_curve` calls
`validate_periodic_parameterization` at `validation_resolution = 1024` with an
aliasing-aware bandwidth (`curve_updates.py:484`) and falls back to the node
polygon only when `full_validation=False` (`:517`). Route direct candidate
acceptance through the same full validation. The gates are then genuinely
removed by construction rather than silently coarsened, which is what section 6
claims and deserves to be true.

## What both neural arms already did to the high modes

A measured finding the results document does not report, and a prediction for
the direct arm. Largest Cartesian amplitude above a given mode:

| Above mode | Shared initial | E0 final | E1 final |
|---:|---:|---:|---:|
| `6` | `0.527356 mm` | `4.612165 mm` | `1.198093 mm` |
| `32` | `0.041734 mm` | `0.185574 mm` | `0.069657 mm` |
| `80` | `0.000286 mm` | `0.023057 mm` | `0.005113 mm` |

Both arms roughen the boundary, and paired roughens it about four times harder
than multistatic at every band. E0's final spectrum is flat and structureless
across modes 2 to 8 — `12.5231`, `9.0439`, `7.6968`, `6.2158`, `5.6194`,
`4.6122`, `3.3514 mm` — which is the quantitative form of the distorted contour
and sits directly upstream of its terminal two-component detections. E1 keeps
the lobe signature but collapsed: `k=4` falls from `5.8369` to `2.8768 mm` and
`k=6` from `4.1023` to `1.8862 mm`, consistent with the separately reported
polar mode-5 fall from `7.181` to `1.530 mm`.

The prediction: high-mode roughening under a falling data objective is already
the observed failure, and full-B96 D-Adam removes every mechanism that was
restraining it — the Eikonal term, the extraction and projection smoothing, and
the conversion gate — while adding none. If it is run first and unregularized,
the most likely outcome is a faster version of E0, and section 10.3 would then
retire the MLP hypothesis on evidence that does not support retiring it.

## What the repository already provides

These are agreements, with the exact seams, so the implementation estimate in
section 5 can be trusted or corrected.

**Section 4's pullback is correct as written.** `fourier_curve`
(`solvers/ordered_boundary/analytic.py:166`) uses exactly
`tau = (2*pi/P)(t - t0)` and forms the first derivative with the
`angular_scale * modes` factor, so all four identities hold verbatim, including
the signs. `KressGeometryPullback` returns `points` and `first_derivatives`
covectors with a `contract` method and documents that they must be composed with
a coherent curve construction — which is precisely this contraction. The seam to
copy is `implicit_adjoint.py:217-227`: keep
`build_paired_objective_adjoint` / `build_indexed_objective_adjoint` and
`build_kress_geometry_pullback`, and replace `build_method_b_pullback` with the
analytic basis contraction.

**Section 3.1's fallback branch can be deleted.** The retained `FourierBoundary`
already exists: `MethodResult.representation` is the final arc-length refit
representation (`method_b.py:157`). It is discarded one frame later, at
`geometry.py:382`, where the build keeps only the discretized curve.
`OrderedSDFGeometryBuild` (`geometry.py:205`) is a frozen dataclass whose
trailing fields already carry defaults, so an optional
`representation: FourierBoundary | None = None` is additive and breaks no
existing construction. No refit, and no reconstruction tolerance to prove.

**Section 5.2's forward seam exists.**
`predict_indexed_curve_response(..., retain_kress_state=True)`
(`forward.py:692`) never evaluates an SDF, runs marching squares or fits Method
B, and its docstring says so. One gap: `predict_paired_curve_response`
(`forward.py:618`) does not accept `retain_kress_state`, so section 8.2's paired
arm cannot build an adjoint without a one-line addition.

**Section 5.1 is nearly free.** `FourierBoundary` (`representations.py:238`) is
already a frozen dataclass with `with_coefficients`, `to_parameterization`,
`bandwidth` and `mode_amplitudes`. Only flatten/unflatten, `with_increment` and
the active/frozen mask are new. Section 5.1's instruction not to introduce a
second equivalent Fourier class should be kept.

**Section 9's warning is already enforced.** `_curve_geometry_build` zeroes the
three SDF residual fields and states in its docstring that they must not be read
as an audit of an MLP.

**One addition to section 7.2.** The analytic gradient is worth more as an
independent check on the existing FD modal Jacobian than as the production
optimizer: `jacobian.T @ base.residual` (`neural_optimization.py:1874`) should
equal it at the same state. The radial Gauss-Newton path has no analytic
gradient cross-check today, and this proposal makes one available for free.

## Suggested ordering

| Order | Work | Approximate cost | What it decides |
|---|---|---|---|
| 1 | Retain `FourierBoundary` on `OrderedSDFGeometryBuild`; capture `c_0` from the saved neural state 0 | minutes | Closes section 3.1 exactly, with no refit |
| 2 | Analytic coefficient pullback plus section 7.2 directional validation, and the cross-check against `jacobian.T @ residual` | hours | Whether the gradient is right, and validates the radial GN Jacobian as a by-product |
| 3 | Predeclare the active band from `resolvable_maximum_mode` and the angular Nyquist limit; record the frozen-tail floor | minutes, no BEM | Fixes the dimension before any run, by an existing rule |
| 4 | Normal/tangential step split and dense-grid motion cap; full-validation candidate acceptance | hours | Whether the trust region and the simplicity check measure what they claim |
| 5 | Short D-GN arm at the declared band, matched to the radial optimizer and prior | as scoped | Whether the Cartesian chart recovers where the radial chart did |
| 6 | Short D-Adam arm at the same band, matched to the implicit optimizer | as scoped | Whether ownership alone changes the descent, with the optimizer held fixed |
| 7 | Full-B96 D-Adam probe, if 5 and 6 leave the dimension question open | as scoped | What free high modes do, read as a permissive arm and not as the matched one |

The disagreement is about which arm is the control and how the step is measured,
not about the method. The guide's discipline should be kept in full: one
declared factor per comparison, no tuning against the target or the 3 GHz
evaluation, no relaxation of the neural gates in the arms that still have them,
and no promotion of a successful short control into a production inverse. One
rule is worth adding — do not run an arm whose optimizer differs from both
reference runs, because neither its success nor its failure can be attributed.

## Measurements made for this review

Four read-only probes over the long run's saved geometry trajectories, with the
script, full-precision output and their caveats at
[`results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics/`](../../../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics/README.md):
the Cartesian mode spectrum at the shared initial and both final states, the
Nyquist-bin exactness check, the frozen-tail displacement against active band,
and the reparameterization gauge cost. No model was loaded, no inverse, BEM
solve, extraction, conversion or gradient evaluation was run, and no saved
artifact was modified. The radial optimizer settings are read from recorded
`metrics.json` configurations, not inferred from defaults.

Their caveats travel with the numbers. These are **Cartesian vector
coefficients in the curve's native arc-length refit parameter** — not the polar
spectra of `01_results.md` and not the arc-length normal modes of the optimizer
review. `mode 5` here and `mode-5 amplitude` there are different quantities
about different objects, and a polar mode-5 star appears here as modes 4 and 6.
The recovery is exact rather than approximate only because `num_nodes` is
exactly `2 * bandwidth + 2`; the reported Nyquist bin is the check, not a
physical quantity. Two independent consistency checks against the results
document hold: mode 0 is `707.598 mm`, the distance from the origin to the
`(0.5, 0.5) m` centre of the configured bounds, and mode 1 over `sqrt(2)` is
`60.377 mm` initially and `50.235 mm` at E1's final state against separately
reported mean polar radii of `60.002` and `50.145 mm`.

The gauge probe is exact in coefficient space and its "geometric change" column
is zero by construction, not by measurement. The frozen-tail table prices the
initial curve only; the same table at a later state would differ, and the
high-mode growth measured above says it would be larger. Nothing here evaluates
the direct control itself — no Cartesian coefficient gradient has been computed,
and the claim that D-GN is affordable at `B_a = 8` is an arithmetic estimate
from the existing Jacobian's cost model, not a timing.
