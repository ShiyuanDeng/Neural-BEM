# BRG handoff — 18 November 2026

## Current state

**Nothing is running on the BRG side. Both 20-case rows are complete.**
All 37 frequencies per case, saved-output checks and final figures are done.
Activity 05 closed in commit `4198a0bba`; no next activity is open.
**Launch nothing without the coordinator's go.** Questions go to the
coordinator in this pane, not directly to the user; stop and ask if needed.

- **04, shipped curvature limit:** [report](../04_run_brg_on_tg002_shapes/results.md),
  figures beside it; results and all original observations in
  `results/brg/tg002_shapes/2026-11-17/`.
- **05, no curvature limit:** [report](results.md), figures beside it;
  results in `results/brg/tg002_no_curvature/2026-11-18/`.
  `completion_checks.json`, `settings_verification.json`, per-case metrics,
  rejection counts, overlap receipts and bulk SHA-256 manifests are retained.

Both rows remain **provisional**, with known contrast. Removing the limit
improved 10 area scores, worsened 8 and left both circles unchanged.
Within 5%: 7/20 in 04, 8/20 in 05; these counts do not settle U5.
05 took 55 min 39 s elapsed, with no process failure or time overrun.

The old **“State at handoff” in the 04 report is superseded by this note**.
Its running PIDs, pending cases, time caps and launch/stop instructions are
historical. The old cap cut C-shape 0.5 after saved frequency 34; attempt 02
completed from that state. Both initial aphex attempts failed the wrapper's
diagnostic-point check; an approved dense interior search fixed it, retaining
the 0.01 clearance test. Fresh attempts completed. All failed files remain.

## Runners and controls

Owned code is in `experiments/baselines/brg/`:

- `run_tg002.py` / `run_tg002_case.m`: original capped 04 launcher, retained
  as history. Do not use it to launch more work.
- `run_tg002_control.py` / `run_tg002_control_case.m`: replacement without
  time cutoffs. Row `shipped` means the 04 continuation and missing cases;
  `retry` means the two approved fresh aphex attempts with shipped settings;
  `control` means 05, starting afresh with the curvature switch off and
  reading 04 observations by hash, with no new data generation.
- `score_tg002_control.py`, `check_tg002_outputs.py`,
  `log_tg002_rejections.py`, `record_tg002_overlap.py` and the report scripts
  retain scoring, saved checks, log counts and shared-machine timing records.

Completion/retry queue receipts are in `results/brg/tg002_completion/2026-11-18/`
and `results/brg/tg002_aphex_retry/2026-11-18/`; their case files remain in 04.
All queues have ended. No STOP file or new launch is needed.

`results/brg/resource_policy.json` records the monitor's last allocation:
ceiling eight while CSI is held, new launches only, at least 3 GiB per added
BRG worker and a 14 GiB host floor plus 2 GiB margin. Empty slots are allowed.
This is historical capacity, **not authorization to launch**. The coordinator
sets a new-launch ceiling if CSI is released. Never stop an active fit just
to reduce concurrency. Each 05 receipt records overlapping BRG/B1 fits.

## User rules and ownership

User's words: “do not stop result-gerating terminal processes due to time
limit unless i say otherwise. if it stucks or goes wrong you should still
stop it. this is only about time limit”. Time figures are reporting targets;
report overruns and continue. Tell the coordinator about a stuck or faulty
run before stopping it unless urgent. Never restart fits for allocation changes.

“Commit by path”; “5 MB per run”. Check shared `git status` first, stage only
owned files and use `git commit -m "..." -- <your paths>`, then push and check
status. Commit failed runs too. Bulk data/states/logs stay ignored in `local/`
with hashes. Do not discard another agent's changes or create branches/worktrees.

Edit only `docs/iterations/brg_adaptation/`, `experiments/baselines/brg/`,
`results/brg/`, `external/patches/brg/`. No BEM run, no edit under `solvers/`
or `experiments/comparison/`, and no CSI start. No new upstream patch was
needed in 04/05; approved patches 03/04 remain. The coordinator owns decisions
and the coordination file. Report in its required block after an activity.

## Open items

- U5: 5% cutoff versus raw errors; how the main table presents both BRG rows.
- Paper cases from k = 15 to 30 remain deferred, only if the user wants them.
  No resume is authorized; saved states and observations stay in place.
- The paper Figure 1 gap remains unexplained: rebuilt errors were 2–8 times
  smaller up to k = 10; removing curvature did not explain it. No further
  gap experiment is authorized.
- The BEM side reads BRG's saved observations **read-only**. Do not move,
  regenerate or overwrite them. Data qualification and BEM fits belong to
  that side. Preserve both provisional rows and all failed attempts.
