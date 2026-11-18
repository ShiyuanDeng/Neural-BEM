# Coordinate the BEM side

This file is the plan for the BEM side of the final comparison: fitting
our BEM inverse to the data that BRG and MF-CC-CSI use. The baseline side
(their code and their runs) stays in
[coordinate_final_comparison.md](coordinate_final_comparison.md).

It is a temporary second file. The user: "i would prefer to use one
coordination file, but temporarily to avoid the current coordination file
being too long you can have a new one". Merge it back when the work is done.

**State, 18 November 2026, 00:30 GMT:** launched. The user: "you are the
coordinator, start the work." `bem-gpu`, `bem-brg` and `bem-csi` run in
Herdr panes beside the coordinator (pane `w2:p1`). The solver lock is with
`bem-gpu`; the main file records it (commit `7069d2422`). No solver code
is edited yet. See [Launch log](#launch-log).

## Start here

For the coordinator who picks this up:

1. Read this file, then the main file and [AGENTS.md](../../AGENTS.md).
2. Read the three handover notes: the
   [solver handover](brg_adaptation/03_adapt_bem_to_brg_data/results.md)
   (last section), the
   [BRG data note](brg_adaptation/01_run_published_examples/data_handoff.md)
   and the [CSI table note](csi_adaptation/03_prepare_simulated_tg002_cases/pipeline.md).
3. Run `git status`. Check what the baseline side is running (see
   [Machine](#machine)).
4. In the main file, record that the solver lock moves to the BEM side,
   holder `bem-gpu`. Tell the baseline coordinator's session.
5. Create the investigation folder (see [Paths](#paths)) and launch
   `bem-gpu`, `bem-brg` and `bem-csi` together, each with its brief below.
6. Hold the review stops. Launch `bem-csi-run` once the CSI adapter passes.
7. Keep the status board here current, and the BEM rows of the main file.

The user agreed that launch needs no second check with them. The
coordinator has not used Herdr in the planning session, so the launch
commands are not written here; load the `herdr` skill.

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
| 1 | Six BRG paper cases, known contrast, to k = 15 | B2 | Saved by BRG, ready | 1 of 6 run to k = 10 by the `brg` agent |
| 1 | Measured Fresnel cylinder `dielTM_dec8f` | C | Ready | Not started |
| 2 | Ten TG-002 shapes at contrast 4, simulated in the Fresnel layout | C | Made by the CSI campaign, as each case finishes | Not started |
| Held | TG-002 shapes with plane-wave data | B1 | See below | Waits for the user |

Table B1 is held until the user opens it. What is agreed for then:

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
| `bem-gpu` | `w2:p5`, top right | Codex `gpt-6-astra`, high | At launch | Make the table path run on the GPU | Yes, it holds the lock |
| `bem-brg` | `w2:p6`, middle right | Codex `gpt-6.1-sol`, high | At launch | Fit the six BRG paper cases | No |
| `bem-csi` | `w2:p7`, bottom right | Claude Opus, high | At launch | Write the CSI adapter, run its first checks and first fit | Only if given the lock after `bem-gpu` |
| `bem-csi-run` | not started | Claude Sonnet, high | When the adapter passes review | Run and watch every BEM fit on CSI data | No |

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
| Baseline coordinator | Another Claude session in Herdr. Requests go through the main file; direct messages only for data requests, each recorded here | "in herdr that coordinator is just in another claude session" |

Why both kinds of CSI data: the CSI repository ships 18 measured Fresnel
files, and our method takes one object with one real contrast. Only the
single dielectric cylinder fits that. It is one circle with nominal truth,
so it cannot compare shape recovery.

## Limits

- Per fit: 13,412 work units and a 1 h wall ceiling.
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
| Table path on the GPU | `bem-gpu` | Done: commit `3612f5195` at 00:32 ([results](adapt_bem_to_baseline_data/01_run_table_path_on_gpu/results.md)). Lock free. Series-limit [proposal](adapt_bem_to_baseline_data/05_lift_series_limit/plan.md) written 00:38, no code. Agent idle in its pane | Wait for the user on the proposal |
| BRG paper cases | `bem-brg` | Wrapper written. [Forward checks](adapt_bem_to_baseline_data/02_fit_brg_paper_cases/results.md): `glider_033` passes to k = 15; `glider_10` needs more resolution; cavity refused above k = 8. No fit yet | Fix the resolution, finish the forward checks, CPU pass |
| CSI adapter | `bem-csi` | Review stop 2 passed 00:36 ([results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md)): adapter correct; simulated circle data above 1% at 4, 6, 7, 8 GHz. Running the first fit on the measured cylinder | Review stop 3: first fit. Simulated fits wait for the user |
| CSI fits | `bem-csi-run` | Not started | Launch after the adapter passes |
| Table B1 | none | Held | Wait for the user |

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

## Waiting on the user

- **Simulated CSI data above 1%.** On the true circle our forward differs
  from CSI's simulated table by 0.17, 0.13, 0.30, 1.14, 0.82, 1.68, 2.29
  and 5.91% at 1 to 8 GHz. Our forward matches the exact series to 1e-13,
  so the error is in the simulated data. It grows with frequency as a grid
  error would (0.625 mm cells). No simulated case is fitted until the user
  answers. Asked 18 November, 00:36. Evidence:
  [CSI adapter results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md).

- **Cavity below k = 15: go or no-go on a solver change.** At 1e-6 the
  series admits k times wave radius up to about 24.7. The true cavity has
  wave radius 2.919, so both cavity cases stop at k = 8. The star (1.557)
  passes on the truth with 6% room, so its fit may stop at k = 12.
  `bem-gpu` wrote the [proposal](adapt_bem_to_baseline_data/05_lift_series_limit/plan.md)
  the user asked for in that case ("propose a solver redesign only if a
  case still stops below 15"), with a [3 s probe](adapt_bem_to_baseline_data/05_lift_series_limit/results.md):
  - What: an opt-in route in A3 that samples the regular waves on the
    boundary and transforms them, used only above the series limit. Off
    by default, so the default path is untouched.
  - Cost: its estimate is 6 to 10 work hours, up to 1 to 2 days if the
    trace resolution does not converge. It adds boundary sampling to A3,
    which the method does not use today.
  - Not proven: that a k = 15 cavity fit then finishes. The next limit is
    trace resolution (incident modes above 96 carry 1.3e-3 at k = 15).
  - Coordinator's recommendation: no go for now. Decide after the first
    BRG pass shows how our BEM does on the cavity at k = 8.
  Asked 18 November, 00:30; proposal ready 00:38.
- **Simulated CSI data above 1%.** On the true circle our forward differs
  from CSI's simulated table by 0.17, 0.13, 0.30, 1.14, 0.82, 1.68, 2.29
  and 5.91% at 1 to 8 GHz. Our forward matches the exact series to 1e-13,
  so the error is in the simulated data. It grows with frequency as a grid
  error would (0.625 mm cells). No simulated case is fitted until the user
  answers. Asked 18 November, 00:36. Evidence:
  [CSI adapter results](adapt_bem_to_baseline_data/03_adapt_bem_to_csi_data/results.md).

- **Cavity below k = 15.** At 1e-6 the series admits k times wave radius
  up to about 24.7. The true cavity has wave radius 2.919, so both cavity
  cases stop at k = 8. The star (1.557) passes on the truth with 6% room,
  so its fit may stop at k = 12. Options: report these rows at the k
  reached, or redesign the incident-wave series in the solver. The user
  agreed earlier to "propose a solver redesign only if a case still stops
  below 15". Asked 18 November, 00:30.

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

- The exact frequency rule on CSI data. A suggestion, not a user decision:
  map the TG-002 default by k times the start radius. That gives a start at
  1 GHz, then 2 and 3 GHz added one at a time, then all frequencies.
- Which session is the baseline coordinator. Settled at launch: the Claude
  session in Herdr pane `w1:p1`, as the main file's restart notes say.

## Sources

- Main plan and rules: [coordinate_final_comparison.md](coordinate_final_comparison.md).
- Solver handover: [BRG 03 results](brg_adaptation/03_adapt_bem_to_brg_data/results.md).
- Chain terms A1 to C12: [inverse_information_chain.md](../reference/inverse_information_chain.md).
- Scoring: [experiments/comparison/scoring.py](../../experiments/comparison/scoring.py).
- Benchmark shapes: [experiments/benchmark/README.md](../../experiments/benchmark/README.md).
