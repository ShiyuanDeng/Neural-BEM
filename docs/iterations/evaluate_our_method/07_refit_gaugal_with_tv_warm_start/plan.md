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
$PY -m experiments.comparison run gaugal/converged_clean_uc_fc --cases circle__c0.5 <nine other c0.5> <ten c4>
```

- The first run's 20 case folders move to
  `results/_probes/gaugal_convergence/2026-11-19/continuation_before_tv_warm_start/`.
- New fits and scores: `results/gaugal/converged_clean_uc_fc/`.
- Report: `results.md` in this folder.

## Who

`native-adapter` writes the fix. `native-run` moves the first run, launches
the refit detached and reports one line per case.
