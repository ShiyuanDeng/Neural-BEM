# B1 campaign report

Generated 2026-11-18T03:36:47.025159+00:00. 38/40 fits have saved metrics.

All 20 case checks pass: 740 frequency comparisons.
Maximum BRG difference 8.75351062e-06; refinement 7.93843874e-07.

| Case | Known area error | Recovered area error | Recovered eta | Known / recovered fit s |
|---|---:|---:|---:|---:|
| circle__c4 | 7.31658833e-07 | 9.48565265e-08 | 4 | 6.69482333 / 8.96353698 |
| circle__c0.5 | 1.83937626e-07 | 3.98913527e-07 | 0.5 | 8.55038212 / 11.7626941 |
| kite__c0.5 | 0.000525713724 | 0.000666783314 | 0.499999914 | 114.578049 / 95.8596272 |
| kite__c4 | 0.00086741554 | 0.000910111235 | 3.99999986 | 57.3083922 / 69.8369329 |
| peanut__c0.5 | 0.000480905146 | 0.000163512862 | 0.500000018 | 14.60603 / 22.9205823 |
| peanut__c4 | 0.000941054603 | 0.000130831945 | 4.00000003 | 42.2772353 / 28.9227784 |
| star__c0.5 | 0.000928646067 | 0.000995842083 | 0.499999725 | 29.6753746 / 40.0334196 |
| star__c4 | 0.000160547604 | 0.000153713927 | 4.00000007 | 48.3346475 / 65.8312229 |
| asymmetric__c0.5 | 0.000400646948 | 0.000399010841 | 0.499999955 | 35.4243722 / 43.2717344 |
| asymmetric__c4 | 0.000288296514 | 0.000255839606 | 4.00000006 | 39.3741762 / 54.8617067 |
| c_shape__c0.5 | 0.000260984275 | 0.000477407073 | 0.499999838 | 18.1886266 / 28.2813455 |
| c_shape__c4 | 5.72178481e-05 | 7.11616931e-05 | 4.00000001 | 27.616953 / 51.9712544 |
| hook__c0.5 | 0.000438502334 | 0.000981688647 | 0.499999099 | 22.995689 / 38.8329389 |
| hook__c4 | 0.000257702134 | 0.000175608428 | 4.0000001 | 47.145616 / 63.8342968 |
| cross__c0.5 | 0.000864723652 | 0.000643155423 | 0.499999681 | 23.47364 / 30.2131388 |
| cross__c4 | 8.59007263e-05 | 0.000106515131 | 4.00000004 | 21.6502535 / 32.2337553 |
| cog__c0.5 | 0.00290269017 | 0.00214085857 | 0.499999813 | 40.9264542 / 37.3706162 |
| cog__c4 | 0.000376742995 | 0.00037678816 | 4.00000014 | 39.9367895 / 55.6419127 |
| aphex_twin__c0.5 | 0.151127379 | 0.0113665214 | 0.499893329 | 1431.13397 / 147.335002 |
| aphex_twin__c4 | pending | pending | pending | pending / pending |

Area errors are raw fractions, not percent. No alignment, tuning, or numerical rerun.
[Every fit: outcome, stage, work, time, contrast and memory](results.md).
[Raw consolidated records](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/campaign_summary.json).

## Work, time and resources

Fit time sum 2997.870 s; worker process time sum 3068.008 s; work 60272 units.
First worker 2026-11-18T02:06:07.580121+00:00; last worker 2026-11-18T02:53:22.580831+00:00.
That interval includes coordinator review waits, data arrival waits and the safe resource-allocation change.

Largest host peak 2.2679 GiB; sampled process GPU peak 1.9844 GiB.
Minimum available host memory 23.4302 GiB, against the 14 GiB floor.
Maximum numerical-worker overlap 4. The authorized ceiling changed from one to two to four.

## Retained failures and checks

Outcomes: {'COMPLETED_SCHEDULE': 38}.
A completed schedule is a solver outcome, not a recovery-quality verdict.
The coordinator classified aphex_twin__c0.5 known contrast as a failed recovery
on 18 November at 02:54 UTC: area error 15.1%. Its endpoint is retained without a rerun.
Series refusals: []; memory requeues: [].
Runs above 120 s: ['aphex_twin__c0.5 known', 'aphex_twin__c0.5 recovered']; above 1 h: [].
Elapsed time never stopped a fit. The original first-fit scoring import failure remains saved;
the owned wrapper path was fixed and the saved endpoint scored, without a numerical rerun.

Every saved fit uses the same 19 BRG observation hashes as its check, and no BEM-made observations.
All checked solver source maps remained clean and unchanged. BLAS/OpenMP and both Torch pools used one thread.
The unedited comparison scoring supplies raw region, boundary, signed-material and contrast scores.

No solver, baseline, scoring or coordination file was edited. Bulk stays local with SHA-256.
