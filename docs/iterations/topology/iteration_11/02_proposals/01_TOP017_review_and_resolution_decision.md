# TOP-017 review — keep the recovery, isolate the numerical obstruction

Prepared 2026-09-15. Read-only review of committed documents, source and selected
terminal artifacts at `243fe19a7937dd519c4a55bc3e04d464ee04d2a4` on
`feature/ordered-boundary-nystrom`. No independent physical forward or inverse
was rerun for this review. TOP-017's measured numerical source was `e3e581f`;
the latest consolidated commit is the documentation/integration reference.

This review proposes TOP-018. Its [contract](../03_plan.md) remains unapproved
until the user explicitly authorizes it. Existing implementation principles and
the staged-execution amendment remain in force; no new approval layer is added.

## 1. Verdict

**There is now a real fixed-topology recovery result.** On central-ellipse-star,
the cumulative-frequency arm passes all original gates, from the same saved
start at which the paired single-frequency arm remains inaccurate. This is the
kind of reconstruction progress the recovery reset was meant to find. Do not
summarize it as another iteration that only reduced training loss.

**The two-star comparison is unfinished because of numerical qualification.**
Do not classify it as a failure of frequency diversity, a topology failure, or
proof that a different optimizer is required. The remaining question is whether
a modest, qualified discretization change permits that particular comparison
to finish.

**No production or twelve-scene promotion yet.** Central success is evidence
for one fixed-count, development-case protocol. The two-star schedule did not
finish, and the earlier merge inverse regression is unresolved.

## 2. Evidence that changes the research decision

| Endpoint or measurement | Committed result | Interpretation |
|---|---|---|
| Central common start | 8.81539 mm boundary; 0.521397 worst evaluation error | Same physical start for S and F |
| Central final S | 6.12516 mm; 0.93029 IoU; 0.321496 worst evaluation error; 4,772 new frequency solves | Improvement, but not recovery |
| Central final F | 0.0623345 mm; 0.999426 IoU; 0.00123772 worst evaluation error; 3,850 new frequency solves | Passes the original gates under this fixed-count protocol |
| Central F stage 2 | 0.745146 mm; 0.0418952 worst evaluation error | Useful geometry already appears when 0.75 GHz is added; do not select this stage as the final output |
| Two-star F stage 2 | Five accepted updates, then a candidate's 0.75-GHz discrepancy is 1.361419901e-7 against 1e-7 | Numerical guard stopped the trial; candidate was not accepted |
| Two-star S stage 3 | Endpoint's 1.25-GHz discrepancy is 1.066409614e-7 against 1e-7 | The all-frequency endpoint audit failed; 1.25 GHz was not fitted by S |

Sources: [result bundle][R1], [independent closeout][R2], and
[iteration-11 result record][R3]. Central F's final terminal record also retains
all four training frequencies, a completed current Jacobian and the configured
gradient stop. The independent reviewer checked source/input hashes and state,
objective and score associations; that recorded review is not an independent
numerical reproduction.

The central F stage-3 endpoint is slightly better than stage 4 on some scores.
Stage 4 stays the final result. No new best-stage selection is licensed.
Frequency-solve counts compare new work at the same resolution; they are not a
controlled runtime benchmark or total end-to-end reconstruction costs.

### What central success supports

The current explicit Fourier/gauge, fixed-count FD/LM, and Müller/Kress machinery
can recover this noncircular pair under the tested cumulative-frequency
protocol. The same start, representation and optimizer at 0.5 GHz alone did not
do so within its matched contract. That supports retaining this machinery and
testing the remaining obstruction before considering architectural replacement.

It does not prove that single-frequency data are globally non-identifying, that
all initializations recover, or that the acquisition alone rather than its
combination with continuation caused every improvement. S's final stage stopped
on its iteration ceiling, not a convergence theorem.

The animation stitches archived topology history, TOP-016 and TOP-017 at labeled
run boundaries. It is useful visualization, not a fresh integrated automatic
circle-to-two-object inversion. Preserve that distinction in figures and talks.

## 3. Why a resolution check is the next justified intervention

The discrepant predictions exceeded the frozen threshold by factors of about
1.36 and 1.07. Neither reported event is a failed matrix solve. The evidence is
that the two selected discretizations no longer agreed sufficiently under the
contract, not that the physical model or optimizer was proved wrong.

A convergence comparison of the *same coefficients* at 128, 256 and 512 nodes is
a direct test of this obstruction. Increasing quadrature nodes is distinct from
increasing Fourier bandwidth: the former refines the forward discretization,
whereas the latter changes the unknown shape space. TOP-018 fixes K=9.

The proposed audit targets the common start, F's last retained state, S's stopped
endpoint, and F's rejected candidate when its coefficients can be reconstructed
exactly from saved steps. It preserves the distinction between a failed candidate
and a failed accepted endpoint. A diagnostic prediction at a rejected state does
not authorize accepting or restarting from that state.

A positive finite-resolution audit supports using the finer pair in the next
bounded experiment. It is not a global error bound for every future geometry.
Runtime qualification remains necessary. If 256/512 does not qualify, this ID
stops; it is not the beginning of an automatic node-doubling campaign.

## 4. Merge: a representation warning, not an exoneration

TOP-017's evaluation-only merge projections gave:

| Fixed projection | Benchmark boundary error | Worst evaluation error |
|---|---:|---:|
| K=9 | 0.715424 mm | 0.0898651 |
| K=17 | 0.0171234 mm | 0.00234457 |

Both passed their numerical checks. These are sampled projection errors, not
best-approximation lower bounds. The dense-distance sampling variation is
reported separately in [R1]. The K=17 projection demonstrates that a feasible
higher-bandwidth representation can describe this truth much more closely under
that procedure; it does not show an inverse will find it.

Consequently, the merge control was not a clean, already-qualified test of all
geometric and prediction gates within the K=9 constrained chart. This qualifies
our interpretation of its regression; it does not erase the measured adverse
F-merge outcome in TOP-016. Do not change K for the principal tests, add a merge
inverse here, or remove merge from eventual qualification.

## 5. Literature backing and limits

**[L1] Borges, Rachh and Greengard, “On the robustness of inverse scattering for
penetrable, homogeneous objects with complicated boundary,” Inverse Problems
39 (2023), 035004; arXiv:2210.11607.** This is a close acoustic transmission
precedent for boundary-only inversion and frequency continuation. Its numerical
method uses a high-order integral-equation forward discretization and controls
boundary complexity separately from forward sampling. It also reports
robustness limits and no guarantee of global convergence. Our TMz paired-source
acquisition, constrained chart and cumulative multi-frequency objective are not
an exact reproduction. The current central result supplies project-specific
evidence; the paper supplies motivation, not our gates or expected success rate.

**[L2] Borges and Greengard, “Inverse Obstacle scattering in two dimensions with
multiple frequency data and multiple angles of incidence,” arXiv:1408.5436.**
The sound-soft study combines band-limited boundary updates, Newton-type
iteration and recursive linearization, using accurate integral-equation forwards.
It supports keeping shape-space regularization, data continuation and forward
accuracy conceptually separate. It does not justify substituting a truth-fitted
curve for an inverse result or relaxing a numerical threshold after a failure.

**[L3] Wu and Martinsson, “Zeta Correction: A New Approach to Constructing
Corrected Trapezoidal Quadrature Rules for Singular Integral Operators,”
arXiv:2007.13898.** Their quadrature study treats high-order discretization of
boundary integral equations on smooth planar contours and compares with Kress
quadrature. It reinforces that quadrature accuracy is a numerical issue to
measure. It is not evidence that this repository needs their replacement rule.
Our choice to test the existing solver at a finer grid is an experimental
recommendation, not a theorem imported from that paper.

[L1]: https://arxiv.org/html/2210.11607v1
[L2]: https://arxiv.org/abs/1408.5436
[L3]: https://arxiv.org/abs/2007.13898

## 6. Decisions on possible next steps

| Recommendation | Decision |
|---|---|
| Preserve central recovery as the leading positive result | Accept; report its fixed-count and development-case scope |
| Perform one saved-state resolution audit | Resolve through TOP-018 Phase A, at most 256 solves |
| If qualified, run the two-star pair at 256/512 | Accept conditionally within the same TOP-018 approval |
| Resume S and F from their different stopped states | Reject for the matched primary comparison; those are audit inputs only |
| Use the same saved common start for both higher-resolution arms | Accept; no replay of TOP-016's common 0.5-GHz optimization |
| Rerun the central pair, sensitivity screen or oracle generation | Reject as unnecessary for this question |
| Loosen 1e-7, accept the failed candidate, or continue after numerical failure | Reject |
| Introduce adaptive quadrature, QBX, a weak BIE, adjoints, a new optimizer, or new topology events | Defer; the present evidence does not isolate them as necessary |
| Change merge K or launch a merge inverse | Defer to a separate capacity-qualified control decision |
| Qualify the complete controller or claim global identifiability | Not established; no suite or automatic promotion under TOP-018 |

## 7. Reusable implementation lessons

- A campaign status cannot erase a valid scene-level result. Report qualified
  successes, unqualified scores, and absent scores separately.
- A failed trial candidate is not a failed retained state. Persist both hashes
  and the exact discrepancy; never silently replace a checkpoint.
- Discretization changes need new objective/derivative evaluations and cache
  identities. A gradient at 128 nodes is not a gradient at 256 nodes.
- Reuse history without falsifying equivalence. A pair restarted from a common
  checkpoint at a different resolution is a new controlled experiment, not an
  exact continuation; unequal stopped endpoints do not make matched starts.
- Keep research controls specific. Node count, representation bandwidth and
  frequency range are three different interventions.
- Add only what answers the next decision. Phase A and its gated continuation
  share one approval; neither becomes an open-ended new research track.

## 8. After TOP-018

Close out even if the finer numerical gate fails. If it passes and the two-star
pair finishes, decide from geometry and unfitted prediction rather than training
loss alone. Then make one explicit choice between addressing the remaining
numerical/fixed-topology limitation or a scoped integration/merge-capacity test.
Do not let one difficult scene automatically authorize indefinite solver work,
and do not treat central success as already qualifying the automatic controller.

[R1]: ../../../../../results/validation/topology/TOP-017-20260914-staged-continuation/README.md
[R2]: ../../../../../results/validation/topology/TOP-017-20260914-staged-continuation/closeout_review.md
[R3]: ../01_results.md
