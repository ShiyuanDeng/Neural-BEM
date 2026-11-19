# Refit GauGal with the TV warm start — plan, 19 November 2026

Written 19:25 UTC. Follows
[activity 06](../06_make_gaugal_fits_converge/results.md).

## User's words

- "fix it if you can" and "try to be quick" (19 November, for activity 06).

The user has not been asked about this refit. The coordinator opened it as a
follow-up of the same investigation.

## Why

Activity 06 found a defect in the frequency continuation. Each stage after
the first reset the TV auxiliary variable to zero on a non-flat image, which
smoothed the image at every stage start. It caused false rejections on
`circle__c0.5` and acted in all 20 fits. Two contrast-0.5 cases sit within
half a percent of the 5% limit, so the count needs a clean run.

## Questions

1. What is the recovery count on the 20 clean cases without the defect?
2. Does `circle__c0.5` now complete all six stages?
3. Do any stages now end on the plateau rule instead of the step cap?

## Settings

Same as activity 06's continuation, with one change:

- Data, cases, start and scoring: TG-002, contrasts 0.5 and 4, 19 real
  frequencies, recovered contrast, protocol version 1.
- Lattice 51, width 0.7, TV weight 0.5, susceptibility limits −0.9 and 15.
- Exact inner solves. Stages with the lowest 1, 2, 4, 8, 16 and 19
  frequencies; plateau rule or 1,000 steps per stage; step 0.2.
- Step safeguard: halve and restart a stage whose mismatch doubles, at most
  four times.
- **Changed:** at a warm-started stage the TV auxiliary starts from the
  discrete gradient of the first candidate, with a zero dual. The first stage
  starts from the zero image as GauGal does.
- No setting is chosen from truth scores. No time stop.

## Comparisons

- Case by case against activity 06's first continuation run.
- Against the saved `default` run (0/20) and the clean BEM rows, reused.

## Success criteria

- All 20 fits complete their six stages with every solve check passed.
- The count is reported whatever it is, with each case's step and restarts.
- If the count at contrast 0.5 stays low with data fitted to about 1%, the
  limit is the lattice and scoring edge, as activity 06 concluded.

## Run budget

20 fits, about 10.5 minutes each with the GPU alone: about 3.5 hours. The
lower-value jobs from activity 06 are paused again for the duration.

## Commands and outputs

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.comparison run gaugal/tvwarm_clean_uc_fc --cases circle__c0.5 <nine other c0.5> <ten c4>
```

- The first run's 20 whole case folders remain in
  `results/gaugal/converged_clean_uc_fc/` (coordinator correction after launch refusal).
- New fits and scores: `results/gaugal/tvwarm_clean_uc_fc/`.
- Report: `results.md` in this folder.

## Who

`native-adapter` writes the fix. `native-run` moves the first run, launches
the refit detached and reports one line per case.

## Native-run launch details

Coordinator go: code 94c39f4c0. The one scratch controller is the existing
`results/_probes/gaugal_convergence/2026-11-19/probe.py`, mode
`--run-tv-warm-start`. It starts one detached CLI, reports each saved case,
and commits/pushes every two cases by exact path. It never changes settings
or reruns a failed case. Preflight requires 14 GiB MemAvailable and records
nvidia-smi. The six lower-value jobs remain paused; no automatic resume.

Exact order: circle__c0.5, kite__c0.5, peanut__c0.5, star__c0.5,
asymmetric__c0.5, c_shape__c0.5, hook__c0.5, cross__c0.5, cog__c0.5,
aphex_twin__c0.5, circle__c4, kite__c4, peanut__c4, star__c4, asymmetric__c4,
c_shape__c4, hook__c4, cross__c4, cog__c4, aphex_twin__c4.

Native-run writes `run_report.md` in this activity, as the coordinator
requested. Launch/state/log/table files have the `tv_warm_start_` prefix
under `results/gaugal/tvwarm_clean_uc_fc/`. Small fit.npz arrays are
force-added; checkpoints stay whole locally with SHA-256 manifests.

## Launch correction, before any fit

The first CLI launch at 19:26:09 UTC failed because the old run.json
settings differ after the TV warm-start fix. No fit ran; this is a launch
failure, not a 0/20 benchmark result. The original run.json was unchanged.

The coordinator changed the run name to `gaugal/tvwarm_clean_uc_fc`.
All 20 first-run case folders were restored whole with git mv to their
original converged run, with hashes checked. The code agent is adding the
new variant. Wait for the coordinator's go and commit before launching.
Same case order, same numerical settings, one detached runner, no time stop.
