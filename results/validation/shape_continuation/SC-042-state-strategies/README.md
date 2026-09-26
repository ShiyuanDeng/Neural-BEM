# SC-042 — matched cleanup and state-cap strategies

2026-09-26. **RUNNING.** Owner: Codex; independent reviewer: unassigned.
Authorized by the user's instruction to execute and continue through successive
research obstacles. Frozen comparison commit: `921325e`.

[Contract](../../../../docs/iterations/shape_frequency_continuation/iteration_23/03_plan.md)
and [mechanism distinctions](mechanism.md). First wave: four treatments on
star/kite; second wave: the remaining four development shapes. No result is
promoted from intermediate accepted states.

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
