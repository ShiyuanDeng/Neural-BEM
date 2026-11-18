# Fit tables made by our own forward: plan

18 November 2026, 11:25 UTC. Written by the BEM coordinator (pane `w2:p1`)
before any result of this activity exists. Runner: `bem-own` (Codex
`gpt-6-astra`, high, full access). Authority:
[coordinate_bem_side.md](../../coordinate_bem_side.md).

This activity and [activity 08](../08_fit_csi_tables_at_ten_frequencies/plan.md)
run side by side. The user's words, the staffing and the starting evidence
are in the activity 08 plan.

## Who chose what

The user asked for the two tests to run together with two subagents, BEM
only. The coordinator proposed this second test and the user agreed
("investigate those two simultaneously"). The coordinator chose the four
shapes, the accuracy rule and the criteria below.

## Question

Are five frequencies enough for a smooth, accurate outline when the data
carry no grid error?

One change from [activity 07](../07_fit_csi_cases_at_five_frequencies/results.md):
the source of the data. The layout, the five frequencies, the fit and its
settings stay the same.

## Data

- Four shapes at contrast 4: circle, star, kite, hook, from the frozen
  TG-002 truth.
- The Fresnel layout of the frozen five-frequency CSI tables: the same
  sources, receivers, 49-per-source mask, pair order and row order, at
  0.5, 1, 1.5, 2 and 2.5 GHz. 8820 rows per table.
- The fields come from our own forward on the true shape. The table is
  written in the CSI seven-column format, so the unchanged reader
  (`csi_data.observations`) returns our scattered field. The source,
  receiver and frequency columns are copied from the frozen CSI table.
- **Accuracy rule:** the data must be accurate to 1e-6 relative or better
  at every frequency, shown by doubling the resolution. As TG-002 does,
  prefer a discretisation different from the fit's: the nodal reference
  solver. If it cannot take this layout without a solver edit, use the
  modal forward at a resolution above the fit's and say so in the results.
- No solver edit. New code lives in `experiments/bem_on_baseline_data/`
  as the agent's own files. `csi_fit.py`, `csi_data.py` and
  `csi_forward_check.py` stay unedited; a thin runner sets the table path
  and the results folder, then calls them.
- New tables in `results/bem/baseline_data/fresnel_own_forward/2026-11-18/data/<shape>/synthetic_input.txt`,
  each with a `.sha256`. No CSI table is edited.

## Checks before a fit

1. The reader returns the generated scattered field to round-off.
2. Circle against the exact series at the five frequencies.
3. `csi_forward_check` on each new table: layout checks pass, and the
   mismatch on the true shape is at the accuracy rule's level, not at the
   0.1 to 0.7% of the CSI tables.
4. For reference, the difference between each new table and the frozen
   CSI table at each frequency. It should repeat the 1% check numbers of
   activity 07.

Send the coordinator the four check results before the first fit.

## Fixed settings (set before any result)

Exactly those of activity 07: centred 65 mm circle start, `modal_muller` +
`slider`, real data only, no localization, no warm-up, no noise level,
recovered contrast from the weak-scatterer start, series limit 1e-9,
13,412 work units, GPU; five ladder stages with quotas 1000, 1000, 1000,
1000, 4000, then the all-frequency stages. One GPU fit per shape, one
pass, no tuning, no rerun. Failures stay in the table. No stop on elapsed
time. Memory: start a fit only with 16.5 GiB available; at most two fits
at a time.

## What to report

For each of the four fits, beside the activity 07 numbers:

- outcome, last stage, work units, fit seconds, contrast;
- final area error, and the area error of every saved stage outline;
- data mismatch per frequency of the final fit;
- one figure in `figures/`: the four fitted outlines over the true ones,
  with the activity 07 outlines for comparison.

## Reading the result (fixed now)

Activity 07 references: circle 0.97%, star 2.34%, kite 3.80%, hook 3.59%.
On TG-002 data with 19 frequencies the recovered contrast-4 shapes reach
0.01 to 0.04% clean and 0.02 to 0.3% with 1% noise.

- All four at or below 0.3%, with smooth outlines: five frequencies are
  enough, and the wiggles of activity 07 come from the error in the CSI
  data.
- Any shape above 0.5%: five frequencies or the layout limit the fit even
  on accurate data. Stop and report; the coordinator then decides on a
  ten-frequency run on our own data.

## Budget

Four tables, four checks, four GPU fits (1 to 5 min each). No CPU
cross-check. Any further run needs the coordinator's word.

## Outputs

- Tables, checks and fits:
  `results/bem/baseline_data/fresnel_own_forward/2026-11-18/`
  (`data/`, `adapter_checks/`, `<shape>__c4/cuda/attempt_01/`, `logs/`).
- This folder: `results.md`, `figures/`.
- Commit by path and push after each step, failures included. At most
  about 5 MB committed; bulk stays local and ignored with its SHA-256.

## Commands

The runner writes the exact commands here before its first run.
