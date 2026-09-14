# User-requested engineering follow-up — 2026-09-14

Authorization: the user asked to implement the three engineering actions discussed
after TOP-017: saved-state resolution diagnosis, complete numerical-failure
checkpoints, and a bounded fresh circle-to-ellipse/star integration test. This is
a follow-up to the completed work, not an automatic successor campaign. Work
stays on `feature/ordered-boundary-nystrom` in the original checkout. No new
branch/worktree, literature search, merge inverse, or two-star continuation.

## Question and bounds

1. Do 256/512 predictions qualify the two-star F retained state, its exact
   rejected candidate, and the S stage-3 endpoint at the unchanged tolerances?
   Reconstruct the rejected candidate from its archived base and step and require
   its archived hash. Evaluate each state at 128/256/512 and all six existing
   frequencies: 54 solves, hard ceiling 72 solves / 300 seconds. No optimization.
2. Save full base/candidate coefficients, production/refined predictions, losses,
   thresholds, settings and work when numerical candidate qualification fails.
   This does not change acceptance or numerical defaults.
3. Run one fresh central-circle inversion: the existing H topology controller
   at 64/128, followed automatically by exact K9 zero-padding and the existing
   cumulative 0.5/0.75/1/1.25-GHz continuation at 128/256. No archived optimized
   state, supplied target count, truth-guided event, restart or best-stage choice.
   Topology: at most 4,000 forward/TD frequency solves and 600 seconds.
   Continuation: quotas 1,000/1,250/1,750/4,000; total at most 8,012 solves
   including initial scoring, and 1,800 seconds. Single worker, single-thread
   BLAS. Each hard stop ends that part; no extension or retry ladder.

The first continuation stage uses the TOP-017 complete-model/step reservation,
now consistently applied to all four stages. It is not promised to reproduce
the older TOP-016 quota endpoint exactly. Numerical qualification may stop the
run; endpoint truth/development scores may not select its trajectory. Both parts
are independently useful; the far-state audit does not choose central settings.

## File/API map and validation

- `run_top017.py::fit_stage`: failure-only serialization of already computed
  data; keep the training-only interface, checkpoints and rejection behavior.
- `run_top017.py::run_schedule`: optional declared stage plan, defaulting to the
  original stages 2–4. Allow the integration driver to include stage 1.
- `run_topology_recovery_followup.py`: bounded saved-state audit and fresh
  topology/continuation orchestration using existing solvers and observations.
  Freeze source/input hashes before numerical work; refuse existing outputs.
- Focused tests: exact failed-candidate replay/hash; diagnostic data matches the
  rejected state while accepted checkpoint survives; all four stages receive
  their declared frequencies; hard stops and budgets; automatic handoff without
  truth/count arguments; TD work accounting and source/input guards.

Retain complete new artifacts separately from sealed TOP-008/016/017 bundles.
Report numerical qualification separately from shape success. A successful
single-scene fresh run is not a suite pass or general policy promotion.
Validate and commit locally; pushing awaits a new `cp` or push instruction.

## Integration repair discovered during validation

The first central attempt stopped after 80 physical API attempts / 4.105 seconds:
the inherited TOP-017 ledger wrapped a routine rejected topology candidate's
`MultiComponentTopologyError` as `PhysicalFailure`, preventing the controller's
normal geometry-refusal handling. This was an instrumentation integration defect,
not evidence against recovery. Preserve that attempt under `central/`.

Add a topology-only exception-preservation option (TOP-017's default remains
unchanged), with a regression test using the actual exception class. Execute the
corrected validation under `central-validated/`, deducting the first attempt's
80 calls and measured wall time from the original topology ceiling. The original
4,000/600 and continuation bounds remain binding across both attempts. Refused
physical API calls stay charged and are separately identified in work accounting.
This correction does not change topology candidates or numerical acceptance.
