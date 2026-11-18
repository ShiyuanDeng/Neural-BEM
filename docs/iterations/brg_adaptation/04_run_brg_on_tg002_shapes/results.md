# Run BRG on TG-002 shapes: provisional baseline results

## State at handoff

Snapshot: **2026-11-18T00:18:36.687219+00:00**. The user requested a fresh-chat handoff while the
existing detached campaign continues. **Do not launch a second campaign,
rerun the pilot, stop these workers, or start any other experiment.** The
live state and receipts supersede the dated case snapshot below.

### Running process and controls

Repository: `/home/drdeng/Neural_SDF_BEM_AD_organised`, branch `organised`.
Current detached campaign supervisor: **PID 727204**. Its actual command is:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python /home/drdeng/Neural_SDF_BEM_AD_organised/experiments/baselines/brg/run_tg002.py --campaign
```

It was launched with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1` and the wrapper's `--campaign --detach` option. That
launch command is historical, **not a command to run again**. Each MATLAB
sets eight compute threads. The supervisor automatically starts the remaining
queue; it does not update this report or commit anything.

Live state: `results/brg/tg002_shapes/2026-11-17/campaign.json`.
Memory samples: `resources.jsonl` beside it. Supervisor output:
`local/launcher.log`; per-case supervisor output: `local/<case>_supervisor.log`.
Each case has `attempt_NN.json`, `summary.json`, `data_summary.json`,
`frequency_NNN.mat`, `final_residuals.json`, `metrics.json` and `fit.json`.
Its full MATLAB log and exact states/data are in that case's ignored `local/`.

The state field `status=ready_after_receipt_repair` is a stale label retained
when this supervisor resumed; **it does not mean the queue is idle**. Read
`active`, `pending`, `updated` and the process list. Normal queue exit writes
`complete` or `stopped`. `campaign.json` updates about every five seconds.
The current implementation allows at most three BRG workers and reserves
4 GiB estimated peak per worker, above a 14 GiB free-memory floor. This has
kept two BRG workers active alongside three CSI MATLAB fits.

Check progress without launching work:

```bash
ps -p 727204 -o pid,ppid,etime,args
cat results/brg/tg002_shapes/2026-11-17/campaign.json
tail -n 1 results/brg/tg002_shapes/2026-11-17/resources.jsonl
# For each active case from campaign.json:
tail -n 8 results/brg/tg002_shapes/2026-11-17/<case>/local/matlab_01.log
```

The original campaign clock started 17 November at 23:41:28 UTC. Its hard
four-hour deadline remains **18 November 03:41:28 UTC**, epoch
`1794973288.138983`; the receipt repair did not reset it. Each case has a
one-hour budget including data and scoring. No tuning rerun is authorized.
The 771.81-second asymmetric eta 4 pilot passed the 900-second rule, so the
remaining cases are already authorized to finish without another question.

**Stopping, only if explicitly requested or needed for the existing limits:**
first verify PID 727204 still names this supervisor, then `kill -TERM 727204`
to prevent further launches. Capture its live `active` list before doing so.
For each active case read `matlab_pid` from its latest attempt receipt and
verify its command contains `run_tg002_case`. Send `kill -TERM -- -<matlab_pid>`
to that MATLAB process group. Do not signal CSI or use a blanket MATLAB kill.
Leave the per-case Python supervisors alive so they save the partial score,
return code and manifest. Stopping only PID 727204 does **not** stop MATLAB.
Do not execute these stop instructions merely to perform this handoff.

### Case-by-case snapshot

| Case | State at the dated snapshot |
|---|---|
| asymmetric__c4 | Done, 37/37; raw area 0.27669129; max residual 0.89327664 |
| asymmetric__c0.5 | Done, 37/37; raw area 0.11053017; max residual 0.13360256 |
| circle__c0.5 | Done, 37/37; raw area 2.3469481e-08; max residual 1.0326396e-10 |
| circle__c4 | Done, 37/37; raw area 2.0352808e-06; max residual 4.8760568e-10 |
| kite__c0.5 | Done, 37/37; raw area 0.47527995; max residual 0.39012093 |
| kite__c4 | Done, 37/37; raw area 0.46463161; max residual 0.86158502 |
| peanut__c0.5 | Done, 37/37; raw area 0.11768157; max residual 0.11628799 |
| peanut__c4 | Running, 29/37 inverse states saved; MATLAB PID 738983 |
| star__c0.5 | Running, 8/37 inverse states saved; MATLAB PID 742423 |
| star__c4 | Waiting in the existing queue; no run started |
| c_shape__c0.5 | Waiting in the existing queue; no run started |
| c_shape__c4 | Waiting in the existing queue; no run started |
| hook__c0.5 | Waiting in the existing queue; no run started |
| hook__c4 | Waiting in the existing queue; no run started |
| cross__c0.5 | Waiting in the existing queue; no run started |
| cross__c4 | Waiting in the existing queue; no run started |
| cog__c0.5 | Waiting in the existing queue; no run started |
| cog__c4 | Waiting in the existing queue; no run started |
| aphex_twin__c0.5 | Waiting in the existing queue; no run started |
| aphex_twin__c4 | Waiting in the existing queue; no run started |

### Exact steps for the successor

1. Read this section, the approved plan and `campaign.json`; verify the live
   PID. Observe the existing launcher. Do not launch another copy or reset
   its deadline. If it has exited, first distinguish normal completion from
   an error using the state, `local/launcher.log`, case supervisor logs and
   latest attempt receipts. Keep failures and partial states.
2. The case runner already performs BRG data generation, all inverse
   frequencies, a BRG-only final-curve residual sweep, frozen-protocol scoring,
   figures and SHA-256 manifests. Reuse those outputs. After a batch finishes,
   confirm its receipt has `case_wall_seconds`, its status/return code, and
   the metrics. The launcher does not commit these automatically.
3. If a finished case lacks a score because only post-processing failed,
   preserve the failure log and run the command below once. It reads saved
   output and does no inversion or forward solve. Do not rerun existing
   scores merely for reassurance; their original timings should stay intact.

   ```bash
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python experiments/baselines/brg/score_tg002.py --case <case>
   ```

4. When the queue ends, check all 20 case receipts and scores. A completed
   case has 37 compact frequency records, 37 data files and exact state files
   in local/, and 37 final-curve residuals. Check finite saved curves/histories,
   log failures, elapsed caps and the memory reserve. Report any incomplete
   case as incomplete; do not silently reset budgets or launch tuning runs.
   A process crash, exhausted cap or unresolved wrapper failure needs a
   coordinator report, not a new unapproved solver change.
5. Run `python experiments/baselines/brg/report_tg002.py`. It reads receipts
   only and preserves this State at handoff section. Complete the results
   with actual completion dates, counts, raw area errors, max final-curve
   residuals, data/inverse/residual-check/scoring times, failures and observed
   overlap. Inspect the case figures. Keep every result labelled provisional.
   Do not perform a BEM check, BEM fit, solver edit or paper k=30 resume.
6. Commit and push each finished batch by explicit paths. Stage only its case
   folders and figures, this report, and `campaign.json`/`resources.jsonl`.
   Include any owned wrapper fix and provenance update. Use
   `git add <owned paths>` then `git commit -m "..." -- <same paths>` and
   `git push`; never a bare commit. At final completion commit remaining
   owned changes and confirm status. Keep roughly 5 MB per case and each
   committed file below 50 MB; local bulk remains ignored with commands and
   SHA-256, and report figures stay in this activity's figures/. Running journals may change immediately
   after a snapshot commit. Other agents' files must remain untouched.
7. End with the report block in `docs/iterations/coordinate_final_comparison.md`:
   activity/date, done/planned and wall time, one result line per case,
   failures/logs, upstream patches, own-code changes, unknowns and next step.
   No new branch/worktree, high-k redesign or BEM-side execution is authorized.

### Known wrapper issue and preserved evidence

The pilot's MATLAB run and scoring completed normally, then Python 3.10
rejected `hashlib.file_digest`. The campaign then hit a missing-timing key.
The small owned fix uses streaming SHA-256, writes timing before hashing and
handles a missing timing receipt. The pilot was **not numerically rerun**.
Its failed supervisor log is committed in
`asymmetric__c4/supervisor_failure.log`; its repaired elapsed time comes from
that failure log's final timestamp. The original deadline was preserved.
Source hashes before/after the fix are in `provenance.json`. Other runs now
write normal receipts. No upstream BRG patch was added in activity 04.

Initial commits: `ba82e75a9` (pilot/request/fix), `10958f916` (circle 0.5),
`3d76fccfb` (circle 4, asymmetric 0.5, kite 0.5). Later snapshot commits include
partial active-case evidence and are intentionally not claims of completion.
The shared checkout can contain CSI/coordinator changes: do not stage them.

### Open items across activities 01–04

- 01: the multi-component missing-L test remains unfixed; it is outside these single-component cases.
- 01: exact-fit zero-gradient SD division can produce NaN/MEX failure; retain public behavior and report recurrence, without a guard.
- 01: the shipped cavity's manufactured-source diagnostic was unsuitable; later wrappers use verified interior points, and the shipped run stays labelled as shipped.
- 02: the Figure 1 gap remains unexplained; curvature candidates agreed exactly, the coordinator accepted the lower rebuilt errors, and no more gap runs are authorized.
- 02: k=30 resumes remain deferred while CSI runs overnight; glider eta 0.33 already completed all 117 frequencies and all other cached data/states are retained.
- 02: cavity eta 2's k=30 finer-grid check is still deferred; glider eta 10's finer-grid check passed.
- 02: star/cavity are vector-recovered shapes with approximately 6e-4 / 2e-4 coordinate accuracy; absent private drivers prevent an exact paper reproduction claim.
- 02: the stopped no-limit glider alternative must not resume; its retained endpoint is k=12.75.
- 03: the accepted one-glider BEM fit ended at k=10 after refusing k=12; the five other paper BEM fits and all further solver work belong to the BEM side.
- 03: the default-path proof and full 17-file/options/test handover are accepted; no baseline-side repeat tests or solver edits are needed.
- 04: the detached provisional campaign is unfinished at this snapshot; finish reporting the existing queue within its original caps.
- 04: BEM-side frozen plane-wave TG-002 data do not yet exist here; the committed `data_request.json` is the generation contract.
- 04: when frozen data arrive, compare every field table and rerun only cases beyond max(1e-5, ten times measured BRG refinement error); preserve provisional records.
- 04: cross-solver forward qualification, BRG refinement checks in that qualification, and both BEM rows belong to the BEM side and were not executed here.
- All: timings overlap CSI/other MATLAB processes and are indicative; clean-machine timing remains for later ownership, with no new timing run authorized now.

## Status and ownership

Campaign started 2026-11-17T23:41:28.138975+00:00; 20/20 cases have saved scores.
Queue state: `complete`; last update 2026-11-18T02:33:43.178302+00:00.
Complete 37-frequency cases: 20/20.
All data and results here are **provisional BRG-forward data**. The BEM side
owns generating and freezing the shared plane-wave data. These are TG-002
shapes with BRG-style observations, not the sealed TG-002 measurements.
No BEM forward, BEM fit or solver edit was performed in this activity.

The old one-hour cap cut C-shape at contrast 0.5 during frequency 35;
34 frequency states were saved. The coordinator authorized a continuation
from that state as attempt 02 and completion of the six unstarted cases,
using new entry points with no time cutoff. The original queue and its
loaded files remain untouched. See the [continuation plan](continuation_plan.md).

Both first aphex_twin attempts failed before data generation because the
wrapper skipped its diagnostic-point fallback when an interior centroid
failed the clearance test. The coordinator approved a dense interior
search retaining clearance >0.01 and fresh attempts, with no BRG or data
rule change. See the [diagnostic-point fix plan](diagnostic_point_fix_plan.md).

The [approved plan](plan.md) records the pilot rule and all choices. The
[single data request](../../../../results/brg/tg002_shapes/2026-11-17/data_request.json)
contains the 37 exact k values, layouts, units, signs, eta values and all ten
true coefficient arrays with source and coefficient hashes. The BEM-side
cross-solver checks and inverse sections remain unexecuted here.

## Actual settings and scoring

Pinned upstream `bda24bddbf4562497280b671bc174ef891b47c6b`, approved patches
03/04, seven-argument RLA call. No new upstream patch. MATLAB R2026a,
8 compute threads per process, with concurrent CSI fits. Times are indicative.
Known eta 0.5 or 4, equal density, unit-amplitude plane waves, finite-radius
scattered fields, negative time convention and outgoing Hankel first kind.

37 frequencies preserve TG-002's 19 labels and add midpoints: exterior
k=0.834234519 to 8.342345186. Each has floor(10k) directions and receivers
on radius 10. One centred unit-disk start; lengths are divided by 65 mm.
Frozen target offsets and rotations remain. Data use 100 exterior points
per wavelength and inversion 70, with public resolution behavior.

The shipped curvature values 0.1 / minimum band 20, better-of-GN/SD,
Gaussian filter, 50 iterations and 1e-5 residual/update stops are unchanged.
No added zero-gradient guard or tuning run. Every inverse frequency saves
its curve, residual history, iterations, exit flag, time and exact state.

Scoring imports `experiments.comparison.scoring` protocol version 1 unchanged.
All components are retained; no alignment is fitted. Returned uniform-
parameter nodes define a Fourier interpolant without truncation or smoothing.
Coordinates return to the benchmark's 50 mm units; truth uses 16,384 samples,
with its existing 201-by-201 material grid and boundary scoring functions.
The table's area error is the raw symmetric-difference area divided by true
area (not percent). Signed susceptibility and known-contrast scores are saved.

Residuals are recomputed on the returned curve at its own saved resolution
for all 37 frequencies, using BRG's forward. The table gives their maximum,
not the history of curves from earlier frequencies. The unchanged clean
residual limit is 0.003; added midpoints are never passed as sealed labels.
This final-curve evaluation has its own time column. No BEM solve is involved.

## Results

| Case | State | Frequencies | Raw area error | Max final residual | Data s | Inverse s | Residual check s | Score s | Case wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| asymmetric__c4 | complete | 37/37 | 0.27669129 | 0.893277 | 19.79 | 717.43 | 25.92 | 2.47 | 771.81 |
| asymmetric__c0.5 | complete | 37/37 | 0.11053017 | 0.133603 | 20.99 | 386.54 | 20.33 | 2.32 | 436.54 |
| circle__c0.5 | complete | 37/37 | 2.3469481e-08 | 1.03264e-10 | 18.88 | 91.08 | 16.53 | 2.28 | 134.82 |
| circle__c4 | complete | 37/37 | 2.0352808e-06 | 4.87606e-10 | 18.19 | 58.54 | 18.51 | 2.15 | 103.57 |
| kite__c0.5 | complete | 37/37 | 0.47527995 | 0.390121 | 13.07 | 205.36 | 8.88 | 2.35 | 235.83 |
| kite__c4 | complete | 37/37 | 0.46463161 | 0.861585 | 13.12 | 739.62 | 10.54 | 2.32 | 771.82 |
| peanut__c0.5 | complete | 37/37 | 0.11768157 | 0.116288 | 15.86 | 491.09 | 15.21 | 2.17 | 530.36 |
| peanut__c4 | complete | 37/37 | 0.50390252 | 1.30272 | 15.69 | 682.95 | 20.67 | 2.38 | 728.08 |
| star__c0.5 | complete | 37/37 | 0.0025279893 | 2.80675e-05 | 30.05 | 265.72 | 32.25 | 2.27 | 336.76 |
| star__c4 | complete | 37/37 | 0.00039247399 | 3.11609e-06 | 30.22 | 744.63 | 33.56 | 2.38 | 817.77 |
| c_shape__c0.5 | complete | 37/37 | 0.052557715 | 0.0537632 | 31.10 | 5105.04 | 29.76 | 2.07 | 5633.83 |
| c_shape__c4 | complete | 37/37 | 0.44474779 | 0.891051 | 31.15 | 770.22 | 27.88 | 2.69 | 838.86 |
| hook__c0.5 | complete | 37/37 | 0.57706138 | 0.480827 | 29.53 | 1025.90 | 25.03 | 2.58 | 1089.86 |
| hook__c4 | complete | 37/37 | 0.52228048 | 0.940662 | 28.89 | 1035.14 | 27.85 | 2.57 | 1101.12 |
| cross__c0.5 | complete | 37/37 | 0.0009136554 | 2.39723e-06 | 21.61 | 626.03 | 20.59 | 2.11 | 676.93 |
| cross__c4 | complete | 37/37 | 0.24642363 | 0.81336 | 20.34 | 589.70 | 16.93 | 2.24 | 635.22 |
| cog__c0.5 | complete | 37/37 | 0.0023331311 | 2.53093e-05 | 21.37 | 378.10 | 21.50 | 1.96 | 428.02 |
| cog__c4 | complete | 37/37 | 0.00047943854 | 7.93098e-06 | 20.26 | 1532.68 | 22.18 | 1.99 | 1581.80 |
| aphex_twin__c0.5 | complete | 37/37 | 0.80147523 | 0.559174 | 18.11 | 435.28 | 13.05 | 2.11 | 479.97 |
| aphex_twin__c4 | complete | 37/37 | 0.89878857 | 0.979737 | 17.66 | 337.48 | 13.61 | 2.19 | 382.32 |

## Timed pilot and forecast

Asymmetric eta=4: data 19.79 s, inversion
717.43 s, final residual evaluation 25.92 s,
scoring/figure 2.47 s; complete case 771.81 s.
The pilot passes the 900-second continuation rule.
Twenty times its measured phase costs gives data 6.60 min,
inverse 239.14 min and residual checks
8.64 min; aggregate case wall forecast
257.27 min before parallelism. This is a one-shape estimate, not a
promise for thin strokes or deep concavities. No case is rerun to tune it.

Completed-case aggregate wall time: 295.25 min across 20 cases.

Elapsed from the original start through latest queue end: 172.25 min; ended 2026-11-18T02:33:43.178302+00:00.

Original capped queue ended 2026-11-18T01:34:01.795957+00:00: case failed or capped; review required. The authorized continuation has no time cutoff; its times are reporting targets. Failed-attempt and interrupted-frequency work remain in case wall time.

Memory: minimum observed available 15.10 GiB; maximum active BRG workers 2. The required reserve is 14 GB. Start/end CSI/MATLAB overlap is retained in each attempt.

## Frequency-ending rejection codes

Counts below read the existing MATLAB logs only. Geometry/filter ier 2 means curvature rejection; ier 1 means self-intersection. The public routine resets a rejected update to the old curve and replaces its code by iteration ier -5 when the residual does not decrease. The filter columns count the selected method at the last iteration of a frequency ending with exit -1. The ier -5 column counts final iteration codes. These overlap; they are not separate groups. Full GN/SD codes and log hashes are in each case's `rejection_counts.json`.

| Case | Logged frequencies | Final filter ier 2 | Final filter ier 1 | Final iteration ier -5 |
|---|---:|---:|---:|---:|
| asymmetric__c4 | 37 | 35 | 0 | 37 |
| asymmetric__c0.5 | 37 | 28 | 0 | 34 |
| circle__c0.5 | 37 | 0 | 0 | 6 |
| circle__c4 | 37 | 0 | 0 | 0 |
| kite__c0.5 | 37 | 37 | 0 | 37 |
| kite__c4 | 37 | 23 | 0 | 32 |
| peanut__c0.5 | 37 | 33 | 0 | 33 |
| peanut__c4 | 37 | 34 | 1 | 36 |
| star__c0.5 | 37 | 0 | 0 | 1 |
| star__c4 | 37 | 5 | 0 | 7 |
| c_shape__c0.5 | 37 | 20 | 0 | 25 |
| c_shape__c4 | 37 | 31 | 0 | 35 |
| hook__c0.5 | 37 | 25 | 0 | 30 |
| hook__c4 | 37 | 30 | 0 | 35 |
| cross__c0.5 | 37 | 13 | 0 | 13 |
| cross__c4 | 37 | 37 | 0 | 37 |
| cog__c0.5 | 37 | 18 | 0 | 21 |
| cog__c4 | 37 | 11 | 0 | 13 |
| aphex_twin__c0.5 | 37 | 30 | 0 | 34 |
| aphex_twin__c4 | 37 | 22 | 12 | 37 |

The coordinator identified curvature rejection as the reason stalled curves could no longer move. Kite at eta 0.5 stops moving after the first frequency's sixth iteration. Activity [05](../05_run_brg_without_curvature_limit/plan.md) is authorized to remove only the curvature limit, reuse these hashed data, and retain this shipped-limit row. Its queue starts only after this queue ends.

## Checks, failures and evidence

Saved-output checks cover 19/20 scored cases. They read existing curves and histories, file counts, receipts, logs and manifest sizes; no inversion or scoring was repeated. Each receipt is saved as `saved_output_check.json` beside its metrics.

No saved-output check failed.

- asymmetric__c4: maximum data-geometry resampling point error 1.66371e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/asymmetric__c4/metrics.json), [curve](figures/asymmetric__c4.png).
  Wrapper failure: Python 3.10 lacks hashlib.file_digest; MATLAB and scoring completed. Receipt repaired with streaming SHA-256; no numerical rerun. See `supervisor_failure.log` in this case folder.
- asymmetric__c0.5: maximum data-geometry resampling point error 1.66371e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/asymmetric__c0.5/metrics.json), [curve](figures/asymmetric__c0.5.png).
- circle__c0.5: maximum data-geometry resampling point error 1.81942e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/circle__c0.5/metrics.json), [curve](figures/circle__c0.5.png).
- circle__c4: maximum data-geometry resampling point error 1.81942e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/circle__c4/metrics.json), [curve](figures/circle__c4.png).
- kite__c0.5: maximum data-geometry resampling point error 1.80062e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/kite__c0.5/metrics.json), [curve](figures/kite__c0.5.png).
- kite__c4: maximum data-geometry resampling point error 1.80062e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/kite__c4/metrics.json), [curve](figures/kite__c4.png).
- peanut__c0.5: maximum data-geometry resampling point error 1.73888e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/peanut__c0.5/metrics.json), [curve](figures/peanut__c0.5.png).
- peanut__c4: maximum data-geometry resampling point error 1.73888e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/peanut__c4/metrics.json), [curve](figures/peanut__c4.png).
- star__c0.5: maximum data-geometry resampling point error 2.33477e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/star__c0.5/metrics.json), [curve](figures/star__c0.5.png).
- star__c4: maximum data-geometry resampling point error 2.33477e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/star__c4/metrics.json), [curve](figures/star__c4.png).
- c_shape__c0.5: maximum data-geometry resampling point error 2.13556e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/c_shape__c0.5/metrics.json), [curve](figures/c_shape__c0.5.png).
  Attempt 2026-11-18T00:25:34.696176+00:00: return code 124; TimeoutExpired(['/home/drdeng/miniconda3/envs/EMNerf/bin/python', '/home/drdeng/Neural_SDF_BEM_AD_organised/experiments/baselines/brg/score_tg002.py', '--case', 'c_shape__c0.5'], 1.9999738428741693); log `results/brg/tg002_shapes/2026-11-17/c_shape__c0.5/local/matlab_01.log`.
- c_shape__c4: maximum data-geometry resampling point error 2.13556e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/c_shape__c4/metrics.json), [curve](figures/c_shape__c4.png).
- hook__c0.5: maximum data-geometry resampling point error 2.14006e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/hook__c0.5/metrics.json), [curve](figures/hook__c0.5.png).
- hook__c4: maximum data-geometry resampling point error 2.14006e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/hook__c4/metrics.json), [curve](figures/hook__c4.png).
- cross__c0.5: maximum data-geometry resampling point error 2.0479e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/cross__c0.5/metrics.json), [curve](figures/cross__c0.5.png).
- cross__c4: maximum data-geometry resampling point error 2.0479e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/cross__c4/metrics.json), [curve](figures/cross__c4.png).
- cog__c0.5: maximum data-geometry resampling point error 2.40835e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/cog__c0.5/metrics.json), [curve](figures/cog__c0.5.png).
- cog__c4: maximum data-geometry resampling point error 2.40835e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/cog__c4/metrics.json), [curve](figures/cog__c4.png).
- aphex_twin__c0.5: maximum data-geometry resampling point error 2.45256e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/aphex_twin__c0.5/metrics.json), [curve](figures/aphex_twin__c0.5.png).
  Attempt 2026-11-18T02:09:11.638360+00:00: return code 1; ; log `results/brg/tg002_shapes/2026-11-17/aphex_twin__c0.5/local/matlab_01.log`.
- aphex_twin__c4: maximum data-geometry resampling point error 2.45256e-15 BRG units; [metrics](../../../../results/brg/tg002_shapes/2026-11-17/aphex_twin__c4/metrics.json), [curve](figures/aphex_twin__c4.png).
  Attempt 2026-11-18T02:09:16.642678+00:00: return code 1; ; log `results/brg/tg002_shapes/2026-11-17/aphex_twin__c4/local/matlab_01.log`.

The frozen-input geometry checks verify source hashes, agreement with the
benchmark's scene definitions, positive orientation, closure, simple curves,
nonzero speed and the 65 mm start. Data resampling errors are measured against
the exact coefficients at the public resampler's returned parameters.

Compact results are committed by batch. Bulk fields, continuation states and
logs remain ignored locally with reproduction commands and SHA-256 manifests.
See [campaign receipt](../../../../results/brg/tg002_shapes/2026-11-17/campaign.json)
and [geometry checks](../../../../results/brg/tg002_shapes/2026-11-17/geometry_checks.json).

## Frozen-data replacement and handoff

Frozen BEM-side observations do not yet exist and were not compared here.
The agreed relative complex-field tolerance is max(1e-5, ten times measured
BRG refinement error); refinement error above 1e-4 returns to the coordinator.
Compare every frequency after units/order/signs are matched. Rerun only cases
whose fields differ beyond that threshold. Preserve these provisional results.
Both BEM rows and cross-solver checks belong to the separate BEM coordinator.
Paper k=30 resumes remain deferred while CSI runs overnight.
