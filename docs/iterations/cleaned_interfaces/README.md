# Cleaned interfaces

**Question:** How can one cumulative SC/MA inverse retain performance across
all 36 configurations while making continuation stages clear and forward
solvers interchangeable?

Opened 2026-09-30 at the user's request. This track owns the cleanup
requirements and implementation. Existing SC/MA implementations and evidence
remain in their original locations. The subsequent user request authorized
implementation first, with the 36-scene campaign to be run by the user.

## Current handoff

| Item | State |
|---|---|
| Current cycle | [Iteration 08](iteration_08/03_plan.md): NU-001, the coefficient-space normal update, pre-registered against nodal CI-001 on the six core configurations ([proposal](iteration_08/02_proposals/01_coefficient_space_update.md), [review against the code](iteration_08/02_proposals/02_review_against_code.md), [control](../../../results/validation/cleaned_interfaces/NU-001-control/README.md)). The nodal path already drifts to r_σ 1.06–1.17, and its basis is not cos(mα)σ (control: up to 66% off). [Iteration 07](iteration_07/01_results.md): modal fixes ([bundle](../../../results/validation/cleaned_interfaces/modal-muller-fixes-20261001/README.md)). The scaled Graf factorization and the 128/160 profile remove both CI-001-modal failure classes. **7 of the 9 affected cases now pass and match nodal; the 2 contrast-13.3 C cases, which nodal does not recover either, stop earlier (`fixed_M31` against `fixed_M43`).** The other 27 have not been rerun. [Iteration 06](iteration_06/01_results.md): CI-001-modal 19/36 (nodal 28/36). [Iteration 03 / CI-001](iteration_03/01_results.md): nodal 28/36; requirement 1 not satisfied |
| User requirements | [Three requirements and the cumulative-pipeline clarification](iteration_01/02_proposals/01_user_requirements.md) |
| Plan | [CI-001 — restore clean inverse interfaces and verify retention](iteration_01/03_plan.md) |
| SPD integration | [Assessment](iteration_01/02_proposals/02_spd_integration_review.md): preserve SPD-010–015 and integrate SPD-016 grid-plus-assembly through maintained interfaces; field-table extension not selected |
| Approval status | User authorized implementation and focused validation, and ran the 36 configurations on 2026-09-30. CI-002 has not been approved |
| Execution status | SPD pairs pass (59.6% and 64.0% time saving, identical decisions); 16 damped catalogs augmented and sealed; all 36 fits and audits complete; no matched runtime pairs |
| Implementation | [`experiments/cleaned_interface`](../../../experiments/cleaned_interface/README.md); [implementation checks](iteration_02/01_results.md); [build re-verification and campaign review](../../../results/validation/cleaned_interfaces/CI-001-campaign-review/README.md) |
| Starting evidence | [Current pipeline inventory](../../pipelines/shape_frequency_continuation.md), [SC handoff](../shape_frequency_continuation/README.md), [MA handoff](../modal_atlas/README.md), [SPD handoff](../speedup/README.md) |
| Next validation | Proposed, not run: declare a CI-002 noise-aware residual gate before any rerun; test one more release after the discrepancy stop; locate the `circle_to_star` divergence from SC-043; run three matched runtime pairs |
| Following step | Proposed, not run: a fresh all-36 modal campaign from the committed fix, then a curve-adaptive trace cutoff (solved-trace tail) for the contrast-13.3 C stop, with the `candidate.py` replay as its test |
| Chebyshev proposal review | [Independent numerical and mathematical review](node_free_modal_muller_review.md): the kernel fix and all three recorded stage decisions reproduce; finite Parseval bounds and the simplicity-certificate claim fail explicit counterexamples. Review scripts and stage replays are isolated from the production backend |
| Modal Müller service | [Accuracy, replays and matched timing](../../../results/validation/cleaned_interfaces/modal-muller-service-20260930/README.md) of the maintained backend in [`experiments/cleaned_interface`](../../../experiments/cleaned_interface/README.md#modal-müller-service) |
| Modal Müller on CUDA | [Accuracy, replays and matched timing](../../../results/validation/cleaned_interfaces/modal-muller-cuda-20261001/README.md) of `device=auto/cuda` (`modal_cuda.py`) |
| Modal campaign | [CI-001-modal review](../../../results/validation/cleaned_interfaces/CI-001-modal-review/README.md): per-case comparison with nodal CI-001 and diagnoses of both failure classes |
| Modal fixes | [Scaled Graf, 128/160 profile, nine-case rerun](../../../results/validation/cleaned_interfaces/modal-muller-fixes-20261001/README.md) |
| Modal versus latest Kress | [Precision, runtime, and completeness comparison](../../../results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930/README.md): independently reconstructed Chebyshev prototype versus maintained SPD-016 CUDA Kress, with CPU controls and sequential repeated timings |

The target is one maintained cumulative implementation. Historical algorithms
supply regression evidence; they are not separate production paths selected
by scene identity. CI-001 does not establish all-36 retention (28/36).

## Cycle history

| Cycle | State |
|---|---|
| [01](iteration_01/03_plan.md) | Original requirements and proposed plan, preserved as the pre-implementation record |
| [02](iteration_02/01_results.md) | Implementation and focused checks; reconstruction/runtime retention remains unestablished |
| [03](iteration_03/01_results.md) | All-36 campaign: 28/36 pass, recovery 34/36; noise-stop residual regressions; runtime not established |
| [04](iteration_04/01_results.md) | Clean modal Müller service: certified log interval, rule-based degrees, full contract; fixture accuracy and three stage replays reproduced; no campaign |
| [05](iteration_05/01_results.md) | Modal Müller on CUDA: 1.7× (production) and 5× (refined) faster than CUDA Kress on the 19-frequency catalog; replays reproduced; field gate missed at the method floor; no inverse run |
| [06](iteration_06/01_results.md) | All-36 modal campaign: 19/36 pass (nodal 28); 27 identical to nodal at ~3× less wall time; Graf refusal (7) and production resolution (2) identified |
| [07](iteration_07/01_results.md) | Modal fixes: scaled Graf plus a finer profile; 7/9 affected cases now match nodal; the C stop needs a curve-adaptive cutoff |
| [08](iteration_08/03_plan.md) | NU-001 plan: coefficient normal update (arms A/B), exact derivative, tiered validity; control done; six-case runs pre-registered |

Follow the [shared iteration workflow](../README.md). Iteration 02 records
the implementation checks; iteration 03 records the inverse campaign.
