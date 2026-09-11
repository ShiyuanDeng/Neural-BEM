# Results and experiment catalogue

The three current inverse pipelines are [Implicit MLP + Method B](inverse/implicit_mlp/README.md), [Explicit Cartesian Fourier](inverse/cartesian_fourier/README.md), and [Explicit Radial Fourier](inverse/radial_fourier/README.md). **Implicit-MLP recovery remains broken/unresolved:** the adjoint gradient checks pass, but all three new 12-pair inverse runs fail recovery acceptance. **Explicit radial reconstruction works in the recorded successful controls**, with separate failures of neural fitting/export and some experimental variants. Cartesian Fourier runs without neural fitting or audits and includes both topology suites. These folders are not yet a matched three-way benchmark.

The old `results/inverse/method_b` results are now [legacy known-shape-family parameter controls](legacy/known_shape_family_parameter_inverse/README.md). They estimate 3–7 unknowns within supplied circle/ellipse/five-lobe/radial-feature families. Their clean recovery videos are not full-MLP inverse evidence. Material and frozen-neural-metric studies now sit inside `inverse/radial_fourier` because they use explicit geometry.

The next [Method B failure diagnostics](../docs/implicit_mlp_diagnostics.md)
are implemented but not yet run: frozen conversion sweeps, controlled Eikonal
activation, and one-update transfer with a zero-update control. Their new
outputs belong under `validation/method_b_failure_diagnostics/`; add measured
conclusions to this register only after reviewing the actual run artifacts.

[catalog.csv](catalog.csv) contains **162 rows across 60 saved or empty run bundles**, including the three existing 12-pair neural runs indexed during this reorganization, the two initial adjoint diagnostics, the radial-topology birth demonstration, and three full-pass topology challenges. This historical CSV predates the Cartesian suites; use the [Cartesian index](inverse/cartesian_fourier/README.md) and [pipeline audit](validation/cartesian_fourier/pipeline-audit-20260910/README.md) for that evidence. The earlier exporter-failed partial attempt is recorded separately in the [adjoint validation index](validation/implicit_mlp_adjoint/README.md). Inverse runs have a row per solver, policy or declared arm; larger supporting sweeps explicitly identify their grouped scope. The catalogue records accepted geometry, derivative/optimizer, MLP role, target and initialization, observation setup, separate recovery/representation outcomes, date evidence, provenance, and each result's implication for the implicit MLP pipeline.

## Find the right evidence

| Location | Evidence and use |
|---|---|
| [Implicit MLP inverse](inverse/implicit_mlp/README.md) | Current circle, ellipse-to-circle and star neural-adjoint runs; all fail recovery acceptance. |
| [Implicit MLP adjoint validation](validation/implicit_mlp_adjoint/) | Direct neural Kress-adjoint and Method-B reverse; gradient checks, circle/star updates and retained failed recovery gates. |
| [Legacy known-shape-family controls](legacy/known_shape_family_parameter_inverse/) | Analytic/frozen-feature fields with 3–7 unknown parameters; Method B and parameter FD, both MOD and Kress. The family is supplied, numerical parameters are inferred; no full-MLP recovery. |
| [Historical MLP feedback](legacy/inverse/mlp_feedback/) | MLP accepted state, modal probes, re-distance and Method-B re-solve: direct evidence for the pipeline to repair. Historical location preserves the implementation version, not a decision to abandon the approach. |
| [Historical normal updates](legacy/inverse/normal_updates/) | Canonical ordered curves/local modal updates with MLP audits. Diagnose bad parameterizations, spectra, schedules and representation barriers. |
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
