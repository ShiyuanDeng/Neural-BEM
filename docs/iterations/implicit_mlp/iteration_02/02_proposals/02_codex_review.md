# Review: iteration 2 implicit-MLP next-step guide

This companion follows the order of the
[ChatGPT proposal](01_chatgpt_guide.md), using the
[iteration-2 results](../01_results.md), the
[closed iteration-1 decisions](../../iteration_01/03_plan.md), and the local
artifacts they index. Reviewed on 2026-09-08 on
`feature/ordered-boundary-nystrom`, base commit
`d41e9c7f2aa76a4f5bcca2134398b83ab29a0297`, with uncommitted implementation and
result changes. The base commit alone does not identify the inspected code.

**Verdict:** proceed with the bounded neural-update diagnostic and retain the
separate star-conversion and ellipse-startup audits. Amend the diagnostic to
distinguish raw zero-contour motion from the converted boundary seen by Kress,
and distinguish corrective higher-mode motion from harmful shape changes.
Keep multistatic as the first isolated acquisition experiment. Frequency,
continuation and optimizer changes remain conditional; this review does not
close iteration 2 or authorize another long inverse.

## Repository state

**Agree.** Preserve MLP geometry ownership, the validated extraction/Method-B
reverse, Kress derivatives, rollback and fidelity limits. Implement diagnostics
around those components. The proposal is a research sequence, not evidence that
the proposed mechanisms have already been measured.

## 1–3. Established results and the main hypothesis

**Agree with the measurements and with treating update geometry as a
hypothesis.** The circle completes its budget with 1.069 mm sampled boundary
error; the star stops with 37.368 mm error and fitted amplitude 0.02072; the
ellipse has an execution failure without a saved production traceback.
The guide correctly separates these outcomes.

The prior full-rank results concern 21 normal modes on the **analytic** initial
and target stars, with resolved direct-curve Kress calculations. They do not
measure the neural Jacobian, higher modes, or the badly deformed intermediate
MLP contours. Likewise, the 1.191 mm target-fit control rules out capacity alone
as an explanation for 37 mm error; it does not certify arbitrary-contour
representation or the requested recovery accuracy.

Loss descent with worsening shape supports investigating the update map. It
does not yet distinguish acquisition weighting, a nonlinear basin,
regularization, conversion effects and optimizer preconditioning. Keep these
alternatives open when interpreting the new diagnostic.

## 4. Priority A — neural weights to boundary motion

### Mathematical quantity

**Proceed, adding a distinction between two boundaries.** The stated formula
is the local normal velocity of the regular **raw MLP zero set**, with outward
normal `grad(f) / ||grad(f)||` for the negative-inside convention. Evaluate it
on independently projected zero-set points and record field residuals and
minimum spatial-gradient norm. A small denominator is a regularity diagnostic;
silently clipping it would change the quantity being measured.

Production Method-B nodes need not satisfy `f = 0`. The
[neural data gradient](../../../../../solvers/sdf_inverse/implicit_adjoint.py)
differentiates extraction, projection, Cartesian Fourier fitting and the
arc-length refit before Kress. The raw-contour formula is therefore not
automatically the derivative of that discrete objective.

For the same weight direction, distinguish:

| Quantity | What it establishes |
|---|---|
| Predicted and actual raw zero-contour motion | Whether the implicit-function diagnostic describes the MLP interface |
| Actual re-converted Method-B motion, with its local derivative where available | What geometric change reaches the forward solver |
| Predicted objective change `g_data @ delta_theta` and fresh candidate loss | Whether the complete implemented derivative predicts the measured data change |

Use the existing
[Method-B replay](../../../../../solvers/sdf_inverse/method_b_pullback.py)
for a discrete derivative comparison when needed. A disagreement between raw
and converted motion could implicate conversion sensitivity even when static
contour distances pass. Static fidelity does not establish derivative fidelity.
This addition preserves the existing inverse update.

### Frozen states

**The requested historical states are available locally.** A read-only artifact
inventory found:

| Bundle | Saved accepted states | Available weight evidence |
|---|---:|---|
| September 8 circle | 0–60 | All 8,577 weights and accepted steps at every state |
| September 8 wrong-start star | 0–47 | All 8,577 weights and accepted steps at every state |
| Iteration-1 `phase_bc/start-at-truth` | 0–3 | All 8,577 weights and accepted steps at every state |

These vectors are in `kress_trajectory.csv`, not
`kress_accepted_iterates.json`. In all three bundles, successive weight
differences exactly match the recorded accepted steps, and the final vectors
exactly match `kress_model.pt`. The response archives also retain the converted
geometry trajectories. Thus circle state 55 and early/intermediate star states
need not be replaced by fresh training.

The checkpoint stores optimizer configuration and diagnostics, **not Adam
moments**. Preserve the guide's restriction on claiming historical proposals.
The final circle gradient was not evaluated by the capped run; any new
gradient there must be labelled a fresh frozen-state evaluation. Before using
reloaded states, reproduce their saved geometry and loss under the recorded
configuration and check parameter order and relevant source provenance.

### Directions and scales

**Proceed with both actual magnitudes and a common diagnostic scale.** Report
the unscaled proposal, then compare spectral shape at equal small RMS predicted
normal displacement. Otherwise a larger motion can look worse solely because
it is larger. Keep the original magnitudes for data/Eikonal cancellation and
for the actual accepted-step analysis. Mark zero-motion directions explicitly.

The production fallback is
`-g_total * learning_rate / max(||g_total||_inf, 1)`, followed by controller
projection. Without active parameter bounds it is collinear with `-g_total`;
their normalized spectra should agree. It is not an independent direction.
Pair an accepted step **into state k** with the gradient and geometry at
**state k-1**. Using the destination gradient would answer a different question.

### Spectral content

**Keep modes 0–20, but qualify energy and usefulness.** Use an arc-length
weighted inner product, a normalized Fourier basis and a declared phase origin.
Refine contour sampling until the reported coefficients and residual energy
stabilize. Energy beyond the fitted range is unresolved sampled energy, not a
measurement of every higher mode. The 64-node circle is not a convergence
certificate for the tail merely because 41 columns can be fitted.

Modes above 10 are **untested**, not established data-null or harmful modes.
In fact, modes 0–20 have 41 real columns: paired-8 at two frequencies has only
32 real residual entries and must have a null space in that expanded probe
space. Paired-12 has 48 entries, but dimension alone does not establish its
rank. If a direction is called weakly observed, measure its normalized data
sensitivity on the actual frozen contour.

For circle, `m >= 2` motion can remove existing noncircular error. For star,
necessary lobe corrections need not stay within low arc-length modes. Compare
signed motion with the current geometric error where a local correspondence
exists, and confirm the resulting actual shape change. Report star fit residuals
and phase reliability as amplitude becomes small. Low-mode energy or unsigned
amplitude/rotation correlation alone does not identify recovery.

## 5. Priority B — validate the induced-motion diagnostic

**Agree; make this a prerequisite to interpretation.** Compare signed normal
displacements using a consistent local correspondence, such as nearby
intersections with the baseline normals. Subtracting equal node indices after
arc-length redistribution can mix tangential relabelling with shape motion.
A symmetric set distance alone does not validate the sign.

On a regular branch, expect displacement prediction error of order `alpha^2`,
or velocity error of order `alpha` after dividing by the step, within a resolved
window. Extraction, projection and polygon sampling eventually impose an error
floor; failure to improve below that floor is not evidence against the formula.
Record correspondence failures and discrete conversion-branch changes separately.
Historical accepted steps outside the linear window still have measurable
actual contour changes; do not silently omit them from the trajectory account.

## 6. Priority C — data versus Eikonal geometry

**Agree, with the same fixed regularizer samples and boundary metric.** Reuse
the saved seed, domain, sample count and penalty weight. Report weight-space
and arc-length weighted boundary-space cosines together with magnitudes;
cosines are undefined for a zero boundary-motion component.

Opposition to data descent does not itself make a regularizer harmful: it may
oppose a geometrically wrong data direction. Conversely, small immediate
zero-contour motion does not make Eikonal irrelevant. It may change spatial
gradient quality, projection behavior and future conversion feasibility.
An ablation should be motivated by measured geometric or feasibility harm,
then tested with the same fidelity contract. Do not decide from gradient norms
or high-mode energy alone.

## 7. Priority D — raw descent and optimizer geometry

**Proceed, comparing Adam primarily with total-gradient descent.** Production
Adam receives the clipped data-plus-Eikonal gradient. Comparing it only with
the raw data gradient confounds regularization and optimizer effects. Save
moments, optimizer step count, clipping, proposal, backtrack factor and fallback
resets in fresh controlled runs. Compare actual proposal magnitudes and equal
RMS small motions separately.

Repeated harmful distortion at matched states would justify an Adam-specific
experiment. Amend the stronger statement that a poor raw gradient makes an
optimizer change inappropriate: a scaled GN/TSVD direction could improve a poor
Euclidean gradient. That outcome would motivate a metric/conditioning study;
it would not establish Adam as the historical cause. Signed improvement on the
actual candidate remains the relevant evidence.

## 8. Priority E — short multistatic neural ablation

**Retain as the first isolated acquisition change, after bounded integration
checks.** E0 paired-8 versus E1 multistatic-8 isolates readout using the same
eight sources and receivers. The historical 12-pair run cannot substitute for
E0. Both arms must start from the same saved weights and optimizer state;
if moments are reset, reset them in both arms. Reuse the same Eikonal samples.

Indexed forward/adjoint building blocks do not yet establish the full neural
driver path. Before either short inverse, verify observation indexing against
the independent oracle, paired selection equivalence, the normalized neural
gradient against fresh weight-direction differences, and candidate rollback.
Validate forward and derivative resolution on the actual starting MLP curve;
the analytic-star 256/512-node study does not qualify every 194-node Method-B
candidate.

### Scaling and work

Use an explicit objective. The current
[normalization](../../../../../solvers/sdf_inverse/optimization.py) is
`L_data = 0.5 * sum_f w_f * ||prediction_f - observation_f||^2 / s_f^2`,
where `s_f` is the fixed observed-column norm with its recorded floor. Preserve
that rule, two unit-weight frequency terms and the 0.01 Eikonal coefficient
for the first comparison; record each arm's scales and data/regularizer
gradient magnitudes. Do not introduce an additional entry-count division.

This preserves the relative-error objective convention, not identical
boundary forces or effective regularization at every state. Arm-specific
response norms change the weighting of the selected entries. Report that
effect explicitly instead of attributing every improvement solely to additional
information. Any different normalization is a separately declared choice.

Three to five accepted updates are a useful diagnostic cap, but not a tight
runtime limit. With two directions and 15 trial magnitudes, five updates could
require 150 candidate evaluations plus initialization. Declare an attempted-
evaluation and wall-time cap as well; count geometry failures, forward and
adjoint work, and evaluation replay separately. Report budget exhaustion as
such rather than forcing five acceptances.

### Decision

Consistent useful lobe motion under valid actual candidates warrants proposing
one longer matched acquisition comparison. It does not automatically authorize
it. Fix the evaluation acquisition as well as its frequencies across arms;
reserve frequencies against the union of E/F and any subsequently proposed
continuation stages. The validated 3 GHz set is a candidate. Keep evaluation
out of acceptance and setting selection; if used to select a method, describe
it as validation and reserve a separate final test.

## 9. Priority F — frequency after multistatic

**Retain conditionally; correct the continuation decision.** A short direct
`{1.5, 2.5}` GHz run that improves actual geometry supports a direct frequency
change. It does not establish that a staged continuation path is needed or
better. Continuation requires its own basin hypothesis and comparison against
a direct run with comparable total work.

Run F from the same frozen weights, with matched optimizer initialization,
normalization convention, two frequency terms and work caps. E1 can serve as
F0 if these settings are identical. A conversion-blocked E experiment should
first resolve that obstruction, rather than automatically trigger F. The
historical star's 2.5 GHz holdout becomes training in F and cannot retain its
holdout label there.

## 10. Conditional neural GN / TSVD diagnostic

**Agree with deferring production integration.** Use the Jacobian of the same
real-stacked, normalized residual as acceptance, through the actual conversion
path. Declare parameter scaling, damping, truncation and the regularization
objective. Use a different symbol for damping than the Eikonal coefficient.
A data-only GN step still has to pass the unchanged regularized acceptance
test; damping alone does not implement that regularizer or a prior-centred IRGN.

Budget Jacobian construction separately. The residual dimension is 32 for
paired-8, 48 for paired-12 and 256 for multistatic-8 at two frequencies. A small
data-space linear solve does not make construction of all neural sensitivities
free. Compare induced motion and actual admissible candidates before adding
an optimizer to the production driver.

## 11. Star terminal conversion-refinement stop

**Agree; run this early enough to qualify the late-star diagnostic.** Retain
the distinction between the near-limit final state and the already collapsed
lobes. Do not relax either fidelity limit or infer recovery from a smaller step.

There is a concrete coupling to handle in the
[current audit](../../../../../solvers/sdf_inverse/geometry.py): its base grid
is `max(257, production_grid)` per axis and its sample count is
`max(512, 4*bandwidth + 4)`, each followed by a refined level. Raising production
resolution can therefore also change the independent audit. Explicitly freeze
one while varying the other in the diagnostic; a simple production-grid sweep
does not isolate them.

Record both directed raw/converted distances, the two level errors and their
change, with branch and sampling checks. Stability at one refinement pair is
not a continuous-contour certificate. Include arc-length integration and
adequate BEM resolution when changing production bandwidth. Any numerical
repair needs evidence of a useful admissible motion, not just a passing
distance at the unchanged accepted weights.

## 12. Circle control

**Keep it, but amend the question.** The evidence shows late sampled boundary
error worsening while loss falls; it does not yet show that the update is
generating harmful `m >= 2` motion. Measure whether it creates those errors,
corrects some while worsening others, or primarily changes converted geometry.
Retain the historical maximum node-to-target metric and supplement it with
resolved signed/RMS shape diagnostics. Agreement with the star would support a
shared mechanism only after these distinctions are checked.

## 13. Ellipse execution gap

**Agree with the proposed capture and qualification.** Save fresh initialization
weights before any geometry construction that can fail, and persist per-stage
logs and traceback even if no final metrics are written. Also identify the
stage: the driver builds the exact-target fitting control before the inverse,
so a startup failure need not occur on the wrong initial ellipse itself.

The archived 3.211626 mm distance and 0.073997 mm refinement change are strong
evidence that the reused circle settings need qualification. They do not
recover the missing traceback or fresh production weights. Keep any new
reproduction separate from the failed arm, qualify exactly its saved weights,
and avoid another long ellipse run until startup passes unchanged tolerances.

## 14. Runtime profiling

**Agree.** Begin with a valid frozen evaluation and representative saved
geometry-rejected trials, then instrument any new short run. Report exclusive
timings or explain nesting so extraction and MLP evaluation are not counted
twice. Include adjoint/Method-B reverse, audit extraction and post-run replay.
Profile before globally increasing resolution; require a proposed speedup to
preserve measured geometry, objective and acceptance decisions.

## 15–16. Execution order and the next-run decision

**Retain the research direction, with explicit gates between stages.**

| Order | Bounded work | Required result before advancing |
|---|---|---|
| 1 | Restore selected real states; capture ellipse startup; profile and audit final-star conversion | Reproduced state/geometry/objective or a specific recorded discrepancy |
| 2 | Validate raw and converted motion; analyse accepted updates and data/Eikonal directions | Resolved signed motions and spectra, with corrective versus harmful changes distinguished |
| 3 | Fresh matched optimizer proposals where historical moments are missing | Actual total-gradient/Adam comparison with declared scale and saved state |
| 4 | Validate indexed neural integration; short E0/E1 comparison | Valid actual-network geometry and a measured acquisition effect within work caps |
| 5 | Conditional F or a bounded GN direction diagnostic, as the preceding result warrants | Evidence for a specific frequency or metric hypothesis |
| 6 | Write the measured decision table and propose one principal long-run change | A reviewed question, fixed controls, disjoint evaluation and explicit total budget |

Treat section 15's stop-and-review requirement as controlling the earlier
section-8 suggestion to authorize a long run immediately. Do not require every
conditional branch to execute if an earlier result supplies a clear decision.
Allow the table to say **unresolved**; numerical audit sensitivity and contour
complexity can coexist, and a three-step outcome need not settle a nonlinear
recovery question.

## 17–18. Deferrals and proposed verdict

**Agree with the deferrals; keep the closing hypothesis conditional.** The
established conclusion is narrower: the tested physical inverse is locally
informative, target fitting is much better than wrong-start recovery, and
weight-induced raw and converted motions now need direct measurement.

If that measurement supports the hypothesis, choose the specific tested change
that improves valid actual-MLP geometry. A high-mode tail alone does not justify
smoothness penalties, better local conditioning alone does not justify a long
acquisition run, and a successful high-frequency start does not establish
continuation. Preserve the fidelity contract and the one-principal-factor
comparison.

## Deliverable and review validation

The next deliverable should report separately **what the weights do to the raw
interface**, **what conversion passes to Kress**, and **which controlled change
improves the actual recovered geometry**. Link those measurements to the
existing failure evidence and leave absent or inconclusive results explicit.

This review checked the supplied iteration records, the relevant current
implementation, and the three saved trajectory/checkpoint inventories above.
Exact accepted-step differences and final-checkpoint weight agreement were
verified. Markdown links and whitespace were checked. No new motion experiment,
inverse, or production test suite was run, and no production implementation or
historical result was changed. The new mathematical and experimental checks
above are recommendations, not claimed measurements.
