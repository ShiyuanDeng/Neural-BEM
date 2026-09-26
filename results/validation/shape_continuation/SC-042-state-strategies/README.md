# SC-042 — matched cleanup and state-cap strategies

2026-09-26. **COMPLETE: 24/24 paths.** Owner: Codex; independent reviewer: unassigned.
Authorized by the user's instruction to execute and continue through successive
research obstacles. Frozen comparison commit: `921325e`.

[Contract](../../../../docs/iterations/shape_frequency_continuation/iteration_23/03_plan.md)
and [mechanism distinctions](mechanism.md). Four treatments on star/kite
were launched first. After inspecting the returned star paths and unchanged
kite, `dispatch_controls.py` starts the other four shapes in freed worker
slots. The six-worker host ceiling is shared with SC-044. No result is
promoted from intermediate accepted states. [Final original tables](TABLES.md)
retain one fitting numerical stop and three endpoint audit timeouts. All
125 saved-evidence checks pass. Fitting cost is 19,874 work units; original
endpoint audits cost 2,663 units.

One-off cleanup passes the frozen six-case development gate: geometric-mean
RMS ratio 0.91466, worst floored RMS/Hausdorff ratio 1.000054, and no additional
fitting failure. This is a development-suffix result, not a universal policy.
Its common-work RMS ratio is 0.98461. The larger terminal gain partly reflects
continuing after the unchanged kite stops numerically (760 versus 1,710 units).
At a common 760-unit ceiling the kite RMS improves by 8.9% and Hausdorff by
54.8%; further fitting improves RMS to 0.02789 mm with Hausdorff 0.14120 mm.

Star, circle, peanut and hook give meaningful ties between the state
strategies. On the development C, cleanup improves Hausdorff from 0.04068 to
0.03354 mm, with RMS below the 0.01 mm comparison floor. Across all six cases,
once/boundary/cap geometry is within the declared 5% tie band. Recurrent
restriction has not earned an advantage on these suffixes. Boundary and cap
fail their original gates because of audit timeouts; separate qualification
must not erase those failures.

[Geometry](geometry.pdf), [geometry versus fitting work](geometry_by_work.pdf),
and [kite artifact detail](kite_feature.pdf) show the complete comparison.
The cleanup strongly reduces but does not eliminate the kite's spurious
curvature; its true tips are not perfectly recovered. See [mechanism and
intrinsic-curvature measurements](mechanism.md).

The kite boundary/cap and C boundary endpoint audits hit their wall limits
during a host memory-pressure event. Their failed original flags remain.
[SC-045](../SC-045-timeout-qualification/README.md) records independent serial
qualifications of the identical endpoints with the original tolerances and
ceilings. These are qualification timeouts, not observed tolerance violations.

All fitting inputs and starting curves are committed JSON. Each arm preserves
its configuration, intentional cleanup jumps, all accepted states, trial and
acceptance histories, endpoint numerical audit and post-run geometry scores.
`analyse.py` rebuilds comparisons and evidence checks without a field solve.

Run from the repository root with the EMNerf Python and `PYTHONPATH=solvers:.`:

```
python results/validation/shape_continuation/SC-042-state-strategies/run.py prepare
python results/validation/shape_continuation/SC-042-state-strategies/run.py run --cases circle_to_star kite --workers 6
python results/validation/shape_continuation/SC-042-state-strategies/run.py run --cases wrong_circle circle_to_c peanut hook --workers 6
python results/validation/shape_continuation/SC-042-state-strategies/analyse.py
```

Existing arm folders are never overwritten. A resumed dispatch skips them;
partial or failed folders must be investigated rather than silently rerun.
No solver or production-default changes. The benchmark permits work-unit
comparisons; elapsed times share a host and are not controlled speed tests.

`regularity.py` measures uniform-arclength curvature spectra and the true
star/kite tips after fitting. The stored-coordinate Fourier cutoff is not an
intrinsic curvature constraint. The campaign's [claims review](../../../../docs/iterations/shape_frequency_continuation/iteration_24/02_claims_review.md)
also distinguishes established filtering/continuation ingredients from the
prospective decision-policy claim being tested in SC-043.
