# FM-003 results

Frozen plan: [iteration 20](../iteration_20/03_plan.md). Existing `feature/shape-frequency-continuation` branch; production policy unchanged.

Baseline `b43fa04c2e27b6b1f7fd05eba153436f4f2e7cc0`. One worker, four frequency threads, auto device; single-threaded BLAS.

Phase L gates: **PASS**. Usable lifts: `[{'frequency_hz': 250000000.0, 'N': 2}]`.

| GHz | N | Full truncation floor | Paired residual | Full lift error | Ambiguity | Linear error |
|---|---|---|---|---|---|---|
| 0.25 | 2 | 0.00344 | 0.001371 | 0.006125 | 1.332e-08 | 0.9543 |
| 0.25 | 3 | 0.0001735 | 3.239e-06 | 0.8892 | 2.719 | 0.9804 |
| 0.25 | 4 | 1.797e-05 | 8.65e-09 | 1.757 | 3.093 | 0.998 |
| 0.5 | 2 | 0.2162 | 0.06975 | 1.317 | 1.952e-07 | 0.9823 |
| 0.5 | 3 | 0.02537 | 0.01371 | 1.114 | 1.934 | 0.9604 |
| 0.5 | 4 | 0.0008897 | 7.148e-05 | 1.777 | 2.861 | 0.9729 |
| 0.75 | 2 | 0.3711 | 0.3026 | 0.7244 | 1.608e-07 | 0.9763 |
| 0.75 | 3 | 0.07111 | 0.0522 | 0.9372 | 1.278 | 0.9581 |
| 0.75 | 4 | 0.05531 | 0.0126 | 1.051 | 2.029 | 0.9743 |

Phase 0 strict replay: **PASS**. Checks: `{'accepted_steps': True, 'stop': True, 'loss': True, 'identical_coefficients': True}`. Loss relative difference 0; maximum coefficient difference 0.

All start draws, refusals, optimizer trials, timeouts and source/input seals are in `results/validation/cleaned_interfaces/FM-003/`. Damped synthetic catalogs support no realism claim.
