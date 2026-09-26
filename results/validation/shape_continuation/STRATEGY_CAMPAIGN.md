# Strategy campaign — status and solve accounting

**RUNNING — incomplete comparisons are provisional.**

| Study | Terminal paths | Qualified scored paths | Fitting + diagnostics, unique | Endpoint audits |
|---|---:|---:|---:|---:|
| [SC-042-state-strategies](SC-042-state-strategies/README.md) | 24/24 | 21 | 19874 | 2663 |
| [SC-043-prospective-band](SC-043-prospective-band/README.md) | 1/18 | 1 | 114 | 114 |
| [SC-044-noisy-fresh-cases](SC-044-noisy-fresh-cases/README.md) | 18/18 | 16 | 10924 | 2169 |
| [SC-045 independent timeout qualifications](SC-045-timeout-qualification/README.md) | 5/5 audits | 4 | 0 | 456 |
| [SC-046 lost-result recovery](SC-046-lost-audit-recovery/README.md) | 1/1 audit | 1 | 0 | 114 |

Data generation: 76 fields. Total recorded work for terminal records: 36504 units.
The lost SC-045 ledger contributes up to 130 additional unrecorded units. Its stored zero denotes missing accounting, not free computation.
Work in running paths is omitted from this snapshot. Interrupted-call costs may be only partially recorded.
SC-044 includes six shared prefix paths; each method is charged its full prefix in complete-path comparisons.
Field and reciprocal units are a declared accounting convention, not identical floating-point cost. Numerical grids vary by case; host timing is uncontrolled.

[Reviewer constraints on novelty](../../../docs/iterations/shape_frequency_continuation/iteration_24/02_claims_review.md).
[Conditions for a useful next iteration](../../../docs/iterations/shape_frequency_continuation/iteration_24/03_next_decisions.md).
[Environment](strategy_campaign_environment.json). [Machine-readable summary](strategy_campaign_summary.json).

Post-fit checks: [doubled metric sampling](strategy_metric_refinement.json), [fresh-case local errors and intrinsic curvature](strategy_feature_errors.json), [development-case regularity](SC-042-state-strategies/regularity.json). These descriptive diagnostics do not replace the frozen gates.

## Retained stopped or unqualified paths

- [SC-042-state-strategies/runs/circle_to_c/boundary/result.json](SC-042-state-strategies/runs/circle_to_c/boundary/result.json): COMPLETED_SCHEDULE; original endpoint audit False. Independent [SC-045 qualification](SC-045-timeout-qualification/audits/3.json): True (original flag unchanged).
- [SC-042-state-strategies/runs/kite/boundary/result.json](SC-042-state-strategies/runs/kite/boundary/result.json): COMPLETED_SCHEDULE; original endpoint audit False. Independent [SC-045 qualification](SC-045-timeout-qualification/audits/1.json): False (original flag unchanged). Separate [SC-046 lost-result recovery](SC-046-lost-audit-recovery/result.json): True.
- [SC-042-state-strategies/runs/kite/cap/result.json](SC-042-state-strategies/runs/kite/cap/result.json): COMPLETED_SCHEDULE; original endpoint audit False. Independent [SC-045 qualification](SC-045-timeout-qualification/audits/2.json): True (original flag unchanged).
- [SC-042-state-strategies/runs/kite/none/result.json](SC-042-state-strategies/runs/kite/none/result.json): NUMERICAL_FAILURE; original endpoint audit True.
- [SC-044-noisy-fresh-cases/runs/asymmetric_lobes/clean/cap/result.json](SC-044-noisy-fresh-cases/runs/asymmetric_lobes/clean/cap/result.json): COMPLETED_SCHEDULE; original endpoint audit False. Independent [SC-045 qualification](SC-045-timeout-qualification/audits/4.json): True (original flag unchanged).
- [SC-044-noisy-fresh-cases/runs/asymmetric_lobes/noise_seed_0/boundary/result.json](SC-044-noisy-fresh-cases/runs/asymmetric_lobes/noise_seed_0/boundary/result.json): DISCREPANCY_REACHED; original endpoint audit False. Independent [SC-045 qualification](SC-045-timeout-qualification/audits/5.json): True (original flag unchanged).
- [SC-044-noisy-fresh-cases/runs/deep_c/noise_seed_0/none/result.json](SC-044-noisy-fresh-cases/runs/deep_c/noise_seed_0/none/result.json): NUMERICAL_FAILURE; original endpoint audit True.
