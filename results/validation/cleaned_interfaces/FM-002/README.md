# FM-002 corrected relaxed-gradient comparison

All arms use the same full-matrix catalogs and damped paired localization. D/R changes only early fitting damping; 0/1 changes only relaxation. Final scoring uses ordinary real data.

| Case | Arm | Outcome | Full recovery | Paired recovery | RMS mm | Seconds |
|---|---|---|---|---|---:|---:|
| modal__c13.3__development_c | D0 | COMPLETED_SCHEDULE | True | True | 3.55566e-05 | 119.8 |
| modal__c13.3__development_c | R0 | NUMERICAL_FAILURE | False | False | 23.032 | 342.2 |
| modal__c13.3__development_c | D1 | COMPLETED_SCHEDULE | True | True | 3.55659e-05 | 275.5 |
| modal__c13.3__development_c | R1 | NUMERICAL_FAILURE | False | False | 10.8337 | 652.9 |
| modal__c13.3__shifted_star | D0 | COMPLETED_SCHEDULE | True | True | 0.00170231 | 320.8 |
| modal__c13.3__shifted_star | R0 | NUMERICAL_FAILURE | False | False | 7.66791 | 364.4 |
| modal__c13.3__shifted_star | D1 | COMPLETED_SCHEDULE | True | True | 0.00169083 | 442.2 |
| modal__c13.3__shifted_star | R1 | NUMERICAL_FAILURE | False | False | 5.55273 | 839.0 |
| modal__c4__development_c | D0 | COMPLETED_SCHEDULE | True | True | 0.000421927 | 79.1 |
| modal__c4__development_c | R0 | COMPLETED_SCHEDULE | True | True | 0.000470514 | 75.1 |
| modal__c4__development_c | D1 | COMPLETED_SCHEDULE | True | True | 0.000545346 | 199.3 |
| modal__c4__development_c | R1 | COMPLETED_SCHEDULE | True | True | 0.000379692 | 202.7 |

Completed 12/12. Numerical stops and budget stops are not evidence of convergence. These are single-run diagnostics, not matched runtime comparisons.
