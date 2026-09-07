# Implicit MLP + Method B: initial adjoint validation

See the [implementation and measured-results report](../../../docs/reports/implicit_mlp_adjoint_2026-09-07.md).

- [Circle](circle-verified-20260907/summary.md): 41 accepted direct neural updates;
  substantial improvement, overall recovery gates FAIL.
- [Star](star-20260907/summary.md): five accepted direct neural updates;
  training loss decreases, holdout and geometry worsen, overall gates FAIL.
- [Star gradient audit](star-20260907/initial_star_gradient_audit.json): full
  network-to-BEM derivative agreement, maximum relative error `2.74e-8`.
- [Partial earlier circle run](circle-20260907/FAILED.md): checkpoint written,
  exporter failed; preserved separately.
- [Validation command and source hashes](validation.json).
- [Reruns after the repairs](rerun-20260907/README.md): the Method-B bandwidth,
  not the optimizer, bounded both targets. The circle then accepts all 60
  updates with a refinement-converged conversion; recovery gates still FAIL,
  and the star's lobe amplitude and phase move away from the target.

Optimizer diagnostics record zero FD probes and zero curve-distillation steps.
Validation finite differences are counted separately. Saved neural checkpoints
and plots are local binary artifacts; JSON/CSV/Markdown provide the textual record.
