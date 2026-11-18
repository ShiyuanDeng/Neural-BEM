# B1 checks, 18 November 2026

No BEM fit has started. The coordinator review stop remains active.
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
| cross__c4 | 0 | None | None | INPUTS_PENDING |
| cog__c0.5 | 0 | None | None | INPUTS_PENDING |
| cog__c4 | 0 | None | None | INPUTS_PENDING |
| aphex_twin__c0.5 | 0 | None | None | INPUTS_PENDING |
| aphex_twin__c4 | 0 | None | None | INPUTS_PENDING |

Limits: BRG relative difference 0.01 at every frequency; refinement 1e-6.
A failed or missing check blocks the case. No resolution or tolerance changed.

[Compact checks and resource receipts](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/check_summary.json).
Each case keeps per-frequency diagnostics and SHA-256 for the local field copies.
Preparation receipts retain all input hashes, unit/layout proofs and default-schedule equality.

Pending: complete missing checks, report to coordinator, then await the first-fit go.
No solver, baseline, shared scoring or coordination file was changed.

## Timing and resources

Numerical check time: 27.759 s; summed worker process time: 52.849 s.
Checks from 2026-11-18T01:55:21.632749+00:00 to 2026-11-18T01:57:22.478112+00:00.
These shared-machine times include concurrent baseline and CSI work.

Peak worker host memory: 1.3505 GiB.
Peak GPU allocated/reserved: 0.2326 / 0.3574 GiB.
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

All 40 inverse fits remain unrun. After all checks, stop for the coordinator go.
First fit is known-contrast circle__c4; stop again to report its measured cost.
