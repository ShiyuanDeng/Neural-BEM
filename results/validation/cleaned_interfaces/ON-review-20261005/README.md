# ON-001/002/003 outside review — recomputed evidence

Review: [iteration 31, 02_claude_review.md](../../../../docs/iterations/cleaned_interfaces/iteration_31/02_claude_review.md).

Everything here is recomputed from saved receipts by one read-only script. The
script runs no physics solves and no fits, and changes no sources. Truth
geometry is read only after the fact, to locate where saved accepted paths
diverged. No fit decision uses it. Runtime is about 15 s on CPU.

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.on_review
```

![Failure terminators and ON-003 truncation](review_figure.png)

| File | Contents | Inputs |
|---|---|---|
| `failure_terminators.json` | Truth distance at entry and exit of every stage for the four failures and the recovered hook c4. For the trial that raised the fatal resolution error: gains, acceptance threshold, per-frequency gate overshoot. Also the PC-001 N1 outcome of the same cases, and a count of numerical obstructions across all 26 successful B runs. | ON-001 `all_B`, PC-001 `N1`, `pipelines.py` |
| `damped_prefix.json` | For all 30 B runs: truth distance at the end of the damped prefix, the loss jump at the switch to real data, and the truth distance across the real stage. Successes end the prefix at 1.13 mm or less; jumps range from 1.2x to 30,696x. | ON-001 `all_B` |
| `on001_arms.json` | E/B pairing and the accuracy trade; physics thread-time shares; solve kinds; screen work counts for B/G/E/EW. | ON-001 `final_comparison.json`, `all_*`, `screen_*` |
| `gaussian_map.json` | Every F qualification state: condition number, width, clipping factor at the 1e-7 m probe, and the displacement at which active clipping begins. | ON-001 `qualification_F*` |
| `ewald_truncation.json` | ON-003 measured circle errors beside the spectral-Ewald k-space term exp(-tau q_max^2) for every registered split and grid. Also contains labelled *estimates* for unregistered splits, and the speed cap for a free assembly. | ON-003 `manifest.json`, `operator_summary.csv`; ON-001 phase totals |
| `on002_status.json` | Tracked status of ON-002 files, its 12 adapter rows, and tracked docs that link to its untracked plan. Also the interruption record, checked against the local Codex session log when that log is present. | ON-002 working tree, git, `~/.codex` |
| `summary.json` | The headline numbers quoted in the review. | All of the above |
| `review_figure.png` | Left: post-hoc truth distance along the B paths, with the fatal gate overshoot at each kill. Right: ON-003 errors against the truncation term. | Same |

Caveats:

- Physics shares are thread-summed seconds divided by four frequency threads.
  They are estimates, not wall-time partitions.
- The ON-003 split values below xi = k* are back-of-envelope estimates from the
  truncation term. They are not measurements.
- The ON-002 adapter files are untracked in the working tree. If they are later
  removed, `on002_status.json` records `adapter128: null`.
