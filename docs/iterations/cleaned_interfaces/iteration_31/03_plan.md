# RG-001 — Decision-relative resolution gate on TG-002

Prepared 2026-10-05 by Claude, from the [outside review](02_claude_review.md),
findings R1–R3. User request: "draft plans for all three tracks".

**Status: PROPOSED.** Nothing has run. Running it needs the user's explicit
approval of the ID RG-001. Approval covers Stages 0–4 below, their single
declared repair and the closeout. It does not cover the successor IDs listed
at the end, a new branch or worktree, or any other experiment.

## Question

Do the four TG-002 failures (aphex 0.5/4/13.3 and hook 13.3) fail because the
inverse cannot reach the truth? Or does a fatal per-frequency field tolerance
abort runs whose trial steps the pipeline's own acceptance test approves?

## Evidence entering

The review recomputes every number below in
[ON-review-20261005](../../../../results/validation/cleaned_interfaces/ON-review-20261005/README.md).

- All four failures end at `lm_backend.py:571` with "candidate leaves the frozen
  numerical-resolution regime". The `modal_fixed` pipeline has no resolution
  response, so the first per-frequency production/refined discrepancy above the
  stage tolerance is fatal. The tolerance is 1e-5 at or below 0.5 GHz and
  1e-7 above.
- Every killing trial reduced the loss. Production and refined gains agreed to
  1e-6–1e-4 relative. `acceptance()` (`lm_backend.py:325`) would have accepted
  each trial by 1.4e3x to 1.7e5x. The gate overshoots were:

  | Case | Overshoot |
  |---|---:|
  | aphex 4 | 2.26x |
  | aphex 13.3 | 1.24x |
  | aphex 0.5 | 39.5x |
  | hook 13.3 | 2784x |

- When killed, aphex 4 was at 1.7 mm RMS and still falling, with ten stages
  left. With nodal reject-then-promote, PC-001 N1 took aphex 4 to 0.30 mm
  RMS and a 1.95 mm Hausdorff upper bound, with a passed audit. It stopped on
  residual (0.055) and the 1800 s wall limit.
- None of the 26 successful B runs ever recorded a numerical obstruction.
- hook 13.3 ends its damped prefix at 6.8 mm RMS. Every success ends it at
  1.13 mm or less, so this is a separate basin problem (R2).

## Fixed comparison

- TG-002 only: all 30 cases with frozen inputs and placements. One centred
  65 mm start, `--localization none`, no grid search or restarts. Physics is
  `modal_muller`, the update is `certified_spectral`, and the policy is the
  default `CumulativePolicy` schedule.
- **C (control):** the retained ON-001 E recipe (`required_accuracy=0.003`),
  otherwise unchanged.
- **RG:** C plus the single opt-in change below. No other setting differs.
- Benchmark caps are unchanged: 120 s fit, 13,412 work units, and a 30 s
  aggregate audit allowance with a 10 s terminal reserve.
- Execution is unchanged:
  - One case worker, CUDA, four frequency threads and one BLAS thread.
  - Fresh interpreters for every case.
  - Contiguous C/RG pairs, each holding the compute lock for the pair.
  - One source fingerprint for the whole campaign.
  - Timing boundary as in the ON-001 confirmation: case entry to fit return,
    after `fit_result.json` is written.
- Recovery gates are unchanged. The endpoint audit still enforces the absolute
  1e-5/1e-7 field agreement, the 1e-3 Jacobian and full-trial derivative
  checks, RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm, and per-frequency
  residual ≤ 0.003. Truth enters only after the fit and audit return, and in
  Stage 0.

## The one change

Add `resolution_gate` to `BackendConfig` and `CumulativePolicy`, with values
`'absolute'` (the default) and `'decision'`.

- **`'absolute'`:** exactly today's behaviour. A per-frequency discrepancy
  above the stage tolerance raises `NumericalFailure` when
  `resolution_response is None`.
- **`'decision'`:** the trial keeps the decision `acceptance()` computed,
  `min(dp, dr) > margin + 5|dp - dr|`, captured before `checked_pair`
  overwrites `accepted`. The overshoot is still recorded on the check row as
  `numerical_obstruction=True` and `gate='decision'`, together with the
  per-frequency ratios. A rejected trial follows the ordinary rejection path
  (damping increase and backtracks), exactly like any other refused proposal.
- Failed or non-finite production or refined evaluations stay fatal in both
  modes.
- Nothing else changes: the endpoint audit, the early exit, the resolution
  profiles, the caps and the receipts' existing fields.
- Receipts add three things: the gate mode, a count of trials accepted despite
  an overshoot, and the largest overshoot among accepted states.

## Stages

### Stage 0 — truth feasibility, before any fit (≤ 15 min)

Truth is used only here and only as a feasibility diagnostic. It changes no
algorithm, setting or case list. For each of the 30 truths:

1. Run the unchanged endpoint audit (`runner.audit`) at the truth curve, with
   the final-stage resolution pair (K_trace 128/160) and all 19 real
   frequencies. Record field agreement, Jacobian and full-trial checks, and
   the per-frequency data residual.
2. For every fit stage in the policy, record the per-frequency production/
   refined discrepancy at the truth against that stage's tolerances and
   catalog. This includes the damped stages at K_trace 64/96.

Registered predictions:

- Every truth passes (1) and has residual ≤ 0.003, since the data were made by
  nodal Kress qualified at 1e-8.
- Whether the aphex truths pass (2) at the damped-stage pair is **uncertain**.
  If an aphex truth fails it, the absolute gate makes that case unreachable by
  construction. The case is then labelled "gate-limited by construction"
  before Stage 2, and its prediction below is revised in writing, not silently.

### Stage 1 — implementation and validation (≤ 75 min)

Focused tests, all required before any fit:

1. **Default unchanged.** In `'absolute'` mode, a saved C/E case replays with
   identical accepted coefficients and decisions.
2. **Synthetic `'decision'` cases.**
   - An overshoot with agreeing positive gains is accepted.
   - An overshoot with disagreeing gains is rejected without raising.
   - A non-finite evaluation still raises.
3. **Replay of the four killing trials.** Rebuild each from its saved base
   state and saved `step_m`. In `'decision'` mode all four must be accepted
   with the recorded gains, to within numerical reproducibility.
4. **Audit unchanged.** The endpoint audit still fails a deliberately
   under-resolved curve.
5. **Regression suites.** The package README validation suite and the affected
   shared-continuation suites, as run before ON-001.
6. **Reproducibility baseline.** Run two fresh C runs each on circle 4 and
   kite 0.5. Their coefficient differences set P1's tolerance; if they are
   bit-identical, P1 requires bit identity.

**Declared repair (one).** If test 3 cannot reproduce a saved killing trial
from the receipts, make one focused correction to the replay construction
only. If it still fails, stop as `QUALIFICATION_INCOMPLETE`.

### Stage 2 — paired all-30 (≤ 60 min of compute)

Run C and RG on all 30 cases as contiguous pairs. Validate, commit and push
after each pair, as in ON-001. Failures run to their caps.

### Stage 3 — independent checks (≤ 30 min)

- Every new recovery gets an independent nodal N1024/N2048 field, Jacobian
  and full-trial check on its endpoint, as in PC-002.
- Every new recovery also gets one further fresh repeat of its RG run, to
  confirm the recovery reproduces.
- Run two extra sequential C/RG timing repeats on circle 4, kite 0.5 and
  star 13.3.

### Stage 4 — diagnostic reach for the four failures (≤ 60 min; not benchmark evidence)

Run RG on the four failures only, with a 900 s fit cap and a 67,060-unit work
cap; the audit allowance is unchanged. These results separate "budget-limited"
from "basin-limited" and are reported apart from TG-002 recovery. A recovery
here is labelled **extended-budget diagnostic**, never a benchmark recovery.

## Predictions (registered before Stage 2)

| ID | Prediction | Falsified by |
|---|---|---|
| P1 | All 26 successes recovered in both arms. C and RG make identical accept/refuse decision sequences, and their accepted coefficients differ by no more than C's own run-to-run variation (Stage 1, test 6). | Any regression or decision change. This means the gate was active in successes, contrary to the receipts. |
| P2 | aphex 4 gets past release_M11 and recovers within the 120 s cap, or at least passes both shape gates with a passed audit. | It stalls at or above 1.7 mm, or its endpoint fails the audit. |
| P3 | aphex 0.5 gets past stage_3_damped and improves on 4.4 mm RMS. Recovery is uncertain; N1 reached 1.6 mm. | It is killed or stalls at or above 4.4 mm. |
| P4 | aphex 13.3 and hook 13.3 still fail, with RMS ≥ 3 mm (damped-prefix basin, R2). | hook 13.3 recovers. That would refute the basin diagnosis. |
| P5 | Converged RG endpoints pass the unchanged audit. | Systematic audit failures at RG endpoints. The absolute gate was then protecting the endpoint, and the follow-up must be a resolution response (RP-001), not a relaxed gate. |

## Classification

| Outcome | Requirement |
|---|---|
| Major recovery success | ≥ 2 new TG-002 recoveries within the benchmark caps; P1 holds |
| Useful partial result | 1 new recovery; or a failure that passes both shape gates with a passed audit; P1 holds |
| Mechanism confirmed, no recovery | The killed failures progress (≥ 25% RMS reduction beyond their B abort point) without recovering; P1 holds |
| Negative | No failure progresses by 25%. The gate was not binding. |
| Invalid | P1 fails. Stop, preserve the evidence, diagnose. No claims. |

Timing is secondary. Report paired C/RG times on common successes, which P1
predicts are equal within noise, together with suite totals including
failures.

## Decision table

| Observation | Next action inside RG-001 | Recommended successor (separate ID) |
|---|---|---|
| Stage 0 shows an aphex truth fails a stage pair | Revise that case's prediction in writing, then continue | RP-001, a modal resolution response |
| P1 fails | Stop | None until diagnosed |
| New recovery | Run the Stage 3 checks, then close | AF-001 for speed; PX-001 for contrast 13.3 |
| Shape gates pass but the audit fails at the endpoint | Record; close as useful partial | RP-001 |
| Progress without recovery, or extended reach recovers | Close as mechanism confirmed | PX-001 and/or RP-001 |
| No progress | Close negative | Re-diagnose from Stage 0 and the receipts |

## Budget and stops

Four hours overall, including implementation, validation, compute waiting and
reporting. Stop opening stages at 3 h 15 min and keep the last 30 min for
closeout. Stages 2 and 4 are serialized under the compute lock. A stage that
cannot finish in time is reported as unfinished, never as negative.

## Implementation map

| Area | Location | Work |
|---|---|---|
| Gate mode | `solvers/bem_inverse/continuation/lm_backend.py` (`BackendConfig`, `fit_stage.validate`, `checked_pair`) | Opt-in `resolution_gate`; default unchanged |
| Plumbing | `solvers/bem_inverse/policy.py` | `CumulativePolicy.resolution_gate` passed into `BackendConfig` |
| Tests | Package test location used by ON-001 | Stage 1 tests 1–4 |
| Campaign | New `experiments/benchmark/rg001.py` | Stage 0 truth check, pairs, extended reach, report and gallery; scores only after return |
| Evidence | `results/validation/cleaned_interfaces/RG-001/` | Stage 0 JSON, all receipts, pairs, table, gallery, independent checks |
| Report | `docs/iterations/cleaned_interfaces/iteration_31/05_results.md` | Classification, predictions scored P1–P5, unrun items |

Keep the maintained package independent of `experiments/` and `results/`. The
existing `experiments/benchmark/*.py` files are not edited; TG-002 inputs are
sealed and not regenerated.

## Successor IDs (described only; not authorized here)

- **PX-001:** contrast-13.3 damped-prefix change, for example stronger damping
  or a longer low-frequency phase. It first needs a read-only, stage-by-stage
  diagnosis of where hook 13.3 loses the curl.
- **AF-001:** adaptive-fidelity acceptance for speed. The refined re-solve is
  47–49% of all solves; a trial would be refined only when its
  gain-to-threshold ratio is small, with periodic verification. Evaluate it by
  replay on saved states before any fit.
- **RP-001:** a modal resolution response (reject, then a bounded trace
  promotion), only if Stage 0 or P5 shows endpoints are resolution-limited.

## References

Kouri, Heinkenschloss, Ridzal and van Bloemen Waanders, SIAM J. Sci. Comput.
36(6), A3011–A3029, 2014. Ziems and Ulbrich, SIAM J. Optim. 21(1), 1–40, 2011.
Both cover inexactness conditions relative to the predicted or actual reduction.
