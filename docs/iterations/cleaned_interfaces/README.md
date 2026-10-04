# Cleaned interfaces

**Question:** How can one cumulative SC/MA inverse retain performance across
all 36 configurations while making continuation stages clear and forward
solvers interchangeable?

Opened 2026-09-30 at the user's request. This track owns the cleanup
requirements and implementation. Existing SC/MA implementations and evidence
remain in their original locations. The subsequent user request authorized
implementation first, with the 36-scene campaign to be run by the user.

## Current handoff

**NU-007a GPU certificates (2026-10-03):** qualified and integrated for explicit
`certified_spectral` selection on CUDA. All 864 offline comparisons and 18
full-path pairs pass; archived NU-006 paths and final curves are unchanged.
Six-case median totals fall from 247.2 s to 149.6 s, with certificate work
reduced from 103.5 s to 7.5 s. CPU selection and the spline/nodal defaults
remain unchanged. The original NU-007 failure is preserved. See the
[qualification report](../../../results/validation/cleaned_interfaces/NU-007a-20261003/README.md).

**Relaxed BIE now has its own [research track](../relaxed_bie/README.md)**
(2026-10-03, user-directed organization). FM-001/FM-002 originals remain in
iterations 18/19 and their sealed result bundles. The new track owns the
updated interpretation and [RB-001 plan](../relaxed_bie/iteration_01/03_plan.md):
test resolution recovery for the four stopped real-prefix trajectories.
Broader closure remains premature because their rejected candidates still
decreased loss at both resolutions. RB-001 is complete; its
[new results](../relaxed_bie/iteration_02/01_results.md) record four removable
stops and four qualified finer endpoints, but no new recoveries within the
retained budgets. The ordinary
damped default and the recorded node-free campaign coverage are unchanged.

**NF-001 outsider audit (2026-10-02–03):** the maintained claim is now
boundary-collocation-free modal physics with optional spline-free quadrature
geometry, not an end-to-end sample-free inverse. Explicit geometry selection
is integrated into the public runner and CLI, certificate arithmetic assumptions
are recorded, and a locally qualified analytic quadrature tangent is available
as an experimental option. See [iteration 17](iteration_17/01_results.md), the
[advance plan](iteration_16/03_plan.md) and the
[evidence bundle](../../../results/validation/cleaned_interfaces/NF-001-outsider-review/README.md).
The user authorized these code fixes and experiments without further approval.
Certified spectral geometry is selectable as `--geometry-update certified_spectral`;
the legacy public default is still spline. CUDA certificate evaluation now
uses the qualified NU-007 path described above.

| Item | State |
|---|---|
| GPU certificate completion | [NU-007a](../../../results/validation/cleaned_interfaces/NU-007a-20261003/README.md): integrated on CUDA after threshold-scaled qualification; 39.5% less wall time on six core cases |
| Relaxed-BIE research | [Standalone track](../relaxed_bie/README.md): RB-001 complete; all four immediate obstructions are removable, but continued full/paired recovery is 0/4. [Original iteration 19](iteration_19/01_results.md) is preserved |
| Node-free cycle | [Iteration 17](iteration_17/01_results.md): NF-001 outsider review and integrated claim/interface fixes; analytic quadrature tangent retained as opt-in after bounded experiments |
| Previous cycle | [Iteration 15](iteration_15/01_results.md): NU-007 (user: "go"), GPU certificates, **stopped at stage 1**. Decisions and tiers matched in all 864 pre-check trials, and certificate time fell 10× (1,520 s → 151 s). The pre-registered relative-bound gate failed (1.5·10⁻⁵). The diagnostic shows these gaps only at bounds ≤ 10⁻⁴ (round-off floor), with no bound within 6.4·10⁻³ of the decision threshold. The campaign was not run. Proposed, not run: NU-007a with a threshold-scaled gate. [Iteration 14](iteration_14/01_results.md): NU-006 (user: "yes go") **retained and adopted as the default `prepare`**. The NU-005 update with all its `prepare` projections batched on the RTX 5090 is decision-identical to NU-005 on the six core cases (same steps and units, final curves within 2.1·10⁻¹⁰ σ₀). Geometry preparation falls from 150 s to 3.9 s, and wall time from 390 s to 242 s (nodal: 573 s). The NU-005 certificates are now 43% of wall time (104 s). Proposed, not run: certificate reuse from modal physics, batched LU and Graf waves on the GPU, all-36. [Iteration 13](iteration_13/01_results.md): NU-005 (user: "keep up to NU005") **retained, no sampled fallback**. Certificate tiers (exact area, then a Lemma 3–4 increment, then the full |W|² certificate) in front of the sampled validity test decided all 1,131 validity checks on the six core cases. The decisions and final curves are bit-identical to NU-004-MS, and the pre-check gates held (864 trials, no shadow disagreement). Certificates add 103 s (390 s against MS's 293 s). Not established: refusal without samples (no trial was refused). Proposed, not run: NU-006 (NUFFT quadrature), certificate reuse from modal physics, Krawczyk refusal, all-36. [Iteration 12](iteration_12/01_results.md): NU-004 (user: "yes go") **retained**. Modal Müller physics with the NU-003 spline-free map matches nodal on 6/6 core cases with no drift flag. It is decision-identical to nodal and to a modal + spline control (same steps, same 9,677 units, final curves within 6·10⁻⁸ σ₀), at 293 s against nodal's 573 s. The quadrature is now 52% of wall time. Still sampled: the self-intersection test. Proposed, not run: NU-005 (validity without samples), NU-006 (NUFFT quadrature), then all-36. [Iteration 11](iteration_11/01_results.md): NU-003 (user: "go") **qualifies**. The CI-001 trial map with its spline resampler replaced by the eq. 9 quadrature matches nodal on 6/6 core cases with no drift flag, and is decision-identical (same accepted steps in all 72 stages, same 9,677 units, final curves within 6·10⁻⁸ σ₀). Geometry preparation is 2.2× slower (total wall time +15%). Still node-based: `nodal_kress` physics and the sampled validity test. Proposed, not run: NU-004 (NU-003 + modal Müller). [Iteration 10](iteration_10/01_results.md): NU-002 offline pre-check (user: "go"). The eq. 9 spectral arclength reset keeps the shape within 10⁻⁵ σ₀ at K = 192 up to r_σ ≈ 3.4, but at the damped bands K = 8–20 it moves the shape by 10⁻⁴–3·10⁻² σ₀ on every drifted state, nodal included (3/64 pass, all peanut). The planned arm B + reset run was not started. Proposed, not run: NU-003, the nodal increment map with its spline resampler replaced by eq. 9. [Iteration 09](iteration_09/01_results.md): NU-001 completed all 12 CUDA runs on six core configurations. Arm A matches 2/6 and arm B 3/6; both trigger drift flags, so the pre-registered decision keeps the nodal trial map. The [iteration 08 plan](iteration_08/03_plan.md) and [validation evidence](../../../results/validation/cleaned_interfaces/NU-001-VALIDATION.md) record the design and execution. [Iteration 07](iteration_07/01_results.md): modal fixes yield 7/9 matching reruns; the other 27 have not been rerun. [Iteration 06](iteration_06/01_results.md): CI-001-modal 19/36 (nodal 28/36). [Iteration 03 / CI-001](iteration_03/01_results.md): nodal 28/36; requirement 1 not satisfied |
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
| [09](iteration_09/01_results.md) | NU-001 six-case CUDA results: neither arm qualifies under the fixed match and drift rules; retain nodal |
| [10](iteration_10/01_results.md) | NU-002 arclength-reset replay: exact at K = 192 for r_σ ≤ 3.4; at K = 8–20 a reset changes the shape, so it cannot repair drift where drift starts; NU-003 proposed |
| [11](iteration_11/01_results.md) | NU-003 spectral increment map: pre-check passes; six-case CUDA run matches 6/6 and is decision-identical to nodal; adopt; 15% slower |
| [12](iteration_12/01_results.md) | NU-004 modal Müller + spline-free map: 6/6, decision-identical to nodal and modal + spline, 2.0× faster than nodal; quadrature dominates geometry |
| [19](iteration_19/01_results.md) | FM-002: corrected relaxed gradient and fixed four-arm, three-case study; damping 3/3 with or without relaxation, real prefix 1/3 with or without; 477 tests pass |
| [20](iteration_20/03_plan.md) / [21](iteration_21/01_results.md) | FM-003: 512-start paired stage-2 census; the lowest-loss endpoint continues to recover the contrast-13.3 C (search failure supported); no zero-loss endpoint |
| [22](iteration_22/03_plan.md) / [23](iteration_23/01_results.md) | FM-004 (user: "go"): all 11 below-gap census endpoints continued; 4/11 recover, the contrast-4 control fails; every failure is the CI-001 numerical-resolution hard stop. Proposed, not run: FM-005 with RB-001's resolution response |

Follow the [shared iteration workflow](../README.md). Iteration 02 records
the implementation checks; iteration 03 records the inverse campaign.
