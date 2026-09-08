# Implicit MLP + Method B: initial adjoint validation

Latest cycle: [iteration-3 long-run evidence](iteration-03-20260908/README.md)
and [research results](../../../docs/iterations/implicit_mlp/iteration_03/01_results.md).
Iteration 2 is closed after diagnostics, repairs, and the completed short/long
acquisition comparisons. Multistatic improves geometry; full recovery remains
unresolved. The initial validation and earlier controls are preserved below.

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
- [Reruns after the repairs](rerun-20260907/README.md): Method-B bandwidth
  constrained the original runs. The circle then accepts all 60
  updates with a refinement-converged conversion; recovery gates still FAIL,
  and the star's lobe amplitude and phase move away from the target.
- [Checkpoint review](review-20260908/README.md): the bandwidth-96 star also
  needed deeper backtracking; the first extra acceptable step is a small crawl.
- [Latest-direction controls and diagnostics](latest-direction-20260908/README.md):
  eight-pair five-parameter recovery succeeds; the target-fitted MLP accepts
  three steps but does not establish recovery. Paired-8 already has full rank
  in the tested 21-mode two-frequency space, while multistatic readout and
  higher frequency improve conditioning. Search bookkeeping is repaired;
  the report motivated the subsequently completed matched acquisition ablation.

Optimizer diagnostics record zero FD probes and zero curve-distillation steps.
Validation finite differences are counted separately. Saved neural checkpoints
and plots are local binary artifacts; JSON/CSV/Markdown provide the textual record.
