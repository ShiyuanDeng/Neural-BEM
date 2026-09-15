# TOP-018 results — qualified two-star recovery

Completed 2026-09-15 under the [iteration-11 contract](../iteration_11/03_plan.md).
The user explicitly approved the audit and conditional pair. Owner and reviewer:
Codex `/root`, with an owner review and no independent-agent review.

**The cumulative-frequency F arm recovers both stars from the saved common
fixed-count start; the matched single-frequency S arm does not.** Both arms
completed their prescribed stages and passed every endpoint numerical check at
256/512 nodes. This resolves the specific TOP-017 two-star comparison that was
previously blocked by numerical qualification.

| Prescribed stage-4 endpoint | Boundary error (mm) | Sampled IoU | Worst development-evaluation error | Original gates |
|---|---:|---:|---:|---|
| S: 0.5 GHz only | 11.793168 | 0.738281 | 1.306218 | Fail |
| F: cumulative 0.5/0.75/1.0/1.25 GHz | 0.00167644 | 1.0 | 3.323707e-6 | Pass |

[Full result bundle][bundle] · [fixed-state figure][figure] ·
[all stages, gradients, exposure and objectives][scorecard] · [owner closeout review][review].

[Side-by-side S/F video (50 s)][video] · [video provenance][video_provenance].
The animation uses all saved accepted-state records, with stages aligned for
playback and no new numerical solves.

## What was measured

Phase A passed with **86 new attempted/completed frequency solves**. All four
fixed states qualified at 256/512 with unchanged thresholds. Predictions for the
three previously audited states reused verified historical evidence (54 earlier
solves); COMMON was evaluated anew. The first and last reduced-gauge directions
both passed the inherited two-scale and numerical-floor checks. No information
screen, oracle, central inverse or historical common-prefix inverse was rerun.

Both new arms started from the identical TOP-016 common low-frequency endpoint
used by TOP-017, at Cartesian K=9. Their stopped TOP-017 endpoints were audit
inputs only. The finer forward resolution and declared wall accommodation were
the intended changes; coefficients, observations, optimizer mathematics,
frequency schedule, acceptance margins and numerical thresholds were preserved.

F first passed all recovery gates at the prescribed stage-3 endpoint, at
0.00239742 mm boundary error. Stage 4 remains the final result. F stopped on its
configured loss target; a current endpoint Jacobian/gradient is also recorded.
S stopped at its maximum iteration count and remains unconverged under the
configured tests. Its final 0.5-GHz relative error is `4.8607495e-5`, despite
poor geometry and development prediction. The conclusion applies to this
bounded paired protocol; it is not a global non-identifiability claim about
single-frequency data.

## Work and reporting integrity

New work totals **8,336 attempted/completed frequency solves, zero failed**:
Phase A 86, S 4,795, F 3,455. Endpoint-inclusive quotas and every solve/wall
ceiling pass. Summed active numerical time was **4,190.657 s**; campaign elapsed
was **2,565.869 s**, with at most two workers and single-thread BLAS. These are
work records, not a controlled runtime comparison against TOP-017.

Measured numerical source is `9bde9d1`. The pre-dispatch 87 mocked/geometry tests
passed. A later reporting-only error occurred after both complete schedules:
list/tuple equality rejected identical frequency metadata. Both failed worker
exits, original metrics and tracebacks are retained. Source/input integrity was
verified unchanged through numerical completion before that annotation code
was corrected. Missing associations were rebuilt from saved artifacts, with
every original scientific field unchanged and zero new physical solves.
The final regression run passed **89 tests**, including the reproducer for
both arms. [Repair and preserved failures][repair].

## Scope and one next decision

This is a fixed-count development-case success from a saved common endpoint.
It does not establish a fresh automatic far-circle-to-two-star pipeline or
twelve-scene qualification. Preserve TOP-017's central success, the later fresh
central integration result, and TOP-016's unresolved merge inverse regression.

**Next decision: prepare one separately approved K=17 merge-control S/F
comparison with qualified representation capacity.** TOP-017's evaluation-only
K=17 merge projection passed the geometric and prediction gates, while K=9 did
not qualify the prediction gate. That is evidence that a more adequate control
representation is available, not evidence that an inverse will find it. Testing
that control is the next discriminating step before broader integration claims.
No merge inverse, new bandwidth change, suite, fresh two-star run or successor
starts under TOP-018.

The [handoff completion roadmap](../README.md#completion-roadmap) records the
conditional sequence after this decision: fresh automatic two-star integration,
the full frozen twelve-scene comparison, then closure against declared gates.
It also records what a new session should read first and which execution
contracts remain to be defined and approved.

[bundle]: ../../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/README.md
[figure]: ../../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/endpoints.svg
[scorecard]: ../../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/scorecard.json
[review]: ../../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/closeout_review.md
[repair]: ../../../../results/validation/topology/TOP-018-20260915-resolution-qualified-pair/reporting_repair.json
[video]: ../../../../results/validation/topology/TOP-018-20260915-two-star-video/two_star_S_vs_F.mp4
[video_provenance]: ../../../../results/validation/topology/TOP-018-20260915-two-star-video/README.md
