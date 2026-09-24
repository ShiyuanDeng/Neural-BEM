# Iteration 14 — SC-031: the stage-1 collapse survives a curvature-aware regularizing LM

2026-09-24. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**SC-031 execution: COMPLETE at its stage-1 gate.** The pre-registered
hypothesis is falsified and stages 2–4 were not run. The measurements are in
the [SC-031 bundle](../../../../results/validation/shape_continuation/SC-031-regularizing-metric/README.md);
the contract is the [iteration-13 plan](../iteration_13/03_plan.md).

## What changed

`lm_backend` gained opt-in switches: `damping_rule="hanke"` (Hanke 1997,
‖r + J d‖ = q‖r‖), `metric="mass" | "curvature"` and trial model logging.
`BorgesUpdate.metric` returns the arclength mass W_Γ, or W_Γ plus the
linearized curvature-change term ℓ⁴KᵀK. The defaults are untouched: the
SC-029 wrong-circle and C prefixes replay exactly. The new tests cover the
circle formulas, a finite-difference curvature variation, arclength-origin
covariance and the Hanke root. No production default changed.

## What the measurement established

1. **The collapse is not an artifact of the step rule.** C and peanut end
   stage 1 at 1.9–2.2 mm tightest radius under every rule tested. These
   are R0 (clipped Gauss–Newton), R1 (Hanke + L² metric) and R2 (Hanke +
   curvature metric), plus SC-024's 6 mm displacement cap. The truth radii
   are 14.6 and 13.5 mm.
2. **The metric was active and the model was accurate.** In R2 the
   curvature term carries a median 64–89% of the step norm on C, kite and
   peanut. Hanke's λ (1e2–3.5e3) is comparable to G. Accepted steps have
   actual/predicted decrease 1.00–1.05. The corner forms through
   well-modelled descent of the stage-1 objective. It is not a finite-step
   failure.
3. **Unplanned observation.** With identical data and objective, R2 ends
   stage 1 at lower misfit than R0 on C, kite and peanut, by 2.8×, 730× and
   11×. It also has lower geometric error (stage-1 GM floored RMS ratio 0.65
   against R0 and 0.82 against R1) and fewer refit refusals than R1. Kite
   improves most: 2.51 vs 5.05 mm RMS and 9 vs 90 refusals. Its sharp tip
   matches a truth radius of 2.14 mm. These are single stage-1 runs on
   development data.

## What remains uncertain

- Whether R2's stage-1 advantage survives the rest of the prefix. That is
  exactly the withheld stage B.
- Whether the collapse is an attractor of the stage-1 objective in
  general. Only one start, one first frequency and one first band were
  tested; SC-029's M = 2 first band avoids it on C and peanut.
- On C the first two iterations used the declared Gauss–Newton fallback,
  so the regularized path began from R0's 16 mm state. Peanut does not
  have this caveat: about 20 regularized steps from 34 mm still collapse.

## Claims

- **Rejected:** a step metric of the SC-027 family, carried by a
  regularizing λ, prevents the stage-1 collapse in this update space.
- **Supported, development evidence only:** the collapse is a well-modelled
  descent path of the stage-1 (0.5 GHz, M = 3) objective. The lever is the
  stage-1 objective (data, band, prior), not the optimizer's step
  geometry. This matches the brief's distinction between *a mode changes
  the data* and *a useful finite step exists*: here the data themselves
  pull the curve into a representation-scale corner.
- **Not established:** any four-stage or recovery benefit of R1/R2.

## Smallest next decision (proposed, not approved)

| Option | Question | Cost | Recommendation |
|---|---|---|---|
| **SC-032: run SC-031's withheld stage B** | Does R2's better stage-1 fit carry to the four-stage prefix under SC-031's unchanged criteria (GM ≤ 0.8, worst ≤ 1.5, star/kite safeguards)? It resumes from the saved stage-A checkpoints; the code already exists. | ≤ 12 paths, ≤ 10,000 units, ≤ 1.5 h | **Do first.** It decides the shared backend that any WP4 comparison must use, and it is cheap. |
| First-stage objective choice (WP4) | Can a truth-free diagnostic at the start choose the first band/frequency that avoids the collapse? SC-029: M = 2 helps C/peanut and harms kite/hook. | Needs WP1 qualification of the chosen quantity | After SC-032, on the adopted backend. |
| Explicit shape prior | Does a curvature prior on the objective change the attractor? | New mechanism, bias risk | Defer; consider only if both above fail. |

The WP1 qualification, the WP2 rollouts and WP5 remain deferred, as in the
[review](../iteration_13/02_proposals/02_state_reconciliation_and_SC-031.md#4-resolution-of-the-briefs-recommendations).
