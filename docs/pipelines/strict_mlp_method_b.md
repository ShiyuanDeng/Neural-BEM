# Strict MLP + Method B: the inverse pipeline to repair

Status reviewed on 2026-09-07. The intended development target is a
single-object inverse whose **accepted geometry belongs to the MLP**, with
Method B converting its zero contour faithfully into the ordered boundary
used by BEM. The radial Fourier studies inform this repair; they do not
replace this objective. This page defines the target and the evidence needed
to assess a repair. The documentation cleanup did not implement it or rerun
an experiment.

## Ownership and present implementation

The desired accepted-state contract is:

```text
accepted MLP weights
  -> negative-inside implicit field and its zero contour
  -> single-component extraction and level-set projection
  -> faithful Method-B ordered curve
  -> Kress forward prediction and fixed observed-data objective
  -> proposed update / candidate MLP weights
  -> repeat extraction, Method B and forward solve for the actual candidate
  -> accept or reject that MLP and its associated geometry and prediction
```

Method B fits Cartesian curve coordinates with Fourier least squares and
performs an arc-length refit. It is already a Fourier method; it differs from
the **radial** Fourier state used in the newer curve inverse. Method B does
not impose a star-shaped chart. Its current front end requires exactly one
regular, simple, closed component within the extraction domain. Increasing
MLP capacity does not remove this single-component extraction contract.
See [Method B](../../solvers/sdf_to_ordered_boundary/method_b.py),
[shared extraction](../../solvers/sdf_inverse/geometry.py) and
[forward interfaces](../../solvers/sdf_inverse/forward.py).

The following implementations must remain distinct:

| Implementation | Accepted geometry / update variables | Relation to the target |
|---|---|---|
| `run_sdf_inverse_comparison.py`, analytic and random-feature cases | Implicit-model parameters; Method B is rebuilt for objective evaluations | Working controls for the full extraction/conversion/forward path; not a scalable full-MLP optimizer |
| Same driver, `siren_*` cases | SIREN network weights via parameter-by-parameter finite differences, followed by Method B | Direct neural parameter experiment; forward cost grows with network parameter count |
| Historical alternating MLP feedback runs | Full MLP; modal proposals are fitted into it and the extracted candidate is re-solved | Failure evidence for the ownership we want to repair; saved results describe earlier implementations |
| Current `run_mlp_sdf_inverse_comparison.py` | Authoritative radial Fourier coefficients; MLP fit and Method-B extraction audit that curve | A different ownership contract, even though its fitting policy is called `legacy_strict` |

The current MLP driver explicitly chooses radial retraction. The library
also retains direct normal-curve updates and a compatibility model-predictor
seam. **Changing a retraction or distillation setting does not restore the
original MLP-owned feedback algorithm.** A repaired entry point must make
ownership explicit and evaluate the actual accepted MLP geometry. See
[driver](../../run_mlp_sdf_inverse_comparison.py),
[optimizer](../../solvers/sdf_inverse/neural_optimization.py) and the
[radial pipeline page](radial_fourier.md).

## What the saved evidence contributes

These are measurements from their recorded revisions, not a rerun on the
current source. Archived feedback runs remain relevant to fixing this
pipeline; archiving identifies superseded implementations, not an abandoned
research objective.

| Evidence | Recorded outcome | Consequence for the repair |
|---|---|---|
| [Method-B circle controls](../../results/inverse/method_b/wrong-circle-mie-20260902/summary.md) | Kress recovers the circle with very small field and geometry errors | Keep an independent-Mie control for the complete conversion path |
| [Method-B parametric star](../../results/inverse/method_b/wrong-star-nystrom-20260903/summary.md) | Recovery succeeds; Kress holdout relative error is about `3.14e-5`, with a material geometry representation floor | Separate conversion accuracy from forward quadrature accuracy |
| [MLP feedback, wrong ellipse to star](../../results/legacy/inverse/mlp_feedback/mlp-fixed-ellipse-to-star-kress-20260903/summary.md) | 25 accepted updates; holdout error worsens from about `1.003` to `1.043`, maximum boundary error from `42.0` to `46.7 mm`; spectral-tail stop | A decreasing intermediate objective and successful fitting are insufficient evidence of useful accepted MLP updates |
| [Radial K5 continuation](../../results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md) | Canonical holdout error `1.339e-8`; extracted MLP holdout error about `0.004327` and canonical/MLP drift about `0.329 mm` | The data and solver can recover this matched target; the MLP/curve transfer remains a separately measurable limitation |
| [Smooth distance supervision](../../results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md) | Smooth targets reduce extracted star drift from about `1.605` to `0.535 mm`; the fit still misses the `0.2 mm` gate | Supervise the intended smooth interface and audit independently; changing distance targets alone has not solved the fit |
| [Discrete Kress derivative validation](../../results/validation/kress_shape_derivative/refined-audits-20260906/summary.md) | Verified directional derivatives and paired-objective adjoints for declared smooth curve/material perturbations | A derivative foundation exists; coupling it to an MLP and actual Method-B conversion is additional work |

The representation-policy ablation reproduces the same radial coefficients
without intermediate fitting. That result measures redundant fitting **in
the radial-owned loop**. It does not establish that an MLP-owned Method-B
inverse cannot work.

## Repair sequence and acceptance evidence

1. **Establish conversion fidelity on frozen MLPs.** Preserve the field,
   extraction grid, projected samples, Method-B bandwidth, arc-length
   settings and BEM nodes as separate recorded quantities. Refine them
   independently. Measure both directions of contour-set distance,
   normalized field residual on the fitted curve, regularity and coherent
   curve derivatives. Compare forward predictions as conversion is refined.
   Finite point checks alone are not a continuous geometry certificate.

2. **Make fitting transfer measurable before closing the inverse loop.**
   Freeze a proposed smooth contour and compare the trained MLP zero set and
   its Method-B conversion to that contour. Use the existing continuous
   distance supervisor as an explicit option, with a matching continuous
   producer and its own refinement tolerance. Separate error from MLP
   fitting, extraction and Method-B refitting. Record Eikonal and off-contour
   distance diagnostics independently of interface and field accuracy.

3. **Repair MLP-owned acceptance.** A modal or explicit curve may help
   construct a proposal, but the training objective must be recomputed on
   the candidate MLP after full extraction and conversion. Accept the
   weights, converted geometry and corresponding response together. Reject
   invalid topology, unresolved conversion, failed representation gates or
   an unacceptable actual data objective. A stale preceding MLP cannot stand
   in for a newly accepted geometry under this ownership contract.

4. **Verify derivative transfer before relying on it.** The existing Kress
   module differentiates the solved discrete problem for coherent curve
   jets at fixed topology, node correspondence and kernel branches. It does
   not differentiate marching-square connectivity, Method-B fitting or
   remeshing. Any chain from its covector into MLP weights must be checked
   against finite differences of the *actual* candidate-weight → extraction
   → Method-B → objective path, across perturbation sizes and resolutions.
   Distinguish a fixed-correspondence check from a complete re-extraction
   check; record failures of smooth correspondence instead of claiming an
   exact derivative through them.

5. **Close the controlled inverse comparison.** Start with the independent
   circle and star data and clearly specified wrong initial fields. Compare
   the repaired strict path with the existing Method-B parameter controls
   and radial diagnostic at declared acquisition, accuracy and work budgets.
   Report initial/final actual-MLP field errors, symmetric geometry error,
   conversion/field refinement, accepted/rejected steps and separate failure
   reasons. Keep holdout data out of step acceptance and setting selection.
   Introduce a non-star-shaped single-object case only after its conversion
   and independent forward reference qualify.

The recorded `1.5 mm` radial per-step drift safety cap and `0.2 mm`
representation-convergence/export gate serve different purposes. Neither
should silently become the repair's universal tolerance. Predeclare
geometry, representation, field and refinement gates for each benchmark,
and report unresolved or unevaluated quantities explicitly. Optimizer
termination, actual reconstruction accuracy and valid MLP delivery are
separate outcomes.

The principal implementation seams are
[the neural model and distance fitting](../../solvers/sdf_inverse/neural.py),
[continuous distance](../../solvers/sdf_inverse/continuous_distance.py),
[Method-B geometry](../../solvers/sdf_inverse/geometry.py),
[parameter-FD reference](../../solvers/sdf_inverse/optimization.py) and
[discrete Kress derivatives](../../solvers/gpr_bem_kress/shape_derivative.py).
No existing command should be described as running the repaired strict
pipeline until that ownership and acceptance behavior has been implemented
and verified.
