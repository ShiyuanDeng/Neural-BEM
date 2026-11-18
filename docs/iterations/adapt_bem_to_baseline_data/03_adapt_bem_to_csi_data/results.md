# Adapt the BEM inverse to CSI data: results

## Review stop 2: forward checks, 18 November 2026

**Outcome: the adapter passes every check, but the simulated circle fails
the user's 1% rule at 4, 6, 7 and 8 GHz.** Our forward matches an exact
series solution to about 1e-13. So the excess is in CSI's simulated data,
not in our forward or the adapter. Per the plan this stops the work: the
coordinator asks the user.

Run: `experiments/bem_on_baseline_data/csi_forward_check.py`, CPU, one
thread, 34.5 s, peak memory 1.2 GB. Solver: a clean `git archive` of commit
`78f084ca9`, because the checkout's `solvers/bem_inverse/` was being edited
by `bem-gpu` (recorded in the receipt). No fit ran. Truth was read only by
this script.

Evidence: [forward_checks.json](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/forward_checks.json),
[truth_predictions.npz](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/truth_predictions.npz),
[cylinder_frame_info.json](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/cylinder_frame_info.json).
The NPZ is git-ignored and stays local; its SHA-256 is beside it.
The first run, kept in `forward_checks_run1_exact_circle_skipped/`, has the same numbers. It
skipped the exact series on the circle because the script's circle test was
too strict (a round-off-sized coefficient); that was fixed and the run repeated.

### Adapter checks

| Check | Result | Pass |
|---|---|---|
| Our factor vs CC-CSI's saved factors (288 rows), conj(Enor·ω_n²) | max relative difference 8.5e-14 | yes |
| Simulated table: conj(incident) vs our unit field i H0(kr)/4, all pairs | ≤ 1.3e-14 | yes |
| Simulated table: factor equals 1 | ≤ 2.9e-14 | yes |
| File order ↔ C order permutation round trip | ≤ 1.2e-16 | yes |
| Ragged vs rectangular B5/B8 at the start circle, all 8 frequencies, band 11 + contrast column | loss 1.2e-16, residual 5.7e-16, Jacobian 7.5e-16, gradient 2.9e-16 (relative) | yes |

The rectangular branch does accept the masked table. The two layouts agree to
round-off, so the frequency-block layout keeps the default loss.

Spread of |c| over the 36 sources (measured file, information only): largest
over smallest is 1.0002–1.0060 per frequency (worst 5 GHz). Phase spread
0.01–0.19°. So dividing by c hardly reweights sources.

### Mismatch per frequency on the true shapes

Relative L2, ‖our forward on the truth − data‖ / ‖data‖. The same to four
digits at the truth's own resolution and at the fit's storage band 192.

| GHz | Circle `circle__c4`, ε 4 | Cylinder `dielTM_dec8f`, nominal ε 3 |
|---|---|---|
| 1 | 0.17% | 47.8% |
| 2 | 0.13% | 23.1% |
| 3 | 0.30% | 24.5% |
| 4 | **1.14%** | 27.7% |
| 5 | 0.82% | 30.5% |
| 6 | **1.68%** | 33.9% |
| 7 | **2.29%** | 37.1% |
| 8 | **5.91%** | 40.4% |

Exact series check: for both circles our forward equals the separation of
variables solution to 6e-16 – 2.3e-13. The circle data differ from that
exact solution by the same amounts as from our forward. The error grows with
frequency, as a grid error would. CSI's forward grid is 0.625 mm with a
staircase boundary and averaged material (CSI note); that cause is likely
but not measured here.

Cylinder: the truth is nominal (about 30 mm offset, ε 3 ± 0.3), and the data
are measured. Fitting one complex number to each frequency, for information
only, leaves 16–37%. A frame check (information only, never used by a fit)
puts the same cylinder at (0,−30), (+30,0) and (−30,0) mm; those give
86–138%, against 23–48% at the nominal (0,+30) mm. So the frame sign is right.
The rest is the nominal geometry and measurement error. It is reported, not
judged.

### Series limit at 8 GHz

The solver's coefficient-based wave radius and loss, at k = 8.38 per 5 cm:

| Curve | Wave radius | k × radius | Loss | Under 1e-9 |
|---|---|---|---|---|
| Cylinder truth | 15 mm | 2.5 | 7.4e-16 | yes |
| Circle truth | 50 mm | 8.4 | 1.4e-13 | yes |
| Start circle | 65 mm | 10.9 | 1.5e-12 | yes |

8 GHz is not refused; the series limit stays 1e-9.

### Open for the coordinator

- The 1% rule fails on the circle at 4, 6, 7 and 8 GHz (worst 5.9%). By the
  user's decision, the coordinator asks the user before any fit.
- Not done yet: the small test file `csi_test.py` from the plan. The
  permutation, factor and conjugation checks above cover the same ground.

Resolved after stop 2: the user chose 1–3 GHz for the simulated tables ("id
say we just supply less frequency range to it, you know below 4GHz such that
simulated data are accurate there"). The coordinator dropped `csi_test.py`;
the adapter checks are now one resumable command, `csi_forward_check.py --cases`.

## Simulated dataset settings, 18 November 2026

Set by the coordinator before any simulated fit, the same for all ten shapes,
in `DATASETS` of [csi_fit.py](../../../../experiments/bem_on_baseline_data/csi_fit.py):

- Rows for 1, 2 and 3 GHz are selected from the retained eight-frequency
  file, which is not rewritten. Every output records the file SHA-256 and the
  rows used (in the file, frequency changes fastest: rows f, f+8, ...).
- Ladder 1; 1–2; 1–3 GHz (bands 3, 6, 9), quotas (1000, 3000, 4000), then the
  default whole-catalog stages (bands 11 to 37) and the frontier. No solver edit.
- The measured cylinder keeps all eight frequencies and its rule.
- A simulated fit refuses to start without that shape's passing adapter check
  and 1% rule at 1–3 GHz. Circle: 0.17, 0.13, 0.30%, passes
  ([check](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/adapter_checks_1to3ghz/circle__c4.json)).

## Review stop 3: first fit, measured cylinder `dielTM_dec8f`, 18 November 2026

Default method, all eight frequencies, ladder 1; 1–2; 1–3; 1–4 GHz then
1–8 GHz, recovered contrast (weak start 1.093 at 1 GHz), no noise level,
1e-9, 13,412 units. Run from the checkout with `solvers/bem_inverse/` clean (GPU table
path `3612f5195` committed); recorded HEAD `67c556a09` (GPU), `a9a945799` (CPU). Command:
`csi_fit.py --case dielTM_dec8f --device cuda|cpu --out results/bem/baseline_data/csi_adapter/2026-11-18/first_fit`.

**Bug fix.** Both passes returned their fits, then the wrapper's record step
failed (it read a stage key `label`; the key is `stage`). The fits were not
affected; `fit.json` and the runner's `local/` files were saved. The fixed
record step rebuilt `metrics.json` from `fit.json` with no refit. The first
write is kept as `metrics_first_write.json`.

| | GPU (reported) | CPU cross-check |
|---|---|---|
| Outcome | `COMPLETED_SCHEDULE` | `TRIAL_WALL_LIMIT` (the 120 s limit) |
| Last stage | `full_6_M37`, frontier adds none | `ladder_2_real` (1–2 GHz), 3 steps in |
| Work units | 894 | 245 |
| Fit time | 1403 s (stage `full_1_M11`: 1138 s) | 134 s |
| Peak memory | 1.9 GB host, 0.8 GB GPU | 0.7 GB |
| Fitted centre | (3.0, 29.2) mm | (2.5, 30.8) mm |
| Equivalent radius | 19.0 mm | 18.2 mm |
| Permittivity | 2.19 | 2.08 |
| Area error vs nominal | 67.8% (missing 3.3%, excess 64.5%) | 84.0% |
| Centre offset vs nominal | 3.1 mm | 2.6 mm |

The CPU pass stopped on its wall limit, not on a numerical failure:
`TRIAL_WALL_LIMIT`, "hard wall limit", after 133.7 s (the check runs between
batches). The two passes agree where both ran: ladder 1 loss 0.0909415672 on
both, contrast 1.73128476 on both (difference 6e-9). The only difference is the
planned stop. Timings are indicative: about 23 of 24 cores were busy, and
the GPU pass used four frequency threads.

Residual per frequency, ‖forward − data‖ / ‖data‖:

| GHz | GPU fit, final curve | Nominal truth (stop 2) |
|---|---|---|
| 1 | 44.5% | 47.8% |
| 2 | 33.3% | 23.1% |
| 3 | 34.7% | 24.5% |
| 4 | 33.2% | 27.7% |
| 5 | 42.3% | 30.5% |
| 6 | 40.0% | 33.9% |
| 7 | 45.9% | 37.1% |
| 8 | 50.4% | 40.4% |

The fit lands near the nominal cylinder (centre within 3.1 mm), but larger
and with lower permittivity: the usual size–contrast trade-off. Its residual
is higher than the nominal truth's at 2–8 GHz, so it stopped in a worse
minimum than the nominal cylinder. Every stage after `full_1_M11` accepted no
step. The fit used no truth; scoring ran after it returned, with the unedited
`experiments/comparison/scoring.py`. Item 5 of the coordinator's list (an
exact-series circle fit to the data) was not run, because the fit landed near
the nominal position.

Evidence: [GPU metrics](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cuda/attempt_01/metrics.json),
[CPU metrics](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/first_fit/dielTM_dec8f/cpu/attempt_01/metrics.json);
`fit.json`, `manifest.json` and `local/` sit beside them.

### Information only: do the data support the nominal cylinder?

Asked by the coordinator after stop 3. Data and exact series only, never fed
to a fit. CPU, one thread, 4 s. Script
[csi_cylinder_info.py](../../../../experiments/bem_on_baseline_data/csi_cylinder_info.py);
evidence [cylinder_info.json](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json).
Loss is the fit's: each frequency divided by its data norm, equal weights,
half the mean squared relative residual.

| Circle (centre, radius, permittivity) | Loss | Residual per frequency 1–8 GHz, % |
|---|---|---|
| BEM GPU fit: (3.0, 29.2) mm, 19.0 mm, 2.19 | 0.0840 | 44.5 33.3 34.7 33.2 42.3 40.0 45.9 50.4 |
| Nominal: (0, 30) mm, 15 mm, 3 | 0.0579 | 47.8 23.1 24.5 27.7 30.5 33.9 37.1 40.4 |
| 15 mm, 3 at the fitted centre | 0.0502 | 47.8 21.4 21.7 25.2 27.4 31.2 33.1 36.8 |
| Least squares, from nominal | 0.0375 | 52.8 17.1 18.0 18.1 20.1 24.1 25.5 25.3 |
| Least squares, from the BEM fit | 0.0375 | same end point |

Both least-squares starts end at **(1.9, 26.2) mm, radius 15.3 mm,
permittivity 3.05**. So under our forward model the data do support a
cylinder of about the nominal size and permittivity, about 4 mm from the
nominal centre. Its loss is less than half the BEM fit's. A circle lies inside
the fit's shape space, so the BEM fit stopped in a worse local minimum; this is
not an adapter or data fault. At 1 GHz the best circle fits worse (52.8%) than
the BEM fit (44.5%): the 1 GHz data favour a larger, weaker scatterer.

GPU fit, stage by stage (from the saved stage receipts):

| Stage | GHz | Accepted steps | Equivalent radius | Permittivity | Centre (mm) | Loss at entry → end |
|---|---|---|---|---|---|---|
| `ladder_1_real` | 1 | 22 | 22.9 mm | 1.73 | (2.6, 34.1) | 0.228 → 0.0909 |
| `ladder_2_real` | 1–2 | 19 | 18.8 mm | 2.14 | (3.1, 29.8) | 0.108 → 0.0848 |
| `ladder_3_real` | 1–3 | 7 | 19.0 mm | 2.15 | (3.2, 30.1) | 0.082 → 0.0773 |
| `ladder_4_real` | 1–4 | 0 | 19.0 mm | 2.15 | (3.2, 30.1) | 0.0754 → 0.0754 |
| `full_1_M11` | 1–8 | 13 | 19.0 mm | 2.19 | (3.0, 29.2) | 0.0996 → 0.0841 |
| `full_2_M15` to `full_6_M37` | 1–8 | 0 each | 19.0 mm | 2.19 | (3.0, 29.2) | 0.0841 → 0.0840 |

The large, weak cylinder comes from the first stage. At 1 GHz alone (k times
radius about 0.3) the data fix mainly the product of size and contrast, and
the weak start (1.09) leads to 22.9 mm at 1.73. Later stages shrink it to
19 mm but never reach the 15 mm basin. From `ladder_4_real` on, the fit
accepts almost nothing. Its stages end normally, so the result stands as the
reported one (coordinator: no retune, no rerun).

## End-to-end check: simulated circle `circle__c4`, 1–3 GHz, 18 November 2026

Simulated dataset settings as above; truth used only by the check before
the fit and by scoring after it. Both passes started with BLAS on many
threads (before the thread fix), so their timings are indicative only.
Commands: `csi_fit.py --case circle__c4 --device cuda|cpu --out results/bem/baseline_data/csi_adapter/2026-11-18/end_to_end --checks .../adapter_checks_1to3ghz`.

| | GPU (reported) | CPU cross-check |
|---|---|---|
| Outcome | `COMPLETED_SCHEDULE` | `TRIAL_WALL_LIMIT` (120 s) |
| Last stage | `full_6_M37`, frontier adds none | `full_1_M11`, 7 steps in |
| Work units | 1993 | 158 |
| Fit time | 465 s | 120 s |
| Peak memory | 1.7 GB host, 0.8 GB GPU | 1.4 GB |
| Permittivity (true 4) | 4.0006 | 4.0007 |
| Equivalent radius (true 50 mm) | 50.007 mm | 50.005 mm |
| Centre offset | 0.010 mm | 0.010 mm |
| Area error | 1.18% (missing 0.58%, excess 0.61%) | 1.07% |
| Residual 1 / 2 / 3 GHz | 0.146 / 0.115 / 0.116% | 0.149 / 0.116 / 0.135% |

The fit's residual is at the level of the data's own error at 1–3 GHz
(the true circle's mismatch: 0.17 / 0.13 / 0.30%). The two passes agree where
both ran (ladder 1–3 losses equal to 1e-17; `full_1_M11` loss after 7 CPU
steps vs 22 GPU steps differs by 4e-11). Stages `full_4` to `full_6` ended
on their quotas (304 units each), as the default schedule allows. The path
runs end to end.

Evidence: [GPU metrics](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/end_to_end/circle__c4/cuda/attempt_01/metrics.json),
[CPU metrics](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/end_to_end/circle__c4/cpu/attempt_01/metrics.json).

## Hand-over to `bem-csi-run`

From the repository root. Each command is resumable: rerunning it skips
finished work. Nothing here changes the solver or the wrapper's logic.

```bash
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
R=results/bem/baseline_data/csi_cases
S=<shape>__c4          # circle, kite, peanut now; the other seven when their tables exist
```

1. Adapter check and forward check on the true shape, with the 1% rule at
   1–3 GHz (about 10 s, CPU, one thread). Exits non-zero if an adapter check
   fails. The file `$R/adapter_checks/$S.json` holds `summary.one_percent_rule`.

   ```bash
   $P experiments/bem_on_baseline_data/csi_forward_check.py --out $R/adapter_checks --cases $S
   ```

2. The fit on the GPU (reported pass, 1 h ceiling). It refuses to start
   unless step 1 passed for that shape.

   ```bash
   mkdir -p $R/logs
   setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cuda \
       > $R/logs/${S}_cuda.log 2>&1 < /dev/null &
   ```

   Optional CPU cross-check (stops at 120 s by design):
   `CUDA_VISIBLE_DEVICES= setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cpu > $R/logs/${S}_cpu.log 2>&1 < /dev/null &`

Outputs: `$R/$S/<device>/attempt_NN/` with `manifest.json` (settings, file
and row SHA-256, commit, solver clean or dirty), `fit.json`, `metrics.json`
(outcome, stages, units, time, peak memory, residual per frequency, scores)
and `local/` (the runner's accepted states).

Run notes:

- **Data:** simulated tables use 1, 2 and 3 GHz of the retained file
  (user decision); the measured cylinder uses all eight. This is set per
  dataset in `DATASETS`, never per case. Do not regenerate tables.
- **Threads:** the scripts now pin BLAS, OpenMP and torch to one thread
  (fixed 18 Nov). Earlier runs (cylinder, first circle) used many threads by
  mistake; only their timings are affected. The GPU pass also runs four
  frequency threads, as the default does.
- **Memory:** a fit starts only with 16.5 GB available, so that it leaves
  14.5 GB after its peak of about 2 GB host (0.8 GB GPU). A guard stops the fit
  below 14 GB and writes `guard_stop.json`. Run fits side by side only while
  each start still meets the 16.5 GB rule.
- **Restarts:** a finished case is skipped. A fit that returned but whose
  record failed is completed from `fit.json` without refitting. Any other
  unfinished attempt is kept and a fresh attempt starts from the start. No
  tuning reruns.
- **Commit** each run by path: `$R/$S`, `$R/adapter_checks/$S.json`, the log.
  NPZ files are git-ignored. Each fit's `local/` is about 3 MB.
- **Report a crash**; do not edit the wrapper or the solver.
- **Time:** the measured cylinder took 23 min on the GPU (eight
  frequencies, loaded machine). The CPU circle ran ladder 1–3 GHz in 21 s.
- The measured cylinder is done (`csi_adapter/2026-11-18/first_fit/`); it is
  not in the runner's list.
