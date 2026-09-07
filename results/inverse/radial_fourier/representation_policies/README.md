# Explicit Radial Fourier: neural fitting and export policies

These runs implement Task A of the 2026-09-05 brief. Historical measurements retain their original payloads; relocated runs are indexed
in the [catalogue](../../../README.md). These radial policies inform
[Implicit MLP + Method B](../../../../docs/pipelines/implicit_mlp.md), but every
accepted reconstruction in this ablation remains an explicit radial curve.

- [`saved-star-20260905/summary.md`](saved-star-20260905/summary.md): final
  saved-configuration comparison, with frozen-curve forward refinement,
  separate outcomes, actual work counts and source/physical provenance.
- [`short-final-20260905/summary.md`](short-final-20260905/summary.md): short
  deterministic contract test, with the independent 0.2 mm export gate.
  Four updates are insufficient for reconstruction convergence. This precedes
  the final additional forward-refinement diagnostics in the saved-star run.
- [short-20260905](../../../legacy/development/representation_policy/short-20260905): retained development result, superseded. It used the
  1.5 mm step-safety cap for final export and therefore incorrectly admitted
  a representation outside the intended 0.2 mm final gate. Do not use its
  export status as evidence of successful SDF delivery.

The [first-batch report](../../../../docs/reports/sdf_kress_first_batch_2026-09-05.md)
interprets these results and the separate smooth-target/parameterization tests.
No absent audit is represented by a zero error. A valid canonical reconstruction
does not imply a successful SDF export.
