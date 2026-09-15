# TOP-019 owner closeout review

2026-09-15. Codex `/root`, implementation owner and reviewer. No independent
review is claimed. **Execution COMPLETE; BOTH_ARMS_RECOVERED.**

`approved_plan.md` is the immutable pre-dispatch copy and retains relative
links from its original directory. The [plan at its source location](../../../../docs/iterations/topology/iteration_12/03_plan.md)
provides working navigation and the later execution-status closeout.

## Contract reconciliation

| Requirement | Evidence / decision |
|---|---|
| Named approval | User's “go” to the TOP-019 request, recorded in `approved_plan.md` and `contract.json` |
| Common start without truth assistance | `reuse.json`, frozen original/padded states; exact old coefficient preservation and zero added modes; original/padded predictions identical at 256 and 512 |
| Adequate capacity and numerical resolution | All three Phase-A states qualify; fixed projection passes <=0.1-mm capacity and original recovery gates; both fixed derivative directions pass |
| Truth/evaluation boundary | Optimizer interface remains training-only; witness retained only in audit/scoring; no new oracle data or truth-based stage selection |
| Matched arms | Identical start; complete stage-1 state/loss histories and terminal hashes match; K=17, same 256/512 nodes and optimizer settings |
| Intervention exposure | S fits only 0.5 GHz; F reaches all cumulative stages; each stage has a completed usable Jacobian/model |
| Final recovery | Both prescribed stage-4 endpoints pass every original gate and numerical check |
| Physical work | 104 audit + 1,284 S + 4,844 F = 6,232 attempted/completed, zero failed; every stage and trial stays inside its solve quota |
| Time and process outcomes | Audit 48.580 s, S 267.339 s, F 975.001 s active time; campaign 1,292.738 s; both worker exits 0; sequential single-thread execution |
| Numerical source | 197 file hashes unchanged; base `8cbf207` plus experiment-owned source snapshots in `measured_sources/`; no shared solver/default edits |
| Verification | 84 source-bound mocked/geometry tests pass; JSON-only replay independently checks complex prediction errors/objectives, state/gradient identities, accepted gains and work |
| Visual QA | `endpoints.svg` rendered and inspected: common/S/F labels, target, axes and contours are legible and correctly associated |

S stage 1 uses 978/1,000 solves; its later stages use 148/1,250, 79/1,750 and
79/4,000. F uses 978/1,000, 1,116/1,250, 1,650/1,750 and 1,100/4,000. All these
counts include the 12-solve endpoint score. Budgets are ceilings, not targets.

Both final stages meet the configured gradient test. Earlier quota endpoints
retain unconfirmed convergence and missing current gradients; neither the
terminal score nor a later gradient changes those historical classifications.
No physical solve, derivative or inverse was run merely to fill reporting gaps.

## Scientific decision

Accept the **new matched protocol's merge recovery**. S passes at 0.0860067 mm
and 0.0116406 worst development-evaluation error. F passes at 0.0214283 mm and
0.00229358, buying 4.01× boundary and 5.08× prediction accuracy for 3.77× work.
There is no binary recovery advantage for F on this control. S's slightly
higher sampled IoU and F's stage-4 increases in some lower-frequency errors
remain in the scorecard; every required recovery gate nevertheless passes.

Keep F as the development candidate for a separately scoped fresh two-star
integration check, alongside the successful lower-cost S merge control. This
decision uses the earlier central/two-star evidence as well as this control;
it does not claim F wins every metric or scene. No universal K=17 policy,
automatic merge event, fresh two-star integration or twelve-scene qualification
was measured here. Preserve TOP-016's adverse K=9 result and all prior successes.

No successor or production promotion is released. Iteration 13 records the
closeout and the single next scoping decision.
