# Purpose of the clean adaptive-continuation pipeline

2026-09-23. Research direction recorded from the user's discussion following
SC-018 and SC-019. This note defines the intended outcome and its scientific
purpose; it is not an implementation plan or a report of completed cleanup.

## The research question we want to answer

We want to understand **when and how an inverse solver should change the
frequencies it fits and the shape degrees of freedom it uses**, so that it
recovers geometry more reliably or reaches a given accuracy at lower cost.
The numerical foundation should let us attribute an outcome to those
decisions. A fixed schedule and an adaptive policy should be interchangeable
strategies acting on the same qualified inverse.

The cleanup serves that question. Its intended product is a separate, clean
implementation with a clear adaptive policy interface, grounded in the
successful numerical behavior of the original explicit Cartesian Fourier /
nodal Kress–Müller pipeline. The original files remain the numerical reference.
Existing forward routines, derivatives, diagnostics and controller machinery
remain useful wherever their behavior is qualified.

## Why this distinction matters now

Three objectives became entangled: cleaning the software dependencies,
reproducing a Borges-inspired inverse, and studying adaptive continuation.
The new implementation changed the inner optimization method, shape update
coordinates, frequency objective and admissibility rules alongside the
continuation machinery. Consequently, a comparison between the two complete
pipelines could not isolate the effect of an adaptive policy.

[Iteration 05](../../iteration_05/01_results.md) established the recovery gap
on existing single-object fixtures. [Iteration 06](../01_results.md) identified
a local benefit from step halving and a curvature setting that excludes the
exact star at the available final band. These findings motivate a clearer
separation of responsibilities. They do not establish that adaptive
continuation conflicts with the original inverse, or that the new geometry
representation is intrinsically inadequate.

A restricted shape space can intentionally exclude fine detail early in
continuation. Its meaning depends on how the policy eventually releases that
restriction, the available measurements and the desired recovery accuracy.
Such choices need to be visible experimental controls rather than assumptions
inherited unnoticed from a different reference problem.

## What we mean by a clean implementation

Cleanliness means understandable ownership of state, numerical decisions and
dependencies. It should preserve the original solver's established damping,
regularization, step bounds, acceptance and stopping behavior while removing
unnecessary coupling to neural/SDF orchestration and historical drivers.
Those safeguards embody numerical experience and belong in the baseline.

The desired separation is:

| Component | Responsibility |
|---|---|
| Geometry and physics | Represent the boundary, evaluate scattering and sensitivities, and establish adequate numerical resolution. |
| Inverse backend | Execute well-defined optimization steps, including regularization, local step control, admissibility, acceptance and stopping diagnostics. |
| Continuation policy | Decide which frequencies or frequency sets and shape subspaces to use, when to reconsider them, and how much work to allocate. |
| Experiment and evaluation | Supply matched inputs, record decisions and costs, and assess reconstruction and prediction independently of the optimizer. |

This separation can be reached while reusing qualified routines. It does not
require independent copies of every solver or a large general-purpose
framework. A wrapper around the original solver can provide the initial
connection, while the intended endpoint is a clean backend with only the
dependencies needed for its numerical work. The original implementation
provides a reference against which extraction and later changes can be checked.

Changing a derivative, parameterization or optimizer remains a distinct
numerical intervention. A cleaner organization should reproduce the
reference behavior under declared tolerances; numerical differences should
have an explicit reason and supporting evidence.

## What the adaptive policy interface should make possible

A policy should receive the current accepted reconstruction, the available
training measurements, optimization history and measured diagnostics. These
may include residuals, sensitivities, conditioning, model prediction quality,
rejection reasons and remaining work. Truth and evaluation observations are
outside this interface.

Its decisions should be explicit and reproducible. The interface should
accommodate a fixed schedule, selecting the next frequency, retaining a
cumulative frequency set, changing the active shape subspace, or spending
more work at the current stage. A single-frequency objective is one supported
choice; it should not be an architectural requirement for adaptive research.

Policies need stable meanings for their controls. An update harmonic, a
stored curve coefficient and a quadrature node are different quantities.
Likewise, Cartesian and arclength-normal harmonics require an explicit
coordinate relationship before a sensitivity-based rule can be transferred
between them. The interface should expose those distinctions and any
coupling to curvature or other admissibility constraints.

Local optimizer safeguards should be shared across policy comparisons.
Research on adaptive regularization or admissibility is also possible, but
those changes must be identified as additional experimental factors. A
policy should not gain an apparent advantage through an undisclosed change
to the backend or feasible set.

This lets us study several kinds of policy on common ground: prescribed
ladders, residual-based rules, sensitivity/atlas-based rules and rules based
on the measured validity of a local model. A policy can be replaced without
rewriting the inverse or changing what an accepted step means.

## How this supports reliable, publishable evidence

The central benefit is an interpretable comparison. With the same backend,
observations, starts and numerical safeguards, differences in recovery or
cost can be connected to declared policy decisions. The successful original
cases provide regression anchors; they are not sufficient by themselves to
establish general robustness or a publishable adaptive-method claim.

The evidence we want to produce has several properties:

- **A credible reference.** Adaptive policies compete with a strong fixed
  strategy on the same backend. Necessary shared repairs remain explicit.
- **Meaningful outcomes.** Comparisons assess geometry, independent prediction,
  success across starts and cost at comparable accuracy. A lower training
  residual or an earlier unsuccessful stop is not automatically an improvement.
- **Complete cost accounting.** Sensitivity construction, frequency probes,
  rejected trials, qualification and repeated work count toward the method's
  cost. Solve counts and wall-clock measurements have stated interpretations.
- **Reproducibility.** Inputs, numerical settings, source versions, policy
  decisions, checkpoints and failure reasons support replay and independent
  inspection. Reports can be rebuilt from retained evidence.
- **Separation of development and evaluation.** Cases used repeatedly to choose
  settings are development evidence. Claims about generalization need untouched
  cases or measurements, with scope appropriate to the claimed application.
- **Honest limits.** Numerical failure, inadmissible geometry, lack of useful
  descent and exhausted work remain distinguishable. Negative and inconclusive
  results stay visible alongside successful reconstructions.

In the longer term, this should let us answer where adaptation helps, which
diagnostic predicts that benefit, what the diagnostic costs, and where the
policy ceases to be reliable. A reproducible explanation of limited benefit
can also be scientifically useful. Clean software makes those questions
testable; novelty and publishability still depend on the resulting evidence.

## The role of the Borges reference

The Borges-inspired method remains a valuable reference configuration and a
source of ideas about continuation, shape updates and regularization. Its
reproduction has its own fidelity question and documented differences in the
[paper audit](../../../../../experiments/shape_continuation/PAPER.md).

That configuration should coexist with the original robust backend through
explicit interfaces. Matching a particular reference driver should not
silently determine the optimizer or admissible geometry used in every
adaptive-policy experiment. Keeping these purposes distinct allows us to
learn from the reference while testing the actual research hypothesis.

Success for this cleanup means that we can introduce a new continuation
policy, compare it fairly against the fixed baseline, explain its successes
and failures, and reproduce the evidence without questioning whether an
unrelated rewrite changed the experiment underneath it.

This direction follows the shared
[research implementation principles](../../../implementation_principles.md).
