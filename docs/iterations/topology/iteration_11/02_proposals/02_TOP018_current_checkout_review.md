# TOP-018 installation and current-checkout review

Reviewed 2026-09-15 by Codex `/root`. This is a document/source and saved-artifact
review, with no physical solves, inverse runs, numerical-code changes or new
test results. No independent-agent review is claimed.

**Decision: accept the bounded TOP-018 proposal with the provenance reconciliation
below. Execution remains PROPOSED — NOT APPROVED FOR EXECUTION / NOT STARTED.**
The user's instruction was “new zip up. git pull, then follow it”. The package
separately requires explicit experiment approval before implementation and
numerical dispatch. Its conditional audit and two trials remain one approval.

## 1. Installation and intervening work

- Read root `AGENTS.md`, the shared iteration workflow and implementation
  principles, the TOP-017 staged-execution amendment, the supplied review/plan,
  and the TOP-017 and engineering closeouts.
- Verified all four entries in the ZIP's `SHA256SUMS.txt`. Both destination
  documents and the TOP-018 result ID were unused before installation.
- Installed the two supplied documents in iteration 11. Preserve the supplied
  review as a review of its stated historical revision; this document records
  the later evidence. Leave iteration-11 `01_results.md` and old bundles intact.
- The user-requested pull merged the remote ZIP commit `ad1913f` with the three
  existing local commits. Current reviewed HEAD is
  `c2a1f2203e2ed6188b5841027dae8853a3035e0e`; package-reviewed HEAD remains
  `243fe19a7937dd519c4a55bc3e04d464ee04d2a4`. Use the existing checkout/branch.
- Reviewed `c4f00ca` (failure snapshots and fresh recovery driver), `5aff98a`
  (topology-specific exception preservation/accounting), and `6a8e8a0`
  (validated follow-up evidence). These retain the historical node defaults and
  optimizer mathematics. The actual eventual TOP-018 measured source must be
  frozen separately after its implementation and tests.

## 2. Resolve the stale premises without repeating work

The [engineering follow-up][followup] already performed 54 frequency solves on
F_RETAINED, F_REJECTED and S_ENDPOINT at 128/256/512. It also completed a fresh
central-circle recovery. The supplied review's warning about a stitched
historical animation still applies to that animation; it no longer describes
the later fresh-run evidence. Preserve both records with their actual scope.

Saved-artifact checks completed in this review:

- All entries in the resolution artifact manifest match. All **571** historical
  file hashes recorded by that audit match the current files.
- Of its **194** recorded numerical-source hashes, **192** match the current
  checkout. The two changed drivers, `run_top017.py` and
  `run_topology_recovery_followup.py`, match their recorded measured revision
  `c4f00ca`. Their subsequent diffs concern topology exception handling,
  prior-attempt integrity and the central repair budget. The saved-state
  `resolution`, `archived_states`, prediction, acquisition, geometry, solver,
  discrepancy and acceptance paths remain unchanged.
- COMMON matches `reuse.json`, both TOP-017 metrics/initial-state records and
  both TOP-016 final states, coefficient for coefficient. Its normalized hash is
  `8fa832c90e40dd36ee4912ec924788d98ddff3390e28c57eef4d21b2a3101559`;
  IDs are `t001.birth` and `t003.birth`, both Cartesian K=9.
- F_RETAINED and S_ENDPOINT agree across terminal, accepted-checkpoint and
  follow-up audit records. The serialized F_REJECTED hashes to the unique
  historical numerical-obstruction candidate, with the matching retained base.
  Exact step/gauge replay is already implemented in `archived_states`; the new
  preflight must retain that assertion rather than use an unchecked last entry.
- Training data contain 24 pairs and the four prescribed frequencies. Their
  0.5-GHz complex column equals the original observation column. The linked
  acquisition/material file matches its recorded hash and the copied original
  observations. The audit and TOP-017 solve configurations match.
- Recomputed every saved discrepancy column from serialized complex predictions
  without forward calls. Maximum 256/512 discrepancy across all three states
  and six frequencies is `2.919667714351461e-11`, consistent with the saved
  qualification. This is verification of existing evidence, not a new audit.

**Accept prediction reuse under plan §A2.** Carry the exact state/configuration
and measured-source associations into TOP-018's manifest; report the 54 solves
as historical work. Do not charge them as new physical calls or claim a complete
new Phase A from them. COMMON's 512-node qualification and the two prescribed
directional checks remain missing. New mocked/geometry tests and the binding
release record also remain required. A later source incompatibility must be
handled under the existing reuse rule and cap, never silently ignored.

## 3. Compact API/file map for implementation after approval

| Existing code | TOP-018 use and required care |
|---|---|
| `run_top017.py::fit_stage` | Pass `(256, 512)` explicitly. Reuse FD/LM, feasible-side stencils, full-batch reservations and failure snapshots. Its caches are local to one fixed stage/configuration; start new calls for each arm/stage. |
| `run_top017.py::run_schedule` | Reuse the stages 2–4 quotas and typed transition rules. Its current hard-stop path skips scoring; the TOP-018 wrapper must perform affordable reporting-only scoring of a retained hard-stop endpoint when appropriate, while preserving the stop and prohibiting transition. |
| `run_top017.py::Ledger` | Use 256/900 for Phase A and 7,000/7,200 per arm. Preserve the 12-solve endpoint reserve and attempt/completion/failure counters. The wrapper must also retain one campaign deadline and total accounting across phases. |
| `run_top017.py::observations`, `run_top016_preflight.py::training_data` | Reuse frozen columns, paired acquisition and equal frequency weights. Only training data enter fitting. Verify source/material metadata before dispatch. |
| `run_top016_preflight.py::prediction`, `relative`, `feasible` | Use the existing forward and physical rules. `relative(a,b)` takes column L2 norms on axis 0 and divides by the higher-resolution prediction norm. Explicitly reject zero/nonfinite denominators. |
| `run_top016_screen.py`, `solvers/sdf_inverse/radial_topology.py` | Reuse the established gauge retraction and central/one-sided quotient formulas for only the first/last basis rows. Inherited steps are `1e-4` and `5e-5`; the two-scale relative derivative stability threshold is `0.25`. Retain numerical-floor and physical-displacement checks; no spectrum or direction search. |
| `run_top016_pilot.py::score`, `acceptance` | Reuse all six endpoint frequency checks, reconstruction gates and unchanged loss-gain rule. Bind new score/gradient records to exact state, active objective and both resolutions. Reuse Phase-A COMMON predictions for the common-start score when fully matched. |
| `run_topology_recovery_followup.py::archived_states` and saved resolution bundle | Reuse exact rejected-step recovery and verified predictions. Do not invoke either the old campaign or the fresh-central entry point. |

Add one small TOP-018 wrapper and focused mocked/geometry tests once approved;
leave historical drivers/defaults unchanged. Use the inherited residual builder
and its actual flattening/scaling rather than a new residual implementation.
Freeze resolved source/input hashes, including the new wrapper, without calling
the experiment-specific TOP-017 `freeze_inputs` compatibility whitelist.

The implementation review must resolve and test dispatch gating, identical
starts/resolutions, all seven §A0 test requirements, post-stop reporting,
campaign limits and cache provenance before any physical work. This source map
does not claim those tests or the future implementation review are complete.

## 4. Recommendation and next action

- **Accept:** the same common start for S/F, unchanged K=9, solver/optimizer,
  tolerances, schedule, caps, and one conditional release gate.
- **Accept with current evidence:** reuse the verified saved predictions and
  preserve the separately validated fresh central result. Neither result
  releases Phase B before the remaining Phase-A checks pass.
- **Reject:** restarting from unequal stopped endpoints, replaying central or
  common-prefix inversions, relaxing thresholds, changing numerical methods,
  or adding a resolution ladder, suite or automatic successor.
- **Defer:** merge-capacity/integration experiments and any new research ID to
  the single evidence-based decision at TOP-018 closeout.

Next action: obtain the package-required explicit TOP-018 approval, then
implement/test the wrapper and execute the existing conditional contract.
Approval covers Phase A and both Phase-B arms if released; no repeated approval
is needed for those same stages. No new branch/worktree, push or additional
merge is part of that contract. No iteration-12 results or TOP-018 numerical
bundle is created before execution.

[followup]: ../../../../../results/validation/topology/TOP-017-followup-20260914-engineering/README.md
