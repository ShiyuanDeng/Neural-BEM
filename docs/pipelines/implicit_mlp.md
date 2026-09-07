# Implicit MLP + Method B: Kress adjoint inverse

Implemented on 2026-09-07: **Implicit MLP + Method B** uses a discrete Kress
adjoint to update neural weights directly. Its accepted geometry belongs to
the MLP. The preferred entry point is
[`run_implicit_mlp_inverse.py`](../../run_implicit_mlp_inverse.py).
**Explicit Radial Fourier** is the separate curve-owned control, now named
[`run_explicit_radial_fourier_inverse.py`](../../run_explicit_radial_fourier_inverse.py).
**Recovery remains FAIL / unresolved.** The new 12-pair circle,
ellipse-to-circle and star experiments all fail overall acceptance, despite
validated adjoint gradients and accepted neural updates. See the
[implementation and validation report](../reports/implicit_mlp_adjoint_2026-09-07.md)
and [active neural results](../../results/inverse/implicit_mlp). The current
optimizer has not completed the intended reconstruction task.

## How the field becomes a boundary

The MLP is a map from a point in space to a scalar value: negative inside
the object, positive outside, and zero on its boundary. Its weights define
the shape. Training encourages signed-distance-like values, but the field
is not certified as an exact SDF.

The extraction front end locates and projects points onto that zero contour.
Method B fits their Cartesian coordinates with Fourier least squares, then
refits after redistribution by arc length. This supplies the ordered smooth
boundary required by Kress. Method B's Cartesian Fourier fit is different
from representing radius as a Fourier function of angle in
[Explicit Radial Fourier](explicit_radial_fourier.md).

Method B does not require a star-shaped object. Its current front end does
require exactly one regular, simple, closed component inside the extraction
domain. Increasing network capacity does not remove that geometry contract.
See [Method B](../../solvers/sdf_to_ordered_boundary/method_b.py),
[shared extraction](../../solvers/sdf_inverse/geometry.py) and
[forward interfaces](../../solvers/sdf_inverse/forward.py).

## How an inverse step updates the MLP

The implemented accepted-state contract is:

```text
accepted MLP weights
  -> negative-inside implicit field and its zero contour
  -> single-component extraction and level-set projection
  -> Method-B ordered curve
  -> Kress forward prediction and fixed observed-data objective
  -> Kress adjoint and reverse geometry derivative
  -> reverse extraction/Method B into MLP weights
  -> Adam proposal / candidate MLP weights
  -> repeat extraction, Method B and forward solve for the actual candidate
  -> accept or reject that MLP and its associated geometry and prediction
```

The physics gradient differentiates positions, curve derivatives, normals,
speeds, quadrature corrections, incident fields and receiver evaluation.
The conversion reverse replays marching-edge interpolation, projection,
chord resampling, Fourier fitting and the arc-length refit on their current
branches. It checks its geometry against the production forward curve.
There is no per-weight finite-difference calculation or per-step training to
copy a proposed curve. A fixed-sample Eikonal regularizer encourages
distance-like values; it does not establish a globally exact SDF.

Backtracking checks the actual re-extracted MLP: boundary motion must stay
within the configured step limit, data loss must decrease, and both the data
loss and data-plus-Eikonal objective must satisfy their Armijo tests. Invalid
geometry is rejected; rejected trials restore accepted weights.
Solver/derivative errors propagate without an FD fallback. Exact marching-grid vertex crossings have
no unique branch derivative and are reported explicitly. Connectivity,
phase choices and interpolation/projection branches remain discrete: the
local derivative does not certify a topology-changing step.

## Entry points and other implementations

The default named neural command uses a float64 64-wide, two-hidden-layer
SIREN initialized on a known wrong shape. Capacity and initialization budget
are configurable. The old comparison driver retains its small-network
defaults for reproducibility; its Kress `siren_*` cases now select adjoint
updates automatically. `--optimizer parameter_fd` is the explicit numerical
reference. Selecting MOD in that comparison still uses the parameter-FD
control, not the separate compressed-cloud MOD neural adjoint.

The following implementations must remain distinct:

| Implementation | Accepted geometry / update variables | Relation to the target |
|---|---|---|
| Legacy known-shape-family controls in `run_sdf_inverse_comparison.py` | 3/4/5/7 parameters; Method B is rebuilt for objective evaluations | Historical family-constrained recovery controls; no full-MLP update |
| `run_implicit_mlp_inverse.py`; comparison driver Kress `siren_*` cases | Neural weights via Kress adjoint and the actual Method-B reverse | MLP-owned neural inverse; full candidate extraction/forward controls acceptance |
| Comparison driver with explicit `--optimizer parameter_fd` | Implicit/network parameters via finite differences, followed by Method B | Numerical derivative/control experiment; forward cost grows with parameter count |
| Historical alternating MLP feedback runs | Full MLP; modal proposals are fitted into it and the extracted candidate is re-solved | Superseded fitting/transfer implementation; its failures are historical evidence |
| `run_explicit_radial_fourier_inverse.py` (old `run_mlp_sdf_inverse_comparison.py` alias retained) | Authoritative radial Fourier coefficients; MLP fit and Method-B extraction audit that curve | Explicit curve control; `legacy_strict` remains only its fitting policy |

The old [parameter-control archive](../../results/legacy/known_shape_family_parameter_inverse)
contains a three-parameter circle, four-parameter ellipse with fixed rotation,
five-parameter star and seven-parameter frozen-random-feature radial field.
The star's five lobes are prescribed; center, mean radius, amplitude and
rotation remain unknowns recovered from measurements. The family is known,
but its target parameter values are not handed to the optimizer. The
seven-parameter case trains only four output coefficients plus center/radius,
not the full feature network. These successes do not establish full-MLP recovery.

The compatibility command `run_mlp_sdf_inverse_comparison.py` still selects
the explicit radial algorithm. Its `legacy_strict` policy means per-step
neural fitting and representation audits while radial coefficients own the
geometry. Use `run_implicit_mlp_inverse.py` for adjoint-driven neural updates.

## Recorded evidence and its limits

These measurements describe their recorded revisions. The legacy controls,
fitting studies and radial runs answer different questions from the current
MLP-owned inverse; none substitutes for its failed recovery qualification.

| Evidence | Recorded outcome | Interpretation |
|---|---|---|
| [Legacy known-shape-family circle control](../../results/legacy/known_shape_family_parameter_inverse/wrong-circle-mie-20260902/summary.md) | Kress recovers the circle with very small field and geometry errors | Keep an independent-Mie control for the complete conversion path |
| [Legacy known-shape-family star control](../../results/legacy/known_shape_family_parameter_inverse/wrong-star-nystrom-20260903/summary.md) | Recovery succeeds; Kress holdout relative error is about `3.14e-5`, with a material geometry representation floor | Separate conversion accuracy from forward quadrature accuracy |
| [MLP feedback, wrong ellipse to star](../../results/legacy/inverse/mlp_feedback/mlp-fixed-ellipse-to-star-kress-20260903/summary.md) | 25 accepted updates; holdout error worsens from about `1.003` to `1.043`, maximum boundary error from `42.0` to `46.7 mm`; spectral-tail stop | A decreasing intermediate objective and successful fitting are insufficient evidence of useful accepted MLP updates |
| [Radial K5 continuation](../../results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md) | Canonical holdout error `1.339e-8`; extracted MLP holdout error about `0.004327` and canonical/MLP drift about `0.329 mm` | The data and solver can recover this exactly representable radial target; MLP/curve transfer remains a separately measurable limitation |
| [Smooth distance supervision](../../results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md) | Smooth targets reduce extracted star drift from about `1.605` to `0.535 mm`; the fit still misses the `0.2 mm` gate | Supervise the intended smooth interface and audit independently; changing distance targets alone has not solved the fit |
| [Discrete Kress derivative validation](../../results/validation/kress_shape_derivative/refined-audits-20260906/summary.md) | Verified directional derivatives and paired-objective adjoints for declared smooth curve/material perturbations | Established the derivative foundation; neural/Method-B coupling is now implemented and separately validated |

The representation-policy ablation reproduces the same radial coefficients
without intermediate fitting. That result measures redundant fitting **in
the radial-owned loop**. It does not establish that an MLP-owned Method-B
inverse cannot work.

Canonical radial recovery works on its recorded cases, while delivery of a
faithful MLP can fail separate representation gates. The current neural and
recorded radial runs have not been compared under a matched benchmark; their
different acquisitions, initialization, shape spaces and work budgets matter.

## Validation and unresolved recovery

The geometry reverse has been checked against analytic Kress directions,
and the full neural-weight gradient against fresh extraction/Method-B/BEM
finite differences at two resolutions. Tests also cover accepted-network
updates and rollback. These validate the implemented derivative and state
transition on tested smooth branches; they do not establish successful
reconstruction or derivatives through topology changes.

Further qualification needs separate measurements of the following:

1. **Conversion fidelity.** Freeze the MLP and refine extraction grid,
   projected samples, Cartesian bandwidth, arc-length integration and BEM
   nodes independently. Measure both directions of contour-set distance,
   normalized field residual, regularity, coherent curve derivatives and
   changes in forward prediction. Sampled checks are not continuous certificates.
2. **Neural field quality.** Measure initial-shape fitting and exact-target
   fitting controls separately from inverse optimization. Distinguish MLP
   fitting error, extraction error and Method-B refitting error; record
   Eikonal and off-contour distance quality separately from boundary accuracy.
3. **Recovery and work.** Report actual-MLP data and holdout errors, symmetric
   geometry error, refinement, accepted/rejected steps and failure reasons.
   Independent recovery gates are qualification checks, beyond the production
   line search's data/regularization and step-validity conditions.
4. **Controlled comparisons.** Compare Implicit MLP + Method B, Explicit
   Radial Fourier and Legacy known-shape-family controls with declared data,
   initialization, geometry resolutions and work budgets. No matched benchmark
   has been completed. Keep holdout data out of acceptance and setting selection;
   qualify a non-star-shaped target and its independent reference before
   extending recovery claims to it.

The [component diagnostic commands](../implicit_mlp_diagnostics.md) provide
frozen conversion, shared-checkpoint Eikonal fitting and a legacy one-step
curve-to-MLP transfer control. The last uses modal finite differences and
fitting; it does not run or reproduce the production adjoint update. These
opt-in studies have not been executed or numerically validated.

The recorded `1.5 mm` radial drift cap and `0.2 mm` representation/export
gate serve separate purposes in Explicit Radial Fourier. They are not
universal tolerances for this pipeline. Each benchmark must declare its
geometry, field, representation and refinement gates. Optimizer termination,
reconstruction accuracy and valid SDF delivery remain separate outcomes.

The principal implementation seams are
[the implicit model and initialization](../../solvers/sdf_inverse/models.py),
[continuous distance](../../solvers/sdf_inverse/continuous_distance.py),
[Method-B geometry](../../solvers/sdf_inverse/geometry.py),
[parameter-FD reference](../../solvers/sdf_inverse/optimization.py) and
[discrete Kress derivatives](../../solvers/gpr_bem_kress/shape_derivative.py),
[Kress geometry reverse](../../solvers/gpr_bem_kress/geometry_pullback.py),
[Method-B reverse](../../solvers/sdf_inverse/method_b_pullback.py), and
[implicit adjoint optimizer](../../solvers/sdf_inverse/implicit_adjoint.py).
