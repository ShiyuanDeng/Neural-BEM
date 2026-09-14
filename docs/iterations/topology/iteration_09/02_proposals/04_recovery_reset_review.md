# Review: stop the topology debugging cascade and isolate recovery

Prepared 2026-09-14 against `feature/ordered-boundary-nystrom` at
`9acae6bac060e84704d938e9a1e63407971841e7`.

- **Document role:** scientific review and next-step recommendation.
- **Execution authority:** none by itself; the bounded successor is **TOP-016** in [the consolidated plan](../03_plan.md).
- **Evidence scope:** review of committed documentation, selected source and recorded results; not an independent rerun.
- **Implementation owner / execution reviewer:** unassigned.

## 1. Structural decision

Keep this review in **iteration 09**. That cycle already contains the TOP-011/012 results and the unexecuted TOP-013/014/015 proposals. There is no reason to create another folder just to reconsider their priority.

Use `iteration_09/03_plan.md` for the new consolidated contract. TOP-016's executed results will open `iteration_10/01_results.md`, including when its answer is negative or budget-limited. Do not create iteration 10 now and do not modify the historical iteration-08 executed plan.

This follows [the shared workflow](../../../README.md). Broader implementation discipline belongs in [the shared principles](../../../implementation_principles.md), not in repeated copies across topology handoffs.

## 2. Verdict

Keep the existing Fourier geometry, Müller/Kress forward and hybrid topology/shape architecture. Freeze new event mechanisms and optimizer redesign. Test whether fixed-topology shape refinement benefits from a bounded frequency-continuation protocol before blaming the automatic topology policy for those shape failures.

This is a change in research priority, not a conclusion that all remaining problems are caused by insufficient data. Optimization, constraints and acquisition can remain interacting limitations.

## 3. Correct the evidence summary before choosing the next experiment

### Some corrections did improve geometry

The phrase “four fixes improved the objective and none improved reconstruction” is too broad. TOP-008's fixed-topology comparison reduced matched boundary error from **18.624 to 9.070 mm**. Its full-suite split case improved from **0.17521 to 0.000023357 mm**, with **1,172 versus 281** recorded BIE solves. The suite still passed 5/12: no additional pass is not the same as no geometric benefit.

The full-suite effects were mixed. Under arm H, `central-ellipse-star` finished with the correct count, while `far-ellipse-star` and `empty-ellipse-star` ended with three components against two in the truth. Retain those regressions as well as the improvements. [E1]

TOP-009/010's difficult two-star continuations are a narrower and legitimate concern: substantially lower training objective did not yield an acceptable reconstruction. Do not generalize that result to every earlier intervention. [E2, E3]

### Tolerance membership is not absence of information

TOP-011 finds large boundary movements that remain inside the 0.003 relative-error tolerance. This establishes that the threshold is not a geometric certificate. It does not establish equal objective values, zero informative gradient, or impossibility of more accurate discrimination using the same observations. [E4]

The saved two-star plateau is not stationary under the reported gradient test and remains well above the objective attained by the true geometry. That prevents both “the optimizer is finished” and “optimization alone will definitely fix it” conclusions. [E3]

### Local displacement probes do not certify distance to truth

The TOP-011 walks start around incorrect boundaries and probe one singular direction at a time. Their large displacements witness ambiguity; their largest measured displacement is not a bound on the complete nonlinear admissible set.

Even a valid small local neighbourhood around a reconstruction need not be centred on the truth. TOP-014's proposed calibration must therefore not be called a certificate of 1-mm reconstruction accuracy. Preserve historical `recovered` strings, but report their meaning as **data-fit threshold reached** rather than geometric recovery. [E4]

### Similar spectra are not equal sensitivity directions

TOP-012's `stage2b_redundancy.py` compares observation norms and singular-value lists. It does not establish equality of the right-singular directions or of the information matrices. In general,

\[
\operatorname{spec}(J_1^T J_1)\approx\operatorname{spec}(J_2^T J_2)
\quad\not\Rightarrow\quad
J_1^T J_1\approx J_2^T J_2.
\]

Here `J_1` and `J_2` are residual Jacobians expressed in the same coefficient coordinates, and `spec` denotes eigenvalues. The lack of improvement from the tested 24-to-48 paired-ring enrichment remains a valid observation. Its stronger “same directions, no spatial information left” explanation needs more evidence. [E5, E6]

Likewise, interleaving samples of one paired transmitter/receiver acquisition does not exhaust independently varied transmitter/receiver configurations, offsets or full multistatic measurements. Close the tested oversampling strategy; do not declare all spatial acquisition alternatives exhausted.

### Additional training frequencies need not consume existing evaluation frequencies

The proposed training schedule is **0.5, 0.75, 1.0 and 1.25 GHz**. The existing **1.5 and 2.5 GHz** observations remain unfitted. This is a separately named experiment; v1 and v2 must remain unchanged.

Those evaluation frequencies have already informed repeated research decisions, so describe them as development evaluation data rather than a fresh blind final test. There is no claim that 1.25 GHz is sufficient for the target accuracy; that is what the bounded pilot tests.

### A nonlinear residual does not by itself justify a new optimizer

For real coefficients `c` and a real residual vector `r(c)` formed by stacking real and imaginary data residuals,

\[
\Phi(c)=\tfrac12\|r(c)\|^2,\qquad
\nabla^2\Phi=J^T J+\sum_i r_i\nabla^2r_i.
\]

`J` is the residual Jacobian. Gauss–Newton already has a quadratic objective model. A finite-step failure of residual linearization does not establish that its omitted residual-weighted Hessian term is the dominant recovery bottleneck. TOP-013 can remain a fallback diagnostic, but extra descent alone must not automatically release an optimizer implementation.

## 4. Literature rationale and limits

**[L1] Carpio, Dimiduk, Le Louër and Rapún (2019), _When topological derivatives met regularized Gauss–Newton iterations in holographic 3D imaging_.**
<https://arxiv.org/abs/1903.12202>

They combine topological derivatives with regularized Gauss–Newton refinement and allow the number of objects to change. This supports retaining the hybrid architectural idea. Their 3D Maxwell holography setting does not validate our 2D TMz candidate rules, acquisition, thresholds or accuracy claims.

**[L2] Borges and Greengard (2014 preprint; subsequent SIAM publication), _Inverse obstacle scattering in two dimensions with multiple frequency data and multiple angles of incidence_.**
<https://arxiv.org/abs/1408.5436>

Band-limited boundary recovery and recursive linearization motivate matching shape complexity to measurement information. Their sound-soft far-field problem differs from dielectric transmission. TOP-016 deliberately holds available shape capacity fixed to isolate an initial comparison; it is not a reproduction of their complete bandwidth schedule.

**[L3] Borges, Rachh and Greengard (2022 preprint), _On the robustness of inverse scattering for penetrable, homogeneous objects with complicated boundary_.**
<https://arxiv.org/abs/2210.11607>

This is a closer transmission analogue and studies shape and volume representations within recursive linearization. Importantly, its comparisons find the volumetric approach more robust. Cite that limitation too: the paper motivates a controlled continuation test, not a claim that boundary methods are universally best or guaranteed to converge. A volume-method rewrite is outside this experiment.

**[L4] Borges and Rachh (2021), _Multifrequency inverse obstacle scattering with unknown impedance boundary conditions using recursive linearization_.**
<https://arxiv.org/abs/2104.13489>

The paper develops frequency continuation and discusses success and failure mechanisms in a nonlinear, nonconvex shape inverse. Its impedance setting is different. Use it to motivate continuation and careful trajectory evaluation, not to equate lower residual with reliable reconstruction.

**[L5] Transtrum and Sethna (2012), _Geodesic acceleration and the small-curvature approximation for nonlinear least squares_.**
<https://arxiv.org/abs/1207.4999>

This is a targeted second-order least-squares option to consider if a later experiment demonstrates that the local model is the practical bottleneck. It is not authority to implement a new optimizer merely because a finite-step linearization error exists.

The particular frequencies, screening thresholds and compute caps in TOP-016 are **project choices**, not parameter values prescribed or guaranteed by these papers.

## 5. Resolve the pending recommendations

| Recommendation | Decision | Consequence |
|---|---|---|
| Preserve the hybrid controller and the demonstrated numerical corrections | Accept | Freeze them during the diagnostic; list enabled options explicitly |
| Make TOP-013 curvature work the leading experiment | Defer | No curvature implementation or automatic descent-to-implementation escalation in TOP-016 |
| TOP-014 documentation clarification | Accept with amendment | Explain `recovered`; retain historical machine-readable strings |
| TOP-014 tolerance-to-truth certificate and immediate suite | Reject as formulated | Local walks do not provide that certificate |
| TOP-015 richer frequencies | Accept with replacement scope | TOP-016 provides a paired fixed-topology pilot with the old evaluation frequencies left unfitted |
| “Frequency is the only acquisition option left” | Reject | Only the tested paired-ring densification has been investigated here |
| Full twelve-scene rerun before demonstrating pilot benefit | Defer | Qualify the pilot first; then design one matched suite in the next cycle |
| New topology mechanisms, MLP revival, BIE replacement or a general experiment framework | Defer | Not authorized by this review or TOP-016 |

On adoption, mark TOP-015 **SUPERSEDED by TOP-016** in a dated status amendment without erasing the original proposal. Record TOP-013 and TOP-014 as deferred/not selected in the handoff; do not claim they were executed or rejected by numerical experiments.

## 6. The next decision

The comparison should distinguish:

1. **Both acquisitions recover from the saved state:** investigate controller use of a now-capable shape inverse; do not assume more frequencies were necessary.
2. **Only the continuation arm recovers or materially improves:** the protocol merits a matched automatic-controller qualification, not a retrospective v1 success claim.
3. **Neither recovers despite useful added sensitivity:** investigate the continuous inverse and feasible representation before adding topology mechanisms.
4. **The candidate acquisition adds no useful sensitivity under the screening test:** close this particular protocol without claiming that all frequency or spatial designs are useless.
5. **Numerical checks or budgets prevent the comparison:** report the precise obstruction and close the bounded experiment as inconclusive.

No single outcome proves a unique cause. The value is that it narrows the next decision without introducing another unrelated mechanism.

## Repository evidence

All paths below were inspected or identified at the pinned source revision. Saved run metadata remain authoritative about the producing revision.

- **[E1]** [TOP-008 results](../../../../../results/validation/topology/TOP-008-20260912-feasible-fd/README.md).
- **[E2]** [TOP-009 results](../../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md).
- **[E3]** [TOP-010 results](../../../../../results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/README.md).
- **[E4]** [TOP-011 results](../../../../../results/validation/topology/TOP-011-20260912-tolerance-sensitivity/README.md).
- **[E5]** [TOP-012 results](../../../../../results/validation/topology/TOP-012-20260912-acquisition-route-a/README.md).
- **[E6]** [TOP-012 spectrum-comparison source](../../../../../results/validation/topology/TOP-012-20260912-acquisition-route-a/stage2b_redundancy.py).
- [TOP-012 full-suite completion log](../../../../../results/validation/topology/TOP-012-20260912-acquisition-route-a/execution_stage3.log).
- [Frozen benchmark and scoring definitions](../../../../benchmarks/topology_scenes.md).
