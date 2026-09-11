# TOP-007 — implementation-owner review

Author/reviewer: Claude, also the proposal author. This is a self-review before
execution; independent scientific review remains **unassigned**.

| Recommendation | Decision and reason |
|---|---|
| Enforce refined admissibility inside the fixed-topology optimizer | Accept. The measured cause is a feasible set that differs between the resolution the optimizer searches in and the resolution the controller evaluates at. Catching the exception later would return a state the solver has already refused. |
| Check geometry only, not a refined objective | Accept. The adapter's curve/topology/clearance checks are what raised; they need a boundary, not a solve. A refined objective per trial would roughly double optimizer cost to answer a question no physics is needed for. |
| Keep it opt-in, default off | Accept. Every recorded bundle, replay study and test keeps its meaning, and the reference arm stays exactly what TOP-006 measured. Whether it becomes the default is decided by this experiment's evidence, not by this review. |
| Replace the uncaught `refined_base` exception with a rollback and a stop reason | Accept, **guard-only**. Making the unguarded path return instead of raising would silently change arm A's recorded outcome from `exception` to a completed failure and destroy the paired reproduction check. |
| Compare A against A+guard, not F against F+guard | Accept. One mechanism at a time. `include_simplest_candidate` is orthogonal and both policies failed these scenes identically; combining them is a later question, not this one. |
| Relax the 10-mm separation floor so the state becomes admissible | Reject. The 64/128/256-node clearances converge from above to roughly 9.96 mm, so the true geometry really is inside the floor. Loosening it would buy passes by disabling a quadrature check. |
| Add a safety margin above the floor so the optimizer stops short of it | Reject for now. It changes the admissible set beyond what the solver requires and adds a tuned constant to the comparison. Resolve through the recorded per-run guard-rejection and clearance diagnostics: if guarded runs sit exactly on the refined floor and still misbehave, a margin becomes a separate contract. |
| Pre-screen candidate states geometrically before their production solve | Defer. It would change candidate-level solve counts and confound the cost comparison this experiment reports. The existing acceptance-time check already rejects refined-inadmissible candidates. |
| Extend the benchmark runner to more than two arms | Accept, as harness only. Scenes, data, acquisition, budgets and gates stay frozen; arm selection becomes explicit and is recorded in the run manifest. The default arm pair is unchanged. |
| Fix shape capacity in the same experiment | Defer to TOP-008. Births are circles and the optimizer cannot change a component's bandwidth; that is a second mechanism and it depends on runs surviving long enough to matter. |
| Branch per experiment ID | Continue on `feature/ordered-boundary-nystrom`, following the same session direction under which TOP-005 was merged and TOP-006 ran. No concurrent implementation track exists. |

The user's 2026-09-11 direction to take Track A as far as possible, and the
same day's instruction to continue from the latest fixes, authorize
implementation and runs for TOP-007. No additional exact-ID phrase is needed
under the session instructions. TOP-008 stays proposed and unapproved.
