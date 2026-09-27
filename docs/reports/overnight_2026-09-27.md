# 27 September: coupled reconstruction, strategies and topology

I waited the requested hour, then pulled at 02:22:38 UTC. Claude's complete
atlas/strategy review and `GPR_next_steps_multi_object_topology.md` arrived in
`34355f99`, so another half-hour poll was unnecessary. Work stayed on the
existing `feature/shape-frequency-continuation` branch; no branch or worktree
was created.

**The useful news is a qualified two-object implementation and a working
simple reconstruction strategy. The more elaborate strategies did not win.**

The new opt-in adapter couples general Cartesian Fourier objects, including
the non-star-shaped C, through the existing Müller/Kress physics and shared
optimizer. Independent two-cylinder fields agree within 7.1e-15, and the
complete-trial derivative passes at better than 3.4e-8 relative error on the
representative coupled fixtures. All 250 continuation/Kress regression tests
pass.

[SC-047](../iterations/shape_frequency_continuation/iteration_27/01_results.md)
completes 12 local reconstructions at two separations, clean and with 1%
noise. Worst boundary RMS falls from 3.81 mm to 0.74–1.03 mm; all 12 final
field audits pass. These starts already have the correct count and C-shaped
outline. Conditional atlas selection costs more and passes none of its four
superiority gates. Four conditional arms retain budget stops.

The atlas now measures each object's sensitivity after removing ambiguity
with the other object's shape. That is a useful diagnostic capability, but
this prospective object-selection rule does not earn its extra work. Claude's
earlier cleanup result remains a practical artifact repair; neither campaign
establishes a superior general atlas controller.

[SC-048](../iterations/shape_frequency_continuation/iteration_28/01_results.md)
adds intrinsic shape errors and tests a specific follow-up against simple
controls. Starting from 3.90 mm worst RMS, compact M5 reaches **0.705 mm**;
M9 reaches 2.72 mm and exact-global-motion enrichment reaches 3.58 mm. All
complete their six-dispatch schedules and pass field audits. The compact
reference gives an 82% reduction here. The enrichment fails its frozen gate,
so the additional noise/separation runs are withheld. This is one local
clean comparison, not evidence of noise robustness for M5 generally.

The **current-scene topological derivative is implemented and numerically
qualified**: shrinking insertions agree to about 7 ppm. Removing an extra
object improves the refined loss. However, wrong boundaries attract false
births even after bounded shape refinement, and the strongest missing-object
candidate sits at the scan edge away from the missing C. Negative derivative
values also fail to predict descent for a finite 3 mm disk in the noisy
correct scene. Automatic births/deletions remain disabled under the roadmap.

The two studies account for **5,468 frequency forward/reciprocal batches**,
plus eight independent series evaluations; tests and geometry-only reporting
are separate. Different quadratures/object counts have different actual
costs. All frozen source receipts and 982 closeout checks pass. Full inputs,
accepted states, rejected trials, failed gates, plots and reproduction drivers
are preserved in the linked bundles. No independent review or production
default promotion is claimed.

The next evidence needed is a predictor of accepted finite progress that
beats the compact control at charged cost, followed by untouched shapes and
independent noise draws. Unknown-count decisions additionally need finite
candidate comparisons against more shape refinement and a declared
discrepancy/complexity rule. The run stops at those research gates rather than
retuning thresholds on these outcomes.
