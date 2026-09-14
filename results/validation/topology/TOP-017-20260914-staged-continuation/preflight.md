# TOP-017 implementation preflight and independent review

Owner: Codex `/root`. Reviewer: Codex `/root/top017_review`, read-only review requested 2026-09-14. Review pending; physical work has not started.

Verified base: `9ad3c8b191c7f1130764c0476480290b0f6a6e4a`. No intervening source changes. Original feature and TOP-016 worktrees were clean and preserved. Package source: `739a8c1:neural_bem_TOP017_handoff.zip`; all SHA256SUMS passed. No existing destination collisions.

## API/file map before numerical edits

- `run_top016_preflight.py`: reuse frozen data builder, prediction, geometry checks and projection procedure; preserve historical source.
- `run_top016_pilot.py`: reuse acceptance and endpoint scoring; preserve historical stage-budget behavior.
- `solvers/sdf_inverse/radial_topology.py::run_multiradial_fd_inverse`: unchanged LM/FD mathematics and public defaults. Declare one optional diagnostics callback to expose complete Jacobian counts before any step, candidate attempts and feasibility refusals. This permits an immediate hard stop on unresolved derivatives and complete exposure accounting without a second optimizer.
- `run_top017.py`: new experiment-specific typed ledger, source/input verification, bounded Phase-A audit, training-only stage adapter and four continuation trials. Only accepted states transition; endpoint score/state hashes must match.
- `summarize_top017.py`: rebuild merge/principal scorecards and decision from JSON only.
- `pytest/sdf_inverse/test_top017.py`: mock forward, clock, batches and scorer to test transitions, hard stops, exposure, failed-attempt accounting and state/diagnostic binding; existing focused tests qualify defaults.

Stage 2 is the first training intervention: F uses 0.5/0.75 GHz; S retains only 0.5 GHz. For q=34 the F complete Jacobian bounds are 136/204/272 frequency solves. Each stage additionally needs initial objective m, at least candidate production m plus up to 2m refined validation, and 12 endpoint solves. Quotas 1250/1750/4000 exceed these bounds. Individual forwards reserve a whole objective; Jacobians reserve their full maximum batch. Stage quotas may advance only after endpoint feasibility/numerical qualification; total solve/time limits and all unsafe interruptions hard-stop.

Physical exceptions will be translated into a distinct counted PhysicalFailure so the optimizer cannot swallow them as candidate infeasibility. Unresolved derivatives are exposed at the new callback before stepping. Last gradients bind exact serialized state hash, active frequencies, equal-frequency residual normalization and production nodes; stale values remain historical. No terminal Jacobian is run just to fill a missing diagnostic.
