# TOP-022 — fresh direct four-frequency recovery test

**Approval status:** APPROVED under the 2026-09-15 user instruction “cp first. then i approve you to finish the rest”.
**Execution status:** NOT STARTED.
TOP-020 is complete, numerically qualified and fails recovery; see [results](../01_results.md).
Owner/reviewer: Codex `/root`; owner review, no independent review claimed.

Question: does training on all four frequencies immediately after the same
fresh automatic H controller avoid the poor recovery of the staged entry path?
This is a protocol comparison; a different result alone does not prove a unique
local-minimum or derivative-error explanation.

Run H freshly from the original distant circle, at the same
64/128 nodes and 4000 calls / 600 seconds. Check event margins and monotonicity;
require a normal training-only handoff. Compare the resulting endpoint hash with
TOP-020 for source/input reproducibility, never load its optimized state to fit.

Use the same K9 zero padding, 256/512 nodes, observations, material, gauge,
feasible set, optimizer and tolerances. Begin directly with the full
0.5/0.75/1/1.25-GHz objective. One declared stage 4, quota 8000 including its 12
endpoint solves; initial scoring 12. Continuation ceiling 8012 / 7200 seconds,
maximum 22 updates with complete models and the unchanged stopping rules.
No new data, truth/count input, extra restart, gate relaxation or best endpoint.
Total ceiling 12012 calls / 7800 active seconds, matching TOP-020's total caps.

Record the changed allocation of the same solve budget and frequency exposure.
Compare prescribed final recovery, numerical qualification, convergence and cost
against the completed TOP-020 staged result, preserving that negative evidence.
Pass supports a revised full-suite candidate contract. Failure calls for a
bounded stationarity/derivative/basin diagnosis before further expensive work.
The already prepared TOP-021 staged suite must remain undispatched if its
TOP-020 release gate fails; do not relabel it as a new protocol silently.

## Owner source review and file/API map

Accept the same original circle, 24-pair observations and verified H topology
prefix. All 197 TOP-020 sources were unchanged during its run; its final
boundary/IoU/development failures are real measured outcomes, not the corrected
reporting-counter field. TOP-018 remains positive under its different saved
COMMON entry. The evidence supports testing the full protocol, not declaring a
proved local minimum or estimating the extra work needed for convergence.

Accept immediate full-frequency refinement as the only new numerical protocol.
Keep the same total cap and per-stage optimizer maximum of 22 updates; the full
budget is now available to one four-frequency stage instead of four successive
active sets. Report this changed allocation explicitly. No altered FD step,
acceptance margin, regularizer, random restart, representation or solver.

Add `experiments/top022/run.py`, reusing TOP-020 input checks, count-independent
handoff, endpoint scorer and H ledger, and the existing TOP-017 schedule with
an explicit single-stage plan `(4, 8000)`. Source/input/test freezing and the
new experiment contract remain owned by this driver. Reuse TOP-020's no-solve
reporter through a small change to read stage numbers/quotas and the experiment
label from the frozen contract; its default TOP-020 result must still replay.
This is a reporting hook, not a change to any physical or optimizer interface.
Add focused tests for the immediate four-frequency exposure, unchanged fresh
handoff, failed-release gate, total cap, and replay of the single-stage result.

Reject dispatch of the already prepared TOP-021 staged suite: its evidence gate
failed. A passing TOP-022 result requires a newly declared full-suite candidate
contract, rather than silently changing TOP-021's staged intervention.
