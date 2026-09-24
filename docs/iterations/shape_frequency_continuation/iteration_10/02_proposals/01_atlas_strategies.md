# Atlas strategies — what to test first

2026-09-24. Owner: Codex. Based on the
[SC-026 interpretation](../01_results.md), before new recovery outcomes.

| Strategy | Falsifiable prediction | Decision |
|---|---|---|
| S1: start at M=2, then resume the existing ladder | Preventing one early harmonic reduces damaging roughening and improves endpoint geometry under the same budget. | Test in SC-028. Changes one stage's band; uses the existing optimizer. |
| S2: continue the cumulative ladder through 1.5, 1.75, 2.0, 2.25 and 2.5 GHz | New data improves geometry more than additional optimization with the old data and the same larger bands. | Test in SC-028, on both S1 and ordinary starts. |
| A small physical step cap in stage 1 | Avoiding large early moves prevents roughening. | Defer. At 0.3 mm per move, 22 iterations allow only 6.6 mm of total maximum motion; an unchanged iteration budget can confound protection with underfitting. The existing physical control also replaces coordinate clipping. |
| SC-027 Sobolev metric | Explicitly penalizing high-order motion reduces roughening across stages. | Defer this more invasive mechanism until the simpler interventions are measured. Its scaling and new-case validation remain open. |
| Reject very weak singular directions | Saves work without worsening recovery. | Defer. Current correlations are not an equal-quality efficiency test, and a noise threshold has not been calibrated. |

S1 is a test of a complete band policy, not proof that harmonic 3 always
causes failure. A smaller initial band can postpone useful shape updates;
later stages may still roughen. S2 tests an acquisition/continuation protocol,
not an improvement at identical data access. A frozen-data extension control
isolates the added frequencies from extra iterations and wider update bands.

The two factors are crossed. Reusing each completed four-stage prefix for
both suffixes gives identical starting coefficients and sunk work. All
six cases run, including the easy circle and known difficult C/kite/peanut.
There is no outcome-based case selection, hyperparameter search or choice
of best iterate. Final results are compared case by case before aggregation.

An improvement here warrants fresh-case qualification; it does not promote
either strategy to a default. Negative and budget-limited outcomes stay in
the same report.
