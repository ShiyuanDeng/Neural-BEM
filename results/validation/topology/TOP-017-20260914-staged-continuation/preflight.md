# TOP-017 implementation preflight and independent review

Owner: Codex `/root`. Reviewer: Codex `/root/top017_review`, read-only review requested 2026-09-14. Review accepted; physical work had not started at review completion.

Verified base: `9ad3c8b191c7f1130764c0476480290b0f6a6e4a`. No intervening source changes. Original feature and TOP-016 worktrees were clean and preserved. Package source: `739a8c1:neural_bem_TOP017_handoff.zip`; all SHA256SUMS passed. No existing destination collisions.

## API/file map before numerical edits

- `run_top016_preflight.py`: reuse frozen data builder, prediction, geometry checks and projection procedure; preserve historical source.
- `run_top016_pilot.py`: reuse acceptance and endpoint scoring; preserve historical stage-budget behavior.
- `solvers/sdf_inverse/radial_topology.py::run_multiradial_fd_inverse`: unchanged LM/FD mathematics and public defaults. Declare one optional diagnostics callback to expose complete Jacobian counts before any step, candidate attempts and feasibility refusals. This permits an immediate hard stop on unresolved derivatives and complete exposure accounting without a second optimizer.
- `run_top017.py`: new experiment-specific typed ledger, source/input verification, bounded Phase-A audit, training-only stage adapter and four continuation trials. Only accepted states transition; endpoint score/state hashes must match.
- `summarize_top017.py`: rebuild merge/principal scorecards and decision from JSON only.
- `pytest/sdf_inverse/test_top017.py`: mock forward, clock, batches and scorer to test transitions, hard stops, exposure, failed-attempt accounting and state/diagnostic binding; existing focused tests qualify defaults.

Stage 2 is the first training intervention: F uses 0.5/0.75 GHz; S retains only 0.5 GHz. For q=34 the F complete Jacobian bounds are 136/204/272 frequency solves. Each stage additionally needs initial objective m, at least candidate production m plus up to 2m refined validation, and 12 endpoint solves. Quotas 1250/1750/4000 exceed these bounds. Individual forwards reserve a whole objective; Jacobians reserve their full maximum batch. Stage quotas may advance only after endpoint feasibility/numerical qualification; total solve/time limits and all unsafe interruptions hard-stop.

Physical exceptions will be translated into a distinct counted PhysicalFailure so the optimizer cannot swallow them as candidate infeasibility. Unresolved derivatives are exposed at the new callback before stepping. Last gradients bind exact serialized state hash, active frequencies, equal-frequency residual normalization and production nodes; stale values remain historical. No terminal Jacobian is run just to fill a missing diagnostic.

## Review resolutions before execution — 2026-09-14

Independent reviewer `/root/top017_review` verified the actual TOP-016 source manifests and observation bytes, coefficient-identical S/F stage-1 endpoints, checkpoint/terminal/score agreement, exact gauge idempotence, 34 reduced directions and radius floors above0.008 m. The equal-frequency objective was verified against the existing residual builder.

- **Accept:** retained inputs, fixed K9/nodes/settings, restarted stages2–4, training-only fit interface, separate typed ledger, diagnostic-only optional hook, bounded K9/K17 merge projection audit.
- **Accept with implemented safeguards:** unresolved complete Jacobians stop before any candidate; physical exceptions count as attempts and use a distinct hard-failure type; wall signals preserve their type and stop during a batch; no scoring follows hard stops. Endpoint scores, gains and gradients carry exact state/objective/resolution associations. Per-frequency requested model events are distinguished from actual physical frequency attempts/completions.
- **Accept binding-quota clarification:** check wall/actual total limits first. A refused next batch is a planned stage transition only when remaining stage quota is the tighter (or equal) constraint and the endpoint reserve fits globally. If the global allowance is tighter, hard-stop. This permits the explicitly approved final planned quota end to complete the schedule without dispatching work over a global limit. Unused quota is not transferred.
- **Accept watchdog safeguards:** no worker launches after the campaign deadline; timeout/unavailable workers retain explicit statuses and actual/null exit codes. The numerical dependency manifest covers root, config and solver Python sources (the JSON-only summarizer is not executed by workers), including acquisition/material imports. Original generated acquisition is compared to the copied observation metadata before solves.
- **Accept audit interpretation:** one optional256/512 prediction comparison per fixed K projection, only if its128/256 result is unresolved; no retries or ladder. The16,384-sample projection is predetermined, and32,768 only checks geometry/projection stability. A merge-only unresolved projection does not invalidate qualified principal starts. No truth projection enters an inverse.
- **Reject:** generic budget advancement, unresolved-derivative advancement, score-only exposure, post-wall scoring, stale diagnostic associations, and treating filtered refined validations as all candidate attempts.
- **Defer:** optimizer/derivative/physical redesign, principal bandwidth changes, new merge/local inverses, more seeds, suites and successors.

The [saved merge audit](merge_stage_audit.md) was rebuilt from JSON before physical release. It distinguishes first shared-stage1 prediction deterioration from first F-stage2 geometric deterioration. Its historical inverse regression remains a promotion blocker.

Mocked tests found and corrected ndarray/list state-hash serialization and exercised the final-stage binding-quota edge. No physical solves were spent on implementation tests. Tests also cover actual wall-signal interruption inside a mocked physical call, reserved batches, failed-attempt accounting, candidate/checkpoint retention, immediate unresolved-column stops, full staged exposure, source/observation reuse and unchanged archived default optimizer trajectories. Final test log and reviewer release are recorded below before numerical execution.

## Independent release

On2026-09-14 `/root/top017_review` accepted the current driver, campaign watchdog, optional core diagnostics,56 passing focused tests in25.36 seconds, and eight-row saved merge audit for approved conditional execution. All identified blockers were resolved. The reviewer performed no edits or physical solves. Phase B remains conditional on Phase A principal input/feasibility/numerical PASS. [Focused test log](focused_tests.log).
