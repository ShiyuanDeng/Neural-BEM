# Results and experiment catalogue

**Latest Cartesian topology evaluation:** [All twelve scenes and videos](validation/topology/TOP-025-20260915-210356-all-scenes-current/README.md), **7/12 passing**, using the frozen current integrated pipeline and original starts.

The three current inverse pipelines are [Implicit MLP + Method B](inverse/implicit_mlp/README.md), [Explicit Cartesian Fourier](inverse/cartesian_fourier/README.md), and [Explicit Radial Fourier](inverse/radial_fourier/README.md). **Implicit-MLP recovery remains broken/unresolved:** the adjoint gradient checks pass, but all three new 12-pair inverse runs fail recovery acceptance. **Explicit radial reconstruction works in the recorded successful controls**, with separate failures of neural fitting/export and some experimental variants. Cartesian Fourier runs without neural fitting or audits and includes both topology suites. These folders are not yet a matched three-way benchmark.

The old `results/inverse/method_b` results are now [legacy known-shape-family parameter controls](legacy/known_shape_family_parameter_inverse/README.md). They estimate 3–7 unknowns within supplied circle/ellipse/five-lobe/radial-feature families. Their clean recovery videos are not full-MLP inverse evidence. Material and frozen-neural-metric studies now sit inside `inverse/radial_fourier` because they use explicit geometry.

The next [Method B failure diagnostics](../docs/implicit_mlp_diagnostics.md)
are implemented but not yet run: frozen conversion sweeps, controlled Eikonal
activation, and one-update transfer with a zero-update control. Their new
outputs belong under `validation/method_b_failure_diagnostics/`; add measured
conclusions to this register only after reviewing the actual run artifacts.

[catalog.csv](catalog.csv) contains **204 rows**. The original 162 rows span 60 saved or empty run bundles, including the three existing 12-pair neural runs indexed during this reorganization, the two initial adjoint diagnostics, the radial-topology birth demonstration, and three full-pass topology challenges. The new topology rows group the TOP-001/TOP-005 replay and controller comparisons by chart/arm; scalar metrics there are worst-case values. Two TOP-019 rows record the prescribed S/F merge endpoints. The original CSV snapshot predates the Cartesian suites; use the [Cartesian index](inverse/cartesian_fourier/README.md) and [pipeline audit](validation/cartesian_fourier/pipeline-audit-20260910/README.md) for that evidence. The earlier exporter-failed partial attempt is recorded separately in the [adjoint validation index](validation/implicit_mlp_adjoint/README.md). Inverse runs have a row per solver, policy or declared arm; larger supporting sweeps explicitly identify their grouped scope. The catalogue records accepted geometry, derivative/optimizer, MLP role, target and initialization, observation setup, separate recovery/representation outcomes, date evidence, provenance, and each result's implication for the implicit MLP pipeline.

## SPD-002 fast default in complete topology pipelines

[Full measured comparison](validation/speedup/SPD-002-20260916-default-pipeline/README.md)
· [Default-promotion closeout](../docs/iterations/speedup/iteration_03/01_results.md) · 2026-09-16:
**Death: 434.65 → 233.73 s (1.86x); split: 418.01 → 221.53 s (1.89x).**
Both reference and fast profiles complete automatic topology and all four
continuation stages and pass every recovery gate. Recovered boundaries differ
by less than 7e-11 m. 261 tests pass. Analytic Cartesian Jacobians and fast CPU
kernels are now the default; the reference profile restores FD/reference CPU.
Two full-case controls, not a new twelve-scene scorecard.

## SPD-001 combined analytic Jacobian and CPU/CUDA speed

[Six-arm measured comparison](validation/speedup/SPD-001-20260915-233833-combined/README.md)
· [Closeout](../docs/iterations/speedup/iteration_02/01_results.md) · 2026-09-16:
**261.2 s → 100.4 s (2.60x)** for one complete four-frequency optimizer update
with analytic derivatives and faster CPU kernels; adding CUDA gives **98.2 s
(2.66x)**. All six arms accept one update and agree within 0.022 micrometres
in coefficient infinity norm. Three-repeat Jacobian timings show 3.11x/3.13x
for those combined paths. 145 tests pass. This is bounded local optimizer
runtime evidence, not full-recovery or default-promotion evidence.

## TOP-019 capacity-qualified merge pair

[Result bundle](validation/topology/TOP-019-20260915-144340-qualified-merge/README.md) ·
[Endpoint figure](validation/topology/TOP-019-20260915-144340-qualified-merge/endpoints.svg) ·
[Iteration 13](../docs/iterations/topology/iteration_13/01_results.md) · 2026-09-15:
both K=17 arms recover and qualify at 256/512. S ends at 0.0860067 mm / 0.0116406
worst evaluation error (1,284 solves); F at 0.0214283 mm / 0.00229358 (4,844).
Total 6,232 completed solves, zero failed. F buys more precision at higher cost;
there is no binary recovery advantage on this control. The historical K=9 merge
regression remains preserved. Fresh automatic two-star integration is next to
scope; no successor or production promotion is approved.

## TOP-018 resolution-qualified two-star pair

[S/F comparison video (50 s)](validation/topology/TOP-018-20260915-two-star-video/two_star_S_vs_F.mp4) ·
[Video provenance](validation/topology/TOP-018-20260915-two-star-video/README.md)

[Result bundle](validation/topology/TOP-018-20260915-resolution-qualified-pair/README.md) ·
[Endpoint figure](validation/topology/TOP-018-20260915-resolution-qualified-pair/endpoints.svg) ·
[Iteration 12](../docs/iterations/topology/iteration_12/01_results.md) · 2026-09-15:
both matched schedules qualified at 256/512. F recovers (0.00167644 mm boundary,
3.323707e-6 worst evaluation error); S fails recovery (11.793168 mm, 1.306218).
8,336 new solves completed, zero failed; all ceilings passed. A post-schedule
reporting error was repaired from saved artifacts, with both failed worker exits
preserved. Fixed-count development-case evidence; no controller promotion or
successor run. TOP-016's merge regression and the earlier central successes remain.

## TOP-017 staged principal continuation

[Central-case video (53 s)](validation/topology/TOP-017-20260914-central-video/central_circle_to_ellipse_star.mp4) · [Video provenance](validation/topology/TOP-017-20260914-central-video/README.md)

[TOP-017 result bundle](validation/topology/TOP-017-20260914-staged-continuation/README.md) · [Iteration 11](../docs/iterations/topology/iteration_11/01_results.md) · 2026-09-14: central F recovered within all original gates and substantially outperformed the matched S control; the two-star pair stopped at frozen numerical gates. The full paired predicate is incomplete, with no promotion. 12,535 new attempted/completed solves, zero failed; all limits respected. Historical TOP-016 evidence and its merge regression remain preserved.

## TOP-016 bounded fixed-topology continuation

[TOP-016 result bundle](validation/topology/TOP-016-20260914-fixed-topology/README.md) · 2026-09-14: both local-information gates passed, but principal and truth-assisted local trials stopped at their first-stage budgets. The completed frequency-continuation merge control introduced a geometric failure. No promotion; 10,306 attempted/completed frequency solves, zero failed. The bundle preserves all arms, exact work, source/input hashes, independent review and reporting limitations. [Iteration 10](../docs/iterations/topology/iteration_10/01_results.md) preserves that closeout; its successor TOP-017 is recorded above.

## Find the right evidence

| Location | Evidence and use |
|---|---|
| [Implicit MLP inverse](inverse/implicit_mlp/README.md) | Current circle, ellipse-to-circle and star neural-adjoint runs; all fail recovery acceptance. |
| [Implicit MLP adjoint validation](validation/implicit_mlp_adjoint/) | Direct neural Kress-adjoint and Method-B reverse; gradient checks, circle/star updates and retained failed recovery gates. |
| [Legacy known-shape-family controls](legacy/known_shape_family_parameter_inverse/) | Analytic/frozen-feature fields with 3–7 unknown parameters; Method B and parameter FD, both MOD and Kress. The family is supplied, numerical parameters are inferred; no full-MLP recovery. |
| [Historical MLP feedback](legacy/inverse/mlp_feedback/) | MLP accepted state, modal probes, re-distance and Method-B re-solve: direct evidence for the pipeline to repair. Historical location preserves the implementation version, not a decision to abandon the approach. |
| [Historical normal updates](legacy/inverse/normal_updates/) | Canonical ordered curves/local modal updates with MLP audits. Diagnose bad parameterizations, spectra, schedules and representation barriers. |
| [Topology treatments](validation/topology/README.md) | TOP-001 allocation failures and TOP-005 selective-refinement qualification, with paired perturbations and actual work accounting. |
| [Cartesian Fourier](inverse/cartesian_fourier/README.md) | Single-component ellipse-to-star recovery, five automatic topology cases, and three topology challenges without an MLP. |
| [Radial controls](inverse/radial_fourier/) | Explicit star-shaped radial coefficients, including strict/curve-only/export-only policies. `legacy_strict` here still owns a radial curve, not an MLP zero set. |
| [Shape/material](inverse/radial_fourier/shape_material/) and [neural metrics](inverse/radial_fourier/neural_metric/) | Analytic-derivative radial variations. Study derivative quality, initialization basins, training-only selection and metric choices. |
| [Representation](representation/) and [validation](validation/) | Frozen MLP fits, Method-B conversion, quadrature, derivatives and forward checks. Isolate failing parts before another full inverse. |
| [Legacy development](legacy/development/), [solver experiments](legacy/solver_experiments/) and [demos](demos/) | Superseded audit versions, QBX evidence, forward/geometry demonstrations. Demos and empty markers are not completed inverse results. |

## Measured results and implications

Dates are recorded UTC dates unless marked **label only**. Error definitions and acquisitions differ; inspect the linked artifact or the catalogue's metric-scope columns before comparing numbers.

| Run / date | Scene and initialization | Actual pipeline | Measured takeaway | Implication for Implicit MLP + Method B |
|---|---|---|---|---|
| [Current 12-pair implicit MLP runs](inverse/implicit_mlp/README.md) · 2026-09-07 | Wrong neural circle/ellipse → circle; wrong neural star → star | Full SIREN weights; Kress adjoint → Method-B reverse → Adam/backtracking | All three recovery gates FAIL; final holdout `0.06394`, `0.31864`, `0.78392`; boundary `1.038`, `6.450`, `26.833 mm`. | Current neural reconstruction needs repair despite validated gradients. These existing runs were indexed, not rerun, during the move. |
| [Implicit MLP circle](validation/implicit_mlp_adjoint/circle-verified-20260907/summary.md) · 2026-09-07 | Wrong neural circle → 50 mm circle; independent Mie | Kress adjoint → Method-B reverse → neural weights | 41 updates, loss `0.921 → 3.09e-6`; holdout `0.07072`, contour `1.038 mm`; overall FAIL. | Direct neural updates work; low training loss still does not meet the representation-relative recovery gates. |
| [Implicit MLP star](validation/implicit_mlp_adjoint/star-20260907/summary.md) · 2026-09-07 | Wrong neural star → five-lobe star; independent Nyström | Same direct neural adjoint; five-step budget | Loss drops 19.16%, holdout worsens `0.8914 → 1.1179`; overall FAIL. Full neural gradient audit agrees to `2.74e-8`. | Correct gradients and accepted training decrease do not establish star reconstruction. |
| [Known-family circle controls](legacy/known_shape_family_parameter_inverse/) · 2026-09-02 | Wrong circle, ellipse or frozen radial-feature field → 50 mm circle; Mie data | 3/4/7 parameter FD → Method B → MOD/Kress | Kress holdout ≈`3.8e-10`–`3.6e-9`; supplied model family contains the exact target. | Legacy parametric recovery, not full-MLP shape discovery. |
| [Known five-lobe family control](legacy/known_shape_family_parameter_inverse/wrong-star-nystrom-20260903/summary.md) · 2026-09-02 23:08 UTC | Five unknown star parameters; lobe count supplied from target configuration | 5 parameter FD → Method B → MOD/Kress | Kress holdout `3.139e-5`; geometry bandwidth contributes the floor. | Legacy recovery within a known star family; not discovering the number of lobes. Folder date is Sep 3 in London. |
| [MLP ellipse → star](legacy/inverse/mlp_feedback/mlp-ellipse-to-star-nystrom-20260903/summary.md) · 2026-09-03 | Wrong ellipse → five-lobe star | MLP-owned geometry; modal FD, re-distance, Method-B re-solve | Kress train/holdout `0.1327`/`0.3400`; boundary error `7.369 mm`; no decreasing re-distanced step. | Isolate whether a promising data update survives fitting and extraction. This is progress, not certified recovery. |
| [Resolved normal updates](legacy/inverse/normal_updates/mlp-resolved-k5-ellipse-to-star-kress-20260904/summary.md) · 2026-09-04 | Wrong ellipse → five-lobe star | Canonical Cartesian curve/local normal updates; MLP audit | Holdout `1.073`; boundary error `46.92 mm` despite faithful MLP tracking of the wrong curve. | Geometry search can fail independently of neural representation. |
| [Radial milestone](inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md) · 2026-09-04 | Wrong ellipse → five-lobe star | Radial K5 FD continuation; mandatory MLP audit | Canonical holdout `1.339e-8`; boundary error `2.570e-10 m`; MLP drift `0.329 mm` misses the separate `0.2 mm` gate. | Use the recovered curve as a controlled neural-fit target; canonical success is not strict delivery. |
| [Radial topology birth](inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/README.md) · 2026-09-08 | Exact A with B absent, plus predeclared wrong-A qualification → two circles | Current-domain TD at 0.50 GHz → resolution-qualified finite birth → multi-radial K1 FD/LM | G0–G5 pass; core train `4.54e-10`, holdouts at most `3.58e-9`; wrong-A train `1.61e-10`. | Demonstrates one explicit topology birth on the declared separated benchmark; it does not establish general or neural topology recovery. |
| [Radial topology challenges](inverse/radial_fourier/topology_challenges/README.md) · 2026-09-09 | Enclosing/far/middle circle → two circles or diagonal ellipse and star | Low-frequency background-TD replacement → cross-resolution acceptance → radial continuation/FD-LM | All three pass. Circle geometry below `1.1e-8 m`; ellipse/star geometry `0.552 mm`, training `5.68e-3`, 2.5-GHz holdout `5.25e-2`. | Extends explicit topology evidence to component replacement and unequal K5 shapes; still clean, separated, noiseless and non-neural. |
| [Representation policies](inverse/radial_fourier/representation_policies/saved-star-20260905/summary.md) · 2026-09-05 | Identical ellipse/star data and initial radial coefficients | Radial FD; `legacy_strict`, `curve_only`, `export_only` | All share 44 updates and holdout `1.3393e-8`. End-to-end times `240.07`, `82.98`, `91.40 s`; strict and final-export representation both fail. | Quantify neural costs and separate outcomes. This does not remove the need to repair MLP-owned geometry. |
| [Smooth-distance fits](representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md) · 2026-09-05 **label only** | Frozen 65 mm circle and five-lobe star; same MLP initialization, samples and 600-step budgets | Polygon vs continuous-distance labels; Method-B extraction audit | Smooth labels improve interfaces/fields; star drift remains `0.5345 mm`; all four strict redistance stopping gates fail. | Improve labels and independently audit extraction; smooth labels alone do not solve neural distance fidelity. |
| [Derivative validation](validation/kress_shape_derivative/refined-audits-20260906/summary.md) · 2026-09-06 | Circle, ellipse, star, zero contrast; frozen directions | Complete Kress JVP/adjoint, FD and independent audits | `96/96` fixed-node checks and separate physical/refinement gate pass. | Reuse verified field derivatives, then verify the neural/Method-B map separately. |
| [Material starts](inverse/radial_fourier/shape_material/material_inverse/bounded-20260906/README.md) · 2026-09-06 | Circle; fixed geometry or joint radial K2/material; clean/1% noisy | Analytic Kress derivative + bounded TRF | Physical recovery passes `5/8`; high-permittivity starts retain failures. | Separate termination, stationarity and recovery; retain adverse starts. |
| [Material robustness](inverse/radial_fourier/shape_material/material_robustness/bounded-20260906/README.md) · 2026-09-06 | Circle and opposite-contrast noncircle; five clean/noisy cohorts | Radial K2/material; full band / continuation / multistart | Recovery `0/5`, `2/5`, `5/5`; bounded two-target study. | Test initialization/schedule effects with training-only selection and explicit budgets. |
| [Frozen neural metrics](inverse/radial_fourier/neural_metric/comparison-20260906/README.md) · 2026-09-06 | Wrong exact circle → circle/star | Explicit radial K5; identity/Sobolev/frozen neural metrics | Three neural seeds underperform explicit controls; all star arms hit the update budget. No MLP training/extraction in the inverse. | Require evidence for neural search benefits; resolved fields do not imply recovery. |

## Preservation, dates and reruns

Original measured JSON/CSV/arrays and commands are preserved. [relocations.json](relocations.json) maps moved paths; original paths remain in the catalogue and historical provenance. Recorded commands describe the old run, including old defaults and output paths. They are **not ready-to-run commands** for overwriting preserved evidence.

Source revisions and hashes describe the measured code. Cleanup also updates driver input/output path literals, so current source hashes can differ without changing the recorded numerical conclusions. This index does not claim present-day source equality or a numerical rerun.

`catalog_status` describes an evidence role, independently of `recovery_outcome` and `representation_outcome`. A `current_diagnostic` can fail; historical evidence can still guide repairs. The two empty-before-cleanup folders have navigation markers only. The new adjoint runs are completed diagnostics, with no claim that their failed recovery gates passed.

The catalogue preserves `recorded_utc` and its `date_source`; a date inferred from a folder is not a verified UTC execution date. Filesystem modification times were not used. In particular, `mlp-joint-k6-...-20260903` records **2026-09-04 08:40 UTC**.

Preserve the superseded short-export, early smooth-fit extraction and derivative-audit bundles: corrected replacements already exist. Post-measurement source changes for saved-star, derivatives and robustness are explained in the [historical reports](../docs/reports/); they do not justify rerunning every old experiment. New evidence should target neural-adjoint recovery, distance fidelity and extraction resolution, using radial/frozen-curve controls to locate failures. Follow the [pipeline guide](../docs/pipelines/implicit_mlp.md) and [reproduction commands](../docs/reproduction.md) for controlled comparisons and fresh output paths.

## Maintaining the catalogue

This is a checked snapshot, not an automatic scan performed by the experiment
drivers. After a new run, add its scene/solver/policy rows to `catalog.csv`
from recorded metadata and link its measured summary here when it changes a
conclusion. Blank metric cells mean unavailable or unevaluated, never zero.
Keep supporting sweeps explicitly grouped and use a fresh stable run ID.

The historical [organization audit](organization_audit.json) records byte-preservation,
path, syntax and the earlier 153-row catalogue checks. It records no numerical rerun
and predates the five new adjoint rows. The
[known-family relocation audit](known_shape_family_relocation_audit.json) records
the later directory moves and payload-preservation checks, without a numerical rerun. The old
geometry path is the sole compatibility alias; [relocations](relocations.json)
explain it and all moves.

## TOP-023 terminal derivative and damping diagnosis

[TOP-023 closeout](validation/topology/TOP-023-20260915-181302-terminal-model/README.md):
the terminal model and selected directional checks pass. Damping 1e-2 gives
3.978× the baseline step gain using 8 versus 24 candidate calls. 396 total new
calls, zero failures; 85 pre-dispatch tests and saved-array replay pass. No
inverse was run. [Iteration 16](../docs/iterations/topology/iteration_16/01_results.md)
records the bounded continuation comparison next; no full suite is released.

## TOP-022 fresh direct four-frequency integration

[TOP-022 closeout](validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars/README.md):
the fresh direct protocol also fails recovery despite qualified numerics.
Final boundary error 9.755053 mm, IoU 0.830130, worst development error 0.619185;
8,247 charged calls. 22 updates stop at maximum iterations with a measured
terminal gradient above tolerance. 112 pre-dispatch tests and artifact replay
pass. [Iteration 15](../docs/iterations/topology/iteration_15/01_results.md)
records the bounded terminal-model diagnosis next; no full suite is released.

## TOP-020 fresh automatic two-star integration

[TOP-020 closeout](validation/topology/TOP-020-20260915-153359-fresh-two-stars/README.md):
the original distant-circle controller finds two objects, but its fresh staged
refinement fails recovery despite qualified numerics (9.97354 mm, IoU 0.828248,
worst development error 0.601150). All 9,375 calls reconcile: 9,308 completed
systems and 67 geometry refusals. The full staged suite is not released;
[iteration 14](../docs/iterations/topology/iteration_14/01_results.md) records the
next bounded protocol check. Historical positive and adverse evidence is kept.

## TOP-024 bounded two-star continuation

[TOP-024 closeout](validation/topology/TOP-024-20260915-201101-bounded-damping-pair/README.md):
**NEITHER_ARM_RECOVERED** under unchanged gates, with 7,504 new calls
and 0 failed/refused. [Iteration 17](../docs/iterations/topology/iteration_17/01_results.md)
records the decision; the overall automatic method remains unqualified.
