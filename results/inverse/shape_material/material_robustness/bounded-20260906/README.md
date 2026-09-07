# Bounded shape/material robustness controls — 2026-09-06

The deterministic, contrast-stratified multistart plus continuation policy recovered all five declared cohorts. Full-band TRF from the hard initial state recovered none; continuation alone recovered the opposite-contrast noncircular target, but not the circle. This supports retaining an explicitly budgeted restart policy for this small inverse problem. It is not evidence of global convergence, a universal continuation schedule, or a multi-material solver.

All 15 workflows were declared before execution. No seeds, budgets, gates, bounds, or source files were changed during the run; no negative arm was discarded or rerun. All training-only selections were sealed before the first candidate was compared with held-out observations or target geometry.

## Frozen protocol

The five cohorts are joint shape/material inversion for a clean and 1% noisy circle, joint inversion for a clean and 1% noisy noncircle, and a clean fixed-circle/material-only control. Each is run with the same three policies. The optimization chart is `[radius, center_x, center_y, cos_2, sin_2, epsr]`, with one positive, lossless interior permittivity and known exterior permittivity 6. Topology, sources, acquisition, and all production defaults are unchanged.

- Circle observations, complex noise, source strengths, frequencies, train/shifted-angle holdout acquisitions, constants, and initial states are loaded verbatim from `../../material_inverse/bounded-20260906/`. Their saved content hashes are verified. No circle observations are regenerated.
- The separately specified noncircle has physical parameters `[0.052, 0.503, 0.497, 0.0025, -0.0015, 8.4]`. Its contrast is opposite to the circle's interior permittivity 3. Truth enters only the independent oracle and later qualification, never candidate construction or restart ranking. Native radial geometry is evaluated with independently implemented Nyström kernels, not the production Kress solver. The oracle is independently refined for training and holdout. Noise seeds are 4306 and 4316, respectively.
- The joint initial state is the historical hard start `[0.043, 0.505, 0.495, -0.002, 0.001, 9]`; the fixed-circle initial state is `[0.05, 0.5, 0.5, 0, 0, 9]`.
- Radius bounds are `[0.035, 0.075]` m, each center coordinate `[0.47, 0.53]` m, each mode coefficient `[-0.004, 0.004]` m, and permittivity `[1.2, 12]`. Scales and origin are preserved in `manifest.json`. The entire geometry box has positive radius, preserving the declared simple radial topology.
- Optimization uses Kress N=64 with analytic curve/material derivatives. Frequencies are 0.5 and 1.5 GHz. Full-band TRF has an 80-evaluation limit; continuation uses cumulative `[0.5]` then `[0.5, 1.5]` GHz with 40 evaluations per stage. This new full-band control has twice the per-fit evaluation limit of historical D; it is not presented as the same-cost historical run.
- Multistart screens five deterministic joint seeds: the original state; its same geometry with material-bound quartiles 3.9 and 9.3; and the geometry-box midpoint circle with those two materials. Fixed-shape screening omits geometry changes and has three unique seeds. The two retained seeds are the best low-frequency representatives on either side of the known exterior permittivity, when both sides are available. Each retained seed receives the same 40+40 continuation schedule. Final selection uses only the minimum common full-band, frozen-weight, training objective over valid evaluated candidates, including valid trial points. No geometry, holdout, stationarity, or truth preference enters that ranking.
- Every policy has global caps of 400 frequency-specific forward attempts and 2400 analytic direction evaluations. Screening, unsuccessful branches, final ranking, and selected-state stationarity audits count. These are bounded, not matched-cost, comparisons.

## Outcomes

Geometry error is independently refined symmetric closest-point set distance. Holdout error is the maximum per-frequency relative error against the **clean shifted-angle reference**, including when training is noisy. Times below are total reconstruction workflow times, including screening and every retained branch, but exclude qualification and oracle preparation.

| Cohort | Policy | Selected epsr | Geometry error (µm) | Clean holdout error | Physical pass | Workflow seconds |
|---|---|---:|---:|---:|:---:|---:|
| Circle, joint, clean | Full band | 4.118896 | 41439.06 | 0.849530 | No | 40.59 |
| Circle, joint, clean | Continuation | 7.584139 | 21740.72 | 0.921418 | No | 24.80 |
| Circle, joint, clean | Multistart | 3.000000 | <1e-7 | 1.78e-14 | Yes | 28.37 |
| Circle, joint, noisy | Full band | 4.124725 | 41492.80 | 0.847524 | No | 43.53 |
| Circle, joint, noisy | Continuation | 7.584815 | 21771.16 | 0.921310 | No | 31.88 |
| Circle, joint, noisy | Multistart | 3.000048 | 64.89 | 0.00348760 | Yes | 35.61 |
| Noncircle, joint, clean | Full band | 7.941752 | 16757.80 | 0.523495 | No | 11.73 |
| Noncircle, joint, clean | Continuation | 8.400000 | <1e-7 | 2.30e-11 | Yes | 2.02 |
| Noncircle, joint, clean | Multistart | 8.400000 | <1e-7 | 2.16e-11 | Yes | 4.50 |
| Noncircle, joint, noisy | Full band | 7.940405 | 16776.80 | 0.523482 | No | 12.21 |
| Noncircle, joint, noisy | Continuation | 8.401947 | 51.05 | 0.00642683 | Yes | 4.25 |
| Noncircle, joint, noisy | Multistart | 8.401947 | 51.05 | 0.00642683 | Yes | 9.03 |
| Circle, fixed, clean | Full band | 10.143255 | 0 | 1.246786 | No | 3.61 |
| Circle, fixed, clean | Continuation | 10.143254 | 0 | 1.246786 | No | 4.16 |
| Circle, fixed, clean | Multistart | 3.000000 | 0 | 1.53e-14 | Yes | 4.52 |

Full band passes 0/5 cohorts, continuation 2/5, and multistart 5/5. In the noisy recoveries, material absolute errors are 0.0000483 for the circle and 0.0019470 for the noncircle. The successful clean geometries agree with the declared truth to numerical precision.

Every stage reported optimizer success, and every declared search completed without reaching a global work cap. Nevertheless, the eight physically unsuccessful selected states also fail the independently checked scaled projected-gradient tolerance of 1e-7: their projected-gradient norms range from 4.49e-7 to 1.01e-5. Optimizer `ftol` termination is not a stationarity or recovery certificate. All seven physically successful selected states pass the stationarity check, with a maximum projected-gradient norm of 1.17e-9. Stationarity, search completion, optimizer status, and physical recovery remain separate fields in the artifacts.

The failed full-band circle solutions reach the radius upper bound and cosine-mode lower bound. Failed full-band noncircle solutions reach the cosine-mode lower bound. The incorrect continuation circle solutions need not sit on a bound. Boundedness and apparently quiet optimizer termination do not establish a correct physical solution.

## Independent qualification and limitations

The premeasurement physical gates require material error <=0.1, geometry set error <=0.2 mm, set-distance/localization refinement agreement <=2 µm, forward self-convergence <=1e-5, and clean holdout relative error <=1e-4 for clean training or <=0.02 for noisy training. Stationarity uses a separate 1e-7 scaled projected-gradient gate. All thresholds are in the original manifest.

The independent noncircle oracle stopped at N=256 after N=128→256 changes of 1.59235e-11 for training and 1.59322e-11 for holdout, below the frozen 1e-8 gate. It used eight frequency-specific solves. This is an independently coded forward check within the same Müller/Nyström mathematical family, not an unrelated physical model.

Selected states are evaluated at N=64, 128, and 256. Maximum N=128→256 field change across all selected states is 5.55e-13, so their large negative-result field errors are not unresolved quadrature. Every selected full-band objective replay differs from the sealed training score by exactly zero. All seven passing geometry audits meet both refinement gates. The two failed full-band circle geometries also slightly exceed the set-distance refinement threshold (2.16 and 2.36 µm), independently of their much larger physical errors; these are retained failures, not silently qualified geometry estimates.

The successful clean-circle joint weighted real Jacobian has singular values approximately `[1.8730, 1.1523, 1.1351, 0.36947, 0.36924, 0.21231]` and radius/material column correlation -0.9599. The clean noncircle values are approximately `[3.6923, 1.5788, 1.4422, 1.0545, 0.85205, 0.76174]`, with radius/material correlation +0.6412. These are local scaled sensitivities, not global identifiability guarantees. Full singular values, correlations, parameter-bound distances, attempted candidates, and stage histories are retained.

This batch has only two targets, one noise draw per target, a six-parameter in-family geometry chart, one known acquisition, and no model mismatch. It establishes a bounded recovery improvement on the declared hard starts, not a statistical robustness rate or a globally reliable optimizer. The multistart combination does not isolate restart benefit from continuation benefit; plain full-band multistart was not tested. No claim of a matched-cost speed advantage is made. No SDF metric benefit, topology update, conductivity inversion, multiple materials, or 3D capability is established here.

## Counted work and provenance

| Policy, summed over five cohorts | Workflow seconds | Forward attempts | Analytic direction evaluations |
|---|---:|---:|---:|
| Full band | 111.68 | 450 | 2276 |
| Continuation | 67.11 | 329 | 1333 |
| Multistart | 82.03 | 424 | 1659 |
| Total | 260.81 | 1203 | 5268 |

There were 721 candidate builds, 723 cache hits, zero invalid probes, zero failed forward solves, and zero failed direction evaluations. Forward work took 18.49 seconds; analytic derivatives took 241.73 seconds. Qualification was separate: 18.35 seconds, 90 candidate builds, and 180 frequency-specific forward solves, including 2.85 seconds of conditioning audits. Observation preparation took 1.32 seconds. Total wall time, including serialization, was 283.71 seconds. Historical circle observation generation cost is exactly zero in this run; its original generation cost remains in the historical artifact rather than being relabeled as free original data.

All observation/acquisition arrays and the sealed selection checkpoint were unchanged; `source_hash_changes_during_run` is empty. `arrays.npz` contains 2303 numeric arrays and is readable with `allow_pickle=False`. Machine-readable files are strict JSON/CSV and non-pickled NPZ. The initial manifest includes the commit, dirty-worktree state, actual relevant working-tree source SHA256 hashes, command, versions, thread caps, physical configuration, bounds, gates, and historical-input hashes. Data and selections were checkpointed before their dependent stages.

The measured robust core SHA256 is `f50d27875565207415913488d7626160b043224bcff40b4d7b124e3fc17778dc`. The sealed selection-file SHA256 is `29fff3da23cb967a614889881fe081e4bd527670c08e6ea3b240a7f5d528245f`. After this run completed, a defensive guard was added to reject nonfinite scalar objectives before candidate eligibility while preserving counted work and explicit failure records; that hardened core has SHA256 `5214202d28d6e785e25f41da337ded4c0aedf7b03ec1a7106f3ed8cba1b0a3b8`. This post-run hardening is not part of the measured source snapshot. The finite measured run had no numeric failures, and its artifacts are not retroactively regenerated.

The pre-run focused integrated suite passed 56 tests, including the new robustness core, historical material core, and both material drivers. The robustness driver contributes six tests covering verbatim frozen replay, independent opposite-contrast oracle construction, unresolved-oracle rejection, the all-selection-before-qualification barrier, explicit absent-candidate failure, and a small real-core serialization/objective-replay workflow.

The final post-guard combined regression passed **561 tests**, with 276 existing warnings in **110.59 s**, including both finite-residual/scalar-loss-overflow regressions. Independent artifact review also verified all 2303 arrays are finite, all four JSON files parse strictly, all 22 immutable input hashes and all 15 selected-state hashes match, and saved full-band rankings and phase totals replay without solver calls. This validation is subsequent to the timed source snapshot, not a rerun of the benchmark.

Reproduction uses the current guarded source and requires a new output directory:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python run_material_robustness_comparison.py --output results/material_robustness/bounded-20260906
```

`selections.json` is the sealed prequalification record, including numeric sensitivity diagnostics; `metrics.json` adds independent qualification and aggregate costs; `metrics.csv` is the compact per-workflow table; `data_manifest.json` records frozen data and independent-oracle provenance; `arrays.npz` retains numeric observations, candidate states, geometry spectra, and predictions. This README is postprocessing of those unchanged measured files.
