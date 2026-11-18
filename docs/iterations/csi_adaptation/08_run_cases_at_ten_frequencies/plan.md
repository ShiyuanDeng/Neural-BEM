# Run MF-CC-CSI at ten frequencies

Plan written 18 November 2026, 12:20 UTC, by the baseline coordinator,
before any fit.

## Why

The user asked why our BEM outlines on the simulated CSI cases are wiggly
and suspected that five frequencies are too few. The BEM side tested ten
frequencies (its activities 08 to 10). This activity gives MF-CC-CSI the
same ten-frequency tables, so both methods have a result on the same data.

## The user's choices

- In the BEM coordinator's pane, 18 November 11:14 UTC: "0.25-2.5 with
  0.25 steps yes. bem only for now. after you are done you can talk to
  baseline side coordinator and brief him to do csi fit."
- Earlier rules that still hold: their code and settings are not changed;
  both methods read the same frozen observations; no run is stopped
  because of a time limit; 14 GiB of memory stays free, plus a 2 GiB
  margin at launch; a shape whose data is more than 1% from our forward is
  not fitted.

## The coordinator's choices

- Shapes: all ten, so every row has both methods. Order: star, hook,
  circle, kite (the four shapes of the BEM wiggle check; star and hook
  also have a five-frequency CSI fit), then asymmetric, cross, cog,
  c_shape, peanut, aphex_twin. The user did not name the shapes. The queue
  can be cut after any fit by setting the ceiling to zero.
- The five-frequency row of table C stays as reported. The ten-frequency
  result is a new, separate row.
- `star` is released alone first, as a live check that the unchanged
  upstream code takes the ten quarter-GHz values. The others are released
  once it iterates.
- The coordinator runs the launcher itself. No agent pane is opened.

## Questions

1. What area error does MF-CC-CSI reach with ten frequencies on each shape?
2. How does that compare with its five-frequency result (seven shapes) and
   with our BEM at ten frequencies on the same table?

## Settings

| Setting | Value |
|---|---|
| Frequencies | 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5 GHz |
| Shapes | The ten TG-002 shapes at permittivity 4, Fresnel layout |
| Data | `results/csi/tg002/2026-11-18_ten_frequency_data/<shape>/forward/synthetic_input.txt`, frozen, 17,640 rows, with a `.sha256` file. Made by the BEM side with the unchanged generator |
| Method | MF-CC-CSI, upstream commit as in activity 07, output-only patch 0003 reused |
| Iterations | 2048, with snapshots at 256, 512 and 1024 |
| Grid | 166 × 166 cells at 1.25 mm; native back-propagation start; eight threads per fit |
| Scoring | Unchanged protocol 1: area error at half the image peak; 0.3 and 0.7 for sensitivity |
| Start | One centred start. No grid search |

Nothing differs from activity 07 except the frequency list, the tables
and the three shapes added.

## Checks before any fit

Done by the coordinator on 18 November 12:05 UTC, saved in
`results/csi/tg002/2026-11-18_ten_frequency/checks/table_checks.json`:

- Each table's SHA-256 equals its `.sha256` file.
- 17,640 finite rows; each source–receiver pair carries the ten
  frequencies in rising order; pair order equals the five-frequency table.
- The rows at 0.5, 1, 1.5, 2 and 2.5 GHz are byte-equal to the frozen
  five-frequency tables.
- Circle against the exact series: 0.13 to 0.44% at the ten frequencies
  (BEM side's `checks.json`).
- Our forward on each true shape, on the same hash: at most 0.71%
  (`aphex_twin`), under 0.45% on the other nine. All ten pass the 1% rule.

## Launching and memory

- The shared resource monitor has exited and left
  `results/csi/resource_policy.json` at zero fits. So this launcher reads
  its own `ceiling.json` (three fits at most) and applies the memory rule
  itself: a fit starts only if 14 GiB plus 2 GiB stays free after 8 GiB is
  reserved for each fit. Measured peaks were 5.3 GiB at five frequencies
  and 6.5 GiB at eight.
- The launcher keeps the urgent rule of the earlier launchers: below
  14 GiB available it stops its newest fit. A stopped fit is kept as a
  failure and is not restarted.
- No stop on time. The STOP file ends the campaign and stops running
  fits; use the ceiling to cut the queue without stopping a fit.

## Run budget (a forecast, not a limit)

- About 4 to 5 s per iteration with two or three fits at once, so about
  2.3 to 2.8 h per fit.
- With today's free memory two fits run at once: the first two end after
  about 2.5 h, the first four after about 5 h, all ten after about 12 h.
- One pass. No rerun unless a verified fault is fixed.

## Success criteria

- Every fit completes 2048 iterations with finite snapshots, on the table
  with the recorded hash.
- Each fit is scored, committed and pushed as it ends.
- A failed fit is kept and reported; it does not block the others.

## Commands

```bash
# dry run
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_ten_frequency --dry-run
# release one shape
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_ten_frequency --release star
# detached launcher (once; resume with --resume)
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 setsid nohup /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.campaign_ten_frequency >results/csi/tg002/2026-11-18_ten_frequency/campaign_launcher.log 2>&1 </dev/null &
```

## Outputs

- Results: `results/csi/tg002/2026-11-18_ten_frequency/<shape>/`
  (`scores.json`, `outcome.json`, `launch.json`, `manifest.json`).
- State: `status.json`, `campaign.json`, `releases.json`, `ceiling.json`
  in that folder.
- Live table: [progress.md](progress.md), rewritten by the launcher.
- `results.md` and a figure follow after the run.
