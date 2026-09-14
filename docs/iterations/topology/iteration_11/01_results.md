# Iteration 11 — central recovery; two-star numerical obstruction

Prepared 2026-09-14. TOP-017 approved by explicit user direction and executed from the verified TOP-016 base `9ad3c8b191c7f1130764c0476480290b0f6a6e4a`, on `track/topology-TOP-017`. Numerical source revision: `e3e581f`. Owner: Codex `/root`; independent reviewer: Codex `/root/top017_review`.

**TOP-017 execution is COMPLETE; the central S/F comparison completed, while the two-star pair hard-stopped at its numerical gates. No promotion.**

The [executed iteration-10 contract](../iteration_10/03_plan.md) owns the scope. The [result bundle](../../../../results/validation/topology/TOP-017-20260914-staged-continuation/README.md) owns measured tables, [full scorecard](../../../../results/validation/topology/TOP-017-20260914-staged-continuation/scorecard.json), [endpoint figure](../../../../results/validation/topology/TOP-017-20260914-staged-continuation/endpoint_quality.png), manifests, exact work, accepted states and diagnostics.

## What improved

Central `F` recovered within all original gates from the retained common-stage start: boundary **8.81539 → 0.0623345 mm**, IoU **0.909688 → 0.999426**, and worst development-evaluation error **0.521397 → 0.00123772**. The paired `S` arm ended at **6.12516 mm** and **0.321496** worst evaluation error. F used **3,850** new physical frequency solves versus S's **4,772**. This establishes useful recovery from this saved fixed-count start under the specified cumulative protocol; it is not a twelve-scene benchmark pass or generalization claim.

The predetermined F stage-2 endpoint already passed all gates. Stage 3 reached 0.0464422 mm and 0.000964216 worst evaluation error; stage 4 was slightly worse on those scores but still passed every gate. Stage 4 remains the final result. Truth/evaluation scores never selected a stage, iterate, restart or frequency.

## What remains unresolved

The two-star `F` arm completed six Jacobians and five accepted updates in stage 2, then rejected a candidate whose 0.75-GHz production/refined discrepancy was **1.36142e-7**, above the frozen **1e-7** tolerance. Its last accepted state and matching gradient remain saved; there is no later full six-frequency/geometry endpoint score. It used 872 solves and did not advance.

The two-star `S` arm transitioned through its stage-2 quota, then its stage-3 endpoint failed the same numerical regime at 1.25 GHz: **1.06641e-7** against **1e-7**. The recorded 11.8958-mm boundary and 1.35250 worst evaluation error are attached to that exact state but are marked numerically unqualified. It used 2,993 solves and did not enter stage 4.

These are numerical-qualification obstructions, with zero failed physical solves. They prevent the complete paired predicate and do not decide the two-star recovery benefit of frequency diversity. The central positive result remains valid evidence. Schedule completion, numerical validity, configured convergence and geometric success remain separate: central F's final stage ended at gradient tolerance, while earlier quota/no-decreasing-step stages do not establish convergence.

## Merge control audit

The saved TOP-016 regression is preserved. A single evaluation-only projection at each K gave benchmark boundary errors **0.715424 mm (K9)** and **0.0171234 mm (K17)**, with worst evaluation errors **0.0898651** and **0.00234457**. Both qualified at 128/256; no 512-node work was needed. Dense projection curves stabilized to about 1.65e-9 m across the two sampling grids; nearest-sample distance variation is separately reported.

This exposes an unqualified representation assumption for the merge control, not an approximation lower bound or an inverse cure. Neither projection initialized an inverse. The [saved merge-stage audit](../../../../results/validation/topology/TOP-017-20260914-staged-continuation/merge_stage_audit.md) retains first prediction deterioration in shared stage 1 and first geometric deterioration in F stage 2.

## Scope, work and validation

Phase A used **48/256** solves and **11.16/300 s**. Total new work: **12,535 attempted/completed, zero failed**; every stage/trial ceiling was respected. Campaign elapsed **1,001.98/7,500 s**, at most two workers with single-thread BLAS. Summed active worker time is 1,866.01 s and is not campaign elapsed time. Historical common-prefix work is reported separately; stage 1, oracle generation and information screens were not rerun.

The implementation uses the inherited FD/LM mathematics and settings, with one optional diagnostics callback and an experiment-owned ledger. Planned quotas can advance with qualified accepted states; global limits and unsafe outcomes hard-stop. Original numerical defaults, old drivers and all TOP-016 evidence remain preserved. The independent review and focused mocked/geometry tests are retained in the bundle. Missing terminal gradients or partial derivative diagnostics remain explicitly missing; no extra Jacobian was run for reporting.

## One next decision

**Decide whether a separately scoped numerical-resolution check of the saved two-star states is justified before any further continuation experiment.** This closeout does not authorize that work, a higher-resolution rerun, a merge inverse, new controls, a suite or a successor ID. TOP-013/014 remain deferred and TOP-015 remains superseded as previously recorded.

Validated work is committed locally. No push, merge or branch deletion is authorized by this closeout.

## Visual evidence addendum — 2026-09-14

The user's follow-up requested video evidence. [This 53-second animation](../../../../results/validation/topology/TOP-017-20260914-central-video/central_circle_to_ellipse_star.mp4) shows the archived central-circle topology history, the shared TOP-016 continuation, and TOP-017's S/F accepted states. [Rendering provenance and limits](../../../../results/validation/topology/TOP-017-20260914-central-video/README.md) explain the explicit run boundaries. No numerical run was repeated and the sealed result bundle is unchanged.

The central shape-recovery result passes all original gates, but TOP-017 began with two already-found components. A fresh integrated automatic run from the initial circle has not been revalidated; the video must not be read as that stronger claim.
