# SC-046 — separate recovery of one lost audit result

**COMPLETE, 2026-09-26: qualification passed.** [Frozen contract](plan.md), [manifest](manifest.json),
[output-writer preflight](preflight.json).

SC-045's first result was lost to a missing output directory after the
numerical audit returned. Its execution failure and up-to-130-unit unknown
cost remain recorded there. This study performs one additional audit of the
same original kite/boundary endpoint after the other SC-045 attempts finish.
All numerical code, inputs, tests and limits are unchanged. Additional cap:
130 units, 900 seconds. Results are also printed to the captured log before
the file write. Original failure flags and original study gates never change.

The [saved result](result.json) passed at 114 additional units: maximum field
discrepancy 4.47e-15, maximum Jacobian-column discrepancy 5.94e-14, and
full-update finite-difference error 3.17e-10. SC-045/046 therefore have
570 measured additional units, plus up to 130 unrecorded units from the
lost first attempt. All five original timeout endpoints now have separate
passing numerical evidence. [Summary](summary.json).

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-046-lost-audit-recovery/run.py prepare
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-046-lost-audit-recovery/run.py
```

This job has terminated and released the SC-043 queue. Do not launch
duplicates. This is operational recovery, not fitting or a new
strategy selected after observing geometry.
