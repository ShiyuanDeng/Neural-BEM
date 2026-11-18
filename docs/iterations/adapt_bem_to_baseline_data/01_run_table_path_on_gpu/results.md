# Run the table path on the GPU: results

18 November 2026. Owner: `bem-gpu`. In progress; solver lock retained.
The coordinator approved the narrow guard removal and stale wording fixes.
No solver edit has been made. All three references must finish first.

## Clean CPU reference

Started 00:22:57 UTC, ended 00:25:00 UTC, source commit `26d95baf2`.
Solver was clean at both ends. The copied BRG driver used TG-002
`circle__c0.5`, `bem/default_clean_uc_fc`, CPU pinned with CUDA hidden,
four frequency threads and one BLAS thread. Other settings follow the plan.

- Existing suite: **109 passed, 3 CUDA skips**, 70.62 s pytest time.
- Default fit: **COMPLETED_SCHEDULE**, 43.452 s fit time, 596 units,
  402 forward solves, 194 derivative batches, 17 accepted steps, 10 stages.
- Contrast: **0.5000000000469913**. Maximum residual: **2.0105158339865096e-7**.
- Guarded process: 123.477 s including suite and setup. Child peak RSS
  **1.742 GiB**; sampled process-group peak 1.660 GiB. Minimum available host
  memory **18.920 GiB**. No memory stop, fit failure or work-limit stop.

[Evidence](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/cpu_before/)
contains settings, source hashes, fit records, test XML, logs, resource receipts
and a SHA-256 manifest for the ignored NPZ array reference. Timings are indicative
on the shared machine. The 4 GiB starting estimate remains conservative against
the measured peak and leaves at least 16 GiB before subsequent launches.

## Pending

Second clean GPU reference, approved edit, CPU/GPU table checks, CPU/GPU default
comparisons, CUDA-visible suite, and coordinator diff review before solver commit.

## First clean GPU reference

Started 00:25:38 UTC, ended 00:25:47 UTC, source commit `59dd6b919`.
Solver clean at both ends. Same default case/settings, explicit CUDA and
four frequency threads; no warm-up. **COMPLETED_SCHEDULE**, 5.507 s fit time,
596 units, 402 forward solves, 194 derivative batches, 17 steps, 10 stages.
Contrast **0.5000000000469924**, maximum residual **2.0105161224902063e-7**.

Guarded wall time **9.231 s**, child peak RSS **1.820 GiB**, minimum available
host memory **19.451 GiB**. CUDA peak allocated **0.896 GiB**, reserved
**1.223 GiB**. No failures. This is the first GPU repeatability reference;
its small numerical difference from CPU is not a before/after code change.
[Evidence](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/gpu_before_1/).
