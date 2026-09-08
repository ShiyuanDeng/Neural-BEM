# Additional review comments

Recorded 2026-09-08 by Claude, after the [ChatGPT guide](01_chatgpt_guide.md)
and the [Codex companion review](02_codex_review.md). Preserved as a dated
discussion; the iteration plan records the conclusions after testing.

A third pass over the same two documents, the September 8 bundles and the
current implementation. These comments follow the guide's order and add to the
Codex review rather than restating it. Six read-only probes were run over the
saved artifacts to settle questions both documents leave open — no inverse, no
weight change, no modified result. They are indexed at the end, and every
number below is stated inline.

## On runtime: the cost is one polygon test, not BEM

**Section 14 is right that BEM should not be assumed dominant, and it is
mis-ranked as a parallel task.** Measured on the star's final saved state, in
the same single-thread environment the suite recorded: one geometry build takes
`13.50 s` and the Kress solve for 12 pairs at both training frequencies takes
`0.195 s`. Geometry is `98.6%` of a candidate evaluation; the run's recorded
average of `12.57 s` is slightly lower because 204 of its 420 evaluations
aborted inside geometry construction. For the circle the same pair is `5.42 s`
and `0.0157 s`, and the measured build equals that run's recorded `5.42 s` per
evaluation exactly.

Inside the build, one function dominates:
`polygon_self_intersection_count` (`solvers/sdf_to_ordered_boundary/frontend.py:513`)
is `81.6%` of the profiled star build and `88.4%` of the circle build, almost
all of it inside the conversion-fidelity audit
(`solvers/sdf_inverse/geometry.py:432`, `85.7%` and `94.7%`). It is an exact
`O(n^2)` Python double loop: one star build spends it across `5,458,368` calls
to `_segments_intersect` and `21,833,472` to `_cross`, over the 15 polygon
checks in one build. Against this, the discrete adjoint the project studies costs
`74.37 s` of the star's `5,353.74 s` and `13.85 s` of the circle's `2,306.50 s`
— about `1%` of each run.

So roughly 1.75 of the suite's 2.13 recorded hours are inside one pure-Python
loop. Vectorizing it, with acceptance by exact integer equality on saved
polygons, changes no accepted result, touches no fidelity limit, and makes
every experiment in both documents five to eight times cheaper. It belongs
first, not in a parallel engineering lane. The guide's `3-5` accepted-update
caps and Codex's wall-clock cap exist mainly because of this constant.

**One profiling question is closed already.** I checked whether testing the
`2 mm` motion cap before the BEM solve would help: `161` of the star's `215`
solved trials and `96` of the circle's `418` are rejected on motion alone,
after paying for a solve they did not need. At `0.195 s` and `0.0157 s` per
solve that is about `31 s` of `5,354 s` and `2 s` of `2,307 s`. Not worth
doing; record it as answered rather than leaving it in the profiling list.

## On Priority C: the regularizer is absent where it matters

**The guide asks whether to ablate the Eikonal term. The measurement says the
question is the opposite one.** `solvers/sdf_inverse/implicit_adjoint.py:252`
draws `512` samples once, uniformly over the whole `0.4 x 0.4 m` box, and fixes
them for the run. Of those `512`, **none** lie within `1 mm` of the star's
final contour, `2` within `2 mm` and `10` within `5 mm`; the nearest is
`1.63 mm` from a contour of `455.5 mm` perimeter. The circle's counts are
`3`, `6` and `9`. The penalty constrains `|grad f|` in the bulk of the box and
effectively nowhere on the zero level set that extraction, projection, Method B
and the motion map all depend on.

The consequence is measured on the contour itself, with the same quantity the
driver already gates (`run_sdf_inverse_comparison.py:1302`, evaluated on the
converted nodes):

| Star state | 0 | 8 | 16 | 24 | 32 | 40 | 47 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Field-gradient norm range | 0.820–1.228 | 0.823–1.300 | 0.797–1.691 | 0.738–2.127 | 0.698–2.828 | 0.496–3.376 | 0.347–3.515 |
| ratio | 1.50 | 1.58 | 2.12 | 2.88 | 4.05 | 6.80 | **10.14** |

The circle drifts the same way, more mildly: `1.02` at state 0 to `1.87` at
state 60. The warm-start gate requires a maximum unit-gradient deviation of
`<= 0.25` and is evaluated only at initialization
(`run_sdf_inverse_comparison.py:1606`); the star ends at `2.515`, ten times what
its start had to satisfy. The comment beside that gate already says nothing
re-imposes the constraint. What is new is that the drift is large and
monotone across the sampled states, that the sampled Eikonal loss rises with
iteration at Spearman `0.996`, and that both sit upstream of three separate
symptoms below.

An inverse-Eikonal ablation is therefore the wrong experiment to promote.
Test the sampling instead — and note the bookkeeping before anyone does. The
fixed sample set is what makes objectives comparable across iterations.
Resampling per iteration stays valid inside a line search only if the accepted
state's penalty is re-evaluated at the top of each iteration, which is cheap
and needs no BEM, and it forfeits the cross-iteration objective comparison. Any
such change alters the objective and must be the declared single factor of
whatever comparison it appears in.

## On Priority A: report the numerator and the denominator separately

**The proposed quantity is right, and as one number it will mislead.** In
`V_n = -(df/dtheta . delta_theta) / ||grad f||` the denominator spans a factor
of `10.14` along the star's final contour. The spectrum of `V_n` is therefore
the numerator's spectrum modulated pointwise by `1/||grad f||(s)`, and
pointwise modulation is convolution in mode space: it moves energy up in mode
number on its own. Report the numerator spectrum, the profile `1/||grad f||(s)`
and its own spectrum, and the quotient. Without that split, "the neural update
injects high modes" and "the field lost its unit gradient" are indistinguishable
and imply different fixes.

The same measurement bears on the trust region. The `2 mm` cap is a maximum
over the converted curve (`solvers/sdf_inverse/implicit_adjoint.py:423-426`),
so the contour point with the smallest `|grad f|` sets the accepted step for
the entire boundary, and that point's `|grad f|` falls from `0.820` to `0.347`
over the run.

## On what the star's error actually is

**The lobes do not shrink toward a circle; they move into the wrong modes, and
the five-parameter summary cannot show it.** Rebuilding the saved states from
the trajectory weights and decomposing the polar radius about the polygon
centroid (amplitudes in mm):

| Star state | m=3 | m=4 | m=5 | m=7 | radial RMS | perimeter | m<=10 | m=11–20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.061 | 0.091 | **7.166** | 0.098 | 5.077 | 410.2 | 99.7% | 0.1% |
| 16 | 3.461 | 1.993 | 3.310 | 0.904 | 4.282 | 422.7 | 98.6% | 1.3% |
| 32 | 5.864 | 4.725 | 0.674 | 3.262 | 6.250 | 437.3 | 97.6% | 2.3% |
| 47 | **6.232** | **5.827** | 1.648 | **4.951** | 7.676 | 455.5 | 95.9% | 3.6% |

The target's `m=5` amplitude is `12.5 mm`. The run takes `m=5` from `7.17` to
`0.67 mm` while `m=3`, `m=4` and `m=7` grow from about `0.1 mm` to `6.23`,
`5.83` and `4.95 mm`, and the perimeter grows `11%`. The fitted amplitude
`0.11966 -> 0.02072` that both documents reason about is the `m=5` projection
alone, which is `2.3%` of the final radial variance: the five-parameter fit is
blind to where the error went. Reports should carry the modal decomposition
beside the fitted star, or the next summary will again describe a collapse that
is really a transfer.

This also gives the guide's decision-table row on modes above 10 a provisional
answer for the states: no. Modes `11–20` hold `3.6%` of the star's final radial
variance and modes above 20 hold `0.5%`. The error sits in `m = 3, 4, 6, 7, 9`
— inside the range iteration 1 measured as full-rank observable. Extending the
update analysis to `m <= 20` is cheap and worth keeping, but the leading
hypothesis should not be that the neural update escapes into unobserved modes.
The circle agrees: its final radial RMS is `0.386 mm` with `m=4` at `0.322`,
`m=5` at `0.259` and `m=8` at `0.221`, and `96.8%` below `m=11`.

## On the landscape: there is no barrier along the direct path

**Both documents keep "nonlinear basin" open as an alternative; it can be
tested for about eight seconds of compute, and I ran it.** Blending node sets
between a saved contour and the Method-B discretization of the exact target
(which lies within `2.09e-6 m` of the saved exact boundary), solving Kress on
each blend at the two training frequencies and evaluating the production
objective:

| alpha | 0.00 | 0.15 | 0.25 | 0.50 | 0.75 | 0.90 | 1.00 |
|---|---:|---:|---:|---:|---:|---:|---:|
| from final star | 0.235146 | 0.225734 | 0.225902 | 0.185616 | 0.071648 | 0.013373 | 0.000000 |
| from initial star | 1.451200 | 1.387786 | 1.300661 | 0.858621 | 0.271891 | 0.045799 | 0.000000 |

At `alpha = 0` this reproduces the recorded final training loss `0.235146` and
relative L2 `0.482413` exactly, so the setup is the production objective. From
the initial star the descent to the truth is strictly monotone; from the final
star it is monotone apart from a `0.13%` rise near `alpha = 0.15–0.25`.

There is no misfit barrier along the straight segment in contour space from
either endpoint to the truth. That is not a convexity claim, and it deliberately
ignores MLP reachability, the conversion audit and the motion cap — which is
what makes it informative. The obstruction is not a wall in the data misfit
between the star's stopping shape and the target.

## On coupling: no single-mode correction is a descent direction

**The same machinery measures observability at the actual frozen contour, which
is what Codex asks for and neither document schedules.** Decomposing the
node-wise correction toward the target (`17.19 mm` RMS) into Cartesian
node-index modes and applying each alone:

| mode | 0 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| loss change at 1 mm RMS | **-0.0104** | +0.0094 | +0.0057 | **-0.0086** | +0.0060 | **-0.0044** | +0.0184 | +0.0109 | -0.0028 |
| loss with the full correction | 0.3071 | 0.3944 | 0.3132 | 0.2957 | 0.2736 | 0.2814 | 0.2614 | 0.2682 | 0.2324 |

Against a base loss of `0.235146`, no single-mode correction above `1 mm` RMS
lowers the loss at all — restoring the target's mode-5 content alone raises it to
`0.2736`, and translating the contour onto the target centre raises it to
`0.3071` — while the joint `5%` step toward the target lowers it to `0.229028`.
Read this as coupling, not as per-mode observability: `1 mm` RMS is a finite
difference rather than a derivative, and mode 0 here is a rigid translation.
The measured statement is that at this state the direction to the truth is a
coordinated combination of modes, and mode-by-mode improvement does not exist.

That is the first measured argument for section 10's metric-aware step, and it
can be tested before any neural optimizer work. This suite's residual is 48
real numbers, and a normal-displacement basis up to `m = 12` has 25 real
degrees of freedom, so a modal Gauss-Newton or TSVD direction at a frozen state
costs about 25 forward solves — roughly `5 s` with the numbers above. If that
step points at the true error while the accepted neural step does not, the
obstruction is the metric and the parameterization, not the physics; if it does
not, a neural GN would not have helped either.

It also reframes Priority E rather than displacing it. Multistatic-8's measured
iteration-1 benefit was conditioning (`73.6 -> 10.4`), which is exactly what a
strongly coupled misfit needs. Keep it as the first acquisition change, and
argue it as conditioning rather than as missing information.

## On section 12: the two cases are in different search regimes

**The shared-mechanism test needs a control neither document states.** Taking
the trial that was rejected immediately before each accepted step — the
constraint that actually set the step length:

| Binding constraint at the next-larger step | Star | Circle |
|---|---:|---:|
| Boundary motion cap | 38 | 25 |
| Conversion refinement change | 8 | 0 |
| Conversion distance and refinement | 1 | 0 |
| Armijo (data and/or regularized) | 0 | 33 |
| Mixed motion and Armijo | 0 | 2 |

In all `47` star iterations the step length was set by a geometry constraint and
never by the objective; `40` of the accepted steps land at exactly backtrack 6.
The circle is objective-limited in the majority, with accepted backtracks spread
from 1 to 10. The star's very first trial offered a `35.0%` loss decrease and
was rejected for `32.8 mm` of motion. Agreement between the two cases therefore
supports a shared mechanism only after conditioning on which constraint binds;
without that, the guide's section-12 comparison can find a common pattern that
is really the trust region in one case and Armijo in the other.

## On section 11: a third branch for the terminal stop

**Add field conditioning beside "audit sensitivity" and "genuinely harder
contour".** The star's accepted conversion distance is `1.47 um` at state 0,
`1.58` at 24, `5.37` at 32, `109.51` at 40 and `144.44 um` at 47, with the
refinement change reaching `9.98 um` against its `10 um` limit. This is a
forty-iteration drift, not a terminal event, and it tracks the gradient-norm
degradation above (Spearman `0.864` between the sampled Eikonal loss and the
conversion error across accepted states).

A discriminating test needs no BEM: from the frozen final weights, run the
Eikonal term alone for a short repair, then measure both the contour movement
and the conversion metrics. Materially improved conversion with a nearly
stationary contour implicates conditioning; unchanged conversion implicates the
contour itself. Endorse Codex's caution that the audit's resolution is derived
from the production grid, freeze one while varying the other, and hold both
limits fixed.

## On the ellipse and on E/F

**Nothing to add to X1 and X2 except that they are cheap, independent and
should stay parallel.** For E and F, keep Codex's requirements — same frozen
weights, declared normalization, declared evaluation and wall caps, evaluation
acquisition fixed across arms — and drop the argument that a `3-5` update cap is
required by cost once the polygon test is fixed. Add one control: both arms
inherit the same field drift from the same wrong start, so report the
on-contour gradient spread per arm, or an acquisition comparison will silently
carry a conditioning difference it did not intend to test.

## Suggested ordering

| Order | Experiment | Approximate cost | What it decides |
|---|---|---|---|
| 1 | Vectorize the polygon self-intersection count, verified by exact integer equality on saved polygons | hours | Whether every later experiment costs 13 s or 2 s per candidate |
| 2 | On-contour field-gradient norms, conversion metrics and radial spectra at every saved state, both cases | minutes, no BEM | Whether the distance-property drift is general, and where it starts |
| 3 | Curve-space transect and single-mode sensitivity at two or three frozen states per case | seconds per state | Whether a misfit barrier exists anywhere on the trajectory |
| 4 | Curve-space modal Gauss-Newton/TSVD direction at the same frozen states | about 5 s per Jacobian | Whether a metric-aware step reaches the true error, before any neural optimizer work |
| 5 | Priorities A and B as written, with the numerator/denominator split | as scoped | What the neural update does to the interface and to the converted boundary |
| 6 | X1/X2 ellipse capture, and the frozen star conversion audit with the conditioning branch | short, parallel | Startup validity; which of three causes ends the star run |

Priorities C, D, E and F stay after these, and a long inverse stays behind all
of them. If step 2 confirms the drift is general, one declared single-factor
regularizer-sampling arm belongs beside E rather than after it.

The disagreement with both documents is about sequence and about which quantity
is diagnostic, not about method. Their discipline should be kept: one principal
factor per expensive comparison, declared budgets, an unchanged fidelity
contract, and refusal to read a falling training loss as recovery. One rule is
worth adding to it — do not spend an expensive comparison while a measured,
uncontrolled drift in the field's distance property sits upstream of the
geometry, the motion cap and the audit.

## Measurements made for this review

Six read-only probes over the September 8 bundles, with their script, full
precision values, environment and source hashes at
[`results/validation/implicit_mlp_adjoint/iteration-02-20260908/review-diagnostics/`](../../../../../results/validation/implicit_mlp_adjoint/iteration-02-20260908/review-diagnostics/README.md):
the runtime split and profile, on-contour gradient norms and radial spectra at
selected states, Eikonal sample proximity, the curve-space transect, the
single-mode sensitivity table, and the line-search statistics recomputed from
the saved trial records. No inverse was launched, no weights were changed, and
no saved artifact was modified.

Their caveats travel with the numbers. Timings are single-machine engineering
measurements and the profiler totals are inflated by profiling overhead, so
only their shares are meaningful. The radial spectra use a polar decomposition
about the polygon centroid, resampled to 512 uniform angles; they are not the
arc-length modal basis the proposals specify, and every state reported has a
single-valued radius. The transect is one straight path in node coordinates
between saved node sets, and ignores MLP reachability, the conversion audit and
the motion cap by construction. The modal sensitivities are finite `1 mm` RMS
differences in Cartesian node-index modes, in which mode 0 is a rigid
translation. Nothing here measures the neural update map itself: that is still
Priority A, and it is still the next thing to build.
