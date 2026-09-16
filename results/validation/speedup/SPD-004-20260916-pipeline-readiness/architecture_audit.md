# What the full pipeline is spending effort on

This is a retrospective audit of the frozen TOP-025 twelve-scene suite, using
saved training predictions for decisions and independent endpoint scores only
for assessment. It performs no new physical solves. The separate SPD-004
fresh measurements compare the current fast CPU pipeline with a conservative
training-only readiness check.

Sources and consumed-file hashes: [audit.json](archive/audit.json),
[audit.csv](archive/audit.csv), and
[architecture_findings.json](archive/architecture_findings.json).

## The twelve scenes need different responses

| Situation at the topology-to-continuation handoff | Scenes | What it suggests |
|---|---|---|
| Conservative training readiness passes; independent recovery also passes | repeated-birth, death, split, far-two-circles | Check completion before launching continuation |
| Conservative readiness fails, but independent recovery already passes | mixed | The first readiness rule leaves some possible savings; retain fallback rather than tune on evaluation data |
| Handoff fails independent recovery, then continuation recovers | merge, central-ellipse-star | Keep real shape/frequency refinement available |
| Handoff fails independent recovery and continuation still fails | far-two-stars | Diagnose search/model/information choices; cheaper steps alone do not establish recovery |
| Returned topology cannot pass the finer-grid handoff | far-ellipse-star, empty-ellipse-star | Enforce future numerical admissibility earlier and study whether it changes the topology route |
| Topology hits its wall limit before handoff | enclosing-ellipse-star, far-three-shapes | Examine topology growth and allocation of fitting effort; the readiness screen cannot help a run that never reaches it |

Four of eight available handoffs pass the conservative screen, with no false
early stops in this archive. Four other scenes have no usable handoff and are
not included in that denominator. This is development evidence on noiseless
synthetic scenes, not a general guarantee from training residual to geometry.

## Automatic model expansion creates work before asking whether it is needed

The existing worker already evaluates the handoff across the training and
evaluation bands at both numerical resolutions. Its continuation protocol then
requires a complete usable optimization model at every prescribed stage:
`run_schedule` rejects missing `effective_training_exposure`. This is useful
for a research comparison of exposure schedules, but it also forces Jacobian
work when the reconstruction already satisfies the task's fit requirements.
SPD-004 changes that completion contract explicitly and records skipped
exposure and unmeasured stationarity honestly.

| Scene | Topology directions | Padded continuation directions | Accepted continuation steps |
|---|---:|---:|---|
| repeated-birth | 9 | 51 | 0, 0, 0, 0 |
| death | 6 | 34 | 0, 0, 0, 0 |
| split | 6 | 34 | 0, 0, 0, 0 |
| far-two-circles | 6 | 34 | 1, 0, 1, 0 |
| merge | 17 | 33 | 14, 8, 8, 3 |
| central-ellipse-star | 20 | 34 | 13, 8, 6, 3 |

These are accessible gauge directions, not raw Cartesian coefficient counts.
Padding is geometrically exact; its cost appears when the optimizer builds and
fits the expanded model. Extra capacity is useful for some scenes, but making
it mandatory before checking readiness wastes model work on others. The first
experiment retains the existing padded state for comparability and bypasses
the unnecessary optimizer; it does not implement adaptive bandwidth selection.

## A single low-frequency success flag is insufficient

The merge handoff's 0.5 GHz relative error is `7.879e-5`, below the original
`0.003` training gate. Its highest added training-frequency error is about
`0.0410`; its independent evaluation error is `0.0940`, which fails the
`0.05` gate. It needs continuation even though the topology controller labels
its low-frequency result recovered.

This supports a full-training readiness check, rather than reusing the
controller's existing success flag. The implemented decision never sees the
independent evaluation values quoted here.

## Expensive unsuccessful candidate refinement deserves a different decision

In the archived central ellipse/star case, the final topology pass constructs
46 candidates, refines 3 and accepts none. Its candidate refinements consume
523 full frequency systems. In the far-two-star case, the final pass considers
74 candidates, refines 4 and accepts none, consuming 430 systems in refinement.
These are historical FD counts, not current fast-runtime shares.

That does not prove the candidates could have been rejected safely without
refinement. It identifies a bounded question for an adaptive controller:
after a small amount of unsuccessful fitting, is the next useful action
another candidate, a different training frequency, or richer shape freedom?
Compare those alternatives at the same final quality, with failed attempts
charged. A blanket smaller candidate budget can remove the eventual winner.

## Finer-grid feasibility belongs in the earlier search

Far and empty ellipse/star runs reach a topology endpoint and then stop with
`automatic endpoint infeasible at continuation nodes`. The baseline has spent
2,530 and 803 physical systems respectively by those stops. Earlier geometric
checking could prevent accepting a state that the next phase cannot use.
This is a proposed change to the search path: merely rejecting the same failure
sooner is not a recovered inverse or a recovery speedup.

The saved [handoff geometry checks](../../topology/TOP-025-20260915-210356-all-scenes-current/qa/handoff_geometry.json)
identify the mismatch precisely: both states pass at 64/128 nodes and fail at
256/512. Their 512-node minimum component gaps are approximately 0.0099889 m,
just below the required 0.01 m; component radius floors all pass. Checking this
future-resolution clearance during topology acceptance is a concrete next
intervention. It must be assessed for recovered geometry, since it changes
which candidate states can enter subsequent fitting.

## Revised architectural order

1. Check adequate full-training fit and final numerical accuracy before
   mandatory continuation; independently verify the returned reconstruction.
2. Carry future numerical requirements into topology acceptance, and use
   evidence of poor progress to choose between topology, data and shape detail.
3. Allocate shape capacity per component instead of using component count alone
   to select a uniform large model.
4. Test inexpensive candidate screening on passes with costly unsuccessful
   refinements, retaining enough alternatives to measure ranking mistakes.
5. Reprofile the remaining workload, then select CPU/GPU and derivative
   implementation improvements for it.

Only the first intervention is implemented in the bounded SPD-004 experiment.
The other items are evidence-backed investigation priorities, not measured
solutions to the hard-scene failures.

The isolated prototype recomputes eight training systems before falling back
to the original continuation, whose initial scorer then repeats that training
work. A later integration could share the exact initial training predictions
between the gate and scorer, preserving evaluation isolation. That additional
reuse is not implemented or included as a measured saving here.
