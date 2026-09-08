# Claude review: the topological derivative is right, and the frequency decides everything

Recorded 2026-09-08 by Claude at `3835f69f378323d3ee6752e069a79d74f1f3207b`,
after the
[initial implementation brief](01_radial_fourier_topology_initial_instructions.md)
and the [Codex review](02_codex_review.md). This is a review, not a plan and not
authorization. Decisions belong in `03_plan.md`.

**Verdict: adopt the architecture, and fix the frequency before anything else.**
The brief's structure survives checking and the Codex review's seven amendments
are, with two exceptions noted below, correct. Both documents nevertheless leave
the single most consequential setting — the T0/T1 frequency — as a decision to be
recorded later, alongside grid shape and node counts, as though it were of the
same kind. It is not. On the repository's own two-circle scene the whole
experiment succeeds at 0.25–0.75 GHz and fails at 1.0–2.0 GHz, and the failure is
not detectable at gate G1.

Two probes were run for this review. They perform **no BEM solve and no inverse**:
every forward value comes from the independent `multicylinder_ref` oracle and the
objective from the production `normalized_complex_residual`, so no discretization
question is entangled with the derivative question. About 22 seconds on one
thread. They are indexed at the end and every value is stated inline.

Four things are new. The exact topological-derivative expression is **derived,
implemented and validated against finite-radius insertions to 0.05%**, so gate G1
can be retired before implementation instead of after it. Gate G2 is
**frequency-dependent and non-monotone**, and the frequency Codex's ordered plan
would most naturally pick is one of the failing ones. The brief's displayed sign
is **wrong** for this repository. And at a failing frequency the birth line
search still **accepts** a component in the wrong place, so G3 as written cannot
protect the result.

## The expression, and its measured agreement

Section 8.2 asks for the sign, conjugation, prefactor, residual normalization and
source-strength factor to be derived from the repository's own conventions. They
are derivable now. The multi-component Kress pipeline accepts nonmagnetic,
lossless media only (`_validate_supported_materials`,
`solvers/gpr_bem_kress/multicomponent.py:424`), so only the zeroth-order
coefficient of the Helmholtz operator jumps across an inclusion. The
polarization-tensor term of the general elliptic theory therefore genuinely
vanishes and the leading correction is the volume term the brief expects. With
`(Delta + k^2) u = -Q delta`, which is the convention both the Kress receiver
operator (`multicomponent.py:1414`) and the oracle's
`line_source_incident_field_matrix` use through `0.25j * H0^(1)(k r)`,

    delta u(x) = (k_i^2 - k_e^2) * pi rho^2 * u(z) * G_Omega(x, z) + o(rho^2),

and differentiating `J = 0.5 * sum_f (w_f / s_f^2) sum_s |p_sf - d_sf|^2` gives

    D_T J(z; Omega) = sum_f (w_f / s_f^2)
                      Re[ (k_i^2 - k_e^2)
                          sum_s conj(p_sf - d_sf) u_sf(z) G_f(z, x_r(s)) ].

`u_sf` carries the physical source strength; `G_f(z, x_r)` is the current-domain
total field at `z` for a **unit** source at the paired receiver, which by
reciprocity is the receiver-to-`z` response. There is **no leading minus sign**
and no factor of one half. Section 8.2's displayed
`D_T J ~ -Re[(k_i^2 - k_e^2) sum_s u_s a_s]` has a sign error relative to its own
displayed `a_s(z) = sum_r w_sr conj(r_sr) G_Omega(z, x_r)`; the brief is right
that the sign must be checked, and this is what it checks to.

Measured against `Q_rho(z) = (J(Omega + B_rho(z)) - J(Omega)) / (pi rho^2)` on the
two-circle scene at 0.5 GHz, with the current domain the exact component A and the
truth A + B:

| probe | `D_T J` | `Q` at 5 mm | 2.5 mm | 1.25 mm | 0.625 mm |
|---|---:|---:|---:|---:|---:|
| true B centre | −1.5927e2 | 3.31% | 0.91% | 0.247% | **0.066%** |
| background (0.50, 0.62) | −5.3337e1 | 7.39% | 1.96% | 0.511% | **0.132%** |
| background (0.66, 0.66) | +3.7809e1 | 15.1% | 3.81% | 0.942% | **0.232%** |

The sign agrees at every probe and every radius, the error falls at the expected
second-order rate, and the ranking separates favourable from unfavourable probes.
The empty-background branch behaves identically (0.066% at 0.625 mm at the true
centre). The brief's "about 10% relative agreement at a strong probe" target is
met with two orders of magnitude to spare.

Two by-products worth putting in the plan as free assertions. `J(empty)` is
exactly `0.5 * sum_f w_f`, because `s_f` is defined as the observed column norm —
measured `0.4999999999999999` — which pins the empty branch's objective
convention without a solve. And every source-strength question dissolves: the
strength enters `_source_strengths` as a scalar multiplier on the incident traces
and on `incident_receiver`, so the solve is exactly linear in it and one factor
of `Q_f` belongs to `u`, none to `G`.

**Consequence for the plan.** G1 does not need to be a discovery step. The plan
can state the expression above, state that it was validated to 0.07% against the
independent oracle before implementation, and make G1 a regression test that the
implemented code reproduces the same numbers — which is a much stronger gate than
"derive it, then see". It also removes the brief's hardest numerical constraint:
Section 11 wants the insertion ladder run through Kress, where the smallest disk
must simultaneously be resolvable, clear A by more than
`2 * max(arc_length_weights)` and stay in the asymptotic regime. Run against the
oracle, `rho` can go as small as the plan likes.

## The frequency decides whether the experiment works at all

Section 16 says the first derivative validation should be at one frequency "to
make sign and scaling interpretable", and Codex's decision list asks
`03_plan.md` to fix "the exact two-circle scene, paired acquisition and single
T0/T1 frequency". Neither says how to choose it. On this scene, with the current
domain the exact A, the grid minimum of the validated field lands here:

| f (GHz) | `k_e r_B` | `D_T J(c_B)` | argmin, n=121 | argmin, n=241 | distance to `c_B` |
|---:|---:|---:|---|---|---:|
| 0.10 | 0.180 | −8.997e1 | (0.5867, 0.5000) | (0.5867, 0.5000) | 16.7 mm |
| 0.25 | 0.449 | −2.377e2 | (0.5733, 0.5000) | (0.5717, 0.5000) | **1.7 mm** |
| 0.50 | 0.898 | −1.593e2 | (0.5733, 0.5000) | (0.5733, 0.5000) | **3.3 mm** |
| 0.75 | 1.348 | −3.238e2 | (0.5700, 0.5000) | (0.5717, 0.5000) | **1.7 mm** |
| 1.00 | 1.797 | −1.442e2 | (0.3033, 0.4767) | (0.3017, 0.4750) | 269.5 mm |
| 1.50 | 2.695 | **+2.301e3** | (0.5033, 0.5000) | (0.5033, 0.5000) | 66.7 mm |
| 2.00 | 3.594 | −1.351e3 | (0.6933, 0.4967) | (0.6917, 0.4950) | 121.8 mm |
| 2.50 | 4.492 | −2.752e3 | (0.5700, 0.5000) | (0.5700, 0.5000) | 0.0 mm |

The true missing centre is `(0.5700, 0.5000)` and B's radius is 35 mm, so a
distance under 35 mm means the minimum is inside the missing object. Below about
`k_e r_B = 1.4` the derivative puts its minimum within 3.3 mm of the missing
centre; from 1.0 to 2.0 GHz it does not, and at 1.5 GHz the missing centre is
close to the field's **maximum**. Both grid resolutions agree to one cell, so
this is a property of the field, not of the sampling.

At 1.5 GHz the derivative at `c_B` is `+2.301e3`, and the insertion ladder
confirms it independently: `Q` converges to `+2.300e3` to 0.046%. Inserting
material at exactly the right place makes the objective **worse**. The whole
birth ray is non-monotone:

| `rho` (mm) | 1 | 5 | 10 | 15 | 20 | 25 | 30 | 35 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `J` at 0.5 GHz | 0.1943 | 0.1827 | 0.1505 | 0.1076 | 0.0645 | 0.0295 | 0.0074 | 0.0000 |
| `J` at 1.5 GHz | 0.3320 | 0.5081 | 1.0129 | 1.4646 | 1.4497 | 0.9917 | 0.3596 | 0.0000 |

`J(A) = 0.3248` at 1.5 GHz. Along the ray to the exact truth the objective first
rises by a factor of 4.5 and only crosses back below `J(A)` at the true radius.
No backtracking rule can traverse that: the brief's `1.0 / 0.75 / 0.50 / 0.35`
ladder and Codex's amendment 7, which extends backtracking *down* to the smallest
resolvable radius, both search in the direction that makes things monotonically
worse. At 0.5 GHz the same ray is monotone and every radius in the ladder is
accepted.

This is the regime boundary the topological-derivative literature lives inside,
and it is not a defect of the method — it is the small-inclusion asymptotic
hypothesis applied to a strong wavelength-scale scatterer. It is also not
specific to the iterative current-domain case: at 1.5 GHz the **empty-background**
one-step field misses the single circle by 146 mm, with `D_T J` at the true centre
positive. The brief treats T0 as convention sanity and T1 as the real test; in
fact T0 and T1 pass and fail together, and T0 is the cheaper place to discover it.

**Consequence for the plan.** The frequency is not a configuration row alongside
grid shape. Order the plan so that the T0 localization sweep — pure oracle
arithmetic, no solver, seconds — runs *before* any node count, `C0`, grid shape or
optimizer decision is fixed, and let its result choose the band. On this scene
0.25–0.75 GHz is the working band and 0.5 GHz is the natural declared default: it
is one of the three frequencies `test_two_circle_comparison.py` already validates,
it sits mid-band, and it is far from both edges of the working range. Record
`k_e r_B` next to every reported frequency, because it, and not the frequency in
GHz, is what generalizes to the next scene.

## The multifrequency indicator inherits the failure

Section 3.7 and Section 16 ask for both a raw sum matching the objective and a
frequency-normalized proposal field, and require that a disagreement be reported
rather than resolved in favour of the truth. Measured on this scene, over the
`0.5 / 1.5 / 2.5 GHz` set that `test_two_circle_comparison.py` validates:

| indicator | argmin | distance to `c_B` |
|---|---|---:|
| raw sum, 0.5 / 1.5 / 2.5 GHz | (0.709, 0.287) | 254 mm |
| min-normalized mean, same set | (0.713, 0.287) | 256 mm |
| raw sum, 0.1 / 0.25 / 0.5 GHz | (0.573, 0.500) | **3.3 mm** |

Normalization does not rescue the high band. The single-frequency magnitudes span
a factor of 20 across 0.25–2.5 GHz, so the raw sum is dominated by the high
frequencies, but dividing by `|min D_T f|` does not help because the high-frequency
fields are wrong-shaped, not merely mis-scaled. Note also that these three rows
were computed over the full `+-0.22 m` square; the two failing rows put their
minimum at radius 0.301 m from the scene centre, which is the source/receiver ring
— see the next section.

**Consequence for the plan.** Keep Section 16's comparison, and expect it to be a
low-band accumulation rather than a whole-band one. The plan should declare the
multifrequency set as a subset of the working band established by the T0 sweep,
not as the existing validation triple.

## The raw field is singular at the stations, and that decides the threshold

Neither document specifies the inspection region beyond "current physical search
bounds" and a list of things to mask. This is not a detail. `u_s(z)` is singular
as `z` approaches a source and `G(z, x_r)` as `z` approaches a receiver, so the
raw field has a logarithmic spike at each of the 48 stations. The threshold rule
of Section 13.1 is *relative to the global minimum*, so a single spike anywhere on
the grid rescales `(1 - C0) min D_T J` and can empty or fragment the real region.

Measured: on a `+-0.22 m` square grid, whose corners reach 0.311 m and therefore
cross the 0.30 m ring, the 0.25 GHz minimum sits at `(0.7117, 0.2883)` — radius
0.2994 m, on the ring — 255 mm from `c_B`, and the `C0 = 0.15` region around it is
1.55 mm across. On a 121-point grid over the same square the spike is missed
entirely and the minimum is at B. That is a settings-dependent result masquerading
as a physics result, and it is exactly what Section 12 forbids resolving by
looking at the truth.

Restricting the region to a disk of radius 0.20 m about the scene centre, which
keeps every point 0.10 m clear of every station, removes it: the two grid
resolutions in the frequency table above then agree to one cell everywhere. The
probes use this and it is the recommendation.

**Consequence for the plan.** Declare the inspection region as a disk inside the
acquisition ring with a station clearance in physical units, not a bounding box
with a masking list, and fix it before the first field is computed. Report the
minimum station distance actually achieved.

Two related resolution points, both of which cut against Codex's amendment 6 in
its current form. The multi-component field-point guard is
`minimum_field_point_clearance_in_weights * max(arc_length_weights)`
(`multicomponent.py:1663`) and the cross-component guard is
`minimum_clearance_in_weights * max(weights)` over the pair
(`multicomponent.py:354`). Both are proxies for node spacing, so both **shrink
under node refinement**. Amendment 6 asks for stable topology and clearance
classification at a finer node count; but a configuration that fails the guard at
production resolution passes it at refined resolution, and "refine until the guard
passes" would admit a component the ordinary quadrature cannot actually resolve.
The guards also move the valid TD grid between resolutions, so the refined field
is not compared on the same point set. The fix is one line of configuration:
declare `minimum_absolute_clearance` in metres and a physical TD mask buffer, so
that refinement changes accuracy and not the admissible set. On this scene neither
guard binds — with 256 nodes on a 35 mm circle the required clearance is 1.7 mm
against a 75 mm gap — so this costs nothing and closes the loophole.

## A birth can be accepted in the wrong place

Section 13.3 and gate G3 treat a strict decrease of the actual objective as the
arbiter of a topology proposal, and Codex's amendment 6 strengthens the margin to
a cross-resolution bound. Both are right about what they exclude. Neither
excludes this: at 1.5 GHz, where the field does not localize B, the `C0 = 0.15`
rule selects a region at `(0.5042, 0.5000)` — 65.8 mm from `c_B`, in the gap
between the two true components — and the birth line search **accepts** it, taking
`J` from 0.324751 to 0.239835 at a 5.64 mm radius. Every radius in the ladder is
accepted. A tighter margin would not have rejected any of them; the decrease is
four orders of magnitude above any plausible numerical floor.

So G3 as written passes while the topology is wrong. The residual is large, and a
small component almost anywhere in the illuminated region can absorb some of it.

**Consequence for the plan.** G3 must carry a qualification alongside the decrease.
Two are available at zero cost and both discriminate cleanly here: the localization
error `e_loc` that Section 12 already defines, and the **number of threshold
regions**, which is 1 at every working frequency and 11, 17 and 34 at 1.5 GHz for
`C0 = 0.15, 0.20, 0.40`. A fragmented mask is a reliable signal that the field is
outside its asymptotic regime. Both are evaluation-only quantities and neither
enters the optimizer, so Section 12's rule is preserved.

## What the threshold and the seed are actually worth

With the inspection disk and a working frequency, the threshold rule is
well-behaved, and the plan can fix its parameters from the numbers rather than
from the 3-D holography paper. Across the working band and three `C0` values, the
selected region's centroid never moves more than 3.7 mm from `c_B`, while the
equivalent-area radius moves by a factor of 5:

| f (GHz) | `C0` | regions | `r_eq` (mm) | centroid error (mm) | best accepted radius (mm) | `J` before → after |
|---:|---:|---:|---:|---:|---:|---|
| 0.25 | 0.15 | 1 | 31.38 | 1.9 | 31.38 | 0.392910 → 0.012297 |
| 0.25 | 0.20 | 1 | 36.45 | 2.0 | 36.45 | 0.392910 → **0.002722** |
| 0.25 | 0.40 | 1 | 53.01 | 1.3 | 39.76 | 0.392910 → 0.024039 |
| 0.50 | 0.15 | 1 | 15.71 | 3.7 | 15.71 | 0.194789 → 0.100858 |
| 0.50 | 0.20 | 1 | 18.16 | 3.5 | 18.16 | 0.194789 → 0.079350 |
| 0.50 | 0.40 | 1 | 26.45 | 3.4 | 26.45 | 0.194789 → 0.022093 |
| 0.75 | 0.15 | 1 | 10.76 | 1.3 | 10.76 | 0.322196 → 0.227178 |
| 0.75 | 0.20 | 1 | 12.51 | 1.5 | 12.51 | 0.322196 → 0.201827 |
| 0.75 | 0.40 | 1 | 18.31 | 1.4 | 18.31 | 0.322196 → 0.120718 |

The true radius is 35.00 mm. Three things follow.

`C0` controls size and not position. Localization is insensitive to it across
`0.15`–`0.40`, so Codex is right to keep `C0 = 0.15` as a declared default and
right that it must not be tuned from truth; the plan can additionally record that
the localization gate does not depend on the choice, which makes the deferral
honest.

`r_eq` is not a size estimator, as Codex's amendment 7 says — and the dependence
is systematic, not noisy. It falls with frequency at fixed `C0` (31.4 → 15.7 →
10.8 mm at `C0 = 0.15`) because the threshold region is a resolution cell of the
indicator, not a footprint of the object. The plan should report `r_eq` as a
scale and expect T3, not T2, to recover the radius.

Backtracking earns its place exactly once, at `C0 = 0.40 / 0.25 GHz`, where
`1.00 r_eq = 53.0 mm` overshoots and `0.75 r_eq = 39.8 mm` is much better
(`J = 0.0240` against `0.376`). Everywhere else the largest admissible radius wins
and the ladder is monotone. Keep the ladder; do not extend it downward as
amendment 7 proposes, because the small end is where the accept-in-the-wrong-place
failure lives.

The best single result available on this scene is `C0 = 0.20` at 0.25 GHz: a
36.45 mm circle proposed from the field alone, 2.0 mm from the true centre against
a true radius of 35.00 mm, cutting the objective by 99.3% in one birth event.

## On the two reviews' choices

Most of the Codex review's amendments hold up. The residual weight `w_f / s_f^2`
and the `sqrt(w_f)/s_f` factor stored in the real residual are correct
(`solvers/sdf_inverse/optimization.py:177`, `:651`). The paired forward really does
compute the full source-by-receiver matrix and take `np.diag`
(`solvers/sdf_bem_multicomponent/forward.py:578`), so the warning about the
measurement set silently widening is a real hazard. The empty-background branch
really does need defining outside `OrderedBoundary2D`, which requires at least one
component. `predict_multicomponent_kress_paired_boundary_response` really is the
right seam for ordinary objective calls. `RadialFourierCurveState` already owns a
validated `component_id`, gauge-fixes mode one to zero and certifies a positive
radius (`solvers/sdf_inverse/curve_updates.py:127`), so "1 + 2K active parameters"
gives the six variables amendment 5 wants for two `K=1` states. Three
corrections and one addition:

**The scene already exists.** Amendment 2 proposes the Cassini split-fixture
endpoint — 45 mm circles at `(0.34, 0.50)` and `(0.66, 0.50)` — and notes it must
be re-qualified because the recorded fixture used a different material pair and
1.2 GHz. That work is unnecessary. `config/two_circle_config.py` declares this
project's two-circle target directly, and
`pytest/solver_comparisons/test_two_circle_comparison.py` already exercises it at
the production material pair with a 24-pair 0.30 m ring at 0.5/1.5/2.5 GHz,
against `gpr_bem_ref`, `gpr_bem_mod`, QBX and a cached gprMax reference. The
probes here use it unchanged. The fixture endpoint should be left to the split
demo that owns it.

**The refinement guards move the admissible set.** Amendment 6, as above: qualify
by refinement, but first pin the clearance and mask thresholds in physical units,
or refinement will relax the very guards it is meant to test.

**Do not extend backtracking downward.** Amendment 7's last bullet. The smallest
resolved disk is where a wrong-place birth is most likely to be accepted, and the
measured ladders never need it.

**The TD assembly is cheaper than either document assumes.** Amendment 4 leaves
open whether the helper "reuses a retained frequency system or performs two
declared source batches", and Section 10.2 warns against looping over grid points.
Neither is necessary. `solve_multicomponent_kress_tmz_total_field_batch` solves
every right-hand side against one factorization
(`multicomponent.py:1711`), `_source_strengths` accepts one strength per source,
and `build_multicomponent_exterior_receiver_operator` takes an arbitrary point
array. So the whole per-frequency TD needs **one** call, with the sources being
the physical sources at strength `Q_f` concatenated with the receivers at
strength 1, and the receiver points being the masked inspection grid. One system
build, one LU, all right-hand sides, one operator. The only cost worth declaring
is memory: that operator holds two dense `(num_grid, num_nodes)` complex
matrices plus their `(num_grid, 2 * num_nodes)` concatenation, about 0.5 GB for a
129-by-129 grid against two 256-node components, so
the plan should either declare the grid budget or chunk the grid inside the
helper.

## What this review does not establish

Everything above is oracle arithmetic on circles. It says nothing about whether
the multi-component Kress path reproduces these numbers — that is exactly gate G0,
and amendment 2's oracle comparison is the right way to establish it. It says
nothing about T3: whether the six-variable two-component radial optimizer can
refine an accepted birth, and nothing about the T4 wrong-A case, where the
residual carries shape error as well as the missing component and the working
frequency band may differ. It uses one frequency at a time with unit weights and
one 24-pair ring; a different acquisition may move the band. And "0.25–0.75 GHz
works" is a statement about 35 mm circles 140 mm apart in `epsr = 6` sand, which
is why the plan should carry `k_e r_B` rather than the frequency.

It does establish that the derivative expression is correct and validated, that
G1 can be a regression test rather than a discovery, and that G2 and G3 are
decided by a setting neither document currently treats as decisive.

## Suggested ordering change for `03_plan.md`

Codex's eight-step order is sound except that its step 1 freezes everything at
once. Split it:

| Order | Bounded work | Evidence before advancing |
|---|---|---|
| 0 | Oracle-only T0/T1 localization sweep over frequency on the declared scene; declare the inspection disk and station clearance first | A working band, with `k_e r_B` recorded; one declared training frequency inside it |
| 1 | Freeze the rest: paired indices, holdout, node counts, absolute clearances, TD grid, `C0`, ladder, objective scales | Complete configuration, no target-derived setting |
| 2–8 | As in the Codex review | As in the Codex review, with G1 demoted to a regression test against the values in this review, and G3 carrying `e_loc` and the threshold-region count as qualifications |

## Probes

Under
[`results/validation/radial_fourier_topology/iteration-01-20260908/review-diagnostics-topological-derivative/`](../../../../../results/validation/radial_fourier_topology/iteration-01-20260908/review-diagnostics-topological-derivative/README.md):

| Probe | What it measures |
|---|---|
| `topological_derivative_asymptotics.py` | Insertion quotients against the derivative, empty and non-empty domains, 0.5 and 1.5 GHz |
| `topological_derivative_localization.py` | Frequency sweep at two grid resolutions, threshold region and seed, birth line search, birth ray |

No BEM solve, no inverse, no optimizer, no repository state touched; about 22
seconds on one thread. Every number quoted above is in the `.txt` output beside
each script.
