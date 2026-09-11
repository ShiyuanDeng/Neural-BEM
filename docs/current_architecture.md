# Current architecture and research direction

Updated 2026-09-11 against [baseline B0](baselines/B0_2026-09-10.md) — commit
**`345038a`** (recorded against `e34ed5f` plus an uncommitted working tree,
committed 2026-09-11). Statements below were checked
against the source at that state, with the TOP-001 extensions below added on
2026-09-11. Where a claim rests on a recorded run rather than on the code, it says so.

The three current inverse pipelines are **Implicit MLP + Method B**, **Explicit
Cartesian Fourier** and **Explicit Radial Fourier**. They differ in which
representation owns the accepted geometry and receives the physics update. The
current research agenda is organised by question rather than by pipeline; see
the [dashboard](README.md).

## Who owns the accepted geometry

| Pipeline | Geometry authority and update | Forward / derivative | Measured status |
|---|---|---|---|
| [Implicit MLP + Method B](pipelines/implicit_mlp.md) | Neural weights; the candidate network's extracted Method-B boundary determines acceptance | Kress discrete adjoint through branch-local extraction/conversion reverse; Adam/backtracking | Gradient validated; all three current 12-pair recovery runs fail overall acceptance |
| [Explicit Radial Fourier](pipelines/explicit_radial_fourier.md) | Radial Fourier coefficients; an MLP fits/audits the accepted curve | MOD or Kress; radial finite differences in the main driver | Canonical curve recovery succeeds on recorded cases; the extracted MLP can still fail representation gates |
| [Explicit Cartesian Fourier](pipelines/explicit_cartesian_fourier.md) | Cartesian Fourier coefficients; no neural field | Kress with finite differences; full coefficient space in the single-component study, gauge-preserving subspace in the topology optimizer | Single-component ellipse-to-star recovery; five automatic topology cases and three challenge cases recorded in each chart |

Both explicit pipelines share one multi-component state object,
`MultiRadialFourierState`, which holds radial **or** Cartesian Fourier
components with persistent IDs and deterministic parameter slices. The chart is
a per-component property, not a separate pipeline.

`run_implicit_mlp_inverse.py` selects Implicit MLP + Method B. Its September 7
circle, ellipse-to-circle and star experiments remain **FAIL / unresolved**.
Correct gradients and accepted data decrease do not establish physical recovery.
Method B remains the neural pipeline's conversion method. This pipeline's
research cycle is **paused by user direction (2026-09-11)** — diagnosing the MLP
is not the current priority — but it is not closed, and the implementation stays
in the tree.

`run_explicit_radial_fourier_inverse.py` selects Explicit Radial Fourier;
`run_mlp_sdf_inverse_comparison.py` remains its compatibility name. The CLI uses
radial retraction and the `legacy_strict` per-step neural fitting policy.
Changing that policy does not change who owns the geometry. The library's
normal-update default and the CLI's radial override remain distinct.

No matched three-way recovery benchmark has been completed.

## Forward solve and derivative paths

The forward is the ordered periodic Kress/Nyström **Müller** solver in
`gpr_bem_kress`: a `PeriodicCurve2D` feeds cancellation-safe ΔV/K/K′/T assembly,
a direct unsquared Müller solve of a dense `2N × 2N` system with two nodal
densities per node, and an explicit exterior receiver operator `C = [D, −S]`.
Topology runs use `N = 64` production and `N = 128` refined nodes per component.
The boundary unknown is **nodal**; there is no modal trace representation.

A condition number is available but off by default, and the code records that it
is `raw_mixed_unit_nodal_2_norm` and not scale-invariant.

Three derivative paths exist and are distinct:

| Path | Used by | Mechanism |
|---|---|---|
| Analytic discrete Kress shape derivative, **single interface** | material inverses; the implicit-MLP geometry pullback | `gpr_bem_kress/shape_derivative.py`, differentiating the actual kernel branches, diagonals, normals, weights, incident traces and receiver map |
| Central finite differences, multi-component | the explicit topology optimizer `run_multiradial_fd_inverse` | Levenberg damping, strict decrease, backtracking, geometry rejection, exact rollback |
| Central finite differences, single-component full chart | `run_explicit_cartesian_fourier_inverse.py` | full `4K + 2` coefficient columns with the phase direction projected out |

The explicit multi-component path **does not** use the analytic derivative:
neither `radial_topology.py` nor `topology_controller.py` imports it.

The verified Kress derivative handles coherent fixed-grid curve/material
directions. The geometry reverse and branch-local Method-B reverse connect it to
neural weights. Discrete connectivity and branch switches are not
differentiated.

Kress is directly imported, not a `solver_select` alias. For selector-backed
commands, `--solver` overrides `SOLVER`; if both are absent, REF is selected.
Use `--solver=mod` explicitly for MOD.

## Topology controller

`solvers/sdf_inverse/topology_controller.py` implements automatic topology
change for the explicit pipelines, in either chart. It receives data and initial
geometry only: **no target component count and no supplied event policy** (the
per-case manifests record `supplied_target_count: false`,
`supplied_event_policy: false`).

| Stage | What it does at B0 |
|---|---|
| Trigger | A topology pass follows every inner fixed-topology solve. The recorded `trigger` is the inner optimizer's stop reason, plus the structural cases `empty_domain` and `component_radius_floor`. It is a label, not a measured stagnation criterion |
| Candidate construction | Births from exterior topological-derivative regions with an equivalent-radius ladder; splits from interior TD corridors parameterised by width, angle, offset and contour modes; deaths by removing components; merges by refitting one outer contour. Family-diversified, capped at `maximum_candidates_per_type` |
| Candidate refinement | **Only the best raw-scoring candidate per (event kind, resulting component count) group** receives `candidate_refinement_iterations` LM steps; all others are compared at their raw loss |
| Acceptance | Production-objective decrease beyond an absolute+relative margin, which must survive at the refined resolution within `cross_resolution_factor`; lowest production loss among survivors wins. Geometry validity is checked first |
| Stopping | `recovered` at `relative_error_tolerance`, else `maximum_events`, `maximum_cycles` or `topology_stationary` |

Candidate rejection reasons are recorded per trial and fall into distinguishable
classes: representation restrictions (gauge-fix refusal, feature-radius floor,
unsupported nested holes), numerical-resolution failures (cross-component
quadrature clearance, cross-resolution margin), geometric inadmissibility
(intersecting or touching components), and poor objective values.

TOP-001 adds optional `candidates_refined_per_group` (default **1**) and
`replay_first_event` controls. Replay bypasses the first fixed-topology solve
on an already gauge-valid pre-event state; subsequent cycles are unchanged.
Allocation ranks by the original raw scores and refines the requested number
per group. Candidate construction, objective, optimizer and acceptance remain B0.

The controller now records per-pass and total uncached objective-call counts,
completed paired predictions, and objective/TD frequency-solve counts by stage.
Final audits are separate. Empty-domain evaluations and optimizer cache hits
require no BIE solve. `evaluation_count` includes objective calls with invalid
boundaries, but not trials rejected by the optimizer before calling the objective.
Completed-forward counts exclude failed predictions; a prediction that fails
after some frequency solves is not a completed prediction. The TOP-001 runs
must audit such failures before interpreting completed counts as all work.
Per-candidate optimizer attempt/infeasibility counts are also retained. These
counters are passive and scoped to each controller invocation. The shared CLI
records source hashes and exposes both allocation controls. See the
[TOP-001 plan](iterations/topology/iteration_01/03_plan.md).

## Representation and physical-model restrictions

The physical model is homogeneous full-space 2-D TMz dielectric transmission
with free-space Hankel kernels. The topology demonstrations are noiseless,
same-material, and use a 24-position paired ring acquisition at 0.5 GHz for
topology decisions.

- **Radial chart:** each component's radius is a function of its polar angle, so
  each component must be star-shaped about its own centre.
- **Cartesian chart under the topology gauge:** each component must be
  gauge-fixed in its own polar angle. That gauge-fixed set is a **linear
  subspace** of dimension `3` for `K ≤ 2` and `2K − 1` above, against `4K + 2`
  coefficients — exactly the radial chart one band lower. A contour fit that
  cannot be gauge-fixed is refused outright.
- **This is a restriction of the current policy, not of Cartesian Fourier
  curves.** The un-gauged chart is implemented; it was measured and rejected on
  optimisation grounds — parameter drift along data-invisible directions,
  degraded quadrature, stalled shape progress — not on expressiveness grounds.
  See [B0 §7](baselines/B0_2026-09-10.md#7-representation-scope-the-distinction-that-matters-most).
- Not implemented: air/ground interface, 3-D inverse, per-component unknown
  materials, nested holes, touching or intersecting boundaries, and noise
  handling.

`ordered_boundary` owns smooth continuous producers and immutable even-node
curve data. Method B fits Cartesian coordinate Fourier series to an extracted,
projected contour and redistributes arc length. Radial Fourier represents radius
as a function of angle; these are different geometry paths, and the difference
is load-bearing: the five-lobed star is exactly modes 1, 4 and 6 in polar angle,
while the same curve resampled to arc length is not band-limited at any
practical bandwidth.

## What has actually been demonstrated

Separating implemented capability from recorded evidence:

| Claim | Status |
|---|---|
| Automatic birth, death, split and merge without a supplied component count | **Implemented and demonstrated** — five cases in each chart stop `recovered` with identical accepted event sequences |
| Three declared replacement challenges | **Demonstrated** — `full_pass` against each case's declared gates in both charts |
| Matched *geometric* accuracy between charts on every case | **Not established.** The split case reaches `175.21 µm` sampled Hausdorff error in the fresh Cartesian audit run against `15.60 nm` radial, while both are accepted and both stop `recovered` |
| Single-component Cartesian ellipse-to-star recovery | **Demonstrated** — maximum boundary error `4.181e-02 → 2.761e-09 m` in 41 accepted updates; the geometric parity gate passes and the two `1e-7` data gates miss narrowly |
| The topology cost gap iteration 1 reported | **Closed**, in the topology optimizer only. The single-component driver still pays the full `4K + 2` and was not changed |
| Implicit-MLP neural recovery | **Unresolved.** Gradients validated; recovery gates fail |
| Object-count recovery from data | Demonstrated **only** on the recorded clean, separated, noiseless, same-material cases above |
| Controlled wall-clock comparison between charts | **Not performed.** Concurrency for the radial bundles is unrecorded |

Historical conclusions stay in their original records. Where a later audit
revised a number, the dated bundle keeps its original measurement and the audit
records the correction — including the nanometre/micrometre unit corrections,
where the stored metre value is authoritative.

## Explicit Radial Fourier variants

These experiments keep explicit radial geometry; they are not additional
MLP-owned pipelines.

| Variant | Driver and role |
|---|---|
| MLP representation policies | `run_sdf_representation_ablation.py` compares `legacy_strict`, `curve_only` and `export_only`; reconstruction and representation are assessed separately |
| [Shape/material](pipelines/explicit_radial_shape_material.md) | `run_material_inverse_comparison.py` and `run_material_robustness_comparison.py` use a fixed curve or radial K2 state plus one interior permittivity, with analytic Kress derivatives |
| Frozen neural metric | `run_neural_metric_comparison.py` uses an initial neural-feature metric on radial geometry; no neural weights are trained during inversion |

## Legacy known-shape-family controls and numerical references

The [Legacy known-shape-family controls](legacy/known_shape_family_controls.md)
optimize three circle, four ellipse, five star, or seven frozen-random-feature
parameters through extraction and Method B. The star family fixes five lobes;
its center, radius, amplitude and rotation are recovered from measurements.
These runs establish recovery within prescribed families, not full-MLP recovery.
Their observations and measured trajectories remain in the
[result archive](../results/legacy/known_shape_family_parameter_inverse).

`run_sdf_inverse_comparison.py` retains these controls and the distinct neural
`--optimizer parameter_fd` reference. For `siren_*` models that option updates
all network weights using a numerical Jacobian and damped Gauss–Newton. Kress
neural cases default to the adjoint; MOD cases in this comparison retain
parameter finite differences. The FD and adjoint optimizers also differ in
update policy and regularization, so switching the flag alone does not isolate
the derivative method. No matched FD-versus-adjoint neural recovery benchmark
has been completed.

Finite differences used to check an adjoint derivative are validation probes,
not complete FD inverse runs. Separately, the older MOD neural B-scan inverse
uses a compressed boundary cloud and its own adjoint shape surrogate; it does
not use Method B.

## Packages

| Package | Role |
|---|---|
| `gpr_bem_ref` | Frozen original; selector default |
| `gpr_bem_mod` | Compressed-cloud implementation, older neural adjoint, and ordered inverse comparison peer |
| `gpr_bem_kress` | Ordered Müller/Kress forward, multi-component forward extension, and opt-in single-interface discrete derivatives |
| `nystrom_ref` / cylinder Mie series | Independent observation and refinement controls |
| `sdf_to_ordered_boundary` | Extraction/projection, Methods A/B/C, and opt-in conversion studies |
| `sdf_inverse` | Implicit-parameter, curve, topology, representation, metric and material experiments |

## Evidence and reproduction

[Results](../results/README.md) classify runs by geometry ownership, solver, MLP
role, scene, recorded date and outcome. Reconstruction, SDF delivery, physical
recovery, optimizer stopping and forward validation remain separate claims.
Failed arms stay with their comparison.

[Reproduction commands](reproduction.md) cover the implemented adjoint inverse
and its separate controls; [B0 §2](baselines/B0_2026-09-10.md#2-what-the-tracks-actually-start-from)
carries the topology and Cartesian commands with the environment they were run
under. The [September 7 adjoint report](reports/implicit_mlp_adjoint_2026-09-07.md)
records gradient validation and the failed circle, ellipse-to-circle and star
experiments. The [September 10 pipeline audit](../results/validation/cartesian_fourier/pipeline-audit-20260910/README.md)
is the freshest verification of the explicit Cartesian path and the only bundle
pinned to the current source by hash. Its numbers and its inversion video are
committed; its `.npz` rasters and `.png` figures are excluded by the
repository's `results/` binary policy and will be absent from a fresh checkout.

Earlier implementation details and recommendations remain in
[dated reports](reports/README.md); mathematics and numerical protocols remain
in [technical references](reference/README.md). Dated plans describe their
original checkpoints; use this page and the current pipeline pages for present
capabilities and defaults.
