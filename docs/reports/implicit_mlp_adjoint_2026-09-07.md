# Implicit MLP + Method B adjoint implementation — 2026-09-07

The neural Method-B inverse now updates MLP weights directly with the Kress
adjoint. **Implicit MLP + Method B** names this MLP-owned path;
**Explicit Radial Fourier** names the separate curve-owned control.
The preferred commands are `run_implicit_mlp_inverse.py` and
`run_explicit_radial_fourier_inverse.py`. Existing entry points remain usable.

## What changes during an inverse step

The MLP supplies a scalar field whose zero contour is the object boundary.
Extraction and Method B turn that contour into a smooth ordered curve for
Kress. The forward solve predicts measurements. The adjoint converts their
error into sensitivities to the boundary geometry, including curve derivatives,
normals, speeds, quadrature and receiver evaluation. A reverse calculation
through the actual extraction/Method-B operations transfers those sensitivities
to network weights. Adam proposes new weights; their newly extracted curve
must lower the measured-data objective before acceptance.

This preserves the MOD neural inverse's direct field-update principle. It does
not reuse MOD's solver-specific, frozen-normal/frozen-weight offset-kernel shape
derivative. The Kress reverse differentiates the discrete Kress forward problem
and composes it with the Method-B conversion. It does not separately move a
curve and train the MLP to copy it. Finite differences remain available as an
explicit reference and in validation, with none in this optimizer's updates.

The SDF is represented by the neural weights, so updating those weights updates
the field everywhere and moves its zero contour. Eikonal regularization encourages
distance-like values. This is an implicit field, not a certified exact signed
distance function. Initialization and the separate exact-target representation
control still involve fitting known shapes; neither is a per-step inverse fit.

The conversion derivative is local to the current marching-square connectivity,
contour phase and interpolation/projection branches. It replays edge interpolation,
projection, chord resampling, Fourier fitting and arc-length refitting with
autograd and checks agreement with the production curve. It does not
differentiate topology changes; exact grid-vertex crossings are explicitly
rejected as derivative ambiguities. Every trial uses fresh production extraction
and a forward solve. Rejection or solver errors restore accepted weights.

Implementation: [optimizer](../../solvers/sdf_inverse/implicit_adjoint.py),
[Kress reverse](../../solvers/gpr_bem_kress/geometry_pullback.py),
[Method-B reverse](../../solvers/sdf_inverse/method_b_pullback.py).

## Validation

Focused tests compare the Kress reverse with independent analytic directional
derivatives and fresh forward finite differences, verify Method-B geometry
replay and neural derivatives, and check the entire neural-weight → extraction
→ Method-B → BEM objective at two resolutions. Optimizer regressions require
actual-network loss decrease and rollback, and prohibit calls to FD or curve
distillation. Driver tests cover routing, defaults, reporting and checkpoint
reload. The combined test command and result are recorded in
[validation.json](../../results/validation/implicit_mlp_adjoint/validation.json).

A separate [initial-star gradient audit](../../results/validation/implicit_mlp_adjoint/star-20260907/initial_star_gradient_audit.json)
uses the actual 1,185-weight star initialization and its independent observations.
Two directions and two step sizes (`2e-6`, `1e-6`) agree with the full fresh
objective to a maximum relative error of `2.74e-8`. Its eight FD probes are
validation-only and are distinct from the optimizer's zero probes.

## Bounded inverse results

These runs use fixed training/holdout data and settings, with no holdout-based
tuning. Both finish and save neural checkpoints, trajectories, metrics and
figures. They use `--no-gate` to complete diagnostic jobs; their recorded overall
acceptance remains **FAIL**.

| Measurement | Circle | Five-lobe star |
|---|---:|---:|
| Network | 64 wide, 2 hidden layers; 8,577 weights | 32 wide, 1 hidden layer; 1,185 weights |
| Kress nodes / acquisition pairs | 64 / 8 | 128 / 6 |
| Accepted updates | 41 (60 maximum) | 5 (5 maximum) |
| Training loss, initial → final | 0.921001 → 3.09194e-6 | 1.27519 → 1.03088 |
| Training relative L2, initial → final | 0.975395 → 0.00183753 | 1.12559 → 1.02016 |
| Holdout relative L2, initial → final | 1.46648 → 0.0707213 | 0.891375 → 1.11790 |
| Maximum node-to-exact-boundary distance, initial → final | 43.2594 → 1.03790 mm | 38.9521 → 41.7873 mm |
| Same network fitted to exact target: boundary distance | 0.234752 mm | 11.5632 mm |
| Actual forward evaluations / adjoint solves | 312 / 84 | 26 / 10 |
| Rejected trials (including invalid geometry) | 270 (3 invalid) | 20 (0 invalid) |
| Optimization FD probes / curve distillation steps | 0 / 0 | 0 / 0 |
| Inverse wall time, excluding pretraining/oracle/reporting | 36.54 s | 19.30 s |
| Stop | No decreasing neural step | Maximum iterations |

The circle improves substantially, but its final contour and holdout errors
exceed twice the measured exact-target fitting control, and optimization stops
above the declared data tolerance. The star run demonstrates five valid data
steps; its geometry and holdout worsen. The small star network's exact-target
fit is itself poor. These measurements do not establish a theoretical
representation floor or isolate the reason for reconstruction failure.

The circle uses independent Mie data, with training frequencies 0.25 and 0.5 GHz
and holdout frequencies 1, 1.5 and 2.5 GHz. The star uses independent Nyström
data, with training frequencies 0.5 and 1.5 GHz and holdout frequencies 0.25,
1 and 2.5 GHz. Full settings, material/acquisition definitions, gates and commands:
[circle summary](../../results/validation/implicit_mlp_adjoint/circle-verified-20260907/summary.md),
[star summary](../../results/validation/implicit_mlp_adjoint/star-20260907/summary.md).
Node-to-boundary distances above are the existing benchmark metric, not a
continuous symmetric Hausdorff certificate. Timings are individual runs.

## Later 12-pair recovery checks

The subsequent runs stamped `20260907T151516` use 12 acquisition pairs,
64-wide, two-hidden-layer SIRENs and a maximum of 60 neural updates. All
three report `acceptance_passed: false`. **Current implicit-MLP recovery
remains FAIL / unresolved**, even though the tested gradient chain is accurate.

| Run | Accepted updates | Training loss, initial → final | Holdout relative L2, initial → final | Final maximum node-to-boundary error | Stop |
|---|---:|---:|---:|---:|---|
| [Circle → circle](../../results/inverse/implicit_mlp/2026-09-07/circle/summary.md) | 43 | 0.921063 → 2.61771e-6 | 1.41727 → 0.0639441 | 1.03817 mm | No decreasing neural step |
| [Ellipse → circle](../../results/inverse/implicit_mlp/2026-09-07/ellipse-to-circle/summary.md) | 60 | 1.77149 → 7.40537e-5 | 1.66865 → 0.318638 | 6.45039 mm | Maximum iterations |
| [Star → star](../../results/inverse/implicit_mlp/2026-09-07/star/summary.md) | 60 | 1.28090 → 0.0624068 | 0.881949 → 0.783925 | 26.8327 mm | Maximum iterations |

Here the shape names describe the initialization and target; inverse updates
act on all 8,577 network weights. These are separate from the archived
[known-shape-family parameter inverses](../../results/legacy/known_shape_family_parameter_inverse),
which estimate only 3, 4, 5 or 7 controls. Those historical controls prescribe
the family (including five lobes for the star), while recovering its unknown
geometric parameter values from data. Their successes do not establish
full-MLP recovery.

The new circle, ellipse and star runs respectively use 334, 364 and 346 actual
forward evaluations and 88, 120 and 120 adjoint solves, with zero optimization
FD probes and zero curve-distillation steps. The decreasing training objectives
do not overcome the failed reconstruction gates. Canonical radial recovery
succeeds on recorded cases, but its neural representation gates are separate,
and no matched implicit-versus-radial benchmark has been completed.

## Superseding measurements

The recovery outcomes above were later re-examined. The
[failure audit](../../results/validation/implicit_mlp_adjoint/failure-audit-20260907/README.md)
attributed them to a premature line-search stop, star pretraining bias and
Method-B contour distortion; the
[repairs](../../results/validation/implicit_mlp_adjoint/repairs-20260907/README.md)
addressed each and added a conversion fidelity guard; the
[reruns](../../results/validation/implicit_mlp_adjoint/rerun-20260907/README.md)
then found that the Method-B Fourier bandwidth, not the optimizer, bounded both
targets. With the bandwidth raised, the circle accepts all 60 updates and ends
on its iteration budget at a refinement-converged conversion error, reaching the
same accuracy the run below reports. Overall recovery still FAILS on both
targets. The runs in this report retain their original settings and outcomes and
are not restated by those later measurements.

## Comparison with the old implicit-MLP finite-difference inverse

No matched FD-versus-adjoint recovery benchmark was run for this implementation.
The FD checks above validate derivatives, not optimization speed or reconstruction
superiority. The historical [SIREN parameter-FD circle run](../../results/legacy/inverse/siren_parameter_fd/siren-circle-mie-20260903/summary.md)
used Kress and the same Method-B resolution, but a different network and acquisition:

| Circle measurement | Historical parameter FD | New adjoint |
|---|---:|---:|
| Trainable weights | 129 | 8,577 |
| Acquisition pairs | 12 | 8 |
| Accepted updates | 10 | 41 |
| Forward evaluations | 2,931 | 312 |
| Inverse wall time | 271.00 s | 36.54 s |
| Final holdout relative L2 | 1.03486 | 0.0707213 |
| Maximum node-to-exact-boundary distance | 17.9750 mm | 1.03790 mm |

These are historical context, not a controlled speedup or accuracy comparison.
The FD path uses damped Gauss–Newton; the adjoint path uses Adam with Eikonal
regularization and different acceptance rules. Initial weights, capacity,
acquisition and iteration budgets also differ. Both runs fail overall recovery
acceptance. A matched algorithm comparison must share initialization, network,
data and geometry settings and report equal work/time budgets. Isolating the
derivative method additionally requires the same optimizer, regularization and
acceptance policy. `--optimizer parameter_fd` retains the old neural-weight FD
reference, but switching that flag alone changes more than the derivative.

## Provenance and limits

Runs record the dirty working tree based on commit
`659c7e47988826352ec00a4b4b0d9c7ca19dd4bb`. The implementation is not committed.
[validation.json](../../results/validation/implicit_mlp_adjoint/validation.json)
records a post-validation source hash manifest. After the runs, driver wording
was corrected to describe the actual differentiable conversion and the named
implicit default iteration budget became 60. Both measured runs explicitly set
their budgets; these edits do not change their numerical results. Their summaries
carry an editorial note; measured JSON, CSV and weights are preserved.

An earlier 20-step circle attempt reached checkpoint saving but failed in report
export because a misplaced overwrite-cleanup block referenced `overwrite` outside
its function. That driver bug was fixed and regression-tested before the complete
circle run above. Its partial [bundle](../../results/validation/implicit_mlp_adjoint/circle-20260907/FAILED.md)
is retained and is not counted as a completed recovery experiment.

Gradient correctness is established for the tested smooth branches. Successful
general reconstruction, topology changes, global SDF accuracy and extraction/BEM
refinement remain separate requirements. No claim of solved star recovery or
universal convergence follows from this implementation.
