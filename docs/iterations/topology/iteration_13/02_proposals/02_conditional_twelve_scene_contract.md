# TOP-021 — conditional complete twelve-scene S/F integration comparison

- **Approval status:** APPROVED under the user’s remaining-work instruction.
- **Execution status:** NOT STARTED; TOP-020 failed recovery, so physical dispatch is blocked by its declared evidence gate.
- **2026-09-15 closeout:** preserve the prepared code and 18 mocked preparation tests. TOP-022 will test a revised entry protocol; this staged suite is not released by a result under a different protocol.
- **Owner/review:** Codex `/root`; owner review, independent reviewer unassigned.
- **Preparation:** orchestration and mocked validation may proceed in new
  `experiments/top021/` files while TOP-020 runs; no file in TOP-020’s source
  manifest may change. This preparation does not release numerical dispatch.

Draft while TOP-020 runs. Dispatch requires a verified TOP-020 fresh-recovery PASS.
User authority: 2026-09-15 “cp first. then i approve you to finish the rest”.

Question: does the candidate cumulative-frequency continuation improve the full
frozen scene benchmark against a matched single-frequency continuation control,
with a fresh automatic H topology prefix in every scene?

All twelve v1 scenes, original initial states, original 0.5/1.5/2.5-GHz data,
material/geometry settings and recovery gates remain frozen. This is a separately
named expanded-acquisition, continuation and budget comparison, not a rewrite of
v1 or a single-mechanism comparison against historical H.

Generate only missing 0.75/1/1.25-GHz observations, at 256 nodes with a 512-node
check, using the existing analytic boundary oracle. Preserve original columns
byte-for-byte. Reuse the three existing expanded-acquisition observation records
for central, two-star and merge, with hashes. Oracle budget: 72 frequency solves /
300 seconds; failed oracle qualification stops suite dispatch.

For each scene, run H freshly on 0.5 GHz at 64/128 nodes (4,000 attempts / 600 s).
The identical prefix is computed once and shared by the two matched arms. Charge
it once in actual campaign work and include it in each arm's standalone cost;
never add shared work twice in campaign totals. Record per-scene prefix failures
for both arms and continue the remaining scenes.

Declare a target-free capacity rule: a single returned component gets K17;
multiple returned components each get K9. This retains the qualified single-body
merge capacity and the qualified multi-body two-star/central capacity while
balancing the number of shape parameters. It depends on the controller result,
not the true count or scene name. The suite qualifies this rule; prior focused
experiments do not establish it as a universal policy. Exact zero padding only.

Both S and F use 256/512 nodes, identical optimizer/gauge/feasible set, four
stage quotas 1000/1250/1750/4000 and 8012 total calls / 7200 seconds per arm.
S uses only 0.5 GHz all four stages; F uses cumulative .5/.75/1/1.25 GHz. Truth
and evaluation only score prescribed endpoints. Stage 4 remains final. No
best-stage choice, retries, tolerance relaxation or gate-dependent early success.

One owner; at most four isolated numerical subprocesses, one scene per process,
S then F sequentially within each scene. Single-thread BLAS; measured sources
frozen throughout. Campaign hard cap: 240360 calls including oracle work;
4-hour wall watchdog. Each scene retains partial work/checkpoints on any hard
stop; attempt the whole matrix unless the campaign hard ceiling prevents it.

Report all 24 arm rows, topology/event/monotonicity gates, numerical qualification,
count/geometry/training/development gates, convergence versus quota completion,
parameter dimensions, attempted/completed/refused calls, actual and standalone
costs. Reference historical H results separately. Central, merge and two-stars
are named regression controls. Preserve adverse rows and original bundles.

Adopt only on a measured recovery/precision/cost improvement without a required
regression. A complete campaign with failed recovery gates is a completed
measurement, not full topology qualification. Diagnose any remaining required
failures before broader promotion, under a separately recorded bounded successor.

## File/API map and owner review

Accept the existing H prefix/ledger, TOP-017 fit and schedule, TOP-020 endpoint
scorer, and TOP-019 scalar saved-prediction replay. Add one suite driver and one
saved-artifact reporter under `experiments/top021/`, with focused contract tests.
No physical solver, topology candidate rule, optimizer or shared default change.
Input preparation generalizes the prior three-scene observation format to the
full immutable scene list. The capacity rule is implemented in a training-only
handoff and tested on different returned counts. Isolated subprocesses avoid
sharing temporary numerical instrumentation across simultaneous scenes.

Accept four-process numerical concurrency as a separately declared suite
setting; do not compare wall times as a controlled speedup. Stage-1 S/F hashes
must match before F stage 2. Hard prefix failures stay in both rows. Refuse all
physical dispatch if input/source/test/TOP-020 evidence checks fail.

Validation covers all twelve input IDs and original columns, oracle reuse and
fail-closed qualification, target-free capacity, exact shared stage-1 behavior,
per-phase and campaign budgets, child-process failures, numerical versus
recovery gates, saved prediction replay and all-row reporting. Freeze sources
and test records only after TOP-020 closes and any reporting corrections are
finished. The next iteration’s agreed plan will link this prepared contract and
record the actual TOP-020 release evidence before the suite starts.
