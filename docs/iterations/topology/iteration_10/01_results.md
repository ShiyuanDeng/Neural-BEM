# Topology iteration 10 — useful local information, an incomplete recovery comparison, and a control regression

TOP-016 completed its authorized bounded execution on 2026-09-14. The user’s instruction to install and follow the supplied handoff approved the iteration-09 contract. [Plan](../iteration_09/03_plan.md) · [Result bundle](../../../../results/validation/topology/TOP-016-20260914-fixed-topology/README.md) · [Independent review](../../../../results/validation/topology/TOP-016-20260914-fixed-topology/closeout_review.md).

## Measured result

The representation and numerical gates passed. The K=9 gauge-constrained Cartesian chart approximated the principal truths within 0.1 mm, and 128/256 was the smallest qualifying common node pair. Original 24-pair observations, IDs and saved states were preserved.

Both information screens passed with eight usable weak directions: median F/S data-change gains were **21.4038** for `far-two-stars` and **17.6264** for `central-ellipse-star`. These are local sensitivity measurements, not reconstruction results.

Both principal S/F pairs exhausted their first-stage allocation before reaching the added frequencies. Their matching retained endpoints therefore cannot compare frequency continuation with single-frequency recovery. The two-star boundary error moved **11.991 → 12.033 mm**. The central ellipse/star error improved **9.223 → 8.815 mm**, IoU **0.7775 → 0.9097**, and worst evaluation error **0.8922 → 0.5214**, while still failing boundary and prediction gates. Preserve that mixed improvement; do not call it successful recovery or no benefit.

The merge control completed all four stages. S ended at **0.5355 mm** boundary error and **0.09807** worst evaluation error. F ended at **1.1082 mm** and **0.16795**, versus **0.5542 mm** and **0.09398** initially. F thus introduced a new geometric gate failure and worsened prediction. That measured adverse control result independently prevents promotion.

Both prescribed truth-assisted local controls stopped after three accepted 0.5-GHz updates, at **236/250** first-stage solves. Boundary error moved **2.2376 → 2.3275 mm** despite improved data fit. Local recoverability remains unresolved within this budget; these are not automatic-recovery trials.

## Cost, implementation and limits

**10,306 attempted/completed frequency solves; zero failed.** Phases 0/1 used **2,781 solves / 777.976 s**. Sum of active trial-worker times was **910.327 s**; trials ran with at most two processes, single-thread BLAS, so this is not end-to-end elapsed time. Every stage cap, including endpoint scoring, and every wall ceiling passed independent and zero-forward checks.

The only numerical API change is opt-in fixed-topology LM hooks for separate loss-change stopping, both-resolution candidate validation, batch reservations, checkpointing before Jacobians and cache accounting. The LM equations, physical solver, chart, controller policy and defaults remain unchanged. No full twelve-scene qualification ran.

Diagnostics are incomplete in specified ways: rejection-gain logs include only candidates reaching refined validation; full feasibility-refusal counts were not preserved; interrupted endpoints lack a newly measured terminal gradient. Earlier gradient files are explicitly associated with their measured states. These limitations do not invalidate retained endpoints or exact physical-solve accounting. [Full scorecard](../../../../results/validation/topology/TOP-016-20260914-fixed-topology/pilot_metrics.json) preserves every stage and arm.

The environment interruption occurred after the six main trials saved their terminal artifacts. The missing parent-orchestrator summary was rebuilt from those artifacts, with unavailable exit codes left null; no completed trial was repeated. The worktree remains `/home/drdeng/Neural-BEM-TOP-016` on `track/topology-TOP-016`.

## Decision

**Close TOP-016 without promotion.** Its principal comparison is inconclusive under the declared budget, and the completed F-merge control regressed. The single next decision is whether a revised fixed-topology contract is warranted, addressing both the merge-control regression and the stage-1 budget obstruction before committing more compute. This is a review decision, not authority to run a successor, change the optimizer, or start a full suite.

TOP-013 and TOP-014 remain deferred/not selected; TOP-015 remains superseded. No new experiment ID is allocated or approved here.
