> Historical record, classified 2026-09-07. Statements of current behavior or
> next work below refer to their original date. The current research target is
> [strict MLP + Method B repair](../pipelines/strict_mlp_method_b.md); see the
> [architecture](../current_architecture.md) and [results catalogue](../../results/README.md).

# SDF / Kress priorities: first-batch implementation and evidence

Date: 2026-09-05. Tasks A, B and the bounded C1/C2 experiment from the
[implementation brief](../legacy/codex_sdf_kress_priorities_2026-09-05.md) are implemented.
Tasks D–H are deferred, as the brief requires. Existing user changes, baseline
defaults and historical measurements were preserved.

## Verdict

The guide's first batch was worth doing. On the saved star configuration the
SDF contributes no change to the accepted reconstruction, but consumes most
of the strict loop's extra work. Decoupling it is now a measured improvement,
not an inference from the old timing breakdown. Smooth-distance supervision
reduces interface and field errors in the frozen tests, but does not make the
MLP a reliable export at the requested budget. Parameter labels demonstrably
cost Fourier modes; the new fit earns a bounded experimental place, not a
production-default promotion.

These conclusions concern noiseless, homogeneous full-space 2-D TMz tests.
The star inverse remains a matched, fixed-topology radial chart with known
material and calibrated acquisition. This is not evidence of arbitrary-shape,
material, topology or 3-D inversion.

## A — reconstruction and representation have separate outcomes

`AlternatingNeuralInverseConfig.distillation_policy` selects one shared
optimizer loop:

| Policy | Reconstruction | Requested representation |
|---|---|---|
| `legacy_strict` (unchanged default) | Existing per-step neural fitting and representation vetoes | Existing strict behavior |
| `curve_only` | Canonical updates and geometry/physics validation; no neural work | Not requested; absent metrics are null |
| `export_only` | The same canonical path as curve-only | One smooth-target fit and audit after reconstruction |

Results add `reconstruction_converged`, `reconstruction_stop_reason`,
`representation_status`, `representation_stop_reason`,
`representation_evaluated`, and `requested_delivery_complete`. The legacy
`converged` and `stop_reason` retain their strict meanings. In new strict
results, `representation_limited_stationary` can therefore coexist with a
converged reconstruction and a failed representation only when the internal
accepted-state stationarity checks actually passed; the reason string alone
is not sufficient evidence. Old artifacts have not
been reinterpreted or rewritten.

`export_neural_sdf_representation` also supports explicit final-only export.
It requires a continuous canonical evaluator, trains a copy, and commits the
model only on success. A failed candidate is not returned as a deliverable
curve. The independent final-export drift gate is 0.2 mm; the historical
1.5 mm per-step safety cap is not an export-accuracy tolerance. Extraction
audits refine separately from BEM nodes. Canonical state is never replaced by
the approximate neural contour. If initialization genuinely comes from an
implicit field, its extraction and validity checks are still required.

The new [ablation driver](../../run_sdf_representation_ablation.py) performs
continuation before the single final export, rather than exporting at every
stage. It records actual SDF/gradient, training, extraction, audit, FD,
line-search and forward work. Strict warm-start cost, reconstruction, export,
final diagnostic cost and shared oracle preparation are separated.

### Fresh saved-star ablation

See the [measured summary](../../results/inverse/radial_fourier/representation_policies/saved-star-20260905/summary.md)
and [complete metrics](../../results/inverse/radial_fourier/representation_policies/saved-star-20260905/metrics.json).

| Policy | Reconstruction seconds | Export seconds | End-to-end seconds | Reconstruction / representation |
|---|---:|---:|---:|---|
| Strict | 229.74 | Not requested | 240.07 | Converged / failed |
| Curve-only | 81.61 | Not requested | 82.98 | Converged / not requested |
| Export-only | 81.62 | 8.41 | 91.40 | Converged / failed |

All three accepted the same 44 updates, with exactly equal recorded canonical
coefficients (declared comparison tolerance `1e-13`). All used 863 inverse
forward evaluations: 816 FD probes, 44 line-search probes, and three stage
initializations; no accepted backtracks or full-validation rejections.
Curve-only/export-only reconstruction made zero SDF value or spatial-gradient
calls, zero neural fits, zero extractions and zero neural field audits. Strict
reconstruction performed 44 fits, 15,160 training steps, 44 extractions and
47 field audits, in addition to its separately counted warm start.

All three achieved canonical training/holdout relative field errors
`1.0683e-8` / `1.3393e-8`. Frozen canonical BEM refinement from N128 to N256
changed the response by `5.89e-14` relative. The strict MLP retained 0.329 mm
drift and holdout error `0.004327`; its extracted-curve field refinement
difference was `1.36e-7`.

The one-shot smooth export exhausted 1,200 training steps: maximum canonical
boundary field residual was 0.351 mm and Eikonal RMS 0.104. It failed before
extraction, so exported-contour drift and fields are null, not zero or claimed
accurate. Its canonical result remains usable; the requested SDF delivery is
incomplete. Merely moving training to the end does not guarantee an export.

These are single-run timings, executed without other project benchmarks
competing for CPU. Shared preparation took another 16.94 seconds. The observed
reconstruction ratio is about 2.8, not a hardware-independent speed claim.
The preceding [short deterministic run](../../results/inverse/radial_fourier/representation_policies/short-final-20260905/summary.md)
also passed the policy contract, but its four updates intentionally did not
converge. Development artifacts are retained and labelled in the
[family index](../../results/inverse/radial_fourier/representation_policies/README.md).

## B — smooth targets improve the interface, not every SDF metric

`signed_distance_to_continuous_curve` localizes multiple candidate minima,
refines them with safeguarded one-dimensional searches, and repeats at a
finer localization resolution. It uses the closest-point outward normal for
the negative-inside sign on a regular simple CCW curve. Failure to reach the
declared numerical refinement agreement is explicit; this is not a global
distance certificate for unresolved arbitrary curves.

`NeuralRedistanceConfig.distance_target="smooth_curve"` requires a matching
continuous producer. The default remains `"legacy_polygon"`. Target tolerance
and localization resolution are independent of solver N. The public
`radial_fourier_parameterization(state)` exposes the exact current radial
curve rather than a new fit. Smooth boundary sampling is configurable;
`smooth_boundary_sampling="legacy_polygon"` isolates target changes at
identical sample locations, assigning actual smooth distances to polygon-edge
samples rather than falsely labelling them zero.

The [frozen circle/star experiment](../../results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md)
holds architecture, initialization, sample coordinates and 600-step budget
fixed, changing only distance targets. Its geometry, audit and field
refinements are stored independently.

| Case | Polygon → smooth extracted drift | Polygon → smooth relative field error |
|---|---|---|
| Circle | 0.233 → 0.0385 mm | 0.01568 → 0.000142 |
| Star | 1.605 → 0.535 mm | 0.05914 → 0.00380 |

The negative result matters: the star's independent global distance RMS
slightly worsened, 3.542 → 3.596 mm, and its contour still misses the 0.2 mm
gate. All four fits exhausted the strict training budget. Circle field
accuracy uses independent Mie data; the star reference is separately refined
Kress on the exact analytic curve, not an independent solver. A changed
normal-offset sampling experiment was not run.

## C — parameter labels matter, but compactness alone is not the gate

The opt-in [parameter-aware module](../../solvers/sdf_to_ordered_boundary/parameter_aware.py)
and [comparison driver](../../run_parameterization_aware_comparison.py) do not
redefine historical Methods A/B/C. C1 compares the same exact ellipse set in
native-angle and exact arc-length parameters, using inverted elliptic
integrals and consistent derivative jets, with no Fourier refit. C2 freezes
projected data and compares Method B, skipping its final arc-length refit,
and a new ordered-label variable-projection Fourier fit. The latter keeps
positive cyclic increments and fixed phase, records conditioning/validity,
and explicitly falls back on invalid or unfaithful fits. Unregularized and
declared spectral-penalty arms remain separate. It is not a reproduction of
the Zhao–Serkh algorithm.

The [bounded measured bundle](../../results/validation/parameterization_aware/first-batch-20260905/summary.md)
contains circle, rotated ellipse, star and a simple non-star-shaped Cartesian
reference, sweeping K1/2/4/8/16 independently of N32/64/128. It records 82
method results and 246 field rows, including seven fallbacks, in 45.50 seconds.
All four native independent Nyström references passed refinement; the
non-star shape needed N1024. Circle analytics provide an additional check.

C1 native-angle ellipse has N32 field error `1.085e-9`, versus `1.075e-4`
for exact arc length, despite the same geometry. Both reach about `1.82e-12`
at N128: parameterization changes quadrature convergence, not the exact field.

At 0.2 mm geometry and `1e-3` maximum-per-frequency field tolerances, C2
ellipse needs K16/N32 with Method B but K1/N32 with ordered-label fitting,
without increased matrix conditioning. Complete work was 0.614 versus
0.594 seconds, below the declared 10% work-reduction threshold. This is a
bounded lower-usable-bandwidth benefit, not an established speed advantage.
Ordered fits also qualify for the star at K8/N64 and non-star at K8/N128;
the baselines have no qualifying row in this ladder, so no matched-accuracy
work comparison is available. The penalty worsens the non-star result.

The [decision supplement](../../results/validation/parameterization_aware/first-batch-20260905/decision_summary.md)
adds the guide's bandwidth criterion from frozen measurements, with input
and postprocessor hashes; original measured files remain unchanged. Retain
this method as an opt-in experiment. There is no broad runtime-win evidence
and no default promotion.

## Reproduction and next decision

Use the `EMNerf` environment and set `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`,
`PYTHONPATH=solvers`. Drivers require fresh output directories; exact measured
commands, working-tree/source hashes, immutable physical observations,
coefficients, resolutions and non-pickled numeric archives are in each bundle.

```bash
python run_sdf_representation_ablation.py --profile short --output-dir results/sdf_representation_ablation/new-short
python run_sdf_representation_ablation.py --profile saved-star --output-dir results/sdf_representation_ablation/new-star
python run_smooth_distance_supervision_comparison.py --help
python run_parameterization_aware_comparison.py --help
```

The final [validation entry](validation_change_log.md#2026-09-05--sdfkress-guide-first-batch-abc)
records commands and test outcomes. Measured source hashes identify the
executed revisions; subsequent driver failure-path hardening and documentation
do not retroactively change those measurements.

Stop here for this batch. The practical next package is D: fixed-geometry
recovery of one interior permittivity, followed by a separate joint
shape/material identifiability experiment. E, a verified derivative of the
actual Kress objective, precedes genuine neural-induced updates. Multi-material,
topology, close-target quadrature and 3-D remain separate design decisions.
