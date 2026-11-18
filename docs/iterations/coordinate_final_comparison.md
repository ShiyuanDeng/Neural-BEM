# Coordinate the final comparison

Read the [short report on the results and their limits](final_comparison_report.md).

This document tracks four methods toward one final comparison: our BEM
inverse, GauGal, BRG and the CSI family. For each method it states the
settings, assumptions and unknowns, and it sets how subagents share the work.

The coordinator (the main session) owns this file. Subagents never edit it.
They report back, and the coordinator updates the status board and the cards.

Last updated: 18 November 2026, 12:05 UTC (a ten-frequency MF-CC-CSI pass
is running on all ten shapes, launched 11:57 UTC; the five-frequency pass
is complete and stays as reported).

## Restart notes (18 November 2026, 03:55 UTC)

Start here after a restart. The user clears the coordinator's chat and the
agents' chats when contexts grow long: on 18 November at 00:25 UTC and
again at about 03:40 UTC.

**State in one look.**
- The user set the band for the simulated CSI cases (table C): 0.5, 1,
  1.5, 2 and 2.5 GHz. The hold on CSI fits is lifted.
- The five-frequency pass is complete (07:47 UTC): data frozen and
  checked for all ten shapes, ten BEM fits, seven MF-CC-CSI fits, no
  failure. Numbers: "Table C, simulated shapes: the numbers" below.
- **Running now: MF-CC-CSI at ten frequencies** (0.25 to 2.5 GHz in
  0.25 GHz steps) on all ten shapes. Detached launcher PID 1227833,
  started 11:57 UTC: **already running, do not relaunch**. See
  "Ten-frequency run" below.
- No agent pane is open: `csi`, `csi-data` and `bem-watch` are closed.
  The coordinator runs this launcher itself.
- BRG: both 20-case rows on the TG-002 shapes are complete. The `brg` pane
  is closed.
- BEM side: every BEM table is filled (B1 40 fits, B2, C measured, C
  simulated). Nothing runs on the BEM side since 05:34 UTC. State:
  [coordinate_bem_side.md](coordinate_bem_side.md).

**Ten-frequency run (opened 18 November, 11:55 UTC).**
- Why: the user asked the BEM coordinator why the BEM outlines on the
  simulated CSI cases are wiggly, suspecting five frequencies are too
  few. The BEM side tested ten frequencies. On CSI the user wrote in the
  BEM coordinator's pane, 11:14 UTC: "0.25-2.5 with 0.25 steps yes. bem
  only for now. after you are done you can talk to baseline side
  coordinator and brief him to do csi fit." The BEM coordinator passed
  this on at about 11:50 UTC; the coordinator read the words itself in
  that session's record.
- What the BEM side found (its "Wiggle check" in
  [coordinate_bem_side.md](coordinate_bem_side.md)): the wiggles come
  mainly from the 0.1 to 0.7% grid error of the simulated tables, which
  the fit follows; ten frequencies help in part.
- Data: `results/csi/tg002/2026-11-18_ten_frequency_data/<shape>/forward/synthetic_input.txt`
  with a `.sha256` file, 17,640 rows, made by the BEM side with the
  unchanged generator. This side now owns the folder. Keep it frozen.
- Checks done before any fit (11:56 UTC,
  `results/csi/tg002/2026-11-18_ten_frequency/checks/table_checks.json`):
  hashes match; the rows of the five old frequencies are byte-equal to the
  five-frequency tables; circle against the exact series 0.13 to 0.44%;
  our forward on each true shape at most 0.71% (`aphex_twin`), on the same
  hashes. All ten pass the 1% rule.
- Plan: [08 plan](csi_adaptation/08_run_cases_at_ten_frequencies/plan.md)
  (`214c917a1`). Settings as in activity 07; only the frequency list, the
  tables and the three added shapes differ.
- Launcher: `experiments.baselines.csi.campaign_ten_frequency`, a copy of
  the five-frequency launcher. State in
  `results/csi/tg002/2026-11-18_ten_frequency/status.json`; live table in
  [progress.md](csi_adaptation/08_run_cases_at_ten_frequencies/progress.md);
  each fit is scored, committed and pushed by the launcher as it ends.
- All ten shapes are released, in this order: star, hook, circle, kite,
  asymmetric, cross, cog, c_shape, peanut, aphex_twin.
- How many run at once: the resource monitor's process has exited and
  left `results/csi/resource_policy.json` at zero. So the launcher reads
  its own `ceiling.json` (three) and starts a fit only if 14 + 2 GiB
  stays free after 8 GiB is reserved per fit. That allowed two fits at
  first and three from 12:04 UTC, when the BEM side's fits had ended.
- To cut the queue without stopping a fit: set `max_csi_fits` to 0 in
  that `ceiling.json`. The `STOP` file stops running fits too; do not
  use it unless the user says so.
- If the launcher dies: fits already running continue. Restart it with
  `--resume` (command in the plan); it never restarts a launched fit.
- Forecast, not a limit: about 2.5 to 3 h per fit; star and hook near
  14:45 UTC, the first four near 17:30, all ten near 22:30 with three at
  a time.
- After the run: write `results.md` and a figure for activity 08, fill
  "Table C, simulated shapes: ten frequencies" below, tell the BEM
  coordinator (`w2:p1`).

**The plan for the simulated cases of table C.** The user, 18 November
03:43 UTC, in this pane:

> Use [0.5, 1, 1.5, 2, 2.5] GHz for all ten C-simulated BEM cases and the
> remaining seven MF-CC-CSI cases. Prepare and freeze the missing-frequency
> data, and give the same observations to both methods.
>
> Relay this to the BEM coordinator. Queue preparation, checks and fits
> with the resource monitor; launch as capacity allows without
> interrupting existing fits. Keep the previous three CSI fits as separate
> eight-frequency results.

Then: "you are the coordinator, open subagents in split panes to monitor
the bem and csi run respectively. an extra pane with astra to prepare data
if needed."

This replaces the 1 to 3 GHz choice (00:55 UTC), the hold (01:36 UTC) and
the open question "1 to 4 or 1 to 5 GHz". A different list in any older
plan, handoff note or prompt box is history.

| Setting | Value | Set by |
|---|---|---|
| Frequencies | 0.5, 1, 1.5, 2 and 2.5 GHz, the same for both methods | User |
| Our BEM | All ten shapes at contrast 4, with recovered contrast | User |
| MF-CC-CSI | Seven shapes: star, asymmetric, c_shape, hook, cross, cog, aphex_twin | User |
| Circle, kite, peanut for CSI | Not rerun. Their fits at 1 to 8 GHz stay as a separate eight-frequency result | User |
| Observations | One frozen five-frequency table per shape. Both methods read the same file, proven by its SHA-256 | User |
| Missing data | 0.5, 1.5 and 2.5 GHz are generated with the unchanged generator (0.625 mm cells, same sources, receivers and mask) | User |
| Old tables and results | Kept as they are. Nothing is moved, replaced or regenerated | User |
| Launching | The resource monitor sets how many jobs run. No running fit is interrupted. No stop on time | User |
| 1 and 2 GHz rows | Copied byte for byte from the frozen eight-frequency tables | Coordinator |
| New data folder | `results/csi/tg002/2026-11-18_five_frequency_data/<shape>/forward/synthetic_input.txt`, with a `.sha256` file beside it | Coordinator |
| Row order | Per source–receiver pair, the five frequencies in rising order | Coordinator |
| CSI settings | Unchanged: 2048 iterations, snapshots at 256, 512 and 1024, the 166 × 166 grid at 1.25 mm, native start | As before |
| CSI results folder | `results/csi/tg002/2026-11-18_five_frequency/` | Coordinator |

**Checks before any fit** (coordinator):
1. The new driver also makes 1 and 2 GHz and matches the frozen rows to
   1e-9, relative. That shows the generator is unchanged.
2. The circle table against the exact series at all five frequencies:
   at most 1% at each. At 1 and 2 GHz it was 0.17% and 0.13%.
3. Our forward on each true shape (BEM side): at most 1% at each
   frequency.
- A shape above 1% is not fitted by either method. Ask the user.
- The new point is 0.5 GHz: the wavelength is 600 mm and their absorbing
  border is five cells thin. Checks 2 and 3 measure whether that matters.

**Order of work.** Data, then checks, then fits. The BEM side checks and
fits a shape as soon as its table is frozen. CSI launches a shape after
its table is frozen and checks 1 to 3 passed for it.

**Agents.** All in Herdr panes beside the coordinator (pane `w1:p1`).

| Name | Pane | Model | Job | Activity |
|---|---|---|---|---|
| `csi-data` | closed 07:48 UTC (was `w1:p9`) | Codex `gpt-6-astra`, high, full access | Done. It prepared, checked and froze the ten five-frequency tables. No fit | `csi_adaptation/06_prepare_five_frequency_data` |
| `csi` | closed 07:52 UTC (was `w1:p8`) | Codex `gpt-6.1-sol`, high, full access | Done. It launched and watched the seven MF-CC-CSI fits, scored and reported them | `csi_adaptation/07_run_seven_cases_at_five_frequencies` |
| `bem-watch` | closed 05:13 UTC (was `w1:pA`) | Codex `gpt-6.1-sol`, high | Done. It watched the BEM side's ten checks and ten fits, read only, and edited nothing | None |

- `csi` reads first: `AGENTS.md`, this file, then the
  [CSI handoff note](csi_adaptation/05_run_simulated_tg002_cases_at_1_to_3_ghz/handoff.md).
  That note's hold and its frequency question are answered by the plan
  above.
- Full access: the coordinator asked once at launch, and the user chose
  "Full access for both" for `csi-data` and `bem-watch` (03:55 UTC). That
  covers this launch only. A Codex pane started without the flag begins in
  the default sandbox, where MATLAB and git do not work.
- Each agent's brief is its first message in its pane. `csi-data` reports
  the circle's checks first, then "frozen" with the commit. `csi` reports
  "ready" with its launch command and waits for the coordinator's go.
  `bem-watch` reports when the BEM side's folder appears, when the ten
  checks are in, and when the ten fits are in.

**Peers.**
- The BEM coordinator, pane `w2:p1`, with `bem-csi-run` (`w2:p8`) for the
  simulated fits and `bem-b1` (`w2:p9`) for table B1. It owns every BEM
  fit and works from [coordinate_bem_side.md](coordinate_bem_side.md).
- The resource monitor, pane `w3:p1` (Codex, set up by the user about
  02:10 UTC). It allocates workers across both sides every 10 minutes,
  with a 14 GiB floor plus a 2 GiB margin. It sets how many jobs run, not
  what they compute. The coordinator adds no resource loop of its own.
  Its ceilings for new launches are in `results/csi/resource_policy.json`
  (first set 03:51 UTC, commit `c03ed283c`): one MATLAB data job, two
  MF-CC-CSI fits, one BEM GPU job across B1 and the simulated cases. The
  CSI launchers re-read the file before each launch. Its pane has no
  Herdr access, so it cannot send notices: read the file, and pass BEM
  ceilings on to the BEM coordinator.

**Progress** (update this list at each step):
- 03:50 UTC: plan recorded here and pushed (`f3c41d0a9`).
- 03:52 UTC: plan sent to the BEM coordinator and the resource monitor.
  `csi` briefed: prepare the launcher for the seven fits, then wait.
- 03:57 UTC: `csi-data` and `bem-watch` opened and briefed. `csi-data`
  starts with the circle.
- 03:58 UTC: `csi` ready (`3ebdc8344`): launcher
  `experiments.baselines.csi.campaign_five_frequency`, half-integer
  frequencies checked, no upstream change. The BEM side is ready too
  (`8975b1edb`): results in
  `results/bem/baseline_data/csi_five_frequency/2026-11-18/`, plan in
  [its activity 07](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md).
  Its 1% checks run on the CPU, about 10 s each.
- 04:00 UTC: circle table frozen (`81f232f15`). Against the exact series:
  0.44, 0.17, 0.13, 0.13 and 0.18% at 0.5, 1, 1.5, 2 and 2.5 GHz, all
  under 1%. The 1 and 2 GHz rows reproduce the old table exactly. The
  other nine follow one by one.
- 04:00 UTC: go to `csi`, with a standing rule: it releases each of its
  seven shapes itself once the table is frozen, its hash matches, and the
  BEM side's check file passes 1% at all five frequencies on the same
  hash. The BEM runner picks up each frozen table by itself as well.
- 04:05 UTC: all ten five-frequency tables frozen (`88007cc67`;
  [06 results](csi_adaptation/06_prepare_five_frequency_data/results.md),
  [data note](csi_adaptation/06_prepare_five_frequency_data/data_note.md)
  with paths and hashes). 303 s in all, no failure. Each table: 8820 rows,
  old pair order, 1 and 2 GHz rows byte-identical to the old table.
  `csi-data` is idle; its pane stays open until the fits are in, in case
  a data question comes up.
- 04:06 UTC: the BEM side's 1% check passes on all ten true shapes, on
  the same hashes. Worst mismatch at the five frequencies: `aphex_twin`
  0.71%; the other nine 0.21 to 0.44%. Files:
  `results/bem/baseline_data/csi_five_frequency/2026-11-18/adapter_checks/`.
- 04:03 to 04:05 UTC: `csi` released all seven shapes. Detached launcher
  PID 977035, **already running, do not relaunch**; state in
  `results/csi/tg002/2026-11-18_five_frequency/status.json`, stop file
  `STOP` there, `--resume` exists. `star` started 04:03 and `asymmetric`
  04:05; five wait for a slot.
- 04:05 UTC: the monitor's ceilings: no data job, two CSI fits, two BEM
  GPU jobs. The last B1 fit has ended.
- 05:05 UTC, CSI: three fits run (`star`, `asymmetric`, `c_shape`); the
  monitor raised the ceiling to three at about 04:10. Measured over the
  first 100 iterations: 2.19, 2.24 and 2.49 s per iteration. At 05:00
  `asymmetric` was at iteration 1380 of 2048. `hook`, `cross`, `cog` and
  `aphex_twin` wait for a slot. No failed or stopped fit.
- 05:10 UTC, BEM (read from its `metrics.json` files; the BEM coordinator
  reports them): all ten fits done, and all completed their schedule.
  Area error: circle 0.97%, asymmetric 1.29%, peanut 1.54%, cross 2.10%,
  star 2.34%, c_shape 2.60%, cog 2.86%, hook 3.59%, kite 3.80%,
  aphex_twin 5.96%. Contrast found 3.9970 to 4.0054. 47 to 247 s per fit.
- 05:12 UTC, same observations confirmed by `bem-watch`: every BEM check
  and fit read the frozen five-frequency file of its shape (path, SHA-256
  and frequency list in each `manifest.json` match the data note). Its
  pane is closed; the job is done.
- 05:12 UTC, from the BEM coordinator: table C's BEM text is updated
  (`4782d87dc`); ten CPU cross-checks still run on its side.
- 05:35 UTC, from the BEM coordinator (`983379bec`): its five-frequency
  pass is closed and every BEM table is filled. The CPU cross-checks match
  the GPU on every stage both finished.
- 07:35 UTC, CSI (read from
  [07 results](csi_adaptation/07_run_seven_cases_at_five_frequencies/results.md)
  and each `scores.json`): six fits completed all 2048 iterations, no
  failure, each scored and pushed by `csi`. Area error at half the peak,
  with our BEM on the same table in brackets: star 3.72% (2.34%),
  asymmetric 6.67% (1.29%), cog 13.29% (2.86%), cross 11.97% (2.10%),
  c_shape 16.03% (2.60%), hook 16.52% (3.59%). Mean permittivity found
  3.71 to 3.87 against 4. At 0.3 and 0.7 of the peak the area error is
  9.6 to 16.5% and 16.3 to 45.1%. 4750 to 5050 s per fit, three at once.
- 07:47 UTC, CSI: `aphex_twin` completed all 2048 iterations (started
  06:46, alone, 3655 s): area error 23.36% at half the peak (our BEM
  5.96%), 28.2% and 58.1% at 0.3 and 0.7, mean permittivity 3.51. All
  seven fits are in and pushed (`183559c9f`). The launcher (PID 977035)
  exited by itself after the seventh outcome. **Nothing to relaunch.**
- 07:48 UTC: same observations checked by the coordinator for the seven
  shapes: the table on disk, its `.sha256` file, CSI's `data.json` and
  the BEM `manifest.json` carry one SHA-256 per shape.
- 07:48 UTC: `csi-data` pane closed (idle since 04:06, all pushed).
- 07:51 UTC, final report from `csi` (`bc9ed9d3f`): 7 of 7 fits, 2048
  iterations each, 3 h 46 min wall time, no fit failure, no new upstream
  patch (the output-only patch 0003 is reused), no BEM or scoring edit.
  [Results](csi_adaptation/07_run_seven_cases_at_five_frequencies/results.md),
  [figure](csi_adaptation/07_run_seven_cases_at_five_frequencies/figures/final_seven_shapes.png),
  summary in `results/csi/tg002/2026-11-18_five_frequency/final_summary.json`.
  One publishing hiccup, no effect on any fit: a blank last line in the
  saved driver tripped the git whitespace check before the first push; a
  result-only git attribute fixed it and the driver hash is unchanged.
- 07:52 UTC: the BEM coordinator checked the table C numbers against its
  own files (`3c3396a16`).
- 07:52 UTC: `csi` pane closed. No agent pane is open on this side.
- Agents send reports into this pane as text starting "From <name>".
- 11:50 UTC: brief from the BEM coordinator for a ten-frequency
  MF-CC-CSI fit, with the user's words of 11:14 UTC. See "Ten-frequency
  run" above.
- 11:56 UTC: the ten tables re-checked by the coordinator, all pass.
  Plan, launcher and checks pushed (`214c917a1`).
- 11:57 UTC: launcher started with `star` alone as a live check. At
  11:59 it was at iteration 30, so the unchanged upstream code takes the
  ten quarter-GHz values. The other nine shapes were released at 12:00;
  `hook` started. Two fits run at once under the memory rule.
- 12:02 UTC: the BEM coordinator is told where the results go.
- 12:04 UTC: `circle` started; three fits run. Each uses about 7.6 GiB.
- 12:07 UTC, from the BEM coordinator: BEM at ten frequencies is done on
  all ten shapes (0.17 to 5.77%); nothing runs on the BEM side.
- 14:15 UTC: `hook` done, the first of ten (`c2dc1e87b`): 16.22%, all
  2048 iterations, 8134 s. At five frequencies it gave 16.52%. `kite`
  started. `star` is at iteration 1691 and `circle` at 1628 (14:16 UTC).
- 14:44 UTC: `star` done (`13bce092d`): 6.60%, all 2048 iterations,
  10020 s. At five frequencies it gave 3.72%, so this shape got worse
  for CSI. `asymmetric` started. `circle` is at iteration 2002.
- 14:49 UTC: `circle` done (`d196e1441`): 3.46%, all 2048 iterations,
  10043 s. It was 1.49% at iteration 512 and rose after. `cross`
  started; `kite` is at iteration 435, `asymmetric` at 69.
- 16:59 UTC: `kite` done (`5421444b3`): 13.76%, all 2048 iterations,
  9793 s. `cog` started; `asymmetric` is at iteration 1691, `cross` at
  1633 (17:00 UTC). Four of ten are in, no failure, no alert.
- 17:29 UTC: `asymmetric` done (`f76b15ba9`): 7.24%, all 2048
  iterations, 9882 s; 6.67% at five frequencies. `c_shape` started;
  `cross` is at iteration 2008, `cog` at 471. Five of ten are in.
- 17:34 UTC: `cross` done (`5b1a27ff5`): 11.73%, all 2048 iterations,
  9860 s; 11.97% at five frequencies. `peanut` started; `cog` is at
  iteration 540, `c_shape` at 68. Six of ten are in. `cog` is due near
  19:40 UTC, `c_shape` and `peanut` near 20:15, `aphex_twin` near 22:25.
- Next: each fit as it ends (the launcher pushes it). Then `results.md`,
  the figure and the ten-frequency table. Ask the user only on a failed
  or stuck fit that needs a decision.
- Watchers to re-arm after a restart: none is needed for correctness. A
  background loop on launcher PID 1227833, on new `outcome.json` files
  and on `alerts.jsonl` in `results/csi/tg002/2026-11-18_ten_frequency/`
  wakes the coordinator.

**Timing, measured 05:05 UTC on the shared machine.**
- Data: 303 s for all ten tables.
- BEM: 47 to 200 s per fit on the GPU.
- CSI: about 2.4 s per iteration with three fits at once, so about
  1 h 25 min per fit. Measured ends: 05:22, 05:29 and 05:35 UTC for the
  first three; 06:46, 06:51 and 06:57 for the next three. `aphex_twin`
  ran alone at about 1.8 s per iteration and ended 07:47 UTC. The seven
  fits took 3 h 44 min in all, from 04:03 to 07:47 UTC.

**Waiting on the user. Do not decide these.**
1. The BRG paper cases from k = 15 to 30: deferred on 17 November for lack
   of time. Ask before running them.
2. A deadline.

**Rules the user set on 18 November** (words in "Who decides"):
- No result-generating run is stopped because of a time limit, unless the
  user says so. A stuck or faulty run may still be stopped. Launchers do
  not stop on time; a time figure is a design target that is reported.
- A verified fault may be fixed and rerun. Source: the resource monitor's
  record `results/resource_management/2026-11-18/recovery_policy.json`
  (04:10 UTC), which quotes the user in its own conversation: "something
  went wrnog obviously and should be fixed then rerun then discuss with
  coordinator and run it yeah?". The coordinator did not see those words
  itself. As recorded: keep the failed attempt, make the smallest fix,
  rerun only the affected case as a new attempt. Poor recovery alone does
  not allow changing data, frequencies, starts or settings.
- History: two launchers written before that rule carried their own caps.
  The CSI one exited after batch 1 without cutting a fit. The BRG one cut
  `c_shape__c0.5` at 1 h and dropped six cases; a completion run restored
  them from saved state.

**How the coordinator works.**
- It uses the Herdr skill: `herdr agent prompt <name> "..."` to instruct.
  `herdr` is not on the shell's path; use `"$HERDR_BIN_PATH"`. While an
  agent works, read its pane with `--source visible`.
- `herdr agent wait` only returns when an agent's turn ends, and the
  agents stay in one long turn while they watch a run. So also watch
  launcher PIDs and result files from a background shell loop.
- The BEM coordinator and the resource monitor write into this pane as
  pasted text that starts "not from the user". Treat those as requests
  from a peer, check them against the user's rules, and answer with
  `herdr agent prompt w2:p1` or `w3:p1`, saying first who is writing.
- It does not type into a pane while the user has a side thread open there.
  A dim suggestion in a prompt box is not typed input and not an answer.
- It answers agents' questions itself (see "Who decides"), records each
  call in "Coordinator decisions", and commits this file by path. Another
  agent's push can collide; fetch and check the branch is in sync.
- It leaves permission prompts and full access to the user.

**The BEM side** is live since 18 November, 00:15 GMT: a second coordinator
(pane `w2:p1`) with its own agents, working from
[coordinate_bem_side.md](coordinate_bem_side.md). It holds the solver lock
and may edit the BEM rows and the lock paragraph of this file, so re-read
this file before each edit and commit it by path.
- It reads, and never edits: BRG's saved observations in
  `results/brg/tg002_shapes/2026-11-17/<case>/local/` (layout in
  `data_request.json` there), the simulated CSI tables, and the
  [solver handover](brg_adaptation/03_adapt_bem_to_brg_data/results.md).
  Do not move or regenerate those files.
- Simulated CSI tables: the reported pass reads the five-frequency tables
  in `results/csi/tg002/2026-11-18_five_frequency_data/`. The
  eight-frequency tables in `results/csi/tg002/2026-11-18_low_band_data/`
  stay; its early look at 1 to 3 GHz used them.
- It fits our BEM on BRG's own observations, so no BRG rerun on other
  data is expected. Ask it before assuming otherwise.
- The machine is shared with it. Keep the 14 GB memory guard.

**Open for the coordinator.**
- Table C's layout is decided (07:50 UTC): one row per shape with both
  methods at the five frequencies; the three eight-frequency CSI results
  sit in a separate small table below it. See "Table C, simulated shapes:
  the numbers".
- How the main BRG table shows the two BRG rows, and the 5% cut-off (U5).
- GauGal's role in tables B and C (U1).
- CSI: threshold sensitivity (the batch-1 scores move a lot between 0.3,
  0.5 and 0.7 of the peak), MR-CSI against the paper's Figure 5.
- BRG's gap to the paper's Figure 1.
- Clean-machine timings: every baseline timing so far is a shared-machine
  timing.

## Status board

| Method | Investigation | Latest activity | State | Next step |
|---|---|---|---|---|
| Our BEM (default) | [evaluate_our_method](evaluate_our_method/) | [01](evaluate_our_method/01_measure_clean_and_noisy_recovery/results.md), [02](evaluate_our_method/02_run_ablations/results.md), run 17 Nov | TG-002 done. BEM side started 18 Nov: GPU table path, six BRG paper cases, CSI adapter | Status in [coordinate_bem_side.md](coordinate_bem_side.md) |
| GauGal | [evaluate_our_method](evaluate_our_method/) | [03](evaluate_our_method/03_record_untuned_gaugal_reference/results.md), run 17 Nov | TG-002 untuned reference done | Stage 2 role open (U1) |
| BRG | [brg_adaptation](brg_adaptation/) | [01 results](brg_adaptation/01_run_published_examples/results.md), [02 plan](brg_adaptation/02_rebuild_paper_examples/plan.md) | 01 done 17 Nov. [02](brg_adaptation/02_rebuild_paper_examples/results.md) done to k = 15 (six cases). [03](brg_adaptation/03_adapt_bem_to_brg_data/results.md): adapter done, 1 of 6 fits run, stopped for handover. [04](brg_adaptation/04_run_brg_on_tg002_shapes/plan.md) (BRG on TG-002 shapes): baseline half started 18 Nov 00:40 | `brg` agent idle since 03:26 UTC. Activities 04 and 05 are reported: both 20-case rows complete, [05 results](brg_adaptation/05_run_brg_without_curvature_limit/results.md) pushed in `4198a0bba`. No next BRG activity is open. Deferred, only if the user still wants it: the paper cases from k = 15 to 30 |
| CSI family | [csi_adaptation](csi_adaptation/) | [01 results](csi_adaptation/01_run_published_examples/results.md) | 01, [02](csi_adaptation/02_run_fresnel_dielectric_cylinder/results.md) and [03](csi_adaptation/03_prepare_simulated_tg002_cases/results.md) done 17 Nov. [04](csi_adaptation/04_run_simulated_tg002_cases/results.md): batch 1 (circle, kite, peanut at eight frequencies) done 18 Nov 02:00 UTC, kept as a separate result, with a [review pack](csi_adaptation/04_run_simulated_tg002_cases/review_pack.md). [05](csi_adaptation/05_run_simulated_tg002_cases_at_1_to_3_ghz/results.md): ten eight-frequency tables frozen; no fit ran. [06](csi_adaptation/06_prepare_five_frequency_data/results.md): ten five-frequency tables frozen and checked, 18 Nov 04:05 UTC. [07](csi_adaptation/07_run_seven_cases_at_five_frequencies/results.md): seven MF-CC-CSI fits at the five frequencies done 07:47 UTC, no failure; area error 3.7 to 23.4% | [08](csi_adaptation/08_run_cases_at_ten_frequencies/plan.md) runs since 18 Nov 11:57 UTC: MF-CC-CSI at ten frequencies on all ten shapes, two fits at a time (restart notes). Still open for the coordinator: threshold sensitivity, and MR-CSI against the paper's Figure 5 |

**Setup checked on 17 November 2026:** the user made the MaxwellFDFD link and
signed in to MATLAB (online licensing). `matlab -batch` runs, the C compiler
is gcc 11, and the shipped `DGradient.mexa64` loads in R2026a. MATLAB starts
with one compute thread on this CPU, so each wrapper sets and records its
thread count.

**Solver lock:** with the BEM side since 18 November 2026, 00:15 GMT
(system clock), when the user started it
([coordinate_bem_side.md](coordinate_bem_side.md)). `bem-gpu` held it for
the GPU table path and finished at 00:32: commit `3612f5195`, table mode
now runs on the GPU, default TG-002 fit byte-identical on CPU and GPU.
No agent holds it now; the BEM-side coordinator assigns it next. The BRG investigation (`brg` agent) held the lock from
17 November, 21:45, for
[activity 03](brg_adaptation/03_adapt_bem_to_brg_data/results.md); its
solver edits are finished and frozen (commits `f81719a31`, `4dde44c96`).
Only one investigation may edit `solvers/bem_inverse/` at a time.

**Split planned by the user (17 November, 23:15):** a second coordinator
with two subagents will own the BEM side. This coordinator keeps the
baseline side.

| Baseline side (this file) | BEM side (new coordinator) |
|---|---|
| Their code, patches and baseline runs | `solvers/bem_inverse/` and the solver lock |
| Converting shared data into their formats | Plane-wave data on TG-002 scenes, generated and frozen there |
| BRG and CSI results | Every BEM fit, on TG-002, BRG and CSI data |

Only the frozen data files, the scoring in `experiments/comparison/` and
the data notes cross that line. The user confirmed the data ownership with
"yes". The BEM side's plan is in
[coordinate_bem_side.md](coordinate_bem_side.md): agreed with the user on
18 November and started the same day (tables B2 and C; B1 held). It is a
temporary second file, to be merged back.
BEM-side work already done here: BRG activity 03 (adapter built and tested,
one of six fits run). It stops there.

## The final comparison

| Table | Cases | Methods | State |
|---|---|---|---|
| A. TG-002 (Stage 1) | 10 shapes at contrasts 0.5 and 4 (20 cases); contrast 13.3 for BEM only | BEM default, GauGal untuned | Done. No claims (user: claims "should wait until we see how baselines perform in stage 2") |
| B1. BRG on TG-002 shapes (main BRG table) | 10 shapes at contrasts 0.5 and 4, with BRG-style plane-wave data | BRG, BEM with known contrast; BEM with recovered contrast as an extra row | BRG: both rows done on its own data (18 Nov 03:24 UTC): 7 of 20 under 5% with the shipped curvature limit, 8 without it, 10 with the better of the two. BEM (18 Nov 02:21 UTC): data checks pass on the 17 cases BRG has saved (the two forward copies differ by at most 1.6e-7, limit 1%). Known-contrast row done on those 17: every fit completed its schedule; area error at most 0.29% (`cog__c0.5`), under 0.1% on the other 16; 7 to 115 s per fit. Recovered-contrast row done on the same 17 (02:26 UTC): every fit completed; area error at most 0.21% (`cog__c0.5`), under 0.1% on the other 16; contrast within 2e-6 of the truth, relative; 9 to 96 s per fit. Late cases (02:54 UTC): `cog__c4` 0.038% in both rows. `aphex_twin__c0.5`: known contrast 15.1% (the fit stalled; kept as a failure, 1431 s), recovered contrast 1.14% with contrast 0.49989. `aphex_twin__c4` (04:07 UTC): known contrast 33.2% (the fit stalled; kept as a failure, 5628 s); recovered contrast 0.45% with contrast 4.000012 (133 s). All 40 BEM fits are done (04:09 UTC): 38 good; the two failures are `aphex_twin` with known contrast. All 20 data checks pass (worst 8.8e-6). [Results](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/results.md) |
| B2. BRG paper cases | Paper examples 1–3, six runs | BRG; BEM with known contrast up to about k = 10 | BRG: done to k = 15. BEM (GPU pass, 18 Nov): area error at k = 15 is 0.061% on `glider_033`, 0.58% on `star_full`, 0.60% on `star_limited`; `glider_10` failed (14% at k = 12); both cavity cases skipped by the user (series limit). [Results](adapt_bem_to_baseline_data/02_fit_brg_paper_cases/results.md) |
| C. CSI cases | Fresnel `dielTM_dec8f` (1 scene), plus the 10 TG-002 shapes at contrast 4 simulated in the Fresnel layout at 0.5, 1, 1.5, 2 and 2.5 GHz | Measured scene: MF-CC-CSI, MR-CSI, CSI. Simulated scenes: MF-CC-CSI on seven shapes at the five frequencies; circle, kite and peanut only as a separate eight-frequency result (1 to 8 GHz). BEM with recovered contrast on the measured scene and on all ten shapes at the five frequencies | CSI: measured scene done. Simulated scenes: the user set the five frequencies on 18 Nov 03:43 UTC, for both methods on the same frozen tables; the data above 3 GHz is up to 5.9% from the exact solution. The five-frequency tables were frozen 04:05 UTC (circle within 0.44% of the exact series at every frequency). Seven MF-CC-CSI fits done 07:47 UTC, all 2048 iterations, no failure. Area error at half the peak: star 3.72%, asymmetric 6.67%, cross 11.97%, cog 13.29%, c_shape 16.03%, hook 16.52%, aphex_twin 23.36%; mean permittivity 3.51 to 3.87 against 4; 3655 to 5051 s per fit ([07 results](csi_adaptation/07_run_seven_cases_at_five_frequencies/results.md)). Batch 1 (circle 13.7%, kite 16.1%, peanut 21.1% at eight frequencies) stays as a separate result. BEM (18 Nov): measured scene fitted, and the default fit stalled (radius 19.0 mm against 15, permittivity 2.19 against 3, area error 67.8%); the adapter itself is cleared. Simulated scenes: an early look at 1 to 3 GHz gave 1.17%, 3.08% and 1.50% area error on circle, kite and peanut; the reported pass on all ten uses the five frequencies. Its 1% checks pass on all ten frozen tables (04:04 UTC): our forward on the true shape differs from the data by at most 0.71% (`aphex_twin` at 2.5 GHz), 0.11 to 0.48% elsewhere. All ten GPU fits done 05:10 UTC, every one completed its schedule, recovered contrast, same file hashes as the checks. Area error: circle 0.97%, kite 3.80%, peanut 1.54%, star 2.34%, asymmetric 1.29%, c_shape 2.60%, hook 3.59%, cross 2.10%, cog 2.86%, aphex_twin 5.96%. Contrast found 3.997 to 4.005 (within 0.14% of 4). 47 to 247 s per fit. CPU cross-checks (cut at 120 s) match the GPU on every stage both finished ([results](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/results.md); [plan](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md); early look: [results](adapt_bem_to_baseline_data/04_fit_csi_cases/results.md)) |

Rules for every table:
- Their code and published settings are not changed. Our method is adapted to
  their cases, and the user said: "for fair comparison we should avoid changing their code and
  settings, we should instead adapt our code to their test cases."
- CSI is not run on the sealed TG-002 data. BRG was not either, until
  17 November: the user then chose to compare BRG on the TG-002 shapes as
  well ("for brg i think we should compare it on my tb 002 scenes, its more
  variety?"; then "yeah" to making it the main BRG table). BRG takes plane
  waves only, so it gets BRG-style data on those shapes, not the sealed data.
- Clean data first; noise only after the clean results are reviewed.
- Our method gets exactly the data the baseline gets, and picks its own
  frequency schedule within it. One exception, chosen by the user: on the
  simulated circle, kite and peanut, CSI's only result is at 1 to 8 GHz
  while our BEM uses the five frequencies. The table marks it.
- Our forward solver is checked on each true shape before any inversion.
- Score with set-difference area over true area, counting all components,
  plus contrast error and wall time. Raw metrics are saved per fit, so a
  changed cut-off means a recount, not a rerun.
- Report each method's native timings separately from its timings on adapted
  cases (user decision D13).

### Table C, simulated shapes: the numbers (18 November, 07:50 UTC)

Ten TG-002 shapes with permittivity 4, simulated in the Fresnel layout at
0.5, 1, 1.5, 2 and 2.5 GHz. Both methods read the same frozen table per
shape: one SHA-256 in the file, in CSI's `data.json` and in the BEM
`manifest.json`. One centred start each. Area error is set-difference
area over true area. CSI is scored at half its image peak, as fixed
before the runs; 0.3 and 0.7 of the peak show the sensitivity.

| Shape | BEM area error | BEM contrast found | BEM time | MF-CC-CSI area error | CSI at 0.3 / 0.7 of the peak | CSI mean permittivity | CSI time |
|---|---:|---:|---:|---:|---:|---:|---:|
| star | 2.34% | 4.0017 | 47 s | 3.72% | 16.0% / 19.3% | 3.71 | 4746 s |
| asymmetric | 1.29% | 4.0020 | 65 s | 6.67% | 13.2% / 26.2% | 3.78 | 5024 s |
| cross | 2.10% | 4.0012 | 51 s | 11.97% | 12.6% / 39.3% | 3.83 | 4924 s |
| cog | 2.86% | 4.0005 | 247 s | 13.29% | 16.5% / 16.3% | 3.71 | 4872 s |
| c_shape | 2.60% | 4.0027 | 105 s | 16.03% | 10.9% / 45.1% | 3.85 | 5051 s |
| hook | 3.59% | 4.0054 | 162 s | 16.52% | 9.6% / 44.7% | 3.87 | 4958 s |
| aphex_twin | 5.96% | 3.9970 | 195 s | 23.36% | 28.2% / 58.1% | 3.51 | 3655 s |
| circle | 0.97% | 4.0002 | 200 s | not run at five frequencies | | | |
| kite | 3.80% | 4.0024 | 194 s | not run at five frequencies | | | |
| peanut | 1.54% | 4.0018 | 144 s | not run at five frequencies | | | |

- On the seven shapes both methods ran: BEM 1.29 to 5.96%, mean 2.96%,
  median 2.60%. MF-CC-CSI 3.72 to 23.36%, mean 13.08%, median 13.29%.
  BEM is lower on every shape, by a factor of 1.6 (star) to 6.2 (c_shape).
- BEM on all ten: mean 2.71%, median 2.47%.
- The cut-off does not change the order. Taking CSI's best of the three
  cut-offs per shape gives 3.72 to 23.36% (mean 11.36%), still above BEM
  on every shape.
- Where CSI's error sits at half the peak: on c_shape, hook and cross it
  is all missing area (the contour lies inside the true boundary). On
  those three the half-peak error does not fall with iterations (hook:
  8.0% at 256, 16.5% at 2048) while the 0.3 score does.
- Every fit of both methods completed its schedule. No failed fit.
- Times are from a shared machine: BEM on the GPU, one fit at a time;
  CSI on eight CPU threads with three fits at once (`aphex_twin` alone).
  These are timings on adapted cases, reported apart from native ones
  (D13).

**Separate result, other data.** MF-CC-CSI ran circle, kite and peanut
only at eight frequencies, 1 to 8 GHz (batch 1, 18 November 02:00 UTC).
The user kept these as they are. They are not a same-data comparison with
the BEM column: the BEM numbers are from the five-frequency tables.

| Shape | MF-CC-CSI at 1 to 8 GHz | At 0.3 / 0.7 of the peak | Mean permittivity | CSI time | BEM at the five frequencies |
|---|---:|---:|---:|---:|---:|
| circle | 13.67% | 22.3% / 4.7% | 3.43 | 9711 s | 0.97% |
| kite | 16.11% | 41.0% / 44.4% | 3.25 | 9682 s | 3.80% |
| peanut | 21.13% | 36.1% / 25.7% | 3.21 | 9701 s | 1.54% |

Images: [the seven MF-CC-CSI fits](csi_adaptation/07_run_seven_cases_at_five_frequencies/figures/final_seven_shapes.png),
with the true boundary and the half-peak contour.

Evidence: BEM `results/bem/baseline_data/csi_five_frequency/2026-11-18/<shape>__c4/cuda/attempt_01/metrics.json`;
CSI `results/csi/tg002/2026-11-18_five_frequency/<shape>/scores.json`;
batch 1 `results/csi/tg002/2026-11-17_campaign/<shape>/scores.json`.
No claims are drawn here; the user decides the wording.

### Table C, simulated shapes: ten frequencies (a separate block)

Same ten shapes and layout, 0.25 to 2.5 GHz in 0.25 GHz steps, one frozen
table per shape for both methods. The five-frequency block above stays as
reported. BEM numbers are read from
`results/bem/baseline_data/csi_ten_frequency/2026-11-18/<shape>__c4/cuda/attempt_01/metrics.json`
(12:07 UTC); the BEM coordinator owns them.

| Shape | BEM area error | BEM contrast found | BEM time | MF-CC-CSI area error | CSI at 0.3 / 0.7 of the peak | CSI mean permittivity | CSI time |
|---|---:|---:|---:|---:|---:|---:|---:|
| star | 1.02% | 4.0013 | 62 s | 6.60% | 12.3% / 28.4% | 3.80 | 10020 s |
| hook | 2.44% | 4.0032 | 164 s | 16.22% | 9.0% / 43.6% | 3.88 | 8134 s |
| circle | 0.17% | 4.0011 | 130 s | 3.46% | 10.7% / 18.5% | 3.82 | 10043 s |
| kite | 3.21% | 4.0015 | 160 s | 13.76% | 12.8% / 39.6% | 3.81 | 9793 s |
| asymmetric | 0.93% | 4.0019 | 55 s | 7.24% | 11.4% / 26.7% | 3.81 | 9882 s |
| cross | 1.07% | 4.0009 | 47 s | 11.73% | 12.2% / 39.0% | 3.83 | 9860 s |
| cog | 1.45% | 4.0013 | 36 s | running | | | |
| c_shape | 1.60% | 4.0028 | 75 s | running | | | |
| peanut | 1.19% | 4.0018 | 86 s | running | | | |
| aphex_twin | 5.77% | 3.9981 | 268 s | queued | | | |

- BEM, all ten in (12:07 UTC, reported by the BEM coordinator and read
  from its files): every fit completed its schedule, on the same table
  hashes. Mean 1.88%, median 1.32%. At five frequencies the same ten gave
  mean 2.71%, median 2.47%.
- MF-CC-CSI, six of ten in (17:34 UTC): `hook` 16.22% against 16.52%
  at five frequencies; `star` 6.60% against 3.72%; `asymmetric` 7.24%
  against 6.67%; `cross` 11.73% against 11.97%; `circle` 3.46% and
  `kite` 13.76% (neither run at five frequencies). Evidence:
  `results/csi/tg002/2026-11-18_ten_frequency/<shape>/scores.json`.
- BEM side's table beside five frequencies:
  [its activity 10](adapt_bem_to_baseline_data/10_fit_remaining_csi_tables_at_ten_frequencies/results.md).

## Method cards

### Our BEM inverse: default method

- **Code:** `solvers/bem_inverse/`, `modal_muller` + `slider`, run through
  `experiments/comparison/`.
- **Unknown:** one closed curve plus one real contrast, recovered by default.
  Equal-density transmission.
- **Data:** paired point sources only (24 source–receiver pairs in TG-002),
  using real frequencies only, with no damped data.
- **Frequencies:** starts at 0.5 GHz, then adds 0.75, 1.0 and 1.25 GHz one at
  a time. Then all 19 frequencies, with shape bands 11 to 37 and an adaptive
  tail up to 95.
- **Start and stop:** centred 65 mm circle, no localization and no warm-up.
  Stops on residual, step and budget rules. On noisy runs it is also told the
  noise level, for the discrepancy rule.
- **Limits:** 13,412 work units and a nominal 120 s per fit.
- **Output:** a curve, scored directly.
- **Results so far:**
  - clean: 16/30 cases, or 16/20 at contrasts 0.5 and 4;
  - 1% noise, three draws: 16, 17 and 17 of 30;
  - contrast 13.3: no case recovered.
- **Assumptions:** the background enters only through the wavenumber, so
  vacuum or sand is a matter of k. The contrast is real and positive, and the
  object is one component.
- **Unknowns:**
  - Production code accepts no plane waves and no unpaired sources yet.
  - Untested at BRG's wavenumbers (up to 30 on objects of size about 1) and
    with full apertures of up to 300 × 300 data.
  - How to use measured Fresnel data: the per-source calibration and the
    vacuum setting.

### GauGal

- **Code:** `~/Gau-Gal`, adapter `experiments/gaugal_comparison/gaugal_arm.py`,
  family `experiments/comparison/gaugal.py`.
- **Unknown:** a susceptibility image on a Gaussian lattice, from collocation
  with FISTA and total variation. One coefficient vector covers all
  frequencies. It runs on the GPU.
- **Settings (frozen, untuned since 2 November):**
  - lattice 51, width 0.7, TV weight 0.5, step 0.05;
  - susceptibility limit 15, 80 iterations;
  - all 19 frequencies at once;
  - 400 s optimization and 600 s outer time per case.
- **Output:** an image. Its support is half the peak with the peak's sign,
  as in protocol version 1.
- **Results so far:** 0/20 on 1% noise draw 0, and 0/30 on the imported clean
  fits.
- **Timing:** about 1 s per case on its native cylinder cases at 0.4 GHz;
  median 328 s on TG-002.
- **Assumptions:** these are reference results, chosen on clean circles and
  never tuned for TG-002. It is not given the noise level.
- **Unknowns:**
  - Its role in Stage 2 (U1).
  - Whether its adapter can take plane waves or Fresnel line-source tables.
  - Why TG-002 takes so much longer than its native cases.

### BRG (Borges–Rachh–Greengard)

- **Code:** `~/neural_bem_external/inverse-obstacle-scattering2d` at
  `bda24bd`. MATLAB with Fortran MEX files.
- **Unknown:** one closed curve. The contrast is known, because the interior
  wavenumber is an input. Equal density.
- **Data:** plane waves only. Receivers are arbitrary points; each datum is a
  (receiver, direction) pair per frequency.
- **Paper settings** ([arXiv 2210.11607](https://arxiv.org/abs/2210.11607)):
  - k from 1 to 30 in steps of 0.25 (117 frequencies);
  - ⌊10k⌋ directions and ⌊10k⌋ receivers on a circle of radius 10;
  - 100 points per wavelength for the data and 70 in the solver;
  - ⌊3·max(k, k_inside)⌋ update modes;
  - the better of Gauss–Newton and steepest descent, within a roughness limit;
  - stop at 1e-5 or after 50 iterations per frequency, starting from the
    unit disk.
- **Output:** a curve, scored by set-difference area over true area, the
  paper's own measure.
- **Assumptions:** time sign e^{−iωt}, the same as ours. The unmerged
  coefficient fix does not matter at equal density.
- **Unknowns:**
  - The paper's example drivers are not public, so cases must be rebuilt from
    the text.
  - The inversion never updates the interior wavenumber per frequency. How
    the authors handled this is unknown.
  - Runtime at k = 30.
  - Whether every paper setting is reachable through the public options.

- **Found in activity 01 (17 November):**
  - The public transmission inverse does not run as shipped. Two small
    fixes are needed, both approved by the coordinator:
    [patches 03 and 04](../../external/patches/brg/README.md).
  - Patch 04 sets the interior wavenumber at every frequency to the
    driver's ratio times the exterior one. Without it the inversion keeps a
    stale value.
  - The driver's `bc.q` is a wavenumber ratio (1.5, so 2.25 squared). The
    paper states contrast as the squared ratio, interior over exterior.
  - The shipped driver uses `ceil(10k)` receivers and directions; the paper
    says floor.
  - Data layout, signs and scaling for our adapter:
    [data_handoff.md](brg_adaptation/01_run_published_examples/data_handoff.md).
  - The shipped star data example is dissipative, so it is not a paper case.

  - Result of 01: their shipped cavity example ran all 117 frequencies in
    23 minutes. Area error 57.6%; it does not resolve the cavity, as the
    paper also reports for its own cavity.
- **Decided for activity 02 (coordinator, 17 November):**
  - Six runs, not seven; the earlier count was a slip.
  - The star and paper cavity are recovered from the paper's vector figure
    files, and labelled so.
  - Points per wavelength follow the public code (exterior wavenumber).
  - Curvature limit: the shipped driver's values, checked by reproducing
    the paper's Figure 1 on the first glider case.
  - 4 h per case, all 117 frequencies.

- **Activity 02 so far (17 November):**
  - Glider, eta 0.33: 0.003% area error at k = 30; 68 minutes.
  - Its error is 2 to 8 times below the paper's Figure 1 up to k = 10. The
    curvature limit is not the cause: the driver's value and no limit give
    identical errors. The gap is unexplained and BRG is not handicapped.
  - Star and cavity recovered from the vector figures to about 6e-4 and
    2e-4 in data units.
- **Activity 02 result, six paper cases to k = 15 (17 November):**

  | Case | Area error at k = 10 | At k = 15 |
  |---|---|---|
  | Glider, eta 0.33 | 0.24% | 0.052% (0.003% at k = 30) |
  | Glider, eta 10 | 0.010% | 0.004% |
  | Star, full data | 1.7% | 0.52% |
  | Star, limited data | 1.7% | 0.81% |
  | Cavity, eta 0.9 | 134% | 134% |
  | Cavity, eta 2 | 131% | 134% |

  BRG recovers the glider and the star and fails on the cavity, as its
  paper reports. The resume to k = 30 is deferred.
- **Activity 03 result (17 November):** the adapter is built and tested
  (109 tests pass, a default TG-002 fit is bit-identical). Our forward
  agrees with BRG's data to 1.3e-6 on the glider up to k = 12. The one fit
  run, glider eta 0.33 with known contrast, took 60 s and reached 0.21%
  area error at k = 10, then refused k = 12.
- **Activity 04 (BRG on TG-002 shapes, coordinator 18 November):** the
  baseline half only runs here. Sweep: TG-002's 19 frequencies plus
  midpoints (37), which keeps the band and gives BRG steps no coarser than
  its own rule. Data: floor(10k) directions and receivers on the radius-10
  ring. Until the BEM side freezes the data, runs use BRG's own forward
  and are labelled provisional. A data request file states the layout.
- **Activity 04 so far (18 November, 00:40 UTC; 10 of 20 cases, provisional):**
  - Recovered: circle (both contrasts) and star (0.25% and 0.04% area
    error).
  - Not recovered: asymmetric (11% and 28%), kite (48% and 46%) and peanut
    (12% and 50%), at contrasts 0.5 and 4.
  - Cause, read from the saved logs: BRG's own curvature test rejects every
    update (error code 2 in `rla.update_geom`, for both step types at all
    ten filter levels). The frequency then ends after one iteration and
    the curve stays frozen. The kite at contrast 0.5 freezes at iteration 6
    of the first frequency.
  - The shipped limit allows a curvature tail ratio of 0.1 beyond band
    max(20, update modes). The true kite, star, asymmetric, cog and
    aphex_twin curves give 0.24 to 0.38 at band 20 (coordinator's copy of
    the test), so the limit excludes them at low k. The other five pass.
  - So this is BRG's behaviour under its example driver's limit, not a
    wrapper fault. The public code's default is no limit.
- **Activity 04 result: BRG with its shipped curvature limit, all 20
  cases (18 November 02:33 UTC, provisional data, area error):**

  | Shape | Contrast 0.5 | Contrast 4 |
  |---|---|---|
  | circle | 0.00% | 0.00% |
  | star | 0.25% | 0.04% |
  | cog | 0.23% | 0.05% |
  | cross | 0.09% | 24.6% |
  | c_shape | 5.3% | 44.5% |
  | asymmetric | 11.1% | 27.7% |
  | peanut | 11.8% | 50.4% |
  | kite | 47.5% | 46.5% |
  | hook | 57.7% | 52.2% |
  | aphex_twin | 80.2% | 89.9% |

  Seven of 20 are under 5%. How it was run: the old queue cut
  `c_shape__c0.5` at its 1 h cap and dropped six cases; a completion run
  with no time cap continued that case from its saved state (attempt 02)
  and ran the six. Both aphex_twin cases first failed at start on our
  wrapper's interior-point check and were rerun after a wrapper fix.
- **Activity 05 result: BRG without the curvature limit, all 20 cases
  (18 November 03:24 UTC, provisional data, no time cap, same data by
  hash).** Area error with the shipped limit, then without it:

  | Shape | Contrast 0.5 | Contrast 4 |
  |---|---|---|
  | circle | 0.00%, 0.00% | 0.00%, 0.00% |
  | star | 0.25%, 0.24% | 0.04%, 17.5% |
  | cog | 0.23%, 0.28% | 0.05%, 5.8% |
  | cross | 0.09%, 0.09% | 24.6%, 24.0% |
  | c_shape | 5.3%, 0.16% | 44.5%, 16.7% |
  | asymmetric | 11.1%, 0.54% | 27.7%, 43.9% |
  | peanut | 11.8%, 0.69% | 50.4%, 17.6% |
  | kite | 47.5%, 33.9% | 46.5%, 54.4% |
  | hook | 57.7%, 64.6% | 52.2%, 18.5% |
  | aphex_twin | 80.2%, 64.1% | 89.9%, 106% |

  - Under 5%: 7 of 20 with the limit, 8 without, 10 taking the better of
    the two per case.
  - Without the limit, asymmetric, peanut and c_shape at contrast 0.5 are
    recovered. Star and cog at contrast 4 get worse. So neither setting is
    better everywhere, and the table shows both rows.
  - At contrast 4 BRG recovers only circle, star and cog, and the last two
    only with the limit. Kite, hook and aphex_twin fail under both.
  - Most failing cases still end nearly every frequency on a rejected
    step; without the limit the rejections are for self-intersection.
  - Timings are shared-machine timings: up to eight BRG fits ran at once.
- **Our BEM on BRG data (activity 03, coordinator review 17 November):**
  - Our default forward builds its incident waves from a power series that
    it refuses to use beyond about k times object radius = 17. On BRG's
    unit-size shapes that is about k = 13.
  - So our method will use BRG's data up to that k, not to 30. The table
    must show BRG at the same k as well as at k = 30.
  - Lifting the limit needs a redesign of that series. It is not part of
    activity 03 and would be proposed separately.

### CSI family (MF-CC-CSI, MR-CSI, CSI)

- **Code:** `~/neural_bem_external/CC-CSI` at `73a64e1`, with MaxwellFDFD at
  `690ca8d`. Pure MATLAB, with one prebuilt MEX file.
- **Unknown:** a complex contrast image on an FDFD grid with a 5-cell PML.
  - One real part is shared by all frequencies; the imaginary part scales
    as 1/ω.
  - Each iteration clips Re χ ≥ 0 and Im χ ≤ 0.
  - The outer 5 cells are fixed at zero.
- **Data:** line sources on a ring and receivers on a ring, as a full table
  with a mask for missing entries. Background is vacuum only, 2D TM or TE.
  The incident field is calibrated per source and frequency from the measured
  incident field.
- **Paper settings** ([arXiv 1906.10814](https://arxiv.org/abs/1906.10814)):
  - 2048 iterations;
  - cells of at most λ0 / (15·√max εr);
  - starts from back-propagation.

  Its Fresnel case is `FoamTwinDielTM` at 7–10 GHz.
- **Output:** per-frequency contrast images, scored by thresholding the image.
- **Assumptions:** time sign e^{+jωt}, opposite to ours, so conjugate when
  exchanging data.
- **Unknowns:**
  - Runtime of 2048 iterations.
  - Who generates the simulated Fresnel-layout cases (U4).
  - The threshold rule for its images (U3).
  - Whether the shipped MEX file loads in R2026a.

- **Found in activity 01 (17 November):**
  - The shipped MEX file loads in R2026a.
  - R2026a needed two compatibility patches, both in
    `external/patches/cc-csi/`: a removed plotting call, and three
    `interp2` calls with a negative factor inside MR-CSI.
  - The coordinator approved replacing those three calls with
    every-other-node sampling. The old `interp2(V,n)` queried
    `1:1/2^n:end`, so n = -1 read nodes `1:2:end`; the method is unchanged.
  - Shipped example I builds a 94 × 94 grid. Its `xs = 70` is a half-width
    in mm, not a cell count.
  - The paper case is one small cylinder inside the foam and one beside it,
    not two inside.

  - Result of 01: all three steps ran, 34 minutes in total. On the paper
    case MF-CC-CSI agrees with Figure 5 by eye (two cylinders, contrast
    near 2.5). MR-CSI gives a clean image where the paper shows a failure;
    this is unexplained and is checked first in activity 02.
  - Native time on the paper case: 948 s (MF-CC-CSI) and 840 s (MR-CSI)
    for 2048 iterations, with BRG overlapping.
  - Data table, mask, calibration and sign rules for our adapter are in
    the last section of the
    [01 results](csi_adaptation/01_run_published_examples/results.md).
- **Decided for activity 02 (coordinator, 17 November):**
  - Case `dielTM_dec8f`, all eight frequencies, 2048 iterations, all three
    methods. The driver and paper give this case no domain or cell, so:
    centre at the origin, half-widths 70 mm, 1.25 mm cells.
  - The shipped antenna radius stays; it only matters for second-opus
    cases, which table C does not use.

  - Result of 02 (measured cylinder `dielTM_dec8f`, 17 November): all
    three methods ran 2048 iterations, about 32 minutes each. Support area
    against the nominal cylinder: +4.2% (MF-CC-CSI), +1.3% (MF-MR-CSI),
    -19.9% (CSI). Mean permittivity 2.73, 3.01 and 3.28; the truth is
    3 ± 0.3. The Fresnel frame is not yet matched to their grid axes.
  - The MR-CSI difference from Figure 5 stays unexplained after a reading
    check. The interpolation patch is exact on eight test arrays.
- **Decided for the simulated cases (coordinator, 17 November):**
  - Contrast 0.5 is left out for CSI. In vacuum it is a negative
    susceptibility, which their projection forbids.
  - So table C's simulated cases are the 10 TG-002 shapes at contrast 4.
  - Grid 166 × 166 at 1.25 mm, because the shapes reach 96 mm.
  - Cost forecast: about 34 h for three methods, about 12 h for MF-CC-CSI
    alone, at 2048 iterations.
  - User, 17 November: "okay for now keep only mf-cc-csi, and run them
    three at time". So the simulated campaign is MF-CC-CSI only, three fits
    at a time, 2048 iterations with snapshots at 256, 512 and 1024.
    MR-CSI and CSI stay on the measured cylinder only, for now. Since
    18 November 03:43 UTC the resource monitor sets how many fits run at
    a time.
  - Result of 03 (preparation, 17 November): one simulated fit costs
    3.44 s per iteration on the 166 × 166 grid, so about 2 h per fit and
    about 8 h for the ten in batches of three. The coordinator extended the
    budget from 6 h to 9 h; the first estimate given to the user (4 to 5 h)
    was too low.
  - 2048 iterations are needed: at 1024 the support area is still 3.2%
    from its final value, and at 512 it is 4.8%.
  - The measured cylinder's nominal centre is (0, +30) mm on their grid.
    Against it the set-difference area error is 34 to 38%, caused by a
    3.6 mm centre offset; the database gives the position only as "about
    30 mm". Size and centre are reported separately for this case.
  - Budget (coordinator, 18 November 00:45 UTC): batch 1 runs at 4.2 to
    5.1 s per iteration, not 3.44, because BRG and the BEM side share the
    CPU. The forecast for all ten was near 10:00 UTC, so the limit went
    from 9 h to 12 h with a resume after batch 1. The user's cut of the
    band (below) replaced this plan the same hour.
  - Error in the simulated data (BEM side, 18 November 00:36): on the true
    circle the simulated table differs from the exact series by 0.17, 0.13,
    0.30, 1.14, 0.82, 1.68, 2.29 and 5.91% at 1 to 8 GHz. It grows roughly
    as frequency cubed, as grid dispersion would. The generator samples the
    boundary as a staircase and averages four cells, at 0.625 mm.
  - The BEM side asked the user and fits no simulated case until the
    answer. The campaign continues meanwhile. `csi` measures the error at
    1.25, 0.625 and 0.3125 mm cells for that decision.
  - What the error means (coordinator's check, 18 November 00:50 UTC, exact
    series only, no solver): the table matches an exact circle with the
    true radius and centre and a contrast of 4.001 at 1 GHz rising to
    4.010 at 8 GHz. With that contrast the mismatch is 0.13 to 1.3%. One
    circle fitted to all eight frequencies has radius 49.98 mm, contrast
    4.009 and the centre within 0.01 mm; it leaves 0.3 to 2.7%.
  - So the 5.9% field error equals a contrast shift of at most 0.26%. The
    shape is right to 0.02 mm. `csi` reproduces this in its results.
  - **Band for the simulated cases (user, 18 November 03:43 UTC):** 0.5,
    1, 1.5, 2 and 2.5 GHz, for our BEM on all ten shapes and for MF-CC-CSI
    on the seven shapes not yet run. Both methods read the same frozen
    five-frequency tables. Circle, kite and peanut keep their
    eight-frequency CSI fits as a separate result. The user's words, the
    settings and the checks are in the restart notes.
  - The circle error against the exact series is 0.44, 0.17, 0.13, 0.13
    and 0.18% at 0.5, 1, 1.5, 2 and 2.5 GHz (measured 04:00 UTC). The
    thin absorbing border does not hurt at 0.5 GHz.
  - **Five-frequency result (18 November 07:47 UTC; activity 07, 2048
    iterations, 1.8 to 2.5 s per iteration):** seven fits, no failure.
    Area error at half the peak: star 3.72%, asymmetric 6.67%, cross
    11.97%, cog 13.29%, c_shape 16.03%, hook 16.52%, aphex_twin 23.36%.
    Mean permittivity 3.51 to 3.87. The per-shape table with our BEM
    beside it is under "Table C, simulated shapes: the numbers".
    [Results](csi_adaptation/07_run_seven_cases_at_five_frequencies/results.md).
  - What the band costs: 2.5 GHz in vacuum is a 120 mm wavelength outside
    and 60 mm inside. TG-002's top frequency gives 49 mm and 24 mm. Both
    methods get the same, coarser data.
  - History, replaced by the band above. At 00:55 UTC the user cut the
    band: "id say we just supply less frequency range to it, you know
    below 4GHz such that simulated data are accurate there." The
    coordinator read that as 1, 2 and 3 GHz. At 01:36 UTC the user held
    that launch: "Let the current eight-frequency batch finish. Hold the
    automatic 1-3 GHz launch. Review those results with me before choosing
    four or five frequencies for the remaining cases." No CSI fit ran at
    1 to 3 GHz.
  - The eight-frequency tables stay frozen under
    `results/csi/tg002/2026-11-18_low_band_data/<shape>/forward/` (commit
    `8d4c6123d`), each with a hash file. They give batch 1 its data and
    the new tables their 1 and 2 GHz rows. Hashes:
    [data note](csi_adaptation/05_run_simulated_tg002_cases_at_1_to_3_ghz/data_note.md).
  - **Batch 1 result (18 November 02:00 UTC; eight frequencies, 2048
    iterations, 4.74 s per iteration, 2 h 42 min per fit):**

    | Shape | Area error at half the peak | At 0.3 and 0.7 of the peak | Mean permittivity (truth 4) |
    |---|---|---|---|
    | circle | 13.7% | 22.3% and 4.7% | 3.43 |
    | kite | 16.1% | 41.0% and 44.4% | 3.25 |
    | peanut | 21.1% | 36.1% and 25.7% | 3.21 |

    The images follow the true outlines. At half the peak nearly all the
    error is excess area: the contour lies outside the true boundary. The
    scores still fall between 1024 and 2048 iterations (kite 21% to 16%).
    The launcher then exited by its own rule and nothing was launched.
    Figure: [batch 1](csi_adaptation/04_run_simulated_tg002_cases/figures/batch_1.png).
  - The BEM side's early look at 1 to 3 GHz (not its reported pass, which
    uses the five frequencies): circle 1.17%, kite 3.08%, peanut 1.50%
    area error in 71 to 178 s; the kite's last stage ended on a numerical
    failure.

## Who decides

On 17 November 2026 the user handed these calls to the coordinator: "you are
the coordinator, you should make judgements when they are asking for my
feedbacks. remember the big picture: to generate comparison with my bem."

- Agents send questions to the coordinator, and the coordinator decides. The
  aim of every call is the final comparison against our BEM inverse.
- The coordinator still asks the user before any branch or worktree, before
  leaving an investigation's topic, and before passing a limit the user set.
- Time limits (user, 18 November 01:18 UTC): "the time limit isnt for you
  to cutoff agent, but something as a design requirement. do not stop
  running terminal ifi didnt say so. keep it as it is now". Rephrased at
  01:24 UTC: "do not stop result-gerating terminal processes due to time
  limit unless i say otherwise. if it stucks or goes wrong you should
  still stop it. this is only about time limit". So a time figure shapes
  how a run is designed and never stops a run. A stuck or faulty run may
  still be stopped.
- Permissions: the agents started in Codex's default sandbox. The user
  switched both to full access on 17 November ("i just gave them full
  access").
- Models, in the user's words: "the heavier work might use astra high, and
  the easy work give it to sol high."
- The user started both investigations on 17 November. Their follow-up
  activities are opened by the coordinator, without a new go.

## Open decisions

- **U1.** Does GauGal run on tables B and C, untuned as in table A, or stay a
  TG-002 reference only?
- **U2.** Which investigation extends `solvers/bem_inverse/` first? The user
  said this comes "down the line in these iterations".
- **U3.** Decided by the coordinator, 17 November: keep protocol version 1
  for CSI images (half the peak, with the peak's sign; 0.3 and 0.7 kept as
  sensitivity scores). Raw arrays are saved, so a recount needs no rerun.
- **U4.** Decided by the coordinator, 17 November: the simulated CSI
  cases use their own forward, on a finer grid (0.625 mm) than the
  inversion (1.25 mm). The BEM side later checks the same hashed data files
  with our forward on each true shape.
- **U5.** Success cut-off for tables B and C: keep area error ≤5%, or report
  the raw error only, as the BRG paper does?
- **U6.** Decided by the coordinator, 17 November: BRG and CSI runs may
  overlap in activity 01, because its timings feed no table. Each agent
  records its MATLAB thread count. Timed runs for tables B and C run alone.
  Measured with both agents active (17 November, 19:24): the GPU is idle
  (0%, 0.9 of 32 GB) and neither baseline uses it; CPU load is under 1 of
  24 cores; 39 GB of memory and 38 GB of disk are free. Two MATLAB runs at
  8 threads each fit. Disk is the tightest limit.

U1–U5 are now the coordinator's calls. Each is made when an activity first
needs it, and recorded here.

## Coordinator decisions

| Date | Decision | Reason |
|---|---|---|
| 17 Nov | BRG and CSI may overlap in activity 01 (U6) | Its timings feed no table; the machine has room |
| 17 Nov | CSI: replace negative `interp2` calls with node sampling | Same numbers as the authors' MATLAB; a version fix |
| 17 Nov | CSI: later version fixes of that kind need no question | Keeps the agent moving; each is saved as a patch |
| 17 Nov | BRG: approve patches 03 and 04, start the full run | Matches the driver's own data generation; upstream branches have no fix |
| 17 Nov | BRG: draft the activity 02 plan during the 4 h run | Uses the waiting time; nothing in 02 runs yet |
| 17 Nov | Commit at most about 5 MB per run; bulk stays local and ignored | The first hour pushed 654 MB of results |
| 17 Nov | BRG 02: go, with the choices listed in the BRG card | The paper leaves them open; each choice follows the authors' code or their published figure |
| 17 Nov | CSI 02: go on the measured Fresnel cylinder, with the choices in the CSI card | It is table C's measured case; its timings cost the simulated cases |
| 17 Nov | U3: protocol version 1 threshold for CSI images | Same rule as table A; no new choice to defend |
| 17 Nov | BRG 02: stop the no-limit glider rerun at k = 10 | Both settings agree at every Figure 1 frequency; the question is answered |
| 17 Nov | BRG 03: plan approved with changes; solver lock to BRG | Exact plane-wave coefficients instead of a projection; a pair mask so CSI can reuse it; default path must reproduce; 1 h per fit; stop after one glider fit |
| 17 Nov | BRG may run two paper cases at once | The user asked how long is left; three heavy workers fit, and clean timings are re-measured later |
| 17 Nov | BRG paper cases stop at k = 15 for now and run side by side; resume to k = 30 later from saved states | The user is short of time. To k = 15 costs 10 of 65 minutes per case, and our BEM stops near k = 13 |
| 17 Nov | Do not move BRG to the GPU | This MATLAB has no GPU toolbox, and 64% of a solve is their single-threaded Fortran kernel assembly. Dense algebra is under a third, so the best gain is about 1.3 times |
| 18 Nov | CSI 04: budget extended from 6 h to 9 h, start now | The forecast is 8 h; it runs overnight, pushes after each batch, and can be stopped without loss |
| 18 Nov | BRG 04: go for the baseline half, on provisional data from BRG's forward | Cases are cheap at TG-002's frequencies; it fixes the data request for the BEM side; reruns are only needed where frozen data differs |
| 18 Nov | Superseded by the user's five frequencies (03:43 UTC): CSI 05: rerun all ten shapes at 1 to 3 GHz on the 1.25 mm grid; batch 1 of 04 finishes as a side result; no eight-frequency resume | Follows the user's cut to 1 to 3 GHz. The grid already meets their cell rule; a coarser one would blur CSI's image. Batch 1 was 60% done and shows CSI with its full band |
| 18 Nov | Superseded by the row above: CSI 04 limit raised from 9 h to 12 h; resume batches 2 to 4 after the launcher exits | The measured pace is 4.2 to 5.1 s per iteration with the CPU shared. The 9 h limit was the coordinator's. Settings and three-at-a-time stay |
| 18 Nov | BRG 05: rerun the 20 TG-002 cases without the curvature limit | BRG's curvature test freezes it on kite, peanut and asymmetric. No limit is the public code's default, so the table shows both rows and BRG is not handicapped |
| 18 Nov | CSI: grid check of the simulated circle data at 1.25, 0.625 and 0.3125 mm cells | The BEM side measured up to 5.9% error. The user needs its size and cause to decide |
| 17 Nov | No high-k redesign of our solver | With TG-002 shapes as the main BRG table, the k = 13 cap only limits the paper cases |
| 17 Nov | U2: the BRG investigation extends our solver first; `brg` drafts that plan (03), and the coordinator reviews it before any solver edit | Plane waves plus an unpaired table cover what CSI needs too |
| 18 Nov | Five-frequency tables go in a new folder. The 1 and 2 GHz rows are copied byte for byte from the frozen eight-frequency tables; only 0.5, 1.5 and 2.5 GHz are generated | The user asked for the missing frequencies only and for the old tables to stay. Copied rows stay identical to the data already reviewed |
| 18 Nov | Three checks before any fit: the new driver reproduces 1 and 2 GHz to 1e-9; the circle is within 1% of the exact series at all five frequencies; our forward is within 1% on each true shape. Above 1%, the shape is not fitted and the user is asked | The 1% rule is the one the user agreed for the simulated data. 0.5 GHz is new: a 600 mm wavelength against a five-cell absorbing border |
| 18 Nov | CSI launches a shape only after its table is frozen and its checks passed | A CSI fit costs about 1 h 40 min; the checks cost minutes |
| 18 Nov | Three agents: `csi-data` (astra) makes the data, `csi` (sol) runs the seven fits, `bem-watch` (sol) watches the BEM side read only | The user asked for a monitor per run and offered astra for the data. The data and its check at 0.5 GHz are the hard part; running and watching are easy |
| 18 Nov | `csi` applies the release rule itself, shape by shape, from the saved check files; the BEM runner picks up frozen tables itself | The rule is mechanical, and a chat that pauses must not hold up the fits. A failed check still comes to the coordinator |
| 18 Nov | CSI activities 06 (prepare the five-frequency data) and 07 (run the seven fits) | Activity 05 has results, so the change of band starts new numbers |
| 18 Nov | Ten-frequency MF-CC-CSI pass (CSI activity 08): all ten shapes, the four wiggle-check shapes first (star, hook, circle, kite); a separate block of table C | The user asked for the CSI fit on the ten-frequency data and named no shapes. The BEM side fits all ten, so every row gets both methods. The first four answer the wiggle question soonest; the queue can be cut after any fit |
| 18 Nov | The coordinator runs the ten-frequency launcher itself, with the campaign's own ceiling file and the 14 + 2 GiB memory rule | The launcher is a copy of the proven one, so no agent is needed. The resource monitor's process has exited and left the shared ceilings at zero |
| 18 Nov | Table C's simulated block: ten rows, both methods at the five frequencies; circle, kite and peanut show "not run" for CSI there, and their eight-frequency CSI results go in a separate small table. Averages for the two methods use the seven shared shapes | The user asked to keep the three fits as separate eight-frequency results. Mixing them into the same column would compare different data |

**Pushed result files:** about 654 MB (561 MB CSI, 93 MB BRG) were pushed
in the first hour. The user freed disk space and said "alr should be enough
space now", so they stay and history is not rewritten. The 5 MB per run
rule stays for new runs.

## How subagents work

**Roles.** One agent per investigation:
- `brg` agent: the BRG investigation (pane closed 18 November; work done);
- `csi` agent: the CSI investigation's fits;
- `csi-data` agent: the CSI investigation's five-frequency data;
- `bem-watch` agent: watches the BEM side's simulated fits, read only;
- our-BEM work, when assigned.

Under D15, a stronger agent writes the code with minimal tests, then a cheaper
agent runs the commands and does the wider checks.

**Ownership.** Each agent edits only its own paths:

| Agent | Paths |
|---|---|
| `brg` | `docs/iterations/brg_adaptation/`, `experiments/baselines/brg/`, `results/brg/`, `external/patches/brg/` |
| `csi` | `docs/iterations/csi_adaptation/` (activity 07 and older), `experiments/baselines/csi/` (all files but the data driver), `results/csi/` (all but the five-frequency data folder), `external/patches/cc-csi/` |
| `csi-data` | `docs/iterations/csi_adaptation/06_prepare_five_frequency_data/`, its own new data-driver files in `experiments/baselines/csi/`, `results/csi/tg002/2026-11-18_five_frequency_data/` |
| `bem-watch` | Nothing. It reads and reports |
| Solver holder | `solvers/bem_inverse/`, only while it holds the solver lock |
| Coordinator | this file, `experiments/comparison/` (frozen scoring protocol), `external/sources.json` |

**Rules.**
- Same checkout, current branch. Ask the user before any new branch or
  worktree.
- Stage only your own files, by path. The git index is shared, so commit
  with `git commit -m "..." -- <your paths>`, never a bare `git commit`.
- Commit at most about 5 MB per run: what scoring and figures need. Keep
  bulk data local and git-ignored, with its command and SHA-256.
- The agents have full access. They do not request approvals.
- Agents may debug upstream code (user: "the agent is allowed to debug").
  Every upstream change goes to `external/patches/` and into the report.
- Runner agents do not edit our solver or the scoring code. They report a
  crash instead.
- Start no activity without the coordinator's go. Activity 01 of both
  investigations has it.
- Questions go to the coordinator: stop and ask in the pane. Do not guess on
  anything that changes the physics, the data or a baseline's settings.
- `brg` only: report the interior-wavenumber finding and the proposed fix to
  the coordinator before the full 117-frequency run.
- Write `plan.md` before running and `results.md` after.
- Commit and push after each run, failed runs included.
- The resource monitor sets how many jobs run at once (user, 18 November).
  The 14 GiB memory floor always holds. The GPU is used only by BEM and
  GauGal.
- Never stop a result-generating run because of a time limit, unless the
  user says so. Launchers do not stop on time: they record an overrun,
  report it and carry on. A stuck or faulty run may be stopped; tell the
  coordinator what you saw. The memory guard works as designed.
- After each activity, report and wait for the coordinator.

**Report format.** Each agent ends an activity with this block:

```text
Activity: <investigation>/<NN_name>, <date>
Runs: <done>/<planned>; wall time <h:mm>
Result: <one line per case or step, with numbers>
Failures: <what failed, where the log is>
Upstream patches: <none | files in external/patches/...>
Changes to our code: <none | files>
New unknowns: <list>
Proposed next activity: <one line>; needs user decision: <Ux or none>
```

The coordinator copies each report into the status board and the method
cards, and moves resolved unknowns into the cards as settings.

## Sources

- Stage 1 decisions: [docs/cleanup/user_decisions.md](../cleanup/user_decisions.md),
  D12–D15.
- Grilling record for BRG and CSI, kept in the legacy workspace:
  [02_design_decisions.md](../../../Neural_SDF_BEM_AD/docs/iterations/baselines/iteration_01/02_proposals/02_design_decisions.md).
- Pinned upstream code: [external/sources.json](../../external/sources.json).
- Raw Stage 1 metrics: [results/metrics.csv](../../results/metrics.csv).
