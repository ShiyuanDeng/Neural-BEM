# ChatGPT proposal: iteration 2 next steps for the implicit-MLP inverse

This is the **first proposal for iteration 2**. It is based on
`01_results.md` and the closed decisions from iteration 1. It is not an agreed
plan and should be reviewed before any new long inverse is launched.

## Repository state

Work from:

- repository: `ShiyuanDeng/Neural-BEM`
- branch: `feature/ordered-boundary-nystrom`

Read first:

- `docs/iterations/implicit_mlp/iteration_02/01_results.md`
- `docs/iterations/implicit_mlp/iteration_01/03_plan.md`
- `docs/pipelines/implicit_mlp.md`
- `solvers/sdf_inverse/implicit_adjoint.py`
- `solvers/sdf_inverse/geometry.py`
- `solvers/sdf_inverse/method_b_pullback.py`
- `solvers/gpr_bem_kress/shape_derivative.py`

Do not reinterpret iteration-1 diagnostics as full neural recovery. Do not
rewrite validated Kress, extraction, Method B or pullback components merely to
make the next experiments convenient.

---

# 1. What iteration 2 establishes

The repaired 12-pair wrong-start suite still does **not** recover the neural
geometry.

Measured outcomes:

- circle:
  - 60 accepted updates;
  - train relative L2 `0.002061`;
  - holdout relative L2 `0.061283`;
  - center error `0.0514 mm`;
  - radius error `0.0137 mm`;
  - maximum sampled boundary error `1.069 mm`;
- star:
  - 47 accepted updates;
  - train relative L2 `0.482413`;
  - holdout relative L2 `0.862650`;
  - maximum sampled boundary error `37.368 mm`;
  - fitted lobe amplitude collapses from about `0.11966` to `0.02072`, while
    the target amplitude is `0.25`;
- ellipse-to-circle:
  - exits before saving a result bundle, so no inverse-accuracy conclusion is
    available.

The completed circle and star runs take about 128 minutes of recorded inverse
time and together attempt more than 800 training evaluations. Therefore the
next work should be bounded diagnostics, not another unchanged 60-step suite.

---

# 2. What should no longer be the main working explanation

Iteration 1 already established:

- the five-parameter star recovers with **8 or 12 paired views** at
  `0.5 / 1.5 GHz`;
- the stacked original-band local normal-mode Jacobian is full rank for the
  tested 21 real modes `m = 0..10`;
- multistatic readout improves local modal conditioning;
- `1.5 / 2.5 GHz` improves the weakest tested multistatic modal direction;
- the target-fitted MLP admits a short local data-descent neighborhood.

Therefore iteration 2 should **not** start from either claim:

```text
the star fails because 8/12 paired measurements cannot see the five lobes
```

or:

```text
the star categorically requires higher frequency
```

The measured local controls do not support either statement.

Likewise, insufficient network capacity alone is not a sufficient explanation:
the same fitting procedure reaches about `1.191 mm` target-fit star error while
the wrong-start inverse ends near `37 mm`.

---

# 3. Main new hypothesis

The strongest iteration-2 clue is common to circle and star:

```text
data loss can keep decreasing while geometric accuracy stops improving or
actively worsens.
```

For circle, states 55 to 60 reduce training relative L2 while sampled boundary
error grows from about `0.982 mm` to `1.069 mm`.

For star, data loss falls substantially while the defining five-lobe amplitude
collapses toward zero.

The target-fitted MLP from iteration 1 also reduced both training and 3 GHz
evaluation error over three accepted steps while sampled boundary error changed
from `1.191 mm` to `1.290 mm`.

This motivates the following **working hypothesis**:

> The remaining failure may lie in the geometry induced by high-dimensional
> neural weight updates: a weight-space descent direction can improve the
> measured fields without producing a useful normal motion of the MLP zero
> contour.

This is not yet established. The next diagnostic should measure it directly.

---

# 4. Priority A — measure neural weight update -> boundary motion

This is the main iteration-2 diagnostic.

## 4.1 Mathematical quantity

For the current neural implicit field

```text
f_theta(x) = 0,   x on Gamma
```

and a small weight perturbation `delta_theta`, the first-order normal motion of
the zero contour is

```text
V_n(x)
  = - [d f_theta(x) / d theta @ delta_theta]
      / ||grad_x f_theta(x)|| .
```

Use the production sign convention and verify the sign and magnitude against
actual re-extracted contours before interpreting it.

This is **diagnostic only**.

Do not change geometry ownership and do not implement:

```text
boundary sensitivity -> prescribed boundary motion -> refit MLP
```

as the inverse update.

The question is only:

```text
what boundary motion does the existing neural update imply?
```

## 4.2 Frozen states

Use available real saved states where possible.

At minimum:

- circle late state, preferably around state 55 and final state;
- star initial accepted state;
- star one early/intermediate accepted state;
- star late state before the terminal conversion-refinement stop;
- target-fitted star MLP initial state.

If a historical checkpoint does not contain the required model or optimizer
state, skip only the unavailable quantity and record the limitation. Do not
construct a substitute and present it as the saved run.

## 4.3 Directions to compare

At each frozen state compute the induced boundary motion for:

```text
-g_data
-lambda * g_eik
-g_total = -(g_data + lambda*g_eik)
fallback steepest-descent direction
```

Also compare:

```text
actual accepted delta_theta
```

between consecutive saved accepted states when both states are available.

For Adam:

- use the actual first/second moments if they are genuinely available;
- otherwise do not synthesize a historical Adam proposal.

A fresh controlled state may later be used to compare raw gradient and actual
Adam proposal under saved optimizer moments.

## 4.4 Boundary spectral content

Parameterize the current ordered boundary by arc length `s`, perimeter `L`.

Project `V_n(s)` onto

```text
1
cos(2*pi*m*s/L)
sin(2*pi*m*s/L)
```

for at least

```text
m = 1..20
```

not only `m <= 10`.

Iteration 1 established observability only for modes 0–10. The neural update
could inject significant higher-frequency contour motion outside that tested
space.

Record:

- RMS normal motion;
- maximum normal motion;
- coefficient magnitude for each mode;
- fraction of motion energy in:
  - `m = 0..5`;
  - `m = 6..10`;
  - `m = 11..20`;
- residual energy beyond the fitted modal range;
- for the star, correlation with the physical amplitude and rotation
  perturbation directions;
- for the circle, total noncircular energy `m >= 2`.

Do not equate an arc-length mode directly with the radial star parameter away
from a circle; treat the modal basis as a local geometric decomposition.

---

# 5. Priority B — validate the induced-motion diagnostic

Before using the modal decomposition scientifically, verify the zero-set
linearization.

For several small scale factors `alpha`, compare

```text
first-order prediction:
x_pred = x + alpha * V_n * n
```

with

```text
actual candidate:
theta_new = theta + alpha * delta_theta
-> re-extract zero contour
-> compare normal displacement
```

Use several perturbation magnitudes and show a convergence window.

Required checks:

- regular contour branch;
- same component/order association;
- sign of normal motion;
- RMS displacement error;
- maximum displacement error;
- first-order error decrease as `alpha -> 0`.

Do not use branch-changing or topology-changing perturbations to validate this
local formula.

---

# 6. Priority C — data gradient versus Eikonal geometry

Iteration 2 records data- and Eikonal-gradient norms, but the report correctly
states that norms do not determine whether the regularizer helps or hurts.

Compute both:

```text
weight-space cosine:
cos(g_data, lambda*g_eik)
```

and, more importantly,

```text
boundary-space cosine:
cos(V_data, V_eik)
cos(V_data, V_total)
```

Also compare their spectra.

Questions to answer:

1. Does the Eikonal term materially move the boundary?
2. Does it reinforce or oppose the data-induced low-order motion?
3. Does it inject higher contour modes?
4. Does it mostly alter the off-boundary field while barely moving the contour?

## Decision

Only if the Eikonal-induced boundary motion is demonstrably harmful should an
inverse-Eikonal ablation be promoted.

Do not remove Eikonal simply because its gradient norm is non-negligible.

---

# 7. Priority D — compare raw data descent with optimizer-induced geometry

The next optimizer question is not merely whether Adam lowers the objective.

At a fresh controlled state where optimizer moments can be saved, compare:

```text
raw data steepest descent
total-gradient steepest descent
actual Adam proposal
fallback proposal
```

through the same induced-boundary-motion diagnostic.

A possible mechanism worth testing is:

```text
g_data = J^T r
```

while Adam applies coordinate-dependent preconditioning in weight space.

This can change the geometric contour motion even when both directions lower
the data objective.

Do **not** claim Adam is the cause in advance.

An optimizer change becomes justified only if, at matched states:

- the raw data-gradient motion contains useful physical/modal shape content;
- Adam systematically suppresses/reverses it or injects undesirable modes;
- the effect repeats at more than one state.

If the raw data-gradient motion is already geometrically poor, replacing Adam
alone is not the right first fix.

---

# 8. Priority E — short multistatic neural ablation

Iteration 1 measured that multistatic-8 improves modal conditioning, and indexed
multistatic forward/adjoint support is implemented and validated. The production
neural inverse still uses paired readout.

This should now be tested on the **actual MLP**, but only with a short matched
run first.

Compare from identical wrong-start neural weights:

```text
E0: paired-8,      {0.5, 1.5} GHz
E1: multistatic-8, {0.5, 1.5} GHz
```

Keep fixed:

- MLP architecture;
- seed and exact initial weights;
- pretraining result;
- Method-B configuration;
- conversion tolerances;
- inverse Eikonal weight;
- optimizer settings;
- maximum boundary motion;
- number of frequency terms;
- accepted-update budget.

Use only around 3–5 accepted updates initially.

Record:

- train loss;
- fixed disjoint evaluation loss;
- center/radius;
- star amplitude/rotation;
- maximum sampled boundary error;
- rejection reasons;
- induced boundary-motion spectrum for each accepted update.

## Scaling requirement

Iteration 1 showed that absolute and target-relative multistatic sensitivity can
tell different stories because the multistatic response norm is larger.

The neural comparison must explicitly define residual normalization and keep
its effective balance with the Eikonal term comparable.

Do not attribute a change to "more information" if the loss/regularizer scaling
also changed unintentionally.

## Decision

If multistatic immediately improves actual lobe motion or reduces harmful modal
leakage, authorize one long multistatic wrong-start star run.

If conditioning improves but actual neural geometry behaves the same way, move
the focus toward neural update geometry / optimizer rather than another
acquisition expansion.

---

# 9. Priority F — short frequency ablation after multistatic

Iteration 1 measured a local modal benefit from replacing multistatic
`{0.5,1.5}` with `{1.5,2.5}` GHz.

Do not jump directly to continuation.

First compare, from the same frozen starting MLP:

```text
F0: multistatic-8, {0.5, 1.5} GHz
F1: multistatic-8, {1.5, 2.5} GHz
```

Keep two frequency terms in both arms.

Again use only a short 3–5 accepted-update budget.

The question is:

```text
does the measured local frequency benefit translate into better actual neural
boundary motion?
```

If yes, continuation becomes justified.

If no, do not spend a long run on frequency continuation yet.

---

# 10. Conditional next optimizer — neural GN / TSVD diagnostic

Do not implement a production Gauss-Newton optimizer immediately.

Promote this only if:

- physical/modal observability remains adequate;
- short multistatic/frequency tests do not resolve the neural geometry;
- or the raw gradient looks geometrically better than Adam.

For real-stacked residual `r` and neural Jacobian `J`, test a diagnostic step

```text
delta_theta
  = -J^T (J J^T + lambda I)^(-1) r
```

and/or a TSVD form.

Compare its **induced boundary motion** with raw steepest descent and Adam.

Important caveat:

- Euclidean minimum weight norm depends on neural parameterization and scale;
- per-layer or parameter-group scaling must be declared;
- a damped GN step is not automatically a prior-centered IRGN method.

The success criterion is geometric:

- useful low-order/star-mode alignment;
- reduced harmful high-mode leakage;
- accepted actual-network candidate;
- improved shape trajectory.

A smaller linearized residual alone is insufficient.

---

# 11. Star terminal conversion-refinement stop

Treat this separately from the lobe-collapse problem.

Iteration 2 shows:

- final accepted conversion distance remains below the `0.2 mm` limit;
- final refinement change is `0.00998257 mm`, almost exactly at the
  `0.01 mm` limit;
- terminal Adam and fallback candidates fail the refinement check;
- the last accepted movements are extremely small.

Perform a frozen-state audit varying **production conversion resolution** and
**independent audit resolution** separately.

Check:

- Method-B bandwidth;
- extraction grid;
- projected samples;
- audit grid/sampling;
- branch consistency;
- raw/converted contour distance;
- refinement-change stability.

Goal:

```text
determine whether the refinement metric is numerically sensitive at this state
or whether the evolving neural contour is genuinely becoming harder to
represent consistently.
```

Do not:

- relax the `0.01 mm` limit;
- indefinitely increase backtracking;
- interpret a microscopic accepted step as recovery.

The star lobes have already collapsed before the terminal stop, so this audit
does not replace the update-geometry study.

---

# 12. Circle as a clean update-geometry control

Keep the circle in the main diagnostic.

Iteration 2 gives an unusually clean situation:

- center essentially correct;
- radius essentially correct;
- residual boundary error about `1.07 mm`;
- late data loss decreases while boundary error rises.

For late circle states, compute the induced normal-motion spectrum and ask:

```text
why does an almost-correct circle continue generating noncircular m >= 2
motion while improving the field objective?
```

If circle and star show the same pattern, that strongly supports a general
neural update-geometry mechanism rather than a star-specific acquisition issue.

---

# 13. Ellipse: close the execution gap before another inverse

Treat the missing ellipse run as a separate engineering/representation task.

Current source-supported evidence is only:

- production run exited with code 1 and saved no result bundle;
- no production traceback was persisted;
- a separate archived September-7 initialization fails the September-8
  conversion checks badly:
  - conversion distance `3.211626 mm` vs `0.2 mm`;
  - refinement change `0.073997 mm` vs `0.01 mm`.

Before rerunning ellipse:

1. persist per-case stdout/stderr and traceback;
2. save the freshly pretrained initial neural weights before geometry
   construction;
3. audit exactly those weights;
4. independently refine ellipse conversion resolution;
5. demonstrate a valid initial contour under unchanged tolerances;
6. only then authorize an inverse.

Do not claim the archived probe reproduced the original exception exactly.

Do not reuse circle resolution as an assumed ellipse-valid setting.

---

# 14. Runtime profiling

Before globally increasing any geometry resolution, profile the actual candidate
evaluation path.

Measure separately:

```text
MLP evaluation
zero-set extraction
projection
conversion-fidelity audit
Method-B fitting
Kress assembly
Kress solve
adjoint solve
geometry / Method-B pullback
Eikonal evaluation
post-optimization evaluation replay
```

Count:

- geometry-rejected candidates;
- candidates that reach BEM;
- accepted candidates.

Iteration 2 rejects hundreds of trials, many before a data loss is even
evaluated. Do not assume BEM is the dominant runtime without measurement.

Any optimization must preserve numerical acceptance results and all fidelity
checks.

---

# 15. Recommended execution order

## Main research path

```text
[ ] A1. Implement delta_theta -> induced V_n on the current zero contour.
[ ] A2. Validate V_n against actual re-extracted candidate contours.
[ ] A3. Decompose V_n into modes 0..20.
[ ] C1. Compare data, Eikonal and total-gradient boundary motion.
[ ] D1. Compare raw steepest descent, fallback and fresh actual Adam motion.
[ ] E1. Run short paired-8 vs multistatic-8 neural ablation.
[ ] F1. Run short multistatic original-band vs 1.5/2.5-GHz ablation.
```

## Parallel bounded engineering tasks

```text
[ ] S1. Frozen final-star conversion/refinement audit.
[ ] X1. Persist ellipse failure logs and save fresh initial weights.
[ ] X2. Qualify ellipse initial conversion before any inverse.
[ ] P1. Profile candidate evaluation costs.
```

Stop after the short acquisition/frequency ablations and write a review before
authorizing a new long wrong-start inverse.

---

# 16. Decision table required before the next long run

The review should answer:

| Question | Measured answer |
|---|---|
| Does raw data descent induce useful geometric motion? | |
| Does the Eikonal term help, cancel or add harmful modes? | |
| Does Adam materially distort the raw-gradient boundary motion? | |
| Are modes above 10 important in neural updates? | |
| Does the same non-target modal leakage appear in both circle and star? | |
| Does multistatic improve **actual MLP geometry**, not just local Jacobian conditioning? | |
| Does the 1.5/2.5 GHz band improve actual MLP geometry beyond multistatic original-band data? | |
| Is the final star refinement stop numerical-audit sensitivity or genuine contour complexity? | |
| Is ellipse initialization valid under a separately qualified conversion resolution? | |
| Which single change is justified for the next expensive comparison? | |

Only one principal factor should change in the next long inverse.

---

# 17. What should remain deferred

Without new evidence, do not:

- enlarge the SIREN;
- weaken conversion-distance or refinement-change tolerances;
- switch geometry ownership to an explicit curve;
- reintroduce boundary-to-MLP fitting;
- repeatedly increase the line-search/backtracking budget;
- redesign Kress quadrature;
- add higher frequencies solely because the target has five lobes;
- add generic weight decay or smoothness penalties;
- implement a full neural GN/IRGN optimizer before comparing its geometric
  direction with the existing ones.

---

# 18. Proposed iteration-2 verdict if the diagnostics support the hypothesis

The working research direction is:

```text
The local physical inverse is informative and the boundary representation is
capable, but a descent direction in the 8,577-dimensional neural parameter
space can induce a zero-contour motion that is poorly aligned with geometric
recovery.
```

The immediate task is therefore not to prescribe a better boundary update, but
to **measure the geometric motion induced by the existing neural update**.

Only after that measurement should iteration 2 choose between:

1. multistatic acquisition;
2. higher-frequency data;
3. modified regularization;
4. continuation;
5. a data-space GN / TSVD / IRGN-style neural update.

The chosen fix should be the one supported by the bounded diagnostics, not the
one that merely lowers the training objective fastest.
