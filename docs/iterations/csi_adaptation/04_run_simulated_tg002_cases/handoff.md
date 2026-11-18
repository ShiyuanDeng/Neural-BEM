**Superseded: read the [current CSI handoff](../05_run_simulated_tg002_cases_at_1_to_3_ghz/handoff.md); no CSI process is running and all further fits are held.**

# CSI campaign handoff

## State at handoff

Captured **2026-11-18T00:19:47.676302+00:00**. The coordinator requested saving work and a fresh
chat. **The detached campaign is still running. Do not launch a second
campaign and do not stop this one as part of the handoff.** No new work
was started for this handoff.

The running launcher regenerates this live `results.md` every 30 seconds.
This section is committed, but its working copy can be overwritten by
that writer. **Read the permanent [handoff.md](handoff.md) if this section
is missing.** The plan links that permanent note too. `git show
HEAD:docs/iterations/csi_adaptation/04_run_simulated_tg002_cases/results.md`
also reads the committed handoff. Never discard live changes to restore
an old report.

### Running process and controls

- Repository: `/home/drdeng/Neural_SDF_BEM_AD_organised`, branch `organised`.
- Actual launcher PID/session/group **708268**; do not confuse the exited
  `setsid` wrapper PID 708267 with the launcher.
- Command already running: `PYTHONPATH=solvers:. setsid nohup
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m
  experiments.baselines.csi.campaign`, output redirected to
  `results/csi/tg002/campaign_launcher.log`, stdin detached.
- Live state: `results/csi/tg002/2026-11-17_campaign/status.json`.
  `campaign.json` contains the PID, original command and budget; its
  `state` remains `starting` until exit, so use **status.json** for live state.
- Read-only checks: `ps -p 708268 -o pid,etime,args`; read `status.json`;
  `tail -n 5 results/csi/tg002/campaign_launcher.log`; read each case's
  `matlab.log` for the last numerical iteration. Read `snapshot_scores.csv`
  or per-case `scores.json` for available scores.
- Stop **only if instructed**: create
  `results/csi/tg002/2026-11-17_campaign/STOP`, or `kill -TERM 708268`.
  The launcher stops only its own MATLAB workers, scores retained raw
  snapshots and commits/pushes the partial batch. Do not kill individual
  workers or other agents' MATLAB jobs to perform an ordinary stop.
- Current source: `experiments/baselines/csi/campaign.py`; each MATLAB fit
  has its own detached session. No background watcher from the chat is
  needed; the read-only chat watcher was ended, not the campaign.

### Batch and time status

Start: **17 November 2026 23:16:53.629 UTC**. Nine-hour deadline:
**18 November 2026 08:16:53.629 UTC**. Budget includes campaign data
preparation. Current live state at capture: `running`, batch 1.

| Case in batch 1 | MATLAB PID | Iteration at capture | Saved/scored snapshots |
|---|---:|---:|---|
| circle | 709974 | 864 | 256,512 |
| kite | 709985 | 869 | 256,512 |
| peanut | 710618 | 866 | 256,512 |

Batch 1 is circle, kite, peanut. All three first-opus data files are
already generated and hashed; circle reuses the exact activity-03 file.
Batch 2 (star,asymmetric,c_shape), batch 3 (hook,cross,cog), and batch 4
(aphex_twin) are **waiting**. Their data/fit jobs have not started.
All fits keep 2048 iterations; none is shortened from snapshot behavior.

At 512 iterations, native elapsed seconds were 2146.683 (circle),
2136.472 (kite), 2137.732 (peanut): about **4.17-4.19 s/iteration** with
three fits together, versus the single-probe 3.441 s/iteration. These are
partial observations, not the required completed-batch forecast.
Provisional batch-1 finish is **01:45-02:00 UTC on 18 November**.
If current rates persist, later hypothetical batch finishes are about
04:15-04:30, 06:45-07:00, and 09:15-09:30 UTC; those are estimates,
**not permission to pass the deadline or a promise those batches launch**.
The old 7.96 h forecast was from the one-case probe and is superseded by
actual concurrent measurements once batch 1 finishes.

Available memory at capture: 21.47 GiB.
The campaign guard uses **MemAvailable >=14 GiB** (free/reclaimable RAM),
not the unused-only MemFree figure, which it also logs. Native descendants
and other MATLAB jobs are monitored. On reserve failure it stops its newest
fit, preserves that failure and reduces its worker limit to two. It does
not touch BRG jobs. Overlap is in `overlap.jsonl`; times are indicative.

### What happens automatically and what the successor must do

1. **Observe the existing launcher.** Do not rerun its command. There is
   no resume CLI; rerunning it against its existing root is unsafe. If it
   exits awaiting a decision, inspect the reason before implementing any
   coordinated resume of the remaining cases; never rerun finished fits.
2. At 256,512,1024,2048, the owned copy writes the native raw last-frequency
   contrast atomically to each `final_contrast.mat`, preserving earlier
   snapshots. Real contrast is common to all eight frequencies; reference
   frequency is 8 GHz. No native display mask, fitted shift or rotation.
3. The launcher scores new snapshots automatically via imports of frozen
   `support_rings`, `region`, `region_scores` in
   `experiments/comparison/scoring.py`. Half the signed peak is primary;
   0.3/0.7 sensitivities are saved too. Mean contrast is epsilon_r = 1+chi;
   contrast error is `abs(mean_epsilon_r/4-1)`. All components/holes count.
4. After each case finishes, check `outcome.json`, `launch.json` return code,
   `matlab_summary.json`, all four raw counts and finite arrays, cost CSV,
   source/data hashes and per-case manifest. The MATLAB wrapper checks exact
   final raw-array equality with its 2048 checkpoint. A failed case remains
   recorded and the controller continues; do not tune settings to fix it.
5. **After batch 1 the full timing check still MUST be made.** The launcher
   writes `first_batch_forecast.json`: elapsed campaign time plus three
   remaining batches at the slowest completed first-batch wall time plus
   seven 43-second forward generations. Read the completed native
   seconds/2048 for each case and the observed three-fit overlap too.
   If the whole-campaign forecast exceeds **9 h**, the launcher publishes
   the batch and exits `awaiting coordinator`. Tell the coordinator then;
   do not launch more cases, change threads/grid/settings, or shorten runs
   yourself. The completed first-batch check has **not** yet happened.
6. After every batch the launcher regenerates the snapshot table in
   `results.md` and `snapshot_scores.csv`, adds a raw-image batch figure,
   writes cost histories/manifests, compresses native logs, and commits and
   pushes named owned paths. Check the push actually succeeded and that
   every finished case has an outcome, full 2048 table entry or preserved
   failure, plus all available early scores. Add a short interpretation,
   failures, overlap and actual timings to the report after automatic
   writes finish; preserve this permanent handoff note.
7. At the end or a stop, check `campaign.json` finished state, `status.json`,
   launcher exit, worker exits and final Git push. The launcher publishes
   its final state too. Write the final report block from
   `docs/iterations/coordinate_final_comparison.md`. Do not mark all ten
   done if only a batch finished or a budget hold remains.
8. If publishing or the launcher fails, read `launcher_failure.txt` and
   `campaign_launcher.log`, keep every output, score existing snapshots,
   and commit/push owned evidence manually. Do not restart a second campaign
   as a substitute for reading its state. Never stop a healthy launcher
   solely to make Git clean.

Exact manual publication form (only if needed, after checking current
writers): `git add <CSI paths>` then `git commit -m "..." -- <same CSI
paths>`, followed by `git push` and scoped `git status`. Allowed paths are
`docs/iterations/csi_adaptation/`, `experiments/baselines/csi/`, `results/csi/`,
`external/patches/cc-csi/`. No bare commit, branch/worktree, solver edit,
comparison edit, cleanup or other-agent staging. The checkout is shared;
foreign BRG/coordinator changes must remain untouched.

### Evidence, environment and storage

Use `/home/drdeng/miniconda3/envs/EMNerf/bin/python` with
`PYTHONPATH=solvers:.` for scoring/imports; system Python lacks Shapely.
MATLAB R2026a uses online licensing and needs network access. Wrappers set
8 threads because its fresh default is one. MaxwellFDFD's existing link
and the shipped `DGradient.mexa64` work. No path patch was required.

`handoff_state.json` records this capture. Per-case `handoff_manifest.json`
hashes current compact/local files; hashes of live append-only files are
point-in-time, while data files remain frozen. Full workspaces, material
maps, seven-column inputs and native uncompressed logs are git-ignored.
Their exact paths/hashes are in data JSON and manifests. Keep them local
for the BEM side; do not regenerate nominally equivalent inputs or delete
previously pushed bulk evidence. Compact raw arrays, costs, resources,
logs and JSON stay near 5 MB per run/batch. Figures go under this activity's
`figures/`, because `/results/**/*.png` is ignored.

At this handoff, the first 256/512 snapshots and scored table have already
been committed and pushed as `35795d15d`. The running launcher will create
normal live modifications after any commit. The permanent note and
cross-activity status addenda are committed separately.

### Open items across activities 01-04

- MR-CSI does not match Figure 5's measured speckled failure; activity-02 reading found no proven cause, so do not tune it.
- Measured-cylinder centre is nominal (0,+30) mm from an approximately specified displacement; exact surveyed coordinates remain unavailable.
- Measured-cylinder registered area error (~35% for CC), support-area bias (+4.2%), vertical offset (~3.6 mm) and full centroid distance (4.108 mm) must stay separate; no fitted registration.
- The introduction's unlabelled setup does not uniquely establish a Cartesian frame alone; activity-03 frame.md records the additional same-file primary sign evidence and limits.
- Companion-paper first-opus radii are reversed relative to shipped CC-CSI; keep shipped 0.72/0.76 m, do not silently import the companion settings.
- Second-opus radius discrepancy 1.8140695 m versus paper 1.67 m remains a documented discrepancy; the coordinator keeps shipped values and table C does not use it.
- BEM must independently cross-check every simulated true shape against the exact retained data file/hash; none of those BEM checks has run in CSI work.
- Native FDFD matrix/residual checks passed, but independent physical/grid-convergence agreement is not established by those internal checks.
- The completed first-batch three-worker rate and nine-hour forecast remain pending; partial rates already suggest the old probe forecast was optimistic.
- Seven simulated cases are still waiting; their results and final 2048 scores do not yet exist.
- Isolated final-comparison timings and actual three-fit scaling are still unqualified under changing BRG overlap.
- Final table-C success cut-off remains the coordinator's call; protocol-1 image threshold is fixed, but no new pass/fail cut-off is chosen here.
- The activity-01 Python launcher's SIGTERM cause is unknown; its MATLAB child completed both paper methods without a rerun, and native times are retained.

Closed choices that must not be reopened silently: susceptibility -0.5
(contrast 0.5) is excluded; only MF-CC-CSI runs on ten contrast-4 shapes;
all use the common 166-by-166 grid, 1.25 mm cells, 2048 iterations and
back-propagation start. The 1024 measured snapshot missed both 1% tests,
so the chosen stability count was 2048. Upstream compatibility patches
0001/0002 remain; patch 0003 is output-only in an owned renamed copy and
is not applied to the external upstream function.
