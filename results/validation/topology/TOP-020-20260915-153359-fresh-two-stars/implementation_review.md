# TOP-020 pre-dispatch owner review

Reviewer: Codex `/root`, implementation owner. No independent review claimed.

- The experiment imports the existing H topology prefix, TD/forward ledger,
  K9 padding, parameter-step policy and TOP-017 staged optimizer unchanged.
  No shared solver/controller/default file is modified.
- Prefix training is exactly the frozen 0.5-GHz column. Handoff receives the
  returned state, controller settings and solve settings only. It checks all
  found components without testing against the true count. Truth and evaluation
  observations are used only by the outer endpoint scorer.
- The historical central helper's 128/256 feasibility pair is replaced only
  in this experiment's handoff with its declared 256/512 pair. This is the
  planned intervention, not a numerical tolerance relaxation.
- Every endpoint batch reserves twelve calls. Existing optimizer code reserves
  complete derivative/step batches and endpoint work, distinguishes planned
  quotas from hard failures, and resets optimizer state between stages.
- Topology refusals stay charged and classified separately from completed BIE
  systems. Independent passive controller totals are reconciled on return.
  Both phase ledgers install their existing hard wall timer.
- Input and measured-source hashes, source-bound mocked tests, original fresh
  central artifacts and source snapshots are checked before and after work.
  Existing outputs are refused. No saved optimized state is read for fitting.
- All complex endpoint predictions are saved. The no-solve reporter reuses the
  already tested scalar complex-error replay from TOP-019, verifies event
  margins, stage progression, gradient/state identities, acceptance and work.
  The reporter dependency is included in the source manifest.
- The final endpoint is stage 4; neither recovery scores nor a better earlier
  stage can change that choice. Numerical qualification and recovery are
  reported separately. Full-schedule convergence is not inferred from quotas.

Proceed only after the source-bound pre-dispatch test record is PASS. Preserve
any failure and stop the conditional suite unless the focused recovery passes.
