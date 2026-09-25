# SC-038 conditional completion of the requested final band

2026-09-25. Recorded while kite's dense M=15 stage is still running, before
its endpoint is available. The user's question asks for release to the
frequency-relevant band M=19. A whole-path time limit should not silently
turn that into a test only of M=15.

If the 768/1536 run ends on `TRIAL_WALL_LIMIT` before any accepted M=19 step,
allow **one** completion of the already planned M=19 stage from its last
accepted curve. Do not launch this on a numerical failure, or if M=19 already
took an accepted step. Keep all numerical settings and tolerances unchanged.
Retain the original time-limited result and count its work.

Use the unspent dense-path solve budget only: at most
`min(1500, 3000 - previous_dense_work_units)` additional units, 22 iterations,
and 900 seconds. Thus the original 3,000-unit dense-path ceiling is unchanged;
only the wall allowance is extended for the remaining stage. There is no
band, damping, tolerance or geometry search. The completed M=9 control is
retained; its denser replay is exactly unchanged from its first stage.

Require the dense endpoint audit to pass before continuing. That audit
already checks all fields and the Jacobian/actual-trial derivative through
M=19, including when the preceding fit stops at M=15. Audit the new endpoint
in the same way (42 units) and score it once (19 fields). These additional
audits remain within the combined 900-unit audit reserve. Stop after this
one opportunity and report its actual outcome, including any remaining limit.
