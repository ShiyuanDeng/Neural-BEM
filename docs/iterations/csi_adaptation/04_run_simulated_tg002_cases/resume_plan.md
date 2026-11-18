# Continue batches 2–4 on the original clock

18 November 2026. The coordinator extended activity 04 from nine to twelve
hours on the original clock: start 17 November 23:16:53.628911 UTC, hard
stop 18 November 11:16:53.628911 UTC (11:17 rounded). This supersedes the
earlier eleven-hour decision. The guard is not a target. No other setting changes.

Leave original launcher PID 708268 alone. Let it finish batch 1, publish
and exit at its first-batch forecast check. Confirm that push before
starting the separate `experiments.baselines.csi.resume_campaign` module.
If the original instead continues to batch 2, do not launch the resume;
tell the coordinator about its unchanged nine-hour hard stop.

The resume runs only star/asymmetric/c_shape, hook/cross/cog, aphex_twin,
in that order, at 2048 iterations, MF-CC-CSI only. Three-worker ceiling,
eight compute threads per fit, original 14 GiB reserve and all numerical
settings stay unchanged. Budget includes the original data preparation,
batch 1, the gap before resume and subsequent data preparation.

It refuses a live original launcher or CSI worker, an existing STOP,
an expired deadline or an existing resume claim. Existing outcome
directories are preserved and skipped; existing unfinished directories
cause a refusal. Exclusive case-directory creation prevents overwriting.
A permanent exclusive resume lock prevents a second resume invocation.

The original campaign.json, status.json, sources.json and STOP are kept.
New state uses resume_campaign.json, resume_status.json, resume_overlap.jsonl
and resume_sources.json under the same campaign root. Source hashes include
the new module; the original launcher's source files remain unchanged.
Raw evidence, scoring, manifests and per-batch commits use the original
CSI helpers. Final reports state the current budget and retain the
historical nine-hour first-batch forecast. Stop/failure outputs are kept.

Before launch, run a read-only dry run on the real campaign folder:

```bash
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.resume_campaign --dry-run
```

After original exit and confirmed batch-1 push, launch detached with
`setsid nohup`, the same module and `--batch-one-commit <confirmed SHA>`.
The module verifies that the remote contains that commit and its three
batch-1 outcomes. Use a local ignored resume log under the campaign root.
No MATLAB test run is needed; the real-folder dry run starts no workers.

Checks completed 18 November, approximately 00:38 UTC: real-folder dry run
passed with write-mode file opens and subprocess creation forbidden.
It listed seven pending cases and refused the live original launcher and
workers. Temporary-folder checks passed for preserving STOP, skipping
finished outcomes, refusing unfinished directories, refusing an existing
resume lock and rejecting an expired original-clock deadline. No MATLAB
was launched. These initial checks used the earlier eleven-hour decision.
The amended exact deadline is 11:16:53.628911 UTC. Every stop check reads
resume_budget_hours.txt; each value used is recorded on first use and
each change in resume_budget_history.jsonl. Missing or invalid text stops
the resume safely. The coordinator can edit the hours without a restart.

The amended real-folder dry run also passed with writes and process
creation forbidden. A temporary control-flow check ran the resume loop
with fake completed workers, without MATLAB: batches/order stayed fixed,
an existing completed case was untouched, original state was unchanged,
an exclusive claim blocked another launch, and changing the temporary
hours file from 12 to 13 updated the deadline and recorded both values.
The real hours file remains 12.

Success: seven additional recorded outcomes, four snapshots per completed
case, fixed-protocol scores, data/source hashes and per-batch pushes.
After each batch check actual scoring, outcomes, push and scoped status.
Write the final coordination report block when done or stopped. No
numerical success cut-off is selected here; BEM checks remain separate.
