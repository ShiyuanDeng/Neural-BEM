# Iteration 09 — the review implemented: qualified atlas, backend ablations, band policies (SC-023 to SC-025)

2026-09-24. Executed from the [iteration 08 plan and its amendments A1–A2](../iteration_08/03_plan.md),
which implement the [Codex outsider review](../iteration_08/02_proposals/01_codex_outsider_review.md)
as [resolved](../iteration_08/02_proposals/02_review_resolution.md). The
user asked for the review to be implemented without further stops. Owner:
Claude. No independent review of this cycle yet.

## Review items, as implemented

| Item | Outcome |
|---|---|
| Conditional steps, physical metric, normal-ray error layer, physical step control, mode mixing | Implemented and tested. The normal-ray layer is exact to 8e-10 m on the review's counterexample. One Borges move on a circle creates the predicted −ε²/2R doubled harmonic, to 0.07% |
| SC-020/021 historical sources | Rebuilt exactly (the hashes match); archived in each bundle |
| Dense-atlas reproducibility | The Borges star atlas regenerates bitwise from commit 5b852c0 in 40 s. Durable upload is left to the user |
| Atlas refinement and directional checks | 12/12 cells and 24/24 directions pass, to ≤ 2e-9 and ≤ 6e-7 ([SC-023 Q0](../../../../results/validation/shape_continuation/SC-023-conditional-candidates/README.md)) |
| Default backend unchanged | A replay of an SC-022 trajectory with the new code is identical |

## What was found

1. **The refit gate caused the "stalls".**
   - SC-022's C and fixed-32 runs were frozen by the arclength-refit gate
     (K=192, 1e-7). Their accepted curves had drifted to it, and they are
     representable at K=384.
   - The early 18–23 mm steps had carved features with 2.6–4 mm curvature
     radii.
   - Relaxing the gate to 1e-5 helps the C most: Hausdorff 19.4 → 11.8 mm.
   - Neither physical step control nor 4× iterations fixes it.
   - Fixed M=32 fails from far starts under every tested variant
     ([SC-024](../../../../results/validation/shape_continuation/SC-024-backend-ablations/README.md)).
2. **No declared truth-free band rule beats Borges' ladder** on one-step
   geometric gain across all 141 recorded states (SC-023). The raw model
   decrease ranks bands backwards (Spearman −0.27).
3. **The local model predicts steps that were never executed.** On 110
   executed rule-chosen steps, realized/predicted is 1.04 (median), and the
   backend accepts 95%. Near convergence, however, wide bands remove 75–86%
   of the stage loss while worsening the geometry.
4. **A post hoc parsimonious rule qualified on development data only.** The
   rule, A2, takes the smallest band whose controlled, admissible step
   reaches ≥ 0.9 of the best model decrease. On development data it beats
   the ladder on median gain, mean gain and positive fraction.
5. **The frozen A2 policy is not reliably better on held-out cases**
   ([SC-025](../../../../results/validation/shape_continuation/SC-025-band-policies/README.md)).
   It wins large on the C (0.37 against 3.20 mm) and the held-out peanut
   (0.31 against 2.94 mm), and loses on the held-out kite (4.38 against
   2.98) and hook (2.34 against 0.53). The progress controller never
   triggered.
6. **Roughening predicts failure, whatever the band rule.** Across 18 runs,
   the tightest curvature radius reached rank-correlates with the final
   error at −0.88.

## Decision

- **Kept:** the clean hybrid, the qualified atlas, the ladder as the
  baseline, and V2 (refit gate 1e-5) as the backend for new runs.
- **Not established:** that the atlas-derived band choice improves recovery.
  The held-out cases (kite, peanut, hook) are now development data.
- **Next lever, proposed and not run:** regularity of the update metric, not
  another band rule. See
  [the proposal](02_proposals/01_regularity_controlled_steps.md). It opens a
  successor experiment, so it waits for the user's go-ahead.
