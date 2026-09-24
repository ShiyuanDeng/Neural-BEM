# SC-030 first pass (one run per arm; repetition pending)

These are preliminary single-run timings, not the final repeated comparison.

| Case | Arm | Schedule status / reason | RMS mm | Work units | Inverse seconds |
|---|---|---|---:|---:|---:|
| Circle | SPD-008 | NUMERICAL_FAILURE | 7.492951 | 134 | 174.9 |
| Circle | Hybrid, cache off | COMPLETED_SCHEDULE | 0.002594 | 87 | 98.1 |
| Circle | Hybrid, cache on | COMPLETED_SCHEDULE | 0.002594 | 87 | 86.7 |
| Star | SPD-008 | UNRESOLVED_DERIVATIVE | 7.342088 | 607 | 361.5 |
| Star | Hybrid, cache off | COMPLETED_SCHEDULE | 0.522234 | 139 | 159.1 |
| Star | Hybrid, cache on | COMPLETED_SCHEDULE | 0.522234 | 139 | 141.2 |
| C | SPD-008 | COMPLETED_SCHEDULE | 18.964258 | 599 | 294.6 |
| C | Hybrid, cache off | COMPLETED_SCHEDULE | 3.201993 | 651 | 743.4 |
| C | Hybrid, cache on | COMPLETED_SCHEDULE | 3.201993 | 651 | 656.4 |
| Kite | SPD-008 | COMPLETED_SCHEDULE | 21.318654 | 355 | 179.2 |
| Kite | Hybrid, cache off | COMPLETED_SCHEDULE | 2.982577 | 411 | 370.2 |
| Kite | Hybrid, cache on | COMPLETED_SCHEDULE | 2.982577 | 411 | 316.4 |
| Peanut | SPD-008 | UNRESOLVED_DERIVATIVE | 13.809034 | 193 | 162.6 |
| Peanut | Hybrid, cache off | COMPLETED_SCHEDULE | 2.944275 | 528 | 557.4 |
| Peanut | Hybrid, cache on | COMPLETED_SCHEDULE | 2.944275 | 528 | 486.4 |
| Hook | SPD-008 | COMPLETED_SCHEDULE | 12.642719 | 357 | 157.1 |
| Hook | Hybrid, cache off | COMPLETED_SCHEDULE | 0.525391 | 195 | 197.6 |
| Hook | Hybrid, cache on | COMPLETED_SCHEDULE | 0.525391 | 195 | 171.5 |

Completing the four-stage schedule is not a recovery certificate. Errors and
stop reasons remain separate. Both methods use the common wrong circle, data,
512/1024 nodes and budgets, with the native algorithm differences documented
in [the implementation review](implementation_review.md).

All cache pairs exact: **True**.
