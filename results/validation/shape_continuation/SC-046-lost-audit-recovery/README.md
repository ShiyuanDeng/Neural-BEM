# SC-046 — separate recovery of one lost audit result

**QUEUED, 2026-09-26.** [Frozen contract](plan.md), [manifest](manifest.json),
[output-writer preflight](preflight.json).

SC-045's first result was lost to a missing output directory after the
numerical audit returned. Its execution failure and up-to-130-unit unknown
cost remain recorded there. This study performs one additional audit of the
same original kite/boundary endpoint after the other SC-045 attempts finish.
All numerical code, inputs, tests and limits are unchanged. Additional cap:
130 units, 900 seconds. Results are also printed to the captured log before
the file write. Original failure flags and original study gates never change.

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-046-lost-audit-recovery/run.py prepare
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-046-lost-audit-recovery/run.py
```

The host already has this job queued. SC-043 waits for its terminal record;
do not launch duplicates. This is operational recovery, not fitting or a new
strategy selected after observing geometry.
