# Iteration 2 — Final Plan for the Implicit-MLP Inverse

Recorded 2026-09-08.

This is the controlling plan for the next implicit-MLP work. It consolidates:

- `docs/iterations/implicit_mlp/iteration_02/01_results.md`
- `docs/iterations/implicit_mlp/iteration_02/02_proposals/01_chatgpt_guide.md`
- `docs/iterations/implicit_mlp/iteration_02/02_proposals/02_codex_review.md`
- `docs/iterations/implicit_mlp/iteration_02/02_proposals/03_claude_review.md`
- `docs/iterations/implicit_mlp/iteration_01/03_plan.md`

Where these differ, give the strongest weight to the **measured frozen-state diagnostics in Claude's review**, because those probes directly interrogate the saved September-8 trajectories and close several hypotheses that the earlier proposal/review only left open.

No unchanged long wrong-start inverse is authorized by this plan.

---

## 1. Current verdict

Retain the present scientific architecture:

```text
MLP weights θ
   │
   ▼
implicit field fθ(x)
   │
   ▼
raw zero contour Γθ = {x : fθ(x)=0}
   │
   ▼
Method-B smooth boundary γθ
   │
   ▼
Kress / BIE solve
   │
   ▼
predicted data d(θ)
   │
   ▼
data objective
   │
   ▼
Kress adjoint / shape sensitivity
   │
   ▼
reverse Method B + extraction
   │
   ▼
∇θ L
   │
   ▼
neural optimizer
```

Geometry ownership remains with the MLP.

Do **not** replace the inverse by:

```text
boundary sensitivity
    -> prescribe boundary displacement
    -> refit MLP
```

The problem we are studying is specifically whether a neural parameter-space update can recover useful implicit geometry through the full differentiable extraction / Method-B / Kress pipeline.

### What iteration 2 has already ruled down

Do not use the following as the main working explanations unless new evidence reopens them:

1. **BEM/Kress accuracy is the dominant failure.**  
   Current forward refinement evidence does not support that.

2. **The SIREN simply cannot represent the target.**  
   The exact-target star fit is vastly better than the wrong-start recovery.

3. **The five-lobe star is invisible to the current data.**  
   Iteration 1 showed the tested physical modal Jacobian is full rank through modes 0–10 at the original band.

4. **The error is mainly escaping into unobserved high modes.**  
   Claude's saved-state decomposition shows the dominant error stays below mode 11.

5. **There is a large data-misfit barrier between the failed star and the truth in curve space.**  
   The tested direct curve-space transect is essentially descending toward the target.

6. **The immediate next experiment should be removing Eikonal regularization.**  
   Claude's measurements point in the opposite direction: the present Eikonal sampling scarcely constrains the interface where the failure develops.

---

# 2. Strongest new evidence from the September-8 review

These measurements should govern the next work.

## 2.1 The field progressively loses its distance-like conditioning on the contour

The inverse Eikonal term uses 512 fixed samples over the whole `0.4 x 0.4 m` box.

For the final star:

- 0 / 512 samples lie within 1 mm of the contour;
- 2 lie within 2 mm;
- 10 lie within 5 mm.

The on-contour field-gradient range evolves approximately as:

| Star state | `min ||∇f||` | `max ||∇f||` | ratio |
|---|---:|---:|---:|
| 0 | 0.820 | 1.228 | 1.50 |
| 8 | 0.823 | 1.300 | 1.58 |
| 16 | 0.797 | 1.691 | 2.12 |
| 24 | 0.738 | 2.127 | 2.88 |
| 32 | 0.698 | 2.828 | 4.05 |
| 40 | 0.496 | 3.376 | 6.80 |
| 47 | 0.347 | 3.515 | **10.14** |

The circle drifts more mildly, from approximately `1.02` spread at initialization to `1.87` by state 60.

This matters directly because local zero-set motion is

```text
V_n(x)
  = - [∂fθ(x)/∂θ · δθ]
      / ||∇x fθ(x)|| .
```

A badly varying denominator can distort both the magnitude and spectrum of the actual geometric motion even if the numerator is well behaved.

It also affects the `2 mm` maximum-boundary-motion trust region: a point with very small `||∇f||` can become the point that limits the step for the whole contour.

## 2.2 The star does not simply become a circle

The saved star transfers geometric energy away from the target `m=5` lobe into other low modes.

Representative polar amplitudes from Claude's reconstruction:

| State | `m=3` mm | `m=4` mm | `m=5` mm | `m=7` mm | radial RMS mm |
|---|---:|---:|---:|---:|---:|
| 0 | 0.061 | 0.091 | 7.166 | 0.098 | 5.077 |
| 16 | 3.461 | 1.993 | 3.310 | 0.904 | 4.282 |
| 32 | 5.864 | 4.725 | 0.674 | 3.262 | 6.250 |
| 47 | 6.232 | 5.827 | 1.648 | 4.951 | 7.676 |

At the final state:

- about `95.9%` of radial variance is in `m <= 10`;
- `m=11..20` contains only about `3.6%`;
- above `m=20` is still smaller.

So the leading failure is not "the network leaks into invisible high frequencies".

## 2.3 The failed contour still has a useful curve-space direction toward the truth

The saved curve-space interpolation from the final star toward the exact target produces nearly monotone reduction in the production data objective.

Therefore there is no evidence of a large curve-space loss barrier separating the failed shape from the truth.

This does **not** prove convexity and does not prove the neural parameterization can realize that path.

It instead shifts attention toward:

- update metric;
- neural parameterization;
- implicit-field conditioning;
- trust-region geometry;
- acquisition conditioning.

## 2.4 The correction is strongly coupled across modes

At the failed star state, several individually "correct" finite modal changes increase the data objective, while a coordinated step toward the truth decreases it.

Therefore do not interpret per-mode sensitivity as "fix mode 5, then mode 4, then ...".

The meaningful local direction may be a coupled combination of modes.

This gives a concrete reason to test a **modal Gauss-Newton / TSVD direction in curve space** before implementing any neural Gauss-Newton optimizer.

## 2.5 Circle and star are not in the same search regime

The constraint setting the next-larger rejected step differs strongly:

| Binding constraint | Star | Circle |
|---|---:|---:|
| Boundary motion | 38 | 25 |
| Conversion refinement | 8 | 0 |
| Conversion distance + refinement | 1 | 0 |
| Armijo objective | 0 | 33 |
| Mixed | 0 | 2 |

The star is effectively geometry/trust-region limited throughout the run.

The circle is often objective/Armijo limited.

So do not infer a shared mechanism merely because both eventually show non-target shape error.

## 2.6 Runtime is dominated by one geometry check, not BEM

On the profiled final star:

```text
geometry build: ~13.50 s
Kress solve for the 12-pair, two-frequency problem: ~0.195 s
```

The dominant cost is `polygon_self_intersection_count`, an `O(n^2)` pure-Python loop inside the conversion-fidelity audit.

This should be fixed first because it can make all subsequent experiments several times cheaper without changing the inverse formulation.

---

# 3. Governing research question

The next iteration should discriminate between three closely related mechanisms:

```text
A. Neural update geometry
   δθ produces the wrong numerator ∂θf · δθ.

B. Implicit-field conditioning
   the numerator may be reasonable, but badly varying ||∇f||
   distorts the zero-contour motion and trust-region behaviour.

C. Data / metric conditioning
   the physically useful correction is strongly coupled and Euclidean
   neural gradient descent is a poor metric for finding it.
```

Acquisition changes such as multistatic should be tested as a **conditioning improvement**, not as a claim that information was missing.

---

# 4. Execution order

The controlling order is:

```text
0. Exact runtime bottleneck repair
1. Saved-state field / geometry characterization
2. Curve-space local metric diagnostic
3. Neural weight -> raw / converted motion diagnostic
4. Frozen field-conditioning repair test
5. Conditional contour-aware Eikonal sampling ablation
6. Fresh optimizer-direction instrumentation
7. Paired-8 vs multistatic-8 short neural comparison
8. Conditional high-frequency multistatic comparison
9. Conditional neural GN / TSVD diagnostic
```

Run the ellipse startup qualification and the frozen late-star conversion audit in parallel once the cheap geometry code is fixed.

Do not authorize a long inverse before the bounded report from these stages is reviewed.

---

# 5. Stage 0 — remove the polygon self-intersection bottleneck

## Goal

Accelerate `polygon_self_intersection_count` without changing its semantics.

## Implementation

Prefer a chunked vectorized implementation of the existing segment-intersection test.

Do not replace it with:

- an approximate spatial heuristic;
- a different topology criterion;
- a relaxed tolerance;
- a library call whose degeneracy semantics differ silently.

## Validation corpus

Replay saved polygons from:

- accepted circle states;
- accepted star states;
- star geometry-rejected candidates;
- base and refined conversion audits;
- near-self-intersection cases.

Require exact integer equality:

```text
new_intersection_count == old_intersection_count
```

for every saved polygon.

Also require identical:

- topology pass/fail;
- conversion-fidelity pass/fail;
- trial rejection reason.

Then benchmark representative circle and star geometry builds.

Only after exact replay equivalence may the new path replace production.

---

# 6. Stage 1 — characterize all selected saved states

Restore the real trajectory weights, not reconstructed surrogates.

Use at least:

### Circle

- state 55;
- state 60.

### Wrong-start star

- state 0;
- state 16;
- state 32;
- state 40;
- state 47.

### Target-fitted star

- state 0;
- each of the available accepted updates.

For every state record:

```text
raw zero contour
Method-B boundary
training data objective
conversion distance
conversion refinement change
min / max / RMS ||∇f|| on raw contour
perimeter
center
radial / arc-length modal spectrum
```

Also record the binding step-size constraint for the historical transition where available.

Any newly evaluated gradient or metric must be labelled:

```text
fresh frozen-state evaluation
```

rather than presented as a historical logged quantity.

---

# 7. Stage 2 — curve-space metric diagnostic before neural GN

This is deliberately done **before** building a neural optimizer.

## 7.1 Local curve basis

At selected frozen Method-B curves, parameterize by arc length `s` and use a normalized normal-motion basis

```text
1
cos(2πms/L)
sin(2πms/L)
```

through at least:

```text
m = 1 ... 12
```

giving 25 real curve-space degrees of freedom including the constant mode.

## 7.2 Residual Jacobian

Build the Jacobian of the same normalized real-stacked production data residual with respect to these curve modes.

Use:

- verified Kress shape derivatives where practical; or
- resolved finite differences on the explicit frozen curve.

The synthetic truth must **not** be used to construct the direction.

## 7.3 Directions

Compute at least:

```text
steepest descent in modal coordinates
damped Gauss-Newton
TSVD Gauss-Newton
```

with declared:

- basis normalization;
- damping;
- truncation threshold;
- residual normalization.

## 7.4 Evaluate after the direction is computed

Only then compare with the known synthetic geometric error:

- signed alignment with target correction;
- actual objective decrease;
- modal composition;
- accepted finite step before geometry degradation.

## Decision

### If curve-space GN is useful and neural motion is poor

Strong evidence that the physical inverse has a coordinated correction but the neural metric / field parameterization prevents reaching it.

Then neural metric diagnostics become justified.

### If curve-space GN is also poor

Do not expect a neural GN optimizer alone to fix the problem.

Prioritize acquisition conditioning or local nonlinearity instead.

---

# 8. Stage 3 — weight-space update to raw and converted geometry

This remains the main missing mechanistic diagnostic.

For the current field:

```text
fθ(x) = 0
```

define for a weight direction `δθ`:

```text
N(s) = ∂fθ/∂θ · δθ
G(s) = ||∇x fθ||
V_n(s) = -N(s) / G(s)
```

## 8.1 Report all three quantities separately

For every tested direction report:

```text
N(s)
G(s)
1/G(s)
V_n(s)
```

and their spectra.

This distinction is mandatory.

Without it, these two failure mechanisms are confounded:

```text
bad neural direction
vs
good numerator distorted by loss of SDF conditioning
```

Do not clip low values of `G`.

Record them.

## 8.2 Directions to compare

At selected states compute:

```text
-g_data
-lambda_eik * g_eik
-(g_data + lambda_eik*g_eik)
production fallback
actual accepted Δθ
```

Use historical Adam directions only if true saved moments/proposals exist.

Do not fabricate a historical Adam proposal.

For every direction report both:

1. actual proposal scale;
2. common rescaled small RMS predicted boundary motion.

This separates direction shape from magnitude.

## 8.3 Validate the implicit-function prediction

For several small `alpha`:

```text
θ_new = θ + alpha * δθ
```

then re-extract the zero contour.

Compare the predicted displacement

```text
alpha * V_n * n
```

against actual signed normal displacement.

Use geometric normal correspondence, not equal node index after reparameterization.

Require a first-order convergence window before interpreting the result.

## 8.4 Raw contour versus Method-B boundary

For the same perturbation distinguish:

```text
predicted raw zero-contour motion
actual re-extracted raw-contour motion
actual re-converted Method-B motion
```

The Kress objective sees the last one.

Static contour fidelity does not prove differential fidelity.

Where available, compare against the existing discrete extraction / Method-B pullback.

## 8.5 Modal analysis

Use an arc-length-weighted orthonormal basis through at least `m=20`.

Report:

```text
m=0..5 energy
m=6..10 energy
m=11..20 energy
unresolved residual
```

But do not interpret high modes as automatically harmful.

For each mode, score **signed geometric effect** relative to the current error.

For the star explicitly track:

```text
m=3
m=4
m=5
m=6
m=7
m=9
```

For the circle report whether the update creates or removes its existing noncircular components.

## 8.6 Objective derivative check

Also verify:

```text
g_data · δθ
```

against the fresh full-pipeline objective difference.

This checks the implemented discrete derivative separately from the raw-interface formula.

---

# 9. Stage 4 — frozen field-conditioning repair

This is the cheapest causal test for the strongest new hypothesis.

Do **not** involve BEM.

At at least:

- star state 32 or 40;
- star state 47;

freeze the geometric interface and run a short field-only repair.

## Objective

Use a deterministic near-interface Eikonal penalty:

```text
R_band
  = mean (||∇x f|| - 1)^2
```

with a strong zero-level anchor on the frozen contour:

```text
R_zero
  = mean fθ(xΓ)^2
```

Optimize only:

```text
R_band + β R_zero
```

No data loss.

No Kress.

The purpose is not to improve the target geometry.

The purpose is to repair the **field conditioning while holding the zero set approximately fixed**.

## After repair measure

- max raw-contour movement;
- RMS raw-contour movement;
- `min/max/RMS ||∇f||` on contour;
- conversion distance;
- refinement-change metric;
- raw/converted contour discrepancy;
- branch consistency.

## Interpretation

### Outcome A

```text
||∇f|| improves strongly
conversion metrics improve strongly
contour barely moves
```

Then loss of field conditioning is causally upstream of the conversion / trust-region failure.

Promote a contour-aware Eikonal sampling experiment.

### Outcome B

```text
||∇f|| improves
conversion metrics do not improve
```

Then the actual contour / Method-B representation is the stronger cause of the conversion deterioration.

### Outcome C

The field cannot be repaired without large contour movement.

Then the neural parameterization itself may couple value/gradient control too strongly, and that should be documented before changing the inverse objective.

---

# 10. Stage 5 — conditional contour-aware Eikonal sampling experiment

Run this only if Stage 4 supports the field-conditioning hypothesis.

Do **not** remove the Eikonal regularizer.

Change only its sampling.

## Baseline

Current:

```text
512 fixed uniform box samples
lambda_eik = 0.01
```

## Proposed comparison arm

Keep:

```text
lambda_eik = 0.01
total samples = 512
```

Use:

```text
256 seeded global box samples
256 deterministic near-contour samples
```

Construct the contour samples from uniform arc-length points on the current accepted raw contour with deterministic signed normal offsets spanning approximately:

```text
[-5 mm, +5 mm]
```

### Line-search bookkeeping

The sample set must remain fixed through a single line search.

After a new state is accepted:

1. rebuild the near-contour sample set;
2. compute the accepted state's regularizer on the new set;
3. use that value as the reference regularized objective for the next line search.

Log the sample-set hash.

This means the regularized objective is iteration-local.

The data objective remains globally comparable.

Document that distinction.

## Short matched test

Start baseline and contour-aware arms from identical saved weights and optimizer state.

Do not change:

- acquisition;
- frequencies;
- Method B;
- fidelity limits;
- trust region;
- optimizer;
- network;
- line-search rules.

Required outputs:

- train data loss;
- regularized loss;
- on-contour `||∇f||`;
- raw/converted motion;
- modal trajectory;
- conversion metrics;
- rejection reasons.

If contour-aware sampling stabilizes the field and improves geometric motion under identical physics, it becomes a candidate principal factor for the next long comparison.

---

# 11. Stage 6 — fresh optimizer geometry

Historical Adam moments are not available.

Therefore do not claim Adam caused the historical failure unless new matched experiments show it.

Instrument every fresh short test to save:

```text
Adam m
Adam v
step count
gradient clipping
raw Adam proposal
every backtrack factor
fallback proposal
fallback reset
```

At matched states compare:

```text
data-only steepest descent
total-gradient steepest descent
actual Adam proposal
fallback
```

using the same:

```text
N(s)
G(s)
V_n(s)
raw contour motion
Method-B motion
modal decomposition
```

A change away from Adam is justified only if actual saved proposals repeatedly distort a demonstrably useful total-gradient direction.

A poor Euclidean gradient does **not** rule out GN/TSVD; it instead motivates a metric-aware step.

---

# 12. Stage 7 — first acquisition experiment: paired-8 vs multistatic-8

Multistatic remains the first acquisition change.

Its rationale is:

```text
better conditioning of a strongly coupled local inverse
```

not:

```text
paired data cannot see the lobes
```

## Comparison

From exactly the same wrong-start MLP weights:

```text
E0: paired-8,      0.5 / 1.5 GHz
E1: multistatic-8, 0.5 / 1.5 GHz
```

Hold fixed:

- MLP architecture;
- initial weights;
- pretraining;
- optimizer state;
- Method-B configuration;
- conversion tolerances;
- trust region;
- Eikonal coefficient;
- whichever sampling scheme was selected by the prior isolated test;
- two frequency terms;
- materials and ring geometry.

## Integration gate

Before the short inverse, validate the complete indexed neural path:

- observation ordering vs independent oracle;
- paired selection equivalence;
- normalized neural directional derivative;
- rollback after rejected candidates;
- starting-curve forward refinement;
- starting-curve derivative refinement.

## Objective normalization

Preserve the existing convention:

```text
L_data
  = 0.5 * sum_f w_f * ||d_f - d_obs,f||^2 / s_f^2
```

with:

- fixed observed-column norm scale `s_f`;
- two unit frequency weights;
- no extra division by number of entries.

Record the resulting data/Eikonal gradient magnitudes in both arms because multistatic changes response norms.

## Evaluation

Use a fixed disjoint validated 3 GHz evaluation acquisition.

Never use it in line-search acceptance or step selection.

## Work cap

Per arm stop at the first of:

```text
5 accepted updates
120 attempted candidate evaluations
declared wall-time cap
```

Once the geometry bottleneck is repaired, these caps can later be relaxed deliberately, but not silently.

## Success criterion

Multistatic is promoted only if it improves the **actual neural geometric trajectory**, for example:

- better coordinated signed correction;
- stronger recovery of target `m=5` without growth of wrong modes;
- lower geometric error at comparable work;
- more stable conversion / field conditioning.

A lower training loss or a better frozen Jacobian condition number alone is insufficient.

---

# 13. Stage 8 — conditional higher-frequency multistatic comparison

Only run if the original-band multistatic arm remains limited in a way consistent with conditioning.

Compare:

```text
F0: multistatic-8, 0.5 / 1.5 GHz
F1: multistatic-8, 1.5 / 2.5 GHz
```

from the same frozen starting state.

Keep:

- optimizer;
- regularizer;
- geometry settings;
- two frequency terms;
- work cap;
- normalization convention.

The same 3 GHz evaluation acquisition may remain disjoint.

Once 2.5 GHz is training data, it is not a holdout.

A successful high-band direct run supports a frequency change.

It does **not** prove continuation is needed.

Continuation remains deferred until a staged path is compared against a direct run at comparable work.

---

# 14. Stage 9 — conditional neural GN / TSVD

Promote this only if the earlier diagnostics show:

```text
curve-space GN direction is useful
neural gradient / Adam motion is not
field conditioning alone does not resolve the mismatch
acquisition change does not already give a simpler repair
```

Use the Jacobian of the same normalized real-stacked residual through:

```text
MLP
 -> extraction
 -> Method B
 -> Kress
 -> observations
```

Test at frozen states:

```text
delta_theta
  = -J^T (J J^T + mu I)^(-1) r
```

and/or TSVD.

Declare:

- parameter scaling;
- damping `mu`;
- TSVD cutoff;
- Eikonal treatment.

Do not confuse damping with the Eikonal regularization coefficient.

Compare:

- predicted residual decrease;
- actual residual decrease;
- raw contour motion;
- Method-B motion;
- modal alignment;
- geometry/fidelity acceptance.

A smaller linearized residual is not enough.

The step must produce a better admissible geometric direction.

---

# 15. Separate late-star conversion audit

The terminal conversion-refinement stop is a separate question from why the shape became wrong.

At late saved star states vary independently:

```text
production extraction / Method-B resolution
independent fidelity-audit resolution
```

Do not let the audit silently derive its resolution from production settings during the diagnostic.

Record:

- raw -> converted directed distance;
- converted -> raw directed distance;
- base-level fidelity error;
- refined-level fidelity error;
- refinement change;
- branch consistency;
- topology;
- on-contour `||∇f||`.

Keep limits fixed:

```text
conversion distance <= 0.2 mm
refinement change <= 0.01 mm
```

Interpret the stop as potentially containing three effects:

```text
1. audit-resolution sensitivity
2. genuinely harder contour / Method-B representation
3. degraded implicit-field conditioning
```

Stage 4 is the causal test for effect 3.

Do not relax the limits.

Do not interpret a microscopic accepted step as recovery.

---

# 16. Circle control

Keep the circle because it is the cleanest nearly-correct geometry.

But always report the binding search constraint.

At states 55 and 60 measure the same:

```text
N(s)
G(s)
V_n(s)
raw motion
Method-B motion
signed modal effect
```

Ask:

```text
Does the late update create noncircular error?
Does it correct some modes while worsening others?
Does most discrepancy enter during Method-B conversion?
Is the field-gradient drift involved even though the run is Armijo-limited?
```

Do not force a shared star/circle explanation if the measured mechanisms differ.

---

# 17. Ellipse startup task

The missing ellipse run is an execution / representation gap, not an accuracy result.

Before another inverse:

1. persist per-case stdout;
2. persist stderr and traceback;
3. save freshly pretrained initial weights **before any geometry construction**;
4. identify the exact failing stage;
5. audit exactly those saved weights;
6. qualify extraction / Method-B resolution independently for that ellipse initialization;
7. keep the same `0.2 mm` and `0.01 mm` fidelity limits.

Do not assume the circle settings are valid for the ellipse.

Once the initialization is topology-valid and independently resolved, run only a short smoke inverse.

Do not schedule a new 60-update ellipse run during this diagnostic cycle.

---

# 18. Decision tree for the next long star experiment

No long inverse is authorized until the bounded diagnostics are summarized.

Choose **one principal factor only**.

## A. Contour-aware Eikonal sampling

Choose if:

- frozen field-only repair improves `||∇f||`;
- conversion metrics improve with little contour motion;
- the short matched inverse preserves field conditioning and improves geometric motion.

## B. Multistatic acquisition

Choose if:

- field-conditioning ambiguity is controlled;
- multistatic gives a clearly better actual-MLP geometric trajectory than paired-8 at matched work.

## C. Higher-frequency multistatic

Choose if:

- multistatic original band remains conditioning-limited;
- 1.5 / 2.5 GHz gives a clear additional geometric benefit in the matched short test.

## D. Neural GN / TSVD metric

Choose if:

- curve-space GN gives a useful coordinated direction;
- neural steepest descent / Adam does not;
- a frozen neural GN/TSVD direction gives a better admissible interface motion.

## E. No factor yet

If none of the gates are met:

```text
do not manufacture a long run
```

Record the mechanism as unresolved and design the next bounded diagnostic.

---

# 19. When the next long run is eventually authorized

Start with **star only**.

Do not immediately rerun the three-case suite.

Keep:

- fixed saved wrong-start initialization;
- validated Kress / adjoint;
- MLP geometry ownership;
- Method-B fidelity limits;
- rollback checks;
- 60 accepted-update cap unless separately justified;
- fixed disjoint 3 GHz evaluation set;
- identical control arm where required.

Change exactly one selected principal factor.

Report jointly:

```text
training objective
evaluation objective
raw contour error
Method-B boundary error
modal trajectory
on-contour ||∇f||
conversion metrics
binding search constraints
attempted evaluations
accepted updates
runtime
```

Falling training loss alone is never success.

---

# 20. Explicit deferrals

Without new evidence, do **not**:

- enlarge the SIREN;
- redesign the whole pretraining objective again;
- remove inverse Eikonal regularization;
- relax conversion tolerances;
- repeatedly deepen backtracking;
- switch geometry ownership to an explicit curve;
- update the boundary and refit the MLP;
- redesign Kress;
- blame BEM accuracy;
- add generic weight decay;
- add ad-hoc smoothness penalties;
- use higher frequency merely because the target has five lobes;
- implement continuation without a direct matched comparison;
- integrate production neural GN / IRGN before qualifying its frozen-state geometric direction.

---

# 21. Required handoff table

Before proposing the next long experiment, fill this table from measurements.

| Question | Measured answer |
|---|---|
| Does the implicit-function prediction match actual raw contour motion? | |
| Does Method B preserve or distort that differential motion? | |
| Is harmful modal content present in `∂θf·δθ`, introduced mainly by `1/||∇f||`, or both? | |
| Does the raw data-gradient direction align with the coordinated geometric correction? | |
| Does the current Eikonal term materially control the interface? | |
| Does the frozen near-contour field repair improve conditioning with little contour movement? | |
| Does contour-aware Eikonal sampling improve a matched short inverse? | |
| Does curve-space modal GN / TSVD recover a useful coordinated local direction? | |
| Does actual Adam distort a useful total-gradient direction? | |
| Does multistatic improve actual neural geometry at matched work? | |
| Does the high-frequency multistatic arm add geometric benefit? | |
| What actually causes the late-star conversion stop? | |
| Is the ellipse initialization reproducibly valid at qualified resolution? | |
| Which single factor, if any, is justified for the next long star comparison? | |

---

# 22. Final working interpretation

The current evidence supports the following narrower statement:

```text
The tested physical inverse is locally informative and the target geometry is
representable, but the full neural inverse can move the zero contour in a
poorly conditioned, strongly coupled geometric direction while the implicit
field itself progressively loses its distance-like behaviour near the
interface.
```

The next iteration should therefore determine, in this order:

```text
field conditioning?
        │
        ▼
curve-space metric / coupled correction?
        │
        ▼
neural update -> actual interface motion?
        │
        ▼
regularizer sampling?
        │
        ▼
acquisition conditioning?
        │
        ▼
neural metric / GN?
```

Only the measured result of those tests should choose the next expensive inverse.
