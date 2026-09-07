# Results and experiment catalogue

The research target is **strict MLP-owned geometry → Method B → BEM**. Its reconstruction and representation failures are the problems to fix. Radial Fourier, optional export, analytic-derivative and material experiments provide controls and lessons for that work; their successes do not establish strict MLP/Method-B recovery. Start with the [strict pipeline guide](../docs/pipelines/strict_mlp_method_b.md).

[catalog.csv](catalog.csv) contains **153 rows across 51 saved or empty run bundles**. Inverse runs have a row per solver, policy or declared arm; larger supporting sweeps explicitly identify their grouped scope. The catalogue records accepted geometry, derivative/optimizer, MLP role, target and initialization, observation setup, separate recovery/representation outcomes, date evidence, provenance, and each result's implication for the strict pipeline.

## Find the right evidence

| Location | Evidence and use |
|---|---|
| [Method-B controls](inverse/method_b/) | Small implicit-parameter inverses rebuilt through Method B. Check extraction and forward accuracy with independent observations; these are not full MLP inverses. |
| [Historical MLP feedback](legacy/inverse/mlp_feedback/) | MLP accepted state, modal probes, re-distance and Method-B re-solve: direct evidence for the pipeline to repair. Historical location preserves the implementation version, not a decision to abandon the approach. |
| [Historical normal updates](legacy/inverse/normal_updates/) | Canonical ordered curves/local modal updates with MLP audits. Diagnose bad parameterizations, spectra, schedules and representation barriers. |
| [Radial controls](inverse/radial_fourier/) | Explicit star-shaped radial coefficients, including strict/curve-only/export-only policies. `legacy_strict` here still owns a radial curve, not an MLP zero set. |
| [Shape/material](inverse/shape_material/) and [neural metrics](inverse/neural_metric/) | Analytic-derivative radial variations. Study derivative quality, initialization basins, training-only selection and metric choices. |
| [Representation](representation/) and [validation](validation/) | Frozen MLP fits, Method-B conversion, quadrature, derivatives and forward checks. Isolate failing parts before another full inverse. |
| [Legacy development](legacy/development/), [solver experiments](legacy/solver_experiments/) and [demos](demos/) | Superseded audit versions, QBX evidence, forward/geometry demonstrations. Demos and empty markers are not completed inverse results. |

## Measured results and implications

Dates are recorded UTC dates unless marked **label only**. Error definitions and acquisitions differ; inspect the linked artifact or the catalogue's metric-scope columns before comparing numbers.

| Run / date | Scene and initialization | Actual pipeline | Measured takeaway | Implication for strict MLP + Method B |
|---|---|---|---|---|
| [Method-B circle controls](inverse/method_b/) · 2026-09-02 | Wrong circle, ellipse or random-feature field → 50 mm circle; Mie data | Implicit parameter FD → Method B → MOD/Kress | Kress holdout ≈`3.8e-10`–`3.6e-9`; each small model family contains the target. | Retain a working extraction/forward control; this does not establish general neural recovery. |
| [Method-B star](inverse/method_b/wrong-star-nystrom-20260903/summary.md) · 2026-09-02 23:08 UTC | Wrong five-parameter star → five-lobe star; independent Nyström | Implicit parameter FD → Method B → MOD/Kress | Kress holdout `3.139e-5`; geometry bandwidth contributes the floor. | Measure extraction error as well as BEM refinement. Folder date is Sep 3 in London. |
| [MLP ellipse → star](legacy/inverse/mlp_feedback/mlp-ellipse-to-star-nystrom-20260903/summary.md) · 2026-09-03 | Wrong ellipse → five-lobe star | MLP-owned geometry; modal FD, re-distance, Method-B re-solve | Kress train/holdout `0.1327`/`0.3400`; boundary error `7.369 mm`; no decreasing re-distanced step. | Isolate whether a promising data update survives fitting and extraction. This is progress, not certified recovery. |
| [Resolved normal updates](legacy/inverse/normal_updates/mlp-resolved-k5-ellipse-to-star-kress-20260904/summary.md) · 2026-09-04 | Wrong ellipse → five-lobe star | Canonical Cartesian curve/local normal updates; MLP audit | Holdout `1.073`; boundary error `46.92 mm` despite faithful MLP tracking of the wrong curve. | Geometry search can fail independently of neural representation. |
| [Radial milestone](inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/summary.md) · 2026-09-04 | Wrong ellipse → five-lobe star | Radial K5 FD continuation; mandatory MLP audit | Canonical holdout `1.339e-8`; boundary error `2.570e-10 m`; MLP drift `0.329 mm` misses the separate `0.2 mm` gate. | Use the recovered curve as a controlled neural-fit target; canonical success is not strict delivery. |
| [Representation policies](inverse/radial_fourier/representation_policies/saved-star-20260905/summary.md) · 2026-09-05 | Identical ellipse/star data and initial radial coefficients | Radial FD; `legacy_strict`, `curve_only`, `export_only` | All share 44 updates and holdout `1.3393e-8`. End-to-end times `240.07`, `82.98`, `91.40 s`; strict and final-export representation both fail. | Quantify neural costs and separate outcomes. This does not remove the need to repair MLP-owned geometry. |
| [Smooth-distance fits](representation/smooth_distance_supervision/task-b-circle-star-refined-20260905/README.md) · 2026-09-05 **label only** | Frozen 65 mm circle and five-lobe star; same MLP initialization, samples and 600-step budgets | Polygon vs continuous-distance labels; Method-B extraction audit | Smooth labels improve interfaces/fields; star drift remains `0.5345 mm`; all four strict redistance stopping gates fail. | Improve labels and independently audit extraction; smooth labels alone do not solve neural distance fidelity. |
| [Derivative validation](validation/kress_shape_derivative/refined-audits-20260906/summary.md) · 2026-09-06 | Circle, ellipse, star, zero contrast; frozen directions | Complete Kress JVP/adjoint, FD and independent audits | `96/96` fixed-node checks and separate physical/refinement gate pass. | Reuse verified field derivatives, then verify the neural/Method-B map separately. |
| [Material starts](inverse/shape_material/material_inverse/bounded-20260906/README.md) · 2026-09-06 | Circle; fixed geometry or joint radial K2/material; clean/1% noisy | Analytic Kress derivative + bounded TRF | Physical recovery passes `5/8`; high-permittivity starts retain failures. | Separate termination, stationarity and recovery; retain adverse starts. |
| [Material robustness](inverse/shape_material/material_robustness/bounded-20260906/README.md) · 2026-09-06 | Circle and opposite-contrast noncircle; five clean/noisy cohorts | Radial K2/material; full band / continuation / multistart | Recovery `0/5`, `2/5`, `5/5`; bounded two-target study. | Test initialization/schedule effects with training-only selection and explicit budgets. |
| [Frozen neural metrics](inverse/neural_metric/comparison-20260906/README.md) · 2026-09-06 | Wrong exact circle → circle/star | Explicit radial K5; identity/Sobolev/frozen neural metrics | Three neural seeds underperform explicit controls; all star arms hit the update budget. No MLP training/extraction in the inverse. | Require evidence for neural search benefits; resolved fields do not imply recovery. |

## Preservation, dates and reruns

Original measured JSON/CSV/arrays and commands are preserved. [relocations.json](relocations.json) maps moved paths; original paths remain in the catalogue and historical provenance. Recorded commands describe the old run, including old defaults and output paths. They are **not ready-to-run commands** for overwriting preserved evidence.

Source revisions and hashes describe the measured code. Cleanup also updates driver input/output path literals, so current source hashes can differ without changing the recorded numerical conclusions. This index does not claim present-day source equality or a numerical rerun.

`catalog_status` describes an evidence role, independently of `recovery_outcome` and `representation_outcome`. A `current_diagnostic` can fail; historical evidence can still guide repairs. The two empty-before-cleanup folders have navigation markers only. This organization claims no completed repaired strict-MLP run.

The catalogue preserves `recorded_utc` and its `date_source`; a date inferred from a folder is not a verified UTC execution date. Filesystem modification times were not used. In particular, `mlp-joint-k6-...-20260903` records **2026-09-04 08:40 UTC**.

Preserve the superseded short-export, early smooth-fit extraction and derivative-audit bundles: corrected replacements already exist. Post-measurement source changes for saved-star, derivatives and robustness are explained in the [historical reports](../docs/reports/); they do not justify rerunning every old experiment. New evidence should target strict MLP/Method-B data-step transfer, re-distance fidelity and extraction resolution, using radial/frozen-curve controls to locate failures. Follow the [strict pipeline guide](../docs/pipelines/strict_mlp_method_b.md) for repair scope and [reproduction commands](../docs/reproduction.md) for fresh output paths and executable reruns. This cleanup executes no experiments.

## Maintaining the catalogue

This is a checked snapshot, not an automatic scan performed by the experiment
drivers. After a new run, add its scene/solver/policy rows to `catalog.csv`
from recorded metadata and link its measured summary here when it changes a
conclusion. Blank metric cells mean unavailable or unevaluated, never zero.
Keep supporting sweeps explicitly grouped and use a fresh stable run ID.

The [organization audit](organization_audit.json) records byte-preservation,
path, syntax and catalogue checks. It records no numerical rerun. The old
geometry path is the sole compatibility alias; [relocations](relocations.json)
explain it and all moves.
