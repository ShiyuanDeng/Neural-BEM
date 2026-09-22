# Shape and frequency continuation qualification

The [research handoff and iterations](../../../docs/iterations/shape_frequency_continuation/README.md)
interpret this evidence and record next decisions. Artifacts remain here.

The implementation is on `feature/shape-frequency-continuation`. Current
controls cover the forward physics, normal derivative, geometry, filtered-step
stopping, single-frequency recovery, warm starts, policy handoffs, cache reuse, qualification rollback and import
isolation and paper-profile/area-scoring controls: **72 tests pass** with the existing Kress isolation/block tests.
The ellipse and extended glider pass the declared recovery gates, and
[SC-013](SC-013-paper-glider-recovery/README.md) recovers the paper's §4.1
glider at both Figure 1 contrasts. Earlier failures remain below; these cases
do not establish general robustness.

| Qualification | Finding |
|---|---|
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
| [SC-013 Figure 1 recovery](SC-013-paper-glider-recovery/README.md) | Four settings corrected against the authors' code. Both contrasts recover the glider: area error 0.849% at k=5 (η=.33) and 0.297% at k=3 (η=10). Supersedes the SC-012 stall. |
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

The full paper schedule (117 frequencies), harder-shape recoveries, high-contrast
qualification and comparative adaptive-policy campaigns have not been run. The non-star-shaped test
establishes geometry support, not inverse recovery of a non-star-shaped target.
