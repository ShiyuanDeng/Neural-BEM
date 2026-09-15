# TOP-022 pre-dispatch owner review

Owner/reviewer: Codex `/root`. No independent review claimed.

The existing TOP-020 fresh input checks, H controller and ledger, count-independent
K9 padding, 256/512 feasibility and endpoint scorer are reused. The schedule is
explicitly `((4, 8000),)`: its first and only fit receives all four training
frequencies. No shared numerical source or optimizer is changed. The original
circle is loaded from v1 inputs; the prior optimized state is hashed only for
comparison after a fresh controller run. A mismatch stops before refinement.

Comparison evidence must be the artifact-verified completed TOP-020 negative.
Inputs, source-bound tests, source snapshots and that comparison are frozen and
verified before and after dispatch. The only changed allocation is one full
objective under the same total calls/time and unchanged 22-update stage limit.
Truth/evaluation remain confined to the prescribed endpoint scorer. There is no
quota extension, endpoint selection, restart or target count in the fit.

The no-solve reporter reads stage labels/quotas from the contract, preserving
TOP-020's four-stage replay while accepting TOP-022's single stage 4. It also
replays the fresh-prefix identity and verifies comparison hashes. TOP-021's
release gate explicitly rejects a different protocol, even if it passes.

Dispatch requires the source-bound test record to pass. Recovery and numerical
qualification remain separate; quota or iteration stopping is not convergence.
