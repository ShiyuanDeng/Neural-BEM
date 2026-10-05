# RG-001 — execution in progress

Approved 2026-10-05 on the existing `feature/shape-frequency-continuation`
branch. The [pre-registered plan](03_plan.md) governs the comparison and stops.

The opt-in `resolution_gate='decision'` retains the existing cross-resolution
loss-gain decision while recording field-tolerance overshoots. The default
remains `absolute`; endpoint audit tolerances and recovery gates are unchanged.

Stage 0 is running before fitting. Its first attempt stopped on a driver cleanup
error after one completed truth check; that evidence and original sources were
committed and pushed before repair. See `RG-001/failed_stage0_01/` and the
[execution record](04_rg001_execution.md).

Stage 1 focused tests: 35 passed, covering gain agreement, rejection and
backtracking, fatal non-finite/failed evaluations, default finite paths,
policy plumbing, and unchanged under-resolution rejection by the endpoint audit.
Regression suites, four saved killing-trial replays, and fresh control
reproducibility remain pending. Stages 2–4 have not opened. No recovery or
classification claim is made while those checks remain incomplete.
