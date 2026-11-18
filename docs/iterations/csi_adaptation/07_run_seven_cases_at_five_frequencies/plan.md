# Run seven cases at five frequencies

Prepared 18 November 2026, 03:51 UTC (system clock: `date -u`).
No fit is authorized until the coordinator's explicit go for step 2.

## Questions and user choices

Measure MF-CC-CSI recovery on the seven remaining TG-002 shapes using
exactly the frozen five-frequency observations shared with our BEM.
The user chose 0.5, 1, 1.5, 2 and 2.5 GHz on 18 November at 03:43 UTC.
Shapes, in queue order: star, asymmetric, c_shape, hook, cross, cog,
aphex_twin. Circle, kite and peanut keep their separate eight-frequency
fits; they are never rerun or edited here. This replaces activity 05's hold.

## Settings and comparisons

MF-CC-CSI only; 2048 iterations; snapshots at 256, 512, 1024 and final
2048; 166 by 166 inverse cells at 1.25 mm; native back-propagation;
one centred start; eight compute threads. No numerical upstream change.
Native conductivity scaling refers to 0.5 GHz; saved images to 2.5 GHz.
Truth enters scoring only. Reuse protocol 1: half the signed peak for the
main score, 0.3 and 0.7 of the peak for sensitivity. Report symmetric
area error over true area, mean permittivity versus 4, centre error,
iteration costs and both native and shared-machine wall time.
Comparisons with BEM belong to the coordinator; no BEM work here.

## Frozen observations and release rule

Read only:
`results/csi/tg002/2026-11-18_five_frequency_data/<shape>/forward/synthetic_input.txt`.
Verify its adjacent `synthetic_input.txt.sha256`, 8820 finite seven-column
rows, five ascending frequencies for each of 1764 source–receiver pairs,
36 sources and 49 receivers each. Never generate, move or write a table.
Pin the verified hash in each coordinator release and recheck before launch.
Read truth from the kept eight-frequency parent, checking the frozen
geometry hash when copying it into the new result folder.

The coordinator releases each shape only after freezing and all data
checks pass: unchanged-generator 1/2 GHz agreement within 1e-9 relative;
circle exact series within 1% at every frequency; BEM true-shape forward
within 1% at every frequency. A table's existence alone cannot release it.
An initially empty release queue remains open for additions while running.

## Budget, process control and success

Seven fits maximum, with no retries or image restart. A resume preserves
all launches and outcomes; interrupted snapshots remain as failed evidence.
Re-read `results/csi/resource_policy.json` before every fit launch and use
its nonnegative integer `max_csi_fits`; missing file means 3. A lower
ceiling delays new launches and never stops a running fit. Invalid policy
blocks launches and is reported. Keep the 14 GiB available-memory floor
and reserve each fit's expected 6.6 GiB peak before starting it.
Urgent memory protection may stop the newest owned fit and preserves it.
Never touch a BEM or BRG process. STOP or an explicit controller signal
stops owned workers and preserves available evidence.

The old shared-machine eight-frequency rate was 4.74 seconds/iteration.
A five-hour total is an estimate and informational target only; no time
figure stops a fit. Measure seconds per iteration around iteration 100,
excluding startup. Complete every released fit unless faulty or explicitly
stopped. Score, write results and commit/push after each outcome, failures
included. Keep new committed evidence below about 5 MB per fit; bulk
stays ignored with hashes. Confirm the push and scoped git status.

Success means seven preserved outcomes at the unchanged 2048-iteration
settings, valid finite raw checkpoints and hashes, all three threshold
scores, measured timings and a report. Poor recovery is reported, not
changed by tuning. A failed data/driver check is reported before any fit.

## Step 1 checks without a fit

Check the native driver and ReadFreData using source inspection and
small MATLAB array checks: five allocated frequency/initial-field blocks,
column-3 equality selection at half-integers, correct 36-source initial
blocks, first-frequency conductivity scaling, last-frequency image
reference. Check the output-only numerical copy against upstream.
Exercise the queue, changing worker ceiling, STOP and resume in temporary
folders with mocked workers; never call the generator or fit during checks.
Run the real launcher only with `--dry-run` before the go.

## Commands and evidence

From the repository root, after the coordinator's go:

```bash
mkdir -p results/csi/tg002/2026-11-18_five_frequency
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 setsid nohup /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_five_frequency >results/csi/tg002/2026-11-18_five_frequency/campaign_launcher.log 2>&1 </dev/null &
```

Release one checked shape (coordinator action; repeat as checks pass):

```bash
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_five_frequency --release star
```

Resume adds `--resume` to the detached launch command. The launcher refuses
live same-campaign workers and preserves STOP; it never removes that file.
An explicit STOP is `touch results/csi/tg002/2026-11-18_five_frequency/STOP`.

Results root: `results/csi/tg002/2026-11-18_five_frequency/`.
State: `campaign.json`, `status.json`, `releases.json`, `overlap.jsonl`;
per case: frozen-input metadata, exact driver, checkpoints, scores,
logs, costs, resources, outcome and SHA-256 manifest. No table subset is
written because both methods read the same full five-frequency file.
Report: this activity's `results.md`; report images: `figures/`.
Check evidence: `checks.md` and result-root `checks/`.
Old launchers remain unlaunched. Edit only activity 07, CSI-owned launcher
files, CSI results outside the data folder, and CSI patches if needed.

## Coordinator go and delegated releases, 18 November 04:00 UTC

The coordinator gave GO to launch with the empty queue and delegated
per-shape releases to CSI. Launcher PID 977035 started at 04:00:52 UTC.
Every minute the separate watcher checks the frozen manifest, passed data
checks and matching sidecar hash, then the BEM adapter check's matching
`frozen_sha256_verified`, true `summary.one_percent_rule`, and all five
`mismatch.per_frequency` values at or below 1%. BEM files are read only.
Missing checks mean wait; a failed check blocks that shape and is reported
immediately. Releases record UTC, shape, table hash and all three check
values in `releases.jsonl` and `releases.md` in this activity.

The circle exact-series check has passed at the five frequencies:
0.44%, 0.17%, 0.13%, 0.13%, 0.18% (coordinator-supplied values).
This does not release any of the seven shapes by itself.
The watcher's background loop checks the launcher PID and status file,
reports iteration timings and outcomes, and never stops a fit on time.
