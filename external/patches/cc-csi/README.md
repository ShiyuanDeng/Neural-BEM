# CC-CSI patches

Upstream base: `73a64e163da34e63fa33f8abe196b9004f45d342`.

`0001-r2026a-remove-obsolete-plottools.patch`: applied 17 November 2026.
Comments out the removed GUI command in `show_InitGuess.m`. No numerical
algorithm, input or setting changes. Apply from the upstream checkout with
`git apply /absolute/path/to/0001-r2026a-remove-obsolete-plottools.patch`.

`0002-restore-legacy-interp2-coarsening.patch`: approved by the coordinator
and applied 17 November 2026. Replaces only the three negative-refinement
calls in `functions/MR_CSI_Brent.m` by sampling the original grid nodes.
The coordinator's reading of legacy `interp2` is that a negative exponent
generated precisely these query coordinates, without rejecting the sign.
No regularization formula or setting changes. The wrapper checks exact
random-array refine/coarsen equality and restores the random-number state.
