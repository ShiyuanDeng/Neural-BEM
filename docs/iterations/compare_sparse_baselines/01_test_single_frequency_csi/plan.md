# Test classical CSI on the native 24-pair data at 0.5 GHz

19 November 2026. Baseline coordinator: Claude, Herdr pane `w5:p1`.
Written before any run. Times are UTC.

## Question

How does classical CSI perform on the exact observations our BEM saw?
The saved ten-frequency CSI results used the denser Fresnel layout
(1,764 pairs per frequency). Native TG-002 has 24 fixed-offset pairs.
Background: [verify_baseline_claims.md](../../verify_baseline_claims.md).

## Settings

| Item | Value | Chosen by |
|---|---|---|
| Cases | `circle__c4`, then `kite__c4` | user |
| Data | sealed TG-002 real catalog, the 0.5 GHz column only, clean | user |
| Acquisition | 24 sources on the 0.30 m ring, one receiver 0.20 rad ahead of each | user (native) |
| Exterior | relative permittivity 6; interior 24 (ratio 4) | user |
| Preserved | source strength, phase convention after a declared conjugation, pair order | user |
| Method | pinned classical `CSI.m`, CC-CSI commit `73a64e1`, unchanged | user |
| Start | native back-propagation, one start per case | user |
| Tuning | none | user |
| Iterations | 2,048 | user |
| Inverse grid | 166 by 166 cells of 1.25 mm, as in the earlier CSI fits | coordinator, from the supervisor's proposal |
| Truth in the fit | none; `epsinv` is passed empty | coordinator |
| Optional | same two cases with the frozen 1% noise draw 0 | user, conditional |

The background wavenumber must equal the native one for permittivity 6.
The adapter may reach it through the native material argument or through
the exact equivalent frequency in vacuum. It records which. The forward
check decides whether the route is right.

## Comparisons

BEM's saved single-frequency clean controls, same 24 readings:
area error 41.11% on circle and 327.04% on kite.
[Circle](../../../results/bem/default_clean_uc_sf0.5/circle__c4/score.json) ·
[kite](../../../results/bem/default_clean_uc_sf0.5/kite__c4/score.json).
The BEM coordinator (`w4:p1`) owns the GPU and every BEM fit.

Reported per case: area error at half peak, sensitivity at 0.3 and 0.7,
material error, relative field residual over the 24 readings, runtime,
failures. Scoring uses the frozen
[scoring.py](../../../experiments/comparison/scoring.py), unchanged.

## Checks that must pass before any fit

1. Input hashes saved for the sealed files, the 24 readings, the CSI
   table and mask, `CSI.m` and both pinned checkouts.
2. Pair order matches exactly. Relative round-trip error of the 24
   readings below 1e-10 after undoing the declared conventions.
3. CSI scores exactly 24 readings: the mask, the data normaliser and the
   data residual each cover 24 entries.
4. FDFD agrees with the exact circle within 1% on the 24 scattered
   readings, with no fitted gain or phase. The pass applies to the
   1.25 mm operators that `CSI.m` receives. A 0.625 mm value is recorded
   as extra evidence.

If check 2 or 4 fails, the adapter agent sends the discrepancy to the
coordinator and all fits are held. The coordinator passes it to the user.

## Subagents

| Name | Pane | Model | Task | Difficulty |
|---|---|---|---|---|
| `native-adapter` | right of `w5:p1` | Codex `gpt-6.2-astra`, high | Acquisition adapter and the four checks | Hard: conventions, background, exact-circle check |
| `native-run` | below it | Codex `gpt-6.1-sol`, medium | Launcher, the fits, scoring, records | Run-mostly, with copy-and-adapt code |

Both run with full access (user, 19 November, asked for this launch).
Briefs: [adapter](brief_adapter.md) · [runs](brief_csi_run.md).
`native-run` may prepare its launcher and scoring while the checks run.
It launches no fit until the coordinator says the checks passed.

## Resource rules

- One MATLAB worker at a time, at most eight threads. No GPU use.
- 8 GiB limit for the MATLAB process family, enforced by the launcher.
- Before each launch read live memory. Launch only if
  `MemAvailable - 8 GiB - expected growth of other jobs >= 16 GiB`.
- Expected growth of other jobs: the figure the BEM coordinator gives.
  Until it answers, count each of its Python fit processes up to 4 GiB.
- The sample and the decision are saved with each launch.
- No stop on time. A memory-guard stop or a faulty run is a recorded
  failure. Failures are kept, committed and not silently rerun.

## Commands

Repository root. One command at a time, in this order.

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
RUN=results/csi/native_tg002/2026-11-19
export PYTHONPATH=solvers:.

# Assignment 1, native-adapter
$PY -m experiments.baselines.csi.native_tg002.inputs --case circle__c4 --data clean --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.inputs --case kite__c4   --data clean --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.check_table --case circle__c4 --data clean --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.check_table --case kite__c4   --data clean --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.check_forward --case circle__c4 --run-dir $RUN

# Assignment 2, native-run, only after the coordinator's go
$PY -m experiments.baselines.csi.native_tg002.fit   --case circle__c4 --data clean --iterations 2048 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.score --case circle__c4 --data clean --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.fit   --case kite__c4   --data clean --iterations 2048 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.score --case kite__c4   --data clean --run-dir $RUN

# Optional, only if both coordinators expect the paired results by 07:00
$PY -m experiments.baselines.csi.native_tg002.inputs --case circle__c4 --data n1d0 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.inputs --case kite__c4   --data n1d0 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.fit   --case circle__c4 --data n1d0 --iterations 2048 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.score --case circle__c4 --data n1d0 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.fit   --case kite__c4   --data n1d0 --iterations 2048 --run-dir $RUN
$PY -m experiments.baselines.csi.native_tg002.score --case kite__c4   --data n1d0 --run-dir $RUN
```

`fit` starts MATLAB detached, with a state file, so a chat restart does
not kill it. It reports elapsed time and the projected finish at
iteration 64.

## Run budget

| Step | MATLAB launches | Target |
|---|---|---|
| Table checks | 2 short | done by 04:15 |
| Forward check | 1, plus a 0.625 mm value; reruns only after a verified bug fix | done by 04:15 |
| Clean fits | 2, circle first | circle done by 05:00, kite by 05:45 |
| Scores and commits | none | by 06:15 |
| Optional noisy fits | 2 | decide at 05:45; finish by 07:00 |

At most four CSI fits tonight. Fit time on this data is unmeasured;
the iteration-64 forecast of the first fit sets the real schedule.
Targets are reports, not reasons to stop a run.

## Outputs

- Raw evidence: `results/csi/native_tg002/2026-11-19/`
  (`inputs/`, `checks/`, `fits/<case>__<data>/`, `logs/`).
- Code: `experiments/baselines/csi/native_tg002/`.
- Reports: `adapter_report.md`, `run_report.md` and `results.md` here.
- Each run is committed and pushed, failures included, by path. At most
  about 5 MB committed per run; bulk stays local with its SHA-256.

## Success

Two clean comparisons by 07:00, or a recorded reason why not. At
handoff, any running case is reported with its ETA.
