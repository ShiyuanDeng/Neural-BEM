> Written-evidence snapshot collected for this iteration on 2026-09-08.
> Source run record: [original report](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/README.md). Numerical claims retain
> their original experiment scope; this copy adds no new measurements.

# Validated implicit-MLP repairs — 2026-09-07

Three targeted changes follow the
[failure audit](../../../../../results/validation/implicit_mlp_adjoint/failure-audit-20260907/README.md). These repair demonstrated
failure mechanisms and add a fidelity guard; they do not establish successful
general inverse recovery.

- **Gradient fallback:** cap large gradients without scaling small gradients
  up to a fixed proposal length. Restarting the saved circle failure with
  its original eight-backtrack limit now accepts three updates, lowering loss
  from `2.617709e-6` to `2.440441e-6`. The fallback needs only 1, 1 and 0
  backtracks. This restart isolates the optimizer change using the historical
  conversion configuration; the old saved contour fails the new fidelity gate.
- **Star pretraining:** default the star proxy's pretraining Eikonal weight
  to zero. `F/||grad F||` is not a global distance, so its regression target
  conflicts with a global unit-gradient penalty. The same 6,000-update,
  64-wide, two-hidden-layer known-target fit again gives **1.15088 mm**
  maximum node-to-target error, versus the original **9.18152 mm**. Circle
  and ellipse retain their previous weight of `0.1`. The new
  `--mlp-pretrain-eikonal-weight` override is separate from the inverse's
  `--eikonal-weight`; actual pretraining weights are saved in metadata.
  Better star contour fitting does not certify global signed-distance quality.
- **Conversion guard:** neural drivers now check independently extracted raw
  contours against Method B at two refined grids and sample counts. The
  symmetric vertex-to-polygon distance must satisfy
  `--conversion-tolerance-mm` (default **0.2 mm**), and its refinement change
  must be within 5% of that budget. Violations reject candidates before BEM
  evaluation. The saved circle and ellipse-derived circle are correctly
  rejected at about **0.267 mm** and **1.822 mm**; the saved star passes at
  **0.179 mm**. This is sampled numerical evidence, not a continuous zero-set
  certificate. It adds extraction work and can reject previously admissible
  starting fields; it does not automatically repair an underresolved conversion.

The [short star inverse](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/star-smoke/summary.md) uses the final star defaults,
four acquisition pairs and two updates. It completes artifact export, accepts
both updates with decreasing actual-network loss, and passes the warm-start
Eikonal check. **Overall recovery remains FAIL**, as expected for this bounded
smoke test; its holdout and recovery gates were not relaxed. No full recovery
benchmark was rerun here; the
[subsequent reruns](../../../../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md) do that, and show the
conversion guard rejecting candidates at both targets' production bandwidths.

Validation: the broader inverse/adjoint suite passed **377 tests**. After the
final change preserving the ellipse default, **40 focused tests passed** for
the final optimizer, driver, pretraining policy and conversion guard.
[validation.json](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/validation.json) records commands, scope and final source
hashes. `git diff --check` passes.

The evidence in [metrics.json](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/metrics.json) includes the circle restart and
saved conversion checks. The same file's `star_target_fit` entry and
[star_with_offsets.json](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/star_with_offsets.json) are **rejected prototypes**:
a broader resolved-distance redesign produced 3 or 23 zero contours and was
excluded from production. [ellipse_initial_fit.json](../../../../../results/validation/implicit_mlp_adjoint/repairs-20260907/ellipse_initial_fit.json)
records a zero-penalty ellipse trial with 5 contours; this is why the ellipse
default was retained. These failures are preserved to avoid presenting them
as validated repairs.

See the [pipeline guide](../../../../pipelines/implicit_mlp.md) for current
settings. Historical run bundles and the pre-existing notebook edit were not
modified. No commit was created.
