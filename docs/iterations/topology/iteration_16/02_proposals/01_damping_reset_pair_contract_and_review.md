# TOP-024 — bounded continuation with and without an initial damping reset

**Approval:** APPROVED under the 2026-09-15 user “cp first. then i approve you
to finish the rest”. **Execution:** NOT STARTED. Owner/reviewer: Codex `/root`;
independent reviewer unassigned. Use the existing branch; no branch/worktree.

## Question and controls

TOP-023 found a better validated step at damping 1e-2. Does an initial damping
reset produce useful reconstruction within a short, matched continuation from
TOP-022's failed terminal state? The existing optimizer is reused unchanged.

Both arms start at exactly the same saved TOP-022 final state, before any
TOP-023 diagnostic candidate. This is a fixed-topology archived-start comparison,
not fresh automatic recovery. Retain K9 polar-gauge components, IDs, 256/512
nodes, 8-mm floor, original material/acquisition and all four training frequencies.
Reuse the exact shared saved initial endpoint score/predictions with provenance.
No new oracle or initial endpoint scoring solves.

The sole arm difference is **initial damping**:

- **A, baseline continuation:** 3.138105960899997e-15, the next value from TOP-022.
- **B, reset continuation:** 1e-2, selected by TOP-023's training-only gain/cost gate.

Keep damping decrease 0.3, increase 10, five damping trials, seven backtracks,
FD step 1e-4, existing step bounds, numerical/acceptance checks and stopping
tolerances. Both arms have **maximum 12 updates**, a smaller shared horizon
for this diagnosis. There is no damping floor, periodic reset, new optimizer,
changed representation or recovery-based endpoint selection.

Each arm is one explicit stage 4 with **4000 charged-call quota**, including
12 final endpoint calls, and **3600 active seconds**. Initial training/model
work is recomputed and charged normally. Complete model/step batches and the
final endpoint must fit. Preserve normal stopping, planned quota stops and hard
failures. The prescribed endpoint is the arm's terminal state, not an earlier
or truth-selected state.

## Release, execution and evidence

Dispatch requires TOP-023's verified completed diagnosis and operational gate
for damping_1e-2. Verify its source/input/artifact hashes and the unchanged
inherited implementation. No diagnostic candidate initializes either arm.

At most **two isolated numerical subprocesses**, BLAS 1, one arm per process.
Total ceiling **8000 new charged calls**; each worker also has an outer **3900-s
timeout** with a 10-s termination grace. Preserve both rows on any failure;
partial accounting must be labelled as a lower bound if no terminal ledger
survives an outer timeout. Wall times are descriptive, not a controlled speedup.

Only final endpoint scoring sees truth and development data. Report each
original count/boundary <=1 mm/IoU >=0.90/0.5-GHz training <=0.003/development
<=0.05 gate, numerical qualification, convergence/quotas, work and physical
changes. Compare the first accepted candidate to its TOP-023 witness with a
1e-10-m coefficient/geometry tolerance and relative objective tolerance 1e-8;
record hashes separately, allowing only declared roundoff-level retraction.
If the first candidate is unavailable after a hard stop, report that failure.

Release a separately declared fresh integration only for an arm that passes
all original reconstruction and numerical gates within these bounds. If both
recover, compare cost and accuracy before choosing the next candidate; do not
attribute a benefit to reset when plain continuation also explains it. If
neither recovers, do not spend another fresh/full-suite run on residual reduction
alone. Preserve any partial metric improvement and diagnose the remaining
failure under a new bounded contract. TOP-021 stays undispatched in every case.

## File/API map and owner review

Add a small TOP-024 driver/reporter and focused tests. Reuse the existing
TOP-017 stage/ledger, TOP-020 endpoint scorer, TOP-023 release evidence and
saved-array verification helpers. Source-bound preparation freezes both arms'
inputs/configurations before launching either subprocess. No shared numerical
file or default changes. Shell timeout bounds worker lifetime independently of
the in-process ledger; preserve actual exit codes and stdout/stderr.

Tests cover exact shared initialization, training-only fit inputs, the sole
initial-damping difference, equal horizon/caps, first-step witness matching,
failed release/partial rows, source guards and saved prediction/work replay.
Freeze measured dependencies and tests; close results into iteration 17.

Accept this bounded comparison because the cheap diagnostic's predeclared gate
passed. Do not infer reconstruction from its one-step gain or blame clipping:
all four measured raw proposals were inside their coordinate limits. Twelve
updates are a bounded reconstruction check, not a claim that failure proves
non-recoverability at arbitrary cost or from every initialization.
