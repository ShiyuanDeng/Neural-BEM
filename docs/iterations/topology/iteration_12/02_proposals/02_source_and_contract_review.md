# TOP-019 source and contract review

**Later approval:** the user's 2026-09-15 “go” approved the conditional contract.
See the [execution plan](../03_plan.md) for current status. The pre-approval
review below remains the record of what was checked before that decision.

2026-09-15. Reviewer: Codex `/root`, also the proposal author. **Owner review
only; independent reviewer unassigned.** [Contract](01_capacity_qualified_merge_contract.md).
Approval remains **PROPOSED — NOT APPROVED FOR EXECUTION**; execution **NOT STARTED**.

## Evidence checked without numerical execution

Remote `refs/heads/feature/ordered-boundary-nystrom` and local HEAD both resolve
to `8cbf207cd50e87832f40b71a6dea3b75a4b3fe65`. The working tree was clean at
intake. Reviewed the latest roadmap, TOP-018 closeout, TOP-016 merge results,
TOP-017 projection and per-stage audit, and current source helpers.

Standard-library JSON/hash checks establish:

- The selected start exactly equals TOP-008 H/merge `final_state` and both
  TOP-016 merge stage-1 initial states. It has one ID, `t001.merge1`, at K=9.
- TOP-016 and TOP-017 merge training files are byte-identical, as are their
  original/evaluation files. The 0.5-GHz columns agree exactly, real and imaginary.
  There are 24 observation pairs; training has four frequencies and the
  original/evaluation file has three.
- TOP-017's scene specification equals frozen v1 as parsed JSON. Their file
  hashes differ because serialization differs; do not reject semantic equality
  or confuse it with byte identity.
- The saved K=17 witness is marked `evaluation_only=true`,
  `used_for_inverse=false`, numerically qualified at 128/256 and passes all
  original gates. Its state hash matches the contract. Its source figure is
  not an inverse endpoint.

| Input | File SHA-256 |
|---|---|
| TOP-016 `phase0/inputs/merge/state.json` | `72f01280d665bd0b50d569dd372d13469f010ddcb536fe978159969b4e675ca6` |
| TOP-017 `inputs/merge/observations.json` | `10069a80ed6a704998ccddb3034e1ed491da0b2b7a303a3896859626e459fc0f` |
| TOP-017 `inputs/merge/training_observations.json` | `a356db2dcedeb361d341b8718a2e516ee77d12e5fb6458915f5c56259f664645` |
| TOP-017 `phase_a/audit.json` | `2eb56f1133ca261432b25c5fcc26f8cfe533b43457ef86074372efaf9df6072f` |

These are file hashes, distinct from canonical state hashes in the contract.
No BIE solve, derivative probe, inverse, geometry experiment or unit test was
run during preparation. Numerical and geometric qualification remains pending.

## Material recommendations resolved

| Recommendation | Resolution |
|---|---|
| Test a representation capable of passing the merge gates | **Accept:** K=17 in both arms; recheck the fixed saved capacity witness at 256/512 in Phase A |
| Use the projection as an easy inverse start | **Reject:** initialize by zero-padding the original controller result; projection remains evaluation-only |
| Reuse the different S/F terminal states | **Reject:** both arms restart before stage 1 from the same original input |
| Reuse saved K=9 optimizer configuration verbatim | **Reject:** source `_optimizer_config` derives per-parameter steps and `max_parameters`; K=17 needs 70 entries rather than 38 and raises the parameter limit from 64 to 70 |
| Reuse 128/256 because the historical projection passed | **Accept with amendment:** retain that historical qualification; deliberately use shared 256/512 for the new pair, with a binding audit and no adaptive fallback |
| Give added frequencies real optimization exposure | **Accept:** all four stages, endpoint-inclusive quotas, complete-model check and typed hard stops from TOP-017 |
| Rerun information screens or build new optimizer machinery | **Defer:** only a measured TOP-019 obstruction could motivate a separately scoped diagnostic; existing adapters support this comparison |
| Integrate fresh two-star recovery and then run all twelve scenes | **Defer:** roadmap steps 2/3 depend on this result and separate contracts |

Source inspection confirms `zero_padded_component` extends each coefficient
array with zeros. The chart stores `4K+2` real parameters and the reduced basis
has `2K-1` rows at K>2; K=17 therefore gives 70/33. Existing `run_schedule`
accepts an explicit stage-1–4 plan; `fit_stage` reserves `70*m+12` for a first
model/step/endpoint opportunity. Every proposed quota exceeds this bound.
The audit's nominal 36+68=104 calls fits its 256 ceiling, and
256+2*(1000+1250+1750+4000)=16,256. Sequential wall ceilings sum to 15,300 s.
These are static design checks, not evidence that the numerical gates pass.

## Verdict

The contract is concrete enough for a named execution decision. It isolates
the new S/F comparison, protects the truth boundary, preserves the historical
regression and can stop before inversion. No scientific result or independent
review is claimed. On approval, consolidate this contract into iteration 12's
`03_plan.md`, record the user's actual approval, implement within scope, perform
the pre-dispatch review/tests and execute its conditional phases. No broader
experiment follows automatically.
