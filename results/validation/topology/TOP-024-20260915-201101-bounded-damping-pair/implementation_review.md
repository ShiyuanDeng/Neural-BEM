# TOP-024 implementation review

Owner review by Codex `/root`; no independent-agent review claimed.

The driver reuses TOP-017's fixed-topology optimizer, complete-batch ledger,
cross-resolution acceptance checks and TOP-020's final scoring without editing
their source. Both configurations are frozen before dispatch. The only arm
difference is initial damping; each permits 12 updates, 4000 calls including
the 12-call terminal score, and 3600 active seconds. Two isolated BLAS-1 workers
are bounded externally by timeout 3900 s plus a 10-s termination grace.

TOP-023's verified release and frozen accepted steps qualify the comparison.
Neither accepted diagnostic candidate initializes fitting: both start from the
exact failed TOP-022 endpoint. The fit receives four training columns and only
training/numerical initial-score fields. Truth and development data are used by
the final scorer. The first accepted step is checked after its normal checkpoint
against the corresponding diagnostic witness with the declared tolerances.

Focused tests exercise release/source rejection, exact initialization,
configuration equality, training-only fit inputs, first-step failure preservation,
hard-stop rows and missing-result accounting. Inherited tests cover the ledger,
optimizer stopping and acceptance checks. The reporter independently replays
saved complex prediction scores, state/gradient associations, trajectories,
acceptance margins, first-step coefficients and objective, and work counters.
Missing worker ledgers are explicitly lower bounds, never zero-work success.

No optimizer redesign, literature search, additional reset, horizon extension,
best-state choice, fresh integration or full-suite dispatch is included.
