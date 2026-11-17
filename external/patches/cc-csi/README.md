# CC-CSI patches

Upstream base: `73a64e163da34e63fa33f8abe196b9004f45d342`.

`0001-r2026a-remove-obsolete-plottools.patch`: applied 17 November 2026.
Comments out the removed GUI command in `show_InitGuess.m`. No numerical
algorithm, input or setting changes. Apply from the upstream checkout with
`git apply /absolute/path/to/0001-r2026a-remove-obsolete-plottools.patch`.

The negative-refinement `interp2` calls in `functions/MR_CSI_Brent.m` are
not patched. Their replacement needs the coordinator's decision.
