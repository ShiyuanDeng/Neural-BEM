# TOP-006 — implementation-owner review

Author/reviewer: Codex, also the proposal author. This is a self-review before
execution; independent scientific review remains **unassigned**.

| Recommendation | Decision and reason |
|---|---|
| Distant large-circle ellipse/star case | Accept. Use a 75-mm-radius circle at (0.40, 0.57), ellipse at (0.55, 0.43), star at (0.61, 0.53). Verify non-overlap and inspection-domain inclusion before solving. |
| Broader scenes | Accept twelve total, including the five unchanged controls. Separate shape complexity from initialization using central/enclosing/empty starts and a distant circle-only control. |
| Current-code comparison | Accept paired A/F with identical source, data, initial states and full controller budgets. No hand-picked event/count or mode schedule. |
| Success measures | Accept separate count, geometry, overlap, training and held-out checks. A controller `recovered` stop alone is insufficient. |
| Oracle | Accept independent cylindrical harmonics for all-circle targets; analytic boundaries with 256-node Kress for other shapes, checked at 512 nodes. The latter is independent geometry/resolution, not an independent solver. |
| Persistent benchmark | Accept immutable v1 specification, shared saved observations, per-scene reports and future-use instructions. |
| Fix failures immediately | Defer to iteration 04 after observing the frozen results; changing the controller during measurement would destroy the baseline. |
| Branch per ID | Use the existing `feature/ordered-boundary-nystrom` checkout in light of the user's preceding merge/branch-cleanup direction. No concurrent implementation track is running. |

The current user request authorizes implementation and runs. No additional
exact-ID permission phrase is needed under the session instructions.
