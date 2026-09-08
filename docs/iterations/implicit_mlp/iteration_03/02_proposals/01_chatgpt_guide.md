# ChatGPT proposal: direct Method-B Fourier control for iteration 3

This is the **first proposal for iteration 3**. It was requested after reviewing
`01_results.md` and the current Explicit Radial Fourier / Implicit MLP + Method B
split. It is not an agreed plan and must not be treated as authorization for a
new long inverse until reviewed.

The purpose is narrow: construct a curve-owned control that keeps the same
Cartesian Fourier representation produced by Method B, so the experiment
removes the implicit neural representation without simultaneously switching to
the radial-Fourier shape chart.

## Repository state

Work from:

- repository: `ShiyuanDeng/Neural-BEM`
- branch: `feature/ordered-boundary-nystrom`

Read first:

- `docs/iterations/implicit_mlp/iteration_03/01_results.md`
- `docs/pipelines/implicit_mlp.md`
- `docs/pipelines/explicit_radial_fourier.md`
- `solvers/sdf_to_ordered_boundary/method_b.py`
- `solvers/sdf_to_ordered_boundary/representations.py`
- `solvers/sdf_inverse/implicit_adjoint.py`
- `solvers/gpr_bem_kress/geometry_pullback.py`
- `solvers/sdf_inverse/forward.py`

Do not reinterpret the existing radial-Fourier success as this control. The
radial inverse changes both geometry ownership and shape coordinates. Do not
rewrite validated Kress assembly, the objective adjoint, or the production
Method-B reverse merely to make this experiment convenient.

---

# 1. Question

The current implicit inverse is

```text
MLP weights
  -> implicit zero set
  -> extraction / projection
  -> Method-B Cartesian Fourier curve
  -> Kress
  -> data objective
  -> Kress geometry pullback
  -> extraction / Method-B reverse
  -> MLP-weight gradient
  -> Adam / backtracking
  -> re-extract the actual candidate
```

The proposed control is

```text
initial MLP
  -> ONE production extraction / Method-B conversion
  -> Method-B Cartesian Fourier coefficients
  -> discard the MLP as an optimization state

Cartesian Fourier coefficients
  -> exact Fourier curve
  -> Kress
  -> same data objective
  -> same Kress geometry pullback
  -> analytic Fourier-coefficient pullback
  -> coefficient update / backtracking
  -> exact Fourier curve
```

The scientific question is:

> If the same Kress physics and the same Method-B Cartesian Fourier geometry
> are optimized directly, does the recovery become straightforward once the
> implicit MLP, Eikonal field, extraction reverse and repeated conversion gates
> are removed from the optimization loop?

A positive result would localize the present difficulty to the implicit
representation/pullback layer much more cleanly than the existing radial
control. It would **not** prove that neural implicit representations cannot
work in general.

---

# 2. Why the existing radial-Fourier inverse is not enough

The working radial control owns a star-shaped state

```text
center + radial Fourier coefficients r(theta)
```

whereas Method B owns a Cartesian vector Fourier curve

```text
gamma(t) = (x(t), y(t)).
```

Those are different charts and impose different geometric structure. A radial
success against an implicit failure therefore changes at least two factors:

1. MLP-owned versus curve-owned geometry;
2. radial star-shaped coordinates versus Method-B Cartesian Fourier
   coordinates.

The proposed control changes only the first factor as far as practical: the
initial authoritative curve is the actual Method-B curve from the neural
pipeline, and subsequent states remain Cartesian Fourier curves of that same
kind.

This is a user-requested ablation, not a proposal to replace the implicit
pipeline as the main research object.

---

# 3. Authoritative state

Use the existing `FourierBoundary` coefficient convention rather than defining
another radial representation.

For period `P`, origin `t0` and

```text
tau = 2*pi*(t - t0)/P,
```

write

```text
gamma(t)
  = a_0
    + sum_{k=1}^B [a_k cos(k tau) + b_k sin(k tau)],
```

with `a_k, b_k in R^2` and `b_0 = 0`.

The full Cartesian state therefore has

```text
2 + 4 B
```

real coefficients. At the current star bandwidth `B = 96`, that is 386 real
controls. Keep this fact visible in all interpretation: the full coefficient
space is much larger than the radial K5 control and, for paired acquisition,
far larger than the real measurement dimension.

## 3.1 Initialization contract

The preferred initialization is:

```text
saved neural state 0
  -> existing production build_ordered_sdf_geometry / Method B
  -> exact final Method-B Fourier representation
  -> coefficient state c_0.
```

If the current geometry builder does not expose the retained `FourierBoundary`,
use the smallest non-invasive seam that obtains it. A refit of the final solver
curve is acceptable only after proving that it reproduces the production
Method-B curve to numerical precision at the production nodes and on a dense
independent sample.

Record:

- coefficient bandwidth;
- period and parameter origin;
- production node count;
- maximum and RMS difference between the neural pipeline's initial Method-B
  curve and the direct control's initial curve;
- forward-prediction difference at all training frequencies.

The direct control should start from the same physical boundary, not merely the
same analytic wrong-shape label.

## 3.2 No repeated Method-B refit in the first control

Once `c_0` is accepted, coefficient updates rebuild the Fourier curve directly.
Do **not** run extraction, projection, least-squares fitting or arc-length
refitting after every step.

In particular, do not silently reparameterize every accepted curve by arc
length unless that nonlinear remap is deliberately added to the state map and
its derivative. For the first control, freeze the period, parameter origin and
uniform native parameter grid. Report speed ratio as a diagnostic instead.

---

# 4. Reuse the Kress adjoint; do not build the inverse with coefficient finite differences

The Kress geometry pullback already returns covectors `q_i` and `p_i` satisfying

```text
dL = sum_i q_i . d gamma_i
   + sum_i p_i . d gamma'_i.
```

For the Fourier coefficients the final pullback is analytic.

Let

```text
omega = 2*pi/P.
```

Then

```text
d gamma / d a_0 = 1

d gamma / d a_k = cos(k tau)
d gamma / d b_k = sin(k tau)

d gamma' / d a_k = -k*omega*sin(k tau)
d gamma' / d b_k =  k*omega*cos(k tau).
```

For each Cartesian component, contract these basis values with the existing
point and first-derivative covectors. Equivalently,

```text
dL/d a_k
  = sum_i q_i cos(k tau_i)
    + sum_i p_i [-k*omega*sin(k tau_i)]

dL/d b_k
  = sum_i q_i sin(k tau_i)
    + sum_i p_i [ k*omega*cos(k tau_i)].
```

Use the componentwise vector form for `R^2` coefficients.

This pullback should be a small NumPy/Torch-free geometry contraction on top of
validated Kress derivatives. There is no reason to replay marching edges,
projection, Fourier least squares or the neural parameter Jacobian.

Do not use central finite differences as the production optimizer at `B=96`.
There are 386 coefficients, so a central coefficient Jacobian would require up
to 772 perturbed forward solves per outer iteration before backtracking. Finite
differences belong only in derivative validation on a handful of random
combined directions.

---

# 5. Minimal implementation seams

Prefer a sibling implementation rather than modifying the radial representation
until the control is validated.

Suggested names are descriptive, not mandatory:

```text
solvers/sdf_inverse/cartesian_fourier_inverse.py
run_direct_method_b_fourier_inverse.py
```

The implementation should provide only the pieces that are genuinely new.

## 5.1 Coefficient state

Either use `FourierBoundary` directly or wrap it in a small immutable state that
provides:

- deterministic flatten / unflatten of `a_0, a_1, b_1, ..., a_B, b_B`;
- `with_increment(delta_c)`;
- exact continuous `PeriodicParameterization2D` reconstruction;
- discretization on the existing even Kress node grid;
- active/frozen coefficient masks when needed for a bounded ablation.

Do not introduce a second mathematically equivalent Fourier class unless the
existing immutable `FourierBoundary` API cannot cleanly own the optimization
state.

## 5.2 Direct curve forward

Reuse the ordered-curve Kress forward path already used by curve-owned
experiments. The control must solve the exact supplied curve; it must not call
an implicit-field extractor internally.

## 5.3 Coefficient gradient

Build the ordinary paired or indexed Kress objective adjoint, call the existing
Kress geometry pullback, then apply the analytic coefficient contraction from
Section 4.

The returned diagnostic should explicitly state something like:

```text
method: kress_discrete_adjoint_cartesian_fourier_pullback
finite_difference_probes: 0
extraction_reverse: false
method_b_reverse: false
neural_parameter_pullback: false
```

## 5.4 Optimizer and line search

For the primary isolation control, prefer the same broad update policy as the
implicit run:

- Adam proposal;
- same backtracking factor;
- same maximum physical boundary-motion limit;
- strict data decrease / data Armijo check;
- rollback of both coefficients and Adam state on rejection.

The coefficient chart and neural-weight chart have very different dimensions
and metrics, so identical raw learning rates are not in themselves a fair
comparison. Use the existing 2 mm physical boundary-motion cap as the invariant
step-scale control and record the unscaled proposal motion before backtracking.

There is no Eikonal term because there is no field. Do not invent a fake
curve-space Eikonal penalty just to make the objective textually identical.
That missing representation regularizer is part of the factor being removed.

A separate Sobolev/curvature or GN/TSVD curve metric may be studied later, but
it must not be silently folded into the first direct-control claim.

---

# 6. Geometry validation after the MLP is removed

The direct curve still needs physical/numerical admissibility checks.

Keep:

- finite coefficients and curve jets;
- curve inside configured bounds;
- positive finite speed on a dense audit grid;
- no sampled self-intersection;
- fixed one-component closed periodic representation;
- even production Kress node count;
- independent Kress node-refinement check at selected states;
- physical maximum-boundary-motion limit during line search.

Remove after initialization, by design:

- marching-grid topology checks;
- raw-zero-set versus Method-B conversion distance;
- conversion-refinement-change gate;
- contour field-gradient checks;
- Eikonal loss;
- MLP representation drift / re-extraction audits.

These are not being relaxed. They cease to exist because the direct Fourier
curve is itself the authoritative geometry.

Report the Fourier speed ratio and spectral tail during the run so numerical
parameterization deterioration is visible even though it is not an implicit
conversion failure.

---

# 7. Validation before any recovery claim

Do not start with a long inverse. First establish four small contracts.

## 7.1 Initial-state identity

For the saved neural initialization:

```text
neural -> Method B -> curve
```

and

```text
captured Method-B coefficients -> direct curve
```

must agree to numerical precision or to an explicitly measured reconstruction
tolerance if a refit was unavoidable.

Also compare Kress predictions from both representations at every training
frequency. They should agree at the forward solver's normal numerical scale.

## 7.2 Fourier pullback directional derivative

At the common initial curve and at one perturbed admissible curve, generate a
few deterministic random coefficient directions `v` and check

```text
g_c . v
```

against central objective finite differences

```text
[L(c + h v) - L(c - h v)] / (2 h)
```

over a shrinking `h` sequence.

This is a derivative check, not a coefficient-FD inverse.

## 7.3 One-step acceptance replay

Take one direct adjoint proposal, backtrack it through the production candidate
checks, and verify:

- the actual accepted curve equals the coefficient state that is committed;
- loss decreases exactly as recorded;
- rejected trials restore the coefficient and optimizer states;
- no MLP/extraction call is made after initialization.

A test that replaces the model with a callable that raises after the initial
conversion is a useful isolation guard.

## 7.4 Node refinement

At initialization and after one accepted direct step, repeat the forward and
coefficient-gradient calculation on a finer Kress node grid. Record prediction
and directional-gradient changes using the same conventions as current Kress
qualification.

Only after these four checks pass should the control be used to discuss neural
recovery.

---

# 8. Primary experiment: matched multistatic star control

Use the iteration-3 multistatic arm first because it produced the best existing
neural geometry while still collapsing the five-lobe amplitude.

Reuse, rather than regenerate when available:

- the exact saved wrong-start neural state 0;
- the exact target/material parameters;
- the same independent Nyström observations;
- full 8-source x 8-receiver training acquisition;
- 0.5 and 1.5 GHz training frequencies and weights;
- the same disjoint multistatic-8 3 GHz evaluation set;
- the same production Kress node count initially;
- the same 2 mm physical candidate-motion cap;
- the same candidate / wall-time accounting convention.

The only required state change is:

```text
MLP-owned Method-B geometry
        ->
curve-owned Method-B Cartesian Fourier geometry.
```

Do not tune against the exact target or the 3 GHz evaluation.

## 8.1 Full-B96 versus active-band issue

Do not hide the dimensionality problem. At `B=96` the Cartesian curve has 386
real coefficients, while the two-frequency 8x8 multistatic dataset supplies
256 real residual components. A full unregularized coefficient recovery is
therefore not a clean identifiability certificate.

Use the following staged interpretation:

### A. Full-B96 short isolation probe

Keep the exact full B96 initial state and allow direct coefficient updates for a
small bounded number of accepted steps. The purpose is not yet full recovery.
Measure whether removing the implicit layer changes:

- data descent per attempted candidate;
- signed nearest-target normal motion;
- mode-5 amplitude and phase;
- unwanted low-mode growth;
- symmetric geometry error;
- frequency of geometry rejections;
- physical proposal size after Adam/backtracking.

If the direct curve immediately produces useful lobe-restoring motion while the
matched neural trajectory did not, that is already strong representation-layer
evidence.

### B. Recovery-oriented active-band control, only if needed

If full B96 is too underdetermined for a meaningful recovery demonstration,
keep the **full B96 authoritative initial curve** but freeze a declared high
Fourier tail and optimize only a lower active band. Choose the active band by a
predeclared numerical rule, not by target recovery, for example the smallest
band whose frozen-tail removal/change is below a strict curve-approximation
budget on the initial Method-B boundary.

Record the active parameter count and the initial-curve change caused by the
choice. Do not present this lower-dimensional arm as a perfectly matched causal
ablation; it is a recovery control showing what the explicit Cartesian curve
can do when its unobservable high modes are not free.

A separate curvature/Sobolev prior or GN/TSVD control may be preferable after
review, but should be named as a second factor rather than bundled into the
first claim.

## 8.2 Paired arm

Do not automatically repeat the full paired-8 long run. Add a paired direct
control only if the multistatic result leaves a specific acquisition question
unresolved. The existing iteration-3 evidence already shows paired data are the
weaker geometry arm.

---

# 9. Metrics to report beside the neural trajectory

At minimum, use the same independent measurements already established in
iteration 3:

- training data objective;
- 3 GHz disjoint evaluation relative L2;
- raw/curve symmetric RMS and mean distance to target;
- sampled symmetric Hausdorff estimate;
- centroid error;
- mean polar radius when a valid polar description exists;
- mode-5 amplitude;
- mode-5 phase / rotation;
- phase-aware mode-5 coefficient error;
- unwanted modes 2--10 excluding 5;
- accepted updates;
- attempted/rejected candidates;
- physical boundary motion per accepted step;
- self-intersection / bounds / speed rejection counts;
- Kress residual and node-refinement diagnostics;
- Fourier speed ratio and high-mode energy.

For matched-work plots, candidate count remains the existing declared proxy,
but also report wall time because a direct curve candidate no longer pays MLP
extraction/conversion cost.

Do not manufacture `raw SDF` metrics for the direct arm. Call its authoritative
boundary `direct Method-B Fourier curve` or equivalent.

---

# 10. Success criteria and interpretation

The useful outcome is not simply `exit 0`.

## 10.1 Strong representation-layer evidence

The claim becomes substantially stronger if the direct Cartesian-Fourier arm,
from the same initial Method-B curve and data, shows all of the following:

- stable validated Kress/Fourier gradients;
- materially lower data objective;
- materially improved independent geometry;
- mode-5 amplitude moves toward 12.5 mm instead of collapsing;
- 3 GHz evaluation improves without entering acceptance;
- progress is not terminated by an equivalent explicit-curve numerical
  pathology.

Then it is reasonable to conclude:

> Kress, the measurement objective and the Cartesian Fourier boundary space can
> produce useful recovery from this start; the present difficulty is introduced
> by the implicit neural representation and the machinery required to map the
> curve objective through that representation.

Use `implicit representation/pullback layer` rather than `the MLP alone` in the
formal conclusion, because the removed factor includes the neural field,
Eikonal regularization, extraction, Method-B reverse and repeated conversion
acceptance.

## 10.2 Weaker but still useful result

If direct B96 improves geometry but does not fully recover, that still shows the
neural state transition is not necessary for useful descent. Do not call it
full recovery.

If only a lower active-band direct arm recovers, conclude that a controlled
explicit Cartesian-Fourier inverse is recoverable, but keep the role of
search-space dimension/regularization separate from the neural representation.

## 10.3 Negative result

If the validated direct Cartesian-Fourier control reproduces the same lobe
collapse or wrong-shape descent, do not blame the MLP. That would redirect the
investigation toward the data objective, acquisition, curve metric,
identifiability or Kress-shape optimization landscape.

This negative result would be scientifically valuable and would prevent more
MLP-only iteration work based on a false premise.

---

# 11. Work limits

This proposal is intended to be cheaper than another neural iteration cycle.

Before review/adoption, do **not**:

- launch another unchanged 60-step neural inverse;
- relax the 0.2 mm neural conversion gate to make old runs continue;
- change acquisition, training frequencies and geometry ownership at the same
  time;
- add neural GN, higher frequency, new Eikonal sampling or topology machinery
  to this control;
- use coefficient finite differences for the production B96 inverse;
- claim the radial-Fourier run already answers this Cartesian control.

A sensible bounded execution, if adopted, is:

```text
implementation + unit tests
-> initial-identity check
-> Fourier-pullback directional validation
-> one accepted-step replay
-> node-refinement check
-> short full-B96 multistatic isolation run
-> review results
-> only then decide whether a recovery-oriented active-band run is needed.
```

Do not automatically promote a successful short control to the new production
inverse. Its job is to locate the source of the current iteration complexity.
