# SC-043 — prospective band decisions

18/18 terminal paths; 0 exceptions; 0 pending.

| Case | Rule | Bands | RMS mm | Hausdorff mm | Work (diagnostic) | Outcome | Audit |
|---|---|---|---:|---:|---:|---|---|
| circle_to_c | atlas | [25, 31, 31] | 0.0062217 | 0.03381 | 684 (228) | COMPLETED_SCHEDULE | True |
| circle_to_c | fixed | [25, 31, 37] | 0.0040929 | 0.025917 | 779 (0) | COMPLETED_SCHEDULE | True |
| circle_to_c | stagnation | [19, 25, 31] | 0.0062803 | 0.033539 | 532 (0) | COMPLETED_SCHEDULE | True |
| circle_to_star | atlas | [31, 37, 43] | 0.011146 | 0.025522 | 703 (228) | COMPLETED_SCHEDULE | True |
| circle_to_star | fixed | [31, 37, 43] | 0.011028 | 0.029289 | 741 (0) | COMPLETED_SCHEDULE | True |
| circle_to_star | stagnation | [31, 37, 37] | 0.018149 | 0.047518 | 741 (0) | COMPLETED_SCHEDULE | True |
| hook | atlas | [25, 31, 31] | 0.0027153 | 0.0083806 | 684 (228) | COMPLETED_SCHEDULE | True |
| hook | fixed | [25, 31, 37] | 0.0020533 | 0.0054345 | 646 (0) | COMPLETED_SCHEDULE | True |
| hook | stagnation | [19, 25, 31] | 0.0022539 | 0.0060843 | 570 (0) | COMPLETED_SCHEDULE | True |
| kite | atlas | [22, 22, 22] | 0.065093 | 0.21383 | 817 (228) | COMPLETED_SCHEDULE | True |
| kite | fixed | [28, 34, 40] | 0.034606 | 0.17058 | 798 (0) | COMPLETED_SCHEDULE | True |
| kite | stagnation | [22, 22, 28] | 0.038771 | 0.15432 | 817 (0) | COMPLETED_SCHEDULE | True |
| peanut | atlas | [25, 25, 31] | 0.0025435 | 0.0081787 | 646 (228) | COMPLETED_SCHEDULE | True |
| peanut | fixed | [25, 31, 37] | 0.0024278 | 0.0074445 | 418 (0) | COMPLETED_SCHEDULE | True |
| peanut | stagnation | [19, 25, 25] | 0.0034569 | 0.0098256 | 646 (0) | COMPLETED_SCHEDULE | True |
| wrong_circle | atlas | [19, 19, 19] | 0.00024467 | 0.00036579 | 342 (228) | COMPLETED_SCHEDULE | True |
| wrong_circle | fixed | [25, 31, 37] | 0.00024467 | 0.00036579 | 114 (0) | COMPLETED_SCHEDULE | True |
| wrong_circle | stagnation | [19, 25, 31] | 0.00024467 | 0.00036579 | 114 (0) | COMPLETED_SCHEDULE | True |

Evidence checks: 248/248.

Exceptions remain in the 18-path denominator. An unqualified diagnostic blocks that policy; it is not a missing successful replicate.
Reported geometric means use available scored pairs. The superiority gate requires all six cases against both controls.
Supplementary common-work comparisons use the last accepted state affordable at the smaller actual path cost, with diagnostics charged. These checkpoints passed fitting acceptance but do not receive new endpoint audits. They do not replace the frozen terminal-state gate.

## Decisions and subsequent fitting

| Case | Rule | Block | Choice | Extra predicted gain / loss | Fitting loss decrease | Diagnostic / fitting work | Stop |
|---|---|---:|---|---:|---:|---:|---|
| circle_to_c | atlas | 1 | 19→25 | 99.887% | 99.939% | 76 / 152 | None |
| circle_to_c | atlas | 2 | 25→31 | 98.955% | 97.216% | 76 / 152 | None |
| circle_to_c | atlas | 3 | 31→31 | 9.868% | 87.235% | 76 / 152 | None |
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
| hook | atlas | 1 | 19→25 | 99.779% | 99.926% | 76 / 152 | None |
| hook | atlas | 2 | 25→31 | 20.881% | 99.365% | 76 / 152 | None |
| hook | atlas | 3 | 31→31 | 4.236% | 83.006% | 76 / 152 | None |
| hook | fixed | 1 | 19→25 | — | 99.984% | 0 / 266 | None |
| hook | fixed | 2 | 25→31 | — | 98.545% | 0 / 266 | None |
| hook | fixed | 3 | 31→37 | — | 93.967% | 0 / 114 | loss_tolerance |
| hook | stagnation | 1 | 19→19 | — | 0.000% | 0 / 38 | no_decreasing_step |
| hook | stagnation | 2 | 19→25 | — | 99.984% | 0 / 266 | None |
| hook | stagnation | 3 | 25→31 | — | 98.545% | 0 / 266 | None |
| kite | atlas | 1 | 22→22 | 5.065% | 51.881% | 76 / 190 | None |
| kite | atlas | 2 | 22→22 | 7.746% | 46.053% | 76 / 190 | None |
| kite | atlas | 3 | 22→22 | 3.507% | 7.772% | 76 / 209 | None |
| kite | fixed | 1 | 22→28 | — | 94.731% | 0 / 266 | None |
| kite | fixed | 2 | 28→34 | — | 30.217% | 0 / 247 | None |
| kite | fixed | 3 | 34→40 | — | 5.544% | 0 / 285 | None |
| kite | stagnation | 1 | 22→22 | — | 51.881% | 0 / 266 | None |
| kite | stagnation | 2 | 22→22 | — | 46.747% | 0 / 285 | None |
| kite | stagnation | 3 | 22→28 | — | 81.518% | 0 / 266 | None |
| peanut | atlas | 1 | 19→25 | 95.396% | 97.258% | 76 / 152 | None |
| peanut | atlas | 2 | 25→25 | 3.732% | 78.870% | 76 / 152 | None |
| peanut | atlas | 3 | 25→31 | 13.192% | 67.129% | 76 / 114 | loss_tolerance |
| peanut | fixed | 1 | 19→25 | — | 99.245% | 0 / 266 | None |
| peanut | fixed | 2 | 25→31 | — | 75.099% | 0 / 114 | loss_tolerance |
| peanut | fixed | 3 | 31→37 | — | 0.000% | 0 / 38 | loss_tolerance |
| peanut | stagnation | 1 | 19→19 | — | 0.000% | 0 / 95 | no_decreasing_step |
| peanut | stagnation | 2 | 19→25 | — | 99.245% | 0 / 266 | None |
| peanut | stagnation | 3 | 25→25 | — | 47.761% | 0 / 285 | None |
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
Trial counts and work after the last accepted state are retained in the machine-readable block records. That work includes derivative and qualification checks, not just avoidable rejected trials.
