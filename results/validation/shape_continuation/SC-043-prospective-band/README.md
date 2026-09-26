# SC-043 — prospective action diagnostic versus simple release rules

**QUEUED, 2026-09-26.** No performance conclusion yet.
[Frozen contract](plan.md), [source/input hashes](manifest.json),
[available outcome table](TABLES.md).

Six development starts, three policies, three decisions per path. The fixed
rule always releases six update modes; the stagnation rule releases when the
last stage stalls; the atlas rule releases when the larger complete-update
model adds at least 10% of current loss in predicted decrease. All use the
same initial cleanup and subsequent K192 state.

Each block has 304 work units. The atlas spends 76 on N/2N field and full
Jacobian qualification, leaving 228 for fitting; the simple rules retain
304. No diagnostic cache reuse is claimed. Every policy gets the same
endpoint audit. Failures are retained in the 18-path denominator.

The frozen claim gate requires a geometric-mean RMS ratio at most 0.8 against
both controls, no RMS/Hausdorff ratio above 1.25 (0.01 mm floors), no additional
failure, and qualified diagnostics and endpoints. Failure rejects this
specific rule and cost model as superior; it does not test every possible
atlas policy.

From the repository root:

```bash
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-043-prospective-band/run.py run --workers 4
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-043-prospective-band/analyse.py
```

The runner never overwrites a run directory. The current host has
the same frozen jobs queued through `dispatch.py` after SC-042 and the separate
SC-045 timeout-qualification follow-up and SC-046 lost-result recovery. It shares at most six numerical workers
with SC-044 and allows one heavy kite job alongside other paths. The
[resource-only tail amendment](scheduling_tail.md) permits two kite paths
only after all other PDE paths finish, with a memory admission gate. Do not launch
a duplicate while the queue is active. Analyses consume
portable JSON. All hashed sources and inputs are tracked in Git.

The one preflight revision is preserved in `preflight_v1/` and described in
the contract/manifest. It occurred before any policy diagnostic or fit.
