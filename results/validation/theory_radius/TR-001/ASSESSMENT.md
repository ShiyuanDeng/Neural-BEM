# Numerical interpretation of TR-001

This reporting supplement uses only saved measurements. It was added during the run after tiny circle-band probes exposed the need to separate numerical-floor effects; the sealed solver, probes, radii, gates and source archive were unchanged.

Of 936 radius probes, 911 exceed 100 times the measured origin field-refinement floor and 25 do not. TCC ratios above 1/2: **0 resolved**, **22 unresolved**. The latter cannot be interpreted as violations of a local theorem. This is still a sampled check, with an origin-based resolution diagnostic, not a uniform bound.

Smallest singular values are separately flagged unresolved when they do not exceed 10 times the measured Jacobian refinement error. Raw diagnostic tables preserve these numbers, but they must not be treated as positive lower stability bounds.

Stage-2 configuration: M5, 0.5 and 0.75 GHz:

| Case | Catalog | Paired rho (mm) | Full rho (mm) | Full/paired |
|---|---|---:|---:|---:|
| circle_c13.3 | damped | 0.119567 | 0.116972 | 0.9783 |
| circle_c13.3 | real | 0.0307932 | 0.0260337 | 0.8454 |
| modal__c13.3__development_c | damped | 0.360487 | 0.351324 | 0.9746 |
| modal__c13.3__development_c | real | 0.00882858 | 0.00938512 | 1.063 |
| modal__c13.3__shifted_star | damped | 0.22183 | 0.291312 | 1.313 |
| modal__c13.3__shifted_star | real | 0.0159317 | 0.0309371 | 1.942 |
| modal__c4__development_c | damped | 0.571437 | 0.665447 | 1.165 |
| modal__c4__development_c | real | 0.244583 | 0.364036 | 1.488 |

These truth-centred neighborhoods address local conditioning. They do not establish recovery from a distant circle, nonuniqueness of paired data, or a safe online band-release rule. TR-002 checks whether archived endpoints are even inside such neighborhoods.

