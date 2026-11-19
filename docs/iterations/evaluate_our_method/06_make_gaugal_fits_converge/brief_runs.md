# Brief for the run agent (`native-run`) — 19 November 2026

From the baseline coordinator (Claude, pane `w5:p1`). This is a new task. Your
native CSI runs are finished and closed.

Read first: [plan.md](plan.md), then
`experiments/gaugal_comparison/gaugal_arm.py` and
`experiments/comparison/gaugal.py`.

## Goal

GauGal recovered 0/20 on TG-002. Find out quickly whether the fits were
simply cut off before converging. Then run the fixed variant on 20 cases.

## Part 1: probe now, with no change to repository code

Write one scratch script in `results/_probes/gaugal_convergence/2026-11-19/`.
It calls `gaugal_arm.reconstruct` as `experiments/comparison/gaugal.py` does
(blind case, lattice 51, width 0.7, TV weight 0.5, limit 15), on clean
`kite__c4` and `kite__c0.5`.

1. Inner solves. Pass `controls=SolverControls(pcg_max_iter=2000)` and run 10
   outer iterations. Report the share of unconverged solves, the worst final
   residual and the seconds per iteration, against the saved cap of 100.
2. Longer fit. Step 0.05, no time limit, as many iterations as fit in about
   15 minutes per case at the faster of the two solver settings. Log the
   weighted mismatch every 10 iterations and the per-frequency data residual
   at the end. Is the mismatch still falling at the end?
3. Step size. On `kite__c4` only, 60 iterations each at steps 0.2 and 1.0.
   Does the weighted mismatch fall faster, or blow up?

Run the two cases side by side on the GPU. Score each final image with the
frozen scoring code and report the area error, but do not use truth scores to
pick anything.

Tell me after each numbered step, in at most five lines, with
`herdr agent prompt w5:p1 "native-run: ..."`. Do not wait for all three.

## Part 2: the 20-case runs, when I say go

The code agent (`native-adapter`) is adding `gaugal/converged_<data>_uc_fs`.
When I send the go:

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.comparison run gaugal/converged_clean_uc_fs
$PY -m experiments.comparison run gaugal/converged_n1d0_uc_fs
```

Contrasts 0.5 and 4 only, 20 cases each. Time the first case and send me the
forecast before the rest. Launch detached (`setsid nohup`) with a state file.
Never stop a run because of time. A stuck or faulty run may be stopped: tell
me what you saw.

## Rules

- Do not edit `experiments/`, `solvers/`, the scoring code or `~/Gau-Gal`.
  Report a crash instead. Your paths: `results/_probes/gaugal_convergence/`,
  `results/gaugal/converged_*`, and `run_report.md` in this folder.
- No new branch or worktree. Commit with
  `git commit -m "..." -- <your paths>` and push after each part, failures
  included. At most about 5 MB per commit; use `git add -f` for small ignored
  files that scoring or figures need. Take times from `date -u`.
- Keep 14 GiB of memory available. Check `nvidia-smi` before each launch.
- Terminal answers: at most three lines per paragraph, plain words.
- Finish with the activity report format in
  `docs/iterations/coordinate_final_comparison.md` ("How subagents work").
