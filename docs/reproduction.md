# Reproduction and next experiments

Prepared 2026-09-07. These commands were checked against the driver source;
no tests, fitting runs, or inverse experiments were executed during the
documentation cleanup. Run them from the repository root after reviewing
the [result register](../results/README.md).

The intended repair target is a **strict MLP + original Method B inverse**.
The runnable commands below provide its controls and component diagnostics.
They do not establish that this repaired pipeline exists or succeeds.
The current alternating-MLP driver makes radial Fourier coefficients the
authoritative shape state; its strict neural policy does not change that
geometry choice.

## Choose evidence to refresh

| Priority | Run | Question it answers |
|---|---|---|
| First | Focused regressions | Do the existing geometry, inverse, neural-policy, and derivative contracts still hold? |
| First | Method B parameter inverse controls | Does extraction through Method B still recover the small known parameter families? |
| First | Frozen Method B and parameter-aware studies | Which errors belong to the fitted geometry, parameter labels, or BEM resolution? |
| When changing neural acceptance/fitting | Radial representation-policy comparison | What does strict fitting cost or reject for the existing radial shape state? |
| When changing derivatives | Kress derivative audit | Are discrete geometry/material derivatives and independent refinement still consistent? |
| Optional | Shape/material controls | Do the separate radial K2 material experiments retain their measured behavior? |
| After implementation | Strict MLP + Method B recovery | Does the intended repaired inverse work? No runnable command is available yet. |

A folder move or a clearer label does not require a numerical rerun.
Keep historical failed runs as evidence. Rerun a failed case only when a
specific implementation change or controlled comparison can explain a new
outcome. Do not rerun every archived September 3–4 MLP variant.

## Shared shell setup

Use one Bash session for the setup and commands below. Each command writes
to a new directory. Refresh `REPRO_STAMP` before repeating the same command;
none of these commands requests overwrite.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
REPRO_STAMP=$(date -u +%Y%m%dT%H%M%S%NZ)
REPRO_PY=(env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python)
```

These are new runs against the current working tree. Original commands,
commit identities, dirty-tree records, and measurements remain in the saved
bundles. A current run is not a claim of byte-for-byte historical replay.

## Focused existing regressions

This covers the Method B frontend, parameter-family inverse controls,
current neural fitting/acceptance contracts, direct curve updates,
representation policies, parameter-aware driver, and Kress derivative seam.
Passing these tests does not validate the pending strict Method B repair.

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

## Method B parameter inverse controls

These optimize a small implicit-field parameter vector using finite
differences. Each candidate is extracted and fit through Method B before
the paired MOD/Kress prediction. They are useful controls for the repaired
pipeline, but do not optimize a general MLP.

The first two commands use independent analytic Mie circle observations,
starting from a wrong circle and a non-distance ellipse. The third uses
independent Nyström observations of a five-lobe star and a wrong star
initialization. Frequencies, geometry resolutions, material definitions,
and acquisition coordinates are recorded by the driver.

```bash
"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target circle --initial-model circle --solvers mod kress \
  --output-dir "results/inverse/method_b/circle-to-circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target circle --initial-model ellipse --solvers mod kress \
  --max-iterations 8 \
  --output-dir "results/inverse/method_b/ellipse-to-circle-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_sdf_inverse_comparison.py \
  --target star --initial-model star --solvers mod kress \
  --output-dir "results/inverse/method_b/star-to-star-${REPRO_STAMP}"
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

## Radial representation-policy diagnostics

These compare `legacy_strict`, `curve_only`, and `export_only` on the
current radial Fourier state. `legacy_strict` is the existing policy name;
it means strict coupling to neural representation acceptance **within this
radial experiment**, not original Method B geometry updates.

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
extracted-curve drift, and held-out fields. A strict initialization failure
is an informative result, not evidence that the inverse ran successfully.

## Kress derivative validation

This checks the complete discrete geometry/material derivative, paired
objective adjoint, independent references, and physical refinement. Its
geometry inputs are explicit curves. It does not differentiate through MLP
training, contour extraction, or a Method B refit.

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

## Optional radial shape/material controls

These retain their separate scope: fixed-circle or radial K2 shape with
one unknown interior permittivity. They are not strict MLP + Method B
recovery experiments.

```bash
"${REPRO_PY[@]}" -m pytest -q \
  pytest/sdf_inverse/test_material_inverse.py \
  pytest/sdf_inverse/test_robust_material_inverse.py \
  pytest/solver_comparisons/test_material_inverse_driver.py \
  pytest/solver_comparisons/test_material_robustness_driver.py

"${REPRO_PY[@]}" run_material_inverse_comparison.py \
  --nodes 64 --audit-nodes 64 128 256 --max-evaluations 40 \
  --output "results/inverse/shape_material/material_inverse/bounded-${REPRO_STAMP}"

"${REPRO_PY[@]}" run_material_robustness_comparison.py \
  --frozen-d results/inverse/shape_material/material_inverse/bounded-20260906 \
  --nodes 64 --audit-nodes 64 128 256 --oracle-nodes 128 256 512 1024 \
  --stage-max-evaluations 40 40 \
  --maximum-forward-solves 400 --maximum-direction-evaluations 2400 \
  --output "results/inverse/shape_material/material_robustness/bounded-${REPRO_STAMP}"
```

The robustness command deliberately reads the original frozen material
dataset, not the new material run above. Its required `arrays.npz` is a
local ignored artifact; preserve it with the bundle. If it is unavailable
in another checkout, exact frozen-data replay is unavailable there until
that artifact is restored. Do not silently substitute newly generated
observations under the old run identity.

## Strict MLP + Method B repair: commands pending

There is currently no driver flag that makes
`run_mlp_sdf_inverse_comparison.py` use original Method B as the evolving
authoritative geometry. Selecting strict distillation, changing modal
continuation, or increasing fitting budgets leaves its radial state in
place. Do not label those runs as the repaired pipeline.

Before supplying a runnable repair experiment, implement and expose the
intended state transition explicitly, including which MLP/curve state is
accepted, how Method B is reconstructed, and which geometry reaches BEM.
Add tests for that transition and for failure/rollback behavior. The
physical qualification should then proceed through:

1. Circle recovery, followed by ellipse-to-circle and ellipse-to-star
   recovery, using fixed observations and recorded initialization.
2. Separate extraction/fitting and BEM-resolution studies on frozen accepted
   states, so a geometry error cannot be hidden by changing quadrature.
3. Separate reconstruction success, strict neural representation acceptance,
   re-extracted boundary/field agreement, and held-out data checks.
4. A controlled comparison with retained radial results using matching data,
   initialization conventions, resolution, and work accounting. Report
   differences in shape space and initialization projection explicitly.

The existing non-star-shaped frozen fitting case is useful for Method B's
geometric scope. It is not yet evidence of non-star-shaped neural inverse
recovery. Add such an inverse case only with an explicit supported target,
observation source, and acceptance protocol.
