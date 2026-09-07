# Implicit MLP + Method B: component diagnostics

Updated 2026-09-07. **The full diagnostic studies have not been run.** Their
contract tests were included in the recorded
[367-test validation](../results/validation/implicit_mlp_adjoint/validation.json);
those tests do not establish numerical conclusions for these studies.
The [driver](../run_method_b_failure_diagnostics.py) supplies three controlled
conversion and fitting experiments. The production
[Implicit MLP + Method B](pipelines/implicit_mlp.md) adjoint inverse is already
implemented; its current recovery remains FAIL / unresolved. This diagnostic
driver does not run that inverse or change its defaults.

The existing [failure evidence](pipelines/implicit_mlp.md#recorded-evidence-and-its-limits)
does not establish that Eikonal training caused the failure. Smooth-distance
supervision improved the frozen star interface, but its remaining error was
measured after both neural fitting and Method B. These experiments separate
those stages. The one-step transfer control deliberately proposes an explicit
curve using finite differences and fits an MLP to it. That is a legacy
fitting/transfer diagnostic, not the production adjoint's direct weight update.
It has no radial chart and is also separate from
[Legacy known-shape-family controls](../results/legacy/known_shape_family_parameter_inverse).

## Experiments and decisions

| Diagnostic | Held fixed | Varied | Readout and next decision |
|---|---|---|---|
| Conversion | Saved MLP weights, acquisition/materials, fixed BEM resolution sequence | Extraction grid, projected samples, Cartesian bandwidth, arc-length integration resolution; one factor at a time | If the independently resolved zero set is accurate but Method B is not, repair the conversion. Inspect the initial fit and arc-length refit separately. |
| Eikonal fitting | Smooth target, architecture, seed, sample locations/targets, warm-up weights **and Adam moments**, equal update counts | Eikonal weights `0`, `0.01`, `0.1` | Compare warm-up, first branch update, and final interfaces/fields. Systematically worse interfaces after activation implicate this fitting penalty/schedule in this controlled setting; it does not isolate the production inverse's regularizer. |
| Legacy one-step transfer/fitting | Saved starting MLP, empty Adam state shared across copies, materials, observations, frequency set, fitting schedule | One fixed local descent direction at `0.05`, `0.2`, `0.8 mm`, plus an exact zero-update target | Compare predicted, direct-curve and re-extracted objectives and measure fitting drift against the intended step. This tests transfer through fitting, not an adjoint neural update. |

The default scenes are the existing frozen 65 mm circle and five-lobe star
(`amplitude=0.2`, rotation `0.15`). Conversion and transfer load their saved
smooth-target MLPs. The optional polygon-trained conversion arm identifies
whether a conversion finding depends on the earlier fitting policy. The
Eikonal study instead reconstructs the original seeded initialization and
trains a **new shared Eikonal-free warm-up**; the saved final weights are not
a warm-up checkpoint. Its default budget is 50 shared updates followed by
550 updates per weight.

The source bundle is
[`task-b-circle-star-refined-20260905`](../results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md).
Both `summary.json` and local `arrays.npz` are required. Missing arrays stop
the driver; it does not silently substitute newly fitted models. Inputs and
source files are hashed in each new run. The acquisition is the bundle's six
paired transmitter/receiver positions at 0.6 and 0.9 GHz, with fixed exterior
relative permittivity 6 and interior 3. These are component diagnostics with
synthetic refined Kress observations, not independent-data inverse recovery
or a held-out reconstruction benchmark.

## Commands

Run from the repository root in Bash. No diagnostic measurement command below
was executed while preparing this study. Each output directory must be new.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
DIAG_STAMP=$(date -u +%Y%m%dT%H%M%S%NZ)
DIAG_PY=(env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python)

"${DIAG_PY[@]}" -m pytest -q pytest/sdf_inverse/test_method_b_failure_diagnostics.py
```

**First: conversion, with both saved fitting policies.** No MLP training.

```bash
"${DIAG_PY[@]}" run_method_b_failure_diagnostics.py \
  --experiments conversion --shapes circle star \
  --frozen-policies legacy_polygon smooth_curve \
  --output-dir "results/validation/method_b_failure_diagnostics/conversion-${DIAG_STAMP}"
```

**Second: controlled Eikonal activation.** Read conversion first; unresolved
geometry must not become an Eikonal conclusion. This saves the shared Adam
checkpoint, every arm's first update, and every final state.

```bash
"${DIAG_PY[@]}" run_method_b_failure_diagnostics.py \
  --experiments eikonal --shapes circle star \
  --output-dir "results/validation/method_b_failure_diagnostics/eikonal-${DIAG_STAMP}"
```

**Third: legacy one-step transfer and the zero-update fitting control.** This
uses the frozen smooth MLPs and the declared `0.1` Eikonal weight. It does not automatically select
whichever Eikonal arm looks best. A follow-up setting needs a separately
identified run and the same zero-update control.

```bash
"${DIAG_PY[@]}" run_method_b_failure_diagnostics.py \
  --experiments transfer --shapes circle star \
  --output-dir "results/validation/method_b_failure_diagnostics/transfer-${DIAG_STAMP}"
```

These are bounded diagnostics, not long inverse runs, but repeated geometry
audits and BEM refinement can dominate fitting cost. No runtime estimate has
been measured for this new driver. Use `--shapes circle` for a first complete
scene. Do not reduce refinement to obtain a passing result.

If the numerical reference remains unresolved, repeat the relevant command
with **the same MLP/training settings** and a new output name. Select the
resolution that failed: for example `--grids 257 513 1025` refines extraction;
`--projected-samples 512 1024 2048` refines the independent spline; and
`--bem-nodes 256 512 1024` refines BEM. Keep unrelated settings fixed and
record the reason for the rerun. A bandwidth change must leave every BEM
node count and projected-sample count capable of resolving the largest
bandwidth; invalid configurations are rejected by the parser.

## Measurement contracts and limitations

**Conversion.** The default common anchor is grid `513²`, 1024 projected
points, Cartesian bandwidth 96, and 4096 arc-length integration samples.
Sweeps use grids 257/513, projected samples 512/1024, bandwidths 24/48/96,
and arc-length integration 2048/4096. Arc-length refit samples stay fixed at
the maximum projected count. All curves use the same BEM sequence 256/512;
increasing bandwidth never silently changes quadrature.

An independent periodic cubic spline interpolates the projected zero-set
points. Grid and projected-sample refinement are checked separately for this
reference; it does not pass through Cartesian Fourier fitting. Geometry uses
two directed closest-curve distances and 512/1024 outer samples. The driver
checks gradient magnitude, outward-normal alignment, speed, field residual
divided by gradient magnitude, sampled topology, and coherent derivatives.
Reference geometry must agree within `2e-6 m`; field refinements must agree
within `1e-7` relative error. A spline interpolation and sampled/refined
agreement are numerical evidence, not a global zero-set certificate.

Read `raw_reference.raw_zero_set_to_target` as the independently measured
neural-interface error. Read each conversion's `to_raw_zero_set` and
`initial_to_arclength` as conversion/refit errors. They are set distances,
not additive error terms. `field_error_to_target` is recorded for the raw
reference and both Fourier stages; `field_error_to_raw` measures the physical
effect of conversion. Always inspect the associated refinement flags.

**Fitting.** The isolated
[helper](../solvers/sdf_inverse/method_b_diagnostics.py) uses the redistance
objective also used for radial-pipeline MLP fitting, with historical polygon
boundary/offset sample locations,
with their actual smooth-curve distance targets. Global samples, targets and
Adam state are shared within each Eikonal comparison. Distance, boundary,
offset, box and Eikonal loss components are reported independently.

The diagnostic trainer intentionally retains the last state after an exact
update budget. The ordinary redistance fitter additionally uses no-op stopping,
early stopping and best-full-objective state selection. Those mechanisms
would confound this fixed-budget comparison and are not replicated. Thus a
result implicates the controlled penalty/training trajectory; it is not an
exact replay of every production stopping decision. The first-update audit
does not take optimizer steps or alter Adam state.

Held-out distance RMS (`1e-5 m`), sampled boundary-target residual (`1e-7 m`),
and training Eikonal RMS (`0.2`) remain separate gates, including for the
zero-weight arm. The extracted-interface gate is separately `0.2 mm`.
Passing one gate cannot hide failure of another.

**Legacy transfer/fitting control.** Central finite differences at 20 and 10 micrometres estimate a
local data gradient in seven normal modes (constant and phase sine/cosine
modes 1–3). Every proposal is a Cartesian Fourier curve with coherent jets;
there is no radial chart. Gradient agreement is required within 5%, alongside
the forward-resolution checks. The fixed direction is normalized to roughly
unit maximum requested normal motion before applying the three scales.
Record requested motion, realized proposal motion and refit distortion.

The objective is `0.5 * ||predicted-observed||² / ||observed||²`, using the
fixed frequency set. Non-descending direct proposals are retained as skipped
rows, not fitted or counted as a transfer test. No direct descent at any
configured scale leaves the transfer study blocked; inspect the direction,
finite-difference checks and scales before extending it.

For every eligible proposal, copy the same frozen MLP and empty Adam state,
fit it, rebuild Method B and solve again. The zero-update arm targets the
exact starting Method-B curve. Its fitting work and schedule match every
nonzero arm. Motion comparisons use symmetric set distances and signed
distances from fixed starting points, avoiding false displacement caused by
arc-length phase changes. The signed-distance motion samples are local
displacement proxies, not exact point correspondences.

`transfer_descent_observed` requires resolved references and improvement of
both the direct and actual re-extracted data objectives. It **does not mean
production inverse acceptance**: inspect fitting gates, conversion drift,
motion discrepancy and no-op drift separately. The retained output key
`strict_inverse_acceptance_evaluated` is always false. The data-gradient estimate
differentiates the explicit curve proposal only; it is not an MLP-weight
gradient or a derivative through extraction. The production adjoint instead
differentiates the actual weight → extraction → Method-B → Kress objective
and updates the weights without fitting a perturbed curve.

## Reading and registering a run

Each run writes a `README.md`, `metrics.json`, per-arm JSON audits, numeric
NPZ geometry/data artifacts, and model/Adam `.pt` checkpoints. Load checkpoints
with `torch.load(path, weights_only=True)`; they contain tensor state and basic
containers. Architecture metadata is in their JSON references.

The top-level record includes UTC start/finish times, scene, fitting policy,
exact CLI settings, input/source hashes, revision, dirty-tree status, elapsed
time and actual BEM/frontend/Method-B attempt counts. Successful fits include
actual update counts and complete pre-update loss histories. A failed fit
does not imply that the full requested budget completed. Numerical failures
retain their error and traceback; available intermediate curves and stages
are saved before later validation. Existing bundles are never overwritten.

`completed` means measurement execution completed. It is not a scientific
pass; read `resolved`, individual gates and failures. The driver returns
nonzero for failed/blocked cases and does not automatically add unreviewed
measurements to the historical [result register](../results/README.md).
After review, add the run date, scene, actual pipeline, resolved/failed gates,
and a supported takeaway there and in `results/catalog.csv`. These planned
experiments have no fabricated result rows or conclusions.
