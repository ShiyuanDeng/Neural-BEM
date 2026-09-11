# TOP-001E broader controller qualification

**Approval status:** APPROVED under the current Track A task.
**Execution status:** COMPLETE. Owner: Codex; independent reviewer: unassigned.

Declared after the unperturbed Cartesian E replay passed, before these runs.
That replay reaches 25.123360-nm sampled Hausdorff using 574 BIE frequency
solves, compared with A's 175.210848 µm and 1,109 solves. The original A/B/C
comparison and E perturbation diagnostic continue without modification.

Run all five original **Cartesian** automatic-controller cases from their
original initializations in A (1 candidate × 3 LM steps) and E (3 × 1).
Use original full-profile data, truth, cap 48, geometry resolutions and all
other controller settings. Ten full inversions, at most three concurrent
single-thread case-pair processes, one-hour wall ceiling. These additional
runs use the already implemented CLI controls and introduce no numerical-code
change. Artifacts: `results/validation/topology/TOP-001E-controller-20260911/`.

Add evaluation-only 1.5/2.5-GHz measurements to both arms. Circle truths use
independent cylindrical harmonics; the connected ellipse uses analytic truth
curves at 256 Kress nodes (mesh-independent, not an independent solver).
Save holdout observations and count their evaluation work separately.

Qualification requires both runs to stop `recovered` with the correct final
component count, and E's geometry, training and holdout errors to be at most
`max(1.1 × A, floor)`. Floors are 1 µm for sampled Hausdorff, 1e-6 for training
relative L2, and 1e-5 for holdout relative L2. These allow negligible numerical
differences on the nanometre controls without hiding a material regression.
Compare every event sequence and both per-case and summed inversion solve
counts. Default changes require all five quality gates and no increase in
summed work; failure leaves E opt-in and is retained in the report. This is
bounded regression qualification, not evidence of global convergence or general
noisy-scene performance.
