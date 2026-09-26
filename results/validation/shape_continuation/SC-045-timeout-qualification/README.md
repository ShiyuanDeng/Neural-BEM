# SC-045 — qualify unchanged endpoints after audit timeouts

**COMPLETE, 2026-09-26: four qualified endpoints, one lost-result execution failure.** [Frozen follow-up contract](plan.md),
[source and endpoint hashes](manifest.json), [host pressure snapshot](host_pressure.json).

Five original audits retain their `TrialWallLimit` failures. This separate
study repeats only endpoint qualification, once per fixed state, with the
same grids, tolerances, derivative test, 130-unit cap and 900-second limit.
It neither reruns fitting nor replaces any original result or gate flag.

The audits run serially in fresh processes after SC-042 completes. SC-044
retains its two workers; SC-043 starts after this follow-up terminates.
Both original and additional work are reported. The numerical test is the
original `SC-042.audit` function, unchanged.

**Execution failure retained:** the first audit returned from the numerical
routine but failed to write because `audits/` had not been created. Its
numerical result and ledger were lost. [Record 1](audits/1.json) is therefore
an output failure, not a numerical pass or tolerance failure. Its actual cost
is unknown, bounded by 130 units; a stored zero denotes missing measured
accounting and must not be interpreted as zero computation. The traceback
remains in `run.log`. Creating the directory fixes subsequent output without
changing frozen numerical code. The remaining four original attempts passed,
each costing 114 units: kite/cap, development-C/boundary, lobed-clean/cap and
lobed-noise-0/boundary. Their measured total is 456 units, plus up to 130
unrecorded units from the first attempt. [Summary](summary.json).

[SC-046](../SC-046-lost-audit-recovery/README.md) freezes one separately charged
recovery of this lost result. The first SC-045 failure remains unchanged.
SC-043 waits for both studies to terminate.

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-045-timeout-qualification/run.py prepare
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-045-timeout-qualification/run.py
```

This sequence has terminated. Existing follow-up records are never
overwritten; the failed first follow-up remains failed.
