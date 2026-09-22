# SC-001 — isolated nodal continuation qualification

2026-09-22. Implementation authorized directly by the user's request to
replicate the paper's algorithm, or build the prerequisites for its continuation.
No branch/worktree was created. No independent review is claimed.

[Implementation and exact algorithm differences](../../../experiments/shape_continuation/README.md).

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
