# HB-002 direct geometry and information tests

## Questions

1. Does item 3 certify actual accepted coefficient steps across whole TG-002 trajectories, using the simple bound or A1's sharper reciprocal-residual bound?
2. Does item 9's physical shape metric change the visible directions when frequencies and update bands are varied independently on saved physical Jacobians?

## Fixed scope before execution

Use NR-001 default spectral trajectories: circle c4, peanut c4, hook c13.3.
Evaluate the simple q coefficient bound on every consecutive same-stage accepted
step. Select eight evenly spaced eligible steps per trajectory for the sharper
A1 `log_modulus` bound. Use the stage's existing trace window plus its default
margin, tolerance 1e-12 and at most 1000 Chebyshev terms. A refusal is recorded,
not repaired by a new forward solve. No new fits or physics calls.

Use FI-001 saved exact Jacobians on hook release, hook final and peanut final.
Rebuild only each state's existing geometry derivative. Compute its mean
squared actual normal displacement metric, remove eigenvalues below 1e-12
of its maximum, and whiten J. Compare M=3, 11 and the state's full M (deduplicate),
and the low catalog (<=0.75 GHz) against all 19 real frequencies. Normalize each
frequency by the observed norm with equal weights within its selected catalog.
Report singular spectra and counts above 1e-3 of the largest singular value;
this is an illustrative relative threshold, not a noise-based recovery claim.
Check invariance under deterministic diagonal changes of parameter units.

Actual curve differences include the refit and use matched coefficient padding.
A1's inequality is conditional on its heuristic floating-point allowance;
no interval-arithmetic proof is claimed. Store per-step receipts, input hashes,
CPU/load information, timing, and concise item-by-item conclusions. Single-thread
CPU cores 4–7; stop after these bounded analyses. No maintained solver changes.
