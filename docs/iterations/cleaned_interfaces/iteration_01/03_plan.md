# CI-001 — restore clean inverse interfaces and verify retention

2026-09-30. Owner: Codex. Independent review: not performed.

- Approval status: **PROPOSED — NOT APPROVED FOR EXECUTION**.
- Execution status: **NOT STARTED**.
- Current user request: document the requirements and organize this plan in
  its own iteration folder before implementation; check the latest SPD work
  and include its integration in the cleaned implementation.
- Governing brief: [user requirements and clarification](02_proposals/01_user_requirements.md).
- Runtime integration: [SPD evidence and integration assessment](02_proposals/02_spd_integration_review.md).

## Intended outcome

One maintained, cumulative SC/MA inverse must retain earlier performance on
all 36 examined configurations. Its continuation policy must be readable stage
by stage, and the physics backend must be selectable through one option.
The nodal Müller/Kress backend remains the reference during cleanup; modal
Müller is the following backend integration.

The requirements document is authoritative. In particular, CI-001 must verify
that the latest improvements retained earlier capabilities. Copying historical
algorithms into a scene-specific dispatcher does not meet the requirement.

## Starting evidence

The [pipeline inventory](../../../pipelines/shape_frequency_continuation.md)
traces the latest inverse extension, MA-005 DF, through SC-050 to the shared
LM fitter. SC-051's 34/36 reference recovery combines archived strategies;
it does not establish retention for one cumulative implementation. MA-005
has results on 20 configurations, and its frontier tail worsens geometric
accuracy on two noisy transfer cases.

The regression scope is the 6 core, 6 fresh/noisy, 7 far-start and 17 modal
configurations in the
[SC-051 manifest](../../../../results/validation/shape_continuation/SC-051-frequency-only/manifest.json).
The two known high-contrast C failures remain visible. Recovering them is not
required merely to demonstrate retention of existing performance.

The runtime baseline includes SPD-010 through SPD-015's integrated frequency
threading, real-frequency CUDA and exact geometry-validation/cache improvements.
The latest SPD-016 bundle qualifies Mie-grid plus complex-frequency CUDA
assembly acceleration on two complete D attempts (2.43–2.75x), with matched
decisions and work. It must be integrated through the new interfaces, rather
than lost during cleanup. Its optional field-table extension is not selected.
See the [integration assessment](02_proposals/02_spd_integration_review.md)
for source locations, measured limits and verification requirements.

## Planned sequence

1. **Establish the cumulative algorithm and regression contract.** Trace the
   latest improvements, their inherited behavior, complete stage paths and
   historical performance across all 36 configurations. Resolve the input
   requirements, especially complex-frequency observations, and record
   per-case numerical tolerances and matched runtime conditions before testing.
2. **Restore the interfaces with the nodal backend.** Separate problem/data,
   geometry/update, continuation policy, optimizer, physics and reporting.
   Extract maintained functionality from result-folder drivers and remove
   process-global contrast and solver overrides. Preserve archived evidence
   and source snapshots. Retain the qualified SPD threading, real CUDA,
   factor-reuse and geometry/cache paths, with reference execution available.
3. **Expose the policy clearly.** A named policy definition supplies both a
   readable pre-run stage plan and the actual execution decisions. Show static
   stage values, adaptive formulas and thresholds, budgets, stop conditions
   and transitions. Record every resolved decision and its reason.
4. **Establish the backend selection.** Pass the physics dependency explicitly
   through fitting, differentiation, localization qualification, frontier
   diagnostics and numerical checks. Keep matrices, traces, factorizations
   and solver-specific resolution choices internal. Declare any independent
   audit backend and validate required capabilities before fitting. Keep
   solver choice independent of CPU/GPU and frequency-thread settings.
5. **Integrate the selected SPD-016 improvements.** Extract the recurrence/GPU
   Mie-grid evaluator into the localization service and fixed-ray damped
   assembly/device LU into the nodal backend. Replace prototype monkeypatches
   with explicit dependencies, preserve support checks, and validate the
   documented reference/OOM behavior. Reproduce the two qualified complete D
   pairs before extending to the cumulative policy and its DF tail.
6. **Verify all-36 retention.** Use focused equivalence checks during extraction,
   then run the cumulative implementation end to end from each prescribed
   initial condition. Distinguish pre-existing algorithmic regressions from
   refactoring changes. Resolve regressions in shared rules, with no hidden
   scene-specific fallback, and repeat affected checks. Include the integrated
   SPD execution path in this campaign and report matched runtime against the
   current accelerated baseline; old serial-CPU timings are not sufficient.

The next backend integration will hold this established inverse policy and
its observations fixed while qualifying modal Müller, then repeat the all-36
comparison. That subsequent implementation is not part of this documentation
step, and no modal accuracy or speed claim is assumed here.

## Acceptance evidence

| Requirement | Evidence needed |
|---|---|
| Retained performance | Complete per-case comparison of recovery, RMS, Hausdorff bound, residual, numerical audit, stopping outcome, work and matched runtime; no aggregate-only verdict |
| Clear policy | Readable stage plan and decision log generated from the executable policy definition, with localization, damping, cleanup and releases explicit |
| Solver toggle | One backend selection controls all physics calls through a common prediction, complete-trial derivative and accuracy/refinement contract |
| SPD integration | Earlier integrated accelerations retained; SPD-016 grid-plus-assembly extracted without global overrides; matched quality/work and timings through clean interfaces, including the all-36 cumulative path |
| Reproducibility | Source/input provenance, full-path accounting, retained failures and independent scoring outside the inverse |

Same-backend extraction should preserve the algorithmic path and work, with
any numerical differences explained. Cross-backend qualification checks
predictions and derivatives through the complete geometry trial; field
accuracy alone does not establish inverse-step accuracy.

## Planning details still to fix

- The exact cumulative policy, including how earlier stabilization and noise
  handling coexist with the later localization and frontier changes.
- The observation contract for earlier cases without damped measurements.
- Per-case numerical equivalence tolerances and runtime comparison conditions.
- The exact accelerated source snapshot, SPD-016 capability/fallback contract
  and controlled worker/thread settings for integration comparisons.
- Bounded validation work/time budgets and a frozen source/input manifest.

These remain explicit planning items. This document does not silently choose
new data, tune policy thresholds or establish numerical results. Results from
execution will open iteration 02 under the shared iteration convention.
