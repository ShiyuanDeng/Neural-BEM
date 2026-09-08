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

The latest [iteration-3 results](../iterations/implicit_mlp/iteration_03/01_results.md)
close the iteration-2 diagnostic and acquisition experiments. Both long star
arms completed, accepting 42 paired and 31 multistatic updates before their
searches stopped. Multistatic improves geometry at matched work but still
loses lobe amplitude. The [research handoff](../iterations/implicit_mlp/README.md)
records the current stage and supported next questions.

The subsequent [failure audit](../../results/validation/implicit_mlp_adjoint/failure-audit-20260907/README.md)
identified a premature line-search stop, pretraining bias and conversion drift.
The fixes below change current defaults; the saved recovery runs above retain
their original settings and FAIL outcomes.

The [reruns after those repairs](../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md)
then showed that the **Method-B Fourier bandwidth** constrained both targets:
the original circle and star runs stopped near the conversion-fidelity budget.
Raising it lets the circle accept all 60
updates and end on its iteration budget rather than a stall. Overall recovery
still FAILS on both targets, and the star's lobe amplitude and phase move away
from the target while its training loss falls.

The [checkpoint review](../../results/validation/implicit_mlp_adjoint/review-20260908/README.md)
corrects the bandwidth-96 star's termination: its next candidate failed the
independent conversion-refinement-change gate, and acceptable fallback steps
exist beyond the historical eight-backtrack limit. The first such step lowers
loss by only 0.039%; resolving search termination does not resolve the roughly
36 mm reconstruction error.

The subsequent [matched controls and observability study](../../results/validation/implicit_mlp_adjoint/latest-direction-20260908/README.md)
recovers the five-parameter star with eight pairs. At both analytic initial and
target geometries, all three acquisitions have full rank in the tested 21-mode
space when 0.5/1.5 GHz are stacked. Multistatic readout improves conditioning,
and 1.5/2.5 GHz strengthens the weakest modes further. These local diagnostics
support the next acquisition ablation; they do not establish general neural
sufficiency. A three-step target-fitted MLP run improves data and holdout losses
while its maximum boundary error rises slightly from 1.191 to 1.290 mm.

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
Neural driver runs additionally require raw/converted contour agreement within
`--conversion-tolerance-mm` (default `0.2`). The check independently extracts
the raw contour at two refined grids and sample counts, and measures symmetric
vertex-to-polygon distances. Their change must be within 5% of the budget.
An unresolved or excessive discrepancy rejects a candidate before its BEM
solve. This is a sampled numerical guard, not a continuous zero-set certificate;
the conversion map and its adjoint replay are unchanged. API callers can opt
in through `OrderedSDFGeometryConfig.conversion_tolerance_m`.

The conversion resolution is what that guard actually constrains, and the
bandwidth dominates it. Refining the extraction grid and projected samples at
a fixed bandwidth changed the measured star error by under a micrometre, while
raising the bandwidth from 48 to 96 reduced it from `0.1999 mm` to `0.0206 mm`;
the circle behaves the same way between bandwidths 10 and 20. `--bandwidth`,
`--grid-resolution` and `--projected-samples` set these per run and default to
each target's own values. A bandwidth needs at least `2 * bandwidth + 2` nodes
and projected samples to be sampled without aliasing, so raising it also raises
BEM cost; invalid combinations are rejected by the parser. The shipped target
defaults are unchanged.
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
The steepest-descent fallback caps large gradients but does not amplify small
ones to a fixed proposal length. Thus its trial size shrinks near a fitted
solution instead of imposing the premature minimum-step stop found in the audit.
Solver/derivative errors propagate without an FD fallback. Exact marching-grid vertex crossings have
no unique branch derivative and are reported explicitly. Connectivity,
phase choices and interpolation/projection branches remain discrete: the
local derivative does not certify a topology-changing step.

Neural adjoint runs now default to 14 backtracking halvings; parameter-FD
controls retain eight. Each evaluated neural trial records independent rejection
reasons in `kress_trials.jsonl`, including the two conversion gates separately.
The default 0.1 mm meaningful-boundary-step floor labels small accepted motions
for reporting and does not change acceptance. `--start-at-truth` initializes a
diagnostic inverse from the existing exact-target fitting control. Accepted
geometry/objective diagnostics are saved in `kress_accepted_iterates.json`;
per-iterate holdout solves are enabled by `--record-accepted-holdout` or
`--start-at-truth` and never enter the optimizer's decisions.

`PairedForwardProblem` continues to observe source row i at receiver row i.
The separate `IndexedForwardProblem` selects arbitrary source/receiver entries,
including full multistatic readout, from the existing full Kress solve. Its
curve/SDF prediction functions and indexed objective adjoint are used by the
matched neural runner. The shared implicit-adjoint optimizer dispatches both
paired and indexed acquisitions; the general comparison driver's paired
defaults remain available.

## Entry points and other implementations

The default named neural command uses a float64 64-wide, two-hidden-layer
SIREN initialized on a known wrong shape. Capacity and initialization budget
are configurable. The old comparison driver retains its small-network
defaults for reproducibility; its Kress `siren_*` cases now select adjoint
updates automatically. `--optimizer parameter_fd` is the explicit numerical
reference. Selecting MOD in that comparison still uses the parameter-FD
control, not the separate compressed-cloud MOD neural adjoint.

Pretraining regresses `F / ||grad F||`, which is exact for a circle's SDF but
only approximates distance for ellipse/star level sets. The default pretraining
Eikonal weight is now `0` for star proxies, avoiding the demonstrated conflict
between that global regression target and a unit-gradient penalty. Circle
and ellipse retain `0.1`: removing the ellipse penalty produced extra zero
contours in validation. `--mlp-pretrain-eikonal-weight` overrides this
choice for both the initialization and exact-target fitting control; `0.1`
restores the historical penalty. Its actual value is saved in pretraining
metadata. The inverse's independent `--eikonal-weight` still defaults to `0.01`.
This improves the measured star interface but does not certify distance quality
or general inverse recovery. The exact-target fit is a fitting control, not a
theoretical representation floor.

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
   The [reruns](../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md)
   cover the bandwidth/grid/sample factors on two frozen checkpoints; arc-length
   integration and BEM nodes remain unmeasured there.
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

The [iteration-2 implementation handoff](../iterations/implicit_mlp/iteration_02/03_implementation.md)
contains the frozen-state diagnostics, exact polygon replay evidence, ellipse
startup qualification, and bounded matched acquisition/sampling commands. New
inverse runs save actual optimizer moments and proposals. Contour-aware Eikonal
sampling and higher-band comparisons retain the final plan's measured-evidence
gates; no new long inverse is selected by the implementation alone.
