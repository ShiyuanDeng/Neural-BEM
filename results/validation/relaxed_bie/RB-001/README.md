# RB-001 — accuracy-controlled continuation

All four FM-002 stops reproduced. Refinement and smaller steps each independently removed every immediate obstruction. All four tails then continued under the same opt-in response, with historical work/time and stage quotas retained.

| Case / arm | RMS before → after (mm) | Hausdorff upper (mm) | Full / paired recovery | Audit 512/1024 · 1024/2048 | Outcome |
|---|---:|---:|---|---|---|
| C / R0 | 23.032 → 22.957 | 60.257 | False / False | False · True | COMPLETED_SCHEDULE |
| C / R1 | 10.834 → 9.8494 | 30.128 | False / False | False · True | TRIAL_WALL_LIMIT |
| Star / R0 | 7.6679 → 7.478 | 16.597 | False / False | False · True | COMPLETED_SCHEDULE |
| Star / R1 | 5.5527 → 5.5974 | 19.801 | False / False | False · True | COMPLETED_SCHEDULE |

![All four returned endpoints](endpoints.png)

## Work and execution

| Case / arm | Historical units | New fit units | Historical + new fit seconds | Fresh total seconds |
|---|---:|---:|---:|---:|
| modal__c13.3__development_c / R0 | 6342 | 1824 | 660.93 | 373.09 |
| modal__c13.3__development_c / R1 | 2641 | 5822 | 1800.08 | 1196.34 |
| modal__c13.3__shifted_star / R0 | 6291 | 2052 | 717.77 | 408.15 |
| modal__c13.3__shifted_star / R1 | 6832 | 1900 | 1160.83 | 373.71 |

Stage A: 3230 dispatched units, 220.78 s. Qualification: 252.65 s. Continued fitting, audits and scoring: 2353.79 s. Total recorded numerical execution: 2827.22 s of the 10,800 s ceiling.

Each continuation retains the 13,412-unit and 1,800-second fitting cap, including archived work and time. Replay and qualification are separately reported diagnostic overhead. Initial audits are reused as historical evidence; each endpoint gets a fresh final audit and, after promotion, the original N512/1024 audit as well.

N512/1024 fitting uses four frequency workers; N1024/2048 fitting uses one. Precision remains double/complex double. All runs are sequential. Backend timings, solver residuals, peak CUDA memory, process RSS, fallbacks and GPU process inventories are in each result receipt. These are single-run diagnostic timings, not matched speedup measurements. The external dispatch monitor counts public evaluation/derivative calls; the fit ledger also charges the frontier’s internal reciprocal batch. The latter governs the fitting cap.

## Evidence and reproducibility

- [Stage-A summary](stage_a.json) and [original archive verification](archive_verification.json).
- [Qualification result](qualification/result.json), [tests](qualification/tests.log), [qualified source seal](qualification/manifest.json), [source differences](qualification/source_changes.patch).
- [Continuation summary](continuation.json), [comparison](comparison.json), and per-case receipts under `runs/`.
- Source/input/plan archives, full replay fields, reconstructed candidates and exact resume states are retained. Original FM-001/FM-002 files are unchanged.
- Rebuild the comparison with `python -m experiments.relaxed_bie.report` in the documented EMNerf environment.

Recovery uses the existing full-matrix and unchanged paired contracts: RMS ≤1 mm, Hausdorff upper ≤2 mm, per-frequency residual limits and a passed numerical audit. No truth-based iterate selection is used. A resource or numerical stop is reported by its actual reason.
