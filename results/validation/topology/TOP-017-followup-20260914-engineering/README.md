# Engineering follow-up: fresh central recovery and two-star resolution

Completed 2026-09-14 under the user's instruction to implement the three
engineering actions. [Scope and bounded implementation](../../../../docs/iterations/topology/iteration_11/02_engineering_followup.md).
No literature search, successor campaign, new branch or higher-bandwidth merge inverse.

**A fresh central circle → ellipse + star run passes all final reconstruction
and numerical gates.** The existing automatic H controller chose its own
split/birth/merge events, then the new handoff zero-padded its result to K9 and
ran all four cumulative-frequency stages. No archived optimized state, supplied
target count, truth-guided update or best-stage selection entered the run.

[Watch the fresh 37-second run](fresh_circle_to_ellipse_star.mp4) ·
[Final figure](fresh_final.svg) · [Full fresh-run record](central-validated/result.json) ·
[Validation](validation.json)

## Fresh central-circle result

| Checkpoint | Boundary error (mm) | IoU | Worst development-evaluation error | Reconstruction gates pass |
|---|---:|---:|---:|---|
| Automatic topology endpoint | 9.222573 | 0.777493 | 0.89216474 | No |
| Continuation stage 1 | 8.815388 | 0.909688 | 0.52139664 | No |
| Continuation stage 2 | 0.745146 | 0.992011 | 0.041895225 | Yes |
| Continuation stage 3 | 0.046442 | 0.999713 | 0.00096421647 | Yes |
| Continuation stage 4 | 0.062334 | 0.999426 | 0.0012377189 | Yes |

Every scored endpoint was numerically qualified at 128/256 nodes. Stage 4 is the
predetermined final endpoint, even though stage 3 has slightly better shape and
evaluation scores. Stages 1/2 ended at planned quotas, stage 3 at no decreasing
step, and stage 4 at the configured gradient tolerance. Completion of the whole
schedule does not assert stationarity at every earlier stage.

The final star boundary error is 0.001286 mm and ellipse error is 0.062334 mm.
The final coefficients and scores reproduce the archived TOP-017 central F
endpoint, now reached through a fresh automatic circle-start computation.
This closes the previously missing end-to-end check for this one scene and
specified protocol. It does not qualify all twelve scenes or promote the
expanded acquisition/budget as a general controller default.

## Two-star resolution diagnosis

Three states were checked: F's retained endpoint, the exact rejected F candidate
(reconstructed with its archived hash), and S's stage-3 endpoint. All six existing
frequencies were evaluated at 128, 256 and 512 nodes. No inverse was rerun.

The table shows the maximum discrepancy across the added training frequencies
0.75–1.25 GHz, whose unchanged tolerance is 1e-7:

| Saved state | 128/256 discrepancy | 256/512 discrepancy |
|---|---:|---:|
| F_rejected | 4.145718e-07 | 1.298853e-11 |
| F_retained | 1.850996e-07 | 1.662187e-12 |
| S_endpoint | 1.06641e-07 | 1.189059e-12 |

All three states pass every applicable tolerance at 256/512. Across all six
frequencies, the largest 256/512 discrepancy is 2.91967e-11. The rejected F step
also satisfies the original loss-acceptance formula at 256/512, with production
and refined gains both approximately 1.6898174e-6. This identifies inadequate
128-node resolution as the immediate obstruction for those exact saved states.

256/512 is now qualified for examining those states; it is not a guarantee that
later optimized candidates will qualify or that the two-star inverse recovers.
No two-star continuation, tolerance relaxation or global node-default change was
made. [Complete predictions, coefficients and comparisons](resolution/result.json).

## Implementation and validation

- Numerical candidate failures now save full base/candidate coefficients,
  production/refined predictions, losses, thresholds, geometry/solve settings,
  accepted-state identity and work, without additional solves.
- The schedule accepts an explicit four-stage plan; its existing stages-2–4
  default and all numerical defaults remain unchanged.
- The new driver joins the existing topology controller and continuation APIs.
  Tests verify exact rejected-step reconstruction, failure-state separation,
  frequency progression, count-independent handoff, budget guards and provenance.
- **67 focused tests pass.** The owner reviewed the implementation and artifact
  associations; no independent-agent review is claimed for this follow-up.

The first fresh-run attempt exposed an instrumentation defect: a normal rejected
close-component candidate was wrapped as a fatal physical error. Its 80 calls /
4.104 seconds remain saved under [central/](central/result.json). The corrected
counter preserves the controller's expected geometry exceptions. The repeat
[central-validated/](central-validated/result.json) deducts that attempt from the
original budget, with a regression test for the actual exception class.

The corrected topology phase charged 2,656 API attempts, including 38 routine
geometry refusals, and completed 2,618 BIE frequency solves (including 8 TD
systems). Continuation completed 4,810 frequency solves with no failures. Its
endpoint-inclusive stage counts are 948/1,146/1,572/1,132, plus 12 initial-score
solves. All original ceilings passed, including the first failed attempt.

Including the 54-solve resolution audit and the preserved first attempt: **7,600
charged frequency-call attempts, 7,561 completed BIE frequency solves, 39
geometry-refused calls**. The first refused call caused the instrumentation
abort; the other 38 were handled normally. Total active numerical wall time was
936.879 seconds, one worker, single-thread BLAS. Refused API calls are not
completed BIE solves; their original ledger fields are retained and classified
explicitly here.

Historical TOP-008/016/017 artifacts remain unchanged. Each numerical phase
records its measured source revision and hashes. The video samples only saved
states from the fresh validation, with no coefficient interpolation or new
numerical solves. [Commands](commands.md), [tests](focused_tests.log),
[artifact verifier](verify_followup.py), [video provenance](video_manifest.json).

## Remaining decision

Whether to scope a two-star continuation at the now-checked 256/512 resolution.
That work, a merge inverse, a suite and any successor remain unexecuted.
Validated implementation and results are committed locally; no push is requested.
