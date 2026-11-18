# Run the table path on the GPU: results

18 November 2026. Owner: `bem-gpu`. In progress; solver lock retained.
The coordinator approved the narrow guard removal and stale wording fixes.
All three clean pre-edit references are complete. The approved solver edit
was made at 00:27 UTC. All proofs pass. Solver remains dirty and awaits
the coordinator's full-diff review before committing.

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

Only coordinator diff review, commit/push, and solver-lock release remain.

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

## Second clean GPU reference and frozen envelope

Started 2026-11-18T00:26:16.413659+00:00, source commit `6a5258daa`; solver clean at both ends.
Same settings as the first GPU reference. **COMPLETED_SCHEDULE**,
5.363 s fit time, 8.740 s guarded wall time.
Peak child RSS 1.820 GiB, minimum available host
memory 19.616 GiB. No failure or limit stop.

All three saved arrays (curve coefficients, image and predictions) are
**byte-identical** between the two pre-edit GPU runs. All 15 stable record
sections are also identical. The frozen repeatability envelope is **zero**:
the post-edit GPU reference must therefore be exact, including stable records.
No thresholds have moved. [Second reference](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/gpu_before_2/)
and [frozen envelope](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/gpu_repeatability.json).

## GPU table agreement after the approved edit

The solver edit removes the two-line CPU-only guard, updates its settings
comment, and removes "CPU" from the three nodal masked-table refusal messages.
No other solver logic changed. The module docstring already described the
CPU/CUDA split correctly and needed no edit. README and chain are updated.

Eight focused checks passed: both illumination kinds, masked/unmasked, and
both explicit CUDA and auto (confirmed `cuda-modal`, without fallback).
The shared curve is translated and noncircular; the same CPU-prepared slider
space isolates the assembly change. Point sources use complex strength.
All masked predictions and derivative rows equal full-table C-order selection.

| Table | Mask | Prediction relative L2 | B7 shape derivative relative L2 | Material-column relative L2 |
|---|---|---:|---:|---:|
| plane | full | 9.30171e-16 | 3.52800e-16 | 1.47217e-13 |
| plane | masked | 1.01129e-15 | 3.38931e-16 | 1.48257e-13 |
| point | full | 1.63819e-15 | 6.27883e-16 | 2.70791e-13 |
| point | masked | 1.57321e-15 | 6.19144e-16 | 2.84008e-13 |

Auto gives the same errors as explicit CUDA. All are below the fixed **1e-10**
limit. Material columns use a common central contrast step of 1e-3. Existing
complete-slider derivative checks remain in the full suite.

Pytest: **8 passed in 2.31 s**. Guarded wall time 3.604 s;
peak child RSS 1.435 GiB; minimum available
memory 20.204 GiB. No failures or limit stops.
[Per-case errors, log, XML and provenance](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/table_checks/).
All post-edit executions are marked solver-dirty validation checks, not
reported baseline comparison fits. Their evidence remains uncommitted until
the coordinator reviews the full solver diff, as explicitly requested.

## CPU default after the edit

The post-edit CPU check completed the same schedule in 43.958 s
fit time (52.515 s guarded process time). All 385 complex
coefficients, 19-by-24 complex predictions and the 201-by-201 float material
image are **byte-identical** to the clean pre-edit CPU reference. All 15
stable record sections match, including decisions, residuals and work.
Clocks are excluded using the copied BRG comparison rule.

Peak child RSS 1.746 GiB; minimum available host
memory 18.543 GiB. No failure or limit stop.
[Run](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/cpu_after/),
[exact comparison](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/cpu_comparison.json).

## GPU default after the edit

The post-edit GPU check completed the same schedule in 5.314 s
fit time (8.216 s guarded process time). Every saved array
and all 15 stable record sections are **byte-identical** to the first clean
GPU reference, satisfying the frozen zero repeatability envelope exactly.
No threshold was changed and no extra fit was needed.

Peak child RSS 1.826 GiB; minimum available host
memory 19.019 GiB. No failure or limit stop.
[Run](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/gpu_after/),
[GPU comparison](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/gpu_comparison.json).

## Full suite and pre-commit review

CUDA-visible `pytest/bem_inverse`: **121 passed, zero skips,
failures or errors**, 74.209 s pytest time. Guarded wall
time 75.596 s; peak child RSS 1.945 GiB;
minimum available host memory 19.193 GiB.
[Suite log, XML and receipt](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/suite_after/).

All **5/5 planned default fits** are complete. Total guarded check time is
**281.378 s**, within the one-hour budget.
Peak child RSS over all checks was **1.945 GiB**;
minimum available memory was **18.543 GiB**.
No failures, tuning reruns, threshold changes or additional solver edits.

All three pre-edit solver source-hash maps agree. All four post-edit checks
(table check, CPU/GPU defaults, full suite) also agree. Only the three approved
Python files differ. The paired default remains exact on CPU and GPU; table
predictions and derivatives agree much more closely than the fixed 1e-10 limit.
[Machine-readable summary](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/verification_summary.json).

The [complete solver/docs/tests diff](../../../../results/bem/baseline_data/gpu_table_path/2026-11-18/solver_review.diff)
is saved for coordinator review: three solver Python files, solver README,
information chain, updated refusal test, and the new eight-case GPU test.
SHA-256: `c7266b91c6957c1384ffda35565821e490328f3209dac3e790b00d12004b86fa`.
The three pre-edit reference commits are pushed: `59dd6b919`, `6a5258daa`,
`78f084ca9`. Post-edit code and evidence are held uncommitted as requested.
Solver lock is still held. No new unknowns; commit and release need the
coordinator's diff review, not a new user decision.
