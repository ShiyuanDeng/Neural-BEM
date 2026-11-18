# Fit the CSI tables at ten frequencies: plan

18 November 2026, 11:25 UTC. Written by the BEM coordinator (pane `w2:p1`)
before any result of this activity exists. Runner: `bem-ten` (Codex
`gpt-6.1-sol`, medium, full access). Authority:
[coordinate_bem_side.md](../../coordinate_bem_side.md).

This activity and [activity 09](../09_fit_tables_from_our_forward/plan.md)
run side by side. Together they ask why the BEM outlines of the
five-frequency pass ([activity 07](../07_fit_csi_cases_at_five_frequencies/results.md))
are wiggly.

## The user's choice

In this pane, 18 November 2026, about 11:00 to 11:15 UTC:

> in C sim comparison, is it true that BEM have zigzaggy boundaries, i
> suspect itsbecause we feed it too litle frequencies (only 5), and plan to
> investigate on this by having a 10-frequencis test run.

> okay, now you as the coordinator, use two subagents here in split herdr
> panes, to investigate those two simultaneously.
> docs/iterations/adapt_bem_to_baseline_data. and for your questions:
> 0.25-2.5 with 0.25 steps yes. bem only for now. after you are done you can
> talk to baseline side coordinator and brief him to do csi fit.

Staffing: "Codex, full access", then "for monitoring tasks ues sol medium.
for harder code writing use astra high".

Chosen by the user: the ten-frequency test, the list 0.25 to 2.5 GHz in
0.25 GHz steps, BEM only, two subagents, the staffing. Chosen by the
coordinator: the four shapes, the checks, the ladder quotas and the
criteria below.

## Starting evidence (read from saved runs, no new fit)

The coordinator read the ten five-frequency fits and scored each saved
stage outline with the wrapper's own `score`.

- **The data carry an error.** Our forward on the true shape differs from
  the CSI tables by 0.1 to 0.7%. The tables come from a 332 × 332 grid with
  0.625 mm cells. BRG's data differ from ours by 0.001% and give outlines
  within 0.1%.
- **The final fit matches the data better than the true shape does.**
  Kite at 2.5 GHz: 0.29% for the true shape, 0.07% for the fit. Aphex Twin:
  0.71% against 0.09%.
- **High bands add error without improving the data fit.** No noise level
  is declared, so every fit runs all bands to 37.

| Shape | Area error at band 7 | 11 | 15 | 19 | 25 | 31 | 37 (final) |
|---|---:|---:|---:|---:|---:|---:|---:|
| circle | 0.08% | 0.43% | 0.64% | 0.73% | 0.79% | 0.91% | 0.97% |
| kite | 3.06% | 4.30% | 4.17% | 4.05% | 3.99% | 3.97% | 3.80% |
| star | 3.81% | 1.66% | 1.01% | 2.16% | 2.28% | 2.32% | 2.34% |
| hook | 4.44% | 1.99% | 2.00% | 3.80% | 3.75% | 3.70% | 3.59% |

The loss is flat from band 15 on (circle 2.29e-6 at band 7 and 2.28e-6 at
band 37). The early look with three frequencies (1, 2, 3 GHz) gave
circle 1.17%, kite 3.08%, peanut 1.50%, about the same as with five.

So two causes are possible: too few frequencies (the user's), or the
error in the data. Every saved CSI-table run has both.

## Question

Does doubling the frequency count inside the same band remove the wiggles
and lower the area error, with the data source unchanged?

One change from activity 07: the frequency list. The ladder follows from
the list by the same rule.

## Data

- Ten frequencies: 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25 and
  2.5 GHz. The same CSI forward, grid, layout, mask and conventions as the
  five-frequency tables
  ([data results](../../csi_adaptation/06_prepare_five_frequency_data/results.md)).
- New tables in `results/csi/tg002/2026-11-18_ten_frequency_data/<shape>/forward/synthetic_input.txt`,
  each with a `.sha256` and a manifest, 17,640 rows. All ten shapes, so the
  baseline side can later fit the same files. Order: circle, star, kite,
  hook, then the other six.
- The generator is the baseline side's, used unchanged. New driver files
  only, named for ten frequencies. No existing file of the baseline side
  and no frozen table is edited or regenerated.
- Proof of an unchanged generator: the rows of the five old frequencies
  must equal the frozen five-frequency table byte for byte.

## Checks before a fit

1. Circle against the exact series at the five new frequencies, as in data
   activity 06.
2. `csi_forward_check` on the true shape, all ten frequencies, each shape.
3. The 1% rule: worst mismatch at or below 1% at every frequency. A shape
   or frequency above 1% is not fitted: stop and tell the coordinator, who
   asks the user. 0.25 GHz is the one to watch (0.5 GHz was the worst of
   the five, 0.44% on the circle).
4. Dry plan: send the coordinator the stage list (frequencies, shape band
   and quota per stage) before any fit. If the rule gives a band the policy
   refuses, such as band 0 at 0.25 GHz, stop and tell the coordinator.

## Fixed settings (set before any result)

- Default method, unchanged from activity 07: centred 65 mm circle start,
  `modal_muller` + `slider`, real data only, no localization, no warm-up,
  no noise level, recovered contrast from the weak-scatterer start, series
  limit 1e-9, 13,412 work units, GPU.
- Frequency rule, unchanged: the ladder adds one frequency at a time,
  lowest first, up to the larger of 3 GHz and half the top; then the
  all-frequency stages on the whole list. All ten lie below 3 GHz, so the
  ladder has ten stages.
- Ladder quotas by the rule of activity 07 (first 1000, last 4000, the
  middle 3000 shared equally): 1000, eight times 375, 4000.
- Shape bands by the default's own rule.
- `csi_fit.py`, `csi_data.py` and `csi_forward_check.py` stay unedited. A
  thin runner of the agent's own sets the table path, the list, the quotas
  and the results folder, then calls them.
- Four shapes at contrast 4: circle, star, kite, hook. One GPU fit each,
  one pass, no tuning, no rerun. Failures stay in the table.
- No stop on elapsed time. Memory: start a fit only with 16.5 GiB
  available; at most two fits at a time.

## What to report

For each of the four fits, beside the activity 07 numbers:

- outcome, last stage, work units, fit seconds, contrast;
- final area error, and the area error of every saved stage outline;
- data mismatch per frequency: true shape (from the check) and final fit;
- one figure in `figures/`: the four fitted outlines over the true ones,
  with the five-frequency outlines for comparison.

## Reading the result (fixed now)

Five-frequency references: circle 0.97%, star 2.34%, kite 3.80%,
hook 3.59%. A clear gain is an area error at most half the reference.

- Clear gain on at least three of four shapes: the frequency count
  matters.
- Otherwise: the count is not the main cause on this data. Activity 09
  then says whether the data error is.

## Budget

Ten forward tables (about 30 to 60 s each in MATLAB), ten true-shape
checks, four GPU fits (1 to 5 min each at five frequencies; expect more
at ten). No CPU cross-check. Any further run needs the coordinator's word.

## Outputs

- Tables: `results/csi/tg002/2026-11-18_ten_frequency_data/`.
- Checks and fits: `results/bem/baseline_data/csi_ten_frequency/2026-11-18/`
  (`adapter_checks/`, `<shape>__c4/cuda/attempt_01/`, `logs/`).
- This folder: `results.md`, `figures/`.
- Commit by path and push after each step, failures included. At most
  about 5 MB committed; bulk stays local and ignored with its SHA-256.

## Commands

Commands from the repository root. No branch or worktree. The runner changes
only imported wrapper settings in its own process. No original file is edited.
The circle command must pass before the remaining data command starts.
The fit commands wait for the coordinator's go and passing checks and dry plan.

```bash
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.prepare_ten_frequency_data --shapes circle
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.prepare_ten_frequency_data --shapes star kite hook peanut asymmetric c_shape cross cog aphex_twin
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B experiments/bem_on_baseline_data/csi_ten_frequency.py check --cases circle__c4 star__c4 kite__c4 hook__c4 peanut__c4 asymmetric__c4 c_shape__c4 cross__c4 cog__c4 aphex_twin__c4
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B experiments/bem_on_baseline_data/csi_ten_frequency.py plan
mkdir -p results/bem/baseline_data/csi_ten_frequency/2026-11-18/logs
for shape in circle star kite hook; do
  setsid nohup /home/drdeng/miniconda3/envs/EMNerf/bin/python -B experiments/bem_on_baseline_data/csi_ten_frequency.py fit --case ${shape}__c4 --device cuda > results/bem/baseline_data/csi_ten_frequency/2026-11-18/logs/${shape}__c4_cuda.log 2>&1 < /dev/null &
  wait
  # Check the result file, commit and push this fit before the next launch.
done
```

Fits run sequentially, leaving room for activity 09. No fit starts before
the dry plan is accepted. Each run records HEAD and solver dirty state.
Bulk tables and material maps stay ignored; compact records contain SHA-256.
The old five-frequency blocks must match in the raw generated table as well
as the final frozen table. No numerical tolerance replaces the byte check.

## Coordinator go, 18 November 2026

The coordinator accepted the checks and dry plan, including band 0 at
0.25 GHz, and released the four GPU fits. At most two BEM fits together
with activity 09; this activity launches one at a time. Times are indicative.
Keep any band-0 failure; no rerun or workaround. Finish stage scores,
per-frequency residuals and the outline figure, then commit and push.

Saved-result reporting command (no forward solve), after each returned fit:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B experiments/bem_on_baseline_data/csi_ten_frequency_fit_report.py
```
