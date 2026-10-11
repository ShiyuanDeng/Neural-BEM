# CG-003 — measured loop-search results

**NO_CONFIRMED_REAL_MINIMUM_IN_BOUNDED_SEARCH**. Fixed-center TG-002 circle instrument, contrast 13.3, 1.5 GHz.

92 discovery loops; 2 expanded roots; 2 distinct numerically qualified t=1 roots.

| Endpoint | Re(radius), mm | Im(radius), mm | Measured loss | Relative residual | Hessian Fq |
|---|---:|---:|---:|---:|---:|
| Initial radius (not stationary at t=1) | 65 | 0 | 0.749885869 | 1.22465168 | -467.974099 |
| Root 0: complex stationary | 64.6837849021 | -0.024428994 | — | — | — |
| Root 1: complex stationary | 64.6837849021 | 0.024428994 | — | — | — |

Loss is the normalized measured-data objective at t=1. Its relative field residual is sqrt(2*loss); a nonreal radius has no reported physical loss.

| Real control | Stop | Final radius, mm | Final t | Maximum sampled t | t=1 crossings |
|---|---|---:|---:|---:|---:|
| real_graph_+1_base | T_DOMAIN_BOUNDARY | 65.2774088017 | -1.99999986979 | -0 | 0 |
| real_graph_+1_half | T_DOMAIN_BOUNDARY | 65.2774088035 | -1.9999999023 | -0 | 0 |
| real_graph_-1_base | T_DOMAIN_BOUNDARY | 64.6578791375 | -1.99999986701 | 0.649164925068 | 0 |
| real_graph_-1_half | T_DOMAIN_BOUNDARY | 64.6578791383 | -1.99999816396 | 0.649167245979 | 0 |

Real controls follow the same start-connected graph in both radius directions, with original and half radius steps. They do not reconnect beyond a refusal.

Edge outcomes: NEW_QUALIFIED_ROOT: 1, KNOWN_ROOT: 91.

Observed transitions: changed_root: 2, identity: 90.

| Nonidentity action | Fold-center t | Starting root | Ending root |
|---|---:|---:|---:|
| edge_000 | 0.649167247036 | 0 | 1 |
| edge_046 | 0.649167247036 | 1 | 0 |

These observed actions concern the fixed attachment paths and 1e-7 root deduplication threshold. They do not certify the full monodromy group or exclude other paths, complex critical values, or unresolved roots.

Wall time including controls, failures and confirmation: **153.01 s**. Peak process RSS: 95.3 MiB.
Production frequency/radius jets: 413,695; refinement jets: 12,216; independent nodal solves: 0.

These are complete search/verification costs, not a runtime comparison against a general inverse solver.

[Frozen plan](../../../../../docs/iterations/complex_geometry/CG-003_plan.md) · [Raw outcome](outcome.json) · [Receipt validation](validation.json)

Reproduce without field evaluations: `python -m experiments.benchmark.cg003_report`.
