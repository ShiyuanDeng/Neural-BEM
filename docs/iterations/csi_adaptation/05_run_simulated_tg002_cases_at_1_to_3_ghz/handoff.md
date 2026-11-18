# CSI handoff — all fits held

18 November 2026. **No CSI process is running. Start no run.** Questions
go to the coordinator in this pane, not to the user; stop and ask there.
This note supersedes the old activity-04 handoff and stale launch orders.

## Current state

The eight-frequency circle/kite/peanut batch completed 2048 iterations
each, with return codes zero. The old launcher exited naturally at
02:00 UTC; pushes `984771ca8` and `bff0fd4a8` are confirmed. The complete
[review pack](../04_run_simulated_tg002_cases/review_pack.md) contains all
256/512/1024/2048 scores at thresholds 0.3/0.5/0.7, permittivity/contrast
errors, costs, timings and the final figure. Review push: `30649383b`.
Main-threshold final area errors: circle 13.67%, kite 16.11%, peanut 21.13%.

**Every other fit is HELD until a new coordinator go with the user's
frequency list.** Four or five frequencies are under consideration.
1–3 GHz was the user's first idea, not the final choice. Whether to run
all ten shapes again or only the remaining seven is also open. Nothing
will auto-launch when this chat closes. The stopped grid check stays stopped.

## Frozen data — never move or regenerate

All ten full eight-frequency parents exist locally at this fixed pattern:

`results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt`

Each has a `.sha256` sidecar. [data_note.md](data_note.md) lists every
parent path/hash and the initial 1–3 GHz subset path/hash. The BEM side
reads these files read-only: **never move, replace or regenerate them**.
Bulk tables/maps are git-ignored; compact evidence is pushed. Seven new
parents used the unchanged original generator and frozen truth; all 29
old source hashes matched. The other three were copied by exact hash.

For frequency f, select column 3 == f: one-based rows `8*j+f`, j=0..1763.
The 1/2/3 GHz rows are interleaved, not the first 5292 rows. Fields use
exp(+j omega t); BEM conjugates once. Full parents retain every frequency.

## Prepared launchers — neither has permission to launch

Reduced/selected-band file: `experiments/baselines/csi/campaign_low_band.py`.
The single frequency setting is `--frequencies` with an ascending GHz
list; no default exists. It verifies/reuses all ten parents by SHA-256 and
has no generation path. Native frequency count, objective/initial-field
blocks follow that list; conductivity scaling uses its first frequency,
and the raw/history image reference uses its last. Grid stays 166×166
at 1.25 mm, 2048 iterations, native back-propagation, three fits at a time.

**Resolve shape scope first:** the code currently loops all ten shapes.
If only seven are approved, adapt that case list before launch. After
the coordinator's go, set the bash array `CSI_FREQUENCIES` to the approved
list, then launch from the repository root with this command:

```bash
mkdir -p results/csi/tg002/2026-11-18_low_band
PYTHONPATH=solvers:. setsid nohup /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_low_band \
  --parent-commit bff0fd4a8 --frequencies "${CSI_FREQUENCIES[@]}" \
  >results/csi/tg002/2026-11-18_low_band/campaign_launcher.log 2>&1 </dev/null &
```

Results root: `results/csi/tg002/2026-11-18_low_band/` (not started).
Its files are `campaign.json`, `status.json`, `STOP`, `budget_hours.txt`
(initially 6, informational target only), `budget_history.jsonl`,
`alerts.jsonl` and per-invocation source hashes. It reads the target at
every check, reports overruns and keeps running. The 14 GiB guard can
delay starts or urgently stop the newest owned fit, preserving evidence.
`--dry-run` is read-only. `--resume` keeps start time, STOP and frequency
list; finished/interrupted fits are preserved, never restarted from an image.

Eight-frequency continuation file:
`experiments/baselines/csi/resume_campaign.py` — prepared, **unlaunched**.
It covers batches 2–4 in the old root, keeps original state/start time,
and reads `resume_budget_hours.txt` (12, now a target, never a time stop).
**Neither launcher may run without the coordinator's new go.** Never
rerun `campaign.py` against the existing old campaign directory.

## Rules and next decisions

User's exact time rule: "do not stop result-gerating terminal processes
due to time limit unless i say otherwise. if it stucks or goes wrong you
should still stop it. this is only about time limit". For a stuck/faulty
fit, tell the coordinator what was seen before stopping unless urgent.
Leave BRG/BEM processes and files alone. Edit only CSI-owned paths; no
edits under solvers/ or experiments/comparison/.

Commit and push code/docs/results after runs, failures included. Shared
checkout/index: stage named own paths and use `git commit -m "..." --
<your paths>`, never a bare commit. Keep about **5 MB per run maximum**;
keep bulk local/ignored with hashes. Confirm push and scoped git status.

Open: user's frequency list and all-ten versus seven scope; threshold
sensitivity; isolated timing (current times overlap BRG/BEM); MR-CSI's
unexplained difference from the paper's Figure 5. The activity folder
name says 1_to_3_ghz: resolve its name with the coordinator if the chosen
band differs. Read [results.md](results.md), [checks.md](checks.md) and
the review pack as needed; do not treat old plans as a launch go.
