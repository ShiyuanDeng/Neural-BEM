# SC-032 — four-stage continuation of SC-031's regularizing-metric arms

**Approval status: APPROVED.** On 2026-09-24 the user replied "go" to the
request "reply 'approve SC-032'", as proposed in [iteration 14](01_results.md).
The approval covers implementation, the run, documentation and commit/push
on the existing checkout, with no new branch or worktree.
**Execution status: COMPLETE (2026-09-24).** All 12 paths finished their
schedules within budget (5,112 stage-B units, 19 min). R2 fails the ≤ 0.8
bar (GM 0.832, worst 1.00), and R1 is worse than R0. The artifacts are in
[the SC-032 bundle](../../../../results/validation/shape_continuation/SC-032-regularizing-metric-prefix/README.md),
and the results open [iteration 15](../iteration_15/01_results.md).
Owner: Claude (Opus 5.5). Independent reviewer: unassigned.

## Question

Does the better stage-1 fit of Hanke + curvature metric (R2) carry through
the four-stage prefix, although the stage-1 collapse persists? This is
SC-031's withheld stage B. It is not a new mechanism.

## Contract

- **Arms and settings:** R1 and R2 exactly as in the [SC-031 plan](../iteration_13/03_plan.md).
  Stages 2–4 (0.75/1.0/1.25 GHz cumulative, M = 5/7/9) resume from SC-031's
  saved stage-A checkpoints, continuing their work and time. The
  numerical sources (`lm_backend`, `updates`, geometry, forward, solvers)
  must hash-match SC-031's manifest. Only the driver may differ, and only by
  gaining the continuation phase.
- **Reference R0:** the SC-029 `baseline/none` four-stage prefixes,
  bitwise-reproduced by SC-030 and by SC-031's C and wrong-circle replays.
- **Fresh bundle:** `results/validation/shape_continuation/SC-032-regularizing-metric-prefix/`.
  It holds hashed copies of the SC-031 stage-A records it resumes from; the
  SC-031 bundle is unchanged.
- **Decision criteria (SC-031's, unchanged):** six cases, RMS floored at
  0.01 mm.
  - R2 qualifies for fresh-case testing (a separate ID) if GM(R2/R0) ≤ 0.8,
    worst ≤ 1.5 and no added hard stop.
  - The gain is attributed to the curvature metric if GM(R2/R1) ≤ 0.8, and
    to the Hanke parameter choice if R1 also passes and GM(R2/R1) > 0.8.
  - A regression over 1.5× on star or kite blocks adoption.
- **Budget, as proposed:**
  - ≤ 10,000 inverse units for the campaign, split equally: 833 stage-B
    units per path, plus SC-031's 8,012-unit prefix cap.
  - ≤ 2,700 s per prefix including stage A.
  - ≤ 1.5 h wall with ≤ 6 single-thread workers.
  - ≤ 228 endpoint evaluation solves.

  A path that reaches its unit or time share is a budget-limited hard stop.
  It is reported as inconclusive for that path and not counted as a method
  failure. Nothing is extended or retried.
- **Measurements:** as SC-031, over all four stages: RMS, Hausdorff, work,
  seconds, the tightest-radius trajectory, refusal categories, λ,
  attainability, ρ, the curvature share of the step norm, and the
  19-frequency catalog residual (evaluation only).

Results open iteration 15.
