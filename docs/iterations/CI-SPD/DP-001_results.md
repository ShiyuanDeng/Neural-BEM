# DP-001: damping feedback and repeated-work repairs

Approved and completed 2026-10-05. [Pre-registration](DP-001_plan.md), [implementation and validation](DP-001_implementation.md), [complete receipts](../../../results/validation/cleaned_interfaces/DP-001/final_comparison.json).

E recovered **26/30** and F recovered **26/30** TG-002 cases. There were 0 recovery regressions and 0 new recoveries. Median paired successful-output speedup was **1.134×** (p10 1.101×; 26/26 faster).

| Audited output boundary | Frozen E | Fixed F |
|---|---:|---:|
| Recovered cases, summed seconds | 436.569 | 386.056 |
| Failed cases, summed seconds | 116.054 | 120.241 |
| All cases, summed seconds | 552.624 | 506.298 |
| Largest recovered RMS, mm | 0.188284 | 0.188331 |
| Largest recovered Hausdorff upper bound, mm | 0.664692 | 0.664758 |
| Largest recovered per-frequency residual | 0.00284194 | 0.00284342 |
| Minimum recorded damping | 1.04604e-14 | 1.05102e-06 |

The summed output boundary fell by 8.4%. These are sums of single-case measurements, not campaign elapsed time. Truth scoring is outside this boundary; interpreter import overhead is outside both arms, while initial CUDA startup and all numerical audits are included. The experiment used one worker, four frequency threads and single-thread BLAS. No warm-up was excluded.

## Failures and controller evidence

Failed cases and outcomes are retained in the complete comparison. The four screen failures stop at the unchanged numerical-resolution gate. The damping floor prevents the tiny schedule values, but it does not establish a resolution response or solve the difficult inverse cases. Aphex 13.3 advances farther with F; its error remains above the recovery gates, and its failed-run time increases.

| Failed case | E RMS mm / output s | F RMS mm / output s |
|---|---:|---:|
| aphex_twin__c0.5 | 4.3983 / 20.37 | 4.4751 / 21.68 |
| aphex_twin__c13.3 | 4.1524 / 42.04 | 2.5703 / 51.09 |
| aphex_twin__c4 | 1.6854 / 27.55 | 1.6855 / 24.34 |
| hook__c13.3 | 8.6575 / 26.09 | 8.6531 / 23.12 |

## Accounting and limits

F records the following disjoint wall components. Remaining setup/output is the difference from the measured audited-output boundary. Geometry and physics cumulative timers are nested and must not be added to this table.

| F wall component | Summed seconds |
|---|---:|
| initial_audit | 28.112 |
| fit_and_localization | 418.453 |
| early_audits | 36.607 |
| terminal_audits | 5.312 |
| remaining_setup_and_output | 17.814 |

This comparison qualifies the combined repairs; it does not isolate each cache, audit batch or damping change. Single executions do not establish timing confidence intervals or identical endpoint shape accuracy. All 30 pairs use the unchanged declared gates. Source/input/import checks and per-batch validation receipts passed. Earlier seals and source archives were preserved.

The agreement controller and audit batching remain explicit options; legacy defaults are unchanged. The report's next numerical research priority is accuracy-selected modal resolution with bounded promotion, followed by adaptive refinement qualification. Rigid translation remains conditional. Neither was silently included in this experiment; no far-start or case-8 rerun occurred.
