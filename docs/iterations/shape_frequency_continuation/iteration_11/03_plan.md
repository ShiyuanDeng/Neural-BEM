# SC-029 — inverse-space qualification and the frozen strategy comparison

2026-09-24. Owner: Codex. Independent reviewer: unassigned.

**Approval status: APPROVED** under the current user request to analyse,
propose, test and document the atlas strategies. **Execution status:
COMPLETE**: all 36 endpoints recorded, including five hard stops.
The [closeout](../iteration_12/01_results.md) reports all frozen comparisons.
The original prospective plan is preserved in [the frozen snapshot](../../../../results/validation/shape_continuation/SC-029-atlas-strategies/frozen_plan.txt),
matching its manifest hash. Existing branch; commit/push milestones.

## Contract

Inherit [SC-028's entire recovery comparison](../iteration_10/03_plan.md),
including both prefixes, all three suffix endpoints, all six development
cases, the exact controls and the 0.8 geometric-mean / 1.5 worst-ratio
decision rule with a 0.01-mm RMS floor. The cases, starts, oracle data,
N=512/1024, K=192, refit tolerance, step controls, weights, damping,
iterations, stage quotas, 8012/15512-unit caps and 3600-second path limits
are unchanged. No new strategy or parameter search is introduced.

**The one difference:** numerical qualification covers all M<=19 update
coordinates, with the same <=1e-6 field and maximum column-relative
Jacobian thresholds. This includes every band either arm will use.
The P=48 atlas remains outside the qualified claim, with its original
failure preserved. Do not call SC-028 a pass.

Reuse the twelve numerical comparisons from the separately declared
active-band diagnostic, since their actual matrices, resolutions and
endpoints are exactly those needed here. Pin the diagnostic, original
field qualification, six reference endpoints, source files and inputs by
hash. No additional solves are needed to evaluate this restricted gate.
The wrong-circle baseline replay and the targeted harness tests remain
mandatory before full dispatch. Each accepted fitting step continues to
use the existing N/2N field acceptance gate. The diagnostic is a
representative preflight, not a Jacobian proof for every future iterate.

## Execution and artifacts

Use the unchanged SC-028 harness. A small wrapper in the fresh
`results/validation/shape_continuation/SC-029-atlas-strategies/` bundle
records this contract, verifies the reused evidence, and constructs its
qualification record. The fitting function receives neither truth nor
evaluation data.

Maximum 12 prefixes and 24 suffixes, 36 endpoints, <=2 h recovery wall
time with at most 12 single-thread workers. Prefix execution has a
2700-second process ceiling; suffix execution has a 4500-second ceiling.
Checkpoint failures and report incomplete paths explicitly. Each suffix
counts its parent work, but its shared prefix is executed only once.
Endpoint evaluation is <=684 separate field solves as in SC-028.

Record all raw histories, parent hashes, stops, errors, work and common
catalog predictions. Report failures alongside successes; no retrospective
case exclusions. Results open iteration 12 and decide only whether a
strategy merits fresh-case qualification. All six cases remain development
data. SC-027 and production-default changes remain outside this test.
