# Coordinate the BEM side

This file is the plan for the BEM side of the final comparison: fitting
our BEM inverse to the data that BRG and MF-CC-CSI use. The baseline side
(their code and their runs) stays in
[coordinate_final_comparison.md](coordinate_final_comparison.md).

It is a temporary second file. The user: "i would prefer to use one
coordination file, but temporarily to avoid the current coordination file
being too long you can have a new one". Merge it back when the work is done.

**State, 18 November 2026, 07:51 GMT:** a fresh coordinator took over at
02:03, after the user restarted the chat ("you have a lot of context so i
plan to start you fresh"). Table B1: all 40 fits are done (04:09) and all 20 data
checks pass. The last fit, `aphex_twin__c4` with recovered contrast, gave
0.45%. Two fits failed in quality, both `aphex_twin` with known
contrast: 15.1% at contrast 0.5 and 33.2% at contrast 4 (94 minutes).
Table C, simulated: the user chose 0.5, 1, 1.5,
2 and 2.5 GHz for all ten shapes at 03:39. The wrapper and the
[plan](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md)
are in use. All ten tables are frozen and all ten 1% checks pass (04:04,
worst 0.71%). The GPU fits run since 04:04, one beside the B1 fit (the
resource monitor raised the BEM ceiling to two at 04:04; one since 04:10).
All ten GPU fits are done (05:10): area error 0.97 to 5.96%, contrast within
0.14% of 4. The ten CPU cross-checks are done (05:34): each stops at 120 s,
and agrees with the GPU fit on every stage both finished. Every BEM table is
now filled; nothing is running on the BEM side.
The baseline side's seven five-frequency MF-CC-CSI fits ended 07:47, no
failure; both methods' numbers are in the main file ("Table C, simulated
shapes: the numbers"). On the seven shared shapes: BEM 1.29 to 5.96% area
error, MF-CC-CSI 3.72 to 23.36%. The machine is quiet since 07:47 and the
monitor's ceilings are all 0 (07:48). The clean timed GPU pass waits only
for the user's go.
A later restart begins at [Start here](#start-here) too.

## Start here

For the coordinator who picks this up, in pane `w2:p1`.

**Who is alive** (Herdr workspace `w2`, same checkout, branch `organised`):

| Agent | Pane | Model | State at 02:02 | Reads first |
|---|---|---|---|---|
| `bem-b1` | `w2:p9`, top right | Codex `gpt-6-astra`, high, full access | Queue released 02:11, two fits at a time: known row on every checked case, then the recovered row; late cases join when their checks pass. 39 of 40 fits done at 04:07. `aphex_twin__c4` known contrast ended 04:06 after 94 min (33.2%, a failed fit); its recovered fit ended 04:09 (0.45%). All 40 fits are done. Final report reviewed and accepted 04:53; its note on the two stalled fits is in ([note](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/aphex_known_contrast_stall.md)). Idle with clean paths; nothing more is asked of it, so the pane may be closed. Ceiling four fits since 02:22. Then it reports and stops. Its `watch-checks` loop waits for the last three BRG manifests. It stops only for a failed check, a crash, a repeating memory requeue or a decision. Do not clear it | Its brief is in its pane; its files are in [06](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/) |
| `bem-csi-run` | `w2:p8`, bottom right; cleared 01:59 | Claude Sonnet, high, permissions bypassed | Done 05:34: ten checks, ten GPU fits, ten CPU cross-checks, [results](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/results.md) accepted. Idle; nothing more is queued, so the pane may be closed. Briefed 03:59 for the five-frequency pass; go for the checks 04:01. It checks each shape when its table is frozen (`<shape>/manifest.json` says `frozen` and the `.sha256` is there), commits each check at once, then fits by a detached waiter that re-reads `results/csi/resource_policy.json` before each launch. It reports the circle check, the check table, the first fit and the end | `AGENTS.md`, this file (Limits, Working with the coordinator), the [07 plan](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md), "State at handoff" in [04 results](adapt_bem_to_baseline_data/04_fit_csi_cases/results.md), the hand-over in [03 results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md) |

Closed, work finished and committed: `bem-gpu` (closed by the user),
`bem-brg` (Codex session `01a1ec04-8da6-75b3-a234-97134f6d1105`, for
`codex resume`), `bem-csi` (Claude session
`cdb198b2-5f13-44a1-9f6d-6b0080654e9e`, for `claude --resume`). Reopen one
only if its own code needs a fix.

**Nothing of the BEM side runs detached**, except what `bem-b1` starts. The
MATLAB jobs on the machine belong to the baseline side; leave them.

**No watcher survives the restart.** Re-arm one first:
`"$HERDR_BIN_PATH" agent wait bem-b1` in a background shell. Load the
`herdr` skill; `herdr` is not on the shell's path, so use
`"$HERDR_BIN_PATH"`.

**Results so far** (GPU passes; details in the status board and the
activity results):

| Table | Case | Our BEM | Baseline, for reference |
|---|---|---|---|
| B2 | `glider_033` | 0.061% area error at k = 15, 71 s | BRG 0.052% |
| B2 | `glider_10` | Failed: 14% at k = 12, lost from k = 1.75 | BRG 0.004% |
| B2 | `star_full` | 0.58% at k = 15, 334 s | BRG 0.52% |
| B2 | `star_limited` | 0.60% at k = 15, 274 s | BRG 0.81% |
| B2 | `cavity_09`, `cavity_2` | Skipped by the user (series limit) | BRG 134% |
| C | Measured cylinder | Default fit stalled: radius 19.0 mm against 15, permittivity 2.19 against 3, area error 67.8%. The adapter is cleared | MF-CC-CSI +4.2% support area, 2.73 |
| C | Simulated circle, kite, peanut, 1 to 3 GHz (early look, not the reported pass) | 1.17%, 3.08%, 1.50% area error; contrast within 0.04% of 4 | CSI's three eight-frequency fits stay as separate results |
| C | Simulated, all ten shapes, 0.5 to 2.5 GHz in five frequencies (the reported pass) | 1% checks pass on all ten (04:04): worst 0.71% (`aphex_twin`, 2.5 GHz); the other nine at most 0.44%. All ten GPU fits done 05:10, every schedule completed. Area error: circle 0.97%, kite 3.80%, peanut 1.54%, star 2.34%, asymmetric 1.29%, c_shape 2.60%, hook 3.59%, cross 2.10%, cog 2.86%, aphex_twin 5.96%. Contrast found 3.997 to 4.005. 47 to 247 s and 1464 to 4477 work units per fit; host peak 1.87 GiB. CPU cross-checks (120 s cut): same loss as the GPU to 4e-9 relative and the same step counts on every stage both finished (5 to 7 per shape) | MF-CC-CSI, seven shapes, same tables (07:47): 3.72% (star) to 23.36% (`aphex_twin`), median 13.29%; above BEM on every shape. Numbers for both methods: main file, "Table C, simulated shapes: the numbers" |
| B1, known contrast | 17 of 20 cases (02:20) | Every fit completed its schedule. Area error at most 0.29% (`cog__c0.5`), under 0.1% on the other 16, median 0.04%. 7 to 115 s and 274 to 4585 work units per fit | BRG, same 17 cases: 6 under 5% (main file, BRG activity 04) |
| B1, recovered contrast | 17 of 20 cases (02:26) | Every fit completed its schedule. Area error at most 0.21% (`cog__c0.5`), under 0.1% on the other 16, median 0.03%. Contrast within 2e-6 of the truth, relative. 9 to 96 s per fit | None; BRG is given the contrast |
| B1 | `cog__c4` | 0.038% area error in both rows (40 s and 56 s); contrast found 4.0000001 | |
| B1 | `aphex_twin__c0.5` | Known contrast: 15.1% area error, a stalled fit, kept as a failure (1431 s, loss stuck at 8.4e-5). Recovered contrast: 1.14%, contrast 0.49989, 147 s | |
| B1, both rows | All 20 cases (04:09) | 40 fits, all completed their schedule. Known contrast: 18 cases at most 0.29%; `aphex_twin` fails at both contrasts (15.1%, 33.2%). Recovered contrast: all 20 at most 1.14% (`aphex_twin__c0.5`), 19 at most 0.45%; contrast within 2.2e-4 relative on `aphex_twin__c0.5`, within 3.2e-6 on the rest | BRG: main file, table B1 |
| B1 | `aphex_twin__c4` | Known contrast: **33.2% area error, a failed fit** (schedule completed, 1546 work units, 5628 s; loss stops at 0.075). Recovered (04:09): 0.45% area error, contrast 4.000012, 133 s, 3592 work units | |

**What to do next, in order:**

1. Done 02:05 for the 16 cases BRG has saved: data checks reviewed, go
   given for the first known-contrast fit (`circle__c4`). Still to review:
   the checks of `cog` and `aphex_twin` when they arrive, by the same
   limits (1e-6 between our resolutions, 1% between the two copies). Above
   1%, a refinement failure or a series refusal on a true shape: ask the
   user before fitting that case.
2. Done 02:11: first fit reviewed (0.024 s per work unit, 1.94 GiB host
   peak, 1.37 GiB on the GPU) and the queue released at two fits at a time.
   A resource monitor (Codex, pane `w3:p1`) rechecks the machine every ten
   minutes and may send a new allocation into this pane; raise or lower
   `bem-b1`'s concurrency by it and by what memory allows (`free -g`,
   14 GiB floor). No stop on elapsed time; a fit stops only if stuck,
   faulty or short of memory. Read `bem-b1`'s results as they land:
   [06 results](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/results.md).
3. BRG's observations exist for 17 of the 20 B1 cases (02:12). `cog__c4`
   is running in BRG's completion run. Both `aphex_twin` cases failed at
   start there, in the baseline wrapper's own interior-point check, before
   any data; the baseline side reruns them after a wrapper fix (main file,
   BRG activity 04). A case counts as ready when its `bulk_manifest.json`
   lists all 37 data files and the hashes match; a manifest without them
   means "inputs pending".
4. Done 05:35: simulated CSI cases, the reported pass. The user's list
   (03:39): 0.5, 1, 1.5, 2 and 2.5 GHz, all ten shapes. Ten 1% checks pass,
   ten GPU fits and ten CPU cross-checks are in:
   [plan](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md),
   [results](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/results.md),
   evidence in `results/bem/baseline_data/csi_five_frequency/2026-11-18/`.
   The settings live in `experiments/bem_on_baseline_data/csi_fit.py` and
   `csi_data.py`. The monitor's ceilings are in
   `results/csi/resource_policy.json`; any BEM launcher re-reads it before
   each launch and counts memory as
   `experiments/resource_management/watch_comparison.py` does.
5. Done: the main file's tables B1, B2 and C carry the BEM states. Keep
   them current; edit only the BEM text there, after re-reading it.
6. All four BEM tables are now filled (B1, B2, C measured, C simulated).
   What is left:
   - Close the idle panes `bem-b1` and `bem-csi-run` (their paths are
     clean; check `git status` first).
   - Done 07:47: the baseline side's seven CSI fits are in, and its
     coordinator wrote both methods' numbers into the main file. The BEM
     column there was checked against our `metrics.json` files at 07:51.
   - The machine is quiet since 07:47 (no baseline job, no BEM job). One
     clean timed GPU pass for the reported fits can now run (commands are
     in the 02, 03, 06 and 07 results). Ask the user before starting it.
     The monitor set every ceiling in `results/csi/resource_policy.json`
     to 0 at 07:48; with a go, ask it (`agent prompt w3:p1`) for one BEM
     slot first. A timed pass writes new attempts beside the reported
     ones; it replaces times only, never a reported score.
   - Then merge this file back into the main file.

**Working notes from the first session:**

- Take every recorded time from `date`. Agents' own clock guesses were up
  to ten minutes off.
- Idle is not finished. An agent's turn ends while its detached fit still
  runs, and one agent sat idle for 24 minutes after its fit had ended.
  After a wake-up, check the process list and the log. To wait across the
  gap: `agent wait <name> --until working`, then `agent wait <name>`.
- A resource monitor runs in pane `w3:p1` (Codex) since about 02:09. It
  says the user asked it "to monitor machine use and adjust running/queued
  tasks every 10 minutes". It sends allocations into this pane; they arrive
  as pasted text. It sets how many fits may run, not what they compute.
  At 02:22 it sent a ceiling of four fits straight to `bem-b1`, because
  this pane held typed input; `bem-b1` reports such changes in its pane.
- The baseline coordinator (pane `w1:p1`) relays user decisions into this
  pane, marked "not from the user". Read the user's own words in its pane
  before acting on one, and record where they were given.
- A pane's screen shows only its last page. To read the user's own words
  in another pane, search the session records:
  `~/.claude/projects/-home-drdeng-Neural-SDF-BEM-AD-organised/*.jsonl`
  (Claude panes) and `~/.codex/sessions/2026/11/18/*.jsonl` (Codex panes).
- The resource monitor's pane has no Herdr access: it cannot send notices.
  Its ceilings for new launches are in `results/csi/resource_policy.json`
  (`max_bem_fits`, memory rule: available minus 4 GiB per BEM fit stays at
  or above 16 GiB). It can be prompted: `agent prompt w3:p1 "..."`. It
  answers in that file.
- The baseline coordinator runs a read-only agent, `bem-watch` (workspace
  `w1`), that reads our five-frequency result files. It never edits our
  files and never prompts our agents.
- Do not `cd` into a subfolder in the coordinator's shell; the working
  directory sticks. Use paths from the repository root.
- Agents commit by path in a shared checkout. Check `git status` for an
  agent's paths before closing its pane.

## Your role

The user: "you are to act as the bem side coordinator and use subagents to
adapt bem to compare with brg and mf-cc-csi on their own datasets."

- You answer the agents' questions yourself. The aim of every call is the
  comparison against our BEM inverse.
- You review choices. The user: "you as coordinator, especially a reviewer
  of choices made by the csi code writing agent."
- You approve every edit to default-path solver code, before and after
  (see [Solver rules](#solver-rules)).
- You may edit the main coordination file (user: "you can edit that file").
  Touch only the BEM rows and the lock paragraph, and re-read it first:
  the baseline coordinator edits it too.

Ask the user before any of these:

- a new branch or worktree;
- leaving the scope below (table B1, noise runs, GauGal);
- passing a limit in [Limits](#limits);
- the default TG-002 result changing at all after a solver edit;
- grid error above 1% in the simulated CSI data;
- a method change beyond a bug fix;
- a physics or data convention in doubt;
- a BRG case that still stops below k = 15.

## Scope and order

| Order | Work | Table | Data | State |
|---|---|---|---|---|
| 1 | Table path on the GPU | all | none | Done 18 Nov; default fit unchanged on CPU and GPU |
| 1 | BRG paper cases, known contrast, to k = 15: two gliders and two stars. The two cavity cases are skipped (user, 18 Nov) | B2 | Saved by BRG, ready | GPU pass done; follow-up checks running |
| 1 | Measured Fresnel cylinder `dielTM_dec8f` | C | Ready | Not started |
| 2 | Ten TG-002 shapes at contrast 4, simulated in the Fresnel layout, at 0.5, 1, 1.5, 2 and 2.5 GHz (the user, 18 Nov 03:39 UTC) | C | Being made by the baseline side: `results/csi/tg002/2026-11-18_five_frequency_data/` (8820 rows per shape). The eight-frequency tables stay in `2026-11-18_low_band_data/` | Early look at 1 to 3 GHz on three shapes (kept apart). Reported pass prepared; waits for the tables |
| 3 | TG-002 shapes with BRG's plane-wave data: 10 shapes at contrasts 0.5 and 4, known contrast then recovered contrast | B1 | BRG's saved observations, `results/brg/tg002_shapes/2026-11-17/<case>/local/` | Opened by the user 18 Nov; `bem-b1` preparing |

Table B1 was held until the user opened it on 18 November. What was
agreed for it:

- Two copies of the data are made, one by BRG's forward and one by ours,
  and compared on every true shape before any fit. The user: "i thought we
  make two copies then compare".
- Both methods then fit the BRG-made copy, so our BEM never fits data from
  its own forward.
- The baseline side already runs BRG on its own copy and calls it
  "provisional" (BRG activity 04). If the copies agree, those runs stand.

## Agents

All four run in Herdr panes with full access. The Claude agents run as
their own Claude Code sessions with permissions bypassed, which matches
Codex full access. The user's words on staffing: "one astra work on gpu
bem, one sol work on cpu bem running on brg cases; then one claude opus
high work on csi, and one claude sonnet high to monitor csi once opus is
donw".

| Agent | Pane | Model | Starts | Job | May edit the solver |
|---|---|---|---|---|---|
| `bem-gpu` | closed by the user, 18 Nov about 01:10 | Codex `gpt-6-astra`, high | At launch | Make the table path run on the GPU | Yes, it holds the lock |
| `bem-brg` | closed by the coordinator, 18 Nov 01:59, work committed | Codex `gpt-6.1-sol`, high | At launch | Fit the six BRG paper cases | No |
| `bem-csi` | closed by the coordinator, 18 Nov 02:00, work committed | Claude Opus, high | At launch | Write the CSI adapter, run its first checks and first fit | Only if given the lock after `bem-gpu` |
| `bem-csi-run` | `w2:p8`, bottom right; cleared 01:59 | Claude Sonnet, high | When the adapter passes review | Run and watch every BEM fit on CSI data | No |
| `bem-b1` | `w2:p9`, top right | Codex `gpt-6-astra`, high | 18 Nov, when the user opened B1 | Fit our BEM to the 20 BRG-generated TG-002 cases: data checks, known-contrast row, recovered-contrast row | No |

`bem-csi-run` watches our fits only. The baseline's MATLAB campaign belongs
to the `csi` agent.

## Working with the coordinator

Rules the coordinator added at launch. They apply to all four agents.

- Questions go to the coordinator: stop and ask in your pane. The
  coordinator watches every pane. Do not ask the user, and do not request
  approvals; you have full access.
- Never edit this file or the main file. Report, and the coordinator
  updates them.
- Python is `/home/drdeng/miniconda3/envs/EMNerf/bin/python`, run from the
  repository root.
- Every run records the commit hash and whether `solvers/bem_inverse/` is
  dirty (`git status --porcelain -- solvers/bem_inverse`). A fit started
  while it is dirty is marked so and is not a reported result.
- Memory is the tight resource. At launch 21 GB was available and the
  guard stops runs below 14 GB, so the three BEM agents share about 7 GB
  until the CSI campaign ends. Measure the peak memory of your first run.
  Start a run only if it leaves 16 GB available. If memory blocks you,
  say so in your pane.
- The GPU belongs to `bem-gpu` until it reports. Others use the CPU.
- CPU cores are nearly full too (load 23 of 24 at launch, from the
  baseline campaigns). Pin BLAS to one thread per fit and count the idle
  cores before starting parallel fits.
- End each activity with the report block from the main file
  ("How subagents work").

### Launch log

18 November 2026, 00:18 GMT. Launched from pane `w2:p1` with Herdr:

| Agent | Command |
|---|---|
| `bem-gpu` | `codex -m gpt-6-astra -c model_reasoning_effort="high" --dangerously-bypass-approvals-and-sandbox` |
| `bem-brg` | `codex -m gpt-6.1-sol -c model_reasoning_effort="high" --dangerously-bypass-approvals-and-sandbox` |
| `bem-csi` | `claude --model opus --effort high --dangerously-skip-permissions` |

- Instruct with `herdr agent prompt <name> "..."`; be woken by
  `herdr agent wait <name>` in a background shell.
- The baseline coordinator is the Claude session in pane `w1:p1`. It wrote
  the lock paragraph itself at 00:15 ("The user started the BEM side
  then"), so no message was sent.
- The empty activity folders already existed at launch.

## Decisions made with the user

Made on 17 and 18 November 2026. Where no words are quoted, the user
answered "yes" to the coordinator's recommendation as written here.

| Topic | Decision | User's words |
|---|---|---|
| Scope | Tables B2 and C now; B1 held | "on their own datasets" |
| Staffing | By dataset, four agents as above | Quoted under Agents |
| Access | Full access for every agent | "full access" |
| Top frequency on BRG cases | Our BEM should reach k = 15, where BRG's runs stop for now | "our bem stop at 15 would look better" |
| How to reach k = 15 | Set the series limit to 1e-6 on BRG paper cases. The TG-002 default stays 1e-9. Use 1e-6 on CSI cases only if 8 GHz is refused. Propose a solver redesign only if a case still stops below 15 | yes |
| GPU | Our default runs on the GPU, so the table path should too. Do it first, not on a trigger | "i dont think gpu is that much work, given our default bem should be ran in gpu"; "you have my permission to touch the frozen default" |
| Default-path edits | Allowed, with the coordinator's approval, and general | "you as coordinator would need to approve it, you must understand that we also run this bem on other datasets so it cant be a local optimisation" |
| Reported result | The GPU pass. The CPU pass is an early look and a cross-check. Flag any case where the two outcomes differ | yes |
| Machine | Use all of it. No fixed worker count; only the memory guard | "its just me using this machine so try use every drop of it" |
| Fresnel calibration | CSI's own rule and factors; same mask; fields conjugated for our time sign; no amplitude fit of our own | yes |
| Start and settings on CSI cases | Default method unchanged: centred 65 mm circle, no localization, recovered contrast, real data | yes |
| Start and settings on BRG cases | Unit disk, known contrast, as set in the main file | yes |
| Noise level | The solver is told none, on measured and simulated data. It stops on its step and budget rules | yes |
| Measured and simulated | Keep both. The measured cylinder is the real-data check; the simulated shapes are the shape comparison | yes, after asking why |
| Grid error | Measure our forward against the simulated data on the true circle first. At or below 1%, go on. Above it, stop and ask the user | yes |
| Adapting | One frequency rule per dataset, fixed before any fit, from the data's wavenumbers only. One pass. Failures stay in the table. No per-case tuning. Bug fixes are allowed; record the rerun | yes |
| Solver lock | One writer at a time. `bem-gpu` first | yes |
| Review stops | Three for the CSI writer, listed below. Send the user a short summary at each; do not wait | yes |
| Done | Per-fit raw metrics from the unedited scoring, a `results.md` per activity, this status board. Final tables stay in the main file. No claims | yes |
| Simulated CSI data, 18 Nov 00:55 UTC | The ten simulated shapes use the 1, 2 and 3 GHz rows only, for CSI and for our BEM. The retained eight-frequency files stay as they are. The measured cylinder keeps all eight frequencies. Given in the baseline coordinator's pane after the circle failed the 1% rule; the BEM coordinator read the words there | "id say we just supply less frequency range to it, you know below 4GHz such that simulated data are accurate there" |
| Series limit, 18 Nov about 01:03 UTC | No solver change. Cases that the series limit stops are skipped: `cavity_09` and `cavity_2` (refused above k = 8 on the true shape). The coordinator's reading for the rest: a case refused by the series limit inside its fit is not rerun, and goes to the user with its last endpoint | "skip the case and similiar ones that have this problem" |
| Simulated CSI data, 18 Nov 01:36 UTC | The frequency set for the simulated cases is open again: the user reviews CSI's eight-frequency batch (circle, kite, peanut) and then chooses four or five frequencies. The 1 to 3 GHz list of 00:55 is no longer final. Given in the baseline coordinator's pane; the BEM coordinator read the words there | "Let the current eight-frequency batch finish. Hold the automatic 1–3 GHz launch. Review those results with me before choosing four or five frequencies for the remaining cases." |
| Simulated CSI data, 18 Nov 03:39 UTC | Final list: 0.5, 1, 1.5, 2 and 2.5 GHz for all ten simulated BEM cases and for CSI's remaining seven. The baseline side prepares and freezes the missing frequencies; both methods read the same files. The three eight-frequency CSI fits stay as separate results. Runs are queued with the resource monitor and never interrupt a running fit. Given in the baseline coordinator's pane (`w1:p1`) and, at 03:17 UTC, in the resource monitor's pane (`w3:p1`); the BEM coordinator read both in the session records | "Use [0.5, 1, 1.5, 2, 2.5] GHz for all ten C-simulated BEM cases and the remaining seven MF-CC-CSI cases. Prepare and freeze the missing-frequency data, and give the same observations to both methods." "Relay this to the BEM coordinator. Queue preparation, checks and fits with the resource monitor; launch as capacity allows without interrupting existing fits. Keep the previous three CSI fits as separate eight-frequency results." Earlier, to the monitor: "i need: c simulated bem, and the remaining seven mf-cc-csi to use [0.5, 1, 1.5, 2, 2.5] frequencies" |
| Time limits, 18 Nov about 01:10 UTC | Said to the baseline coordinator about its runs. Whether it also covers the BEM side's 120 s CPU cut and 1 h ceiling is asked, not assumed | "do not stop result-gerating terminal processes due to time limit unless i say otherwise. if it stucks or goes wrong you should still stop it. this is only about time limit" |
| Table B1 opened, 18 Nov about 01:45 UTC | Our BEM on the 20 BRG-generated TG-002 cases, by one dedicated agent that owns both rows: known contrast first, recovered contrast after. Both rows use BRG's saved observations. One GPU fit at a time at first; more only when the machine allows | "Open B1: BEM on the 20 BRG-generated TG-002 cases. Run the agreed data checks, then known-contrast fits first and recovered-contrast fits afterwards. Both rows must use the saved BRG observations." "Start a dedicated B1 subagent with that brief. One agent owns both comparison rows, running one numerical fit at a time initially. Increase concurrency only when machine capacity allows." |
| Capacity and time, same message | Start one GPU fit when current BEM work frees capacity; reserve its peak plus margin above the 14 GiB floor; measure the first fit before raising concurrency; recheck when the CSI batch ends. Existing jobs keep running; the simulated-CSI frequency hold stays. Elapsed-time targets are reports, not stops | "Prepare now, and start one GPU fit when the current BEM work frees capacity. Reserve its expected peak memory plus margin above the 14 GiB floor. Measure the first fit before increasing concurrency." "Recheck capacity when the current CSI batch finishes. Leave existing jobs running, keep the simulated-CSI frequency hold, and treat elapsed-time targets as reports rather than reasons to stop." |
| Baseline coordinator | Another Claude session in Herdr. Requests go through the main file; direct messages only for data requests, each recorded here | "in herdr that coordinator is just in another claude session" |

Why both kinds of CSI data: the CSI repository ships 18 measured Fresnel
files, and our method takes one object with one real contrast. Only the
single dielectric cylinder fits that. It is one circle with nominal truth,
so it cannot compare shape recovery.

## Limits

- Per fit: 13,412 work units. The 1 h wall ceiling held for the older
  passes only: table B1 and the five-frequency CSI pass have no stop on
  elapsed time (the user: time targets are reports, not stops).
- A CPU fit that passes 120 s stops and waits for the GPU path. 120 s is
  the default method's nominal fit time.
- Memory: keep 14 GB available. Wrap long runs in a guard that stops its
  own process group below that. Six 8 GB workers once killed the desktop.
- Commit at most about 5 MB per run. Bulk stays local and ignored, with its
  command and SHA-256.
- First-pass timings are indicative. A clean timed pass runs later on the
  GPU, on a quiet machine.

## Solver rules

`solvers/bem_inverse/` has one writer at a time.

- `bem-gpu` holds the lock from launch until its work is proven and
  committed. Then it closes and the lock is free.
- `bem-csi` writes outside the solver. If it needs a solver edit, it asks
  the coordinator for the lock after `bem-gpu` is done.
- `bem-brg` and `bem-csi-run` never edit the solver. They report a crash.

Approving an edit to default-path code:

1. Before the edit, the agent sends what it will change and why the change
   is general.
2. No dataset-specific branch or constant goes inside the solver. Those
   live in the wrappers under `experiments/`.
3. After the edit, three checks: the default TG-002 fit is unchanged, a
   plane-wave table works, and a point-source table works.
4. The coordinator reads the diff before the commit.

"Unchanged" means bit-identical on the CPU pin, as the `brg` agent proved
with `experiments/baselines/brg/check_default_regression.py` and
`compare_default_regression.py`. Copy those scripts; do not run them in
place, because they write into the `brg` agent's results. For the default
on the GPU, measure run-to-run repeatability before the edit and show the
result after is within it. That GPU rule is the coordinator's proposal.

If the solver's behaviour changes, update the
[information chain](../reference/inverse_information_chain.md) and the
solver README in the same commit.

## What exists already

Solver, from the `brg` agent (commits `f81719a31`, `4dde44c96`):

- Plane waves and unpaired point-source tables, each with an optional
  mask, behind `ModalSettings(table_mode=True)`. The point-source table is
  the layout CSI uses.
- The default TG-002 fit is bit-identical after those edits.
- Options, changed files and tests are listed in the
  [solver handover](brg_adaptation/03_adapt_bem_to_brg_data/results.md).

The CPU-only guard:

- `solvers/bem_inverse/forward_solvers/modal_muller.py` refuses table mode
  unless the device is `cpu` (the check in `_table_acquisition`).
- In the default GPU path, only geometry preparation (A1) and matrix
  assembly (A2) run on the GPU. Waves (A3), the linear solve, fields (A4)
  and the Jacobian (B7) run on the CPU there too.
- The new table code sits in those CPU stages. So the GPU work is small:
  lift the guard, and check the GPU geometry gives the plane-wave code what
  it needs.

The series limit:

- `ModalSettings.series_loss`, default 1e-9, in the same file. The check is
  in `a3_waves.py` (`regular_kernels`).
- The loss is machine round-off times the Bessel function I0 of k times
  the curve's wave radius. It measures digits lost in the incident-wave
  series.
- At 1e-9 the solver refuses above k times radius of about 17.7. At 1e-6
  the cap is about 24.7, which covers k = 15 for a radius up to 1.65.
- The true glider has radius 1.28. The fitted glider reached 1.52.
- 1e-6 is the size of our agreement with BRG's data (1.3e-6) and 100 times
  below the fit residual (1.3e-4).

BRG paper cases:

- One fit ran: glider eta 0.33, 0.21% area error at k = 10 in 60 s on one
  CPU thread, then refused entering k = 12.
- The run wrapper `experiments/baselines/brg/run_bem_adaptation.py` takes
  only `glider_033`, pins the CPU and has no series-limit option. So
  `bem-brg` has a small wrapper to write before it can run.
- BRG's saved data: `results/brg/paper_examples/2026-11-17/<case>/local/data_NNN.mat`,
  57 frequencies to k = 15 for all six cases. `experiments/baselines/brg/brg_data.py`
  reads it. Layout and signs are in the
  [BRG data note](brg_adaptation/01_run_published_examples/data_handoff.md).
- Cases: `glider_033`, `glider_10`, `star_full`, `star_limited`,
  `cavity_09`, `cavity_2`. BRG's own results are in
  [BRG activity 02](brg_adaptation/02_rebuild_paper_examples/results.md).

CSI data:

- Measured: `~/neural_bem_external/CC-CSI/FresnelData/The_first_opus/dielTM_dec8f.txt`.
  CSI's results on it are in `results/csi/fresnel/2026-11-17_diel_tm/`.
- Nominal truth of the measured cylinder: centre (0, +30) mm, radius
  15 mm, permittivity 3 ± 0.3. See the
  [frame note](csi_adaptation/03_prepare_simulated_tg002_cases/frame.md).
- Simulated: `results/csi/tg002/2026-11-17_campaign/<shape>/forward/synthetic_input.txt`,
  with the truth beside it. Use the retained file; do not regenerate it.
- Table layout, mask, calibration and sign: the
  [CSI table note](csi_adaptation/03_prepare_simulated_tg002_cases/pipeline.md)
  and the last section of the
  [CSI 01 results](csi_adaptation/01_run_published_examples/results.md).
- In short: 36 line sources at 0.72 m, 49 measured receivers per source
  out of 72 positions at 0.76 m, eight frequencies from 1 to 8 GHz, vacuum.
  One complex calibration factor per source and frequency, taken at the
  25th measured receiver. Their time sign is opposite to ours.

## Paths

Investigation: `docs/iterations/adapt_bem_to_baseline_data/`.

| Activity | Agent | Code | Results |
|---|---|---|---|
| `01_run_table_path_on_gpu` | `bem-gpu` | `solvers/bem_inverse/`, `pytest/bem_inverse/` | `results/bem/baseline_data/gpu_table_path/` |
| `02_fit_brg_paper_cases` | `bem-brg` | `experiments/bem_on_baseline_data/brg_*` | `results/bem/baseline_data/brg_paper/` |
| `03_adapt_bem_to_csi_data` | `bem-csi` | `experiments/bem_on_baseline_data/csi_*` | `results/bem/baseline_data/csi_adapter/` |
| `04_fit_csi_cases` | `bem-csi-run` | none; it runs the code from 03 | `results/bem/baseline_data/csi_cases/` |
| `05_lift_series_limit` | `bem-gpu` | a probe only; proposal closed, no go from the user | `results/bem/baseline_data/series_limit_proposal/` |
| `06_fit_brg_tg002_cases` | `bem-b1` | `experiments/bem_on_baseline_data/b1_*` | `results/bem/baseline_data/brg_tg002/` |

- BEM-side agents read the `brg` and `csi` paths and never edit them.
- Nobody on this side edits `experiments/comparison/`. Import its scoring.
- PNG and NPZ files under `results/` are git-ignored. Put report figures in
  the activity's `figures/` folder.
- Same checkout, branch `organised`. Stage only your own files, by path:
  `git commit -m "..." -- <your paths>`. Commit and push after each run,
  failed runs included.
- Each agent writes `plan.md` before running and `results.md` after, and
  ends with the report block from the main file.

## Briefs

Give each agent its brief, this file and [AGENTS.md](../../AGENTS.md). The
rules in [Solver rules](#solver-rules), [Limits](#limits) and
[Paths](#paths) apply to all four.

### `bem-gpu`: run the table path on the GPU

- Goal: `ModalSettings(table_mode=True)` works with the GPU device, for
  plane waves and point-source tables, masked and unmasked.
- Send the coordinator the planned change before any solver edit.
- Prove: CPU and GPU agree on predictions and derivatives for both table
  kinds; the default TG-002 fit is unchanged; the existing test suite
  passes.
- Keep it general. No BRG or CSI branch inside the solver.
- Then report, release the lock and close.

### `bem-brg`: fit the six BRG paper cases

- Write one run wrapper for all six cases from the existing one-case
  wrapper. Keep the schedule rule of the
  [BRG 03 plan](brg_adaptation/03_adapt_bem_to_brg_data/plan.md); only the
  cap moves to k = 15.
- Settings: table mode, `series_loss=1e-6`, known contrast, unit-disk
  start, `modal_muller` + `slider`, real data, no localization.
- Before each fit, check our forward on the true shape against BRG's saved
  data at every frequency the fit will use, with the thresholds of the
  BRG 03 plan.
- Rerun `glider_033` to k = 15. Its k = 10 result stays as history.
- First pass on CPU, in parallel on spare cores. Second pass on the GPU
  when `bem-gpu` is done; that pass is the reported one.
- Score with the unedited `experiments/comparison/scoring.py`. Save raw
  metrics, failures included. No tuning reruns.
- Stop and report if a case still refuses below k = 15.

### `bem-csi`: write the CSI adapter

- Goal: read CSI's seven-column table into our point-source table, with
  the same mask, CSI's calibration factors and the sign flip.
- Write outside the solver. Use the CPU table path for early checks and
  the GPU path once it exists.
- Measured cylinder first, then the simulated circle.
- Stop for review three times: after the plan, after the forward checks on
  the true cylinder and true circle, and after the first fit.
- Report the mismatch between our forward and the data per frequency. It
  is never fed into a fit.
- Hand over one resumable command per planned fit, with short run notes.

### `bem-csi-run`: run and watch the CSI fits

- Run the measured cylinder and the ten simulated shapes with the commands
  from `bem-csi`, as each simulated table is finished by the baseline side.
- Check our forward on each true shape before its fit.
- Do not change the wrapper's logic or the solver. Report a crash.
- Report after each batch.

## Review stops for the CSI adapter

At each stop, send the user a short summary and go on, unless a physics or
data convention is in doubt.

| Stop | Check |
|---|---|
| Plan, before any code | Where the calibration factors come from, and that they match CSI's branch. Conjugation of fields. Mask and row order. Vacuum constants. The start. The frequency rule, fixed from wavenumbers only. Whether any solver edit is asked for |
| Forward checks | Mismatch per frequency on the true cylinder and the true circle. The 1% rule on the circle. Whether 8 GHz passes the series limit |
| First fit | Limits kept. Raw metrics saved. No truth used by the fit. Default TG-002 fit unchanged if the solver was touched |

## Machine

- 24 cores, 62 GB of memory, one GPU with 32 GB.
- Checked 18 November, about 00:00: the GPU was idle and the load was
  about 20, from the CSI campaign's three MATLAB jobs.
- That campaign started 18 November 00:10 and is forecast at about 8 h.
  BRG's runs on TG-002 shapes started 00:40.
- Our table fits take one CPU thread each until the GPU path exists.

## Status board

| Work | Agent | State | Next step |
|---|---|---|---|
| Table path on the GPU | `bem-gpu` | Done: commit `3612f5195` at 00:32 ([results](adapt_bem_to_baseline_data/01_run_table_path_on_gpu/results.md)). Lock free. Its series-limit proposal is closed: no go from the user. The user is closing its pane | None |
| BRG paper cases | `bem-brg` | Reported GPU pass done 01:23; follow-up checks done 01:36 ([results](adapt_bem_to_baseline_data/02_fit_brg_paper_cases/results.md)). Area error: `glider_033` 0.061% at k = 15 (71 s); `star_full` 0.58% (334 s); `star_limited` 0.60% (274 s); `glider_10` failed (14% at k = 12; lost from k = 1.75). Cavities skipped by the user. CPU and GPU paths differ through the slider preparation (B6), an existing default behaviour. Agent closed 01:59 | Clean timed pass on a quiet machine; uncut CPU cross-checks if the user allows |
| CSI adapter | `bem-csi` | Done and closed 02:00 ([results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md)). Measured cylinder fitted (default fit stalled; adapter cleared). Wrapper reads the ten frozen tables; the frequency list is one setting, now (1, 2, 3) GHz; dry check shows the stage lists unchanged for what ran | None |
| CSI fits | `bem-csi-run` | Early look at 1 to 3 GHz done 01:56 ([results](adapt_bem_to_baseline_data/04_fit_csi_cases/results.md)): circle 1.17%, kite 3.08% (numerical failure in its last stage, kept), peanut 1.50%. Reported pass at 0.5 to 2.5 GHz ([plan](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/plan.md)): ten 1% checks pass (worst 0.71%); ten GPU fits done 05:10, area error 0.97 to 5.96%, contrast within 0.14% of 4 | Done 05:34: CPU cross-checks agree with the GPU on every common stage; [results](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/results.md) accepted. Left: a clean timed pass on a quiet machine |
| Table B1 | `bem-b1` | Both rows done on the first 17 cases, 34 fits, all completed and reportable. Known row (02:20): area error 1.8e-7 to 2.9e-3, 599 s of fitting in total. Recovered row (02:26): area error 9.5e-8 to 2.1e-3, contrast within 2e-6, 725 s in total. Host peak at most 2.27 GiB. Late cases: `cog__c4` 0.038% in both rows; `aphex_twin__c0.5` 15.1% known (failed in quality) and 1.14% recovered; `aphex_twin__c4` 33.2% known (failed in quality, 5628 s; ended 04:06), 0.45% recovered (contrast 4.000012, 133 s). All 40 fits done 04:09. All 20 data checks pass: worst difference from BRG 8.8e-6 (`aphex_twin__c0.5`), worst between our resolutions 7.9e-7 (`cog__c4`, limit 1e-6). Earlier: data checks pass on 17 of 20 cases ([results](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/results.md)): the two forward copies differ by at most 1.6e-7 (limit 1%), our resolutions by at most 1.7e-13 (limit 1e-6). First fit, `circle__c4` known contrast, 02:06: completed schedule, 274 of 13,412 work units, 6.7 s, area error 7.3e-7 ([report](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/first_fit_report.md)). Queue released 02:11 at two fits at a time. `cog__c4` and `aphex_twin` wait for BRG's completion run | Done 04:53: 40 fits, [final report](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/final_report.md) and [stall note](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/aphex_known_contrast_stall.md) accepted. Left: close the idle pane; a clean timed pass later |

## Coordinator decisions

| Date | Decision | Reason |
|---|---|---|
| 18 Nov, 00:21 | Go for `bem-gpu`'s solver edit: remove the device check in `ModalMuller._table_acquisition`, and fix the wording that calls table mode CPU-only. Nothing else without a new proposal | The paired default returns before that check, so it cannot change. Both geometry classes give A3 the same host fields; A4 and B7 work on host arrays after either assembly. No dataset name or constant |
| 18 Nov, 00:21 | `bem-gpu` takes its three pre-edit references (CPU once, GPU twice) before the edit. Its limits are fixed in its plan: 1e-10 between CPU and GPU tables; the GPU default inside the measured run-to-run spread | A reference taken after the edit proves nothing; limits set before the results |

| 18 Nov, 00:27 | CSI review stop 1: [plan](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/plan.md) approved. Calibration, conjugation, mask, constants and start as written | Checked against `ReadFreData.m`: the factor is taken at row 25 in file order, and equals the conjugate of CSI's factor times its frequency scaling. No fitted amplitude |
| 18 Nov, 00:27 | CSI frequency rule, fixed for every CSI case: add one frequency at a time up to half the top frequency, then the whole catalog. That is 1; 1–2; 1–3; 1–4; then 1–8 GHz | `bem-csi`'s proposal, chosen over the earlier suggestion (1; 1–2; 1–3; all). It keeps the four default stage quotas and the default's factor-2 last jump, and uses only the data's frequencies |
| 18 Nov, 00:27 | CSI series limit: 1e-9. A refusal by the series limit, in a check or inside a fit, is reported to the coordinator and is not final. The switch to 1e-6 is made for the whole CSI dataset, never for one case | The user's rule ("only if 8 GHz is refused"), kept free of per-case settings. The coordinator's reading |
| 18 Nov, 00:27 | `bem-csi` checks once that the frequency-block loss equals the default rectangular loss on a CSI table | The default method must keep its own loss |
| 18 Nov, 00:29 | BRG forward resolution: one trace-cutoff minimum for all six cases, set in the wrapper (`ModalSettings(trace_minimum=K)`). K is the smallest multiple of 32 at which every true shape passes the two forward thresholds, plus one step of 32. Fixed before any fit | `glider_10` failed the forward check at k = 7 (3.9e-5). The refined solve agrees with BRG, so it is resolution: the default profile ignores the interior wavenumber, which is 3.2 times the exterior one at eta 10. A setting, not a solver edit or a method change |
| 18 Nov, 00:29 | BRG cavity: run the prefix rule as far as the series admits and record where it ends. No loosening beyond 1e-6. The redesign question goes to the user | True cavity wave radius 2.919, so the series refuses above k = 8 even at 1e-6 |

| 18 Nov, 00:32 | `bem-gpu`'s diff approved for commit. It is the approved edit only: the two-line device check, one comment, three message wordings, README and chain, the refusal test, and a new eight-case GPU test | All proofs pass. CPU and GPU default fits are byte-identical before and after; the two pre-edit GPU runs were byte-identical too. Tables agree between CPU and GPU to 2.8e-13 against a 1e-10 limit. 121 tests pass |
| 18 Nov, 00:32 | `bem-gpu` drafts a proposal, with no solver code, for lifting the series limit: activity `05_lift_series_limit` | The user agreed to "propose a solver redesign only if a case still stops below 15". The cavity does |

| 18 Nov, 00:36 | CSI review stop 2: the adapter passes. Go for the first fit on the measured cylinder, on the GPU and on the CPU. No fit on a simulated table until the user answers on the 1% rule | Factors match CSI's saved ones to 8.5e-14; the simulated incident field matches ours to 1.3e-14; the frequency-block loss equals the default loss to round-off; the series limit holds at 1e-9. The circle data fail the 1% rule |
| 18 Nov, 00:40 | BRG forward checks: where our forward is converged (refinement under 1e-6) but still differs from BRG by more than 1e-5 at every resolution, record the failed threshold and go on to the fit. Thresholds are not changed | `cavity_09` at k = 1.25: refinement 2.6e-13, BRG difference 2.7e-5. No resolution can move it; the cause is on the reference side or in how the true curve is represented. The fit reads BRG's data; the true curve is used only in this check and in scoring |
| 18 Nov, 00:57 | BRG GPU pass: go, the reported pass. Same settings as the CPU pass: K = 192 for all six cases, 1e-6, the fixed prefix rule. Fits run from a queue as memory allows | The CPU pass was stopped by its 120 s limit on every case (last k 1.5 to 2.5), so it is an early look only. 16 GB was available against the 14 GB guard |
| 18 Nov, 01:00 | Frequency rule for the simulated CSI cases (1 to 3 GHz), fixed before any fit: ladder 1; 1–2; 1–3 GHz, then the default whole-catalog stages on 1–3 GHz. Ladder quotas 1000, 3000, 4000. The measured cylinder keeps its rule (1; 1–2; 1–3; 1–4; all) | All three wavenumbers (1.05, 2.10, 3.14) lie inside the default TG-002 ladder's range (1.28 to 3.21), so the ladder covers the catalog with bands 3, 6, 9 against the default's 3, 5, 7, 9. The half-the-top rule would leave one ladder stage and a factor-3 jump. The quotas are the default four with the two middle ones merged, so the total stays 13,412 |
| 18 Nov, 01:00 | The runs start only if they leave 14.5 GB available (was 16 GB) | Memory fell to 16 GB available; the user's guard is 14 GB and a BEM fit peaks at 1.4 to 1.9 GB |
| 18 Nov, 01:25 | BRG GPU pass accepted as the reported pass for `glider_033`, `star_full` and `star_limited`. `glider_10` stays in the table as a failed fit, not as a series-limit skip | At k = 12 its residual is 0.73 and its area error 14%, so the fit had failed before the series refused k = 15 (the bad curve has wave radius 1.68 against 1.28 for the truth). The plan says failures stay in the table. The coordinator's reading of the user's skip decision; the user may overrule |
| 18 Nov, 01:25 | `bem-brg` looks for the cause of the CPU and GPU path differences, checks only: forward and Jacobian on both devices at K = 192, and the first iteration where the saved paths part | The user's rule is to flag any case where the two differ. Same-iteration curve differences are 1e-5 on three cases and 6e-2 on `glider_033`, far above the 1e-13 between devices in the table checks |
| 18 Nov, 01:32 | CSI review stop 3: the first fit on the measured cylinder is accepted as run. No retune, no rerun. `bem-csi` adds an information-only check: an exact-series circle fitted to the measured table | Limits kept (894 units, 1403 s), raw metrics saved, no truth in the fit, solver untouched. The fit landed 3.1 mm from the nominal centre but too large and too weak (radius 19.0 mm against 15, permittivity 2.19 against 3, area error 67.8%). Its residual (33 to 50%) is above the nominal truth's (23 to 40%), so the check asks whether the data support the nominal cylinder under our forward at all |
| 18 Nov, 01:32 | Data request to the baseline coordinator (pane `w1:p1`): generate the other seven simulated tables now, not at each CSI batch start | Only circle, kite and peanut exist. The BEM fits would otherwise wait about 4 h |
| 18 Nov, 01:33 | Measured cylinder: the result stands as a failure of the default fit, and the adapter is cleared. No retune | Information-only check, data only: a least-squares circle from the exact series ends at centre (1.9, 26.2) mm, radius 15.3 mm, permittivity 3.05, loss 0.0375, from the nominal start and from the fit's end point alike. Our fit ended at loss 0.0840 (radius 19.0 mm, permittivity 2.19). The large, weak cylinder comes from the 1 GHz stage, where the data fix mainly size times contrast; later stages accept almost nothing |
| 18 Nov, 01:33 | `bem-csi-run` launched on the hand-over: circle, kite and peanut now; the other seven when the baseline side sends their paths. The measured cylinder is not rerun | The adapter passed its three review stops; the hand-over is one resumable command per step. GPU fits repeat bit for bit, so a second cylinder fit adds nothing |
| 18 Nov, 01:39 | Simulated CSI fits: `bem-csi-run` finishes circle, kite and peanut at 1 to 3 GHz as an early look and starts nothing else. The reported pass waits for the user's frequency list | The user reopened the list at 01:36 UTC. Three fits of about 8 minutes cost little and can inform the review; seven more would be wasted if the list changes |
| 18 Nov, 01:39 | Frequency rule for the simulated cases, fixed now for whatever list the user picks: the ladder adds one frequency at a time up to the larger of 3 GHz (the top of the default ladder in wavenumber, 3.21 per length unit) and half the top frequency; then the default all-frequency stages on the whole list. Ladder quotas 1000, 3000, 4000 for three ladder stages, the default four for four | It reproduces both rules already fixed (1; 1–2; 1–3 on a 1 to 3 GHz list; 1 to 4 then all on the eight-frequency cylinder), and gives 1; 1–2; 1–3 then all for a four- or five-frequency list. Fixed before any result on such a list exists |
| 18 Nov, 01:39 | BRG: the CPU and GPU path difference is explained and accepted; no rerun. `glider_10` stays a failed fit | Forward and Jacobian agree between devices to 1e-13 at K = 192. The difference enters in B6: the slider preparation uses NumPy least squares on the CPU and a Torch eigen-solve on the GPU, which is existing default behaviour, not the table path. Directions differ by 1e-13 to 1e-10 and the early stages amplify that (3e-8 at k = 1, iteration 3; 6e-2 at k = 2.5). Why the path amplifies so strongly is not proven. `glider_10` never gets near the truth: 16% area error after k = 1, and its residual jumps from 0.08 to 0.57 at k = 1.75 |
| 18 Nov, 01:42 | The ten simulated tables are received and checked: `results/csi/tg002/2026-11-18_low_band_data/<shape>/forward/synthetic_input.txt`, baseline commit `8d4c6123d`. The wrapper is pointed at them once `bem-csi-run`'s three early-look fits are done, not before | All ten exist with 14,112 rows (eight frequencies) and match their `.sha256` files; circle, kite and peanut are byte-identical to the campaign tables already in use. Changing the wrapper in the middle of a batch would mix source hashes |
| 18 Nov, 01:49 | B1 settings, fixed before any fit and the same for all 20 cases: the default TG-002 method unchanged (default schedule on the default's 19 frequencies, start fixture, default resolution, 1e-9), run in the TG-002 package units. Only the data force a difference: plane-wave tables, frequency blocks, and the known contrast in row one | BRG saved 37 frequencies that include the default's 19, and its unit disk is the TG-002 start. BRG's data use a 0.065 m length unit; the default's band rule depends on the unit, so our fits convert to 0.05 m |
| 18 Nov, 01:49 | B1 data checks: our forward makes its own copy on each true shape at all 37 frequencies and compares it with BRG's. Limits set now: 1e-6 between our resolutions; 1% between the two copies at every frequency, else stop and ask the user | The check agreed with the user ("i thought we make two copies then compare"). The 1% limit is the user's rule for the simulated CSI data, applied here by the coordinator |
| 18 Nov, 01:49 | B1 runs on the GPU only, one fit at a time, with no time-based stop. The agent is Codex `gpt-6-astra` high | The user's brief. The task has unit conversion and data checks that decide the main BRG table, so it is the heavier kind |
| 18 Nov, 01:57 | Early look at 1 to 3 GHz accepted as run; nothing is retried. `bem-csi` now points the wrapper at the ten frozen tables, makes the frequency list one setting with the fixed ladder rule, and closes two record-step gaps. The early-look numbers went to the baseline coordinator for the user's review | Circle 1.17%, kite 3.08% (its last stage ended on a numerical failure; kept), peanut 1.50% area error; contrast within 0.04% of 4. CPU and GPU agree on every stage both completed, and two GPU repeats were identical. The runner's batch is finished, so the wrapper can change without mixing source versions |
| 18 Nov, 02:00 | Handoff, at the user's request: `bem-brg` and `bem-csi` closed with their work committed; `bem-csi-run` wrote a "State at handoff" section and was cleared; `bem-b1` left running | The user: "close panes that are no longer needed, for panes that are monitoring and could also use a clear then let them also be ready to handoff, then you clear them." `bem-b1` is ten minutes into its task and has little context to shed |
| 18 Nov, 02:00 | `bem-csi`'s wrapper update accepted: ten frozen tables with hash check, frequency list as one setting, the two record-step gaps closed | Its dry check shows the stage plans for the cylinder and for 1 to 3 GHz identical to the runs that happened, and gives ladder 1; 1–2; 1–3 then all for 1–4, 1–5 and 1, 2, 3, 5 GHz |

| 18 Nov, 02:05 | B1 data checks accepted for the 16 cases BRG has saved, and the wrapper's settings with them. Go for the first known-contrast fit, `circle__c4`, without waiting for `cog` and `aphex_twin` | Worst difference between BRG's copy and ours 1.6e-7 (kite at contrast 0.5) against 1%; worst between our resolutions 1.7e-13 against 1e-6; unit conversion holds to 2.85e-14 in phase. Read in the wrapper: the default schedule on the default's 19 frequencies (asserted equal apart from frequency blocks), the weak start equal to `experiments/comparison/bem.py`, truth used only in checks and scoring. BRG's data come from BRG's own forward (`provenance.json`). 35 GB was available. BRG's completion run may need hours for the last four cases |
| 18 Nov, 02:05 | Three wrapper fixes before the fit, none in the method. A case is fitted on its own passed check, not on all 20. The fit no longer refuses while another BEM command runs; memory is the only limit, and one B1 fit at a time holds until the coordinator raises it. The recovered row needs the same case's known fit, not all 20 | The wrapper as written would refuse every fit until BRG finishes four more cases, and would refuse while its own manifest watcher or a CSI fit runs. The user's limit is the memory guard, not a count of commands. The coordinator's reading of "known-contrast fits first": the known row runs first on every checked case; a late case runs known, then recovered |

| 18 Nov, 02:11 | First B1 fit accepted as run, and the queue released: the known row on every checked case, then the recovered row; a late case joins when its check passes, and a failed check blocks it. Two fits at a time. No stop between fits; `bem-b1` stops only for a failed check, an unexplained crash, a repeating memory requeue or a decision | `circle__c4` completed its schedule in 274 work units and 6.7 s, with 1.94 GiB host peak and area error 7.3e-7; solver clean; the only fault was a missing import path in scoring, fixed without a rerun. 37 GB was available, load 3 of 24, GPU idle. The count of two is the resource monitor's allocation for now (pane `w3:p1`, 02:09 UTC, acting on the user's request to it; the coordinator saw the monitor's message, not the user's own words). Memory alone would allow more |
| 18 Nov, 02:11 | `bem-b1` restarts its manifest watcher and puts a file lock with retry around its commits | The running watcher held an older report writer that would overwrite the fit rows in `results.md`. Two fits and the watcher commit in one checkout and would collide on the git index |

| 18 Nov, 02:12 | A BRG manifest that does not list all 37 data files means "inputs pending", not a failed check. `bem-b1`'s watcher keeps watching and the queue does not wait | Both `aphex_twin` folders hold a manifest with two log files and no data: BRG's wrapper stopped at 02:09 on "No strictly interior diagnostic point with 0.01 clearance". The baseline coordinator already records it and plans a rerun, so no message was sent |

| 18 Nov, 02:23 | B1 concurrency ceiling of four fits accepted. `bem-b1` paused only its scheduler at 02:22, let the two running fits end, and restarts the queue at four | The resource monitor sent the new ceiling straight to `bem-b1` at about 02:22, with the same memory rule and no change to settings, checks or row order. 36 GB was available and a fit peaks at 2.24 GiB, so four fits take about 9 GiB. No running fit was interrupted |

| 18 Nov, 02:54 | `aphex_twin__c0.5` with known contrast stays in the table as a failed fit: 15.1% area error. No rerun, no retune | The plan says failures stay in the table, and GPU fits repeat bit for bit. From its saved stages: the loss stops at 8.4e-5; the first two all-frequency stages accept no step; two later stages take about 500 s each for 266 and 152 work units. The recovered-contrast fit on the same data reaches loss 2.8e-11 and 1.14% area error, so the data and the adapter are sound. The cause of the stall is not known |
| 18 Nov, 04:08 | `aphex_twin__c4` with known contrast stays in the table as a failed fit: 33.2% area error. No rerun, no retune | Same pattern as at contrast 0.5. The schedule completed (last stage `full_10_M61`) with 1546 work units in 5628 s. The loss is 0.096 after the first all-frequency stage and ends at 0.075; six of the ten all-frequency stages accept no step or return at once, and four take 492, 1654, 1259 and 1890 s. Its data check passed (2.8e-6 from BRG's copy), so the data are sound. Both failed fits are `aphex_twin` with the contrast given; the cause is not known |
| 18 Nov, 04:10 | Table B1 is complete: 40 fits, 38 good, 2 failed in quality. Both failures are `aphex_twin` with the contrast given (15.1% and 33.2%); with the contrast recovered the same two cases reach 1.14% and 0.45% | `aphex_twin__c4` recovered: schedule completed, loss 8.4e-10, contrast 4.000012, 133 s, against 5628 s and loss 0.075 with the contrast given. Same data, same start curve; only the start contrast and the free contrast differ. The cause is open: ask `bem-b1` from saved records, no rerun |
| 18 Nov, 04:53 | `bem-b1`'s [final report](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/final_report.md) and its [note on the two stalled fits](adapt_bem_to_baseline_data/06_fit_brg_tg002_cases/aphex_known_contrast_stall.md) are accepted. B1 is closed on the BEM side; no rerun. A test of the cause would be a new activity and needs a go | From saved records only. With the true contrast fixed on the centred 65 mm start circle the first loss is 6.7 and 2.3, against 0.23 and 0.26 from the weak start. The fixed-contrast path brings the curve into near self-contact in the ladder (smallest gap 0.0004 and 0.0016 mm at the end, against 6.5 mm on the truth). After that most proposals are refused by the self-intersection check (568 and 973 refusals; none in the recovered fits), and 98 to 99% of the time goes to forward geometry preparation (A1). The records cannot separate the start contrast from the free contrast direction; both readings are marked as hypotheses in the note |
| 18 Nov, 04:53 | The simulated fits stood still from 04:12 to about 04:53 with a free BEM slot. `bem-csi-run` aligns its waiter's memory count with the monitor's and restarts it | The waiter took the memory of the top MATLAB process only (3.6 GiB) against a 6.0 GiB reservation, so it saw 7.5 GiB of growth still to come and 15.1 GiB left, under the 16 GiB line. The monitor sums each job with its child processes (5.2 GiB) against 6.6 GiB, sees 4.1 GiB of growth and 18.5 GiB left, and had granted the slot. No fit was stopped; 40 minutes of GPU time were lost. The coordinator was away in that time |
| 18 Nov, 05:10 | The ten five-frequency GPU fits are accepted as the reported pass for the BEM row of table C (simulated). Nothing is rerun | Every fit completed its schedule on a clean solver and read the table with the same SHA-256 as its check. The final residuals (0.04 to 0.40% per frequency) are at or under the data's own error on the true shape (0.11 to 0.71%), so each fit reached the level of the data error. The largest area errors are `aphex_twin` 5.96%, kite 3.80% and hook 3.59%; the top frequency is 2.5 GHz, a 12 cm wavelength against shapes of about 13 cm |
| 18 Nov, 05:36 | `bem-csi-run`'s [results](adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies/results.md) are accepted; the five-frequency pass is closed. The CPU cross-checks stay as cut runs | All ten CPU runs stop at 120 s inside the first three all-frequency stages. On the 5 to 7 stages that both devices finished, the loss differs by at most 3.8e-9 relative (hook), the contrast by at most 1.3e-10, and the step counts are equal on every shape. So the GPU path equals the CPU path through the whole ladder here; the end of a CPU fit is not reached. The coordinator's own read of the saved metrics; the runner adds its numbers to its results |
| 18 Nov, 07:51 | The main file's numbers for table C (simulated), written by the baseline coordinator at 07:50, are checked and accepted for the BEM column. The median in `bem-csi-run`'s results is corrected from 2.2% to 2.47% | Area error, contrast and time of all ten BEM fits there equal our `metrics.json` and `fit.json` values; BEM mean 2.71% and median 2.47% on ten shapes, 2.96% and 2.60% on the seven shared ones, recomputed. For each of the ten shapes the table's SHA-256 is in our check and our manifest; for the seven shared shapes it is also in CSI's `data.json`. The runner's 2.2% was the mean of the fourth and fifth value; the coordinator's 05:36 status to the user repeated it |
| 18 Nov, 03:55 | Simulated CSI cases at 0.5 to 2.5 GHz: the frequency rule of 01:39 is applied as fixed. All five frequencies lie below 3 GHz, so the ladder has five stages (0.5; 0.5–1; 0.5–1.5; 0.5–2; 0.5–2.5 GHz), then the default all-frequency stages on the list. Ladder quotas 1000, 1000, 1000, 1000, 4000 | The rule was fixed "for whatever list the user picks"; only the quotas for five stages were missing. First and last are the default's; the default's middle 3000 units are shared equally, so the ladder total stays 8000 and the fit total 13,412. Shape bands by the default's own rule: 1, 3, 4, 6, 7 (default TG-002: 3, 5, 7, 9). Set before any result on this list. A scratch run on our own synthetic kite data showed only that the five stages run |
| 18 Nov, 03:55 | The five-frequency GPU fits have no stop on elapsed time (the wrapper's 1 h ceiling is removed). The CPU cross-check keeps its 120 s cut | The user: "treat elapsed-time targets as reports rather than reasons to stop", and the relayed order says no stop on time. `aphex_twin__c4` in B1 shows a fit can pass 1 h and still move. The CPU run is a cross-check, not a result; whether to lift its cut is still asked |
| 18 Nov, 03:55 | The five-frequency pass writes to `results/bem/baseline_data/csi_five_frequency/2026-11-18/`, apart from the early look. A fit now refuses a check made on another table (SHA-256) or another frequency list | The early-look folder holds finished attempts and passing 1 to 3 GHz checks for circle, kite and peanut; reusing it would skip those fits and accept the old checks. Both methods must provably read the same file |
| 18 Nov, 03:58 | Resource ceilings: the BEM side follows `results/csi/resource_policy.json` (one BEM fit at a time across B1 and the simulated cases, set 03:51). The ten 1% checks run on the CPU as each table is frozen. The monitor was asked for a second BEM slot, for one simulated fit beside the B1 fit | The monitor is set up by the user and sets how many jobs run. The checks use one CPU thread for about 10 s each and no GPU, and CSI's seven fits wait for them. The B1 fit `aphex_twin__c4` has run 86 min with no time stop; ten short simulated fits (1 to 3 min each in the early look) would otherwise wait behind it |
| 18 Nov, 04:01 | Go to `bem-csi-run` for the 1% checks, shape by shape as each table is frozen. A table is frozen when its `<shape>/manifest.json` says `frozen` and the `.sha256` is beside it | The baseline coordinator's rule, sent 04:00. The circle table is verified: 8820 rows, five frequencies, SHA-256 `43b641d7…` equal to its `.sha256`. Its own check against the exact series gives 0.44, 0.17, 0.13, 0.13, 0.18% |
| 18 Nov, 04:05 | The ten 1% checks are accepted; all ten shapes are fitted. Mismatch on the true shape at 0.5, 1, 1.5, 2, 2.5 GHz, in %: circle 0.44, 0.17, 0.13, 0.13, 0.18; kite 0.12, 0.19, 0.17, 0.20, 0.29; peanut 0.21, 0.17, 0.11, 0.17, 0.26; star 0.42, 0.17, 0.18, 0.14, 0.27; asymmetric 0.28, 0.18, 0.20, 0.20, 0.37; c_shape 0.30, 0.30, 0.22, 0.21, 0.28; hook 0.21, 0.17, 0.16, 0.14, 0.19; cross 0.27, 0.16, 0.15, 0.14, 0.24; cog 0.40, 0.18, 0.14, 0.14, 0.31; aphex_twin 0.35, 0.40, 0.46, 0.48, 0.71 | All under the 1% limit. Our two resolutions agree to 6e-9 or better, and on the circle our forward equals the exact series to 1e-15, so the mismatch is the data's grid error. Each check records its table's SHA-256. The monitor raised `max_bem_fits` to 2 at 04:04; the circle fit started beside the B1 fit |
| 18 Nov, 03:55 | The coordinator made these wrapper edits itself (`csi_fit.py`, `csi_data.py`, `csi_policy_dry_check.py`); `bem-csi-run` only runs | `bem-csi` is closed; the edits are settings and one start check, no solver file. The dry check reproduces the saved plans of the cylinder and of the early look, apart from the removed ceiling |

## Waiting on the user

- **Time limits on the older BEM passes.** For B1 and the five-frequency
  pass it is settled: elapsed-time targets are reports, not stops. Still
  unsaid: whether the 120 s cut on the CPU cross-checks of tables B2 and C
  should be lifted, so that CPU and GPU outcomes can be compared at the
  end of a fit. On the five-frequency cases the cut runs already agree with
  the GPU on every stage both finished, so little hangs on it there.
- **The clean timed GPU pass.** Reported times so far are from a loaded
  machine. The machine is quiet since 07:47 (18 Nov); the pass now needs
  only a go. Asked 07:52.
- **The two failed `aphex_twin` fits with known contrast (table B1).** They
  stay as failures. A test of the cause (start contrast or fixed contrast)
  would be a new activity; not started.

Answered, all recorded under "Decisions made with the user":

- **The frequency list for the simulated CSI cases** (18 Nov 03:39 UTC):
  0.5, 1, 1.5, 2 and 2.5 GHz, all ten shapes.

- **The series limit** (18 Nov about 01:03 UTC). At 1e-6 the series admits
  k times wave radius up to about 24.7. The true cavity has wave radius
  2.919, so both cavity cases stop at k = 8. The user chose to skip them;
  there is no solver change. `bem-gpu`'s
  [proposal](adapt_bem_to_baseline_data/05_lift_series_limit/plan.md) and
  [probe](adapt_bem_to_baseline_data/05_lift_series_limit/results.md) stay as
  a record: an opt-in sampled route in A3, estimated at 6 to 10 work hours.
  The star (1.557) passes on the truth with 6% room; if its fit is refused
  at k = 15 it goes to the user with its last endpoint.
- **The simulated CSI data above 1%** (18 Nov 00:55 UTC; the list was
  reopened at 01:36, see above). The circle
  differed by 0.17, 0.13, 0.30, 1.14, 0.82, 1.68, 2.29 and 5.91% at 1 to
  8 GHz; the data error grows with frequency. The user cut the simulated
  cases to 1 to 3 GHz. Evidence:
  [CSI adapter results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md).

## Open points

Unknowns the work will settle:

- Whether 1e-6 reaches k = 15 on the star and cavity. Measured 18 Nov on
  the true shapes: star 1.557 (passes, 6% room), cavity 2.919 (refused
  above k = 8). The fitted star is still open.
- Whether GPU runs of the default fit repeat bit for bit. Settled
  18 Nov: yes, on `circle__c0.5`, twice before the edit and once after.
  The fit takes 5.3 s on the GPU and 43 s on the CPU pin, and peaks at
  1.8 GB of host memory.
- Whether the CSI adapter needs any solver edit.
- The grid error in the simulated data. The planning coordinator's rough,
  unmeasured guess is several percent at 8 GHz and much less at low
  frequency.
- Whether 8 GHz passes the series limit on every simulated shape. The
  shapes reach 96 mm, which gives k times radius of about 16 on the truth.

Calls left to the coordinator:

- The exact frequency rule on CSI data. Settled in "Coordinator decisions"
  (00:27, 01:00, 01:39 and 03:55): one frequency at a time up to the larger
  of 3 GHz and half the top frequency, then all frequencies.
- Which session is the baseline coordinator. Settled at launch: the Claude
  session in Herdr pane `w1:p1`, as the main file's restart notes say.

## Sources

- Main plan and rules: [coordinate_final_comparison.md](coordinate_final_comparison.md).
- Solver handover: [BRG 03 results](brg_adaptation/03_adapt_bem_to_brg_data/results.md).
- Chain terms A1 to C12: [inverse_information_chain.md](../reference/inverse_information_chain.md).
- Scoring: [experiments/comparison/scoring.py](../../experiments/comparison/scoring.py).
- Benchmark shapes: [experiments/benchmark/README.md](../../experiments/benchmark/README.md).
