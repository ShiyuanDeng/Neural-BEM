# SC-045 — independent qualification after audit timeouts

2026-09-26. Owner: Codex; independent reviewer unassigned. This follow-up is
authorized by the user's instruction to continue through research obstacles.

Five endpoint audits in SC-042/044 exceeded their 900-second emergency limits
during a host memory-pressure event. Their original fitting results and
failed audits remain immutable. The observed audit traces report
`TrialWallLimit`, not a failed field, Jacobian or finite-difference tolerance.
They stopped after 81, 84, 104, 100 and 101 of the normal 114 work units.
At the first investigation, Linux memory pressure averaged 73.37% over
300 seconds (72.87% full stalls); these figures diagnose an environmental
obstruction, without identifying a unique cause. Timing is uncontrolled.

Freeze precisely these returned states before any follow-up solve:

- SC-042 kite / boundary and cap;
- SC-042 circle_to_c / boundary;
- SC-044 asymmetric_lobes / clean / cap;
- SC-044 asymmetric_lobes / noise_seed_0 / boundary.

Hash each original result, audit and configuration, the numerical sources,
and all inherited observation inputs. Run the original `SC-042.audit` once
per endpoint: identical curve coefficients, stage, observations, weights,
grids, field gates, all-column Jacobian gate, FD direction/step, 130-unit
ceiling and 900-second emergency ceiling. No fit, cleanup, new iteration,
finer grid, tolerance relaxation or second retry is allowed.

Execute serially after all SC-042 paths terminate, while SC-044 retains its
two workers. Delay SC-043 until these five independent audits terminate.
This limits the heavy 768/1536-node jobs to one at a time during this phase.
The subsequent SC-043 dispatcher additionally limits simultaneous heavy
jobs by a conservative memory weight, with no change to any numerical rule.

Maximum additional qualification work: 650 units. Record every replay cost
in addition to the original failed cost. Do not replace original `passed`
flags or turn a failed frozen gate into a pass. A successful follow-up
qualifies the unchanged returned geometry in a separately reported study;
it does not retrospectively change the original experiment's outcome.
Separate comparison of mathematical/numerical behavior from wall-limit
failures. A failed follow-up remains a substantive qualification barrier.
