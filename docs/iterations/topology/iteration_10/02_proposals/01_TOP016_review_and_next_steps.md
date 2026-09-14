# TOP-016 review — expose the intervention before judging it

Prepared 2026-09-14. Read-only review of `track/topology-TOP-016` at
`9ad3c8b191c7f1130764c0476480290b0f6a6e4a`. No repository BIE or inverse was rerun
for this review. The small analytic geometry illustration below is explicitly
separate from the repository's measurements.

**Recommendation:** close TOP-016 as recorded; propose one bounded TOP-017
continuation from its saved endpoints. Repair the experiment's stage-transition
semantics, not the optimizer or the topology architecture. Keep the adverse
merge result and audit its representation assumptions. Do not promote a policy
or run the twelve-scene suite.

## 1. Findings that change the next decision

| Evidence | Interpretation supported |
|---|---|
| Added-frequency screen gains of 21.4038 for `far-two-stars` and 17.6264 for `central-ellipse-star`, eight usable directions each | Added frequencies carry useful local shape sensitivity under the measured protocol. Not proof of recovery. |
| Both principal S/F pairs stopped in the identical 0.5-GHz first stage | The principal comparison never tested the intended acquisition difference. Matching endpoints are not a negative result for frequency continuation. |
| Central case: 9.223 → 8.815 mm, IoU 0.7775 → 0.9097, worst evaluation error 0.8922 → 0.5214 | Genuine mixed progress under the shared low-frequency stage, still outside boundary and prediction gates. |
| Two-star case: 11.991 → 12.033 mm | No useful boundary improvement in that bounded low-frequency continuation. |
| Merge F completed: 0.5542 → 1.1082 mm and worst evaluation error 0.09398 → 0.16795 | A measured adverse control result. It remains a blocker to promotion. |
| Principal/local endpoints have missing newly evaluated terminal gradients | Do not infer endpoint stationarity from older gradient files or from a resource stop. |

Sources: [result report][R1], [independent closeout][R2], and [iteration-10 handoff][R3].
The implementation recorded 10,306 attempted/completed frequency solves with no
failed solves. Do not repeat those experiments to recreate summaries.

## 2. The main problem is in the contract and orchestration

The approved TOP-016 contract treated stage-budget exhaustion as an inconclusive
trial termination. `run_top016_pilot.py` implements that interpretation: after
saving/scoring an endpoint, a terminal `failure_type` of `Budget` breaks the
outer stage loop. Its `TrialLedger` also used the broad budget exception for
stage reservations. This was not an agent refusing to follow the plan.

The previous handoff therefore had a design defect: it could spend its first
allocation without ever exposing the experimental arm to new training data.
Tightening low-frequency stopping and using a finite-difference Jacobian in
34 reduced directions made that failure mode material. The tiny local-control
allocation encountered the same obstruction. [R4], [R5]

**Correction for the new contract:** a stage quota is a planned transition from
one objective to the next, provided the retained state is valid and numerical
checks pass. A whole-trial solve cap, wall limit, unresolved numerical problem,
or implementation error is a hard stop. These are different events, not
alternative descriptions of one exception.

This is a quota-limited continuation experiment. Completing its schedule does
not certify convergence at any stage. Conversely, a planned quota transition
need not make the *whole bounded protocol* incomplete. TOP-016's historical
classification remains unchanged.

## 3. The merge regression needs a small audit, not a replacement optimizer

The final merge error is not uniformly worse at every frequency:

| Quantity | Initial | Final F |
|---|---:|---:|
| 0.5-GHz relative error | 7.8788e-05 | 2.1288e-04 |
| 0.75-GHz relative error | 1.1153e-03 | 7.0344e-04 |
| 1.0-GHz relative error | 1.1289e-02 | 2.2832e-03 |
| 1.25-GHz relative error | 4.1032e-02 | 8.5188e-03 |
| 1.5-GHz evaluation error | 0.04708 | 0.02652 |
| 2.5-GHz evaluation error | 0.09398 | 0.16795 |

The deterioration is visible already after the first added-frequency stage:
boundary error changes from 0.5355 mm after stage 1 to 0.9212 mm after stage 2,
while 2.5-GHz error rises from 0.09807 to 0.15360. Endpoint production/refined
prediction discrepancies are tiny. This is a frequency-dependent trade-off in
the recorded fit, not evidence by itself of a bad BIE quadrature. [R6]

A missing control qualification also matters. The merge truth is an ellipse
with semiaxes 92 and 39 mm. TOP-016's representation audit explicitly loops over
only the two principal scenes. It never qualified the merge truth in the same
constrained K=9 chart. [R7], [R8]

An ellipse is low-order Cartesian Fourier in its eccentric-anomaly parameter,
`(a cos t, b sin t)`. It is not generally low-order in the imposed *polar-angle*
parameter:

\[
\gamma(\theta)=x_0+r(\theta)(\cos\theta,\sin\theta),\qquad
r(\theta)=\frac{ab}{\sqrt{b^2\cos^2\theta+a^2\sin^2\theta}}.
\]

Here `a,b` are the semiaxes, `x_0` is the centre and `theta` is polar angle. The
current constrained Cartesian K=9 space corresponds to radial modes through 8;
this is a policy restriction, not a limitation of unrestricted Cartesian curves.

**Illustration calculated for this review, not a repository recovery result:**
sample the analytic radius at 32,768 uniform polar angles, take its real FFT,
zero modes above 8 or 16, invert the FFT, and compare the resulting curves using
dense bidirectional nearest-neighbour distances. The sampled errors are about
**0.50628 mm** at radial degree 8 and **0.01045 mm** at degree 16. This is one
specific projection, not the repository's fitter, a globally optimal Hausdorff
approximation, or a lower bound on attainable inverse error. In particular it
**does not prove the 1-mm gate impossible**. It motivates checking the omitted
control rather than assuming the 0.1-mm representation qualification extends to
it.

TOP-017 permits only an evaluation-only K=9/K=17 geometry/prediction audit for
this control. No high-bandwidth inverse, fitted ellipse-family replacement,
new prior, or favourable control substitution follows automatically. A poor
projection alone cannot prove the current chart incapable; an attainable
counterexample is not an optimality certificate.

## 4. Decisions

| Recommendation | Decision |
|---|---|
| Preserve TOP-016 as complete bounded execution with inconclusive principals and adverse merge control | Accept. No historical rewrite. |
| Increase the first-stage budget and repeat all runs | Reject. Reuse the saved common-stage endpoints and spend work on the untested stages. |
| Rerun the successful sensitivity screen or oracle generation | Reject unless a specific source/input mismatch invalidates reuse; that mismatch stops this contract rather than silently regenerating data. |
| Let every budget exception advance the schedule | Reject. Only a typed, planned stage-quota event can advance. |
| Audit merge representability and frequency trade-offs | Accept, within a small non-optimization budget. |
| Change K, regularization, damping or topology policy during the principal comparison | Reject for TOP-017. |
| Immediately rerun the merge optimizer or the two local controls | Defer. Their current evidence remains visible; they are not necessary to expose the principal acquisition intervention. |
| TOP-013/014/015, MLP, adjoint or Boundary–BIE redesign | Remain deferred/superseded as recorded; not released by this review. |

The proposed execution contract is [../03_plan.md](../03_plan.md). The small
shared-principles amendment is [02_staged_execution_addendum.md](02_staged_execution_addendum.md).

## 5. Literature support and limits

**L1. Borges & Greengard, _Inverse obstacle scattering in two dimensions with
multiple frequency data and multiple angles of incidence_ (2014), §§3–4.**
Band-limited updates and frequency continuation are used together; the Newton
solve has iteration, update-size and residual stopping criteria. This supports
bounded inner solves as a legitimate design component, not our exact quotas or
a guarantee of recovery from an unconverged low-frequency state.
https://arxiv.org/abs/1408.5436

**L2. Borges, Rachh & Greengard, _On the robustness of inverse scattering for
penetrable, homogeneous objects with complicated boundary_ (2022), §2.1 and §4.**
The transmission setting is closer to this project. The work distinguishes
representation/update bandwidth, regularization, acquisition and optimization.
Its usual frequency marching solves successive single-frequency problems; our
cumulative objective is a declared variant. Neither its parameterization nor
its plane-wave/multistatic acquisition is the repository's paired TMz setup.
https://arxiv.org/abs/2210.11607

**L3. Borges & Rachh, _Multifrequency inverse obstacle scattering with unknown
impedance boundary conditions using recursive linearization_ (2021), §6.**
Their experiments exhibit lower intermediate residual but worse final shape
for one optimization variant, and discuss the interaction between termination
and frequency continuation. This supports retaining prediction/geometry gates;
it does not diagnose the merge regression or prescribe its cure.
https://arxiv.org/abs/2104.13489

All quotas and decision thresholds in TOP-017 are operational project choices,
not constants justified by these papers. Later full-suite qualification and
truly untouched generalization data remain separate requirements.

## Evidence pointers

[R1]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/results/validation/topology/TOP-016-20260914-fixed-topology/README.md
[R2]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/results/validation/topology/TOP-016-20260914-fixed-topology/closeout_review.md
[R3]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/docs/iterations/topology/iteration_10/01_results.md
[R4]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/docs/iterations/topology/iteration_09/03_plan.md
[R5]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/run_top016_pilot.py
[R6]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/results/validation/topology/TOP-016-20260914-fixed-topology/runs/F-merge/metrics.json
[R7]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/config/topology_scenes_v1.json
[R8]: https://github.com/ShiyuanDeng/Neural-BEM/blob/9ad3c8b191c7f1130764c0476480290b0f6a6e4a/run_top016_preflight.py
