# SC-005 — physical filtered-step stopping

This repeats SC-004's glider k=1:0.25:8 contract with the stopping bug repaired.
The step norm is now arclength-weighted RMS physical displacement after filtering,
before the arclength gauge changes. Maximum displacement and raw coefficient
norm remain separate diagnostics. Every filter level uses the small-step stop.
Two new regression controls check suppressed harmonic motion and an actual
filtered circle inverse stopping before its data residual meets tolerance.

The same 1500-forward cap now ends at k=4.75 rather than k=3.25. All 1500 solves
succeed; completed stages pass their N/2N checks. The endpoint still fails the
completion, shape and held-out prediction gates. This is a repaired stopping
criterion, not a successful glider recovery. The full trial history is retained.

The next controlled comparison disables the added step-halving loop, following
the paper's immediate progression to filtering when proposals are inadmissible.
All other controls, including the budget, remain fixed. This comparison is
motivated by the trial history: many updates shrink onto the curvature bound
before a filtered full update is considered.

The truth's arclength-curvature tail above mode 16 is approximately 0.146,
exceeding the 0.1 gate at k=8; above mode 24 it is approximately 0.091.
These are evaluation-only observations, not inputs to the inverse policy.
Longer frequency coverage may therefore be necessary even with correct search.

See [summary](summary.json) for authoritative metrics and timings and
[manifest](manifest.json) for command and source hashes. A tiny separate curvature
spectrum diagnostic ran concurrently, so these wall times are not a dedicated
performance benchmark.
