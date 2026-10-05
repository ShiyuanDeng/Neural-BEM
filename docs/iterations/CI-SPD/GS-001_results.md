# GS-001 — single-frequency GauGal C-shape probe

The first adapted known-material GauGal run used TG-002 `c_shape__c13.3`
with only 24 paired measurements at 0.5 GHz, from the prescribed centred
circle. It stopped after 12 accepted updates: residual **147.019% →
30.177%**, 112.27 s fitting, 240.62 s including qualification/build.
The fixed 0.5 contour remained approximately circular: sampled symmetric
RMS **28.265 → 26.712 mm**, sampled Hausdorff **51.316 → 47.539 mm**,
occupancy IoU **0.330 → 0.333**, centroid error **30.064 → 29.713 mm**.
This output does not recover the C-shape or meet the benchmark gates.

The operator/solver issue that stopped ON-002 was resolved for this probe
by exact separable Gaussian mass preconditioning of the unchanged physical
equations. Dense direct-solve/complete-gradient controls pass. Both full-grid
adjoints pass, off-pair measurements are zero, and directional finite
differences pass. Start-disk Mie disagreement improved from **3.107% at
128/112** to **0.811% at 256/224**, triggering the preregistered refinement.
The final inner true residual is **6.10e-8**, below the 1e-6 gate.

The stop is **LINE_SEARCH_STALLED**, not an inner-solve failure. Every last
backtrack has a qualified solve, but its objective approaches approximately
0.0566 instead of the current 0.0455 as the step shrinks. This suggests the
native finite TV proximal iteration does not approach the current state in
the small-step limit. It is an updater limitation requiring an independent
check; it does not establish a single-frequency identifiability limit.

The pinned GauGal source remains unchanged. The solver and coefficient-TV
adaptation live only in the experiment package. All 30 focused adapter and
benchmark tests pass. The full histories, rejected trials, native states,
source snapshot and reconstruction figure are preserved in
`results/validation/cleaned_interfaces/GS-001/`.

No damped or other-frequency data enters fitting. Truth is accessed only
after saving the inverse output for readout. These sampled contour distances
are diagnostic, not the benchmark's certified all-frequency audit. This is
an adapted known-material volume inverse, not released GauGal cylinder
performance or a BEM timing-parity experiment.
