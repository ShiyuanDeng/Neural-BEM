# Resolution of the 2026-09-24 outsider review

2026-09-24. Implementation owner: Claude. Reviewer: Codex
([review](01_codex_outsider_review.md),
[audit](../../../../../results/validation/shape_continuation/review-20260924/README.md)).
The user asked for the review to be implemented directly after it landed.

Before resolving, I re-read the audit's JSON. The p=15 sign reversal, the 135
model-gain ratios (0.926–1.767) and the circle proxy counterexample all
reproduce. One further observation strengthens point 1. At 1.25 GHz the
contiguous 0–15 solve aligns *worst* with the error proxy (cosine 0.40). The
M=9-plus-pair solve aligns at 0.97. Alignment therefore depends on the
other retained modes, and it does not change steadily as harmonics are
added.

Nothing in the review is rejected.

| # | Review point | Decision | Implementation |
|---|---|---|---|
| 1 | A full-space step component is not a recommendation to add that harmonic | **Accept** | `atlas_survey.conditional_step(G, g, keep, λ)` solves on a declared coordinate set. A test pins it to the Schur-complement form. All band comparisons from now on use conditional solves. SC-022's observation 3 describes one joint P=48 solve, and is read that way. |
| 2 | The stored step is damped and unclipped, not unregularized; per-frequency rank ≤ 48; the live λ is trajectory history | **Accept** | The labels are corrected. SC-023 evaluates every candidate on a declared damping grid that is independent of the trajectory. The GN cutoff is reported as 1e-5 on the singular values of J. |
| 3 | The "true error" layer is a signed closest-distance proxy | **Accept** | `atlas_survey.normal_ray_error` intersects each current-normal ray with the truth polygon and flags nodes without a nearby crossing. It is exact on the offset-circle counterexample, and tested there. The proxy is kept and renamed in new outputs. Direction claims use the normal-ray layer, and outcome claims use the geometry of actual finite trials. |
| 4a | Whole-vector norms and cosines need the Fourier mass metric W = diag(1, ½, …) | **Accept** | `atlas_survey.rms_weights` and `physical_norm`/`physical_cosine`. New summaries report physical RMS, maximum normal and, where useful, slope. |
| 4b | Per-coefficient bounds are not physical, band-independent step bounds | **Accept, as a separate shared-backend option** | `BackendConfig.step_control`, default `"coefficient"`, which is unchanged, so SC-020–022 replay. The `"physical"` setting scales the whole step so that its maximum normal move stays within a declared bound. This keeps the step's direction, where clipping does not. It is a shared-backend ablation, applied to every arm that uses it. |
| 4c | The M=32 failures hold only under the tested clipping, damping, starts and retries | **Accept** | The wording is qualified in the records (Codex's notes). The physical-step ablation in SC-024 tests the claim directly. |
| 5 | An update band is a local tangent restriction; finite moves plus regauging mix harmonics | **Accept** | A test applies one Borges move h = ε cos mθ to a circle. It measures the 2m harmonic of the radial offset in the new arclength against −ε²/(2R). "Cannot reach" in the SC-020 records becomes "a measured local plateau". |
| N1 | Atlas cells need derivative refinement and actual-update directional checks | **Resolve through a named diagnostic** (SC-023 Q0) | Representative cells (early, stalled, cavity, highest frequency) are recomputed at N=1024. They are compared column by column and in conditional steps with the stored N=512 layers. Directional finite differences are taken through the actual Borges trial. Budget ≤ 1 h. Artifacts go beside SC-023. |
| N2 | SC-020/021 source text is not recoverable from current hashes | **Accept, done** | The exact texts were rebuilt by reversing the two logged post-run edits. The rebuilt SHA-256 values equal the recorded ones (`source_archive/check.json` in both bundles). |
| N3 | The dense NPZ files are untracked | **Resolve through a diagnostic; durable upload deferred to the user** | One SC-022 case is regenerated from the repository and compared array by array. Zip timestamps make whole-file hashes non-reproducible. The files are 171 MB. Publishing them as a release asset or on an archive is an outward-facing upload, so the user decides. Until then, the offline claims rest on regeneration plus the comparison. |
| N4 | K=192, the catalog and the truth-assisted diagnostics are development information | **Accept** | Circle, star, C and merge are development cases from here on. Held-out evaluation cases are declared in the [SC-023/024 plan](../03_plan.md) before any policy development. They will not be generated or run until a policy is frozen. |

## Next scientific step, as the review recommends

The review's question is adopted unchanged: *does conditional, physically
scaled local information predict which data and update subspace will produce
a useful admissible step at lower cost?* The [plan](../03_plan.md) orders the
work as the review does:

1. Labels, metric and cell qualification (N1).
2. SC-023: conditional candidates offline on the stored blocks. Finite trials
   are pure geometry, so they are checked for admissibility and for the change
   in geometric error without any physics solve.
3. SC-024: bounded nonlinear probes of the most discriminating choices, with
   the physical-step ablation.
4. A frozen minimal policy against the ladder and a progress controller, with
   ablations, then the held-out cases.
