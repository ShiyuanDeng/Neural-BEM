# SC-049: far circle to C, one full reconstruction

2026-09-27. **APPROVED / EXECUTION COMPLETE; NOT RECOVERED.** See the
[iteration 29 results](../iteration_29/01_results.md). The frozen pre-run
contract remains in the artifact bundle. The user requested: "now try a new
scene, a complex one. say far circle to c". Owner: Codex; self-review only.
Use the existing checkout; no branch or worktree creation.

## Fixed scene and question

Test the complete current fixed continuation path from a spatially displaced
circle, rather than a saved suffix start. The initial circle has centre
(0.32, 0.62) metres and radius 0.065 metres. The target is the existing
non-star-shaped C centred about (0.5, 0.5), with 40-mm centreline radius,
18-mm half-thickness, 110-degree half-angle and 0.3-radian rotation. Preserve
the original qualified, noiseless SC-022 observations at all 19 frequencies
from 0.25 to 2.5 GHz. This is a new initialization stress test, not an unseen
target shape or a speedup benchmark. Record initial separation before fitting.

## Fixed execution

- Reuse the SC-035 projected update with cumulative M=3/5/7/9 frequency stages,
  K=8/12/16/20, the original 22-iteration and 1000/1250/1750/4000-unit quotas.
- Follow with the SC-038 full-catalog M=11/15/19 release, K192, 1500 units per
  stage. Then use the SC-043 fixed M=25/31/37 release, 304 units per stage,
  with its one-time K64 cleanup immediately before M25 and K192 evolution.
- N512 production and N1024 refinement; original LM controls and discrepancy
  tolerances. Stop the path on a numerical or hard-budget failure. No restart,
  altered initial location, threshold tuning or truth-selected iterate.
- Explicit CUDA, four frequency threads, one BLAS thread and SPD-014 spatial
  pruning. Fit caches and independent direct diagnostic caches are enabled.
  One numerical worker at a time. Freeze numerical sources and input hashes.
- One path: at most 13412 fitting units and 1800 fitting seconds. Reserve up
  to 260 units/600 seconds for two independent audits and 152 units/600 seconds
  for initial/final atlases. Total numerical ceiling: 13824 units/3000 seconds.

## Evidence and stopping

Before fitting, validate the circle and run the existing full-trial directional
derivative and N/2N field/Jacobian audit over the full frequency catalog.
Persist every accepted state and stage outcome. After fitting stops, audit the
returned endpoint independently using the same 1e-3 Jacobian/FD and existing
frequency-specific field limits. Report failures and partial work explicitly.

Score the initial and returned curves only for evaluation. The declared
recovery screen requires symmetric boundary RMS <=1 mm, sampled Hausdorff
estimate <=2 mm, maximum catalog relative residual <=0.003, and passing
endpoint audit. Report each separately; these are this single-scene screen's
criteria, not the twelve-scene topology benchmark. No topology change is needed
or tested. No held-out-frequency claim: the release uses all 19 frequencies.

Build an initial and final normal-harmonic sensitivity atlas at N512/1024,
P48, charging every field and reciprocal solve. Use the existing frequency
executor, one work counter per frequency and independent exact cache scopes.
Report N/2N discrepancies; atlas values are diagnostic and never select steps.
Save a geometry/progress figure and atlas figures with the complete timing,
work, configuration and provenance receipt. Do not rerun historical campaigns.

Artifacts: `results/validation/shape_continuation/SC-049-far-circle-to-c/`.
Results open iteration 29, preserving SC-048's conclusions.
