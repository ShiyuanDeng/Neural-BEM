# Shape and frequency continuation qualification

The [research handoff and iterations](../../../docs/iterations/shape_frequency_continuation/README.md)
interpret this evidence and record next decisions. Artifacts remain here.

The implementation is on `feature/shape-frequency-continuation`. Current
controls cover the forward physics, normal derivative, geometry, filtered-step
stopping, single-frequency recovery, warm starts, policy handoffs, cache reuse, qualification rollback and import
isolation and paper-profile/area-scoring controls. At `1a6a55a`, **171 tests pass**
across `experiments/shape_continuation`, `pytest/gpr_bem_kress` and
`pytest/ordered_boundary`; the [review](../../../docs/iterations/shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
records the validation scope.
The ellipse and extended glider pass the declared recovery gates.
[SC-014](SC-014-figure1-calibration/README.md) shows partial Figure 1 agreement
at contrast 0.33 over k in [1,5] under the raw-area hypothesis; contrast 10 is
unmatched. The driver-inspired profile differs from upstream resolution and
stopping, and the Figure 1 plotting convention is unverified. These corrected
interpretations leave all recorded measurements intact. Earlier failures remain
below; these cases do not establish general robustness.

| Qualification | Finding |
|---|---|
| [2026-09-24 outsider review](review-20260924/README.md) | SC-020/021/022 audit: counts, local dense-artifact hashes and 32 step replays confirmed; all 135 accepted steps have positive model gain. Derived and measured qualifications cover conditional harmonic steps, signed-distance error proxies, physical metrics and local-band interpretations. 12 targeted tests pass. |
| [SC-022 atlas survey](SC-022-atlas-survey/README.md) | Full atlas on three cases: 159 state records, 2,679 computed cells; 32 first-trial step replays agree to ≤1.5e-13. The tested fixed M=32 configuration fails; Borges' ladder reaches 0.005/1.43/19.4 mm on circle/star/C. Descriptive, with interpretation qualified by the 2026-09-24 review. |
| [SC-021 update band M=32](SC-021-hybrid-update-band-32/README.md) | **PASS.** SC-020 with only M raised from 16 to 32. The hybrid beats the hash-identical SPD rerun: 0.0088 against 0.048 mm, 150 against 256 work units, no rejected trials. This is development evidence on one near-truth case. |
| [SC-020 clean hybrid vs SPD](SC-020-spd-matched-hybrid/README.md) | **PASS** on the near-truth merge handoff, against a hash-identical SPD rerun. Every hybrid endpoint is qualified. Final 0.076 versus 0.048 mm, 580 versus 256 units; M=16 leaves a measured 0.050-mm high-mode error plateau. The review treats this as local evidence, not permanent spectral unreachability. See [iteration 07](../../../docs/iterations/shape_frequency_continuation/iteration_07/01_results.md). |
| [SC-019 step halving and curvature](SC-019-step-halving/README.md) | Exact ellipse-to-star control replay; halving improves recovery but is insufficient. The inherited 1% curvature gate excludes the exact star. Halving plus the 10% default reduces training error 94.7%→8.18%, but all four diagnostic arms still fail recovery. |
| [SC-018 legacy single-object comparison](SC-018-legacy-single-object/README.md) | All 30 runs complete on shared old fixtures/data. Previous Cartesian Fourier inverse passes 6/6; each new policy passes only circle-to-circle. Independent line-source bridge/derivative checks pass. See [iteration 05](../../../docs/iterations/shape_frequency_continuation/iteration_05/01_results.md) for interpretation and confounders. |
| [SC-015 atlas structure](SC-015-atlas-structure/README.md) | The detectable band is 2.5k at contrast 0.33 and 2.9k at contrast 10, against the manuscript's `3max(k,ki)`; the circle's exact rank-one selection rule is destroyed off the circle; gradients at different frequencies oppose each other, measurably and without truth. |
| [SC-016 validity horizon](SC-016-validity-horizon/README.md) | The first-order atlas predicts out to an RMS displacement of `0.12/k`, reproduced at double quadrature; the per-harmonic horizon follows the free atlas diagonal to 0.04 dex at low contrast and fails at contrast 10. |
| [SC-017 atlas controller](SC-017-atlas-controller/README.md) | Matched-budget arms against the fixed ladder: atlas-chosen frequencies match it within 3% on four starts, as the measured gradient alignment predicts; the measured band rule fails on every start because the arclength harmonic axis inflates off the circle. Contrast 10 did not complete within the declared budget. |
| [SC-002 profiling](SC-002-profile-after/README.md) | 19.66 s → 0.835 s inverse-only ellipse; identical accepted states. |
| [SC-003 derivative resolution](SC-003-resolution-refined/README.md) | Spectral arclength integration removes a derivative error floor; field/Jacobian refinement through k=8. |
| [SC-004 checked policy smoke](SC-004-policy-smoke/summary.json) | Wavelength-scaled stage policy and checkpoints pass the ellipse gates. |
| [SC-004 glider](SC-004-glider-k8/README.md) | A filtered-step stopping defect wastes the budget; stops at k=3.25. |
| [SC-005 glider](SC-005-glider-filtered-step/README.md) | Correct physical stopping advances to k=4.75 under the same cap; recovery still fails. |
| [SC-005 ellipse regression](SC-005-ellipse-regression/summary.json) | All gates pass after the repair, with the same 21 forward calls and 8 Jacobians. |
| [SC-006 filter-only comparison](SC-006-glider-paper-filter/README.md) | No added backtracking: budget ends at k=7.25, but shape and prediction errors worsen. |
| [SC-007 restart checks](SC-007-restart-smoke/README.md) | Restart preserves the problem and endpoint; field and full-Jacobian stage checks pass. |
| [SC-008 glider extension](SC-008-glider-extension/README.md) | Reaches k=12 with 522 additional forwards (2022 cumulative); held-out error 9.98e-6 and conservative relative boundary-error bound 0.001803. |
| [SC-010 step/controller refactor](SC-010-step-controller/README.md) | Fixed trajectories and trials remain bitwise/exactly identical; a 13-decision adaptive ellipse example passes all gates. |
| [SC-011 paper preparation](SC-011-paper-preparation/README.md) | Actual Figure 1 contrasts and audited settings; zero-solve full plan; two one-update smoke cases pass resolution checks in 2.85 s total. No expensive inverse run. |
| [SC-012 user-run paper glider](SC-012-paper-glider-k2/README.md) | Contrast .33 reaches k=2 in 16.42 s / 231 forwards; all resolution checks pass, but last two stages accept no updates. Final area error 15.7%; not converged recovery. |
| [SC-013 Figure 1 recovery](SC-013-paper-glider-recovery/README.md) | Four settings corrected against the authors' code. Both contrasts recover the glider: area error 0.849% at k=5 (η=.33) and 0.297% at k=3 (η=10). Supersedes the SC-012 stall. Its 2.5x–26x comparison with Figure 1 assumes the printed normalized-area interpretation. Partly superseded by SC-014. |
| [SC-014 Figure 1 profile comparison](SC-014-figure1-calibration/README.md) | Five arms; contrast 0.33 has partial agreement under the raw-area hypothesis (log10 RMS 0.117, ratio range 0.65–1.57). Contrast 10 remains unmatched. Neither the plotted normalization nor the author band rule is identified. See the linked review for remaining stopping/resolution differences. |
| [SC-009 conservative scoring](SC-009-conservative-scoring/summary.json) | Ellipse regression with the shape gate applied to the continuous-boundary error upper bound. |

Each run retains its source hashes, command, observations, states and rejected
trials. Small steps, exhausted search, iteration limits and work limits are
distinct from a data fit. The optimizer never receives truth or holdout data.

## Original SC-001 qualification

2026-09-22. Implementation authorized directly by the user's request to
replicate the paper's algorithm, or build the prerequisites for its continuation.
No branch/worktree was created. No independent review is claimed.

[Implementation and exact algorithm differences](../../../experiments/shape_continuation/README.md).

**Subsequent cleanup/profile:** [SC-002](SC-002-profile-after/README.md) reduces
inverse-only runtime from 19.66 s to 0.835 s on the saved ellipse, with bitwise
identical accepted states and 34 passing tests. The original SC-001 records
below remain unchanged.

## Evidence

- New pipeline plus existing Kress isolation and block controls: **32 tests
  passed**, including circle-series forward accuracy, normal derivative versus
  rebuilt finite differences, arclength geometry, non-star-shaped geometry,
  single-frequency recovery, warm starts, budget stopping and clean imports.
- The short ellipse pilot starts from a unit circle, with a translated/rotated
  ellipse as truth, contrast 1.44 and five single-frequency stages from k=1 to 2.
- The endpoint passes the declared 128/256 forward-refinement, unused
  frequency/acquisition, and boundary-error gates. Its inverse uses 21 forward
  evaluations and 8 Jacobians. This is a local functionality qualification,
  not a general recovery or adaptive-continuation comparison.

## Preserved runs

| Bundle | Status and interpretation |
|---|---|
| [ellipse](SC-001-20260922-ellipse/) | Inverse completed. Scoring then failed because the initial scorer imported unavailable Shapely. Inputs, states, manifest and stage history are retained. |
| [ellipse-02](SC-001-20260922-ellipse-02/) | Completed with a NumPy/SciPy scorer; all four pilot gates pass. The nearest-node boundary metric includes a parameter-sampling error floor, recorded with its sampling bound. |
| [ellipse-03](SC-001-20260922-ellipse-03/) | Final harness qualification; preserves every accepted state and uses point-to-segment boundary distances. The mathematical inverse is unchanged from the first run. Read `summary.json` for authoritative measurements. |

The first frequency stops on a small step with residual about 3.1e-4, rather
than being mislabeled converged. Later frequencies reach the data-fit tolerance.
No monotonic comparison is made between different-frequency residuals. Holdout
observations and true geometry are evaluated only after inversion.

The full paper schedule (117 frequencies), harder-shape recoveries and high-contrast
qualification have not been run. The non-star-shaped test
establishes geometry support, not inverse recovery of a non-star-shaped target.
SC-015 to SC-017 add a measured characterization of the frequency/shape
interaction and one matched-budget controller comparison built on it; they do
not extend the recovery qualification above.
