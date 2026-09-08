# Implicit MLP failure causes — 2026-09-07

This audit identifies **a premature circle line-search stop, avoidable star
pretraining bias, and measurable Method-B contour distortion**. It reloads
the three `20260907T151516` inverse checkpoints and runs a matched star
exact-target pretraining comparison. Production code and historical results
are unchanged. These are diagnostic measurements, not successful inverse
reconstructions or replacements for the existing recovery gates.

**1. Confirmed: the circle stops because the line search is too short.**

The final checkpoint reproduces its saved training loss exactly:
`2.6177094827112525e-6`. The production steepest-descent fallback is
normalized to a maximum weight displacement of `1e-3`, independently of
gradient magnitude. The CLI permits only eight halvings, even though the
optimizer dataclass defaults to twelve.

| Fallback trial | Maximum weight displacement | Actual data loss | Data Armijo | Regularized Armijo | Boundary-step gate |
|---|---:|---:|---|---|---|
| Eight halvings: last permitted trial | 3.90625e-6 | 2.68628e-6 | FAIL | PASS | PASS |
| Nine halvings: first additional trial | 1.953125e-6 | 2.46523e-6 | PASS | PASS | PASS |

One extra halving lowers data loss by **5.83%**, lowers the regularized
objective, and moves the sampled curve by only **0.0201 mm**. This is the
existing production direction with the existing acceptance conditions.
It requires no new optimizer or relaxed gate. The total gradient norm is
`0.03449`, and its negative direction is a data-descent direction. Thus this
stop does not establish stationarity or an unavoidable conflict with the
inverse Eikonal penalty. The original Adam moments were not saved; replay of
them is unnecessary for testing the deterministic fallback.

The concrete failure mechanism is the fixed normalized proposal combined
with a finite minimum trial size. A longer/adaptive search or a shrinking
proposal can address this stop. One successful additional step does not
establish eventual recovery.

Code: [CLI backtracking limit](../../../../run_sdf_inverse_comparison.py#L616),
[proposal and acceptance](../../../../solvers/sdf_inverse/implicit_adjoint.py#L343).
Measurements: [metrics.json](metrics.json), circle `direction_probes`.

**2. Confirmed in the tested seed: the star pretraining objective causes a
large, avoidable shape bias.**

Both arms use the production 64-wide, two-hidden-layer SIREN, seed 0,
identical random sample sequence, Adam and cosine schedule, and 6,000
updates. Only the pretraining Eikonal weight changes. The `0.1` arm exactly
reproduces the recorded known-target control's Method-B boundary error.

| Known-target star fitting | Eikonal weight 0.1 | Eikonal weight 0 |
|---|---:|---:|
| Maximum native Method-B node-to-target error | 9.18152 mm | 1.15088 mm |
| Maximum raw projected zero-set node-to-target error, 513 grid / 1,024 samples | 9.56116 mm | 1.20021 mm |
| Independent probe-set RMS error to the supervision function | 5.24481 mm | 0.579484 mm |
| Training Eikonal mean-square residual, final reported batch | 1.26028e-4 | 6.42351e-2 |

The boundary error decreases about **eightfold**, before any inverse solve.
This rules out interpreting the recorded 9.18 mm control as an intrinsic
capacity limit of this network. It is an outcome of this fitting procedure.
The zero-weight arm remains imperfect and has worse distance-gradient quality.

The mechanism is supported by the actual supervision function:
`F / ||grad F||` approximates distance locally near the interface but is not
a global signed distance for the star. Nevertheless, the loss combines
regression to that function over uniform whole-box samples with a whole-box
unit-gradient penalty and has no separate interface-fitting term. Finite
differences of the supervision function at two steps agree on a global
Eikonal RMS of about `1.09117`, versus `0.03684` within its 2 mm proxy band.
The global statistic uses 10,000 seeded probes with the central 5 mm removed;
it is sensitive to large gradients away from the boundary. The two objectives
are not globally compatible, and this matched comparison shows their
practical effect on the learned interface.

Pretraining uses a **fixed weight of 0.1** in `_build_siren_field`.
`--eikonal-weight` controls the separate inverse penalty, normally `0.01`;
changing that CLI flag does not alter this pretraining problem. This study
changes the penalty from initialization, not after a shared warm-up. It
does not isolate the inverse penalty or demonstrate that removing it repairs
inverse recovery. True distance supervision, interface terms, and a better
scaled/localized penalty remain candidate repairs requiring their own tests.

Code: [pretraining wiring](../../../../run_sdf_inverse_comparison.py#L774),
[training loss](../../../../solvers/sdf_inverse/models.py#L1249),
[supervision function](../../../../solvers/sdf_inverse/models.py#L1279).
Measurements and checkpoints: [pretraining.json](pretraining.json).

**3. Confirmed: Method B changes the neural contour, especially for the
ellipse-initialized circle.**

Frozen models were independently extracted at grid 513 and sampled at
1,024/2,048 points. Production Method-B settings were held fixed; only its
output sampling density changed for the comparison below.

| Final checkpoint | Raw contour-to-target maximum, 2,048 samples | Converted contour-to-target maximum, 2,048 samples | Raw/converted symmetric vertex-to-polygon distance |
|---|---:|---:|---:|
| Circle → circle | 1.07245 mm | 1.05163 mm | 0.266825 mm |
| Ellipse → circle | 8.25455 mm | 6.46147 mm | 1.82141 mm |
| Star → star | 26.9002 mm | 26.8835 mm | 0.177587 mm |

The raw/converted set-distance statistic changes by approximately 0.11,
0.20, and 1.27 micrometres, respectively, when doubling sample density.
The ellipse's converted boundary understates the error present in its raw
neural contour even when both are densely sampled. The forward objective
is evaluated on the converted contour, so accepting a lower forward loss
does not ensure fidelity to the raw zero set.

These are sampled target distances and polygonal set distances, not
certified continuous Hausdorff distances. The separate grid/sample probes
in `metrics.json` are not a complete conversion refinement study. The
measurements nevertheless show that the large star error already exists
before Method B; conversion is not its dominant source. A conversion
fidelity gate and independent refinement would address a separate limitation.

Measurements: [conversion.json](conversion.json), [metrics.json](metrics.json).

**4. Recovery remains limited by the training objective and unfinished
optimization; the precise conditioning/identifiability contribution is not
isolated.**

| Recorded inverse | Final training relative L2 | Final holdout relative L2 | Termination |
|---|---:|---:|---|
| Circle → circle | 0.001690 | 0.063944 | Premature line-search stop demonstrated above |
| Ellipse → circle | 0.008951 | 0.318638 | 60-update budget exhausted |
| Star → star | 0.245624 | 0.783925 | 60-update budget exhausted |

The circle fits the center and mean radius well but retains contour errors.
The ellipse and star still reduce loss in their last iterations. Recomputed
final data-gradient norms are `0.3572` and `4.6354`, respectively; the budget
stops do not show stationarity.

Each run updates 8,577 weights from 24 complex training measurements. Many
weight directions must be unobserved to first order, although some represent
field changes that do not move the contour. The circle training frequencies
are only 0.25/0.5 GHz. Sparse measurements, weakly constrained contour modes,
and nonlinear optimization are credible remaining contributors to the
train/holdout gap. No Jacobian spectrum, matched acquisition ablation, or
multi-start study was run, so these are not separately proven root causes.

**The present evidence does not implicate BEM accuracy as the dominant
failure.** Keeping the MLP and Method-B conversion fixed, circle training
predictions change by about `3e-15` when increasing nodes 64 → 128 → 256.
The ellipse changes by `9.08e-13` then `2.85e-15`. Star predictions change
by `5.71e-6` at 128 → 256 and `3.60e-10` at 256 → 512; its training loss
remains approximately `0.0624061`. The archived gradient validation also
passes on tested smooth branches. This audit reproduces saved losses but
does not rerun the full historical test suite or certify every derivative
branch. It does not test topology changes or legacy curve-to-MLP transfer.

The repair order supported by these measurements is: remove the demonstrated
minimum-step limitation; repair and separately qualify star pretraining;
control conversion fidelity; then test optimization and acquisition with
matched settings and independent holdout checks. No full inverse was rerun
with those repairs in this audit.

Reproduction, from the repository root, using a **new** output directory:

```bash
AUDIT_PY=(env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python)
AUDIT_SOURCE=results/validation/implicit_mlp_adjoint/failure-audit-20260907
AUDIT_OUT=/tmp/implicit-mlp-failure-audit-new
"${AUDIT_PY[@]}" "$AUDIT_SOURCE/implicit_mlp_failure_audit.py" "$AUDIT_OUT"
"${AUDIT_PY[@]}" "$AUDIT_SOURCE/implicit_mlp_pretraining_audit.py" "$AUDIT_OUT"
"${AUDIT_PY[@]}" "$AUDIT_SOURCE/implicit_mlp_conversion_audit.py" "$AUDIT_OUT"
```

The first script requires a new directory; the other scripts add their
measurements there. Input checkpoints and response NPZ files must exist
locally. [provenance.json](provenance.json) records input/source hashes,
revision, audit-script hashes and a corrected diagnostic setup error from
an earlier unsuccessful attempt. The optional output-directory argument
was added after measurement and does not change numerical settings. The
audited bundles have since moved to `results/inverse/implicit_mlp/<date>/<case>`;
provenance.json points at the new paths and every recorded input hash still
verifies. The frozen scripts are unchanged, so their `*/metrics.json` glob
predates that date level and needs `*/*/metrics.json` to rerun. Binary
artifacts follow the repository's existing ignore rules. These audits are
separate from the broader planned studies in `docs/implicit_mlp_diagnostics.md`.
