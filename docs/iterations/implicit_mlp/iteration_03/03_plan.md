# Iteration 3 — final plan and decisions

Consolidated 2026-09-08 from the [iteration-3 results](01_results.md), the
[ChatGPT proposal](02_proposals/01_chatgpt_guide.md), the
[first Claude review](02_proposals/02_claude_review.md), and the
[second Claude review](02_proposals/03_claude_second_review.md). This is the
agreed plan for the next bounded experiment. It does not claim that the MLP is
already the cause of the recovery failure; the experiment below is designed to
test that attribution.

## Verdict

Build a **curve-owned Cartesian Fourier control in the exact Method-B chart**.
Initialize it once from the saved neural state through the production
extraction/Method-B path, then remove the MLP, Eikonal field, extraction reverse
and repeated conversion gates from the optimization loop.

Run two direct arms on the same iteration-3 E1 multistatic data:

1. **D-GN** — Cartesian Fourier coefficients with Levenberg Gauss-Newton and a
   radial-style `k^4` smoothness prior;
2. **D-Adam** — the same Cartesian Fourier state with Adam/backtracking and no
   curve prior, matching the implicit optimizer family as closely as physical
   coefficient units allow.

The two arms answer different questions. D-GN asks whether the explicit
Cartesian chart is recoverable with a shape-appropriate optimizer. D-Adam asks
whether the same data and optimizer family become useful once the implicit
representation/pullback layer is removed. Neither arm alone is allowed to
stand in for both claims.

Do **not** start with full bandwidth 96. At 194 Kress nodes, B96 has 386 real
Cartesian coefficients against 388 real nodal coordinates and therefore gives
almost free nodal motion. Do **not** start with B8 either: in Method B's
arc-length chart the target itself contains material higher harmonics and B8
has an approximately 1.85 mm target truncation scale.

The agreed active band is **B32**, with modes 33–96 retained from the exact
initial Method-B representation and frozen during inversion. B32 is fixed
before any direct inverse from the saved initial curve alone: the measured
maximum contribution of modes above 32 is `146.862 um`, below the existing
`0.2 mm` neural conversion-distance budget, whereas the B16 tail is
`491.833 um`. Do not search bands 17–31 or tune the band against target
recovery. The reviews' target-aware diagnostic is recorded only as a floor:
with the initial high tail frozen, the target/initial tail mismatch at B32 is
about `43.311 um` RMS and `111.816 um` maximum in the shared arc-length
parameter. Report that floor beside every result; do not use it in acceptance
or hyperparameter selection.

## Final decisions

| Topic | Decision |
|---|---|
| Primary question | Can the same E1 data recover a useful star when the authoritative state is the Method-B Cartesian Fourier curve rather than an implicit MLP? |
| Initial state | Exact final `FourierBoundary` produced by the saved neural state-0 Method-B conversion; no refit |
| Full stored bandwidth | B96, because that is the production Method-B representation |
| Active optimization bandwidth | **B32**; freeze modes 33–96 at their initial coefficients |
| Active coordinates | 130 stored real coefficients through B32; remove the one exact parameter-origin phase gauge from proposed motion |
| Primary acquisition | Iteration-3 **E1 multistatic-8**, 64 entries, 0.5/1.5 GHz, same observations and normalization |
| Holdout | Same disjoint multistatic-8 3 GHz evaluation; never used for acceptance, band choice or stopping |
| D-GN | Analytic Kress residual Jacobian through existing JVPs; Levenberg damping; Cartesian `k^4` smoothness prior at weight `1e-4` |
| D-Adam | Existing Adam defaults, learning rate `1e-3`, 14 halvings, rollback, projected data gradient; no Eikonal and no curvature prior |
| Physical trust region | Maximum **normal** boundary displacement `2 mm` on a dense continuous audit; tangential motion reported separately |
| Candidate validity | Full continuous Fourier validation, bounds, finite positive speed and self-intersection checks; no raw-SDF conversion gates after initialization |
| First execution order | Validate implementation -> D-GN -> D-Adam |
| Full-B96 direct inverse | Deferred; only reconsider in the next cycle if B32 results specifically require it |
| Paired-8 direct arm | Deferred; paired-8 has measured low-mode angular aliasing |
| More angles | Deferred for E1; multistatic-24 did not improve the measured low-mode conditioning over multistatic-8 |
| More frequencies | Separate future factor if the direct controls fail; the review shows six frequencies improve E1 low-mode conditioning |

The comparison to the old radial success remains qualified. That run used a
radial chart, 11 parameters, Levenberg GN, a `k^4` prior, 24 paired angles and
six frequencies. The present direct arms are matched primarily to the
**implicit failure**, not to every factor of the radial success. Do not describe
D-GN as a fully matched radial reproduction.

---

# 1. State and forward contract

## 1.1 Retain the production Method-B representation

`fit_method_b(...)` already returns the final arc-length-refitted
`FourierBoundary` as `MethodResult.representation`. Preserve that object on
`OrderedSDFGeometryBuild` through a new optional field rather than reconstructing
it from solver nodes.

The initialization must therefore be exactly:

```text
saved E1/E0 shared neural state 0
  -> production extraction / projection
  -> production Method B including arc-length refit
  -> retained B96 FourierBoundary c_0
  -> direct curve state
```

After `c_0` is captured, no direct candidate may evaluate the neural model,
extract a zero set, project marching samples, fit Method B, or run a conversion
audit.

Record at initialization:

- full B96 coefficients and hashes;
- active/frozen coefficient mask;
- period and parameter origin;
- Kress node count;
- equality of the retained representation's discretization and the original
  production Method-B curve;
- equality of the direct-curve and original neural-pipeline Kress predictions
  at both training frequencies.

Because the actual retained representation is used, no fallback refit or
"reconstruction tolerance" is part of the accepted design.

## 1.2 Reuse `FourierBoundary`

Do not create a second equivalent Cartesian Fourier representation. Add small
helpers, in a sibling direct-inverse module if convenient, for:

- deterministic flatten/unflatten of `a_0, a_1, b_1, ..., a_B, b_B`;
- `with_increment(delta_c)`;
- active/frozen masks;
- exact coefficient direction jets at the native Kress parameters;
- phase-gauge generator and projection;
- dense normal/tangential motion audits.

The authoritative state remains the full B96 `FourierBoundary`; only the B32
subvector is trainable.

## 1.3 Direct curve forward

Use `predict_indexed_curve_response(..., retain_kress_state=True)` for E1. It
must solve the supplied ordered curve without any SDF conversion. Do not route
this experiment through an implicit-field compatibility seam.

A paired direct arm is not in the agreed execution, so adding
`retain_kress_state` to `predict_paired_curve_response` is optional and should
not delay the E1 control.

---

# 2. Exact Cartesian coefficient derivatives

For period `P`, parameter origin `t_0`,

```text
tau = 2*pi*(t - t_0)/P,
omega = 2*pi/P,
```

and

```text
gamma(t) = a_0
         + sum_{k=1}^B [a_k cos(k tau) + b_k sin(k tau)],
```

use the exact basis identities

```text
d gamma / d a_0 = 1

d gamma / d a_k = cos(k tau)
d gamma / d b_k = sin(k tau)

d gamma' / d a_k = -k*omega*sin(k tau)
d gamma' / d b_k =  k*omega*cos(k tau).
```

The existing Kress geometry pullback returns point and first-derivative
covectors satisfying

```text
dL = sum_i q_i . d gamma_i
   + sum_i p_i . d gamma'_i.
```

Contract those covectors with the basis above for the D-Adam scalar data
gradient. This replaces `build_method_b_pullback`; there is no extraction,
least-squares, arc-length-refit or neural-weight reverse in the direct loop.

## 2.1 D-GN residual Jacobian

Do **not** build D-GN from central coefficient finite differences unless the
analytic path fails validation.

The repository already has `KressDirection` and
`linearize_kress_forward(...)`, which compute the exact discrete forward JVP
for one coherent position/first-derivative direction using the stored Kress
system and one tangent solve per frequency. For each active Cartesian Fourier
coefficient:

1. build its exact position and first-derivative jets on the native grid;
2. call the existing Kress forward JVP at each training frequency;
3. select the E1 indexed measurements;
4. apply the exact fixed residual normalization used by the inverse;
5. assemble one real residual-Jacobian column.

Then form

```text
g = J.T @ r
H_GN = J.T @ J.
```

This uses validated discrete derivatives rather than two perturbed full forward
solves per coefficient. Central finite differences remain a validation probe,
not the production D-GN Jacobian.

## 2.2 Required derivative cross-check

At initialization and one nontrivial admissible direct state, verify all three
routes agree:

```text
geometry-pullback analytic coefficient gradient
        ~= J.T @ residual from analytic Kress JVP columns
        ~= central finite difference of the scalar objective
           along random combined coefficient directions.
```

Also check several analytic JVP residual directions directly against shrinking
central finite differences of the residual. Record convergence rather than one
chosen step.

No inverse may run until these checks pass at the project's usual derivative
accuracy scale.

---

# 3. Gauge and physical step definition

A Cartesian Fourier parameterization has an exact phase gauge: shifting the
parameter origin rotates every Fourier mode pair but does not change the point
set. A fixed-parameter displacement can therefore be large while the physical
shape motion is zero.

Do not use `max ||delta gamma(t)||` as the sole trust-region metric.

## 3.1 Remove the exact phase direction

At every accepted state construct the infinitesimal coefficient direction that
corresponds to a global parameter shift. Remove that one direction from the
optimization step.

For D-GN, solve in an orthonormal complement of the gauge direction, then map
the step back to full active coefficient coordinates.

For D-Adam:

- project the data gradient off the gauge direction before updating moments;
- form the Adam proposal;
- project the final proposal off the gauge direction again;
- advance moments only when the projected proposal is accepted;
- restore both coefficients and moments on rejection.

The gauge projection itself must be unit-tested by applying an explicit small
phase rotation and confirming zero point-set change and near-zero projected
normal motion.

## 3.2 Dense normal-motion trust region

For every candidate evaluate the displacement relative to the current curve on

```text
N_audit = max(validation_resolution, 64 * (full_bandwidth + 1))
```

samples. With B96 this is at least 6208 points.

Decompose

```text
delta gamma = delta_n n + delta_t t.
```

Use

```text
max |delta_n| <= 2 mm
```

as the physical motion cap. Record, but do not silently suppress:

- maximum and RMS normal motion;
- maximum and RMS tangential motion;
- tangential/normal energy ratio;
- phase-gauge component removed from the raw proposal.

A large tangential fraction is a diagnostic. It is not allowed to consume the
normal trust region and is not to be interpreted as physical shape progress.

---

# 4. Continuous candidate validation

Removing the MLP removes SDF-specific gates; it does **not** make an arbitrary
Cartesian Fourier curve automatically admissible.

Every candidate that can become accepted must pass full continuous
parameterization validation using the **full B96 bandwidth**, not only the 194
solver-node polygon.

Keep:

- finite Fourier coefficients and derivatives;
- curve inside configured bounds;
- finite positive speed;
- dense self-intersection/simple-curve validation;
- fixed one-component periodic representation;
- even Kress node count;
- physical normal-motion cap;
- selected-state Kress node refinement.

Remove after initialization by construction:

- marching-grid topology checks;
- raw-zero-set versus Method-B conversion distance;
- conversion-refinement-change gate;
- contour field-gradient tests;
- Eikonal loss;
- MLP representation/extraction drift checks.

These limits are not relaxed; the quantities no longer exist because the
Fourier curve itself is authoritative.

Record speed ratio and full Cartesian spectrum at every accepted state. The
iteration-3 neural runs already showed high-mode roughening while data loss
fell, so high-mode growth remains a first-class diagnostic even though modes
33–96 are frozen here.

---

# 5. Optimizer arms

## 5.1 D-GN — explicit-chart recoverability

Use the analytic residual Jacobian from section 2.1.

The solve is Levenberg Gauss-Newton in the gauge-free active subspace. Reuse the
radial optimizer's damping/trust-region logic where applicable.

Use a Cartesian analogue of the radial smoothness prior:

- prior weight `1e-4`;
- no penalty on rigid translation / the lowest bulk mode block;
- modes `k >= 2` priced proportional to `k^4`;
- normalize the prior to the best-determined diagonal scale of `J.T @ J`, as
  the radial implementation does.

Record the exact Cartesian weight vector; do not claim it is algebraically the
same prior as the radial chart.

Candidate acceptance uses the actual direct curve and actual data objective,
not the linear model. Keep the radial-style Armijo/damping logic and the same
2 mm normal trust region.

D-GN answers:

> Is this Method-B Cartesian shape space recoverable under E1 when optimized
> with a stable low-dimensional shape method?

## 5.2 D-Adam — implicit-layer ablation

Use the same active/frozen Fourier state and the same E1 data.

Use:

- PyTorch/NumPy Adam semantics matching the neural optimizer defaults;
- learning rate `1e-3`;
- the same beta/epsilon defaults as the neural run;
- 14 backtracking halvings;
- projected data gradient;
- gauge-projected Adam proposal;
- steepest-data-gradient fallback if the Adam direction is not a valid descent
  direction or exhausts its search, with optimizer-state reset only on accepted
  fallback as in the neural path;
- exact rollback of coefficients and Adam state on rejection.

There is **no Eikonal term** and **no curvature prior** in D-Adam. Do not invent
one to make the text of the objectives match. Their absence is part of removing
the implicit field/regularization layer.

Use data loss alone for the Armijo acceptance objective, plus geometry validity
and the 2 mm normal-motion cap.

D-Adam answers:

> With the same acquisition and optimizer family, does direct Method-B geometry
> behave cleanly once updates no longer have to pass through neural weights,
> field conditioning, extraction, Method-B reverse and conversion gates?

---

# 6. Validation gates before inverse execution

All gates below must pass before either direct arm is interpreted.

## Gate A — exact initialization identity

From the saved shared neural state 0:

- retained `FourierBoundary` discretization exactly reproduces the production
  Method-B curve at production nodes;
- dense evaluation agrees with the production Method-B parameterization;
- direct-curve Kress predictions agree with the original neural-path prediction
  at 0.5 and 1.5 GHz;
- no refit is present.

## Gate B — coefficient derivatives

At two states:

- scalar analytic pullback versus random-direction scalar finite differences;
- analytic JVP residual directions versus residual finite differences;
- `J.T @ r` versus analytic scalar pullback.

Use shrinking step sequences and preserve the tested Kress near/direct branch
margins in diagnostics.

## Gate C — gauge and motion audit

Verify:

- explicit phase shifts leave the point set unchanged;
- phase projection removes that direction;
- normal-motion cap is invariant to a pure phase shift to first order;
- normal/tangential split converges under denser audit sampling.

## Gate D — acceptance / rollback

For each optimizer arm run at least one accepted and one rejected synthetic or
real candidate and prove:

- accepted coefficients equal the solved curve;
- rejected trials restore coefficients;
- D-Adam rejected trials also restore optimizer moments;
- no neural/extraction routine is called after initialization.

## Gate E — Kress refinement

At initialization and after the first accepted state of each arm compare the
production 194-node result with a 388-node discretization of the same continuous
Fourier curve. Check both forward prediction and a small set of directional
derivatives.

If the direct curve does not refine, stop. Do not interpret optimizer behavior.

---

# 7. Primary experiment

Use the exact saved iteration-3 E1 setup:

```text
shared wrong-start neural state 0 -> one-time Method B -> direct c_0
acquisition: multistatic-8, 8 sources x 8 receivers
training frequencies: 0.5 and 1.5 GHz
observations: same independent Nystrom data
geometry: same bounds and material parameters
full Method-B representation: B96
active direct band: B32
Kress production nodes: 194
holdout: disjoint multistatic-8 at 3 GHz
```

Run **D-GN first**, then **D-Adam**. This ordering gives a stable explicit-chart
reference before judging Adam.

For each arm use a bounded run:

- at most **40 accepted updates**;
- at most **30 inverse minutes** for the arm;
- stop earlier on the optimizer's declared convergence/stall condition;
- save every accepted state and every rejected candidate reason;
- record checkpoints at accepted updates 0, 5, 10, 20 and 40 when they exist.

The 3 GHz evaluation and exact target metrics are computed for reporting only,
after accepted states are saved. They never alter the optimization path.

Do not match the arms by raw forward-solve count: D-GN deliberately spends
extra tangent solves to estimate curvature. Report accepted updates, attempted
candidates, tangent/adjoint solve counts, Kress wall time and total wall time so
matched-work views can be constructed afterward without changing either run.

---

# 8. Measurements and recovery classification

Use the same independent geometry/evaluation definitions established in
iteration 3. At minimum record:

- training data objective and relative L2;
- disjoint 3 GHz relative L2;
- symmetric RMS and mean curve-to-target distance;
- sampled symmetric Hausdorff estimate;
- centroid error;
- mean polar radius when polar representation is valid;
- polar mode-5 amplitude and rotation;
- phase-aware mode-5 coefficient error;
- unwanted polar modes 2–10 excluding 5;
- Cartesian Fourier amplitudes through B96;
- active/frozen spectral energy;
- maximum/RMS normal and tangential accepted motion;
- gauge component removed;
- speed ratio;
- candidate validity/rejection counts;
- Kress residual and node-refinement diagnostics;
- adjoint/JVP/tangent solve counts and runtime.

Do not manufacture SDF metrics for the direct arms.

For a **strong direct recovery** claim, require all of the following at a saved
state without using them for stopping:

- symmetric RMS geometry error `<= 1.0 mm`;
- sampled symmetric Hausdorff estimate `<= 2.0 mm`;
- phase-aware mode-5 coefficient error `<= 2.0 mm` while a valid polar
  description exists;
- disjoint 3 GHz relative L2 `<= 0.10`;
- no failed numerical refinement qualification.

These gates are intentionally far looser than the nanometre radial control but
far stronger than the iteration-3 neural E1 final state (`9.506 mm` symmetric
RMS, collapsed lobes, 3 GHz relative L2 `0.544476`). A run that improves
substantially but misses any gate is reported as partial improvement, not
recovery.

Always state the frozen-tail floor (`43.311 um` RMS, `111.816 um` maximum in the
review's shared-parameter metric) beside final geometry errors. If a direct arm
approaches that scale, the frozen tail rather than the optimizer may be the
limiting factor.

---

# 9. Interpretation matrix

| D-GN | D-Adam | Allowed conclusion |
|---|---|---|
| Strong recovery | Strong recovery | Strong evidence that the current implicit representation/pullback layer is responsible for most of the iteration complexity under E1: the same data and Method-B curve space recover cleanly without it, even with Adam |
| Strong recovery | Fails / poor geometry | Explicit Cartesian geometry is recoverable, but optimizer/metric matters. Do **not** blame the MLP alone; the neural weight-space/Adam metric is entangled with the failure |
| Fails | Strong recovery | Treat as an implementation/prior anomaly first; D-GN is the supposedly more stable reference and the discrepancy must be explained before a scientific claim |
| Fails | Fails | The proposed MLP attribution is not supported by this control. Do not move to more MLP repair by default; open the next cycle on objective/landscape/frequency/chart conditioning |

A negative direct result does **not** automatically mean the data lack the
lobes. The second review measured E1's twelve low-order physical directions as
well conditioned at the initial state, with mode 5 visible. Conversely, that
local result does not establish the full B32 or neural maps are well
conditioned; save singular spectra of the actual D-GN Jacobian so this can be
measured directly.

For D-GN, record singular values of the gauge-free active residual Jacobian at
initial, intermediate and final/stall states. This is the missing bridge between
the review's 12-direction observability probe and the actual 129-dimensional
shape update space.

---

# 10. Explicitly deferred work

Do not mix the following into iteration-3 execution:

- full-B96 D-Adam or D-GN;
- a paired-8 direct arm;
- more source angles for E1;
- paired-24 reproduction of the radial acquisition;
- six-frequency / higher-band direct inversion;
- neural GN/TSVD/IRGN;
- altered Eikonal sampling or field repair;
- relaxed neural conversion limits;
- topology-changing implicit methods;
- replacing the production implicit inverse with the direct control.

If both direct B32 arms fail after all validation gates pass, the **first**
deferred factor to reconsider in the next cycle is frequency, not more angles:
the second review found multistatic-24 essentially unchanged from multistatic-8
in the tested low-mode conditioning, while six frequencies improved that
conditioning materially.

A full-B96 permissive probe is lower priority than that question. Its geometry
space is almost the free solver-node space and a failure or success would be
harder to attribute.

---

# 11. Execution sequence

The adopted order is:

```text
1. retain production FourierBoundary on OrderedSDFGeometryBuild
2. implement active/frozen Cartesian coefficient helpers
3. implement analytic scalar coefficient pullback
4. implement analytic residual-Jacobian columns through KressForwardJVP
5. implement phase-gauge projection
6. implement dense normal/tangential motion audit and full B96 validation
7. pass Gates A-E
8. run bounded E1 D-GN B32
9. run bounded E1 D-Adam B32
10. compute common independent geometry, holdout, spectrum and refinement report
11. open the next iteration from those measured outcomes
```

Do not launch steps 8–9 if any derivative, gauge, state-identity or Kress
refinement gate fails. Fix the control first.

## Handoff

Execution of this plan should create the next iteration's `01_results.md`.
Until then, iteration 3 remains the active cycle with an agreed plan and
execution pending. The purpose of this experiment is diagnostic: determine
whether the implicit MLP representation and its pullback/field machinery are
what make the current recovery loop difficult, while keeping the Method-B
Cartesian geometry and E1 data as controlled as practical.
