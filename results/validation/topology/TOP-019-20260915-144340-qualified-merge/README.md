# TOP-019: capacity-qualified merge-control comparison

**BOTH_ARMS_RECOVERED.** Compare precision and work before selecting a policy for fresh integration.

Approved 2026-09-15 by the user's “go” response to the named audit/conditional-pair
request. Codex `/root` owns implementation and review; no independent review is
claimed. Existing checkout and branch, one numerical worker, single-thread BLAS.

## Binding audit

Phase A: **PHASE_A_PASS**, 104 attempted solves.
Failed requirements: [].
All numerical thresholds are unchanged. The fixed truth projection is
evaluation-only; both inverses use the zero-padded original controller endpoint.
[Audit and numerical checks](phase_a/audit.json) · [Input provenance](reuse.json).

## Prescribed endpoints

| Endpoint | Boundary mm | IoU | 0.5 GHz | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Gates | Qualified | Stop | Solves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|
| COMMON | 0.5541558 | 0.9934354 | 7.878761e-05 | 0.001115283 | 0.01128871 | 0.04103175 | 0.04708466 | 0.09398022 | False | True | start | 0 |
| S stage 1 | 0.09438918 | 0.9998001 | 1.085219e-06 | 2.677378e-06 | 4.223116e-05 | 0.000536142 | 0.001867381 | 0.01214149 | True | True | STAGE_QUOTA_REACHED | 978 |
| S stage 2 | 0.08600671 | 0.9998001 | 9.162548e-07 | 2.504421e-06 | 4.591855e-05 | 0.000581454 | 0.001925301 | 0.0116406 | True | True | gradient_tolerance | 148 |
| S stage 3 | 0.08600671 | 0.9998001 | 9.162548e-07 | 2.504421e-06 | 4.591855e-05 | 0.000581454 | 0.001925301 | 0.0116406 | True | True | gradient_tolerance | 79 |
| S stage 4 | 0.08600671 | 0.9998001 | 9.162548e-07 | 2.504421e-06 | 4.591855e-05 | 0.000581454 | 0.001925301 | 0.0116406 | True | True | gradient_tolerance | 79 |
| F stage 1 | 0.09438918 | 0.9998001 | 1.085219e-06 | 2.677378e-06 | 4.223116e-05 | 0.000536142 | 0.001867381 | 0.01214149 | True | True | STAGE_QUOTA_REACHED | 978 |
| F stage 2 | 0.04359743 | 0.9998001 | 2.41972e-07 | 5.476958e-07 | 1.22827e-05 | 0.000216769 | 0.0008421547 | 0.005210789 | True | True | STAGE_QUOTA_REACHED | 1116 |
| F stage 3 | 0.02260894 | 0.9990014 | 8.641875e-08 | 1.696517e-07 | 2.476083e-07 | 1.05464e-05 | 9.64501e-05 | 0.002475152 | True | True | STAGE_QUOTA_REACHED | 1650 |
| F stage 4 | 0.02142826 | 0.9994006 | 1.772564e-07 | 4.738943e-07 | 1.232189e-06 | 1.691149e-06 | 5.527504e-05 | 0.002293578 | True | True | gradient_tolerance | 1100 |

Unrun or unavailable arms: [].
The final endpoint is stage 4; stopped states are explicitly retained states.
The supplied count is not newly recovered. S fits only 0.5 GHz; F fits cumulative
0.5/0.75/1.0/1.25 GHz. The 1.5/2.5-GHz scores are development evaluation.
Both arms use K=17 and 256/512; quota stops do not establish convergence.
See the [full scorecard](scorecard.json) for objective/gradient associations,
stopping, effective exposure and missing scores.

## Work and provenance

**6232 attempted / 6232 completed /
0 failed frequency solves.** Attempt accounting complete:
True. Active numerical time:
1290.920 s; campaign elapsed:
1292.738 s. No historical prediction solves reused.
All audit and per-stage endpoint work is included. Ceilings are 16,256 attempted
solves and 15,300 s; this is not a controlled historical runtime comparison.

[Ledger](work_ledger.json) · [Frozen contract](contract.json) ·
[Manifest](manifest.json) · [Approved plan](approved_plan.md) ·
[Implementation review](implementation_review.md) · [Tests](pre_dispatch_tests.log) ·
[Environment and command](environment.json) · [Workers](campaign.json) ·
[Saved-state figure](endpoints.svg) · [Figure provenance](figure_manifest.json).

Rebuild from saved artifacts, without physical solves:

```bash
python experiments/top019/summarize.py --bundle results/validation/topology/TOP-019-20260915-144340-qualified-merge
```

The historical TOP-016 merge regression and earlier central/two-star successes
remain separate evidence. No result automatically releases a successor or suite.
