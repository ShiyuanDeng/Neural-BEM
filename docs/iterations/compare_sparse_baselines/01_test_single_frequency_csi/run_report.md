# Native classical CSI on the 24-pair TG-002 data

Updated 2026-11-19T04:00:43Z. All four approved fits completed without failures.
The two clean runs were released by “checks passed, go”; the noisy pair
was released separately after the clean kite fit. No fit was rerun.

## Fixed settings

Pinned classical `CSI.m` at `73a64e1`, unchanged. One native back-propagation
start per case, no tuning, 2,048 iterations, 166 by 166 cells at 1.25 mm.
The solver receives `epsinv=[]`; truth is opened only for checks and scoring.

One real 0.5 GHz frequency, exactly 24 sealed source/receiver pairs.
Background permittivity 6, interior 24: the true relative susceptibility
is 3 and the true material ratio is 4. `n1d0` uses the frozen 1% draw 0.

## Scores

Area errors use the frozen signed-peak scoring path, without registration.
Material L2 uses real susceptibility on the shared 201 by 201 grid.
Field residual is the independent `native_predict` result over all 24
readings, divided by their observed norm, in native source units.
No gain or phase is fitted. Noisy residuals use the noisy observations.

| Case | Data | Area % at 0.5 | At 0.3 | At 0.7 | Material L2 | Field residual % | Wall s |
|---|---|---:|---:|---:|---:|---:|---:|
| circle__c4 | clean | 45.9455 | 44.0099 | 61.3256 | 0.8257722 | 24.0092 | 615.548 |
| kite__c4 | clean | 50.0675 | 38.0403 | 70.8261 | 0.6357027 | 12.4490 | 622.278 |
| circle__c4 | n1d0 | 45.5519 | 43.7198 | 61.0339 | 0.8255296 | 23.9848 | 611.885 |
| kite__c4 | n1d0 | 50.2917 | 37.9909 | 70.9716 | 0.6361037 | 12.5809 | 613.176 |

CSI’s own printed costs are separate quantities. The data cost uses its
optimised contrast sources; the independent residual predicts again from
the saved image. Small CSI data costs here coexist with larger field residuals.

| Case | Data | CSI data cost | CSI state cost | CSI total cost |
|---|---|---:|---:|---:|
| circle__c4 | clean | 1.59e-05 | 0.000941 | 0.00095648 |
| kite__c4 | clean | 1.4e-05 | 0.000462 | 0.00047644 |
| circle__c4 | n1d0 | 1.59e-05 | 0.00094 | 0.00095634 |
| kite__c4 | n1d0 | 1.42e-05 | 0.000471 | 0.00048473 |

## UTC times and resources

Times come from `date -u`. Fits ran sequentially, on CPU, with eight threads.
Before each launch: no MATLAB process, at least 32 GiB available.
This reserves 8 GiB for CSI, 8 GiB expected BEM growth and 16 GiB free.
Each MATLAB family ran inside a systemd user scope with `MemoryMax=8G`
and `MemorySwapMax=0`. There was no time stop. Memory peaks below are
sampled process-family RSS, not an exact kernel peak.

| Case | Data | Launch UTC | Finish UTC | Native CSI s | Peak RSS GiB |
|---|---|---|---|---:|---:|
| circle__c4 | clean | 03:14:34 | 03:24:49 | 610.310 | 1.600 |
| kite__c4 | clean | 03:25:57 | 03:36:19 | 616.837 | 1.595 |
| circle__c4 | n1d0 | 03:37:51 | 03:48:02 | 606.510 | 1.592 |
| kite__c4 | n1d0 | 03:49:03 | 03:59:16 | 608.240 | 1.584 |

Total fit wall time: 2462.887 s (0:41:02).
The first circle reached iteration 64 at 03:14:59 UTC: elapsed 24.950 s,
projected total 798.411 s and finish 03:27:52 UTC. This initial forecast
included configuration time. The actual circle finished at 03:24:49 UTC.
The forecast, each finish and each score push were sent to `w5:p1` with Herdr.

## Checks

Preparation checks passed: solver byte identity, memory threshold boundaries,
existing-MATLAB refusal, missing-check refusal, 24-reading normalisation
and cost-log parsing. `checks/launcher_preparation.json` records them.

The adapter’s true dual-cell circle image passed both scoring self-tests:
half-peak area error 0.689719%, material L2 0.0616660, field residual
0.642927675%. Re-running `native_predict` gave exactly the saved 24
predictions and adapter residual. See `checks/run_self_tests/check.json`.

Each fit’s output check found all 33 returned snapshots finite: iterations
64 through 2,048 and CSI’s duplicate final entry. The final snapshot equals
the final image, which equals the image used by the independent predictor.

## Saved BEM comparison

Copied from the two saved clean BEM score/fit files, without rerunning BEM.
`checks/bem_rows.json` includes their original paths and hashes.

| Case | Area % at 0.5 | Material L2 | Field residual % | Wall s |
|---|---:|---:|---:|---:|
| circle__c4 | 41.1077 | 0.5316405 | 0.1481 | 16.828 |
| kite__c4 | 327.0443 | 1.4633784 | 22.0062 | 99.026 |

For the clean circle, saved BEM has lower area, material and field errors.
For the clean kite, CSI has lower errors on all three measures.
For this one frozen noise draw, CSI’s half-peak area error changes by
-0.394 percentage points on circle and +0.224 points on kite.
The field residuals remain about 24% on circle and 12.5% on kite.

## Evidence and retained files

Raw root: `results/csi/native_tg002/2026-11-19/`. Each fit saves its score,
cost history, MATLAB log, resource samples, launch decision, timing, input
hashes, output checks and manifest. Compact `final_image.mat` and
`prediction.mat` are force-added to Git as requested by the coordinator.
Bulk `snapshots.mat` stays local with its size and SHA-256 in the manifest.

- circle__c4, clean: [score](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/score.json), [state](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/state.json), [manifest](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/manifest.json).
- kite__c4, clean: [score](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__clean/score.json), [state](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__clean/state.json), [manifest](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__clean/manifest.json).
- circle__c4, n1d0: [score](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__n1d0/score.json), [state](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__n1d0/state.json), [manifest](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__n1d0/manifest.json).
- kite__c4, n1d0: [score](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__n1d0/score.json), [state](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__n1d0/state.json), [manifest](../../../../results/csi/native_tg002/2026-11-19/fits/kite__c4__n1d0/manifest.json).

Owned code: `experiments/baselines/csi/native_tg002/fit.py`, `native_fit.m`,
and `score.py`. The adapter’s files, the pinned solver, frozen scoring
and BEM code were not edited by native-run.

Activity: compare_sparse_baselines/01_test_single_frequency_csi (runs), 2026-11-19
Runs: 4/4; wall time 0:41 (sum of fit wall times)
Result: circle__c4 clean: area 0.5/0.3/0.7 45.9455%/44.0099%/61.3256%; material 0.8257722; field 24.0092%; runtime 615.548 s
Result: kite__c4 clean: area 0.5/0.3/0.7 50.0675%/38.0403%/70.8261%; material 0.6357027; field 12.4490%; runtime 622.278 s
Result: circle__c4 n1d0: area 0.5/0.3/0.7 45.5519%/43.7198%/61.0339%; material 0.8255296; field 23.9848%; runtime 611.885 s
Result: kite__c4 n1d0: area 0.5/0.3/0.7 50.2917%/37.9909%/70.9716%; material 0.6361037; field 12.5809%; runtime 613.176 s
Failures: none; no retries or memory stops
Upstream patches: none
Changes to our code: native_tg002/fit.py, native_fit.m, score.py
New unknowns: cause of the large gap between CSI data cost and independent field residual
Proposed next activity: coordinator reviews the four-case comparison; no further fits started
