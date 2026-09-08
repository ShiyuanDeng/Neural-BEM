# Codex task: latest directions for the implicit-MLP star inverse

## Status

Work from:

- repository: `ShiyuanDeng/Neural-BEM`
- branch: `feature/ordered-boundary-nystrom`
- current reviewed head: `7f9e7d6a3b292cd9fa63d9b9be5e26f483d82c09`

This document supersedes the ordering in the earlier
[implementation guide](01_chatgpt_guide.md) where it conflicts
with the two [2026-09-08 reviews](02_codex_review.md).

Read first:

- `docs/pipelines/implicit_mlp.md`
- `docs/iterations/implicit_mlp/iteration_01/02_proposals/01_chatgpt_guide.md`
- `docs/iterations/implicit_mlp/iteration_01/02_proposals/02_codex_review.md`
- `results/validation/implicit_mlp_adjoint/review-20260908/README.md`
- `results/validation/implicit_mlp_adjoint/rerun-20260907/README.md`
- `results/validation/implicit_mlp_adjoint/rerun-20260907/star-bw96/summary.md`
- `results/legacy/known_shape_family_parameter_inverse/wrong-star-nystrom-20260903/summary.md`
- `run_sdf_inverse_comparison.py`
- `run_implicit_mlp_inverse.py`
- `solvers/sdf_inverse/forward.py`
- `solvers/gpr_bem_kress/shape_derivative.py`

Do not rewrite validated BEM, Method-B, extraction, adjoint, pullback,
pretraining or rollback machinery just to make these experiments convenient.

---

# 1. Corrected interpretation

## 1.1 What is already established

Keep these:

- the old fixed-normalized fallback caused a false circle minimum-step stop and
  has been repaired;
- star pretraining with a global Eikonal weight conflicted with the proxy target,
  and the validated star default is now zero pretraining Eikonal weight;
- raw MLP / Method-B contour disagreement is explicitly guarded;
- Method-B Fourier bandwidth, not grid/sample refinement, dominated frozen
  conversion error;
- bandwidth 96 represents the recorded star checkpoint well below the
  `0.2 mm` conversion-distance budget.

Do not re-debug these first.

## 1.2 Corrected star termination

The recorded `star-bw96` stop was **not** a clean stationary or unavoidable
line-search stop.

The frozen-checkpoint audit shows:

- backtrack 8, the last production trial, passes conversion distance but fails
  the independent conversion-refinement-change check;
- backtracks 9, 10 and 12 satisfy all tested production acceptance conditions;
- therefore an acceptable descent step exists beyond `max_backtracks = 8`.

But the first extra valid step reduces loss by only about `0.039%`.

Therefore separate:

1. **why the implementation stopped**;
2. **why the accepted geometry is still wrong by roughly 36 mm**.

The first is nearly closed. The second is the research problem.

## 1.3 Strong historical control

The historical five-parameter star control succeeds at the same
`0.5 / 1.5 GHz` band with 12 paired measurements.

Kress reaches approximately:

- holdout relative L2 `3.14e-5`;
- maximum boundary error `0.039 mm`;
- amplitude error `5.4e-6`;
- rotation error `1.35e-7`.

Therefore `0.5 / 1.5 GHz` is not categorically incapable of recovering the
five-lobe target when a strong five-parameter star-family prior is imposed.

Do not make "higher frequency is required" the working conclusion before
matched acquisition and shape-space tests.

## 1.4 Important acquisition fact

The current ring experiment is quasi-monostatic / paired.

`PairedForwardProblem` observes source row `i` only at receiver row `i`.

With eight source/receiver pairs and one frequency:

```text
8 complex measurements = 16 real residual directions
```

With two frequencies:

```text
32 real residual directions
```

The neural model has 8,577 weights. Thus the neural data Jacobian has rank at
most 32 in the present experiment. This is measurement arithmetic, not a claim
that every other weight direction moves the boundary.

More importantly, Kress already forms the full receiver-by-source response
matrix before selecting the paired diagonal, and the adjoint cotangent is already
represented as a full receiver-by-source matrix.

With the same eight sources and receivers, full multistatic readout gives:

```text
64 complex measurements per frequency = 128 real residual directions
```

at close to the present forward-solve cost.

This is now a major experimental lever.

---

# 2. Latest priority order

Do this in order:

```text
A. matched 5-parameter star: 12 pairs -> 8 pairs
B. start-at-truth MLP control
C. close backtracking/rejection bookkeeping
D. physical + modal observability:
      paired-8 vs paired-12 vs multistatic-8
E. frequency sweep inside those observability tests
F. direct MLP acquisition ablation using the informative acquisition
G. recursive frequency continuation only if frequency adds useful modes
H. neural GN / TSVD / IRGN only if data are demonstrably adequate
```

Do not begin with another long 60-update neural run.

---

# 3. Phase A — cheapest matched control

## Goal

Determine whether changing only `12 -> 8` paired views breaks the already
successful five-parameter inverse.

Reuse the existing analytic star parameterization/controller and Kress
parameter-FD damped Gauss-Newton path. Do not create another optimizer.

Run:

```text
A0: 12 paired views, train {0.5, 1.5} GHz   # historical reference
A1:  8 paired views, train {0.5, 1.5} GHz   # new matched control
```

Keep fixed:

- wrong initial analytic star;
- target;
- materials;
- Kress branch;
- independent Nystrom observations;
- forward/conversion resolution;
- optimizer and stopping settings.

If current resolution standards differ from the historical run, make a matched
resolved A0/A1 pair rather than silently changing only A1.

Record per accepted iterate:

- training and holdout relative L2;
- center error;
- mean-radius error;
- amplitude error;
- rotation error;
- maximum boundary error;
- accepted/rejected trials;
- forward evaluations;
- wall time.

### Decision

If A1 succeeds, eight paired views are sufficient **inside the five-parameter
star family**. This does not establish sufficiency for a general neural boundary.

If A1 fails while A0 succeeds, angular acquisition matters even under the
strong prior. Paired-8, paired-12 and multistatic-8 become mandatory observability
arms.

---

# 4. Phase B — start-at-truth MLP

## Goal

Separate local conditioning/objective failure from a bad basin reached from the
wrong initial star.

Reuse the exact-target SIREN fit already built for the representation-floor
control as the inverse initialization.

Start with the bad neural acquisition:

```text
8 paired views
train {0.5, 1.5} GHz
bandwidth 96
current repaired pretraining / inverse regularization
```

A short bounded run is sufficient initially.

Record every accepted step:

- raw data loss;
- regularized objective;
- maximum boundary error to target;
- fitted center/radius/amplitude/rotation;
- fixed holdout performance;
- conversion distance;
- conversion refinement change;
- boundary movement;
- rejection reason for every rejected trial.

Also record initial data-gradient and Eikonal-gradient norms.

### Decision

If the MLP stays near truth, the local basin is usable; focus on reaching it
from the wrong initialization.

If the MLP walks away while lowering data loss, the current objective/acquisition
admits geometrically wrong descent directions even near truth. Prioritize
multistatic acquisition and observable-mode regularization.

If it cannot take a usable step, distinguish guard/search termination from true
lack of descent using Phase C.

---

# 5. Phase C — close termination bookkeeping

This is bounded engineering work, not the main reconstruction study.

1. Increase diagnostic fallback depth to around 12–16 halvings.
2. Preserve all current tolerances.
3. Log rejection reasons separately:

```text
extraction/topology
conversion distance
conversion refinement change
boundary-motion limit
data Armijo
regularized Armijo
non-finite / solver failure
```

4. Report the first accepted step beyond the historical eight-backtrack limit.
5. Declare a step-size floor so a tiny crawl is not described as meaningful
   recovery.

Do not relax the conversion guard merely to keep optimization moving.

---

# 6. Phase D — observability: acquisition before frequency

This is the main diagnostic.

First compare:

```text
paired-8
paired-12
multistatic-8
```

at the original `0.5 / 1.5 GHz` band.

## 6.1 Preserve the paired contract

Do not silently change `PairedForwardProblem`.

For multistatic experiments, either:

- introduce a separate generalized/indexed observation specification; or
- add a measurement-index layer selecting arbitrary `(source, receiver)` entries
  from the already-computed full Kress response.

Preserve existing paired behavior bit-for-bit.

Reuse the existing full Kress response and full cotangent machinery rather than
duplicating the forward solver.

## 6.2 Physical five-parameter Jacobian first

At the wrong initial star and exact target, compute response Jacobians for the
existing physical directions:

```text
center_x
center_y
mean_radius
amplitude
rotation
```

Compare:

```text
D0: paired-8
D1: paired-12
D2: multistatic-8
```

at:

```text
0.5 GHz
1.5 GHz
stacked {0.5, 1.5} GHz
```

Report native-unit derivatives, but compare conditioning only after a declared
scale normalization. Prefer equal RMS normal boundary displacement per
direction.

Record:

- per-column complex sensitivity norms;
- real-stacked singular values;
- effective rank at relative thresholds `1e-2`, `1e-3`, `1e-4`;
- normalized column correlations;
- amplitude/rotation sensitivity;
- correlation of amplitude/rotation with center/radius;
- combined-frequency spectra.

Do not quote an unscaled condition number mixing metres, relative amplitude and
radians.

## 6.3 General boundary modal Jacobian second

Use equal-RMS normal perturbations on arc length:

```text
m = 0..10
V_0 = constant
V_m,c(s) = cos(2*pi*m*s/L)
V_m,s(s) = sin(2*pi*m*s/L)
```

These are diagnostic probes only. They do not become the production geometry
representation and are not fitted back into the MLP.

Again compare paired-8, paired-12 and multistatic-8 at 0.5, 1.5 and stacked
`{0.5,1.5}` GHz.

Pay special attention to mode-5 cosine/sine directions.

Dimension facts at one frequency:

```text
paired-8:      <= 16 real data directions
paired-12:     <= 24 real data directions
multistatic-8: <= 128 real data directions
```

The `m=0..10` basis has 21 real columns, so paired-8 at one frequency must have
a null space by dimension alone.

## 6.4 Validate derivatives

Spot-check new Jacobian assembly with fresh central finite differences over
several perturbation magnitudes and show a convergence window.

Check forward and derivative node refinement at any new frequencies before
making observability claims.

---

# 7. Phase E — frequency sweep after acquisition baseline

Once Phase D works, sweep:

```text
0.25
0.5
1.0
1.5
2.0
2.5 GHz
```

for each relevant acquisition arm.

Ask quantitatively:

```text
Does higher frequency strengthen amplitude/phase or mode-5 directions beyond
what multistatic readout already provides?
```

Report:

- physical amplitude/rotation sensitivity vs frequency;
- mode-5 sensitivity vs frequency;
- smallest relevant singular values;
- effective rank;
- combined-frequency spectra for candidate training sets.

Do not encode `kR = 5` as a hard cutoff.

---

# 8. Holdout discipline

Reserve evaluation frequencies against the union of every planned training
stage.

If later continuation may train on:

```text
{0.5, 1.0, 1.5, 2.0, 2.5} GHz
```

none can remain in the common holdout.

Candidate common holdout:

```text
{0.25, 3.0} GHz
```

but verify the 512-node star oracle self-convergence at `3.0 GHz` before using
it. If it is not converged, select another disjoint frequency only after an
explicit oracle-resolution check.

Never use holdout loss for line search, hyperparameter tuning, acquisition
selection or frequency-path selection.

---

# 9. Decision after observability

## Case 1: paired-8 weak, multistatic-8 strong at 0.5/1.5

Highest-priority fix:

```text
multistatic acquisition before adding higher frequency
```

Run the direct MLP under multistatic-8 with the original frequencies.

## Case 2: paired and multistatic remain weak until 2.0/2.5

Highest-priority fix:

```text
higher-frequency information
```

Then test direct multi-frequency MLP and continuation.

## Case 3: five-parameter Jacobian strong, general modal Jacobian poor

Interpretation:

```text
the data recover the strongly constrained star family but not arbitrary shape
directions stably
```

Prioritize multistatic acquisition if it improves modal conditioning; otherwise
use inverse regularization / frequency-dependent information. Do not enlarge
the SIREN.

## Case 4: modal Jacobian good and start-at-truth stable, wrong-start MLP fails

Interpretation:

```text
basin / nonlinear neural optimization is the main suspect
```

Proceed to continuation.

## Case 5: start-at-truth walks away despite strong observability

Interpretation:

```text
the neural objective / parameterized update geometry remains problematic
```

Proceed later to the scaled neural-Jacobian / GN diagnostic.

---

# 10. Phase F — direct MLP acquisition ablation

Only launch long neural inverses after D/E identify informative configurations.

Keep fixed:

- SIREN architecture and seed;
- wrong-star initialization;
- validated star pretraining;
- inverse Eikonal setting;
- Method-B bandwidth 96 unless a new conversion audit proves otherwise;
- conversion tolerance;
- acceptance contract;
- declared work budget.

Change one acquisition factor at a time.

Likely arms:

```text
F0: paired-8,      {0.5,1.5}      # existing baseline
F1: paired-12,     {0.5,1.5}      # if pair count matters
F2: multistatic-8, {0.5,1.5}      # high priority if D shows benefit
F3: best acquisition, informative high-frequency set from E
```

If adding a third frequency, control objective scaling because a fixed Eikonal
weight changes relative importance when the number of data terms changes.

Primary success evidence is geometric:

- lobe amplitude moves toward target;
- lobe phase moves toward target;
- center/radius do not catastrophically regress;
- maximum boundary error decreases;
- fixed holdout improves;
- conversion remains resolved.

Training-loss decrease alone is not success.

---

# 11. Phase G — recursive frequency continuation

Do this only if E shows higher frequencies add useful geometric information.

Preserve the current ownership loop:

```text
MLP weights
 -> zero contour
 -> Method B
 -> Kress
 -> adjoint
 -> reverse extraction / Method B
 -> MLP weights
```

Do not reintroduce:

```text
boundary sensitivity
 -> prescribed boundary motion
 -> fit MLP to moved curve
```

as the production update.

Suggested path:

```text
0.5 -> 1.0 -> 1.5 -> 2.0 -> 2.5 GHz
```

At each stage:

1. start from accepted MLP weights from the prior stage;
2. use only the current stage frequency initially;
3. reset Adam moments by default;
4. use a declared stage work budget;
5. record stage-local objective and one fixed external evaluation set;
6. retain only accepted MLP state.

Compare continuation against a direct run with comparable total forward
evaluations, not merely equal nominal iteration counts.

A cumulative-frequency variant can come later.

---

# 12. Phase H — neural Jacobian / GN only if still needed

Do **not** run the full 8,577-weight Jacobian as the first observability test.

Reasons:

- the rank ceiling is already known from measurement dimension;
- Euclidean minimum-weight-norm directions depend on neural parameter scaling;
- physical/modal Jacobians are cheaper and geometrically interpretable.

Use the neural Jacobian only after:

- low-dimensional recovery succeeds;
- physical/modal observability is adequate;
- acquisition has been enriched if needed;
- continuation still does not recover the neural star.

Then diagnose the scaled real data-to-weight Jacobian.

Candidate step:

```text
delta_theta = -J^T (J J^T + lambda I)^(-1) r
```

or TSVD / a properly specified IRGN scheme.

Requirements:

- declare the weight-space metric/scaling;
- distinguish damped Gauss-Newton from prior-centred IRGN;
- keep actual candidate extraction, Method-B conversion, BEM solve and rollback;
- do not replace the MLP with an explicit curve-owned optimizer;
- report singular spectrum/effective rank before adding a production optimizer.

---

# 13. What not to change yet

Do not, without evidence:

- enlarge the SIREN;
- relax conversion-fidelity gates;
- redesign Kress quadrature;
- replace Method B;
- reintroduce curve-to-MLP fitting;
- add arbitrary weight-space smoothness penalties;
- call higher frequency the fix before measuring it;
- call eight paired views sufficient merely because a five-parameter prior
  succeeds.

Keep distinct:

```text
forward representation bandwidth
inverse information bandwidth
shape-prior dimension
measurement dimension
optimization basin
optimizer
```

---

# 14. Required artifacts

Use a new result root, for example:

```text
results/validation/implicit_mlp_adjoint/latest-direction-20260908/
```

At minimum:

```text
README.md
metrics.json
provenance.json
commands.txt
```

For observability:

```text
physical_jacobian.csv
modal_jacobian.csv
singular_values.csv
column_correlations.csv
derivative_validation.csv
```

Useful plots:

- physical parameter sensitivity vs frequency;
- modal sensitivity vs frequency;
- singular spectra for paired-8 / paired-12 / multistatic-8;
- selected Gram/correlation matrices;
- amplitude/phase trajectories for matched inverse controls.

Every README must state:

- commit SHA;
- acquisition definition;
- source/receiver count;
- paired or multistatic readout;
- training and holdout frequencies;
- forward/conversion resolution;
- work budget;
- optimizer;
- stop reason;
- rejection-reason counts;
- what the experiment establishes;
- what it does not establish.

---

# 15. Immediate checklist

Do these first:

```text
[ ] A1: five-parameter star with 8 paired views at 0.5/1.5 GHz
[ ] B:  short start-at-truth MLP run
[ ] C:  deeper fallback + rejection-reason audit
[ ] D0: physical Jacobian, paired-8 vs paired-12 vs multistatic-8
[ ] D1: mode-0..10 Jacobian under the same three acquisitions
[ ] E:  frequency sweep only after D0/D1 are trustworthy
```

Stop after D/E and write a decision table before launching another long neural
inverse.

The decision table should answer:

1. Is the low-dimensional star recoverable with 8 paired views?
2. Is the exact MLP target locally stable?
3. What actually terminates candidate steps?
4. Which physical star directions are observed?
5. Which general boundary modes are observed?
6. Does multistatic readout improve those directions?
7. Does higher frequency add information beyond multistatic readout?
8. Which acquisition should be used for the next full MLP run?

---

# 16. Overall research direction

The current evidence does **not** support reducing the problem to:

```text
"the star needs higher frequency"
```

The sharper question is:

```text
How much acquisition information is required when moving from a five-parameter
shape prior to an 8,577-weight neural implicit geometry?
```

The next experiments should compare **shape-space dimension** against
**measurement-space richness** directly.

The most promising near-term hypothesis is that the paired acquisition discards
a large amount of scattering information that the Kress solve already computes.
If multistatic readout materially improves the general-boundary Jacobian, that
is a more fundamental result than an optimizer tweak.

Frequency continuation and neural Gauss-Newton remain strong later directions,
but they should be justified by the matched observability evidence above.
