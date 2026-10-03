# Phase 2 entry correction, before execution

During Phase 1, code review found that the general `runner.fit` adapter in
`fm003.continuation` would run a new all-frequency original-start audit on the
stage-2 winner. That adds a gate before stage 3, which the frozen suffix does not
contain. No Phase 2 fit had been run, and no truth scoring from Phase 1 had occurred.

Use `python -m experiments.cleaned_interface.fm003_suffix` for Phase 2. It carries
the archived CI-001 original-start qualification as provenance, charges no new
entry-audit work, enters stage 3 directly, and performs the ordinary final audit.
The suffix operations, optimizer, 13,250-unit/1,784.5-second remaining fit budgets,
900-second phase deadline, winner selection, and recovery contract are unchanged.
The receipt explicitly labels the original-start audit as historical, not performed
at the stage-2 endpoint. This supersedes the Phase 2 invocation in `04_execution.md`.

The original implementation seal and all Phase L/0/1 evidence remain immutable.
The suffix adapter has a separate source/input receipt and source archive. Its
bounded test checks that the first audit call carries historical qualification
without evaluating a new gate, and the final call executes the real audit.
