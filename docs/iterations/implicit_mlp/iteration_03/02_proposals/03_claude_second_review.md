# Second Claude review: the reference success, and what the data can resolve

Recorded 2026-09-08 by Claude, in a session that began without the first
review's working context, after the
[ChatGPT guide](01_chatgpt_guide.md), the
[first Claude review](02_claude_review.md) and the
[iteration-3 results](../01_results.md). This is a review, not a plan and not
authorization. Decisions belong in `03_plan.md`.

The first review's code claims survive independent checking; the list is in the
last-but-one section, and nothing structural in it needed correcting. Its
central objection — that the control as written is matched to the implicit
failure and not to the radial success, so a negative result could not carry the
meaning section 10.3 assigns it — is right, and this review reaches the same
conclusion by a route the first one did not take.

Three things are new. The first is that the radial success differs from the
iteration-3 runs in **acquisition** as well as chart, optimizer, prior and
dimension, which no document has recorded. The second is that this turns out
**not** to explain E1, and the measurement that shows it also removes a
candidate from the results document's ranked list. The third is that the first
review's active-band recommendation is priced in the wrong chart, and its error
floor prices the wrong quantity; both are corrected here with numbers.

Two probes were run for this review. Unlike the first review's, they perform
Kress **forward** solves — about 700 of them, ten minutes on one thread — on
frozen analytic curves. No inverse, no MLP, no extraction, no conversion, no
adjoint. They are indexed at the end and every value is stated inline.

## The reference success used a different acquisition

Section 10.1 states its conclusion against the radial success, and the first
review correctly insisted that the comparison be matched to it. Both documents
then take the acquisition as the one thing that is already shared. It is not.
The recorded configurations of the two runs are:

| | radial-Fourier star run | iteration-3 E0 | iteration-3 E1 |
|---|---|---|---|
| Source/receiver pairs | **24** | 8 | 8 |
| Measurement entries | 24 paired | 8 paired | 64 multistatic |
| Training frequencies | **6**, 0.25–2.5 GHz | 2, 0.5/1.5 GHz | 2, 0.5/1.5 GHz |
| Real residual components | **288** | **32** | 256 |
| Geometry parameters | 11 | 8,577 | 8,577 |
| Optimizer | Levenberg GN, `k**4` prior | Adam + backtracking | Adam + backtracking |
| Ring standoff | 0.30 m | 0.30 m | 0.30 m |
| Target | star, 50 mm, 12.5 mm, 5 lobes | same | same |
| Initial mean radius | 50.987 mm | 60.002 mm | 60.002 mm |
| Initial mode-5 amplitude | **0.000 mm** | 7.181 mm | 7.181 mm |
| Initial centre error | 28.284 mm | 28.306 mm | 28.306 mm |
| Outcome | converged, **0.257 nm** max sampled boundary error, 82.98 s | 14.097 mm | 9.506 mm |

Sources are from `results/inverse/radial_fourier/representation_policies/saved-star-20260905/metrics.json`
(`experiment.num_pairs = 24`, six `angular_frequencies_rad_s`, `curve_only`
policy `accepted_updates = 44`,
`canonical_maximum_sampled_boundary_error_m = 2.569831856107766e-10`) and, for
the neural arms, the long run's `observations.npz`, whose arrays are `E0 (8, 2)`
and `E1 (64, 2)` complex. Both use `driver._ring_scan` at standoff 0.30 m, so
the rings are physically the same; only the number of angles and frequencies
differs.

The initial states differ too, and not in the direction that would explain the
outcome away. The radial run starts from an ellipse — mode 2 at `15.926 mm`,
mode 4 at `3.886 mm` and mode 5 at **exactly zero** — with a mean radius already
near the target's 50 mm. The neural runs start from a wrong-radius star that
already carries `7.181 mm` of mode 5, 57% of the target amplitude. Both share
the same `28.3 mm` centre error. So the run that had to create the lobes from
nothing reached `0.257 nm`, and the runs that began with more than half of them
lost them.

Two more things follow immediately. The radial success had **nine times** E0's
real data and 1.13 times E1's, on **eleven** parameters rather than 8,577. And
the first review's identifiability arithmetic — "386 coefficients against 256 real
residual components" — is the E1 figure; for E0 it is 386 against **32**.

The guide's section 8 fixes the 8x8 two-frequency acquisition for the direct
control. That is the right choice for the ownership ablation, and the wrong
choice for a claim stated against the radial success. Acquisition is a fifth
unmatched factor and should be named as one.

## Whether that matters: it does for E0, and not for E1

Rather than argue the point, it is measurable. The probe builds the central
finite-difference Jacobian of the data with respect to twelve low-order shape
directions — two centre translations and radial polar modes 0 and 2..10 — at the
exact target and at the shared initial contour, under seven acquisitions, using
the inverse's own residual normalization. Coherence
`|<J_a, J_b>| / (||J_a|| ||J_b||)` is 1 when two boundary modes are
indistinguishable at first order.

At the shared initial contour, the state the search actually starts from:

| Acquisition | real components | condition | \|\|J_m0\|\| | \|\|J_m5\|\| | m5~m3 | m0~m8 |
|---|---:|---:|---:|---:|---:|---:|
| **E0 paired-8, 2 f** | 32 | 5.27 | 86.5 | 89.4 | **0.3645** | **0.3239** |
| **E1 multistatic-8, 2 f** | 256 | 8.76 | 61.6 | 24.2 | 0.0709 | 0.0191 |
| paired-8, 6 f | 96 | 2.88 | 300.0 | 246.0 | 0.0232 | 0.0022 |
| multistatic-8, 6 f | 768 | 3.58 | 122.0 | 50.6 | 0.0389 | 0.0045 |
| paired-24, 2 f | 96 | 2.93 | 87.1 | 85.5 | **0.0003** | **0.0008** |
| multistatic-24, 2 f | 2,304 | 8.95 | 61.6 | 23.7 | 0.0011 | 0.0006 |
| paired-24, 6 f — the radial run's acquisition | 288 | 1.84 | 312.0 | 239.0 | 0.0063 | 0.0398 |

Every row is the same frozen curve seen by a different acquisition, so the
differences between rows are acquisition alone. The last row is the radial run's
acquisition applied to the neural starting state, which that run never saw.

**E0 has a genuine eight-fold aliasing defect.** Modes 5 and 3 sum to 8, and so
do modes 0 and 8 and modes 2 and 6; on an eight-angle scan those are exactly the
pairs a `(N-1)//2` Nyquist limit cannot separate, which is what
`run_mlp_sdf_inverse_comparison.py:862` already says in its own comment.
Across all seven acquisitions and both states, paired-8 at two frequencies is
the only one whose alias pairs exceed `0.3`:

| Acquisition | m5~m3 | m2~m6 | m0~m8 | m5~m3 | m2~m6 | m0~m8 |
|---|---:|---:|---:|---:|---:|---:|
| | *at the target* | | | *at the initial contour* | | |
| **paired-8, 2 f** | **0.3105** | 0.0847 | **0.5126** | **0.3645** | 0.1224 | **0.3239** |
| paired-8, 6 f | 0.1868 | 0.1084 | 0.4068 | 0.0232 | 0.1734 | 0.0022 |
| multistatic-8, 2 f | 0.0318 | 0.0344 | 0.0327 | 0.0709 | 0.0434 | 0.0191 |
| paired-24, 2 f | 0.0000 | 0.0002 | 0.0000 | 0.0003 | 0.0021 | 0.0008 |
| paired-24, 6 f | 0.0000 | 0.0225 | 0.0000 | 0.0063 | 0.0059 | 0.0398 |

Twenty-four angles remove the coupling in every state and at both frequency
counts. Six frequencies at eight angles help inconsistently — strongly for
`m5~m3` and `m0~m8` at the initial contour, much less at the target, and not at
all for `m2~m6`. The angle count is the factor that removes it reliably.

This has a fingerprint in the saved trajectory that the results document reports
only at its endpoints. Polar radial amplitudes in mm, from the arms'
`geometry_trajectory.json`:

| state | E0 m2 | E0 m3 | E0 m5 | E0 m8 | | E1 m3 | E1 m4 | E1 m5 | E1 m6 |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0 | 0.081 | 0.061 | 7.181 | 0.034 | | 0.061 | 0.091 | 7.181 | 0.043 |
| 10 | 4.095 | 5.205 | 5.560 | 2.908 | | 1.235 | 2.503 | 5.487 | 1.059 |
| 20 | 4.805 | **7.819** | 6.539 | 3.959 | | 1.597 | 4.265 | 2.734 | 2.085 |
| final | polar description lost from state 25 | | | | | 1.801 | **4.184** | **1.530** | 1.965 |

E0's largest spurious growth is exactly mode 3, the alias partner of the mode 5
it is trying to fit, with mode 8 — the alias partner of mode 0 — second. The
correspondence is worth recording. It is not proof: a coherence of `0.36` is
coupling, not degeneracy, and E0 also loses its polar description entirely at
state 25, which aliasing does not explain.

**E1 does not have that defect, and more angles would not help it.** Its alias
coherences are `0.019` to `0.071`; the second receiver index breaks the
source-angle aliasing, as it should. Decisively, **multistatic-24 buys nothing**:
condition `8.95` against multistatic-8's `8.76`, with the same per-mode
sensitivities to three figures. Nine times the data, no change.

**Neither arm is modally ill-conditioned.** Over twelve low-order directions the
condition numbers are `5.27` and `8.76`, and mode 5's sensitivity is within a
factor of `2.6` of mode 0's. The star's mode 5 is plainly visible to E1's data
at the start.

**Frequencies are a different matter from angles.** Six frequencies at eight
multistatic angles improve the condition number from `8.76` to `3.58` and raise
`||J_m5||` from `24.2` to `50.6`; twenty-four angles at two frequencies leave
both essentially unchanged. The two halves of "more data" are not
interchangeable here, and only the angle half is measured to be spent.

Three consequences.

The results document's priority-5 candidate — "decide whether frequency or a
neural metric adds a simpler repair" — should be **split rather than retired**.
Its angle half is measured to be exhausted for the multistatic arm: nine times
the entries changes nothing. Its frequency half is, if anything, *supported* by
the same probe, since the band it would add measurably improves low-mode
conditioning. That is a sharper question than the candidate as written, and a
cheaper one.

The guide's premise is **strengthened, not weakened**. Because the low-mode
problem under E1's data is well posed, a curve-owned control restricted to a low
band is a well-conditioned problem that ought to recover. If it does not, that
is strong evidence about the objective or the landscape rather than about the
representation — which is section 10.3's conclusion, now resting on a measured
premise instead of an assumed one.

The first review's open question — "the real question is the decay of the
shape-to-data singular spectrum, not the parameter count" — is **answered for
the low-mode regime and only there**. Twelve directions are well conditioned.
Nothing here measures the 386-coefficient or 8,577-weight maps, and the failure
must live in the difference.

## The active band is priced in the wrong chart

The first review recommends an active band of `B_a = 6` to `8`, reasoning that
the star's Cartesian signature is modes 4 and 6. The signature claim is exactly
right, and now exact: in the **polar-angle** parameter the target is

```text
(R + A cos 5t) (cos t, sin t)  ->  modes 1, 4 and 6 only,
```

measured at `70.711`, `8.83883` and `8.83883 mm`, with everything above mode 6
at `5.1e-14 mm`. Mode 0 is `707.107 mm`, the distance from the origin to
`(0.5, 0.5) m`, and mode 1 over `sqrt(2)` is `50.000 mm`.

But Method B refits by **arc length**, and that is the chart the direct control
would optimize. The star's polar-parameter speed ratio is `2.151657`, so the
remap is strongly nonlinear and the same curve is **not** bandlimited in the
chart actually used. Its arc-length spectrum is `k=1: 72.138`, `k=4: 9.266`,
`k=6: 7.225`, then `k=9: 1.241`, `k=11: 0.210`, `k=14: 0.555`, `k=16: 0.354 mm`,
and the bandwidth the target itself needs is:

| `B_a` | active real coefficients | max truncated displacement | RMS |
|---:|---:|---:|---:|
| 6 | 26 | 1847.954 um | 1025.346 um |
| 8 | 34 | 1847.954 um | 1025.346 um |
| 12 | 50 | 1118.437 um | 508.916 um |
| 16 | 66 | 476.032 um | 206.357 um |
| 24 | 98 | 203.481 um | 76.059 um |
| 32 | 130 | 106.893 um | 41.312 um |
| 48 | 194 | 29.366 um | 11.004 um |

At `B_a = 8` the target's own truncation is `1.848 mm`, nine times the `200 um`
conversion gate the neural arms are held to. `B_a = 24` is the first band inside
that gate.

**The band must be declared in the arc-length chart, not the polar one.** This
does not overturn the first review's recommendation so much as bound it: modes 4
and 6 carry `9.27` and `7.23 mm` and are inside `B_a = 8`, so a low-band arm can
still demonstrate lobe recovery. It cannot be described as able to represent the
target, and its floor must be stated with its result.

## The frozen-tail floor prices the wrong quantity

The first review corrected the guide's section 8.1.B budget on the ground that
it "prices an approximation the experiment never makes", and then reported
`947.909 um` at `B_a = 8` as "boundary detail the arm can never correct". The
same objection applies to that number. The design freezes the tail at the
**initial** curve's coefficients; what the arm can never correct is the
**difference** between the target's tail and the initial curve's tail, not the
size of the initial tail. Since the frozen modes are L2-orthogonal to the active
ones, that floor is exact in the parameterwise L2 metric, minimized over the
parameter-origin gauge:

| `B_a` | \|tail(initial)\| max | \|tail(target)\| max | **floor RMS** | **floor max** |
|---:|---:|---:|---:|---:|
| 6 | 964.105 um | 1847.954 um | **674.117 um** | 1652.690 um |
| 8 | 947.909 um | 1847.954 um | **671.201 um** | 1731.630 um |
| 12 | 729.310 um | 1118.437 um | 385.668 um | 948.114 um |
| 16 | 491.833 um | 476.032 um | 213.446 um | 533.600 um |
| 24 | 394.010 um | 203.481 um | 117.181 um | 293.361 um |
| 32 | 146.862 um | 106.893 um | 43.311 um | 111.816 um |

The first column is the first review's number and reproduces it exactly. The
floor at `B_a = 8` is `671 um` RMS and `1732 um` maximum — parameterwise
displacements in the shared arc-length parameter, which upper-bound pointwise
curve distance and are not the symmetric point-to-curve distances of
`01_results.md`.

The first review's conclusion nevertheless survives its own number: against E1's
final raw symmetric RMS of `9.506 mm`, a `0.67 mm` floor is not disqualifying,
and it is honest. Record the floor next to the arm's result, and do not let a
run that stops at `0.7 mm` be read as convergence.

## The Gauss-Newton arm costs twice what was estimated

The first review makes D-GN the primary control and prices it: "the existing FD
modal Jacobian (`_modal_jacobian`) costs one forward solve per active parameter
per outer iteration". It costs **two**. `_modal_jacobian`
(`solvers/sdf_inverse/neural_optimization.py:893`) evaluates
`plus_value` and `minus_value` per column and forms a central difference; the
one-sided fallback at `:920` is a two-solve second-order stencil used only when
a side fails topology.

This matters twice over, because the analytic pullback of the guide's section 4
does not remove it. That contraction yields the **gradient** of the scalar
objective, `dL/dc`, not the residual Jacobian `J` that Gauss-Newton needs.
Obtaining `J` needs either finite-difference columns or one adjoint per residual
component, and the repository's Gauss-Newton path takes the first route. Whether
a per-component adjoint would be cheaper here — the Kress matrix is shared
across the right-hand sides at a frequency — was not investigated and is an open
question, not a cost claim. On the existing route D-GN is finite-difference
bound at two solves per active parameter, and the first review's step-2
cross-check of `jacobian.T @ residual` against the analytic gradient is exactly
the right validation for it.

Measured on this machine at the production geometry, one multistatic-8
two-frequency Kress solve at 194 nodes takes `0.185 s` and one curve build
`0.127 s`, single-threaded. The table below scales that one measurement by
parameter count, so every row is like-for-like at E1's acquisition; the radial
row is not that run's own recorded time, and none of these are controlled
benchmarks:

| Arm | active real parameters | solves per outer iteration | approximate cost |
|---|---:|---:|---:|
| radial control, `K=5` | 11 | 22 | ~7 s |
| D-GN at `B_a = 8` | 34 | 68 | ~21 s |
| D-GN at `B_a = 24` | 98 | 196 | ~61 s |
| D-GN at full `B = 96` | 386 | 772 | ~4 min |

The first review's affordability conclusion holds with the corrected constant:
`68` is still the same order as the radial control's `22`, and even the band the
target actually needs is a minute per outer iteration. Its section-4 warning
against coefficient finite differences at `B = 96` also holds — but as a cost
argument at `4 min` per iteration, not a prohibition.

## The first review's code claims, checked

Independently verified in the working tree, and correct as stated: the
`num_nodes >= 2 * bandwidth + 2` requirement at `geometry.py:158` with
production at exactly `194 = 2*96 + 2`; `MethodResult.representation` as the
final arc-length refit representation (`method_b.py:157`) and its discard at
`geometry.py:382`, where the build keeps only
`fit.parameterization.discretize(...)` — `geometry.py` mentions
`representation` nowhere else, so the proposed optional field is additive, and
`OrderedSDFGeometryBuild` (`geometry.py:205`) is a frozen dataclass whose
trailing fields already carry defaults; `predict_indexed_curve_response(...,
retain_kress_state=True)` at `forward.py:692` and the absence of that keyword
from `predict_paired_curve_response` at `forward.py:618`; `_curve_geometry_build`
checking bounds and `sampled_self_intersection_count` **at the 194 nodes only**
(`forward.py:432`, `:461`) and zeroing the three SDF residual fields with a
docstring saying they must not be read as an MLP audit;
`radial_fourier_state_curve` calling `validate_periodic_parameterization` at
`validation_resolution = 1024` and falling back to the node polygon only when
`full_validation=False` (`curve_updates.py:484`, `:517`); the dense audit at
`max(validation_resolution, 64 * (K + 1))` (`:588`); `FourierBoundary`
(`representations.py:238`) as a frozen dataclass with `with_coefficients`,
`bandwidth` and `to_parameterization`; `fourier_curve`
(`ordered_boundary/analytic.py:166`) using the `tau = (2*pi/P)(t - t0)`
convention the guide's section 4 identities assume; the Levenberg-damped
Gauss-Newton solve `normal_matrix + trial * diag(scaling) + diag(curvature)`
(`neural_optimization.py:1055`), the gradient `jacobian.T @ base.residual`
(`:1874`), the `k**4` `_curvature_penalty` (`:982`) and the gauge-fixed radial
chart (`curve_updates.py:276`); and the recorded radial configuration
`direct_curve_retraction: radial_fourier`, `curvature_penalty_weight: 0.0001`,
`maximum_mode: 5`, which is 11 real parameters.

The seam to copy for the direct pullback, `implicit_adjoint.py:217-227`, is as
described: keep the objective adjoint and `build_kress_geometry_pullback`,
replace `build_method_b_pullback` with the analytic basis contraction.

Three corrections, all above: the finite-difference cost, the frozen-tail
quantity, and the chart the band is declared in.

## What this changes for the plan

The first review's D-GN / D-Adam bracketing is right and should be adopted; its
warning against running an arm whose optimizer matches neither reference run is
the single most useful rule in either document. Its ordering stands, with four
amendments.

| | Amendment |
|---|---|
| 1 | Declare **acquisition** as a named factor alongside chart, optimizer, prior and dimension. Either add one arm at the radial run's paired-24 / six-frequency acquisition, or state in the write-up that the control is matched to the implicit failure only |
| 2 | Declare the active band **in the arc-length chart**, and record the target's own truncation there. `resolvable_maximum_mode` intersected with the angular Nyquist limit is a **polar** rule; a polar cap `K` corresponds to Cartesian modes `K±1`, so it must be translated, not applied verbatim. On E1's acquisition that rule returns 3, which would exclude the lobes; the first review's `B_a = 6..8` is the better choice and needs its own justification |
| 3 | Report the frozen-tail **floor**, not the initial tail: `671 um` RMS at `B_a = 8`. State it beside the arm's final error |
| 4 | Price D-GN at **two** solves per active parameter |

One item on the results document's ranked list should be split rather than
amended. Priority 5's angle half is measured and spent: multistatic-24 is
indistinguishable from multistatic-8 over the low modes, so more angles are not
the multistatic arm's missing ingredient. Its frequency half points the other
way — six frequencies improve E1's low-mode condition number from `8.76` to
`3.58` — and is now a cheaper, better-posed question than the candidate as
written. Its neural-metric half is untouched by this evidence.

E0's aliasing gives the guide's section 8.2 a better reason than it had. The
guide defers the paired arm because paired is "the weaker geometry arm"; the
sharper statement is that paired-8 has a measured first-order confusion between
mode 5 and mode 3 that 24 angles remove entirely, so a paired direct control at
that acquisition would inherit a known defect. If a paired arm is ever wanted,
run it at paired-24.

Everything else in the first review's discipline should be kept in full: one
declared factor per comparison, the normal/tangential step split and dense-grid
motion cap, full-validation candidate acceptance, no tuning against the target
or the 3 GHz evaluation, and no promotion of a short control into a production
inverse.

## Measurements made for this review

Two probes, with scripts, full-precision output and their caveats at
[`review-diagnostics-identifiability/`](../../../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics-identifiability/README.md):
the modal sensitivity, coherence and singular spectrum under seven acquisitions
at two frozen states, and the arc-length chart bandwidth with the frozen-tail
floor. About 700 Kress forward solves on frozen analytic curves at the long
run's own geometry configuration. **No inverse was run, no MLP was loaded, no
extraction, projection, Method-B fit, conversion audit or adjoint was
evaluated, and no saved artifact was modified.** The trajectory table is read
from saved `geometry_trajectory.json` files with no new computation. The radial
run's acquisition, optimizer settings and outcome are read from its recorded
`metrics.json`, not inferred from defaults.

The caveats travel with the numbers and are stated in full in that README. The
three that matter most for reading the tables above: the modal probe is a
**linearization at two states over twelve low-order directions**, and says
nothing about the 386-coefficient or 8,577-weight maps; the initial state is a
**radial fit through mode 10** of the shared initial contour, reproducing its
reported mean radius `60.0024 mm` and mode-5 amplitude `7.1807 mm` but
discarding its higher modes; and a coherence of `0.36` is **coupling, not
degeneracy**, so the correspondence with E0's mode-3 growth is a recorded
observation and not a demonstrated cause. Polar modes here are the polar modes
of `01_results.md`; the Cartesian modes of the bandwidth probe and of the first
review's chart probe are different objects, and every table above says which it
uses.
