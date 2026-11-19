# Native CSI preparation and runs

Prepared 19 November 2026, UTC. No CSI fit has started. The coordinator's
exact release, “checks passed, go”, is still required before invoking fit.

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
They await the adapter's passed forward check and fixture.

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

Activity: compare_sparse_baselines/01_test_single_frequency_csi (runs), 2026-11-19
Runs: 0/2; wall time 0:00
Result: preparation checks passed; required truth-fixture self-tests pending; BEM rows copied
Failures: no fit attempted; initial check-only correctly refused missing adapter check records
Upstream patches: none
Changes to our code: native_tg002/fit.py, native_fit.m, score.py
New unknowns: adapter forward-check result; fit runtime and peak memory
Proposed next activity: finish the two fixture self-tests, then wait for “checks passed, go”
