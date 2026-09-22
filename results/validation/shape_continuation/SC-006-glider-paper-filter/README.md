# SC-006 — comparison without added backtracking

This uses exactly the SC-005 k=1:0.25:8 contract except `--backtracks 0`,
which removes the added step-halving loop before Gaussian filtering.
It retains SVD, explicit residual decrease, the same curvature/projection
limits, 50 iterations per frequency, and the 1500-forward / 600-second cap.
It is therefore a comparison of search sequencing, not exact author code.

The cap is exhausted at k=7.25 (1500 successful forwards, 691 Jacobians),
but recovery is worse: relative sampled boundary error 0.190 and held-out
relative prediction error 0.0797. Completed stages and the endpoint pass
forward refinement. Many stages find no admissible decreasing proposal;
others make small translated/filtered updates for all 50 iterations.
Advancing farther in frequency is not itself evidence of better inversion.

The safeguarded SC-005 trajectory remains the baseline. The filter-only
variant stays available as an explicit comparison control, not the default.
Subsequent frequency extension will resume the SC-005 endpoint, with the
additional budget and parent state recorded; it is not a same-budget result.

Source hashes and command: [manifest](manifest.json). All measured residuals,
trial reasons and timings: [summary](summary.json). The observation arrays
can be checked bitwise against SC-005, and all states/checkpoints are retained.
