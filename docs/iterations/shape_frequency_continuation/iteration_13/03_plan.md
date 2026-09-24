# SC-031 — curvature-aware regularizing LM against the stage-1 collapse

**Approval status: APPROVED.** On 2026-09-24 the user replied "go" to the
explicit request "say 'approve SC-031' to start it". This authorizes
implementation, qualification, the gated two-stage run, documentation and
commit/push milestones on the existing `feature/shape-frequency-continuation`
checkout. It creates no branch or worktree and authorizes no other ID.
**Execution status: IN PROGRESS.**
Owner: Claude (Opus 5.5). Independent reviewer: unassigned.

This plan consolidates the [review and proposal](02_proposals/02_state_reconciliation_and_SC-031.md),
which responds to the [research brief](02_proposals/01_atlas_to_inverse_research_brief.md).
SC-027 is **SUPERSEDED** by SC-031. The proposal's evidence (RD-1) and its
reasoning are not repeated here.

## Question and hypothesis

Is the stage-1 curvature collapse a property of the Gauss–Newton path that a
curvature-aware metric can steer around, or an attractor of the stage
objective that no step metric avoids?

**H:** with Hanke's rule (q = 0.7) and the curvature-change metric (R2), the
tightest radius at the end of stage 1 stays ≥ 7 mm on C and peanut. With the
same rule and the L² mass metric (R1) it ends below 5 mm on both.
- H is falsified as a path-metric mechanism if R2 also ends below 5 mm on both.
- The effect is attributed to the parameter choice rather than the metric if
  R1 also ends at ≥ 7 mm on both.
- 5–7 mm is inconclusive for that case.

## Arms

All arms use the six development cases, the identical wrong-circle start and
the four-stage V2 ladder prefix of the [baseline lock](02_proposals/02_state_reconciliation_and_SC-031.md#2-wp0-baseline-lock-no-new-runs).

| Arm | Step system | λ per iteration |
|---|---|---|
| R0 current | (G + λ diag(max(diag G, 1))) d = −g | Schedule: 1e-3, ×0.3 after success. Existing SC-029 `baseline/none` results; not rerun. |
| R1 mass | (G + λ W_Γ) d = −g | Hanke: ‖r + J d(λ)‖ = q‖r‖ |
| R2 curvature | (G + λ R_Γ) d = −g | Hanke: ‖r + J d(λ)‖ = q‖r‖ |

- W_Γ = (1/P)∫ bᵢbⱼ ds is the arclength mass of the normal-update basis on
  the current curve (P is the perimeter).
- R_Γ = W_Γ + ℓ⁴ (1/P)∫ KᵢKⱼ ds, with Kᵢ = −(bᵢ,ss + κ²bᵢ) in physical
  units. The smoothing length is ℓ = 1/(2.5 k_e,max), with k_e,max the
  exterior wavenumber at the stage's highest active frequency: 15.58,
  10.39, 7.79 and 6.23 mm by stage.
- q = 0.7. If Gauss–Newton cannot reach q‖r‖, λ = 1e-12 × the mean
  eigenvalue of the metric-scaled Gauss–Newton matrix.
- A failed trial escalates λ ×10 and halves exactly as the current loop
  does. λ is recomputed at each iteration, with no carry-over.
- q, ℓ, the factor 2.5 and the fallback are fixed here. None is tuned
  after results.

Unchanged for R1/R2: data and weights, M = 3/5/7/9, K = 192, N = 512/1024,
refit 1e-5, coefficient clipping, acceptance and cross-resolution gates,
tolerances, 22 iterations, SPD quotas, stop rules and the exact validation
cache. The optimizer never receives truth.

## Implementation map

- `lm_backend.BackendConfig` gains opt-in fields: `damping_rule`
  (`schedule` | `hanke`), `hanke_ratio`, `metric` (`marquardt` | `mass` |
  `curvature`), `detectability_factor` and `log_model`. The defaults
  reproduce V2 bitwise. `fit_stage` uses the metric matrix in the damped
  solve and, under `hanke`, sets the first damping of each iteration from
  the rule. With `log_model`, each trial records pred = −gᵀd − ½dᵀGd for
  the executed step, plus the Hanke λ and whether the rule was attainable.
- `updates.BorgesUpdate.metric(space, kind, smoothing_m)` returns W_Γ or
  R_Γ in update coordinates.
- A small driver, `experiments/shape_continuation/regularity_cases.py`,
  reuses the SC-029 harness helpers (`schedules`, observations, `score`).
- Tests go in `pytest/shape_continuation/test_regularizing_metric.py`.

No change to forward solves, refit, acceptance, clipping or production defaults.

## Qualification (before any arm runs)

1. **Default replay:** with defaults and the cache, the SC-029 wrong-circle
   and C `baseline/none` prefixes replay exactly: accepted states, trials,
   stops and work units.
2. W_Γ and R_Γ on a circle equal diag(1, ½, …) and
   (1 + ℓ⁴(m² − 1)²/R⁴)·W respectively.
3. K_Γ agrees with a finite-difference normal variation of curvature on a
   noncircular curve (relative error ≤ 1e-3).
4. Arclength-origin shift: R′ = TᵀRT to 1e-10 relative.
5. The Hanke solve hits the ratio q to 1e-8 when attainable and falls back
   otherwise; the λ = 0 and λ → ∞ limits are correct.
6. The existing package tests pass.

**Amendment before execution:** the proposal's qualification budget of
≤ 300 units could not cover the full C replay (651 units). It becomes
≤ 1,000 units, declared before any run.

## Execution, gate and budget

- **Stage A:** stage 1 only for R1 and R2 on all six cases, checkpointed.
- **Gate:** release stage B only if R2 ends stage 1 at a tightest radius
  ≥ 7 mm on at least one of C and peanut, with no hard stop that R0 did not
  have. Otherwise stop, score the stage-A endpoints and report.
- **Stage B:** stages 2–4 for R1 and R2, resumed from the stage-A
  checkpoints with work and time continued, then score the endpoints.
- **Caps:** per prefix, 8,012 units and 2,700 s. For the campaign,
  ≤ 25,000 inverse units, ≤ 3 h wall with ≤ 6 single-thread workers,
  ≤ 228 endpoint evaluation solves and ≤ 1,000 qualification units. Hard
  stops are retained as outcomes; the remaining budget is checked before
  stage B.

## Metrics and decision

- **Measured:** endpoint symmetric RMS, Hausdorff and its conservative
  bound, work and inverse seconds. Per stage: the tightest-radius
  trajectory, refusal categories, accepted-step cusp index, λ, stop
  anatomy and ρ = actual/pred where pred > 0. At endpoints, the
  19-frequency catalog residual (evaluation only).
- **Decision:** six cases, RMS floored at 0.01 mm.
  - R2 qualifies for fresh-case testing (a separate ID) if
    GM(R2/R0) ≤ 0.8, worst ≤ 1.5 and no added hard stop.
  - The gain is attributed to the curvature metric if GM(R2/R1) ≤ 0.8,
    and to the parameter choice if R1 also passes and GM(R2/R1) > 0.8.
  - A regression over 1.5× on star or kite, the legitimate-detail
    controls, blocks adoption.
  - If the collapse is avoided without an RMS improvement, collapse is not
    the binding limit.

**Artifacts:** `results/validation/shape_continuation/SC-031-regularizing-metric/`.
Results open iteration 14.
