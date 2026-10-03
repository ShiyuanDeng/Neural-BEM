# TR-002: theory diagnostic evidence

Empirical finite-dimensional diagnostics. No certified convergence radius or new recovery claim.

Execution complete: **True**. Numerical wall time: **4.7 s**. Forward frequency solves: **69**; derivative batches: **0**.

Source/input hashes, source archive, execution settings and concurrent processes are in [manifest.json](manifest.json). Timings with other campaign activity are not matched benchmarks.

| Case | Full data | Transition | Graph valid | Applicable | Indicator passes |
|---|---|---|---|---|---|
| modal__c13.3__development_c | False | stage_1_damped → stage_2_damped | False | False | — |
| modal__c13.3__development_c | False | stage_2_damped → stage_3_damped | False | False | — |
| modal__c13.3__development_c | False | stage_3_damped → stage_4_damped | False | False | — |
| modal__c13.3__development_c | False | stage_4_damped → stage_4_undamped | False | False | — |
| modal__c13.3__development_c | True | stage_1_damped → stage_2_damped | False | False | — |
| modal__c13.3__development_c | True | stage_2_damped → stage_3_damped | True | False | — |
| modal__c13.3__development_c | True | stage_3_damped → stage_4_damped | True | True | False |
| modal__c13.3__development_c | True | stage_4_damped → stage_4_undamped | True | True | False |
| modal__c13.3__shifted_star | False | stage_1_damped → stage_2_damped | False | False | — |
| modal__c13.3__shifted_star | False | stage_2_damped → stage_3_damped | True | False | — |
| modal__c13.3__shifted_star | False | stage_3_damped → stage_4_damped | True | False | — |
| modal__c13.3__shifted_star | False | stage_4_damped → stage_4_undamped | True | False | — |
| modal__c13.3__shifted_star | True | stage_1_damped → stage_2_damped | False | False | — |
| modal__c13.3__shifted_star | True | stage_2_damped → stage_3_damped | True | False | — |
| modal__c13.3__shifted_star | True | stage_3_damped → stage_4_damped | True | False | — |
| modal__c13.3__shifted_star | True | stage_4_damped → stage_4_undamped | True | False | — |
| modal__c4__development_c | False | stage_1_damped → stage_2_damped | False | False | — |
| modal__c4__development_c | False | stage_2_damped → stage_3_damped | True | False | — |
| modal__c4__development_c | False | stage_3_damped → stage_4_damped | True | True | False |
| modal__c4__development_c | False | stage_4_damped → stage_4_undamped | True | True | False |
| modal__c4__development_c | True | stage_1_damped → stage_2_damped | True | False | — |
| modal__c4__development_c | True | stage_2_damped → stage_3_damped | True | True | False |
| modal__c4__development_c | True | stage_3_damped → stage_4_damped | True | True | False |
| modal__c4__development_c | True | stage_4_damped → stage_4_undamped | True | True | False |

Inapplicable is not a failed recovery prediction: the sufficient local argument does not apply to that endpoint. These retrospective numbers use truth and cannot be an online scheduling rule. Sampled chart tests and truncation measurements are not continuum bounds.

