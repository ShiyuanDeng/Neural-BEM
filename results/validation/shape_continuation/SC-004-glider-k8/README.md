# SC-004 — longer continuation exposed filtered-step stopping failure

The wavelength-scaled resolution policy was first checked on the ellipse
([policy smoke](../SC-004-policy-smoke/summary.json), all gates pass). This run
then attempted the glider on k=1:0.25:8, 50 iterations/frequency, 20 points per
wavelength, minimum K=48/N=128, contrast 1.44, and explicit N/2N stage checks.
Its declared inverse cap was 1500 forward evaluations / 600 wall seconds.

It exhausted the evaluation budget at k=3.25 after 273 Jacobians and 1500
completed forward evaluations. No forward failed. Completed stage handoffs
and the final geometry pass forward refinement. Shape/prediction gates fail;
the planned k=8 endpoint was not reached. All checkpoints and trials remain.

Diagnosis from the terminal trials: curvature tail approaches the 0.1 bound;
Gaussian filtering removes most of the normal update, but the implementation
records the **unfiltered** coefficient norm and disables the small-step stop
whenever filtering is active. Near-identical filtered updates consequently
continue consuming iterations/forward calls. Small improvements are not
stationarity or successful recovery.

The next repair measures RMS and maximum physical boundary displacement after
filtering and applies the declared small-update criterion to that actual
motion. No frequency, curvature, projection or data-fit tolerance is relaxed.
The same bounded run will be repeated. This failure remains the control and
is not retrospectively described as a complete continuation experiment.

Command and source hashes: [manifest](manifest.json). All measurements and
phase timings: [summary](summary.json). `checkpoint_*.json/.npz` record every
completed or budget-stopped stage before evaluation. The initial observation
matrices are in `inputs.npz`, with 256/512 checks in the summary.
