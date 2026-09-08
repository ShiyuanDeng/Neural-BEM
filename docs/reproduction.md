# Reproduction commands

Updated 2026-09-07 for the implemented **Implicit MLP + Method B** Kress-adjoint
inverse. Run these commands from the repository root after reviewing the
[result register](../results/README.md). The
[new validation report](reports/implicit_mlp_adjoint_2026-09-07.md) records the
executed gradient tests and circle, ellipse-to-circle and star runs, including
failed recovery gates for all three new 12-pair cases. Recovery remains
unresolved. **Explicit Radial Fourier** owns radial coefficients and has
separate reconstruction and MLP representation gates. Optional archived
controls below do not constitute another active inverse pipeline.

## Choose evidence to refresh

| Scope | Run | Question it answers |
|---|---|---|
| Current pipeline | [Implicit MLP + Method B](pipelines/implicit_mlp.md) | Are full neural gradients correct, actual-MLP steps decreasing, and independent recovery checks satisfied? |
| Current pipeline | [Explicit Radial Fourier](pipelines/explicit_radial_fourier.md) | Does the explicit curve recover the data, and does its fitted MLP satisfy separate representation gates? |
| Regression and derivative validation | Focused tests and Kress audits | Do geometry, update, rollback, and derivative contracts still hold? |
| Conversion diagnostics | Frozen Method B studies and [Implicit MLP diagnostics](implicit_mlp_diagnostics.md#commands) | Which errors belong to extraction, conversion, Eikonal activation, or transfer? Diagnostic commands are available; the experiments have not been run. |
| Radial variants | Representation policies and [shape/material controls](pipelines/explicit_radial_shape_material.md) | What changes when fitting policy, material unknowns, or continuation change? |
| Optional archive | [Legacy known-shape-family controls](legacy/known_shape_family_controls.md) | Does Method B still recover the small prescribed families? |

Keep failed runs as evidence and write new measurements to fresh directories.
Directory and documentation changes do not require numerical reruns.

## Shared shell setup

Use one Bash session for the setup and commands below. Each command writes
to a new directory. Refresh `REPRO_STAMP` before repeating the same command;
none of these commands requests overwrite.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
REPRO_STAMP=$(date -u +%Y%m%dT%H%M%S%NZ)
REPRO_DATE=$(date -u +%Y-%m-%d)
REPRO_PY=(env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python)
```

These are new runs against the current working tree. Original commands,
commit identities, dirty-tree records, and measurements remain in the saved
bundles. A current run is not a claim of byte-for-byte historical replay.

## Focused regressions

This covers the Method B frontend, parameter-family inverse controls,
current neural fitting/acceptance contracts, direct curve updates,
representation policies, parameter-aware driver, and Kress derivative seam.
The neural adjoint has its additional focused tests in the next section.

```bash
"${REPRO_PY[@]}" -m pytest -q \
  pytest/ordered_boundary \
  pytest/sdf_to_ordered_boundary \
  pytest/sdf_inverse/test_solver_neutral_inverse.py \
  pytest/sdf_inverse/test_star_target_inverse.py \
  pytest/sdf_inverse/test_parameter_fd_audit_regressions.py \
  pytest/sdf_inverse/test_geometry_sign_contract.py \
  pytest/sdf_inverse/test_neural_mlp_inverse.py \
  pytest/sdf_inverse/test_neural_redistance_regressions.py \
  pytest/sdf_inverse/test_neural_audit_regressions.py \
  pytest/sdf_inverse/test_direct_curve_updates.py \
  pytest/sdf_inverse/test_distillation_policy.py \
  pytest/sdf_inverse/test_representation_ablation_driver.py \
  pytest/solver_comparisons/test_parameterization_aware_driver.py \
  pytest/gpr_bem_kress/test_shape_derivative.py \
  pytest/solver_comparisons/test_kress_shape_derivative_driver.py
```

## Implicit MLP + Method B adjoint

The named entry point uses a float64 SIREN (width 64, two hidden layers),
Kress adjoint, direct neural updates and fresh extraction/Method-B/BEM for
candidate acceptance. It defaults to 60 update attempts. Initial fitting and
the separate exact-target representation control are diagnostics outside the
inverse loop; no proposed curve is fitted during an adjoint update.

```bash
"${REPRO_PY[@]}" -m pytest -q \
  pytest/gpr_bem_kress/test_geometry_pullback.py \
  pytest/sdf_inverse/test_method_b_pullback.py \
  pytest/sdf_inverse/test_implicit_adjoint.py \
  pytest/sdf_inverse/test_implicit_adjoint_driver.py

"${REPRO_PY[@]}" run_implicit_mlp_inverse.py \
  --target circle --max-iterations 60 --num-pairs 12 --num-nodes 64 \
  --output-dir "results/inverse/implicit_mlp/${REPRO_DATE}/circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_implicit_mlp_inverse.py \
  --target circle --initial-model siren_ellipse \
  --max-iterations 60 --num-pairs 12 --num-nodes 64 \
  --output-dir "results/inverse/implicit_mlp/${REPRO_DATE}/ellipse-to-circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_implicit_mlp_inverse.py \
  --target star --max-iterations 60 --num-pairs 12 --num-nodes 128 \
  --output-dir "results/inverse/implicit_mlp/${REPRO_DATE}/star-${REPRO_STAMP}"
```

These bounded experiments currently fail some recovery gates; a nonzero gate
exit is expected. Artifacts are written before enforcement. The saved validation
runs used `--no-gate` to finish as diagnostic jobs; that option does not alter
optimization, gate values or the reported failure. These commands use the
same declared 60-attempt budgets as the new 12-pair runs; none currently
establishes successful recovery. Check
`metrics.json`, `summary.md`, trajectories and the accepted `kress_model.pt`.
Per-solver diagnostics count adjoint solves, actual forward evaluations,
rejected trials and zero optimization FD probes/distillation steps.

Use `run_explicit_radial_fourier_inverse.py` for the existing radial experiment.
The old `run_mlp_sdf_inverse_comparison.py` name remains a compatibility entry
point. In the shared comparison driver, Kress `siren_*` cases now default to
adjoint; `--optimizer parameter_fd` explicitly selects the numerical reference.

### Optional neural finite-difference reference

This updates every SIREN weight through a numerical residual Jacobian. It is
distinct from the archived known-shape-family controls. The small network
keeps that reference bounded; its forward cost grows with its parameter count.

```bash
"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target circle --initial-model siren_circle --solvers kress \
  --optimizer parameter_fd --mlp-hidden-features 32 --mlp-hidden-layers 0 \
  --max-iterations 10 --num-pairs 12 --num-nodes 64 \
  --output-dir "results/inverse/implicit_mlp/${REPRO_DATE}/parameter-fd-reference-${REPRO_STAMP}"
```

The reference uses damped Gauss–Newton; the adjoint path uses Adam and Eikonal
regularization. A flag switch therefore compares complete optimizer policies,
not just derivative implementations. No matched FD-versus-adjoint neural
recovery benchmark has been completed. Directional FD checks in the tests
above validate gradients rather than reconstruction performance.

## Explicit Radial Fourier

This pipeline updates radial Fourier coefficients. Its MLP fits and audits
the curve under the `legacy_strict` policy; it does not own the accepted
physics geometry. Recorded canonical reconstruction success and neural
representation failures are separate outcomes.

```bash
"${REPRO_PY[@]}" run_explicit_radial_fourier_inverse.py \
  --target star --initial-shape ellipse --solvers kress \
  --output-dir "results/inverse/radial_fourier/ellipse-to-star-${REPRO_STAMP}"
```

Use the representation-policy commands below to compare fitting and export
policies. The [pipeline page](pipelines/explicit_radial_fourier.md) records
the geometry ownership and continuation defaults.

## Optional archive: Legacy known-shape-family controls

These optimize a small implicit-field parameter vector using finite
differences. Each candidate is extracted and fit through Method B before
the paired MOD/Kress prediction. They test the conversion and forward path
within prescribed shape families; they do not optimize a general MLP.

The saved archive covers 3 circle, 4 ellipse, 5 star and 7 frozen-random-feature
parameters. The [archive explanation](legacy/known_shape_family_controls.md)
describes their scope. The star has five lobes fixed in advance; its center, mean radius,
amplitude and rotation are recovered from measurements. Family knowledge is
provided, not the correct values of the unknown parameters. These controls
remain reproducible, but their outputs belong in
`results/legacy/known_shape_family_parameter_inverse/`, outside the two active
inverse pipelines.

The first two commands use independent analytic Mie circle observations,
starting from a wrong circle and a non-distance ellipse. The third uses
independent Nyström observations of a five-lobe star and a wrong star
initialization. Frequencies, geometry resolutions, material definitions,
and acquisition coordinates are recorded by the driver.

```bash
"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target circle --initial-model circle --solvers mod kress \
  --optimizer parameter_fd \
  --output-dir "results/legacy/known_shape_family_parameter_inverse/circle-to-circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target circle --initial-model ellipse --solvers mod kress \
  --optimizer parameter_fd --max-iterations 8 \
  --output-dir "results/legacy/known_shape_family_parameter_inverse/ellipse-to-circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target star --initial-model star --solvers mod kress \
  --optimizer parameter_fd \
  --output-dir "results/legacy/known_shape_family_parameter_inverse/star-to-star-${REPRO_STAMP}"
```

Read `summary.md` alongside `metrics.json`: compare recovered geometry,
training and held-out fields, finite-difference consistency, and declared
acceptance gates. Retain failed gates rather than suppressing them with
`--no-gate`.

## Frozen Method B curves and fitting diagnostics

This first command reuses three checked Cartesian Method B coefficient
bundles. It holds the continuous fitted curve fixed while refining Kress
nodes and comparing with the independent high-resolution Nyström solver.
It does not repeat SDF fitting and does not run an inverse. The curves are
normalized to a 0.05 m mean radius by the driver.

```bash
REPRO_CURVES=results/validation/sdf_boundary_parameterization/kress-scalar-proxy-20260902/frozen_curves
"${REPRO_PY[@]}" run_ordered_nystrom_validation.py \
  --preset quick --nodes 128,256 --reference-nodes 512 --shapes none \
  --curve-npz "${REPRO_CURVES}/circle__g257x257__m256__b__k004.npz" \
  --curve-npz "${REPRO_CURVES}/rotated_ellipse__g257x257__m256__b__k032.npz" \
  --curve-npz "${REPRO_CURVES}/radial_fourier_star__g257x257__m256__b__k032.npz" \
  --timing-repeats 3 --enforce \
  --output-root results/validation/ordered_boundary_nystrom \
  --run-id "method-b-frozen-${REPRO_STAMP}"
```

The next command repeats the bounded C1/C2 study: an exact ellipse
parameterization control, followed by Method B, skip-refit, and ordered-label
fits using a shared frozen extraction per case. Circle, ellipse, star, and
a smooth non-star-shaped case are included. This is a fitting and
physical-field study, not neural inverse recovery.

```bash
"${REPRO_PY[@]}" run_parameterization_aware_comparison.py \
  --cases circle,ellipse,star,nonstar \
  --bandwidths 1,2,4,8,16 --bem-nodes 32,64,128 \
  --grid-size 257 --projected-samples 128 \
  --audit-samples 256 --localization-samples 1024 --fit-iterations 100 \
  --output "results/validation/parameterization_aware/method-b-controls-${REPRO_STAMP}"
```

Use the separate geometry, representation-validity, oracle, and physical
field gates in `metrics.json`. A small fitting residual or successful
optimizer exit alone is insufficient. Retain failed fits and unresolved
refinement as part of the comparison.

## Explicit Radial Fourier representation policies

These compare `legacy_strict`, `curve_only`, and `export_only` on the
current radial Fourier state. `legacy_strict` is the existing policy name;
it requires per-step neural fitting and representation acceptance within the
radial experiment. The radial curve continues to own the geometry.

Start with the short ellipse-to-circle control. Run the saved-star profile
when a change warrants the longer comparison. The latter reads the recorded
September 4 radial ellipse-to-star configuration; it is not a restored
pre-radial pipeline.

```bash
"${REPRO_PY[@]}" run_sdf_representation_ablation.py \
  --profile short --policies legacy_strict curve_only export_only \
  --output-dir "results/inverse/radial_fourier/representation_policies/short-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_sdf_representation_ablation.py \
  --profile saved-star --policies legacy_strict curve_only export_only \
  --output-dir "results/inverse/radial_fourier/representation_policies/saved-star-${REPRO_STAMP}"
```

Compare reconstruction and representation status separately. Inspect
trajectory equality for curve-only versus export-only, actual neural work,
extracted-curve drift, and held-out fields. An initialization failure under
`legacy_strict` means that policy's inverse did not run successfully.

## Kress derivative validation

This checks the complete discrete geometry/material derivative, paired
objective adjoint, independent references, and physical refinement. Its
geometry inputs are explicit curves. This audit does not include the neural
extraction/Method-B reverse; the neural pullback tests above check that chain.

```bash
"${REPRO_PY[@]}" run_kress_shape_derivative_validation.py \
  --cases circle ellipse star zero_contrast \
  --nodes 32 64 128 --frequencies-ghz 0.5 1.5 \
  --steps 1e-2 1e-3 1e-4 1e-5 1e-6 \
  --output-dir "results/validation/kress_shape_derivative/refined-audits-${REPRO_STAMP}"
```

Read both `discrete_gate_passed` and `physical_gate_passed`, including
per-case failed rows. A fixed-node derivative identity is distinct from
convergence to the independent physical reference.

## Optional Explicit Radial Fourier shape/material controls

These retain their separate scope: fixed-circle or radial K2 shape with
one unknown interior permittivity. They are not Implicit MLP + Method B
recovery experiments.

```bash
"${REPRO_PY[@]}" -m pytest -q \
  pytest/sdf_inverse/test_material_inverse.py \
  pytest/sdf_inverse/test_robust_material_inverse.py \
  pytest/solver_comparisons/test_material_inverse_driver.py \
  pytest/solver_comparisons/test_material_robustness_driver.py

"${REPRO_PY[@]}" run_material_inverse_comparison.py \
  --nodes 64 --audit-nodes 64 128 256 --max-evaluations 40 \
  --output "results/inverse/radial_fourier/shape_material/material_inverse/bounded-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_material_robustness_comparison.py \
  --frozen-d results/inverse/radial_fourier/shape_material/material_inverse/bounded-20260906 \
  --nodes 64 --audit-nodes 64 128 256 --oracle-nodes 128 256 512 1024 \
  --stage-max-evaluations 40 40 \
  --maximum-forward-solves 400 --maximum-direction-evaluations 2400 \
  --output "results/inverse/radial_fourier/shape_material/material_robustness/bounded-${REPRO_STAMP}"
```

The robustness command deliberately reads the original frozen material
dataset, not the new material run above. Its required `arrays.npz` is a
local ignored artifact; preserve it with the bundle. If it is unavailable
in another checkout, exact frozen-data replay is unavailable there until
that artifact is restored. Do not silently substitute newly generated
observations under the old run identity.

## Interpreting the remaining failures

[Implicit MLP diagnostics](implicit_mlp_diagnostics.md#commands) provide three
component experiments for conversion, Eikonal activation, and one-update
transfer. Their contract tests have run; the experiments themselves have not.
They do not perform inverse recovery.

The current neural gradient and rollback tests verify the update contract.
Physical qualification still requires accurate reconstructed geometry,
re-extracted fields, and held-out measurements. Frozen-state conversion and
BEM-resolution studies can separate these errors without changing the inverse
state during an audit.

No matched comparison with Explicit Radial Fourier has been completed. Such a
comparison must record matching observations, initialization conventions,
resolution, and work accounting, as well as differences in available shapes.
The existing non-star-shaped frozen fitting case demonstrates conversion
scope, not non-star-shaped neural inverse recovery.
