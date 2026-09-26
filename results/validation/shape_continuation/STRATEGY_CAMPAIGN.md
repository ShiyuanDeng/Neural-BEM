# Strategy campaign — status and solve accounting

**RUNNING — incomplete comparisons are provisional.**

| Study | Terminal paths | Qualified scored paths | Fitting + diagnostics, unique | Endpoint audits |
|---|---:|---:|---:|---:|
| [SC-042-state-strategies](SC-042-state-strategies/README.md) | 24/24 | 21 | 19874 | 2663 |
| [SC-043-prospective-band](SC-043-prospective-band/README.md) | 0/18 | 0 | 0 | 0 |
| [SC-044-noisy-fresh-cases](SC-044-noisy-fresh-cases/README.md) | 11/18 | 9 | 7390 | 1371 |
| [SC-045 independent timeout qualifications](SC-045-timeout-qualification/README.md) | 0/5 audits | 0 | 0 | 0 |

Data generation: 76 fields. Total recorded work for terminal records: 31374 units.
Work in running paths is omitted from this snapshot. Interrupted-call costs may be only partially recorded.
SC-044 includes six shared prefix paths; each method is charged its full prefix in complete-path comparisons.
Field and reciprocal units are a declared accounting convention, not identical floating-point cost. Numerical grids vary by case; host timing is uncontrolled.

[Reviewer constraints on novelty](../../../docs/iterations/shape_frequency_continuation/iteration_24/02_claims_review.md).
[Conditions for a useful next iteration](../../../docs/iterations/shape_frequency_continuation/iteration_24/03_next_decisions.md).
[Environment](strategy_campaign_environment.json). [Machine-readable summary](strategy_campaign_summary.json).

Post-fit checks: [doubled metric sampling](strategy_metric_refinement.json), [fresh-case local errors and intrinsic curvature](strategy_feature_errors.json), [development-case regularity](SC-042-state-strategies/regularity.json). These descriptive diagnostics do not replace the frozen gates.

## Retained stopped or unqualified paths

- [SC-042-state-strategies/runs/circle_to_c/boundary/result.json](SC-042-state-strategies/runs/circle_to_c/boundary/result.json): COMPLETED_SCHEDULE; original endpoint audit False.
- [SC-042-state-strategies/runs/kite/boundary/result.json](SC-042-state-strategies/runs/kite/boundary/result.json): COMPLETED_SCHEDULE; original endpoint audit False.
- [SC-042-state-strategies/runs/kite/cap/result.json](SC-042-state-strategies/runs/kite/cap/result.json): COMPLETED_SCHEDULE; original endpoint audit False.
- [SC-042-state-strategies/runs/kite/none/result.json](SC-042-state-strategies/runs/kite/none/result.json): NUMERICAL_FAILURE; original endpoint audit True.
- [SC-044-noisy-fresh-cases/runs/asymmetric_lobes/clean/cap/result.json](SC-044-noisy-fresh-cases/runs/asymmetric_lobes/clean/cap/result.json): COMPLETED_SCHEDULE; original endpoint audit False.
- [SC-044-noisy-fresh-cases/runs/asymmetric_lobes/noise_seed_0/boundary/result.json](SC-044-noisy-fresh-cases/runs/asymmetric_lobes/noise_seed_0/boundary/result.json): DISCREPANCY_REACHED; original endpoint audit False.
