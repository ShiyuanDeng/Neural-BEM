# Field-defined topology events — side quest

**Low-expectation side quest.** Opened and closed 2026-09-16. Exploratory, off
the critical path of the [topology track](../topology/README.md). It kept its
own `FDE-` numbering, declared no contract, dispatched no expensive inversion,
created no branch or worktree, and **modified no production code**.

## Question

Could the 2024 Gaussian-splatting density-control literature (3DGS-MCMC
state-preserving relocation, Revising-Densification opacity correction, AbsGS
gradient collision) plus classical topological-derivative theory replace the
template-grid heuristics in `generate_topology_candidates`
(`solvers/sdf_inverse/topology_controller.py:403`)?

## Outcome — every borrowed mechanism failed; the diagnostic found two real defects

| Mechanism | Verdict |
|---|---|
| M1 — non-cancelling score (AbsGS) | **refuted.** Median corridor cancellation ratio 0.8446, not < 0.2; size correlation **+0.132**, opposite to prediction |
| M4 — theta trigger (Amstutz–Andrä) | **refuted.** Pass/fail ranges overlap; Spearman(theta, loss) −0.8392 |
| M2 / M3 — presence variable, relocation | **blocked.** Contrast is a global material property, not per-component |
| P5 — analytic Jacobian affordability | **holds.** One Jacobian = 1 factorization + 12 tangent solves, 0.67 s |

**The findings that justified the exercise came from the diagnostic, not the
borrowed mechanisms**, and neither is about scoring:

1. **`split_seed_radius_factors` defaults to `(1.,)`**, so the only surviving
   split variant is a pair of equal-area circles that **intersect across the
   cut** and cannot be evaluated. Across all 22 events, **238 of 325 split
   candidates (73.2%) are unevaluable**, and at **9 of 22 events every** split
   candidate is lost before scoring. A config-only change to `(1., .7, .5)`
   takes that to 0 of 22 — and changes no raw winner. The failure is silent in
   the logs.
2. **The contour fit — the only variant that can express a lobed split child —
   fails 76.4% of attempts** (321 of 420), always on the polar-angle gauge.
   81.3% of split pieces are not star-shaped about their centroid and **0 of
   461** survive an ungauged fit, because both charts are polar-angle
   parameterizations. This is the binding constraint and it is a representation
   limit, not a tolerance.

Full numbers, including a withdrawn earlier claim and how it was caught:
[iteration 01 results](iteration_01/01_results.md).

## State

| Item | Current state |
|---|---|
| Stage | **CLOSED** — FDE-001 executed; M1, theta refuted; M2/M3 blocked |
| Plan | [FDE-001](iteration_01/02_proposals/FDE-001_field_defined_events.md) |
| Results | [iteration 01](iteration_01/01_results.md) |
| Production code changed | none |
| Handoff | The representation limit belongs to the topology track's own research question; no successor is declared here |
| Git scope | `feature/ordered-boundary-nystrom`, no new branch or worktree |
