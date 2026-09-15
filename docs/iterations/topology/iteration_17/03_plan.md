# TOP-025 — current pipeline across all twelve scenes, with videos

- **Approval:** APPROVED by the user's request to show how the latest code performs
  in all cases, organized with videos of successes and failures.
- **Execution:** COMPLETE. All 86 source-bound pre-dispatch tests pass,
  including an actual video-encoding smoke check; tests make no physical solves.
- **Owner/reviewer:** Codex `/root`; owner review, no independent review claimed.
- **Workspace:** existing checkout and `feature/ordered-boundary-nystrom` branch.

## Question and meaning of latest

Measure the current integrated automatic H → cumulative-frequency F pipeline on
all twelve immutable v1 scenes, from each original initialization. Freeze the
current source and original data. This descriptive evaluation is explicitly
requested despite TOP-024's negative result; it does not claim that TOP-021's
conditional matched-comparison gate passed and leaves that experiment unchanged.

Use existing H at 64/128 nodes, then the prepared target-free capacity rule:
K17 for one returned component, K9 per component otherwise, by exact zero padding.
Use the unchanged feasible FD/LM algorithm and cumulative .5/.75/1/1.25-GHz
training at 256/512. No per-scene protocol choice, archived optimized start,
supplied true count or added damping reset. TOP-022's direct-entry and TOP-024's
terminal reset remain diagnostics; neither was adopted as the integrated policy.

This measures the current candidate across the matrix. A single candidate run
does not establish a causal improvement over historical policies or a matched
runtime advantage. Retain all failures and preserve previous result bundles.

## Bounds and gates

- All twelve original scenes, starting coefficients, acquisition, material,
  original observations and recovery gates are unchanged.
- Reuse verified expanded training observations for central/two-star/merge.
  Generate only missing added-frequency columns, 256 with 512 qualification;
  oracle ceiling 72 calls / 300 s. Any oracle failure blocks numerical dispatch.
- Per scene: H 4000 attempts / 600 s; F stage quotas 1000/1250/1750/4000,
  including each final score, plus 12 initial score calls: 8012 / 7200 s.
- At most four isolated BLAS-1 numerical workers. External scene timeout 7900 s
  plus 10-s termination grace; campaign watchdog 7 hours. Maximum new calls
  **144216 = 72 + 12 × (4000 + 8012)**. No rerun, adaptive extension or reset.
- Failed scenes do not stop remaining scenes. Record partial work as a lower
  bound after outer timeouts. Unsafe topology or numerical states stop that scene.
- Success requires the original count, <=1-mm boundary error, >=0.90 IoU,
  <=0.003 original training error, <=0.05 development error, valid topology
  event margins and all numerical checks. The prescribed final endpoint is used.

## Implementation and deliverables

Add `experiments/top025/` orchestration, saved-artifact reporting and rendering,
reusing TOP-021's data/capacity helpers, TOP-017's ledger/schedule, TOP-020's
scorer and existing saved-array verification. No shared solver/default edit.
Tests cover complete scene coverage, fresh starts, capacity, phase isolation,
budgets, failure preservation, zero-solve reporting and accepted-frame provenance.

Provide a results index with all twelve outcomes and failure reasons, per-scene
MP4s, final overlays, an overview MP4 and machine-readable scores/work. Videos
show actual saved accepted states with phases labelled, no coefficient
interpolation, and no claim that playback time equals solve time. For failures,
show the last retained state and the recorded obstruction. Truth is for scoring
and visual display only. Visually verify the contact sheet and representative
video frames, and probe every MP4 for successful encoding.

Results open iteration 18. This suite ends with an honest inventory of the
current method; no corrective redesign or successor is included.

## Closeout

[TOP-025-20260915-210356-all-scenes-current](../../../../results/validation/topology/TOP-025-20260915-210356-all-scenes-current/README.md):
7/12 scenes pass. All twelve scenes were attempted; videos and verification
are complete. Results open [iteration 18](../iteration_18/01_results.md).
