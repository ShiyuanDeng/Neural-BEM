# GU-001: three gauge-keeping geometry updates on hook c13.3

Plan: [03_plan.md](../../../../docs/iterations/geometry_updates/iteration_02/03_plan.md).
Build notes: [05_implementation.md](../../../../docs/iterations/geometry_updates/iteration_02/05_implementation.md).
Run 2026-10-25 11:33–12:02 on an Apple M1 Pro (CPU only), code `645fc19e3`.

Four arms ran at once, one run each, two frequency threads each:
`python -m experiments.benchmark.gu001 run --arm <arm>`. Physics `modal_muller`
(as `modal_fixed`), `--localization none`, default `CumulativePolicy`
(13,412 units, 1,800 s fit), the benchmark's endpoint audit. No reruns.

## Result

**The slider recovers hook c13.3; no other arm does.** It is the only arm that
gets past the near-touch failure and reaches truth (RMS 0.0002 mm, audit passed).

| Arm | Outcome | Data loss | RMS error (mm) | Max error (mm) | Fit time | Speed ratio |
|---|---|---:|---:|---:|---:|---:|
| spectral | physics refused a trial curve, in release_M11 | 0.592 | 8.28 | 25.07 | 124 s, 695 units | 6.47 |
| uncentred | physics refused a trial curve, in fixed_M55 | 0.308 | 7.58 | 23.30 | 1,684 s, 4,707 units | 1.05 |
| n_update + penalty | physics refused a trial curve, in stage_3_damped | 0.00583 + penalty 1.2e-5 | 8.23 | 26.83 | 50 s, 281 units | 2.56 |
| slider | schedule completed (loss tolerance), in fixed_M67 | 6.2e-15 | 0.0002 | 0.0007 | 497 s, 2,978 units | 1.70 |

- Every failure is the modal A1 `|W|^2` refusal of a nearly self-touching
  trial curve, as in NR-001.
- Data losses come from different stages and catalogs, so they compare only
  within a stage.
- Max error is the point-to-polyline Hausdorff distance to truth. Speed ratio
  is max/min speed of the returned curve.
- The spectral rerun reproduces NR-001 (same stage, RMS 8.28 mm).

| Arm | Accepted steps | Max speed ratio | Final E | Max E | Max zero-step jump (mm) | Max crop (mm) | Geometry s | s per unit | Audit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| spectral | 92 | 6.47 | 1.9e-2 | 2.1e-2 | — | 1.37 | 11 | 0.178 | failed |
| uncentred | 166 | 2.02 | 6.4e-5 | 1.2e-2 | 0.58 | 0.91 | 371 | 0.358 | failed |
| n_update + penalty | 43 | 2.56 | 0.16 | 0.16 | — | — | 0 | 0.179 | failed |
| slider | 125 | 1.72 | 8.8e-2 | 0.10 | — | — | 39 | 0.167 | passed |

Speed ratio of the last accepted curve in each stage:

| Stage | spectral | uncentred | n_update | slider |
|---|---:|---:|---:|---:|
| warmup_025_damped | 1.013 | 1.000 | 1.000 | 1.000 |
| stage_1_damped | 1.018 | 1.002 | 1.024 | 1.030 |
| stage_2_damped | 1.018 | 1.011 | 1.115 | 1.161 |
| stage_3_damped | 1.036 | 1.017 | 2.562 | 1.703 |
| stage_4_damped | 1.058 | 1.037 | — | 1.712 |
| stage_4_undamped | 3.503 | 2.020 | — | 1.715 |
| release_M11 | 6.466 | 1.003 | — | 1.715 |
| release_M15 to fixed_M43 | — | 1.000–1.009 | — | 1.698–1.710 |
| fixed_M49, fixed_M55 | — | 1.058, 1.054 | — | 1.698 |
| fixed_M61, fixed_M67 | — | — | — | 1.698 |

## Answers

**1. Do they stop speed unevenness from drifting?**

- Uncentred refit: yes. Accepted curves stay within 1.06 of even speed,
  except at the end of stage_4_undamped (2.02). That stage stores only band
  2M+2 = 18, so the crop of the arclength refit is coarse.
- Slider: it holds what it has, but not from the start. The ratio rose from
  1.0 to 1.70 in the damped stages (small storage band, large steps). It then
  stayed at 1.70–1.72 through stage 4 and all 11 full-catalog stages.
- N-update with the level penalty: no. The ratio reached 2.56 in stage 3, and
  the refused trial curve had 153 (a cusp). The penalty was 0.2% of the loss
  (1.2e-5 against 5.8e-3), too weak to act, as the plan expected.
- Spectral, for reference, drifted from 1.06 to 3.5 and then 6.5.

**2. Does any avoid spectral's near-touch failure?**

- The slider does, and recovers the shape.
- The uncentred refit passes release_M11, where spectral fails. But from
  release_M11 on it stays at data loss 0.3–0.46, a wrong shape (RMS 7.6 mm).
  It hits the same refusal in fixed_M55, after 1,684 s.
- The N-update hits it earlier than spectral, in stage_3_damped.

**3. What does each cost?**

- The geometry update is a small part of the fit, except for the uncentred
  refit. Per preparation: N-update about 0 s (exact arrays), slider 0.27 s,
  spectral 0.11 s (only M ≤ 11 reached).
- The uncentred refit uses spectral's preparation: 2.0 s on average through
  M = 55, 368 s in all, 22% of its fit. Spectral would cost the same at those
  bands.
- Wall time per work unit is 0.17–0.18 s for spectral, N-update and slider,
  and 0.36 s for the uncentred refit. The uncentred arm ran its last 18 minutes
  alone, so its load differed; its geometry share explains the gap.

## Limits

- One scene, one run per arm. The slider's recovery shows it can pass hook
  c13.3, not that it keeps the other 26 recoveries.
- The N-update audit failed on field agreement at the failed endpoint, as the
  other failed arms did. Its slide columns passed the Jacobian check (worst
  8.6e-5), so the predicted failure there did not happen.
- A trial curve refused by the geometry checks saves no curve. Every arm here
  ended on a physics refusal, which the failure record saves, so each video's
  last frame shows the refused curve.

## Files

- `<arm>/` — `manifest.json`, `summary.json`, `runs/hook__c13.3/` (stage
  records with history and trials, `final_audit.json`, `result.json`),
  `steps.csv` (one row per accepted curve: loss, data loss, penalty, speed
  ratio, E, actual maximum normal move, zero-step jump, crop) and `<arm>.mp4`.
- `table.md`, `report.json` — from `python -m experiments.benchmark.gu001 report`.
- `logs/` — campaign output per arm.
