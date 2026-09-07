# Current architecture and research direction

Reconciled 2026-09-07. This page distinguishes implemented paths from the
agreed repair target; it does not claim that repair is already implemented.

## Research direction

**Fix strict MLP + Method B for single-object inversion.** The neural implicit
field should own reconstructed geometry, with a faithful, validated Method-B
boundary supplied to the physical solver. Method B is an active development
target, not merely a comparison to keep beside radial Fourier.

Radial runs isolate reconstruction, continuation, fitting, and representation
errors. Their findings inform the strict pipeline's next steps. Success on an
authoritative radial curve does not establish recovery through an MLP-owned,
re-extracted Method-B boundary. The [strict pipeline document](pipelines/strict_mlp_method_b.md)
owns the repair plan and acceptance requirements.

## Implemented paths

| Path | Geometry authority and update | Forward / derivative | Present role |
|---|---|---|---|
| Implicit-parameter inverse | Implicit-model parameters; extraction and Method B at every evaluation | MOD or Kress; parameter finite differences | Working small-parameter controls; tiny SIREN FD evidence is negative |
| Radial shape inverse | Explicit radial Fourier state; MLP fits/audits it | MOD or Kress; radial finite differences | Reconstruction and representation diagnostics |
| Shape/material inverse | Explicit radial K2 state and one interior permittivity | Kress analytic directional derivatives | Bounded material, continuation, and restart experiments |
| Frozen neural metric | Explicit radial state with initial neural-feature metric | Kress objective adjoint | Update-metric diagnostic; no training during inversion |
| Older neural B-scan inverse | Neural field; compressed implicit boundary cloud | MOD adjoint shape surrogate | Separate older implementation, without Method B |
| Multi-component extraction/forward | Extracted ordered loops | Multi-component Kress forward | Prescribed split demonstration, not a topology-changing inverse |

See [strict MLP / Method B](pipelines/strict_mlp_method_b.md),
[radial shape and MLP policies](pipelines/radial_fourier.md), and
[shape/material experiments](pipelines/shape_material.md) for exact ownership,
drivers, limitations, and implications for the repair.

The original MLP comparison CLI selects radial retraction and strict per-step
fitting. `legacy_strict` names a representation policy; it does not restore
historical MLP-owned geometry. The library's normal-update default and the CLI's
radial override are distinct. Curve-only and final-export policies are
exercised by the separate representation-ablation driver.

## Physics, geometry, and solvers

The physical model is homogeneous full-space 2-D TMz dielectric transmission
with free-space Hankel kernels. Current ordered inverse evidence uses one
regular closed component. Radial geometry additionally requires a star-shaped
object. There is no implemented air/ground interface, 3-D inverse, object-count
recovery, or per-component unknown-material inverse.

`ordered_boundary` owns smooth continuous producers and immutable even-node
curve data. Method B fits Cartesian coordinate Fourier series to an extracted,
projected contour and redistributes arc length. Radial Fourier represents
radius as a function of angle; these are different geometry paths.

| Package | Role |
|---|---|
| `gpr_bem_ref` | Frozen original; selector default |
| `gpr_bem_mod` | Compressed-cloud implementation, older neural adjoint, and ordered inverse comparison peer |
| `gpr_bem_kress` | Ordered Müller/Kress forward, multi-component forward extension, and opt-in single-interface discrete derivatives |
| `nystrom_ref` / cylinder Mie series | Independent observation and refinement controls |
| `sdf_to_ordered_boundary` | Extraction/projection, Methods A/B/C, and opt-in conversion studies |
| `sdf_inverse` | Implicit-parameter, curve, representation, metric, and material experiments |

Kress is directly imported, not a `solver_select` alias. For selector-backed
commands, `--solver` overrides `SOLVER`; if both are absent, REF is selected.
Use `--solver=mod` explicitly for MOD. The verified Kress
derivative handles coherent fixed-grid curve/material directions. It does not
automatically differentiate extraction, topology, or a future MLP-owned update.

## Evidence and reproduction

[Results](../results/README.md) classify runs by geometry ownership, solver,
MLP role, scene, recorded date, outcome, and implication for strict MLP + Method B.
Reconstruction, SDF delivery, physical recovery, optimizer stopping, and
forward validation remain separate claims. Failed arms stay with their comparison.

[Reproduction commands](reproduction.md) distinguish runnable diagnostics from
the pending repair. The 2026-09-07 cleanup ran no tests or numerical experiments
and changed no optimizer or physical model. Driver edits only relocate
artifact inputs and default outputs.

Earlier implementation details and recommendations remain in
[dated reports](reports/README.md); mathematics and numerical protocols remain
in [technical references](reference/README.md). Dated plans cannot override
this page or the strict-pipeline repair objective.
