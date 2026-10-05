# RG-001 execution record

User approved RG-001 with “go on RG-001” on 2026-10-05 and explicitly selected
the existing `feature/shape-frequency-continuation` branch. No branch or worktree
was created. The pre-registered plan remains unchanged.

Execution began at 09:24 UTC. The four-hour ceiling is 13:24 UTC; no new stage
opens after 12:39 UTC. Stage 0 has a 15-minute limit. Truth-stage checks retain
the full frozen truth coefficients even when a stage stores fewer modes:
cropping would diagnose a different shape. Identical catalog/resolution requests
are reused across stages; all fixed and possible frontier stages are recorded.

Production/refined failures and non-finite evaluations are fatal under both
gates, as required by the plan. For finite solver-ready states the default
absolute gate retains its decisions, accepted coefficients, and stage behavior.
The historical production-failure branch refused a proposal; the explicit
fatal-failure contract tightens that exceptional path, without relaxing it.

Other pre-existing untracked work is preserved and excluded from RG-001 commits.

The first Stage 0 attempt stopped after writing `circle__c0.5.json` because the
driver called a nonexistent `ModalMuller.close()`. Its original manifest, source
archive, receipt and traceback are retained in `RG-001/failed_stage0_01/` and
were validated, committed and pushed before repair. Cleanup now calls `close`
only when supplied by the backend. The rerun freezes a fresh campaign manifest;
no fitting or numerical qualification setting changed.

Stage 0 completed in 102.34 s: 30/30 truths pass the original endpoint audit
and residual criterion. All aphex truths pass all declared stage pairs, so P2–P4
are not revised. `cog__c13.3` is labelled gate-limited by construction under the
plan's exact-truth diagnostic: its early production/refined pairs overshoot,
while its final pair passes. This labels field qualification at those exact
truth states; it does not assert that an intermediate fit must reach the exact
truth during the damped prefix.

The four saved killing trials replay with exactly matching production and
refined gains (zero relative differences), and all four are accepted by the
decision gate. The declared replay-construction repair was not needed.
