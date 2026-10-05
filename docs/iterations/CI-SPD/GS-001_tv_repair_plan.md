# GS-001 follow-up — qualify the small-step TV limit

Registered after the first probe, before this follow-up fit. The original
run is preserved and published in commit `7b5bd696`; no evidence is replaced.

The native coefficient-TV routine's final rejected steps do not approach
the current objective as their size halves. Check its zero-regularization
limit independently on a fixed synthetic bounded image. If confirmed,
replace only the finite TV prox with a bounded dual projection for the same
periodic isotropic coefficient-TV objective. Require identity at zero,
maximum change <=4 alpha for bounded inputs, feasibility, and a decrease in
the proximal objective on independent images. Keep the pinned source read-only.

Run a fresh probe in `GS-001/qualified_tv/` with the same C-shape case,
0.5 GHz paired data, known contrast, centred circle, grid selection,
gradient, lambda schedule, line search, 300-step/30-minute caps and readout.
No parameter is selected from target geometry or the previous truth scores.
Rerun the pre-fit numerical checks. The new TV step is an explicit adaptation;
do not attribute its performance to unchanged released GauGal. Compare both
outputs, publish the failed native step evidence and commit/push the new run.
