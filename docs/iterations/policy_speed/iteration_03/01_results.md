# PS-003: GPU slider policy comparisons

Questions: why are hook fits slow, which declared policy helps, and does slider recover other TG-002 cases?

Consumed fits: 7/13. Next fit: O2B.

Saved GU-002 and PS-002 are references, not concurrent controls. No reference reruns.

| Run | Case | Recovered | Fit s | Final checks s | Accepted | Actual calls | Charged units | RMS mm |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GU-002 | hook__c13.3 | True | 30.29 | 2.52 | 125 | 2978 | 2978 | 0.0002302 |
| PS-002 | hook__c13.3 | False | 25.49 | 3.469 | 58 | 1676 | 1672 | 6.605 |
| D1 | hook__c13.3 | False | 43.48 | 3.175 | 117 | 3040 | 3036 | 0.5129 |
| D2 | hook__c13.3 | True | 19.7 | 1.641 | 122 | 2653 | 2653 | 0.0004239 |
| H1 | hook__c13.3 | True | 25.46 | 1.95 | 119 | 2558 | 2558 | 0.0002482 |
| H2 | hook__c13.3 | False | 26.86 | 2.046 | 129 | 3012 | 3012 | 0.06962 |
| H3 | hook__c13.3 | True | 16.26 | 1.701 | 122 | 2653 | 2653 | 0.0004252 |
| O1B | circle__c4 | True | 2.213 | 1.853 | 9 | 278 | 278 | 1.055e-05 |
| O1S | circle__c4 | False | 1.495 | 0.8166 | 9 | 277 | 277 | 1.056e-05 |

## Saved-run explanation

GU-002 used 40 accepted iterations and 15.926 s in M11/M15, with no rejected trials there.
Its loss fell from 0.14065 to 0.024019. Releasing M19 then reached 0.000072 in four iterations.
This is consistent with restricted update directions, but the saved run alone cannot establish the cause.

PS-002 left stage_3_damped after six iterations at loss 0.005709; GU-002 used 19 and reached 0.000656.
PS-002 entered M11 at loss 0.550665 versus 0.14065. Its early exits changed the later path.
M43/M49 then cost 9.703 s, with eight rejected trials; it failed recovery in M55.

The saved runs lack raw/clipped proposal sizes, skipped tiny proposals and damping retry counts.
Thread-level physics times overlap and are not wall-time totals. New batch timers measure wall time.


Detailed stages: [PS-003 evidence](../../../../results/validation/cleaned_interfaces/PS-003/README.md).
