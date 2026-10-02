# Maintained-policy follow-up — closed by user scope change

The user closed the broad comparison because its source plan came from an outdated branch. All campaign schedulers and fit workers are stopped. Partial attempts and completed results are preserved; no further campaign is scheduled.

## Demonstrated value for the cleaned interface

The portable change is in `experiments/cleaned_interface/runner.py`:

- Stream each numerical audit by frequency, releasing coarse/fine matrix and LU handles once their prediction and reciprocal derivative are extracted. FD directions retain only prediction arrays.
- If the prescribed initial audit fails before localization/fitting, reuse that failure for the identical endpoint instead of repeating an expensive audit. The endpoint receipt records zero new work and links the original audit work.
- The objective, normalized stacking, every numerical threshold, random FD direction and solve/reciprocal work charges are preserved.

A fresh-process **single-curve**, five-frequency N512/1024 measurement gives:

| Audit | Total peak RSS | Wall seconds | Work units |
|---|---:|---:|---:|
| Original dense retention | 2211.1 MiB | 31.79 | 30 |
| Streamed | 565.3 MiB | 32.37 | 30 |

Peak RSS decreased **74.4%**. All saved numerical outputs are bitwise equal. These timings establish no speedup. Total RSS includes imports; a zero incremental streamed high-water mark means import-time memory dominates, not zero audit allocation.

The self-contained cleaned-interface tests cover nodal **and modal** services against the previous dense audit, plus no repeated audit for an unchanged failed start: **3 passed**. The coupled derivative/contract and existing interface tests also pass (**26 tests**). The parent separately validated the portable audit-only change without experimental adapters.

Evidence: [dense RSS receipt](audit_memory_dense.json), [streamed RSS receipt](audit_memory_streamed.json), [cleaned tests](cleaned_audit_validation.log), [broader local tests](final_validation.log). Reproduce the isolated measurement with `python -m experiments.cleaned_interface.audit_memory --method dense` or `--method streamed`, specifying `--output`.

## Completed experimental evidence

The real-only coupled execution used the actual maintained `CumulativePolicy` and `runner.fit`, with TD starts replacing inapplicable single-circle localization and the available four-frequency prefix replacing the unavailable 1.25 GHz input. It was an explicit adaptation, not a frozen-default reproduction.

`death` and `split` both completed the full schedule, passed both numerical audits and all original geometry/training/holdout gates, at **154 fit work units each**. They have identical fitting inputs and identical final coefficients, so they are **one independent input case**, not two independent successes. Their evaluation-only K192 validation-grid error was repaired by raising the grid to represent the retained band; the original errors and unchanged inverse endpoints are retained.

The full twelve-scene strategy comparison **did not finish**. The matched SCIF pilot was stopped during its path; it is not a completed SCIF result. No RLA/SCIF superiority or full-suite recovery claim follows. Earlier small controls remain separately labeled in the parent results directory.

Nine active fits were marked `STOPPED_SCOPE_CHANGE`, not numerical failures. Two earlier initial-audit time-limit attempts remain preserved, including the attempted longer-audit rerun. Last accepted states, stage checkpoints, audit receipts, source snapshots and logs remain available. Interrupted work counts are lower bounds and are not presented as complete ledgers.

All twelve additional damped observation sets had already qualified (120 setup solves). They contain additional information and are not evidence of equal-information superiority over real-only methods.

## Archive and scope

[closure_summary.json](closure_summary.json) inventories completed, stopped and unstarted configurations. [scope_closure.json](scope_closure.json) records the user's scope-change stop. [The implementation note](../../../experiments/exploratory_continuation/MAINTAINED_POLICY.md) describes the archived adapters and planned matched contract; its campaign commands are historical reproduction instructions, not pending authorized work.

The reusable cleaned audit fix and tests are separated from the broader experimental adapters and campaign archive. No existing maintained policy defaults or scene/acquisition catalogs were changed by the portable audit fix.
