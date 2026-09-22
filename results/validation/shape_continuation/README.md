# Shape and frequency continuation qualification

The implementation is on `feature/shape-frequency-continuation`. Current
controls cover the forward physics, normal derivative, geometry, filtered-step
stopping, single-frequency recovery, warm starts, policy handoffs and import
isolation: **41 tests pass** with the existing Kress isolation/block tests.
The ellipse passes recovery gates; the bounded glider tests below include
failures and must not be read as evidence of general robustness.

| Qualification | Finding |
|---|---|
| [SC-002 profiling](SC-002-profile-after/README.md) | 19.66 s → 0.835 s inverse-only ellipse; identical accepted states. |
| [SC-003 derivative resolution](SC-003-resolution-refined/README.md) | Spectral arclength integration removes a derivative error floor; field/Jacobian refinement through k=8. |
| [SC-004 checked policy smoke](SC-004-policy-smoke/summary.json) | Wavelength-scaled stage policy and checkpoints pass the ellipse gates. |
| [SC-004 glider](SC-004-glider-k8/README.md) | A filtered-step stopping defect wastes the budget; stops at k=3.25. |
| [SC-005 glider](SC-005-glider-filtered-step/README.md) | Correct physical stopping advances to k=4.75 under the same cap; recovery still fails. |
| [SC-005 ellipse regression](SC-005-ellipse-regression/summary.json) | All gates pass after the repair, with the same 21 forward calls and 8 Jacobians. |
| [SC-006 filter-only comparison](SC-006-glider-paper-filter/README.md) | No added backtracking: budget ends at k=7.25, but shape and prediction errors worsen. |

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

The full paper schedule (117 frequencies), hard-shape recoveries, high-contrast
qualification and adaptive policies have not been run. The non-star-shaped test
establishes geometry support, not inverse recovery of a non-star-shaped target.
