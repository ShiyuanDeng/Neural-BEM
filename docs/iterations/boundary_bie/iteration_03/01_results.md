# BIE-004 — coupled analytic Jacobians qualify and reduce cost

2026-09-15. These completed results open Boundary–BIE iteration 03.
Owner/reviewer: Codex / self-review; no independent reviewer claimed.

**BIE-004 passes its fixed-topology accuracy and operational cost gates.**
The [iteration-02 contract](../iteration_02/03_plan.md) extended the existing
analytic self-interface derivative through both directed cross-object
interactions, incident fields and receiver operators. All implementation stays
under `experiments/bie004_multi_derivative/`; shared numerical source is unchanged.

On TOP-018 COMMON and TOP-022 terminal two-star states, the complete
34-direction residual Jacobians at 1.25 GHz agree with gauge-retracted central
FD to 1.414e-7 and 1.405e-7 relative error. All 1,008 scaled operator comparisons
pass. Selected directions qualify at both 0.5/1.25 GHz and 256/512 nodes per
object; mixed-direction Taylor tests show the expected second-order trend.

Three paired terminal-state timings, including fresh geometry, assembly,
factorization, derivative work and evaluation, give **26.249 seconds analytic
versus 49.083 seconds FD**, a **1.870x median speedup** with nonoverlapping
ranges. Each full Jacobian uses **1 versus 69 factorizations** and **35 versus
69 RHS batches**. All 24 source RHS are retained in both arms. Timings were
run sequentially, with no other repository numerical worker detected at arm
boundaries. This establishes a local sensitivity-cost improvement.

Measurements, complete saved Jacobians, operator/refinement/Taylor results,
timing ranges, budget ledger and limitations live in the
[BIE-004 result bundle](../../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md).
The [saved-table audit](../../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/reporting_validation.json)
replays the primary errors and verifies unchanged sources/inputs. The initial
test-input failure is preserved and counted; no physical formula or scientific
gate was changed to obtain the result.

## Scope and single next recommendation

**Prepare one opt-in integration and matched inverse validation**, coordinating
shared-file changes with topology's measurement windows and keeping existing
defaults until that comparison passes. No inverse or successor was executed by
BIE-004. This result does not establish improved shape recovery, all-frequency
inverse qualification, derivatives of topology events, general re-gauging,
lossy/magnetic media, or material/source sensitivities.

The BIE-002 negative modal-compression result remains unchanged. BIE-004 uses
the same Kress formulation and nodal field representation.
