# SC-043 — prospective band decisions

8/18 terminal paths; 0 exceptions; 10 pending.

| Case | Rule | Bands | RMS mm | Hausdorff mm | Work (diagnostic) | Outcome | Audit |
|---|---|---|---:|---:|---:|---|---|
| circle_to_c | fixed | [25, 31, 37] | 0.0040929 | 0.025917 | 779 (0) | COMPLETED_SCHEDULE | True |
| circle_to_c | stagnation | [19, 25, 31] | 0.0062803 | 0.033539 | 532 (0) | COMPLETED_SCHEDULE | True |
| circle_to_star | atlas | [31, 37, 43] | 0.011146 | 0.025522 | 703 (228) | COMPLETED_SCHEDULE | True |
| circle_to_star | fixed | [31, 37, 43] | 0.011028 | 0.029289 | 741 (0) | COMPLETED_SCHEDULE | True |
| circle_to_star | stagnation | [31, 37, 37] | 0.018149 | 0.047518 | 741 (0) | COMPLETED_SCHEDULE | True |
| wrong_circle | atlas | [19, 19, 19] | 0.00024467 | 0.00036579 | 342 (228) | COMPLETED_SCHEDULE | True |
| wrong_circle | fixed | [25, 31, 37] | 0.00024467 | 0.00036579 | 114 (0) | COMPLETED_SCHEDULE | True |
| wrong_circle | stagnation | [19, 25, 31] | 0.00024467 | 0.00036579 | 114 (0) | COMPLETED_SCHEDULE | True |

Evidence checks: 98/98.

Exceptions remain in the 18-path denominator. An unqualified diagnostic blocks that policy; it is not a missing successful replicate.
Reported geometric means use available scored pairs. The superiority gate requires all six cases against both controls.
Supplementary common-work comparisons use the last accepted state affordable at the smaller actual path cost, with diagnostics charged. These checkpoints passed fitting acceptance but do not receive new endpoint audits. They do not replace the frozen terminal-state gate.

## Decisions and subsequent fitting

| Case | Rule | Block | Choice | Extra predicted gain / loss | Fitting loss decrease | Diagnostic / fitting work | Stop |
|---|---|---:|---|---:|---:|---:|---|
| circle_to_c | fixed | 1 | 19→25 | — | 99.939% | 0 / 228 | gradient_tolerance |
| circle_to_c | fixed | 2 | 25→31 | — | 99.681% | 0 / 266 | None |
| circle_to_c | fixed | 3 | 31→37 | — | 61.628% | 0 / 285 | None |
| circle_to_c | stagnation | 1 | 19→19 | — | 0.000% | 0 / 38 | no_decreasing_step |
| circle_to_c | stagnation | 2 | 19→25 | — | 99.939% | 0 / 228 | gradient_tolerance |
| circle_to_c | stagnation | 3 | 25→31 | — | 99.681% | 0 / 266 | None |
| circle_to_star | atlas | 1 | 25→31 | 97.531% | 94.024% | 76 / 152 | None |
| circle_to_star | atlas | 2 | 31→37 | 92.925% | 91.198% | 76 / 152 | None |
| circle_to_star | atlas | 3 | 37→43 | 42.042% | 87.180% | 76 / 171 | None |
| circle_to_star | fixed | 1 | 25→31 | — | 94.032% | 0 / 266 | None |
| circle_to_star | fixed | 2 | 31→37 | — | 92.666% | 0 / 228 | None |
| circle_to_star | fixed | 3 | 37→43 | — | 86.828% | 0 / 247 | None |
| circle_to_star | stagnation | 1 | 25→31 | — | 94.032% | 0 / 266 | None |
| circle_to_star | stagnation | 2 | 31→37 | — | 92.666% | 0 / 228 | None |
| circle_to_star | stagnation | 3 | 37→37 | — | 13.664% | 0 / 247 | None |
| wrong_circle | atlas | 1 | 19→19 | 0.000% | 0.000% | 76 / 38 | loss_tolerance |
| wrong_circle | atlas | 2 | 19→19 | 0.000% | 0.000% | 76 / 38 | loss_tolerance |
| wrong_circle | atlas | 3 | 19→19 | 0.000% | 0.000% | 76 / 38 | loss_tolerance |
| wrong_circle | fixed | 1 | 19→25 | — | 0.000% | 0 / 38 | loss_tolerance |
| wrong_circle | fixed | 2 | 25→31 | — | 0.000% | 0 / 38 | loss_tolerance |
| wrong_circle | fixed | 3 | 31→37 | — | 0.000% | 0 / 38 | loss_tolerance |
| wrong_circle | stagnation | 1 | 19→19 | — | 0.000% | 0 / 38 | loss_tolerance |
| wrong_circle | stagnation | 2 | 19→25 | — | 0.000% | 0 / 38 | loss_tolerance |
| wrong_circle | stagnation | 3 | 25→31 | — | 0.000% | 0 / 38 | loss_tolerance |

The forecast compares two optimal linearized directions at the declared test radius. The subsequent fit runs multiple damped LM steps, so its total decrease is not a calibration test of that single forecast. A retained band followed by poor improvement is evidence about this decision rule, not proof that all higher modes are unobservable.
