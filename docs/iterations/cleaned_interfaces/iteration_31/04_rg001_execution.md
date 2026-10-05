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

Stage 1 completed before opening Stage 2. Regression suites pass (247 + 348
checks); the initial suite's one failure was solely the archived dictionary
missing the new default field. The assertion now explicitly requires
`resolution_gate='absolute'` and still compares every archived numerical setting.
Two fresh C runs each on circle 4 and kite 0.5 have bit-identical accepted paths
and decisions, setting P1's coefficient tolerance to zero. Fresh C paths also
reproduce the saved ON-001 E paths bitwise on both controls.

Stage 2 completed all 30 contiguous C/RG pairs. Both arms recover 26/30;
all 26 prior successes have bit-identical decisions, accepted paths and stage
endpoints between C and RG. Aphex 4 improves RMS by 60.6% (1.685 → 0.664 mm)
but fails Hausdorff and field audit gates. No new benchmark recovery occurs.

Stage 3 completed all six declared timing pairs; P1 remains exact. With no
new recoveries, the new-recovery-only nodal audits and recovery repeats are
inapplicable, not unfinished.

Stage 4 completed the four extended-budget diagnostics in 505.00 s. None
recovers. Aphex 0.5 and hook 13.3 reproduce their benchmark endpoints exactly
and stop on production failures. Aphex 4 also reproduces the endpoint exactly;
with additional time it stops on exhausted accuracy-limited trials rather than
the wall cap. Aphex 13.3 reaches 3.776 mm RMS before a production failure.
All extended endpoints fail the unchanged field audit.

Final validation checks all 80 fit receipts, the frozen source fingerprint,
the input seal, recovery calculations, settings and work caps. All 26 fresh C
successes also reproduce the saved ON-001 E paths and final coefficients
bitwise. Five failed runs have a few completed frequency calls beyond the
retained dispatcher's charged total; actual backend attempt counts were checked
separately and also remain within every fit cap. Numerical code was not changed
to address that pre-existing receipt convention inside this single-change study.

Closeout classification: **Mechanism confirmed, no recovery**. P1 holds;
P2 and P3 are falsified; P4 holds. All 26 converged common successes pass the
audit; no newly converged failure endpoint is available for P5, while its
warning about unresolved RG endpoints is observed in all four failures.
The gate remains opt-in. No successor ID was opened, and all authorized stages
are complete well inside the four-hour ceiling.
