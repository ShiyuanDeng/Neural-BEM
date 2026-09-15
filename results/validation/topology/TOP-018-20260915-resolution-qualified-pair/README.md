# TOP-018: resolution qualification and matched two-star pair

**F_RECOVERED_RELATIVE_TO_MATCHED_S.** Consider one separately scoped merge-capacity qualification before a broader integration comparison.

Approved 2026-09-15 by the user's “yesh” response to the named TOP-018 approval
request. Owner/reviewer: Codex `/root` (owner review; no independent-agent review).
The existing checkout and branch were used. No production promotion or successor
is authorized. The fresh central recovery and TOP-016 merge regression remain
separate, preserved evidence.

## Audit and release

Phase A: **PHASE_A_PASS**, 86 new attempted
frequency solves. The earlier 54-solve audit supplies verified predictions for
three historical states; it does not supply new inverse results. COMMON is the
same saved K=9 endpoint for both arms. [Resolution table](resolution_table.md),
[full audit](phase_a/audit.json), [reuse provenance](reuse.json).

## Endpoint scorecard

| Endpoint | Boundary mm | IoU | 0.5 GHz | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Gates | Qualified | Stop | New solves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|
| COMMON | 12.03275 | 0.714194 | 6.425897e-05 | 0.01457302 | 0.102388 | 0.3409127 | 0.5532678 | 1.413749 | False | True | reused/start | 0 |
| S stage 2 | 11.99703 | 0.7183871 | 5.806625e-05 | 0.01430803 | 0.1003861 | 0.3320495 | 0.5340378 | 1.392819 | False | True | STAGE_QUOTA_REACHED | 1249 |
| S stage 3 | 11.89599 | 0.7252747 | 5.354136e-05 | 0.01367564 | 0.09565672 | 0.3153828 | 0.5056774 | 1.352495 | False | True | STAGE_QUOTA_REACHED | 1743 |
| S stage 4 | 11.79317 | 0.7382812 | 4.860749e-05 | 0.01284125 | 0.08965067 | 0.2958482 | 0.4746695 | 1.306218 | False | True | maximum_iterations | 1803 |
| F stage 2 | 8.919867 | 0.7999326 | 0.003042578 | 0.007574629 | 0.02694313 | 0.09409227 | 0.1826985 | 0.8155913 | False | True | STAGE_QUOTA_REACHED | 1176 |
| F stage 3 | 0.002397422 | 1 | 1.499855e-06 | 3.181522e-06 | 5.884674e-06 | 1.078334e-05 | 1.895445e-05 | 4.747837e-05 | True | True | STAGE_QUOTA_REACHED | 1707 |
| F stage 4 | 0.001676437 | 1 | 1.114879e-08 | 1.723928e-08 | 3.483598e-08 | 7.069936e-08 | 5.304007e-07 | 3.323707e-06 | True | True | loss_tolerance | 572 |
| TOP-017 central F (reused) | 0.06233449 | 0.9994264 | 6.729321e-07 | 1.331013e-06 | 2.1003e-06 | 3.250992e-06 | 2.547995e-05 | 0.001237719 | True | True | reused/start | 0 |

The final endpoint is prescribed stage 4. Earlier stages are never selected as
the final answer. Both two-star arms use 256/512; the separate central row reuses
TOP-017 at 128/256 and has no new solves. The fixed count was supplied by COMMON.
S fits only 0.5 GHz; its other frequency scores are endpoint audits. F fits the
prescribed cumulative frequencies. Errors at 1.5/2.5 GHz are development
evaluation scores. Geometry gates are boundary <=1 mm and IoU >=0.90; prediction
gates are original-training error <=0.003 and worst evaluation error <=0.05.

Aggregate objectives change with the active set. The [JSON scorecard](scorecard.json)
keeps production/refined objectives, exposure, convergence, actual stops,
acceptances, gradients and state associations separate. Reporting-only scores
cannot release a stopped stage.

## Work, provenance and verification

New calls: **8336 attempted, 8336 completed,
0 failed**. Historical reused calls: 54, excluded from new
work. Summed active numerical wall time: 4190.657 s;
campaign elapsed: 2565.869 s. At most two workers,
single-thread BLAS. This is not a runtime comparison with TOP-017.

[Work ledger](work_ledger.json) · [frozen contract](contract.json) ·
[source/input manifest](manifest.json) · [approved plan](approved_plan.md) ·
[implementation review](implementation_review.md) · [tests](pre_dispatch_tests.log) ·
[environment and exact command](environment.json) · [worker commands](campaign.json).

Rebuild without physical solves:

```bash
python experiments/top018/summarize.py --bundle results/validation/topology/TOP-018-20260915-resolution-qualified-pair
```

## Preserved reporting failure and repair

Both numerical schedules completed before their workers exited with a
post-schedule annotation error: Python list/tuple equality rejected identical
frequency values. The [diagnosis](reporting_failure_diagnosis.md), original
`metrics_before_reporting_repair.json` files and worker tracebacks are retained.
The source/input hashes were verified unchanged through numerical completion
before the reporting code was corrected. Measured numerical source remains
`9bde9d1`; later reporting changes are identified separately.

[Reconciliation record](reporting_repair.json) verifies that every original
scientific field is unchanged. Only missing objective associations and integrity
metadata were rebuilt. No physical solve, derivative, inverse or restart was
performed by the repair. Worker exit failures remain visible in the scorecard.

## Saved geometry

[Common start and prescribed terminal states](endpoints.svg).
The figure uses only saved coefficients; [state/source associations](figure_manifest.json).

## Final closeout

[Owner review](closeout_review.md) · [Verification](closeout_verification.json) · [Commands](commands.md) · [89 final tests](final_tests.log).
