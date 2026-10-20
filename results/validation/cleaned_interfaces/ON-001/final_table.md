# ON-001 confirmed comparison

Classification: **useful partial result**.

| Case | B recovered | E recovered | B/E time | E RMS mm | E Hausdorff upper mm | E max residual | E audit |
|---|---|---|---|---|---|---|---|
| circle__c0.5 | True | True | 1.252 | 0.00001 | 0.01928 | 1.02445e-06 | True |
| circle__c4 | True | True | 1.240 | 0.00002 | 0.01941 | 1.25116e-05 | True |
| circle__c13.3 | True | True | 1.593 | 0.00005 | 0.01933 | 5.76011e-05 | True |
| kite__c0.5 | True | True | 3.857 | 0.18828 | 0.66469 | 0.00261846 | True |
| kite__c4 | True | True | 2.127 | 0.13221 | 0.37016 | 0.00206733 | True |
| kite__c13.3 | True | True | 1.151 | 0.03221 | 0.11949 | 0.00121647 | True |
| peanut__c0.5 | True | True | 2.099 | 0.02602 | 0.09632 | 0.000244032 | True |
| peanut__c4 | True | True | 1.693 | 0.01241 | 0.04570 | 0.000226816 | True |
| peanut__c13.3 | True | True | 1.296 | 0.00328 | 0.03006 | 0.00118528 | True |
| star__c0.5 | True | True | 1.571 | 0.05221 | 0.19856 | 0.00043641 | True |
| star__c4 | True | True | 1.624 | 0.03773 | 0.11203 | 0.000766661 | True |
| star__c13.3 | True | True | 1.600 | 0.01096 | 0.05663 | 0.00147169 | True |
| asymmetric__c0.5 | True | True | 1.955 | 0.08062 | 0.39695 | 0.000703913 | True |
| asymmetric__c4 | True | True | 1.896 | 0.04059 | 0.17125 | 0.000951669 | True |
| asymmetric__c13.3 | True | True | 1.340 | 0.01141 | 0.08107 | 0.00188661 | True |
| c_shape__c0.5 | True | True | 1.421 | 0.00588 | 0.04675 | 0.000181717 | True |
| c_shape__c4 | True | True | 1.445 | 0.00500 | 0.03938 | 0.000973329 | True |
| c_shape__c13.3 | True | True | 1.182 | 0.00036 | 0.02850 | 0.00013447 | True |
| hook__c0.5 | True | True | 1.591 | 0.03372 | 0.12487 | 0.00284194 | True |
| hook__c4 | True | True | 1.510 | 0.00603 | 0.05234 | 0.00093586 | True |
| hook__c13.3 | False | False | — | 8.65745 | 25.13288 | 1.63058 | True |
| cross__c0.5 | True | True | 1.905 | 0.12616 | 0.25725 | 0.00179965 | True |
| cross__c4 | True | True | 1.520 | 0.01755 | 0.06474 | 0.00183313 | True |
| cross__c13.3 | True | True | 1.211 | 0.00277 | 0.02953 | 0.000220603 | True |
| cog__c0.5 | True | True | 1.895 | 0.06111 | 0.20455 | 0.00195304 | True |
| cog__c4 | True | True | 1.469 | 0.03971 | 0.12293 | 0.0011635 | True |
| cog__c13.3 | True | True | 1.328 | 0.01069 | 0.05439 | 0.00251715 | True |
| aphex_twin__c0.5 | False | False | — | 4.39830 | 11.05874 | 1.29864 | True |
| aphex_twin__c4 | False | False | — | 1.68538 | 5.14993 | 0.75993 | True |
| aphex_twin__c13.3 | False | False | — | 4.15241 | 14.12383 | 1.65385 | False |

Timing distributions contain only common recovered cases; failures remain in the inventory and suite totals.
