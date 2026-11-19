# Native CSI preparation and runs

Prepared 19 November 2026, UTC. Coordinator released the clean fits with
“checks passed, go” at 03:14 UTC. Circle launched at 03:14:34 UTC and finished at 03:24:49 UTC.
Kite follows after circle scoring, commit and push. No noisy fits are released.

The owned wrapper calls the byte-identical pinned `CSI.m`, passes `epsinv`
empty, keeps its native start, and requests 2,048 iterations. Its returned
64-step images are saved without patching upstream. The log supplies separate
CSI data and state costs. The independent final-image prediction supplies
the 24-reading native field residual.

The detached launcher uses `setsid nohup`, eight threads and CPU only.
A systemd user scope with `MemoryMax=8G` worked during preparation. The
launcher uses it when available, with a family RSS watcher as fallback.
There is no time stop. Existing output folders cannot be reused.

The BEM coordinator supplied 8 GiB expected growth. Therefore launch requires
32 GiB available and no process named MATLAB. The sample is saved before
launch. Input hashes, adapter check hashes, solver hash, resources, state,
iteration-64 forecast and output hashes are retained per fit.

Preparation checks passed: 31.99 GiB refusal, 32 GiB acceptance, refusal with
an existing MATLAB, missing-check refusal, 24-reading residual normalisation,
cost-log parsing, and pinned solver byte identity. A separate synthetic
circle image gave 0.8956% area error through the scoring path. This is a
smoke check; it does not replace either required adapter-fixture self-test.
Evidence: `results/csi/native_tg002/2026-11-19/checks/launcher_preparation.json`.

The required two self-tests are implemented in `score.py --self-test`.
They use the adapter's `truth_1.25mm.mat`, including its dual-cell average
image, without generating another truth raster. The area check requires
less than 2% error, allowing the inverse-grid sampling error. The prediction
check calls `native_predict` again and requires agreement with the adapter's
coarse residual and saved predictions within 1e-10 in sealed-field norm.
They passed at 03:13:47 UTC: half-peak area error 0.689719%, material L2
0.0616660, field residual 0.642927675%, and zero prediction difference
from the adapter. Evidence: `checks/run_self_tests/check.json`.

Additional preparation commands, with the plan's PY, RUN and PYTHONPATH:

```bash
$PY -m experiments.baselines.csi.native_tg002.score --run-dir $RUN --self-test
$PY -m experiments.baselines.csi.native_tg002.fit --case circle__c4 --data clean --run-dir $RUN --check-only
```

These commands start no inverse fit. The first uses one bounded MATLAB
configuration and prediction once the adapter checks have passed.

Saved BEM rows were copied without rerunning BEM to `checks/bem_rows.json`:

| Case | Area error | Material L2 | Field residual | Runtime seconds |
|---|---:|---:|---:|---:|
| circle__c4 | 0.4110773 | 0.5316405 | 0.001480697 | 16.8278 |
| kite__c4 | 3.2704430 | 1.4633784 | 0.220062010 | 99.0265 |

## Clean circle result

Launch 03:14:34 UTC; finish 03:24:49 UTC. All 2,048 iterations completed,
without failures. Wall time 615.548 s; native CSI time 610.310 s; sampled peak
process-family RSS 1.600 GiB, within the enforced 8 GiB scope.

| Area error at 0.5 | At 0.3 | At 0.7 | Material L2 | Native field residual |
|---:|---:|---:|---:|---:|
| 45.9455% | 44.0099% | 61.3256% | 0.8257722 | 24.0092% |

CSI's own printed final data cost is 1.59e-5; state cost is 9.41e-4.
They are separate from the independent field residual. The final image has
four half-peak components. No fitted registration or gain was used.

All 33 returned snapshots are finite (64 through 2,048, plus CSI's duplicate
final entry). The last snapshot equals the final image used by the predictor.
Bulk `snapshots.mat` stays local with its SHA-256 in the per-fit manifest.
[Score](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/score.json) ·
[State](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/state.json) ·
[Manifest](../../../../results/csi/native_tg002/2026-11-19/fits/circle__c4__clean/manifest.json).

Activity: compare_sparse_baselines/01_test_single_frequency_csi (runs), 2026-11-19
Runs: 1/2; wall time 0:10
Result: circle area 45.9455%, 44.0099%, 61.3256%; material 0.8257722; field 24.0092%; runtime 615.548 s
Failures: none; initial check-only correctly refused missing adapter check records
Upstream patches: none
Changes to our code: native_tg002/fit.py, native_fit.m, score.py
New unknowns: fit runtime and peak memory
Proposed next activity: run clean kite after circle commit and push
