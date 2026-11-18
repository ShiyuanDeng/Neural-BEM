# B1 checks, 18 November 2026

19 BEM fits have saved metrics. The coordinator released the queue with two B1 fits.
CUDA checks use default production/refined profiles and series_loss=1e-9.
Both fitting rows will read only the saved, hash-verified BRG observations.

| Case | Checked / 37 | BRG relative maximum | Refinement maximum | Status |
|---|---:|---:|---:|---|
| circle__c0.5 | 37 | 3.449730949448483e-11 | 2.5084136253513013e-14 | PASS |
| circle__c4 | 37 | 2.3626958902908266e-11 | 1.0178611771241843e-13 | PASS |
| kite__c0.5 | 37 | 1.571658211227961e-07 | 8.556081846362675e-15 | PASS |
| kite__c4 | 37 | 6.302133854441157e-08 | 2.892130931925261e-14 | PASS |
| peanut__c0.5 | 37 | 5.760770615747587e-11 | 1.9764547244817685e-14 | PASS |
| peanut__c4 | 37 | 2.0111624564395245e-11 | 5.056256589365459e-14 | PASS |
| star__c0.5 | 37 | 1.945585478693775e-08 | 6.022040282049014e-14 | PASS |
| star__c4 | 37 | 3.601822487599074e-08 | 8.11750341525282e-14 | PASS |
| asymmetric__c0.5 | 37 | 2.866670111652846e-08 | 2.927315598756006e-14 | PASS |
| asymmetric__c4 | 37 | 3.363311300933154e-08 | 5.950050195094314e-14 | PASS |
| c_shape__c0.5 | 37 | 7.395506330481163e-11 | 5.442516712441383e-14 | PASS |
| c_shape__c4 | 37 | 1.6302641726884027e-11 | 1.1501106734337583e-13 | PASS |
| hook__c0.5 | 37 | 2.694799908250825e-10 | 2.5983151346773448e-14 | PASS |
| hook__c4 | 37 | 1.470589075456192e-11 | 1.688450230318075e-13 | PASS |
| cross__c0.5 | 37 | 2.0557080104187058e-11 | 1.6279779075760412e-14 | PASS |
| cross__c4 | 37 | 1.3194908220155407e-11 | 5.094598303199394e-14 | PASS |
| cog__c0.5 | 37 | 1.4235514624814591e-09 | 1.42246317739985e-09 | PASS |
| cog__c4 | 0 | None | None | INPUTS_PENDING |
| aphex_twin__c0.5 | 0 | None | None | INPUTS_PENDING |
| aphex_twin__c4 | 0 | None | None | INPUTS_PENDING |

Limits: BRG relative difference 0.01 at every frequency; refinement 1e-6.
A failed or missing check blocks the case. No resolution or tolerance changed.

[Compact checks and resource receipts](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/check_summary.json).
Each case keeps per-frequency diagnostics and SHA-256 for the local field copies.
Preparation receipts retain all input hashes, unit/layout proofs and default-schedule equality.

Passing checks release cases automatically. Incomplete manifests remain inputs pending.
No solver, baseline, shared scoring or coordination file was changed.

## Timing and resources

Numerical check time: 30.867 s; summed worker process time: 58.368 s.
Checks from 2026-11-18T01:55:21.632749+00:00 to 2026-11-18T02:07:37.497206+00:00.
These shared-machine times include concurrent baseline and CSI work.

Peak worker host memory: 1.3505 GiB.
Peak GPU allocated/reserved: 0.2356 / 0.3574 GiB.
Lowest available host memory: 18.3737 GiB; floor 14 GiB.

Clean, unchanged solver sources in every completed check: True.
One frequency/BLAS/OpenMP/Torch thread; default trace cutoffs 64 and 96 on these truths.

## Preparation and pending work

Input checks verify recorded BRG SHA-256, table layout, units and frozen coefficients.
Multiplying lengths by 1.3 and dividing wavenumbers by 1.3 preserves the phase products
to 2.85e-14; complex fields are unchanged. Default schedule and adaptive tail match exactly
apart from ragged blocks; elapsed-time stopping is disabled as instructed.

[Wrapper/capacity events](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/preparation_events.json).
The shared-branch push error was resolved by an ordinary push; no check was repeated.

Coordinator note, 18 November: check each remaining case only after its BRG manifest
exists and matches all 37 files. Cross at eta 4, cog and aphex_twin at both contrasts
were pending at the first 15-case stop. The baseline completion run owns those files.
The watch-checks command picks up newly finished manifests without repeating checks.

19 of 40 inverse fits have saved metrics; the two-worker queue is authorized.
Checked cases may fit without waiting for late baseline manifests (coordinator, 18 November).
The first known-contrast circle__c4 fit has its own immutable first_fit_report.md.

## Saved inverse fits

| Case | Row | Outcome | Last stage | Units | Seconds | Area error | Contrast | Host / GPU peak GiB |
|---|---|---|---|---:|---:|---:|---:|---:|
| asymmetric__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 1443 | 35.4244 | 0.000400647 | 0.5 | 2.109 / 1.865 |
| asymmetric__c4 | known | COMPLETED_SCHEDULE | full_7_M43 | 1496 | 39.3742 | 0.000288297 | 4 | 2.132 / 1.979 |
| c_shape__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 690 | 18.1886 | 0.000260984 | 0.5 | 1.977 / 1.693 |
| c_shape__c4 | known | COMPLETED_SCHEDULE | full_7_M43 | 1020 | 27.617 | 5.72178e-05 | 4 | 2.085 / 1.984 |
| circle__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 356 | 8.55038 | 1.83938e-07 | 0.5 | 1.926 / 1.660 |
| circle__c0.5 | recovered | COMPLETED_SCHEDULE | full_6_M37 | 573 | 11.7627 | 3.98914e-07 | 0.5 | 2.037 / 1.691 |
| circle__c4 | known | COMPLETED_SCHEDULE | full_6_M37 | 274 | 6.69482 | 7.31659e-07 | 4 | 1.936 / 1.369 |
| circle__c4 | recovered | COMPLETED_SCHEDULE | full_6_M37 | 404 | 8.96354 | 9.48565e-08 | 4 | 2.022 / 1.605 |
| cog__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 1796 | 40.9265 | 0.00290269 | 0.5 | 2.103 / 1.674 |
| cross__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 1083 | 23.4736 | 0.000864724 | 0.5 | 1.953 / 1.799 |
| cross__c4 | known | COMPLETED_SCHEDULE | full_7_M43 | 910 | 21.6503 | 8.59007e-05 | 4 | 2.022 / 1.941 |
| hook__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 774 | 22.9957 | 0.000438502 | 0.5 | 1.952 / 1.865 |
| hook__c4 | known | COMPLETED_SCHEDULE | full_7_M43 | 1670 | 47.1456 | 0.000257702 | 4 | 2.150 / 1.977 |
| kite__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 4585 | 114.578 | 0.000525714 | 0.5 | 2.099 / 1.865 |
| kite__c4 | known | COMPLETED_SCHEDULE | full_6_M37 | 2292 | 57.3084 | 0.000867416 | 4 | 2.092 / 1.676 |
| peanut__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 632 | 14.606 | 0.000480905 | 0.5 | 1.941 / 1.846 |
| peanut__c4 | known | COMPLETED_SCHEDULE | full_6_M37 | 1790 | 42.2772 | 0.000941055 | 4 | 2.100 / 1.961 |
| star__c0.5 | known | COMPLETED_SCHEDULE | full_6_M37 | 1194 | 29.6754 | 0.000928646 | 0.5 | 2.114 / 1.666 |
| star__c4 | known | COMPLETED_SCHEDULE | full_9_M55 | 1803 | 48.3346 | 0.000160548 | 4 | 2.238 / 1.955 |

[First-fit report](first_fit_report.md).
